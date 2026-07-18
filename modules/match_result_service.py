"""Áp dụng kết quả, xử lý tranh chấp, cập nhật và hoàn tác thống kê/RP.

Module không khai báo route; dependency được liên kết khi app khởi động.
"""

EXPORTED_NAMES = ['sync_room_after_admin_match_change', 'apply_match_result', 'resolve_match_dispute_with_result', 'cancel_match_dispute', 'update_player_after_match', 'reverse_player_match_stats', 'reverse_confirmed_match_result']

def configure(context):
    """Liên kết module với dependency hiện tại của ứng dụng."""
    globals().update(context)


def sync_room_after_admin_match_change(match, target, actor_id=None):
    """Đồng bộ đúng cột host_score/guest_score mà không sửa created_at."""
    if not match or not match.get("id"):
        return
    result = execute_query(
        db.table("match_rooms").select(
            "id,match_id,host_user_id,guest_user_id,status,host_score,guest_score,note,confirmed_by_id,state_expires_at"
        ).eq("match_id", match.get("id")).limit(1),
        "load_room_for_admin_match_sync",
        attempts=2,
    )
    room = (result.data or [None])[0]
    if not room:
        return

    status = str(target.get("status", match.get("status")) or "")
    score1 = target.get("score1", match.get("score1"))
    score2 = target.get("score2", match.get("score2"))
    p1_id = str(match.get("player1_id") or "")
    p2_id = str(match.get("player2_id") or "")
    host_id = str(room.get("host_user_id") or "")
    if host_id == p2_id:
        host_score, guest_score = score2, score1
    else:
        # Mặc định cấu trúc hiện hành: player1 là chủ phòng.
        host_score, guest_score = score1, score2

    room_payload = {
        "host_score": host_score,
        "guest_score": guest_score,
        "status": _room_status_from_match_status(status),
        "note": target.get("note", match.get("note")),
        "updated_at": now_iso(),
    }
    if status == "confirmed":
        room_payload["confirmed_by_id"] = target.get("confirmed_by_id") or actor_id
        room_payload["state_expires_at"] = None
    elif status == "waiting_confirm":
        room_payload["confirmed_by_id"] = None
        room_payload["state_expires_at"] = future_iso(RESULT_CONFIRM_TIMEOUT_SECONDS)
    elif status == "playing":
        room_payload["confirmed_by_id"] = None
        room_payload["state_expires_at"] = future_iso(ROOM_MATCH_INACTIVITY_TIMEOUT_SECONDS)
    else:
        room_payload["confirmed_by_id"] = None
        room_payload["state_expires_at"] = None

    execute_query(
        db.table("match_rooms").update(room_payload).eq("id", room.get("id")),
        "sync_room_after_admin_match_change",
        attempts=2,
    )


