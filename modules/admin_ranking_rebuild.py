"""Tính lại BXH sau khi Admin sửa tỷ số hoặc trạng thái trận.

Mọi trận được phát lại theo ``created_at`` gốc. Module chỉ tính toán, không truy cập
Flask/Supabase, nhờ đó có thể kiểm thử độc lập và không làm thay đổi thời điểm trận.

Điểm quan trọng:
- Giữ nguyên phần thống kê/RP gốc không được tạo bởi các dòng trong bảng ``matches``
  (ví dụ dữ liệu import/legacy hoặc điều chỉnh thủ công).
- Tính lại toàn bộ các trận confirmed theo đúng thứ tự thời gian.
- Không bao giờ đưa ``created_at`` vào payload cập nhật.
"""
from __future__ import annotations

import random
from typing import Any, Callable, Iterable, Mapping


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return int(default)


def _sort_key(match: Mapping[str, Any]) -> tuple[str, str]:
    return (str(match.get("created_at") or ""), str(match.get("id") or ""))


def _outcome_for_player(match: Mapping[str, Any], user_id: str) -> str | None:
    p1_id = str(match.get("player1_id") or "")
    p2_id = str(match.get("player2_id") or "")
    if user_id not in {p1_id, p2_id}:
        return None
    score1 = _int(match.get("score1"), -1)
    score2 = _int(match.get("score2"), -1)
    if score1 < 0 or score2 < 0:
        return None
    own, opp = (score1, score2) if user_id == p1_id else (score2, score1)
    if own > opp:
        return "win"
    if own < opp:
        return "loss"
    return "draw"


def _derive_initial_streaks(
    user: Mapping[str, Any],
    old_confirmed_matches: list[Mapping[str, Any]],
) -> tuple[int, int]:
    """Suy ra chuỗi trước trận đầu tiên sao cho lịch sử cũ phát lại không đổi kết quả cuối.

    Nếu chuỗi có điểm reset (thua đối với win streak; thắng/hòa đối với loss streak),
    trạng thái ban đầu không còn ảnh hưởng nên dùng 0. Nếu không có điểm reset, trừ số
    trận liên quan khỏi giá trị cuối hiện tại để bảo toàn dữ liệu legacy.
    """
    user_id = str(user.get("id") or "")
    outcomes = [
        outcome
        for match in sorted(old_confirmed_matches, key=_sort_key)
        if (outcome := _outcome_for_player(match, user_id)) is not None
    ]
    current_streak = max(0, _int(user.get("streak")))
    current_loss_streak = max(0, _int(user.get("loss_streak")))
    if not outcomes:
        return current_streak, current_loss_streak

    if "loss" in outcomes:
        initial_streak = 0
    else:
        initial_streak = max(0, current_streak - sum(1 for item in outcomes if item == "win"))

    if any(item in {"win", "draw"} for item in outcomes):
        initial_loss_streak = 0
    else:
        initial_loss_streak = max(0, current_loss_streak - sum(1 for item in outcomes if item == "loss"))

    return initial_streak, initial_loss_streak


def _old_contributions(
    matches: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, int], dict[str, dict[str, int]], dict[str, list[Mapping[str, Any]]]]:
    delta_sums: dict[str, int] = {}
    stat_sums: dict[str, dict[str, int]] = {}
    confirmed_by_user: dict[str, list[Mapping[str, Any]]] = {}

    def stats_for(user_id: str) -> dict[str, int]:
        return stat_sums.setdefault(user_id, {
            "total_matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
        })

    for raw in matches:
        match = dict(raw)
        if str(match.get("status") or "") != "confirmed":
            continue
        score1 = _int(match.get("score1"), -1)
        score2 = _int(match.get("score2"), -1)
        if score1 < 0 or score2 < 0:
            continue
        p1_id = str(match.get("player1_id") or "")
        p2_id = str(match.get("player2_id") or "")
        if p1_id:
            delta_sums[p1_id] = delta_sums.get(p1_id, 0) + _int(match.get("delta1"))
            row = stats_for(p1_id)
            row["total_matches"] += 1
            row["wins"] += int(score1 > score2)
            row["draws"] += int(score1 == score2)
            row["losses"] += int(score1 < score2)
            row["goals_for"] += score1
            row["goals_against"] += score2
            confirmed_by_user.setdefault(p1_id, []).append(match)
        if p2_id:
            delta_sums[p2_id] = delta_sums.get(p2_id, 0) + _int(match.get("delta2"))
            row = stats_for(p2_id)
            row["total_matches"] += 1
            row["wins"] += int(score2 > score1)
            row["draws"] += int(score2 == score1)
            row["losses"] += int(score2 < score1)
            row["goals_for"] += score2
            row["goals_against"] += score1
            confirmed_by_user.setdefault(p2_id, []).append(match)

    return delta_sums, stat_sums, confirmed_by_user


