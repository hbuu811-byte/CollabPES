"""Bộ máy tính RP xếp hạng.

Không truy cập Flask/Supabase. Hàm nhận callback xác định cấp Rank để có thể
kiểm thử riêng và thay công thức mà không sửa route phòng đấu.
"""
BASE_WIN_POINTS = 21
BASE_LOSS_POINTS = -20
PLACEMENT_MATCHES = 10
PLACEMENT_WIN_MULTIPLIER = 1.10
MIN_RANK_ADJUSTED_WIN_POINTS = 19
MAX_RANK_ADJUSTED_WIN_POINTS = 24
MAX_POSITIVE_POINTS_PER_MATCH = 35
WIN_STREAK_BONUSES = {3: 5, 5: 10, 8: 15, 10: 20}

def get_win_streak_bonus(player, won):
    if not won:
        return 0
    next_streak = int(player.get("streak", 0) or 0) + 1
    return WIN_STREAK_BONUSES.get(next_streak, 0)

def rank_adjusted_win_points(winner, loser, get_rank_level):
    winner_level = get_rank_level(winner.get("rank_points", 0))
    loser_level = get_rank_level(loser.get("rank_points", 0))
    rank_advantage = loser_level - winner_level
    return max(MIN_RANK_ADJUSTED_WIN_POINTS,
               min(MAX_RANK_ADJUSTED_WIN_POINTS, BASE_WIN_POINTS + rank_advantage))

def calculate_deltas(player_a, player_b, score_a, score_b, get_rank_level, **_unused):
    score_a = int(score_a)
    score_b = int(score_b)
    if score_a == score_b:
        return 0, 0
    a_won = score_a > score_b
    winner = player_a if a_won else player_b
    loser = player_b if a_won else player_a
    winner_matches = int(winner.get("total_matches", 0) or 0)
    loser_matches = int(loser.get("total_matches", 0) or 0)
    if winner_matches < PLACEMENT_MATCHES or loser_matches < PLACEMENT_MATCHES:
        win_points = BASE_WIN_POINTS
    else:
        win_points = rank_adjusted_win_points(winner, loser, get_rank_level)
    if winner_matches < PLACEMENT_MATCHES:
        win_points = round(BASE_WIN_POINTS * PLACEMENT_WIN_MULTIPLIER)
    win_points += get_win_streak_bonus(winner, True)
    win_points = min(MAX_POSITIVE_POINTS_PER_MATCH, max(1, int(win_points)))
    return (win_points, BASE_LOSS_POINTS) if a_won else (BASE_LOSS_POINTS, win_points)
