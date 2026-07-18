"""Nghiệp vụ Admin chỉnh kết quả trận.

Module này không phụ thuộc Flask. app.py chỉ truyền các hàm DB/RP cần thiết vào,
nhờ đó phần quản lý trận không còn chồng trực tiếp với các route khác.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass
class AdminMatchEditResult:
    ok: bool
    message: str
    category: str = "success"
    action: str = ""


def parse_score(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        score = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("Tỷ số phải là số nguyên.")
    if score < 0 or score > 99:
        raise ValueError("Tỷ số phải nằm trong khoảng 0–99.")
    return score


def score_changed(match: Mapping[str, Any], score1: int | None, score2: int | None) -> bool:
    return score1 != match.get("score1") or score2 != match.get("score2")


def recalculate_confirmed_match(
    *,
    match: dict[str, Any],
    score1: int,
    score2: int,
    note: str,
    reverse_result: Callable[[dict[str, Any]], bool],
    update_match: Callable[[dict[str, Any]], None],
    apply_result: Callable[[dict[str, Any]], Any],
    sync_room: Callable[[dict[str, Any]], None],
) -> AdminMatchEditResult:
    """Hoàn tác kết quả cũ, lưu tỷ số mới rồi tính RP lại đúng một lần."""
    if not reverse_result(match):
        return AdminMatchEditResult(False, "Không thể hoàn tác RP cũ nên chưa thay đổi kết quả.", "danger")

    reset_payload = {
        "score1": score1,
        "score2": score2,
        "status": "waiting_confirm",
        "delta1": None,
        "delta2": None,
        "confirmed_by_id": None,
        "note": note or "Admin sửa kết quả và yêu cầu tính lại RP.",
    }
    update_match(reset_payload)

    fresh_match = dict(match)
    fresh_match.update(reset_payload)
    apply_result(fresh_match)
    sync_room({
        "score1": score1,
        "score2": score2,
        "status": "confirmed",
        "note": note or "Admin đã sửa kết quả và tính lại RP.",
    })
    return AdminMatchEditResult(True, "Đã sửa kết quả, hoàn tác RP cũ và tính lại RP theo tỷ số mới.", "success", "recalculated")