def _initial_player_state(
    user: Mapping[str, Any],
    confirmed_delta_sum: int,
    confirmed_stats: Mapping[str, int],
    old_confirmed_matches: list[Mapping[str, Any]],
    default_points: int,
) -> dict[str, Any]:
    current_points = _int(user.get("rank_points"), default_points)
    initial_streak, initial_loss_streak = _derive_initial_streaks(user, old_confirmed_matches)
    return {
        "id": user.get("id"),
        "rank_points": max(0, current_points - int(confirmed_delta_sum)),
        "total_matches": max(0, _int(user.get("total_matches")) - _int(confirmed_stats.get("total_matches"))),
        "wins": max(0, _int(user.get("wins")) - _int(confirmed_stats.get("wins"))),
        "draws": max(0, _int(user.get("draws")) - _int(confirmed_stats.get("draws"))),
        "losses": max(0, _int(user.get("losses")) - _int(confirmed_stats.get("losses"))),
        "goals_for": max(0, _int(user.get("goals_for")) - _int(confirmed_stats.get("goals_for"))),
        "goals_against": max(0, _int(user.get("goals_against")) - _int(confirmed_stats.get("goals_against"))),
        "streak": initial_streak,
        "loss_streak": initial_loss_streak,
    }


def _apply_state(state: dict[str, Any], delta: int, goals_for: int, goals_against: int) -> None:
    won = goals_for > goals_against
    drew = goals_for == goals_against
    lost = goals_for < goals_against
    state["rank_points"] = max(0, _int(state.get("rank_points")) + _int(delta))
    state["total_matches"] = _int(state.get("total_matches")) + 1
    state["wins"] = _int(state.get("wins")) + int(won)
    state["draws"] = _int(state.get("draws")) + int(drew)
    state["losses"] = _int(state.get("losses")) + int(lost)
    state["goals_for"] = _int(state.get("goals_for")) + _int(goals_for)
    state["goals_against"] = _int(state.get("goals_against")) + _int(goals_against)
    if won:
        state["streak"] = _int(state.get("streak")) + 1
        state["loss_streak"] = 0
    elif lost:
        state["streak"] = 0
        state["loss_streak"] = _int(state.get("loss_streak")) + 1
    else:
        # Giữ chuỗi thắng qua trận hòa như logic hiện hành; chuỗi thua kết thúc.
        state["loss_streak"] = 0


def _winner_loser(match: Mapping[str, Any], score1: int, score2: int) -> tuple[Any, Any]:
    if score1 > score2:
        return match.get("player1_id"), match.get("player2_id")
    if score2 > score1:
        return match.get("player2_id"), match.get("player1_id")
    return None, None


