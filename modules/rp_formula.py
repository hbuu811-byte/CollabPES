"""Cấu hình công thức RP của PES Arena.

File này chỉ chứa phiên bản, hằng số và mô tả công thức. Không truy cập Flask,
Supabase hoặc dữ liệu người dùng. Mọi thay đổi công thức RP phải được thực hiện
ở đây và tăng ``RP_FORMULA_VERSION``.
"""
from __future__ import annotations

RP_FORMULA_VERSION = "RP_V1.12.0"
RP_FORMULA_NAME = "PES Arena RP – Biến thiên có kiểm soát"
RP_RANDOM_SEED_NAMESPACE = f"PES_ARENA|{RP_FORMULA_VERSION}"

PLACEMENT_MATCHES = 10
MAX_POSITIVE_POINTS_PER_MATCH = 50

# Người thắng
WIN_BASE_RANGE = (21, 23)
WIN_VARIATION_RANGE = (-1, 3)
PLACEMENT_WIN_BONUS_RANGE = (1, 4)
PLACEMENT_WIN_TOTAL_RANGE = (22, 29)
HOST_WIN_FACTOR = 0.95

# Người thua
PLACEMENT_LOSS_RANGE = (14, 19)
REGULAR_LOSS_RANGE = (19, 23)
LOSS_STREAK_START = 4
LOSS_STREAK_RANGES = {
    4: (22, 24),
    5: (23, 26),
    6: (25, 27),
}
LOSS_STREAK_SEVEN_PLUS_RANGE = (25, 30)

# Chuỗi thắng: chỉ thưởng đúng trận chạm mốc.
WIN_STREAK_BONUSES = {3: 5, 5: 10, 10: 15}

# Tương thích với một số phần giao diện/code cũ. Không dùng làm fallback RP.
BASE_WIN_POINTS = WIN_BASE_RANGE[0]
PLACEMENT_WIN_MULTIPLIER = 1.0
MIN_RANK_ADJUSTED_WIN_POINTS = WIN_BASE_RANGE[0]
MAX_RANK_ADJUSTED_WIN_POINTS = WIN_BASE_RANGE[1]


def formula_summary() -> dict:
    """Trả mô tả ngắn, có thể lưu vào rp_details hoặc hiển thị trong Admin."""
    return {
        "version": RP_FORMULA_VERSION,
        "name": RP_FORMULA_NAME,
        "winner": {
            "base": list(WIN_BASE_RANGE),
            "variation": list(WIN_VARIATION_RANGE),
            "placement_bonus": list(PLACEMENT_WIN_BONUS_RANGE),
            "placement_total": list(PLACEMENT_WIN_TOTAL_RANGE),
            "host_factor": HOST_WIN_FACTOR,
        },
        "loser": {
            "placement": list(PLACEMENT_LOSS_RANGE),
            "regular": list(REGULAR_LOSS_RANGE),
            "loss_streak_start": LOSS_STREAK_START,
        },
    }
