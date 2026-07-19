"""Phát lại lịch sử BXH sau khi Admin sửa tỷ số hoặc trạng thái trận.

Module không khai báo route; dependency được liên kết khi app khởi động.
"""

EXPORTED_NAMES = ['rebuild_rankings_after_admin_change']

def configure(context):
    """Liên kết module với dependency hiện tại của ứng dụng."""
    globals().update(context)


def rebuild_rankings_after_admin_change(
    match_id, override_payload, *, lock_token, actor_id=None
):
    """Phát lại toàn bộ lịch sử confirmed theo ``created_at`` gốc.

    - Không ghi ``created_at`` vào bất kỳ payload nào.
    - Giữ lại RP/thống kê gốc không sinh ra từ bảng matches.
    - Có rollback best-effort nếu một cập nhật giữa chừng thất bại.
    """
    require_db()
    _require_owned_ranking_rebuild_lock(lock_token)

    users_result = execute_query(
        db.table("users").select(
            "id,rank_points,total_matches,wins,draws,losses,goals_for,goals_against,streak,loss_streak"
        ),
        "admin_rebuild_load_users",
    )
    matches_result = execute_query(
        db.table("matches").select("*").order("created_at", desc=False),
        "admin_rebuild_load_matches",
    )
    rooms_result = execute_query(
        db.table("match_rooms").select("match_id,host_user_id"),
        "admin_rebuild_load_hosts",
        attempts=2,
    )
    users_rows = [dict(row) for row in (users_result.data or [])]
    matches_rows = [dict(row) for row in (matches_result.data or [])]
    user_original = {str(row.get("id")): row for row in users_rows if row.get("id")}
    match_original = {str(row.get("id")): row for row in matches_rows if row.get("id")}
    host_by_match = {
        str(row.get("match_id")): row.get("host_user_id")
        for row in (rooms_result.data or []) if row.get("match_id")
    }

    override = {key: value for key, value in dict(override_payload or {}).items() if key != "created_at"}
    user_updates, match_updates = build_replay_plan(
        users=users_rows,
        matches=matches_rows,
        overrides={str(match_id): override},
        calculate_deltas=calculate_ranked_deltas,
        get_rank_level=get_rank_level,
        apply_host_factor=apply_host_xp_factor,
        host_by_match=host_by_match,
        default_points=DEFAULT_POINTS,
        placement_matches=PLACEMENT_MATCHES,
        host_win_factor=HOST_WIN_FACTOR,
        formula_version=RP_FORMULA_VERSION,
        formula_summary=formula_summary,
        seed_namespace=RP_RANDOM_SEED_NAMESPACE,
    )

    changed_matches = {
        current_id: dict(payload)
        for current_id, payload in match_updates.items()
        if _payload_differs(match_original.get(str(current_id)), payload)
    }
    changed_users = {
        user_id: dict(payload)
        for user_id, payload in user_updates.items()
        if _payload_differs(user_original.get(str(user_id)), payload)
    }

    applied_matches = []
    applied_users = []
    try:
        _require_owned_ranking_rebuild_lock(lock_token)
        for current_match_id, payload in changed_matches.items():
            safe_payload = {key: value for key, value in payload.items() if key != "created_at"}
            safe_payload["updated_at"] = now_iso()
            result = execute_query(
                db.table("matches").update(safe_payload).eq("id", current_match_id),
                f"admin_rebuild_match:{current_match_id}",
            )
            if not (result.data or []):
                raise RuntimeError(f"Không cập nhật được trận {current_match_id}.")
            applied_matches.append(str(current_match_id))

        _require_owned_ranking_rebuild_lock(lock_token)
        for user_id, payload in changed_users.items():
            result = execute_query(
                db.table("users").update(payload).eq("id", user_id),
                f"admin_rebuild_user:{user_id}",
            )
            if not (result.data or []):
                raise RuntimeError(f"Không cập nhật được người chơi {user_id}.")
            applied_users.append(str(user_id))

        target_match = dict(match_original.get(str(match_id)) or get_match(match_id) or {})
        target_match.update(override)
        sync_room_after_admin_match_change(
            match_original.get(str(match_id)) or target_match,
            target_match,
            actor_id=actor_id,
        )
    except Exception:
        # Rollback best-effort. Không bao giờ phục hồi/ghi created_at vì nó chưa bị sửa.
        for user_id in reversed(applied_users):
            original = user_original.get(user_id) or {}
            restore = {
                key: original.get(key)
                for key in (
                    "rank_points", "total_matches", "wins", "draws", "losses",
                    "goals_for", "goals_against", "streak", "loss_streak"
                )
            }
            try:
                db.table("users").update(restore).eq("id", user_id).execute()
            except Exception as rollback_exc:
                app.logger.exception("rollback user %s failed: %s", user_id, rollback_exc)
        for current_match_id in reversed(applied_matches):
            original = match_original.get(current_match_id) or {}
            restore = {
                key: original.get(key)
                for key in (
                    "score1", "score2", "status", "note", "delta1", "delta2",
                    "winner_id", "loser_id", "confirmed_by_id",
                    "rp_formula_version", "rp_details", "updated_at"
                )
            }
            try:
                db.table("matches").update(restore).eq("id", current_match_id).execute()
            except Exception as rollback_exc:
                app.logger.exception("rollback match %s failed: %s", current_match_id, rollback_exc)
        raise

    cache_delete("_rz_players_all", "_rz_users_map", "_rz_matches_all", "_rz_rooms_all")
    ttl_cache_delete("players_raw", "achievement_map", "rooms_raw")
    try:
        sync_achievements_for_users(list(user_updates.keys()))
    except Exception as exc:
        app.logger.warning("admin rebuild achievement warning: %s", exc)
    return len(changed_matches), len(changed_users)