def apply_match_result(match):
    """Apply one ranked result exactly once with clear validation and recovery.

    The match row is claimed by changing its status to ``processing_result``.
    A repeated click cannot apply RP twice, even when requests overlap.
    """
    if not match or not match.get("id"):
        raise ValueError("Thiếu dữ liệu trận đấu.")
    # Không cho request người chơi ghi RP trong lúc Admin đang phát lại lịch sử.
    # Trận confirmed đã có delta vẫn được trả idempotent phía dưới.
    if match.get("status") != "confirmed":
        assert_ranking_rebuild_not_running()
    if match.get("score1") is None or match.get("score2") is None:
        raise ValueError("Trận chưa có tỉ số.")

    # Idempotency: a confirmed match with stored deltas was already applied.
    if match.get("status") == "confirmed" and match.get("delta1") is not None and match.get("delta2") is not None:
        return _safe_int(match.get("delta1")), _safe_int(match.get("delta2"))
    if match.get("status") == "processing_result":
        raise ValueError("Kết quả đang được xử lý. Không cần nhấn xác nhận lần nữa.")

    player1_id = match.get("player1_id")
    player2_id = match.get("player2_id")
    if not player1_id or not player2_id:
        raise ValueError("Trận đấu thiếu ID của một trong hai người chơi.")

    player1 = get_user(player1_id)
    player2 = get_user(player2_id)
    if not player1 or not player2:
        missing = []
        if not player1:
            missing.append("người chơi 1")
        if not player2:
            missing.append("người chơi 2")
        raise ValueError("Không tìm thấy dữ liệu " + " và ".join(missing) + ". Chưa cập nhật RP.")

    score1 = _safe_int(match.get("score1"), -1)
    score2 = _safe_int(match.get("score2"), -1)
    if score1 < 0 or score2 < 0:
        raise ValueError("Tỉ số không hợp lệ.")

    original_status = str(match.get("status") or "waiting_confirm")
    try:
        claim = execute_query(
            db.table("matches").update({
                "status": "processing_result",
                "updated_at": now_iso(),
            }).eq("id", match["id"]).eq("status", original_status),
            "claim_match_result",
        )
        if not (claim.data or []):
            fresh = get_match(match["id"])
            if fresh and fresh.get("status") == "confirmed":
                return _safe_int(fresh.get("delta1")), _safe_int(fresh.get("delta2"))
            raise ValueError("Kết quả đã được một yêu cầu khác xử lý hoặc trạng thái trận đã thay đổi.")

        # Đóng khe race: Admin có thể tạo khóa sau lần kiểm tra đầu nhưng trước khi
        # request này claim được dòng trận. Khi đó trả status về và dừng trước khi ghi RP.
        assert_ranking_rebuild_not_running()

        delta1, delta2 = calculate_deltas(
            player1, player2, score1, score2,
            match.get("team1"), match.get("team2"),
            match.get("team1_overall"), match.get("team2_overall"),
            match.get("team1_tier"), match.get("team2_tier"),
            rng=random.Random(f"{RP_RANDOM_SEED_NAMESPACE}|{match.get('id')}"),
        )
        delta1, delta2 = _safe_int(delta1), _safe_int(delta2)
        # Không còn fallback -20. Nếu engine trả delta sai dấu/0 cho trận thắng-thua,
        # dừng xử lý và ghi lỗi thay vì âm thầm che lỗi bằng một giá trị hợp lệ giả.
        delta1, delta2 = validate_ranked_deltas(score1, score2, delta1, delta2)

        # The 0.95 coefficient belongs to the actual room host, not implicitly player1.
        host_user_id = match.get("host_user_id")
        if not host_user_id:
            try:
                room_row = execute_query(
                    db.table("match_rooms").select("host_user_id").eq("match_id", match["id"]).limit(1),
                    "get_result_host",
                    attempts=2,
                )
                host_user_id = (room_row.data or [{}])[0].get("host_user_id")
            except Exception as exc:
                print(f"get_result_host warning match={match.get('id')}: {type(exc).__name__}: {exc}")
        if str(host_user_id or "") == str(player1_id) and score1 > score2:
            delta1 = _safe_int(apply_host_xp_factor(delta1, match.get("host_xp_factor", HOST_WIN_FACTOR)))
            if _safe_int(player1.get("total_matches")) < PLACEMENT_MATCHES:
                delta1 = max(22, min(29, delta1))
        elif str(host_user_id or "") == str(player2_id) and score2 > score1:
            delta2 = _safe_int(apply_host_xp_factor(delta2, match.get("host_xp_factor", HOST_WIN_FACTOR)))
            if _safe_int(player2.get("total_matches")) < PLACEMENT_MATCHES:
                delta2 = max(22, min(29, delta2))

        update_player_after_match(player1, delta1, score1, score2)
        update_player_after_match(player2, delta2, score2, score1)

        execute_query(
            db.table("matches").update({
                "delta1": int(delta1),
                "delta2": int(delta2),
                "rp_formula_version": RP_FORMULA_VERSION,
                "rp_details": {
                    "source": "modules/rp_formula.py",
                    "formula": formula_summary(),
                    "seed": f"{RP_RANDOM_SEED_NAMESPACE}|{match.get('id')}",
                    "delta1": int(delta1),
                    "delta2": int(delta2),
                },
                "status": "confirmed",
                "note": "Đã xác nhận.",
                "updated_at": now_iso(),
            }).eq("id", match["id"]).eq("status", "processing_result"),
            "finalize_match_result",
        )
    except Exception as exc:
        print(f"apply_match_result ERROR match={match.get('id')} status={original_status}: {type(exc).__name__}: {exc}")
        try:
            execute_query(
                db.table("matches").update({"status": original_status, "updated_at": now_iso()})
                .eq("id", match["id"]).eq("status", "processing_result"),
                "restore_match_after_result_error",
                attempts=2,
            )
        except Exception as restore_exc:
            print(f"apply_match_result RESTORE ERROR match={match.get('id')}: {type(restore_exc).__name__}: {restore_exc}")
        raise

    # Badge synchronization is auxiliary and must never invalidate a confirmed match.
    try:
        sync_achievements_for_users([player1_id, player2_id])
    except Exception as exc:
        print(f"achievement_sync warning match={match.get('id')}: {type(exc).__name__}: {exc}")
    return int(delta1), int(delta2)


