"""Danh hiệu chuỗi thắng và sự kiện SHUTDOWN.

Module thuần Python, không phụ thuộc Flask hay Supabase nên có thể nâng cấp
và kiểm thử độc lập.
"""
import json

WIN_STREAK_TITLES = {
    3: "HAT-TRICK!",
    4: "POKER!",
    5: "MEGA WIN!",
    6: "UNSTOPPABLE!",
    7: "TERMINATOR!",
    8: "MONSTER WIN!",
    9: "GODLIKE!",
    10: "BEYOND GODLIKE!",
}
WIN_STREAK_EVENT_PREFIX = "WIN_STREAK_EVENT:"

def get_win_streak_title(streak):
    try:
        value = int(streak or 0)
    except (TypeError, ValueError):
        value = 0
    if value < 3:
        return ""
    if value >= 10:
        return WIN_STREAK_TITLES[10]
    return WIN_STREAK_TITLES.get(value, "")

def get_win_streak_badge(streak):
    try:
        value = int(streak or 0)
    except (TypeError, ValueError):
        value = 0
    title = get_win_streak_title(value)
    if not title:
        return None
    return {"icon": "🔥", "title": title, "count": value, "label": f"{title} · {value} trận thắng"}

def is_ranked_match_for_streak(match, room=None):
    values = [(match or {}).get("match_mode"), (match or {}).get("mode"),
              (match or {}).get("match_type"), (room or {}).get("match_mode")]
    normalized = {str(v or "").strip().lower() for v in values if v is not None}
    return not bool(normalized & {"friendly", "giao_huu", "giao hữu"})

def build_win_streak_event(match, room, users_before):
    if not is_ranked_match_for_streak(match, room):
        return None
    winner_id = (match or {}).get("winner_id")
    loser_id = (match or {}).get("loser_id")
    if not winner_id or not loser_id:
        return None
    winner = (users_before or {}).get(winner_id, {})
    loser = (users_before or {}).get(loser_id, {})
    winner_name = winner.get("display_name") or "Người chiến thắng"
    loser_name = loser.get("display_name") or "Đối thủ"
    winner_old_streak = int(winner.get("streak", 0) or 0)
    loser_old_streak = int(loser.get("streak", 0) or 0)
    winner_new_streak = winner_old_streak + 1
    event_id = f"{(match or {}).get('id', 'match')}:{winner_id}:{winner_new_streak}:{loser_old_streak}"
    if loser_old_streak >= 3:
        return {"id": event_id, "kind": "shutdown", "title": "SHUTDOWN!",
                "subtitle": f"{winner_name} đã chấm dứt chuỗi {loser_old_streak} trận thắng của {loser_name}",
                "toast_title": "THÔNG BÁO HỆ THỐNG", "toast_duration": 8000, "overlay_duration": 4000,
                "winner_id": winner_id, "loser_id": loser_id, "winner_streak": winner_new_streak,
                "broken_streak": loser_old_streak}
    if winner_new_streak in WIN_STREAK_TITLES:
        title = WIN_STREAK_TITLES[winner_new_streak]
        return {"id": event_id, "kind": "milestone", "title": title,
                "subtitle": f"{winner_name} đã thắng {winner_new_streak} trận liên tiếp",
                "toast_title": "THÔNG BÁO HỆ THỐNG", "toast_duration": 6000, "overlay_duration": 4000,
                "winner_id": winner_id, "loser_id": loser_id, "winner_streak": winner_new_streak,
                "broken_streak": 0}
    return None

def encode_win_streak_room_note(event):
    if not event:
        return "Khách đã xác nhận kết quả."
    return WIN_STREAK_EVENT_PREFIX + json.dumps(event, ensure_ascii=False, separators=(",", ":"))

def parse_win_streak_room_note(note):
    raw = str(note or "")
    if not raw.startswith(WIN_STREAK_EVENT_PREFIX):
        return None
    try:
        event = json.loads(raw[len(WIN_STREAK_EVENT_PREFIX):])
        return event if isinstance(event, dict) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