def build_replay_plan(
    *,
    users: Iterable[Mapping[str, Any]],
    matches: Iterable[Mapping[str, Any]],
    overrides: Mapping[str, Mapping[str, Any]],
    calculate_deltas: Callable[..., tuple[int, int]],
    get_rank_level: Callable[[int], int],
    apply_host_factor: Callable[[int, float], int],
    host_by_match: Mapping[str, Any],
    default_points: int,
    placement_matches: int,
    host_win_factor: float,
    formula_version: str,
    formula_summary: Callable[[], Any],
    seed_namespace: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Trả về payload cập nhật user/match sau khi phát lại lịch sử.

    ``created_at`` không bao giờ xuất hiện trong payload cập nhật.
    """
    original_matches = [dict(row) for row in matches]
    delta_sums, stat_sums, confirmed_by_user = _old_contributions(original_matches)

    states: dict[str, dict[str, Any]] = {}
    for user in users:
        user_id = str(user.get("id") or "")
        if user_id:
            states[user_id] = _initial_player_state(
                user,
                delta_sums.get(user_id, 0),
                stat_sums.get(user_id, {}),
                confirmed_by_user.get(user_id, []),
                default_points,
            )

    effective_matches: list[dict[str, Any]] = []
    for original in original_matches:
        match = dict(original)
        override = overrides.get(str(match.get("id") or ""))
        if override:
            match.update({key: value for key, value in dict(override).items() if key != "created_at"})
        effective_matches.append(match)

    match_updates: dict[str, dict[str, Any]] = {}
    for match in sorted(effective_matches, key=_sort_key):
        match_id = str(match.get("id") or "")
        if not match_id:
            continue
        status = str(match.get("status") or "")
        if status != "confirmed":
            if match_id in overrides:
                match_updates[match_id] = {
                    **{key: value for key, value in dict(overrides[match_id]).items() if key != "created_at"},
                    "delta1": None,
                    "delta2": None,
                    "winner_id": None,
                    "loser_id": None,
                    "rp_formula_version": None,
                    "rp_details": None,
                }
            continue

        p1_id = str(match.get("player1_id") or "")
        p2_id = str(match.get("player2_id") or "")
        score1 = _int(match.get("score1"), -1)
        score2 = _int(match.get("score2"), -1)
        if score1 < 0 or score2 < 0:
            raise ValueError(f"Trận {match_id} đã xác nhận nhưng thiếu tỷ số.")
        if p1_id not in states or p2_id not in states:
            if match_id in overrides:
                raise ValueError(f"Trận {match_id} thiếu dữ liệu người chơi để tính lại kết quả mới.")
            # Dữ liệu legacy có thể còn trận của tài khoản đã bị xóa. Giữ nguyên delta
            # đã lưu và phát lại phần của người chơi còn tồn tại để không khóa cả BXH.
            if p1_id in states:
                _apply_state(states[p1_id], _int(match.get("delta1")), score1, score2)
            if p2_id in states:
                _apply_state(states[p2_id], _int(match.get("delta2")), score2, score1)
            continue

        player1, player2 = states[p1_id], states[p2_id]
        rng = random.Random(f"{seed_namespace}|{match_id}")
        delta1, delta2 = calculate_deltas(
            player1,
            player2,
            score1,
            score2,
            get_rank_level=get_rank_level,
            team_a=match.get("team1"),
            team_b=match.get("team2"),
            team_overall_a=match.get("team1_overall"),
            team_overall_b=match.get("team2_overall"),
            team_tier_a=match.get("team1_tier"),
            team_tier_b=match.get("team2_tier"),
            rng=rng,
        )
        delta1, delta2 = _int(delta1), _int(delta2)
        host_id = str(match.get("host_user_id") or host_by_match.get(match_id) or "")
        factor = match.get("host_xp_factor", host_win_factor)
        if host_id == p1_id and score1 > score2:
            delta1 = _int(apply_host_factor(delta1, factor))
            if _int(player1.get("total_matches")) < placement_matches:
                delta1 = max(22, min(29, delta1))
        elif host_id == p2_id and score2 > score1:
            delta2 = _int(apply_host_factor(delta2, factor))
            if _int(player2.get("total_matches")) < placement_matches:
                delta2 = max(22, min(29, delta2))

        _apply_state(player1, delta1, score1, score2)
        _apply_state(player2, delta2, score2, score1)
        winner_id, loser_id = _winner_loser(match, score1, score2)
        payload = {
            "delta1": delta1,
            "delta2": delta2,
            "winner_id": winner_id,
            "loser_id": loser_id,
            "rp_formula_version": formula_version,
            "rp_details": {
                "source": "admin_chronological_replay",
                "formula": formula_summary(),
                "seed": f"{seed_namespace}|{match_id}",
                "delta1": delta1,
                "delta2": delta2,
            },
        }
        if match_id in overrides:
            payload.update({key: value for key, value in dict(overrides[match_id]).items() if key != "created_at"})
        match_updates[match_id] = payload

    user_updates = {
        user_id: {
            "rank_points": state["rank_points"],
            "total_matches": state["total_matches"],
            "wins": state["wins"],
            "draws": state["draws"],
            "losses": state["losses"],
            "goals_for": state["goals_for"],
            "goals_against": state["goals_against"],
            "streak": state["streak"],
            "loss_streak": state["loss_streak"],
        }
        for user_id, state in states.items()
    }
    return user_updates, match_updates