def resolve_match_dispute_with_result(
    dispute,
    score1,
    score2,
    resolved_by_id,
    resolution_type,
    resolution_note="",
    final_dispute_status="resolved",
):
    if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
        raise ValueError("Tranh chấp này đã được xử lý hoặc không còn hiệu lực.")

    score1 = parse_score(score1)
    score2 = parse_score(score2)
    if score1 is None or score2 is None:
        raise ValueError("Trận được công nhận phải có đủ hai tỷ số.")

    match_id = dispute.get("match_id")
    lock_token = acquire_ranking_rebuild_lock(resolved_by_id, match_id)
    try:
        match = get_match(match_id)
        if not match or match.get("status") != "disputed":
            raise ValueError("Trận đấu không còn ở trạng thái tranh chấp.")

        final_note = (
            resolution_note or "Tranh chấp đã được xử lý và kết quả được công nhận."
        ).strip()[:500]
        override = {
            "score1": score1,
            "score2": score2,
            "status": "confirmed",
            "confirmed_by_id": resolved_by_id,
            "note": final_note,
        }
        rebuild_rankings_after_admin_change(
            match_id, override, lock_token=lock_token, actor_id=resolved_by_id
        )

        execute_query(
            db.table("match_disputes").update({
                "status": final_dispute_status,
                "resolution_type": resolution_type,
                "resolution_score1": score1,
                "resolution_score2": score2,
                "resolution_note": final_note,
                "resolved_by_id": resolved_by_id,
                "resolved_at": now_iso(),
                "updated_at": now_iso(),
            }).eq("id", dispute.get("id")).in_("status", list(DISPUTE_PENDING_STATUSES)),
            "finish_match_dispute_chronologically",
        )

        resolved_match = get_match(match_id) or {}
        delta1 = _safe_int(resolved_match.get("delta1"))
        delta2 = _safe_int(resolved_match.get("delta2"))
        users = users_map()
        p1_name = users.get(match.get("player1_id"), {}).get("display_name", "Player 1")
        p2_name = users.get(match.get("player2_id"), {}).get("display_name", "Player 2")
        create_notifications_for_users(
            [match.get("player1_id"), match.get("player2_id")],
            "✅ Tranh chấp đã được xử lý",
            f"Trận {p1_name} {score1} - {score2} {p2_name}: {final_note}",
            f"/room/{dispute.get('room_id')}",
            "dispute_resolved",
        )
        return delta1, delta2
    finally:
        release_ranking_rebuild_lock(lock_token)


