"""Ghi nhận các trận thua do bỏ cuộc vào bảng matches.

Không thay đổi công thức RP. Module chỉ bảo đảm mọi lần phạt bỏ cuộc có một
bản ghi lịch sử tương ứng, kể cả khi người chơi bỏ cuộc trước lúc quay đội.
"""

EXPORTED_NAMES = [
    "record_room_forfeit_match",
    "is_forfeit_match",
    "forfeit_loser_id",
    "forfeit_display_note",
]


def configure(context):
    """Liên kết dependency từ app.py mà không tạo import vòng."""
    globals().update(context)


def _safe_delta(value):
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError, OverflowError):
        return 0


def _forfeit_marker(offender_role):
    role = "host" if str(offender_role or "").lower() == "host" else "guest"
    return f"[FORFEIT:{role}]"


def forfeit_display_note(match_or_note):
    """Bỏ marker kỹ thuật trước khi đưa ghi chú ra giao diện."""
    if isinstance(match_or_note, dict):
        note = str(match_or_note.get("note") or "")
    else:
        note = str(match_or_note or "")
    for marker in ("[FORFEIT:host]", "[FORFEIT:guest]"):
        if note.lower().startswith(marker.lower()):
            return note[len(marker):].strip()
    return note


def is_forfeit_match(match):
    """Nhận diện bản ghi bỏ cuộc mới và dữ liệu bỏ cuộc từ các bản cũ."""
    if not isinstance(match, dict) or str(match.get("status") or "") != "cancelled":
        return False
    note = str(match.get("note") or "").casefold()
    if "[forfeit:host]" in note or "[forfeit:guest]" in note:
        return True
    if match.get("loser_id"):
        return True
    if any(token in note for token in ("bỏ cuộc", "bỏ trận", "bỏ dở", "rời phòng sau khi")):
        return True
    delta1 = _safe_delta(match.get("delta1"))
    delta2 = _safe_delta(match.get("delta2"))
    return (delta1 < 0) != (delta2 < 0)


def forfeit_loser_id(match):
    """Trả về ID người bị tính thua, hỗ trợ cả dữ liệu cũ không có loser_id."""
    if not is_forfeit_match(match):
        return None
    if match.get("loser_id"):
        return match.get("loser_id")

    note = str(match.get("note") or "").casefold()
    if "[forfeit:host]" in note:
        return match.get("player1_id")
    if "[forfeit:guest]" in note:
        return match.get("player2_id")

    delta1 = _safe_delta(match.get("delta1"))
    delta2 = _safe_delta(match.get("delta2"))
    if delta1 < delta2 and delta1 < 0:
        return match.get("player1_id")
    if delta2 < delta1 and delta2 < 0:
        return match.get("player2_id")
    return None


def _history_payload(room, offender_role, penalty_delta, reason, event_type):
    role = "host" if str(offender_role or "").lower() == "host" else "guest"
    host_id = room.get("host_user_id")
    guest_id = room.get("guest_user_id")
    loser_id = host_id if role == "host" else guest_id
    delta = _safe_delta(penalty_delta)
    if delta > 0:
        delta = -delta
    note = f"{_forfeit_marker(role)} {str(reason or 'Người chơi bỏ cuộc.').strip()}"

    payload = {
        "player1_id": host_id,
        "player2_id": guest_id,
        "status": "cancelled",
        "delta1": delta if role == "host" else 0,
        "delta2": delta if role == "guest" else 0,
        "loser_id": loser_id,
        "note": note,
        "rp_details": {
            "source": "room_forfeit",
            "event_type": str(event_type or "manual_forfeit"),
            "offender_role": role,
            "penalty_delta": delta,
        },
        "updated_at": now_iso(),
    }

    optional_room_fields = {
        "team1": "host_team",
        "team2": "guest_team",
        "team1_overall": "host_team_overall",
        "team2_overall": "guest_team_overall",
        "team1_logo_url": "host_team_logo_url",
        "team2_logo_url": "guest_team_logo_url",
        "team1_league": "host_team_league",
        "team2_league": "guest_team_league",
    }
    for match_field, room_field in optional_room_fields.items():
        value = room.get(room_field)
        if value not in (None, ""):
            payload[match_field] = value
    return payload


def _minimal_payload(payload):
    """Payload dự phòng, chỉ dùng các cột đã tồn tại từ những bản đầu."""
    keys = (
        "player1_id", "player2_id", "status", "delta1", "delta2", "note", "updated_at",
    )
    return {key: payload.get(key) for key in keys}


def record_room_forfeit_match(room, offender_role, penalty_delta, reason, event_type="manual_forfeit"):
    """Cập nhật hoặc tạo một bản ghi lịch sử cho lần bỏ cuộc.

    - Có match_id: chuyển trận hiện tại thành bản ghi bỏ cuộc.
    - Chưa quay đội/chưa có match_id: tạo một dòng matches mới.
    - Nếu schema cũ thiếu cột loser_id/rp_details, tự thử lại bằng payload tối thiểu.
    """
    if not isinstance(room, dict):
        return None
    if not room.get("host_user_id") or not room.get("guest_user_id"):
        return None

    payload = _history_payload(room, offender_role, penalty_delta, reason, event_type)
    match_id = room.get("match_id")

    if match_id:
        try:
            execute_query(
                db.table("matches").update(payload).eq("id", match_id),
                "record_forfeit_existing_match",
                attempts=2,
            )
        except Exception as exc:
            app.logger.warning("Forfeit history full update failed; retrying minimal payload: %s", exc)
            execute_query(
                db.table("matches").update(_minimal_payload(payload)).eq("id", match_id),
                "record_forfeit_existing_match_minimal",
                attempts=2,
            )
        cache_delete("_rz_matches_all")
        return match_id

    try:
        result = execute_query(
            db.table("matches").insert(payload),
            "record_forfeit_new_match",
            attempts=2,
        )
    except Exception as exc:
        app.logger.warning("Forfeit history full insert failed; retrying minimal payload: %s", exc)
        result = execute_query(
            db.table("matches").insert(_minimal_payload(payload)),
            "record_forfeit_new_match_minimal",
            attempts=2,
        )

    created = (result.data or [None])[0] if result else None
    created_id = created.get("id") if isinstance(created, dict) else None
    if created_id:
        try:
            execute_query(
                db.table("match_rooms").update({
                    "match_id": created_id,
                    "updated_at": now_iso(),
                }).eq("id", room.get("id")).is_("match_id", "null"),
                "attach_forfeit_match_to_room",
                attempts=2,
            )
        except Exception as exc:
            # Bản ghi lịch sử đã tồn tại; lỗi liên kết phụ không được xóa lịch sử.
            app.logger.warning("Could not attach forfeit match to room %s: %s", room.get("id"), exc)
    cache_delete("_rz_matches_all")
    return created_id
