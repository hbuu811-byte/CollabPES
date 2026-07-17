"""Bộ máy tính RP thuần Python cho PES Arena.

Các con số của công thức nằm riêng tại :mod:`modules.rp_formula`. Module này
chỉ thực hiện tính toán và không truy cập Flask/Supabase.
"""
from __future__ import annotations

import random
from typing import Callable, Mapping, MutableMapping, Tuple

from modules.rp_formula import (
    BASE_WIN_POINTS,
    LOSS_STREAK_RANGES,
    LOSS_STREAK_SEVEN_PLUS_RANGE,
    LOSS_STREAK_START,
    MAX_POSITIVE_POINTS_PER_MATCH,
    PLACEMENT_LOSS_RANGE,
    PLACEMENT_MATCHES,
    PLACEMENT_WIN_BONUS_RANGE,
    PLACEMENT_WIN_MULTIPLIER,
    PLACEMENT_WIN_TOTAL_RANGE,
    REGULAR_LOSS_RANGE,
    MIN_RANK_ADJUSTED_WIN_POINTS,
    MAX_RANK_ADJUSTED_WIN_POINTS,
    WIN_BASE_RANGE,
    WIN_STREAK_BONUSES,
    WIN_VARIATION_RANGE,
)


def get_win_streak_bonus(player: Mapping, won: bool) -> int:
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
    """Tên tương thích cũ; công thức hiện tại chưa điều chỉnh thắng theo chênh Rank."""
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
        points = max(PLACEMENT_WIN_TOTAL_RANGE[0], min(PLACEMENT_WIN_TOTAL_RANGE[1], points))
    return max(1, min(MAX_POSITIVE_POINTS_PER_MATCH, int(points)))


def _progressive_loss_streak_range(next_loss_streak: int) -> Tuple[int, int]:
    if int(next_loss_streak) >= 7:
        return LOSS_STREAK_SEVEN_PLUS_RANGE
    return LOSS_STREAK_RANGES.get(int(next_loss_streak), REGULAR_LOSS_RANGE)


def _loser_points(loser: Mapping, rng) -> int:
    matches = int(loser.get("total_matches", 0) or 0)
    next_loss_streak = int(loser.get("loss_streak", 0) or 0) + 1
    if matches < PLACEMENT_MATCHES:
        deduction = _randint(rng, *PLACEMENT_LOSS_RANGE)
    else:
        deduction = _randint(rng, *REGULAR_LOSS_RANGE)
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


def validate_deltas(score_a: int, score_b: int, delta_a: int, delta_b: int) -> Tuple[int, int]:
    """Kiểm tra dấu và giá trị RP; không tự thay lỗi bằng -20."""
    score_a, score_b = int(score_a), int(score_b)
    delta_a, delta_b = int(delta_a), int(delta_b)
    if score_a > score_b and not (delta_a > 0 and delta_b < 0):
        raise ValueError(f"RP không hợp lệ cho trận người chơi 1 thắng: {delta_a}/{delta_b}")
    if score_b > score_a and not (delta_a < 0 and delta_b > 0):
        raise ValueError(f"RP không hợp lệ cho trận người chơi 2 thắng: {delta_a}/{delta_b}")
    if score_a == score_b and (delta_a < 0 or delta_b < 0):
        raise ValueError(f"RP hòa không được âm: {delta_a}/{delta_b}")
    return delta_a, delta_b


def calculate_deltas(
    player_a: MutableMapping,
    player_b: MutableMapping,
    score_a: int,
    score_b: int,
    get_rank_level: Callable,
    rng=None,
    **_unused,
) -> Tuple[int, int]:
    rng = rng or random
    score_a, score_b = int(score_a), int(score_b)
    if score_a == score_b:
        return validate_deltas(score_a, score_b, *_draw_points(player_a, player_b, get_rank_level))
    a_won = score_a > score_b
    winner = player_a if a_won else player_b
    loser = player_b if a_won else player_a
    win_points = _winner_points(winner, rng)
    loss_points = _loser_points(loser, rng)
    deltas = (win_points, loss_points) if a_won else (loss_points, win_points)
    return validate_deltas(score_a, score_b, *deltas)
