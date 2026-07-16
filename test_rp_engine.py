"""Kiểm thử nhanh công thức RP RP_V1.12.0. Chạy: python test_rp_engine.py"""
import random
from modules.rp_engine import calculate_deltas, validate_deltas
from modules.rp_formula import RP_FORMULA_VERSION


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

    regular_losses = [calculate(regular, regular, 1, 0, seed) for seed in range(2000)]
    regular_deductions = [-loss for _, loss in regular_losses]
    assert min(regular_deductions) == 19
    assert max(regular_deductions) == 23
    assert set(regular_deductions) == {19, 20, 21, 22, 23}

    for current, minimum, maximum in [
        (3, 22, 24),
        (4, 23, 26),
        (5, 25, 27),
        (6, 25, 30),
        (10, 25, 30),
    ]:
        loser = dict(regular, loss_streak=current)
        results = [calculate(regular, loser, 1, 0, seed) for seed in range(2000)]
        deductions = [-loss for _, loss in results]
        assert min(deductions) == minimum
        assert max(deductions) == maximum


    assert calculate({"rank_points": 900}, {"rank_points": 1200}, 0, 0) == (5, 0)
    assert calculate({"rank_points": 1200}, {"rank_points": 900}, 0, 0) == (0, 5)
    try:
        validate_deltas(1, 0, 22, 0)
        raise AssertionError("Delta thua bằng 0 phải bị từ chối")
    except ValueError:
        pass
    assert RP_FORMULA_VERSION == "RP_V1.12.0"
    print("OK - RP Engine RP_V1.12.0")


if __name__ == "__main__":
    run()
