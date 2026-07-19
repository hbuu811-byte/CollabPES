"""Xóa bằng chứng, phòng, trận và tài khoản theo thứ tự an toàn.

Module không khai báo route; dependency được liên kết khi app khởi động.
"""

EXPORTED_NAMES = ['remove_match_dispute_evidence', 'delete_room_safe', 'delete_match_safe', 'delete_player_safe']

def configure(context):
    """Liên kết module với dependency hiện tại của ứng dụng."""
    globals().update(context)


def remove_match_dispute_evidence(match_id):
    if not match_id or db is None:
        return
    try:
        result = execute_query(
            db.table("match_disputes").select("evidence_path").eq("match_id", match_id),
            "list_match_evidence_for_cleanup",
            attempts=2,
        )
        for row in result.data or []:
            remove_dispute_evidence_object(row.get("evidence_path"))
    except Exception as exc:
        print(f"remove_match_dispute_evidence warning: {exc}")


def delete_room_safe(room_id):
    room = get_room(room_id)
    if not room:
        return

    if room.get("match_id"):
        delete_match_safe(room.get("match_id"))

    db.table("chat_messages").delete().eq("room_id", room_id).execute()
    db.table("match_rooms").delete().eq("id", room_id).execute()


def delete_match_safe(match_id):
    match = get_match(match_id)
    if match:
        reverse_confirmed_match_result(match)

    remove_match_dispute_evidence(match_id)
    db.table("match_rooms").update({
        "status": "cancelled",
        "match_id": None,
        "note": "Admin đã xóa trận liên kết.",
        "updated_at": now_iso(),
    }).eq("match_id", match_id).execute()

    db.table("matches").delete().eq("id", match_id).execute()


def delete_player_safe(user_id):
    user = get_user(user_id)
    if not user:
        return False, "Không tìm thấy tài khoản."

    if is_admin_user(user):
        return False, "Không được xóa tài khoản admin chính."

    for room in list_rooms():
        if user_id in [room.get("host_user_id"), room.get("guest_user_id")]:
            delete_room_safe(room["id"])

    for match in list_matches():
        if user_id in [match.get("player1_id"), match.get("player2_id")]:
            delete_match_safe(match["id"])

    for invite in list_invites():
        if user_id in [invite.get("from_user_id"), invite.get("to_user_id")]:
            db.table("match_invites").delete().eq("id", invite["id"]).execute()

    db.table("chat_messages").delete().eq("user_id", user_id).execute()
    db.table("user_devices").delete().eq("user_id", user_id).execute()
    db.table("users").delete().eq("id", user_id).execute()
    return True, ""
