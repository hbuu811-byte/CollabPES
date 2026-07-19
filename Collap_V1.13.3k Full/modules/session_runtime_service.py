"""Quản lý thời gian không hoạt động và chính sách polling.

Module thuần, không phụ thuộc Flask/Supabase để tránh dồn thêm nghiệp vụ vào app.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

IDLE_TIMEOUT_SECONDS = 60 * 60
IDLE_WARNING_SECONDS = 5 * 60
ACTIVITY_SYNC_SECONDS = 5 * 60

# Không tự đăng xuất trong các trạng thái cần hoàn tất trận đấu.
PROTECTED_ROOM_STATUSES = {
    "playing",
    "friendly_playing",
    "waiting_result_confirm",
    "waiting_confirm",
    "disputed",
}


@dataclass(frozen=True)
class IdleDecision:
    expired: bool
    protected: bool
    remaining_seconds: int


def room_blocks_idle_logout(room: Mapping[str, Any] | None) -> bool:
    if not room:
        return False
    status = str(room.get("status") or "").strip().lower()
    has_two_players = bool(room.get("host_user_id") and room.get("guest_user_id"))
    return has_two_players and status in PROTECTED_ROOM_STATUSES


def idle_decision(*, now_ts: int, last_activity_ts: int, room: Mapping[str, Any] | None = None) -> IdleDecision:
    elapsed = max(0, int(now_ts) - int(last_activity_ts))
    remaining = max(0, IDLE_TIMEOUT_SECONDS - elapsed)
    protected = room_blocks_idle_logout(room)
    return IdleDecision(
        expired=elapsed >= IDLE_TIMEOUT_SECONDS and not protected,
        protected=protected,
        remaining_seconds=remaining,
    )


def client_config() -> dict[str, int]:
    return {
        "idle_timeout_seconds": IDLE_TIMEOUT_SECONDS,
        "warning_seconds": IDLE_WARNING_SECONDS,
        "activity_sync_seconds": ACTIVITY_SYNC_SECONDS,
    }
