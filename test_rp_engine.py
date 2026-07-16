"""Kiểm thử nhanh công thức RP V1.11.0. Chạy: python test_rp_engine.py"""
import random
from modules.rp_engine import calculate_deltas


def rank_level(points):
    return 1 if int(points or 0) < 1100 else 2


def calculate(player_a, player_b, score_a, score_b, seed=1):
    return calculate_deltas(player_a, player_b, score_a, score_b, rank_level, rng=random.Random(seed))


def run():
    newcomer = {"rank_points": 1000, "total_matches": 0, "streak": 0, "loss_streak": 0}
    regular = {"rank_points": 1000, "total_matches": 11, "streak": 0, "loss_streak": 0}

    placement = [calculate(newcomer, newcomer, 1, 0, seed) for seed in range(1000)]
    assert 22 <= min(win for win, _ in placement) <= max(win for win, _ in placement) <= 29
    assert 14 <= min(-loss for _, loss in placement) <= max(-loss for _, loss in placement) <= 19

    for current, minimum, maximum in [(3, 26, 27), (4, 27, 28), (5, 28, 29), (6, 29, 30)]:
        loser = dict(regular, loss_streak=current)
        results = [calculate(regular, loser, 1, 0, seed) for seed in range(500)]
        deductions = [-loss for _, loss in results]
        assert minimum <= min(deductions) <= max(deductions) <= maximum

    assert calculate({"rank_points": 900}, {"rank_points": 1200}, 0, 0) == (5, 0)
    assert calculate({"rank_points": 1200}, {"rank_points": 900}, 0, 0) == (0, 5)
    print("OK - RP Engine V1.11.0")


if __name__ == "__main__":
    run()
