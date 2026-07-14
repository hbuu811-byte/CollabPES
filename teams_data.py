TEAM_TIER_META = {
    "S+": {"label": "S+", "power_min": 80.50, "power_max": 81.60},
    "S": {"label": "S", "power_min": 79.50, "power_max": 80.49},
    "A+": {"label": "A+", "power_min": 78.50, "power_max": 79.49},
    "A": {"label": "A", "power_min": 77.50, "power_max": 78.49},
    "B": {"label": "B", "power_min": 76.00, "power_max": 77.49},
    "C": {"label": "C", "power_min": 74.50, "power_max": 75.99},
    "D": {"label": "D", "power_min": 73.33, "power_max": 74.49},
}

TEAMS = [
    {"display": "Manchester City", "overall": 85},
    {"display": "Real Madrid", "overall": 85},
    {"display": "Bayern Munich", "overall": 84},
    {"display": "Inter Milan", "overall": 84},
    {"display": "Arsenal", "overall": 83},
    {"display": "Liverpool", "overall": 83},
    {"display": "Barcelona", "overall": 82},
    {"display": "PSG", "overall": 82},
    {"display": "Atletico Madrid", "overall": 81},
    {"display": "Bayer Leverkusen", "overall": 81},
    {"display": "Borussia Dortmund", "overall": 80},
    {"display": "Tottenham Hotspur", "overall": 80},
    {"display": "AC Milan", "overall": 79},
    {"display": "Juventus", "overall": 79},
    {"display": "Napoli", "overall": 78},
    {"display": "RB Leipzig", "overall": 78},
    {"display": "Aston Villa", "overall": 77},
    {"display": "Newcastle United", "overall": 77},
    {"display": "Roma", "overall": 76},
    {"display": "Real Sociedad", "overall": 76},
    {"display": "Benfica", "overall": 75},
    {"display": "Sporting CP", "overall": 75},
    {"display": "Ajax", "overall": 74},
    {"display": "Porto", "overall": 74},
    {"display": "Galatasaray", "overall": 73},
    {"display": "Fenerbahce", "overall": 73},
]


def _power_from_overall(overall):
    return round(73.33 + (int(overall or 73) - 73) * 0.75, 2)


def _tier_from_power(power_score):
    score = float(power_score or 0)
    for tier, meta in TEAM_TIER_META.items():
        if meta["power_min"] <= score <= meta["power_max"]:
            return tier
    return "S+" if score > 81.60 else "D"


def _tier_from_overall(overall):
    return _tier_from_power(_power_from_overall(overall))


for team in TEAMS:
    team["power_score"] = _power_from_overall(team["overall"])
    team["tier"] = _tier_from_power(team["power_score"])


TEAM_COUNT = len(TEAMS)
TEAM_TIERS = sorted({team["tier"] for team in TEAMS})
_TEAM_BY_NAME = {team["display"].lower(): team for team in TEAMS}


def get_team_info(team_name):
    if not team_name:
        return None
    return _TEAM_BY_NAME.get(str(team_name).lower())


def get_team_overall(team_name):
    team = get_team_info(team_name)
    return int(team["overall"]) if team else 80


def get_team_tier(team_name):
    return _tier_from_overall(get_team_overall(team_name))