def cancel_match_dispute(dispute, resolved_by_id, resolution_note=""):
    if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
        raise ValueError("Tranh chấp này đã được xử lý hoặc không còn hiệu lực.")

    match = get_match(dispute.get("match_id"))
    if not match or match.get("status") != "disputed":
        raise ValueError("Trận đấu không còn ở trạng thái tranh chấp.")

    final_note = (resolution_note or "Admin đã hủy trận tranh chấp; không cộng hoặc trừ điểm.").strip()[:500]
    execute_query(
        db.table("matches").update({
            "status": "cancelled",
            "note": final_note,
            "updated_at": now_iso(),
        }).eq("id", match.get("id")),
        "cancel_disputed_match",
    )
    execute_query(
        db.table("match_rooms").update({
            "status": "cancelled",
            "note": final_note,
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).eq("id", dispute.get("room_id")),
        "cancel_disputed_room",
    )
    execute_query(
        db.table("match_disputes").update({
            "status": "resolved",
            "resolution_type": "cancelled",
            "resolution_note": final_note,
            "resolved_by_id": resolved_by_id,
            "resolved_at": now_iso(),
            "updated_at": now_iso(),
        }).eq("id", dispute.get("id")),
        "cancel_match_dispute",
    )

    users = users_map()
    p1_name = users.get(match.get("player1_id"), {}).get("display_name", "Player 1")
    p2_name = users.get(match.get("player2_id"), {}).get("display_name", "Player 2")
    create_notifications_for_users(
        [match.get("player1_id"), match.get("player2_id")],
        "🚫 Trận tranh chấp đã bị hủy",
        f"Trận giữa {p1_name} và {p2_name} đã được Admin hủy. Không ai bị cộng hoặc trừ điểm.",
        "/matches",
        "dispute_cancelled",
    )


def update_player_after_match(player, delta, goals_for, goals_against):
    win = 1 if goals_for > goals_against else 0
    draw = 1 if goals_for == goals_against else 0
    loss = 1 if goals_for < goals_against else 0

    delta = _safe_int(delta)
    goals_for = _safe_int(goals_for)
    goals_against = _safe_int(goals_against)
    new_points = max(0, _safe_int(player.get("rank_points")) + delta)
    current_streak = int(player.get("streak", 0) or 0)
    new_streak = current_streak + 1 if win else 0 if loss else current_streak

    execute_query(
        db.table("users").update({
            "rank_points": new_points,
            "total_matches": _safe_int(player.get("total_matches")) + 1,
            "wins": _safe_int(player.get("wins")) + win,
            "draws": _safe_int(player.get("draws")) + draw,
            "losses": _safe_int(player.get("losses")) + loss,
            "goals_for": _safe_int(player.get("goals_for")) + goals_for,
            "goals_against": _safe_int(player.get("goals_against")) + goals_against,
            "streak": new_streak,
        }).eq("id", player["id"]),
        f"update_player_after_match:{player.get('id')}",
    )
    ttl_cache_delete("players_raw", "achievement_map")




def reverse_player_match_stats(player, delta, goals_for, goals_against):
    """Hoàn tác đúng một trận đã áp dụng, không đụng tới dữ liệu người chơi khác."""
    if not player:
        return

    win = 1 if goals_for > goals_against else 0
    draw = 1 if goals_for == goals_against else 0
    loss = 1 if goals_for < goals_against else 0

    db.table("users").update({
        "rank_points": max(0, int(player.get("rank_points", 0) or 0) - int(delta or 0)),
        "total_matches": max(0, int(player.get("total_matches", 0) or 0) - 1),
        "wins": max(0, int(player.get("wins", 0) or 0) - win),
        "draws": max(0, int(player.get("draws", 0) or 0) - draw),
        "losses": max(0, int(player.get("losses", 0) or 0) - loss),
        "goals_for": max(0, int(player.get("goals_for", 0) or 0) - int(goals_for or 0)),
        "goals_against": max(0, int(player.get("goals_against", 0) or 0) - int(goals_against or 0)),
        # Không thể suy ngược chính xác chuỗi thắng lịch sử nếu có trận mới hơn.
        # Đặt về 0 để tránh giữ chuỗi thắng sai sau khi Admin sửa/xóa trận.
        "streak": 0,
    }).eq("id", player["id"]).execute()


def reverse_confirmed_match_result(match):
    """Hoàn tác một trận confirmed bằng delta đã lưu, không reset toàn bộ BXH."""
    if not match or match.get("status") != "confirmed":
        return False
    if match.get("score1") is None or match.get("score2") is None:
        return False

    player1 = get_user(match.get("player1_id"))
    player2 = get_user(match.get("player2_id"))
    if not player1 or not player2:
        return False

    score1 = int(match.get("score1") or 0)
    score2 = int(match.get("score2") or 0)
    reverse_player_match_stats(player1, int(match.get("delta1", 0) or 0), score1, score2)
    reverse_player_match_stats(player2, int(match.get("delta2", 0) or 0), score2, score1)
    return True
