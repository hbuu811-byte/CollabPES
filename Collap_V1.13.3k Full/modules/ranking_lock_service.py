"""Khóa phát lại BXH và các helper so sánh trạng thái trận/phòng.

Module không khai báo route; dependency được liên kết khi app khởi động.
"""

EXPORTED_NAMES = ['_safe_int', '_load_ranking_rebuild_lock', '_ranking_rebuild_lock_is_expired', 'get_active_ranking_rebuild_lock', 'assert_ranking_rebuild_not_running', 'acquire_ranking_rebuild_lock', 'release_ranking_rebuild_lock', '_require_owned_ranking_rebuild_lock', '_match_state_signature', '_payload_differs', '_room_status_from_match_status']

def configure(context):
    """Liên kết module với dependency hiện tại của ứng dụng."""
    globals().update(context)


def _safe_int(value, default=0):
    """Convert Supabase/form numeric values to a real integer safely."""
    try:
        return int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return int(default)


def _load_ranking_rebuild_lock(allow_failure=False):
    if db is None:
        return None
    try:
        result = execute_query(
            db.table("system_settings").select("setting_value")
            .eq("setting_key", RANKING_REBUILD_LOCK_KEY).limit(1),
            "load_ranking_rebuild_lock",
            attempts=1,
        )
        row = (result.data or [None])[0]
        value = (row or {}).get("setting_value")
        return dict(value) if isinstance(value, dict) else None
    except Exception as exc:
        app.logger.warning("load ranking rebuild lock failed: %s", exc)
        if allow_failure:
            return None
        raise


def _ranking_rebuild_lock_is_expired(lock_info):
    if not lock_info:
        return True
    expires_at = aware_utc(parse_dt(lock_info.get("expires_at")))
    return not expires_at or expires_at <= aware_utc(now_dt())


def get_active_ranking_rebuild_lock(clean_stale=True):
    lock_info = _load_ranking_rebuild_lock()
    if not lock_info:
        return None
    if _ranking_rebuild_lock_is_expired(lock_info):
        if clean_stale:
            try:
                db.table("system_settings").delete().eq(
                    "setting_key", RANKING_REBUILD_LOCK_KEY
                ).execute()
            except Exception as exc:
                app.logger.warning("cleanup stale ranking lock failed: %s", exc)
        return None
    return lock_info


def assert_ranking_rebuild_not_running():
    lock_info = get_active_ranking_rebuild_lock()
    if lock_info:
        raise ValueError(
            "Admin đang tính lại lịch sử BXH. Vui lòng thử lại sau khi thao tác hoàn tất."
        )


def acquire_ranking_rebuild_lock(actor_id=None, match_id=None):
    """Giành khóa DB duy nhất trước khi sửa lịch sử/RP.

    Dùng INSERT vào setting_key duy nhất thay vì khóa RAM, vì Vercel có thể chạy
    nhiều instance cùng lúc. Khóa hết hạn tự động để tránh kẹt khi request bị dừng.
    """
    require_db()
    existing = get_active_ranking_rebuild_lock()
    if existing:
        raise ValueError("Một thao tác tính lại BXH khác đang chạy. Vui lòng thử lại sau.")

    token = secrets.token_hex(16)
    payload = {
        "token": token,
        "actor_id": actor_id,
        "match_id": match_id,
        "created_at": now_iso(),
        "expires_at": future_iso(RANKING_REBUILD_LOCK_SECONDS),
    }
    try:
        db.table("system_settings").insert({
            "setting_key": RANKING_REBUILD_LOCK_KEY,
            "setting_value": payload,
            "updated_at": now_iso(),
        }).execute()
    except Exception as exc:
        # Có thể instance khác vừa chèn khóa sau lần đọc phía trên.
        active = get_active_ranking_rebuild_lock(clean_stale=False)
        if active:
            raise ValueError("Một thao tác tính lại BXH khác đang chạy. Vui lòng thử lại sau.") from exc
        raise

    try:
        verified = get_active_ranking_rebuild_lock(clean_stale=False)
        if not verified or verified.get("token") != token:
            raise ValueError("Không thể giành khóa tính lại BXH an toàn.")

        # Nếu một request xác nhận đã claim trận trước khi khóa được tạo, không phát lại
        # song song. Request xác nhận sẽ tự trả trạng thái về; Admin chỉ cần thử lại.
        processing = execute_query(
            db.table("matches").select("id").eq("status", "processing_result").limit(1),
            "check_processing_result_before_rebuild",
            attempts=1,
        )
        if processing.data:
            raise ValueError("Có kết quả trận đang được xác nhận. Vui lòng thử lại sau vài giây.")
        return token
    except Exception:
        release_ranking_rebuild_lock(token)
        raise


def release_ranking_rebuild_lock(token):
    if not token or db is None:
        return
    try:
        active = _load_ranking_rebuild_lock(allow_failure=True)
        if active and active.get("token") == token:
            db.table("system_settings").delete().eq(
                "setting_key", RANKING_REBUILD_LOCK_KEY
            ).execute()
    except Exception as exc:
        app.logger.warning("release ranking rebuild lock failed: %s", exc)


def _require_owned_ranking_rebuild_lock(token):
    active = get_active_ranking_rebuild_lock(clean_stale=False)
    if not active or active.get("token") != token:
        raise ValueError("Khóa tính lại BXH đã mất hoặc hết hạn; chưa lưu thay đổi.")


def _match_state_signature(match):
    return (
        str((match or {}).get("status") or ""),
        (match or {}).get("score1"),
        (match or {}).get("score2"),
        str((match or {}).get("updated_at") or ""),
    )


def _payload_differs(current, payload):
    for key, value in dict(payload or {}).items():
        if key in {"created_at", "updated_at"}:
            continue
        if (current or {}).get(key) != value:
            return True
    return False


def _room_status_from_match_status(status):
    return {
        "playing": "playing",
        "waiting_confirm": "waiting_result_confirm",
        "disputed": "disputed",
        "confirmed": "confirmed",
        "cancelled": "cancelled",
    }.get(str(status or ""), str(status or ""))
