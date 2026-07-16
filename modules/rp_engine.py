"""Bộ máy tính RP xếp hạng PES 2026 - V1.11.1.

Module thuần Python, không truy cập Flask/Supabase. Dữ liệu chuỗi thua hiện tại
được app.py truyền vào qua khóa ``loss_streak`` của từng người chơi.
"""
from __future__ import annotations

import random
from typing import Callable, Mapping, MutableMapping, Tuple

# Giữ các tên hằng cũ để app.py và module bên ngoài không bị lỗi import.
BASE_WIN_POINTS = 21
BASE_LOSS_POINTS = -20
PLACEMENT_MATCHES = 10
PLACEMENT_WIN_MULTIPLIER = 1.0
MIN_RANK_ADJUSTED_WIN_POINTS = 21
MAX_RANK_ADJUSTED_WIN_POINTS = 23
MAX_POSITIVE_POINTS_PER_MATCH = 50

WIN_BASE_RANGE = (21, 23)
WIN_VARIATION_RANGE = (-1, 3)
PLACEMENT_WIN_BONUS_RANGE = (1, 4)
PLACEMENT_WIN_TOTAL_RANGE = (22, 29)
PLACEMENT_LOSS_RANGE = (14, 19)
REGULAR_LOSS_BASE_RANGE = (19, 23)
LOSS_STREAK_START = 4
LOSS_STREAK_MAX_DEDUCTION = 30

LOSS_STREAK_RANGES = {
    4: (22, 24),
    5: (23, 26),
    6: (25, 27),
}
LOSS_STREAK_SEVEN_PLUS_RANGE = (25, 30)

# Chỉ thưởng đúng trận chạm mốc. Từ mốc 10 trở đi, cứ thêm 5 trận thắng liên tiếp +15 RP.
WIN_STREAK_BONUSES = {3: 5, 5: 10, 10: 15}


def get_win_streak_bonus(player: Mapping, won: bool) -> int:
    """Trả thưởng chuỗi thắng của trận sắp được ghi nhận."""
    if not won:
        return 0
    next_streak = int(player.get("streak", 0) or 0) + 1
    if next_streak == 3:
        return 5
    if next_streak == 5:
        return 10
    if next_streak >= 10 and next_streak % 5 == 0:
        return 15
    return 0


def rank_adjusted_win_points(winner: Mapping, loser: Mapping, get_rank_level: Callable) -> int:
    """Tên hàm tương thích cũ; V1.11.1 không cộng/trừ RP thắng theo chênh Rank."""
    del winner, loser, get_rank_level
    return BASE_WIN_POINTS


def _randint(rng, minimum: int, maximum: int) -> int:
    return int(rng.randint(minimum, maximum))


def _winner_points(winner: Mapping, rng) -> int:
    matches = int(winner.get("total_matches", 0) or 0)
    points = _randint(rng, *WIN_BASE_RANGE)
    points += _randint(rng, *WIN_VARIATION_RANGE)

    if matches < PLACEMENT_MATCHES:
        points += _randint(rng, *PLACEMENT_WIN_BONUS_RANGE)

    points += get_win_streak_bonus(winner, True)
    if matches < PLACEMENT_MATCHES:
        # Tổng RP thắng trong 10 trận đầu, kể cả thưởng chuỗi, luôn nằm trong 22-29.
        points = max(PLACEMENT_WIN_TOTAL_RANGE[0], min(PLACEMENT_WIN_TOTAL_RANGE[1], points))
    return max(1, min(MAX_POSITIVE_POINTS_PER_MATCH, int(points)))


def _progressive_loss_streak_range(next_loss_streak: int) -> Tuple[int, int]:
    """Trả khoảng trừ theo đúng mốc chuỗi thua của V1.11.1."""
    streak = int(next_loss_streak)
    if streak >= 7:
        return LOSS_STREAK_SEVEN_PLUS_RANGE
    return LOSS_STREAK_RANGES.get(streak, REGULAR_LOSS_BASE_RANGE)


def _loser_points(loser: Mapping, rng) -> int:
    matches = int(loser.get("total_matches", 0) or 0)
    current_loss_streak = int(loser.get("loss_streak", 0) or 0)
    next_loss_streak = current_loss_streak + 1

    if matches < PLACEMENT_MATCHES:
        deduction = _randint(rng, *PLACEMENT_LOSS_RANGE)
    else:
        # Sau 10 trận đầu: lấy trực tiếp một giá trị ngẫu nhiên 19-23.
        # Không cộng biến thiên phụ để tránh nhiều tổ hợp cùng dồn về -20 RP.
        deduction = _randint(rng, *REGULAR_LOSS_BASE_RANGE)

    if next_loss_streak >= LOSS_STREAK_START:
        deduction = _randint(rng, *_progressive_loss_streak_range(next_loss_streak))

    return -max(1, int(deduction))


def _draw_points(player_a: Mapping, player_b: Mapping, get_rank_level: Callable) -> Tuple[int, int]:
    level_a = int(get_rank_level(player_a.get("rank_points", 0)))
    level_b = int(get_rank_level(player_b.get("rank_points", 0)))
    if level_a < level_b:
        return 5, 0
    if level_b < level_a:
        return 0, 5
    return 0, 0


def calculate_deltas(
    player_a: MutableMapping,
    player_b: MutableMapping,
    score_a: int,
    score_b: int,
    get_rank_level: Callable,
    rng=None,
    **_unused,
) -> Tuple[int, int]:
    """Tính delta RP cho hai người chơi theo cơ chế V1.11.1."""
    rng = rng or random
    score_a = int(score_a)
    score_b = int(score_b)

    if score_a == score_b:
        return _draw_points(player_a, player_b, get_rank_level)

    a_won = score_a > score_b
    winner = player_a if a_won else player_b
    loser = player_b if a_won else player_a
    win_points = _winner_points(winner, rng)
    loss_points = _loser_points(loser, rng)
    return (win_points, loss_points) if a_won else (loss_points, win_points)
