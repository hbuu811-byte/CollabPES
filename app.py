import csv
import json
import hashlib
import io
import os
import random
import secrets
import string
import time
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from functools import wraps
from collections import Counter

from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError
from flask import (
    Flask,
    jsonify,
    flash,
    g,
    has_request_context,
    make_response,
    send_file,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from supabase import create_client

from modules.cache_utils import (
    cache_get, cache_set, cache_delete, ttl_cache_get, ttl_cache_set, ttl_cache_delete,
)
from modules.datetime_utils import (
    now_dt, now_iso, future_iso, aware_utc, seconds_until, parse_dt, format_vn_datetime,
)
from modules.rp_formula import (
    BASE_WIN_POINTS, PLACEMENT_MATCHES, PLACEMENT_WIN_MULTIPLIER,
    MIN_RANK_ADJUSTED_WIN_POINTS, MAX_RANK_ADJUSTED_WIN_POINTS,
    MAX_POSITIVE_POINTS_PER_MATCH, WIN_STREAK_BONUSES, HOST_WIN_FACTOR,
    RP_FORMULA_VERSION, RP_RANDOM_SEED_NAMESPACE, formula_summary,
)
from modules.rp_engine import (
    calculate_deltas as calculate_ranked_deltas, validate_deltas as validate_ranked_deltas,
)
from modules.admin_match_service import parse_score, score_changed
from modules.admin_ranking_rebuild import build_replay_plan
from modules.system_feature_service import post_login_endpoint, dashboard_is_enabled
from modules.session_runtime_service import (
    IDLE_TIMEOUT_SECONDS, idle_decision, room_blocks_idle_logout, client_config as session_client_config,
)
from modules.win_streaks import (
    WIN_STREAK_TITLES, WIN_STREAK_EVENT_PREFIX, get_win_streak_title,
    get_win_streak_badge, build_win_streak_event, encode_win_streak_room_note,
    parse_win_streak_room_note,
)


load_dotenv()

APP_NAME = "PES Arena – Bản Lĩnh Sân Cỏ"
APP_VERSION = "V1.13.13"
DEFAULT_POINTS = 1000
DEVICE_COOKIE_NAME = "rankzone_device_id"
COOLDOWN_MINUTES = 3
ONLINE_TIMEOUT_SECONDS = 90
CHAT_COOLDOWN_SECONDS = 5
CHAT_MAX_LENGTH = 200
AVATAR_BUCKET = "avatars"
AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_OUTPUT_SIZE = 512
AVATAR_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
DISPUTE_EVIDENCE_BUCKET = "dispute-evidence"
DISPUTE_EVIDENCE_MAX_BYTES = 4 * 1024 * 1024
DISPUTE_EVIDENCE_MAX_SIDE = 1600
DISPUTE_EVIDENCE_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

ACHIEVEMENT_DEFINITIONS = [
    {"code": "first_match", "icon": "⚽", "name": "Bước chân đầu tiên", "description": "Hoàn thành trận đấu đầu tiên.", "metric": "total_matches", "threshold": 1, "priority": 10},
    {"code": "warrior_20", "icon": "🛡️", "name": "Chiến binh sân cỏ", "description": "Hoàn thành 20 trận đấu.", "metric": "total_matches", "threshold": 20, "priority": 20},
    {"code": "winner_10", "icon": "🏅", "name": "Kẻ chinh phục", "description": "Giành 10 chiến thắng.", "metric": "wins", "threshold": 10, "priority": 30},
    {"code": "goals_50", "icon": "🎯", "name": "Sát thủ vòng cấm", "description": "Ghi tổng cộng 50 bàn thắng.", "metric": "goals_for", "threshold": 50, "priority": 40},
    {"code": "hot_streak_5", "icon": "🔥", "name": "Chuỗi lửa", "description": "Thắng liên tiếp 5 trận.", "metric": "streak", "threshold": 5, "priority": 50},
    {"code": "top_one", "icon": "👑", "name": "Đỉnh bảng", "description": "Từng giữ vị trí số 1 BXH sau ít nhất 5 trận.", "metric": "position", "threshold": 1, "priority": 60},
]
ACHIEVEMENT_BY_CODE = {item["code"]: item for item in ACHIEVEMENT_DEFINITIONS}
ADMIN_LEVELS = {"owner", "admin"}
ACCOUNT_STATUSES = {"pending", "approved", "rejected", "banned"}
REMATCH_HOST_READY_NOTE = "__rematch_host_ready__"
REMATCH_GUEST_READY_NOTE = "__rematch_guest_ready__"
REMATCH_HOST_DECLINED_NOTE = "__rematch_host_declined__"
REMATCH_GUEST_DECLINED_NOTE = "__rematch_guest_declined__"
REMATCH_EXPIRED_NOTE = "__rematch_expired__"

DISPUTE_REASON_OPTIONS = {
    "wrong_score": "Sai tỷ số",
    "wrong_winner": "Sai người thắng",
    "interrupted": "Trận bị gián đoạn",
    "unilateral_entry": "Kết quả nhập không đúng thỏa thuận",
    "other": "Lý do khác",
    "timeout": "Hết thời gian xác nhận",
    "legacy": "Tranh chấp từ phiên bản cũ",
}
DISPUTE_PENDING_STATUSES = {"pending", "processing"}

# Khóa toàn cục ngắn hạn dùng khi Admin phát lại lịch sử BXH.
# Lưu trong Supabase để có hiệu lực trên nhiều Serverless Function/instance.
RANKING_REBUILD_LOCK_KEY = "admin_ranking_rebuild_lock"
RANKING_REBUILD_LOCK_SECONDS = 5 * 60

INVITE_TIMEOUT_SECONDS = 60
ROOM_READY_TIMEOUT_SECONDS = 30 * 60
RESULT_CONFIRM_TIMEOUT_SECONDS = 60 * 60
REMATCH_TIMEOUT_SECONDS = 60
ROOM_EMPTY_INACTIVITY_TIMEOUT_SECONDS = 30 * 60
ROOM_MATCH_INACTIVITY_TIMEOUT_SECONDS = 60 * 60
ROOM_ABANDON_PENALTY = 20
ROOM_TIMEOUT_PENALTY_RANGE = (22, 25)

RANK_K_FACTOR = 32
RANK_SCALE = 400
TEAM_OVR_BASE = 79
TEAM_OVR_WEIGHT = 20

# Cấu hình công thức: modules/rp_formula.py; logic tính: modules/rp_engine.py

# Rank/Tier difficulty system (V1.8.1)
SMART_RANDOM_CORRECT_WEIGHT = 0.70
SMART_RANDOM_STRONGER_WEIGHT = 0.15
SMART_RANDOM_WEAKER_WEIGHT = 0.15

# Danh hiệu chuỗi thắng đã tách sang modules/win_streaks.py



DEFAULT_RANKS = [
    {"min": 0, "max": 499, "name": "Gà", "short_name": "Gà", "abbr": "G", "code": "CHICKEN", "icon": "🐔", "slug": "ga"},
    {"min": 500, "max": 699, "name": "Non", "short_name": "Non", "abbr": "N", "code": "NOVICE", "icon": "🌱", "slug": "non"},
    {"min": 700, "max": 899, "name": "Báo Thủ", "short_name": "Báo", "abbr": "BT", "code": "LIABILITY", "icon": "⚠️", "slug": "bao-thu"},
    {"min": 900, "max": 1099, "name": "Mới Tập Chơi", "short_name": "Mới Chơi", "abbr": "MTC", "code": "BEGINNER", "icon": "🎮", "slug": "moi-tap-choi"},
    {"min": 1100, "max": 1399, "name": "Bán Chuyên", "short_name": "B.Chuyên", "abbr": "BC", "code": "SEMI_PRO", "icon": "⚔️", "slug": "ban-chuyen"},
    {"min": 1400, "max": 1699, "name": "Chuyên Nghiệp", "short_name": "C.Nghiệp", "abbr": "CN", "code": "PROFESSIONAL", "icon": "🎯", "slug": "chuyen-nghiep"},
    {"min": 1700, "max": 1999, "name": "Đẳng Cấp", "short_name": "Đ.Cấp", "abbr": "ĐC", "code": "CLASS", "icon": "💎", "slug": "dang-cap"},
    {"min": 2000, "max": 2349, "name": "Siêu Sao", "short_name": "S.Sao", "abbr": "SS", "code": "SUPERSTAR", "icon": "🌟", "slug": "sieu-sao"},
    {"min": 2350, "max": 2699, "name": "Huyền Thoại", "short_name": "H.Thoại", "abbr": "HT", "code": "LEGEND", "icon": "🏆", "slug": "huyen-thoai"},
    {"min": 2700, "max": None, "name": "GOAT", "short_name": "GOAT", "abbr": "GOAT", "code": "GOAT", "icon": "👑", "slug": "goat"},
]

MATCH_STATUS_LABELS = {
    "confirmed": "Đã xác nhận",
    "cancelled": "Đã hủy",
    "disputed": "Đang tranh chấp",
    "playing": "Đang thi đấu",
    "waiting_confirm": "Chờ xác nhận",
    "waiting_ready": "Chờ Chủ Phòng Quay",
    "waiting_result_confirm": "Chờ xác nhận kết quả",
}

ACTIVITY_PRIORITY = {
    "ready": 0,
    "in_room": 1,
    "waiting_confirm": 2,
    "playing": 3,
}


app = Flask(__name__)

# Tên biến chính thức giữ giống bản Production v1.9.3.
# Các tên dự phòng chỉ giúp app tương thích nếu Vercel từng được cấu hình theo tên cũ.
app.secret_key = (
    os.getenv("FLASK_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "rankzone-fc-dev-secret-change-me"
).strip()

APP_ENV = (os.getenv("APP_ENV") or os.getenv("VERCEL_ENV") or "production").strip().lower()
PES_ARENA_TEST_MODE = (os.getenv("PES_ARENA_TEST_MODE") or "false").strip().lower() in {"1", "true", "yes", "on"}
ALLOW_SIMPLE_TEST_PASSWORDS = (os.getenv("ALLOW_SIMPLE_TEST_PASSWORDS") or "false").strip().lower() in {"1", "true", "yes", "on"}
DATABASE_SAFETY_TOKEN = (os.getenv("DATABASE_SAFETY_TOKEN") or "").strip()

def is_test_mode():
    return APP_ENV in {"test", "testing", "development", "preview"} and PES_ARENA_TEST_MODE and DATABASE_SAFETY_TOKEN == "PES_ARENA_TEST_DATABASE"


def simple_test_passwords_enabled():
    """Only allow one-character passwords in an explicitly isolated test environment."""
    return is_test_mode() and ALLOW_SIMPLE_TEST_PASSWORDS


def minimum_password_length():
    return 1 if simple_test_passwords_enabled() else 6


def validate_new_password(password: str):
    minimum = minimum_password_length()
    if len(password or "") < minimum:
        return False, f"Mật khẩu mới phải có ít nhất {minimum} ký tự."
    return True, ""

supabase_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
supabase_key = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or ""
).strip()

db = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None


# Cache đã tách sang modules/cache_utils.py

def execute_query(query, label="Supabase", attempts=4, delay=0.25):
    """Retry short-lived Vercel/Supabase network failures before returning 500."""
    last_error = None

    for attempt in range(max(1, attempts)):
        try:
            return query.execute()
        except Exception as exc:
            last_error = exc
            message = f"{type(exc).__name__}: {exc}".lower()

            transient = any(token in message for token in (
                "connecterror",
                "connection",
                "server disconnected",
                "remoteprotocolerror",
                "timeout",
                "temporarily",
                "device or resource busy",
                "resource busy",
                "errno 16",
                "eagain",
            ))

            if not transient or attempt >= max(1, attempts) - 1:
                print(f"{label} failed after {attempt + 1} attempt(s): {exc}")
                raise

            # Backoff ngắn: 0.25s, 0.5s, 0.75s...
            time.sleep(delay * (attempt + 1))

    raise last_error



_admin_checked = False


# =========================
# Basic helpers
# =========================
# Tiện ích thời gian đã tách sang modules/datetime_utils.py

def _normalize_storage_public_url(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("publicUrl") or value.get("public_url") or value.get("signedURL") or value.get("signed_url")
    return str(value or "")


def prepare_avatar_bytes(file_storage):
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise ValueError("Bạn chưa chọn ảnh đại diện.")

    raw = file_storage.read(AVATAR_MAX_BYTES + 1)
    if len(raw) > AVATAR_MAX_BYTES:
        raise ValueError("Ảnh đại diện không được vượt quá 2 MB.")
    if not raw:
        raise ValueError("File ảnh đang trống.")

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            image_format = (probe.format or "").upper()
            width, height = probe.size
            probe.verify()
        if image_format not in AVATAR_ALLOWED_FORMATS:
            raise ValueError("Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP.")
        if width < 80 or height < 80:
            raise ValueError("Ảnh quá nhỏ. Vui lòng chọn ảnh từ 80×80 pixel trở lên.")
        if width * height > 25_000_000:
            raise ValueError("Ảnh có độ phân giải quá lớn.")

        with Image.open(io.BytesIO(raw)) as source:
            source = ImageOps.exif_transpose(source)
            source = source.convert("RGB")
            avatar = ImageOps.fit(
                source,
                (AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            output = io.BytesIO()
            avatar.save(output, format="WEBP", quality=86, method=6)
            return output.getvalue()
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValueError("File đã chọn không phải ảnh hợp lệ hoặc đã bị lỗi.")


def upload_avatar_to_storage(user_id, avatar_bytes):
    require_db()
    object_path = f"{user_id}/{uuid.uuid4().hex}.webp"
    bucket = db.storage.from_(AVATAR_BUCKET)
    bucket.upload(
        object_path,
        avatar_bytes,
        {
            "content-type": "image/webp",
            "cache-control": "31536000",
            "upsert": "false",
        },
    )
    public_url = _normalize_storage_public_url(bucket.get_public_url(object_path))
    if not public_url:
        try:
            bucket.remove([object_path])
        except Exception:
            pass
        raise RuntimeError("Không lấy được đường dẫn ảnh sau khi tải lên.")
    return object_path, public_url


def remove_avatar_object(object_path):
    if not object_path or db is None:
        return
    try:
        db.storage.from_(AVATAR_BUCKET).remove([object_path])
    except Exception as exc:
        print(f"remove_avatar_object warning: {exc}")


def prepare_dispute_evidence_bytes(file_storage):
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    raw = file_storage.read(DISPUTE_EVIDENCE_MAX_BYTES + 1)
    if len(raw) > DISPUTE_EVIDENCE_MAX_BYTES:
        raise ValueError("Ảnh bằng chứng không được vượt quá 4 MB.")
    if not raw:
        raise ValueError("File ảnh bằng chứng đang trống.")

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            image_format = (probe.format or "").upper()
            width, height = probe.size
            probe.verify()
        if image_format not in DISPUTE_EVIDENCE_ALLOWED_FORMATS:
            raise ValueError("Bằng chứng chỉ chấp nhận ảnh JPG, PNG hoặc WEBP.")
        if width < 100 or height < 100:
            raise ValueError("Ảnh bằng chứng quá nhỏ. Vui lòng chọn ảnh từ 100×100 pixel trở lên.")
        if width * height > 30_000_000:
            raise ValueError("Ảnh bằng chứng có độ phân giải quá lớn.")

        with Image.open(io.BytesIO(raw)) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            source.thumbnail(
                (DISPUTE_EVIDENCE_MAX_SIDE, DISPUTE_EVIDENCE_MAX_SIDE),
                Image.Resampling.LANCZOS,
            )
            output = io.BytesIO()
            source.save(output, format="WEBP", quality=86, method=6)
            return output.getvalue()
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValueError("File bằng chứng không phải ảnh hợp lệ hoặc đã bị lỗi.")


def upload_dispute_evidence(match_id, user_id, evidence_bytes):
    require_db()
    object_path = f"{match_id}/{user_id}/{uuid.uuid4().hex}.webp"
    bucket = db.storage.from_(DISPUTE_EVIDENCE_BUCKET)
    bucket.upload(
        object_path,
        evidence_bytes,
        {
            "content-type": "image/webp",
            "cache-control": "3600",
            "upsert": "false",
        },
    )
    return object_path


def remove_dispute_evidence_object(object_path):
    if not object_path or db is None:
        return
    try:
        db.storage.from_(DISPUTE_EVIDENCE_BUCKET).remove([object_path])
    except Exception as exc:
        print(f"remove_dispute_evidence_object warning: {exc}")


def get_dispute_evidence_signed_url(object_path, expires_in=3600):
    if not object_path or db is None:
        return None
    try:
        response = db.storage.from_(DISPUTE_EVIDENCE_BUCKET).create_signed_url(
            object_path,
            max(60, int(expires_in)),
        )
        return _normalize_storage_public_url(response)
    except Exception as exc:
        print(f"get_dispute_evidence_signed_url warning: {exc}")
        return None


def achievement_progress(player, definition, position=None):
    metric = definition.get("metric")
    threshold = max(1, int(definition.get("threshold", 1) or 1))
    if metric == "position":
        current = 1 if position == 1 and int(player.get("total_matches", 0) or 0) >= 5 else 0
    else:
        current = max(0, int(player.get(metric, 0) or 0))
    return current, threshold, min(100, round((current / threshold) * 100))


def eligible_achievement_codes(player, position=None):
    eligible = []
    for definition in ACHIEVEMENT_DEFINITIONS:
        current, threshold, _ = achievement_progress(player, definition, position)
        if current >= threshold:
            eligible.append(definition["code"])
    return eligible


def list_user_achievement_map():
    cached = cache_get("_rz_user_achievement_map")
    if cached is not None:
        return cached
    shared = ttl_cache_get("achievement_map")
    if shared is not None:
        return cache_set("_rz_user_achievement_map", shared)
    mapped = {}
    try:
        result = execute_query(
            db.table("user_achievements").select("user_id,achievement_code,unlocked_at"),
            "list_user_achievements",
            attempts=2,
        )
        for row in result.data or []:
            mapped.setdefault(str(row.get("user_id")), {})[row.get("achievement_code")] = row
    except Exception as exc:
        print(f"list_user_achievement_map warning: {exc}")
    ttl_cache_set("achievement_map", mapped, 30)
    return cache_set("_rz_user_achievement_map", mapped)


def decorate_player_achievements(player, position=None, achievement_map=None):
    if not player:
        return player
    achievement_map = achievement_map if achievement_map is not None else list_user_achievement_map()
    saved = achievement_map.get(str(player.get("id")), {})
    achievements = []
    for definition in ACHIEVEMENT_DEFINITIONS:
        current, threshold, progress = achievement_progress(player, definition, position)
        unlocked = definition["code"] in saved or current >= threshold
        item = dict(definition)
        item.update({
            "unlocked": unlocked,
            "unlocked_at": (saved.get(definition["code"]) or {}).get("unlocked_at"),
            "current": current,
            "progress": progress,
        })
        achievements.append(item)
    unlocked_items = sorted(
        [item for item in achievements if item.get("unlocked")],
        key=lambda item: int(item.get("priority", 0)),
        reverse=True,
    )
    player["achievements"] = achievements
    player["unlocked_achievements"] = unlocked_items
    player["achievement_count"] = len(unlocked_items)
    player["featured_achievement"] = unlocked_items[0] if unlocked_items else None
    return player


def sync_achievements_for_users(user_ids, notify=True):
    user_ids = [str(user_id) for user_id in dict.fromkeys(user_ids or []) if user_id]
    if not user_ids or db is None:
        return []
    try:
        result = execute_query(
            db.table("users").select("*").eq("role", "player"),
            "achievement_fresh_players",
            attempts=2,
        )
        players = [dict(item) for item in (result.data or [])]
        players.sort(key=_player_ranking_sort_key)
        positions = {str(item.get("id")): index for index, item in enumerate(players, 1)}
        by_id = {str(item.get("id")): item for item in players}

        existing_result = execute_query(
            db.table("user_achievements").select("user_id,achievement_code"),
            "achievement_existing",
            attempts=2,
        )
        existing = {(str(row.get("user_id")), row.get("achievement_code")) for row in (existing_result.data or [])}
        newly_unlocked = []
        for user_id in user_ids:
            player = by_id.get(user_id)
            if not player:
                continue
            for code in eligible_achievement_codes(player, positions.get(user_id)):
                if (user_id, code) in existing:
                    continue
                try:
                    execute_query(
                        db.table("user_achievements").insert({
                            "user_id": user_id,
                            "achievement_code": code,
                            "unlocked_at": now_iso(),
                        }),
                        "achievement_unlock",
                        attempts=2,
                    )
                    existing.add((user_id, code))
                    newly_unlocked.append((user_id, code))
                    if notify:
                        definition = ACHIEVEMENT_BY_CODE.get(code, {})
                        create_user_notification(
                            user_id,
                            f"{definition.get('icon', '🏅')} Huy hiệu mới",
                            f"Bạn đã mở khóa huy hiệu {definition.get('name', code)}.",
                            f"/profile/{user_id}",
                            "achievement",
                        )
                except Exception as exc:
                    if "duplicate" not in str(exc).lower():
                        print(f"achievement_unlock warning: {exc}")
        if has_request_context():
            setattr(g, "_rz_user_achievement_map", None)
        return newly_unlocked
    except Exception as exc:
        print(f"sync_achievements_for_users warning: {exc}")
        return []


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def is_admin_user(user) -> bool:
    return bool(
        user and (
            user.get("role") == "admin"
            or user.get("admin_level") in ADMIN_LEVELS
        )
    )


def is_owner_user(user) -> bool:
    return bool(
        user and (
            user.get("admin_level") == "owner"
        )
    )


ADMIN_PERMISSION_GROUPS = {
    "users": ["users_view", "users_approve", "users_edit", "users_delete", "password_reset", "accounts_import"],
    "matches": ["matches_view", "matches_confirm", "matches_cancel", "matches_delete"],
    "operations": ["rooms_manage", "invites_manage", "announcements_manage"],
    "system": ["system_features_manage", "chat_manage", "friendly_manage", "registration_codes_manage", "admin_logs_view"],
    "rp": ["rp_view", "rp_simulate", "rp_backup_restore"],
    "permissions": ["permissions_manage"],
}
ADMIN_PERMISSION_LABELS = {
    "users_view":"Xem người dùng", "users_approve":"Duyệt tài khoản", "users_edit":"Sửa tài khoản",
    "users_delete":"Xóa tài khoản", "password_reset":"Xử lý quên mật khẩu", "accounts_import":"Import CSV",
    "matches_view":"Xem trận",
    "matches_confirm":"Xác nhận trận", "matches_cancel":"Hủy trận", "matches_delete":"Xóa trận",
    "rooms_manage":"Quản lý phòng", "invites_manage":"Quản lý lời mời",
    "announcements_manage":"Quản lý thông báo", "system_features_manage":"Bật/tắt tính năng hệ thống", "chat_manage":"Quản lý Chat", "friendly_manage":"Quản lý Giao hữu",
    "registration_codes_manage":"Quản lý mã đăng ký", "admin_logs_view":"Xem nhật ký Admin",
    "rp_view":"Xem công thức RP", "rp_simulate":"Tính thử RP",
    "rp_backup_restore":"Backup/Khôi phục RP", "permissions_manage":"Cấp/thu hồi quyền Admin",
}
LEGACY_ADMIN_PERMISSION_FIELDS = {
    "create_test_account": "admin_can_create_test_account",
    "import_accounts_csv": "admin_can_import_accounts_csv",
    "accounts_import": "admin_can_import_accounts_csv",
}
SYSTEM_FEATURE_DEFAULTS = {
    "dashboard_enabled": False,
    "friendly_enabled": True, "lobby_chat_enabled": True, "room_chat_enabled": True,
    "registration_codes_enabled": True, "announcements_enabled": True,
}

def _admin_permissions(user):
    raw = (user or {}).get("admin_permissions") or {}
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except Exception: raw = {}
    return raw if isinstance(raw, dict) else {}


def has_admin_permission(user, permission_code: str) -> bool:
    if is_owner_user(user): return True
    if not is_admin_user(user): return False
    permissions = _admin_permissions(user)
    if permission_code in permissions: return permissions.get(permission_code) is True
    legacy = LEGACY_ADMIN_PERMISSION_FIELDS.get(permission_code)
    return bool(legacy and user.get(legacy) is True)


def get_system_features():
    features = dict(SYSTEM_FEATURE_DEFAULTS)
    try:
        result = execute_query(db.table("system_settings").select("setting_value").eq("setting_key", "admin_system_features").limit(1), "get_system_features", attempts=2)
        row = (result.data or [{}])[0]
        raw = row.get("setting_value")
        if isinstance(raw, str): raw = json.loads(raw)
        if isinstance(raw, dict): features.update({k: bool(v) for k,v in raw.items() if k in features})
    except Exception as exc:
        print(f"get_system_features warning: {exc}")
    return features


def system_feature_enabled(key: str) -> bool:
    return bool(get_system_features().get(key, SYSTEM_FEATURE_DEFAULTS.get(key, False)))


MAINTENANCE_SETTING_KEY = "server_maintenance_config"
VN_TIMEZONE = timezone(timedelta(hours=7))
_maintenance_cache = {"value": None, "expires_at": 0.0}


def _maintenance_default_config():
    return {
        "manual_closed": False,
        "close_at": "",
        "open_at": "",
        "message": "Hệ thống đang được bảo trì. Vui lòng quay lại sau.",
        "updated_at": "",
    }


def _parse_maintenance_time(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=VN_TIMEZONE)
        return parsed.astimezone(VN_TIMEZONE)
    except (TypeError, ValueError):
        return None


def _normalize_maintenance_input(value):
    parsed = _parse_maintenance_time(value)
    return parsed.isoformat(timespec="minutes") if parsed else ""


def get_maintenance_config(force=False):
    now_ts = time.time()
    if not force and _maintenance_cache.get("value") is not None and now_ts < _maintenance_cache.get("expires_at", 0):
        return dict(_maintenance_cache["value"])

    config = _maintenance_default_config()
    try:
        result = execute_query(
            db.table("system_settings").select("setting_value")
            .eq("setting_key", MAINTENANCE_SETTING_KEY).limit(1),
            "get_server_maintenance_config",
            attempts=2,
        )
        row = (result.data or [{}])[0]
        raw = row.get("setting_value")
        if isinstance(raw, str):
            raw = json.loads(raw)
        if isinstance(raw, dict):
            for key in config:
                if key in raw:
                    config[key] = raw[key]
    except Exception as exc:
        app.logger.warning("Maintenance config load failed: %s", exc)

    config["manual_closed"] = bool(config.get("manual_closed"))
    _maintenance_cache["value"] = dict(config)
    _maintenance_cache["expires_at"] = now_ts + 15
    return config


def get_maintenance_status(config=None):
    config = dict(config or get_maintenance_config())
    now = datetime.now(VN_TIMEZONE)
    close_at = _parse_maintenance_time(config.get("close_at"))
    open_at = _parse_maintenance_time(config.get("open_at"))

    closed = bool(config.get("manual_closed"))
    # Lịch đóng có thể bật máy chủ tự động, lịch mở có thể mở lại kể cả khi
    # công tắc đóng thủ công đang bật. Mốc thời gian đến sau có quyền ưu tiên.
    transitions = []
    if close_at:
        transitions.append((close_at, True, "close"))
    if open_at:
        transitions.append((open_at, False, "open"))
    for when, state, _kind in sorted(transitions, key=lambda item: item[0]):
        if now >= when:
            closed = state

    future = [(when, state, kind) for when, state, kind in transitions if when > now]
    next_transition = min(future, key=lambda item: item[0]) if future else None
    countdown = None
    if next_transition:
        seconds = max(0, int((next_transition[0] - now).total_seconds()))
        if seconds <= 30 * 60:
            countdown = {
                "kind": next_transition[2],
                "target_iso": next_transition[0].isoformat(),
                "seconds": seconds,
                "label": "Máy chủ sẽ đóng để bảo trì" if next_transition[2] == "close" else "Máy chủ sẽ mở trở lại",
            }

    return {
        "closed": closed,
        "message": str(config.get("message") or _maintenance_default_config()["message"]),
        "close_at": close_at.isoformat() if close_at else "",
        "open_at": open_at.isoformat() if open_at else "",
        "close_at_input": close_at.strftime("%Y-%m-%dT%H:%M") if close_at else "",
        "open_at_input": open_at.strftime("%Y-%m-%dT%H:%M") if open_at else "",
        "countdown": countdown,
    }


def _current_session_is_admin():
    if not session.get("user_id"):
        return False
    try:
        return is_admin_user(current_user())
    except Exception:
        return False


def normalize_invite_code(value: str) -> str:
    return (value or "").strip().upper().replace(" ", "")


def generate_invite_code_value(length: int = 10) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


RANK_RANGE_SETTING_KEY = "rank_ranges"
_rank_range_cache = {"value": None, "expires_at": 0.0}


def _validate_rank_ranges(raw_ranges):
    """Validate the 10 rank definitions stored in system_settings."""
    if isinstance(raw_ranges, dict):
        raw_ranges = raw_ranges.get("ranks") or raw_ranges.get("value") or raw_ranges
    if not isinstance(raw_ranges, list) or len(raw_ranges) != 10:
        raise ValueError("Cấu hình khoảng điểm Rank phải có đúng 10 Rank.")

    normalized = []
    previous_max = -1
    required_text_fields = ("name", "short_name", "abbr", "code", "icon", "slug")
    for index, item in enumerate(raw_ranges):
        if not isinstance(item, dict):
            raise ValueError(f"Rank {index + 1} không đúng định dạng.")
        row = dict(item)
        minimum = int(row.get("min"))
        maximum_raw = row.get("max")
        maximum = None if maximum_raw in (None, "", "null") else int(maximum_raw)
        if index == 0 and minimum != 0:
            raise ValueError("Rank đầu tiên phải bắt đầu từ 0 RP.")
        if index > 0 and minimum != previous_max + 1:
            raise ValueError(f"Rank {index + 1} phải bắt đầu từ {previous_max + 1} RP.")
        if index < 9 and maximum is None:
            raise ValueError(f"Rank {index + 1} phải có điểm kết thúc.")
        if maximum is not None and maximum < minimum:
            raise ValueError(f"Khoảng điểm Rank {index + 1} không hợp lệ.")
        if index == 9 and maximum is not None:
            raise ValueError("Rank cuối cùng phải để max = null.")
        for field in required_text_fields:
            row[field] = str(row.get(field) or "").strip()
            if not row[field]:
                raise ValueError(f"Rank {index + 1} thiếu trường {field}.")
        row["min"] = minimum
        row["max"] = maximum
        normalized.append(row)
        previous_max = maximum if maximum is not None else previous_max
    return normalized


def load_rank_ranges(force=False):
    """Always load active Rank ranges from Supabase system_settings."""
    now = time.time()
    if not force and _rank_range_cache["value"] is not None and now < _rank_range_cache["expires_at"]:
        return _rank_range_cache["value"]
    if db is None:
        raise RuntimeError("Chưa cấu hình kết nối Supabase để đọc khoảng điểm Rank.")

    result = execute_query(
        db.table("system_settings").select("setting_value").eq("setting_key", RANK_RANGE_SETTING_KEY).limit(1),
        "load_rank_ranges",
        attempts=3,
    )
    if not result.data:
        # Tự tạo cấu hình lần đầu để không cần chạy hoặc lưu file SQL trên GitHub.
        execute_query(
            db.table("system_settings").upsert({
                "setting_key": RANK_RANGE_SETTING_KEY,
                "setting_value": DEFAULT_RANKS,
                "updated_at": now_iso(),
            }, on_conflict="setting_key"),
            "seed_rank_ranges",
            attempts=3,
        )
        configured = _validate_rank_ranges(DEFAULT_RANKS)
    else:
        stored = result.data[0].get("setting_value")
        if isinstance(stored, str):
            stored = json.loads(stored)
        configured = _validate_rank_ranges(stored)

    _rank_range_cache.update({"value": configured, "expires_at": now + 30})
    return configured


def get_rank_ranges():
    return load_rank_ranges()


def get_rank_info(points: int):
    ranks = load_rank_ranges()
    safe=max(0,int(points or 0)); selected=ranks[0]
    for rank in ranks:
        if safe>=rank["min"]: selected=rank
    result=dict(selected); nxt=next((r for r in ranks if r["min"]>safe),None)
    result["points"]=safe; result["next_rank"]=nxt
    result["points_to_next"]=max(0,nxt["min"]-safe) if nxt else 0
    if nxt:
        span=max(1,nxt["min"]-selected["min"]); result["progress"]=max(0,min(100,round(((safe-selected["min"])/span)*100)))
    else: result["progress"]=100
    return result

def is_goat_player(player, position=None):
    """GOAT is the official level 10 rank (2700+ RP)."""
    return bool(player) and get_rank_info(player.get("rank_points", 0)).get("code") == "GOAT"


def get_player_rank_info(player, position=None):
    return get_rank_info(player.get("rank_points", 0) if player else 0)

def get_rank_name(points:int)->str: return get_rank_info(points)["name"]
def get_rank_display(points:int)->str:
    r=get_rank_info(points); return f'{r["icon"]} {r["name"]}'


def get_team_power_score(team_name):
    """Đọc power_score của CLB trực tiếp từ bảng teams trên Supabase."""
    info = get_db_team_info(team_name) if team_name else None
    if info and info.get("power_score") is not None:
        try:
            return float(info.get("power_score"))
        except (TypeError, ValueError):
            pass
    return 73.33


def get_tier_strength(tier):
    """Return numeric club strength: D=1 ... S+=7."""
    values = {"D": 1, "C": 2, "B": 3, "A": 4, "A+": 5, "S": 6, "S+": 7}
    return values.get(str(tier or "").strip().upper(), 1)


def get_match_difficulty(player, opponent, player_tier, opponent_tier):
    """Combined rank gap and club compensation.

    Positive values mean the player's real matchup is harder; negative values
    mean the player has the easier matchup.
    """
    rank_gap = get_rank_level(opponent.get("rank_points", 0)) - get_rank_level(player.get("rank_points", 0))
    club_compensation = get_tier_strength(player_tier) - get_tier_strength(opponent_tier)
    return rank_gap - club_compensation


def get_difficulty_factor(difficulty, won):
    """Return the requested win/loss coefficient for one player."""
    difficulty = int(difficulty or 0)
    if difficulty >= 3:
        return 1.20 if won else 0.80
    if difficulty >= 1:
        return 1.10 if won else 0.90
    if difficulty <= -3:
        return 0.80 if won else 1.20
    if difficulty <= -1:
        return 0.90 if won else 1.10
    return 1.00


def get_current_loss_streak(user_id):
    """Đếm số trận thua liên tiếp gần nhất từ lịch sử đã xác nhận."""
    if not user_id or db is None:
        return 0
    try:
        result = execute_query(
            db.table("matches")
            .select("player1_id,player2_id,score1,score2,status,created_at")
            .or_(f"player1_id.eq.{user_id},player2_id.eq.{user_id}")
            .eq("status", "confirmed")
            .order("created_at", desc=True)
            .limit(30),
            f"get_loss_streak:{user_id}",
            attempts=2,
        )
    except Exception as exc:
        print(f"get_current_loss_streak warning user={user_id}: {type(exc).__name__}: {exc}")
        return 0

    streak = 0
    for match in result.data or []:
        score1 = _safe_int(match.get("score1"), -1)
        score2 = _safe_int(match.get("score2"), -1)
        if score1 < 0 or score2 < 0 or score1 == score2:
            break
        is_player1 = str(match.get("player1_id")) == str(user_id)
        lost = (is_player1 and score1 < score2) or ((not is_player1) and score2 < score1)
        if not lost:
            break
        streak += 1
    return streak


def calculate_deltas(player_a, player_b, score_a: int, score_b: int, team_a=None, team_b=None,
                     team_overall_a=None, team_overall_b=None, team_tier_a=None, team_tier_b=None,
                     rng=None):
    """Lớp tương thích: route cũ gọi như trước, công thức nằm trong rp_engine."""
    player_a_for_rp = dict(player_a or {})
    player_b_for_rp = dict(player_b or {})
    player_a_for_rp["loss_streak"] = get_current_loss_streak(player_a_for_rp.get("id"))
    player_b_for_rp["loss_streak"] = get_current_loss_streak(player_b_for_rp.get("id"))
    return calculate_ranked_deltas(
        player_a_for_rp, player_b_for_rp, score_a, score_b, get_rank_level=get_rank_level,
        team_a=team_a, team_b=team_b, team_overall_a=team_overall_a,
        team_overall_b=team_overall_b, team_tier_a=team_tier_a, team_tier_b=team_tier_b,
        rng=rng,
    )

TEAM_LOGO_BUCKET = "team-logos"
LEAGUE_LOGO_FOLDER = "league-logos"
LEAGUE_LOGO_FILES = {
    "africa": "africa.png",
    "bundesliga": "bundesliga.png",
    "europe": "europe.png",
    "laliga ea sports": "laliga-ea-sports.png",
    "la liga ea sports": "laliga-ea-sports.png",
    "laliga": "laliga-ea-sports.png",
    "ligue 1": "ligue-1.png",
    "ligue1": "ligue-1.png",
    "premier league": "premier-league.png",
    "serie a": "serie-a.png",
    "serie bkt": "serie-bkt.png",
    "sky bet championship": "sky-bet-championship.png",
    "championship": "sky-bet-championship.png",
    "south america": "south-america.png",
    "super lig": "super-lig.png",
    "süper lig": "super-lig.png",
}

def get_league_logo_url(league_name):
    """Tạo URL public tới team-logos/league-logos trên Supabase Storage."""
    import unicodedata
    raw = str(league_name or "").strip()
    if not raw or not supabase_url:
        return ""
    key = " ".join(raw.lower().replace("-", " ").replace("_", " ").split())
    key_ascii = "".join(ch for ch in unicodedata.normalize("NFKD", key) if not unicodedata.combining(ch))
    filename = LEAGUE_LOGO_FILES.get(key) or LEAGUE_LOGO_FILES.get(key_ascii)
    if not filename:
        for alias, candidate in LEAGUE_LOGO_FILES.items():
            if alias in key or alias in key_ascii:
                filename = candidate
                break
    if not filename:
        return ""
    from urllib.parse import quote
    object_path = f"{LEAGUE_LOGO_FOLDER}/{filename}"
    return f"{supabase_url}/storage/v1/object/public/{TEAM_LOGO_BUCKET}/{quote(object_path, safe='/')}"

SMART_RANDOM_MODE = "Smart Rank"


CLUB_TIER_RANGES = {
    "S+": (80.50, 81.60),
    "S": (79.50, 80.49),
    "A+": (78.50, 79.49),
    "A": (77.50, 78.49),
    "B": (76.00, 77.49),
    "C": (74.50, 75.99),
    "D": (73.33, 74.49),
}
CLUB_TIER_ORDER = ["S+", "S", "A+", "A", "B", "C", "D"]

# Tỷ lệ Tier CLB theo từng Rank (khóa là level 0..9 trong code).
# Tổng tỷ lệ của mỗi Rank luôn bằng 100.
RANK_CLUB_TIER_WEIGHTS = {
    0: {"S+": 100},
    1: {"S+": 100},
    2: {"S+": 100},
    3: {"S+": 75, "S": 25},
    4: {"S+": 10, "S": 45, "A+": 45},
    5: {"S+": 5, "S": 20, "A+": 50, "A": 25},
    6: {"S": 5, "A+": 15, "A": 45, "B": 35},
    7: {"A+": 5, "A": 10, "B": 50, "C": 35},
    8: {"B": 10, "C": 55, "D": 35},
    9: {"B": 15, "C": 25, "D": 60},
}


def power_score_to_tier(power_score):
    """Classify one club into S+..D using power_score only."""
    try:
        score = float(power_score)
    except (TypeError, ValueError):
        return "D"
    for tier in CLUB_TIER_ORDER:
        minimum, maximum = CLUB_TIER_RANGES[tier]
        if minimum <= score <= maximum:
            return tier
    if score > CLUB_TIER_RANGES["S+"][1]:
        return "S+"
    return "D"


def _normalize_team_row(row):
    """Chuẩn hóa một dòng CLB lấy trực tiếp từ bảng teams trên Supabase."""
    if not row:
        return None
    name = row.get("team") or row.get("display")
    if not name:
        return None
    try:
        overall = int(row.get("overall") or 0)
    except (TypeError, ValueError):
        return None
    if overall <= 0:
        return None
    return {
        "id": row.get("id"),
        "display": str(name),
        "team": str(name),
        "league": row.get("league") or "",
        "overall": overall,
        "tier": str(row.get("tier") or power_score_to_tier(row.get("power_score"))).strip().upper(),
        "logo_file": row.get("logo_file") or "",
        "logo_url": row.get("logo_url") or "",
        "defence": row.get("defence"),
        "midfield": row.get("midfield"),
        "attack": row.get("attack"),
        "speed": row.get("speed"),
        "strength": row.get("strength"),
        "total_stats": row.get("total_stats"),
        "power_score": row.get("power_score"),
    }


_TEAM_CACHE = {"loaded_at": 0.0, "rows": [], "by_name": {}, "pools": {}}
_TEAM_CACHE_TTL_SECONDS = 30
TEAM_COUNT = 0


def _load_teams_from_supabase(force=False):
    """Chỉ đọc CLB từ Supabase; không còn CSV hoặc teams_data.py dự phòng."""
    global TEAM_COUNT
    now = time.monotonic()
    if not force and _TEAM_CACHE["rows"] and now - _TEAM_CACHE["loaded_at"] < _TEAM_CACHE_TTL_SECONDS:
        return _TEAM_CACHE["rows"]
    if db is None:
        raise RuntimeError("Chưa cấu hình kết nối Supabase để đọc bảng teams.")
    result = execute_query(
        db.table("teams")
        .select("id,league,team,overall,defence,midfield,attack,speed,strength,total_stats,power_score,tier,logo_file,logo_url,is_active")
        .eq("is_active", True),
        "load_teams_from_supabase",
        attempts=3,
    )
    rows = []
    by_name = {}
    pools = {}
    for raw in result.data or []:
        team = _normalize_team_row(raw)
        if not team:
            continue
        rows.append(team)
        by_name[team["team"].casefold()] = team
        pools.setdefault(team["overall"], []).append(team)
    if not rows:
        raise RuntimeError("Bảng teams trên Supabase không có CLB hoạt động.")
    _TEAM_CACHE.update({"loaded_at": now, "rows": rows, "by_name": by_name, "pools": pools})
    TEAM_COUNT = len(rows)
    return rows


def get_random_team_pools():
    """Trả nhóm CLB theo overall, chỉ từ Supabase."""
    _load_teams_from_supabase()
    return _TEAM_CACHE["pools"]


def get_db_team_info(team_name):
    """Tìm CLB theo tên trong dữ liệu Supabase đã cache ngắn hạn."""
    if not team_name:
        return None
    try:
        _load_teams_from_supabase()
        return _TEAM_CACHE["by_name"].get(str(team_name).casefold())
    except Exception as exc:
        print(f"get_db_team_info error: {exc}")
        return None


def get_team_info(team_name):
    return get_db_team_info(team_name)


def get_team_overall(team_name):
    info = get_db_team_info(team_name)
    try:
        return int(info.get("overall")) if info else 0
    except (TypeError, ValueError):
        return 0


def get_team_tier(team_name):
    info = get_db_team_info(team_name)
    return str(info.get("tier") or "") if info else ""


SMART_RANDOM_MODE = "Smart Tier Random"
RECENT_TEAM_EXCLUSION_COUNT = 5
HOST_XP_FACTOR = 0.95
MATCH_MODE_RANKED = "ranked"
MATCH_MODE_FRIENDLY = "friendly"


def get_rank_level(points: int) -> int:
    """Return rank level from 0 (lowest) to 9 (highest)."""
    safe_points = max(0, int(points or 0))
    level = 0
    for index, rank in enumerate(load_rank_ranges()):
        if safe_points >= rank["min"]:
            level = index
    return level


RANK_TIER_SETTING_KEY = "rank_club_tier_weights"
_rank_tier_config_cache = {"value": None, "expires_at": 0.0}


def _validate_rank_tier_weights(raw_weights):
    """Validate imported 1..10 Rank mapping and convert it to internal 0..9 levels."""
    if not isinstance(raw_weights, dict):
        raise ValueError("RANK_CLUB_TIER_WEIGHTS phải là một dictionary.")

    normalized = {}
    for rank_number in range(1, len(load_rank_ranges()) + 1):
        row = raw_weights.get(rank_number)
        if row is None:
            row = raw_weights.get(str(rank_number))
        if not isinstance(row, dict) or not row:
            raise ValueError(f"Rank {rank_number} chưa có tỷ lệ Tier CLB.")

        clean_row = {}
        total = 0
        for tier, percent in row.items():
            tier = str(tier).strip().upper()
            if tier not in CLUB_TIER_ORDER:
                raise ValueError(f"Rank {rank_number} có Tier không hợp lệ: {tier}.")
            if isinstance(percent, bool) or not isinstance(percent, (int, float)):
                raise ValueError(f"Tỷ lệ {tier} của Rank {rank_number} phải là số.")
            percent = int(percent)
            if percent < 0 or percent > 100:
                raise ValueError(f"Tỷ lệ {tier} của Rank {rank_number} phải từ 0 đến 100.")
            if percent:
                clean_row[tier] = percent
                total += percent

        if total != 100:
            raise ValueError(f"Tổng tỷ lệ Rank {rank_number} đang là {total}%, bắt buộc phải bằng 100%.")
        normalized[rank_number - 1] = clean_row
    return normalized


def load_rank_tier_weights(force=False):
    now = time.time()
    if not force and _rank_tier_config_cache["value"] is not None and now < _rank_tier_config_cache["expires_at"]:
        return _rank_tier_config_cache["value"]

    configured = RANK_CLUB_TIER_WEIGHTS
    if db is not None:
        try:
            result = execute_query(
                db.table("system_settings").select("setting_value").eq("setting_key", RANK_TIER_SETTING_KEY).limit(1),
                "load_rank_tier_weights",
                attempts=2,
            )
            if result.data:
                stored = result.data[0].get("setting_value")
                if isinstance(stored, str):
                    stored = json.loads(stored)
                configured = _validate_rank_tier_weights(stored)
        except Exception as exc:
            print(f"load_rank_tier_weights fallback warning: {exc}")

    _rank_tier_config_cache.update({"value": configured, "expires_at": now + 30})
    return configured


def get_rank_tier_weights(level: int):
    """Return the active Admin-configured Tier percentages for one rank level."""
    safe_level = max(0, min(len(load_rank_ranges()) - 1, int(level or 0)))
    return load_rank_tier_weights().get(safe_level, RANK_CLUB_TIER_WEIGHTS[safe_level])


def _all_random_teams():
    pools = get_random_team_pools()
    teams = []
    for pool in pools.values():
        for team in pool:
            team = dict(team)
            try:
                team["power_score"] = float(team.get("power_score"))
            except (TypeError, ValueError):
                team["power_score"] = round(73.33 + (int(team.get("overall", 73)) - 73) * 0.75, 2)
            # Tier is always calculated from power_score, never trusted from stale CSV data.
            team["tier"] = power_score_to_tier(team["power_score"])
            teams.append(team)
    return teams


def _recent_team_names(user_id, limit=RECENT_TEAM_EXCLUSION_COUNT):
    """Return the last distinct clubs used by one player, newest first."""
    if not user_id:
        return []
    names = []
    try:
        matches = sorted(
            list_matches(),
            key=lambda item: str(item.get("created_at") or item.get("updated_at") or ""),
            reverse=True,
        )
        for match in matches:
            if match.get("player1_id") == user_id:
                name = match.get("team1")
            elif match.get("player2_id") == user_id:
                name = match.get("team2")
            else:
                continue
            if name and name not in names:
                names.append(name)
            if len(names) >= limit:
                break
    except Exception as exc:
        print(f"recent_team_history warning: {exc}")
    return names


def _teams_in_tiers(teams, tiers, excluded_names=None):
    allowed = {str(tier).upper() for tier in (tiers or [])}
    excluded = {str(name).casefold() for name in (excluded_names or []) if name}
    return [
        team for team in teams
        if str(team.get("tier") or "").upper() in allowed
        and str(team.get("display") or "").casefold() not in excluded
    ]


def _weighted_tier_choice(tier_weights, teams, excluded_names):
    """Pick a Tier by configured percentage, then return clubs in that Tier.

    If a configured Tier has no available club after anti-repeat filtering,
    the remaining available percentages are automatically re-normalized.
    """
    available = []
    for tier, weight in (tier_weights or {}).items():
        candidates = _teams_in_tiers(teams, [tier], excluded_names)
        if candidates and float(weight or 0) > 0:
            available.append((tier, float(weight), candidates))
    if not available:
        return None, []

    roll = random.random() * sum(weight for _, weight, _ in available)
    cumulative = 0.0
    for tier, weight, candidates in available:
        cumulative += weight
        if roll <= cumulative:
            return tier, candidates
    tier, _, candidates = available[-1]
    return tier, candidates

def _pick_rank_team(player, all_teams, extra_excluded=None):
    level = get_rank_level(player.get("rank_points", 0))
    tier_weights = get_rank_tier_weights(level)
    recent = _recent_team_names(player.get("id"))
    extra = list(extra_excluded or [])
    excluded = list(dict.fromkeys(recent + extra))
    selected_tier, candidates = _weighted_tier_choice(tier_weights, all_teams, excluded)

    # Keep anti-repeat whenever possible; relax 5 -> 3 -> 1 -> 0 only if needed.
    if not candidates:
        for keep_recent in (3, 1, 0):
            selected_tier, candidates = _weighted_tier_choice(
                tier_weights, all_teams, recent[:keep_recent] + extra
            )
            if candidates:
                break
    if not candidates:
        raise ValueError(f"Không có CLB phù hợp cho rank {load_rank_ranges()[level]['name']}.")
    return random.choice(candidates), selected_tier, tier_weights, recent


def get_smart_random_rule(player_a, player_b):
    level_a = get_rank_level(player_a.get("rank_points", 0))
    level_b = get_rank_level(player_b.get("rank_points", 0))
    return {
        "level_a": level_a,
        "level_b": level_b,
        "rank_gap": abs(level_a - level_b),
        "advantage": "Mỗi Rank có tỷ lệ xuất hiện Tier CLB riêng.",
        "summary": "Random theo tỷ lệ Tier riêng của từng Rank; chống lặp 5 CLB gần nhất; không trùng CLB.",
        "rule_a": get_rank_tier_weights(level_a),
        "rule_b": get_rank_tier_weights(level_b),
    }


def smart_random_team_pair(player_a, player_b):
    """Random clubs from rank-linked S+..D tiers with anti-repeat protection."""
    all_teams = _all_random_teams()
    if len(all_teams) < 2:
        raise ValueError("Không đủ dữ liệu CLB để Smart Random.")

    team_a, tier_a_selected, weights_a, recent_a = _pick_rank_team(player_a, all_teams)
    team_b, tier_b_selected, weights_b, recent_b = _pick_rank_team(
        player_b, all_teams, extra_excluded=[team_a.get("display")]
    )

    if str(team_a.get("display")).casefold() == str(team_b.get("display")).casefold():
        allowed_b = set(weights_b.keys())
        alternatives = [
            team for team in all_teams
            if str(team.get("display")).casefold() != str(team_a.get("display")).casefold()
            and str(team.get("tier") or "").upper() in allowed_b
        ]
        if not alternatives:
            raise ValueError("Không tìm được hai CLB khác nhau trong các Tier phù hợp.")
        team_b = random.choice(alternatives)

    return {
        "mode": SMART_RANDOM_MODE,
        "team_a": team_a["display"],
        "team_b": team_b["display"],
        "overall_a": int(team_a["overall"]),
        "overall_b": int(team_b["overall"]),
        "total_stats_a": int(team_a.get("total_stats") or 0),
        "total_stats_b": int(team_b.get("total_stats") or 0),
        "power_score_a": float(team_a.get("power_score", 0)),
        "power_score_b": float(team_b.get("power_score", 0)),
        "tier_a": team_a["tier"],
        "tier_b": team_b["tier"],
        "logo_a": team_a.get("logo_url") or "",
        "logo_b": team_b.get("logo_url") or "",
        "league_a": team_a.get("league") or "",
        "league_b": team_b.get("league") or "",
        "team_id_a": team_a.get("id"),
        "team_id_b": team_b.get("id"),
        "band_a": tier_a_selected,
        "band_b": tier_b_selected,
        "recent_excluded_a": recent_a,
        "recent_excluded_b": recent_b,
        "rank_gap": abs(get_rank_level(player_a.get("rank_points", 0)) - get_rank_level(player_b.get("rank_points", 0))),
        "summary": get_smart_random_rule(player_a, player_b)["summary"],
    }


def get_available_team_tiers():
    """Return active club tiers for the friendly-mode selector."""
    tiers = []
    for team in _all_random_teams():
        tier = str(team.get("tier") or "").strip().upper()
        if tier and tier not in tiers:
            tiers.append(tier)
    preferred = CLUB_TIER_ORDER
    return sorted(tiers, key=lambda value: (preferred.index(value) if value in preferred else 99, value))


def friendly_random_team_pair(tier, excluded_names=None):
    """Pick two different active clubs from the selected tier; no history is created."""
    selected_tier = str(tier or "").strip().upper()
    if not selected_tier:
        raise ValueError("Hãy chọn Tier CLB cho trận giao hữu.")
    excluded = {str(name or "").casefold() for name in (excluded_names or []) if name}
    candidates = [
        team for team in _all_random_teams()
        if str(team.get("tier") or "").strip().upper() == selected_tier
        and str(team.get("display") or "").casefold() not in excluded
    ]
    if len(candidates) < 2 and excluded:
        candidates = [
            team for team in _all_random_teams()
            if str(team.get("tier") or "").strip().upper() == selected_tier
        ]
    if len(candidates) < 2:
        raise ValueError(f"Tier {selected_tier} cần ít nhất 2 CLB khác nhau để đá giao hữu.")
    team_a, team_b = random.sample(candidates, 2)
    return {
        "mode": MATCH_MODE_FRIENDLY,
        "selected_tier": selected_tier,
        "team_a": team_a["display"],
        "team_b": team_b["display"],
        "overall_a": int(team_a["overall"]),
        "overall_b": int(team_b["overall"]),
        "total_stats_a": int(team_a.get("total_stats") or 0),
        "total_stats_b": int(team_b.get("total_stats") or 0),
        "power_score_a": float(team_a.get("power_score", 0)),
        "power_score_b": float(team_b.get("power_score", 0)),
        "tier_a": team_a.get("tier") or selected_tier,
        "tier_b": team_b.get("tier") or selected_tier,
        "logo_a": team_a.get("logo_url") or "",
        "logo_b": team_b.get("logo_url") or "",
        "league_a": team_a.get("league") or "",
        "league_b": team_b.get("league") or "",
    }


def apply_host_xp_factor(delta, factor=HOST_XP_FACTOR):
    """Apply the room-host coefficient to the absolute RP change."""
    try:
        safe_factor = float(factor or HOST_XP_FACTOR)
    except (TypeError, ValueError):
        safe_factor = HOST_XP_FACTOR
    value = int(delta or 0)
    if value <= 0:
        return value
    adjusted = round(value * safe_factor)
    return max(1, adjusted)


def require_db():
    if db is None:
        raise RuntimeError("Supabase chưa được cấu hình. Kiểm tra file .env.")


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def get_device_id():
    device_id = request.cookies.get(DEVICE_COOKIE_NAME)
    if not device_id:
        device_id = getattr(g, "new_device_id", None)
    if not device_id:
        device_id = str(uuid.uuid4())
        g.new_device_id = device_id
    return device_id


@app.after_request
def set_device_cookie(response):
    device_id = getattr(g, "new_device_id", None)
    if device_id:
        response.set_cookie(
            DEVICE_COOKIE_NAME,
            device_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
        )
    return response


# =========================
# Database helpers
# =========================

def get_user_by_username(username):
    """Find a user by username without creating extra Supabase clients."""
    require_db()
    normalized = str(username or "").strip()
    if not normalized:
        return None

    result = execute_query(
        db.table("users").select("*").ilike("username", normalized).limit(20),
        "get_user_by_username",
    )
    target = normalized.casefold()
    return next(
        (
            row for row in (result.data or [])
            if str(row.get("username") or "").strip().casefold() == target
        ),
        None,
    )


def get_user(user_id):
    require_db()
    result = execute_query(
        db.table("users").select("*").eq("id", user_id).limit(1),
        "get_user",
    )
    return result.data[0] if result.data else None


def is_user_online_now(user):
    seen = parse_dt((user or {}).get("last_seen_at"))
    cutoff = now_dt() - timedelta(seconds=ONLINE_TIMEOUT_SECONDS)
    return bool((user or {}).get("is_online")) and bool(seen) and seen >= cutoff


def _player_ranking_sort_key(player):
    points = int(player.get("rank_points", 0) or 0)
    wins = int(player.get("wins", 0) or 0)
    goals_for = int(player.get("goals_for", 0) or 0)
    goals_against = int(player.get("goals_against", 0) or 0)
    total_matches = int(player.get("total_matches", 0) or 0)
    name = str(player.get("display_name") or player.get("username") or "").casefold()
    return (-points, -wins, -(goals_for - goals_against), -goals_for, -total_matches, name)


def list_players(include_admin=False):
    require_db()
    cached = cache_get("_rz_players_all")
    if cached is None:
        shared = ttl_cache_get("players_raw")
        if shared is None:
            result = execute_query(
                db.table("users").select("*").order("rank_points", desc=True),
                "list_players",
            )
            shared = result.data or []
            ttl_cache_set("players_raw", shared, 8)
        cached = [dict(row) for row in shared]
        cache_set("_rz_players_all", cached)

    players = cached if include_admin else [p for p in cached if p.get("role") == "player"]
    safe = []
    for player in players:
        item = dict(player)
        item["is_online"] = is_user_online_now(item)
        safe.append(item)

    # Xếp hạng ổn định khi nhiều người bằng điểm: thắng, hiệu số, bàn thắng, số trận.
    achievement_map = list_user_achievement_map()
    if not include_admin:
        safe.sort(key=_player_ranking_sort_key)
        for position, item in enumerate(safe, 1):
            item["position"] = position
            item["rank_info"] = get_player_rank_info(item, position)
            decorate_player_achievements(item, position, achievement_map)
    else:
        for item in safe:
            item["rank_info"] = get_rank_info(item.get("rank_points", 0))
            decorate_player_achievements(item, None, achievement_map)

    return safe


def users_map():
    cached = cache_get("_rz_users_map")
    if cached is not None:
        return cached

    mapped = {user["id"]: user for user in list_players(include_admin=True)}
    return cache_set("_rz_users_map", mapped)


def get_device_link(device_id):
    result = db.table("user_devices").select("*").eq("device_id", device_id).limit(1).execute()
    return result.data[0] if result.data else None


def link_device_to_user(user):
    # Tài khoản admin chính không bị giới hạn thiết bị; admin phụ vẫn là player.
    if user.get("role") == "admin":
        return True, ""

    device_id = get_device_id()
    link = get_device_link(device_id)

    if link and link["user_id"] != user["id"]:
        return False, "Thiết bị này đã được liên kết với một tài khoản player khác."

    ip = get_client_ip()
    user_agent = request.headers.get("User-Agent", "")

    if not link:
        execute_query(
            db.table("user_devices").insert({
                "user_id": user["id"],
                "device_id": device_id,
                "ip_address": ip,
                "user_agent": user_agent,
                "last_seen_at": now_iso(),
            }),
            "link_device_create",
        )
    else:
        execute_query(
            db.table("user_devices").update({
                "ip_address": ip,
                "user_agent": user_agent,
                "last_seen_at": now_iso(),
            }).eq("id", link["id"]),
            "link_device_update",
        )

    return True, ""


def device_can_register():
    device_id = get_device_id()
    link = get_device_link(device_id)
    if link:
        return False, "Thiết bị này đã có tài khoản player. Mỗi thiết bị chỉ được tạo 1 tài khoản."

    ip = get_client_ip()
    ua = request.headers.get("User-Agent", "")

    # Chặn mềm: cùng IP + cùng User Agent đã từng đăng ký.
    result = (
        db.table("users")
        .select("id")
        .eq("role", "player")
        .eq("register_ip", ip)
        .eq("register_user_agent", ua)
        .limit(1)
        .execute()
    )

    if result.data:
        return False, "Thiết bị/trình duyệt này có dấu hiệu đã đăng ký tài khoản player."

    return True, ""



def list_all_users():
    require_db()
    result = execute_query(
        db.table("users").select("*").order("created_at", desc=True),
        "list_all_users",
    )
    return result.data or []


def log_admin_action(action, target_type="system", target_id=None, target_label="", details=""):
    """Ghi nhật ký quản trị; lỗi ghi log không được làm hỏng thao tác chính."""
    try:
        actor = current_user()
        if not actor or not is_admin_user(actor):
            return
        execute_query(
            db.table("admin_activity_logs").insert({
                "admin_user_id": actor.get("id"),
                "admin_name": actor.get("username") or actor.get("display_name") or "Admin",
                "action": str(action)[:80],
                "target_type": str(target_type)[:50],
                "target_id": str(target_id)[:120] if target_id else None,
                "target_label": str(target_label)[:160] if target_label else None,
                "details": str(details)[:1000] if details else None,
                "ip_address": get_client_ip(),
            }),
            "log_admin_action",
            attempts=2,
        )
    except Exception as exc:
        print(f"Admin audit log warning: {exc}")


def existing_user_id(user_id):
    """Trả về UUID chỉ khi người dùng thực sự còn tồn tại trong public.users."""
    if not user_id:
        return None
    try:
        result = execute_query(
            db.table("users").select("id").eq("id", user_id).limit(1),
            "existing_user_id",
            attempts=1,
        )
        rows = result.data or []
        return rows[0].get("id") if rows else None
    except Exception as exc:
        print(f"existing_user_id warning: {exc}")
        return None


def create_admin_announcement(title, message, admin_user_id=None):
    """Tạo thông báo và tự phục hồi khi khóa ngoại admin cũ bị lệch.

    Một số dự án nâng cấp từ phiên bản cũ còn giữ session/admin UUID không còn
    tồn tại trong public.users. Khi đó Postgres trả mã 23503. Thông báo không
    bắt buộc phải có admin_user_id nên ta thử lại với NULL thay vì gây lỗi 500.
    """
    payload = {
        "admin_user_id": existing_user_id(admin_user_id),
        "title": title,
        "message": message,
        "is_active": True,
    }
    try:
        return db.table("admin_announcements").insert(payload).execute()
    except Exception as exc:
        error_code = str(getattr(exc, "code", "") or "")
        error_text = str(exc)
        if payload["admin_user_id"] and (error_code == "23503" or "23503" in error_text):
            payload["admin_user_id"] = None
            return db.table("admin_announcements").insert(payload).execute()
        raise


def list_admin_activity_logs(limit=150):
    try:
        result = execute_query(
            db.table("admin_activity_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit),
            "list_admin_activity_logs",
        )
        return result.data or []
    except Exception as exc:
        print(f"list_admin_activity_logs warning: {exc}")
        return []


def get_password_reset_request(request_id):
    result = execute_query(
        db.table("password_reset_requests").select("*").eq("id", request_id).limit(1),
        "get_password_reset_request",
    )
    return result.data[0] if result.data else None


def list_password_reset_requests(status=None, limit=100):
    try:
        query = (
            db.table("password_reset_requests")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        result = execute_query(query, "list_password_reset_requests")
        rows = [dict(row) for row in (result.data or [])]
        users = users_map()
        for row in rows:
            user = users.get(row.get("user_id"), {})
            row["current_username"] = user.get("username") or row.get("username_snapshot") or "-"
            row["current_zalo_name"] = user.get("zalo_name") or row.get("zalo_name_snapshot") or "-"
        return rows
    except Exception as exc:
        print(f"list_password_reset_requests warning: {exc}")
        return []


def list_user_devices():
    """Lấy IP gần nhất của thiết bị để Admin kiểm tra trùng IP."""
    require_db()
    try:
        result = execute_query(
            db.table("user_devices")
            .select("user_id,ip_address,last_seen_at,created_at")
            .order("last_seen_at", desc=True),
            "list_user_devices",
        )
        return result.data or []
    except Exception as exc:
        # Không làm sập trang Admin nếu bảng thiết bị tạm thời truy vấn lỗi.
        print(f"list_user_devices warning: {exc}")
        return []


def decorate_admin_users(users):
    """Bổ sung IP gần nhất và cảnh báo IP dùng chung cho danh sách Admin."""
    rows = [dict(user) for user in users]
    for row in rows:
        row["admin_permissions"] = _admin_permissions(row)
    devices = list_user_devices()

    known_ips_by_user = {str(user.get("id")): set() for user in rows}
    latest_ip_by_user = {}

    for user in rows:
        user_id = str(user.get("id"))
        register_ip = (user.get("register_ip") or "").strip()
        if register_ip:
            known_ips_by_user.setdefault(user_id, set()).add(register_ip)

    # Dữ liệu đã sắp xếp mới nhất trước, nên IP đầu tiên là IP gần nhất.
    for device in devices:
        user_id = str(device.get("user_id") or "")
        ip = (device.get("ip_address") or "").strip()
        if not user_id or not ip:
            continue
        known_ips_by_user.setdefault(user_id, set()).add(ip)
        latest_ip_by_user.setdefault(user_id, ip)

    ip_owners = {}
    for user_id, ip_values in known_ips_by_user.items():
        for ip in ip_values:
            ip_owners.setdefault(ip, set()).add(user_id)

    username_by_id = {str(user.get("id")): user.get("username", "-") for user in rows}

    for user in rows:
        user_id = str(user.get("id"))
        known_ips = sorted(known_ips_by_user.get(user_id, set()))
        duplicate_ips = [ip for ip in known_ips if len(ip_owners.get(ip, set())) > 1]
        duplicate_accounts = sorted({
            username_by_id.get(owner_id, "-")
            for ip in duplicate_ips
            for owner_id in ip_owners.get(ip, set())
            if owner_id != user_id
        })

        user["latest_ip"] = latest_ip_by_user.get(user_id) or user.get("register_ip") or "-"
        user["known_ips"] = known_ips
        user["duplicate_ips"] = duplicate_ips
        user["duplicate_ip_count"] = max(
            [len(ip_owners.get(ip, set())) for ip in duplicate_ips] or [0]
        )
        user["duplicate_ip_accounts"] = duplicate_accounts

    return rows


def build_duplicate_ip_groups(users):
    """Gom các IP đang được từ 2 tài khoản trở lên sử dụng để Admin dễ kiểm tra clone."""
    ip_users = {}

    for user in users:
        user_id = str(user.get("id") or "")
        if not user_id:
            continue
        for ip in user.get("known_ips") or []:
            normalized_ip = (ip or "").strip()
            if not normalized_ip:
                continue
            ip_users.setdefault(normalized_ip, {})[user_id] = user

    groups = []
    for ip, owners in ip_users.items():
        if len(owners) < 2:
            continue

        accounts = sorted(
            [
                {
                    "id": owner.get("id"),
                    "username": owner.get("username") or "-",
                    "display_name": owner.get("display_name") or owner.get("username") or "-",
                    "account_status": owner.get("account_status") or "approved",
                    "role": owner.get("role") or "player",
                    "admin_level": owner.get("admin_level") or "none",
                }
                for owner in owners.values()
            ],
            key=lambda item: item["username"].lower(),
        )
        groups.append({
            "ip": ip,
            "account_count": len(accounts),
            "accounts": accounts,
            "usernames": [item["username"] for item in accounts],
        })

    groups.sort(key=lambda item: (-item["account_count"], item["ip"]))
    return groups


def get_invite_code_record(code_value):
    code_value = normalize_invite_code(code_value)
    if not code_value:
        return None
    result = execute_query(
        db.table("registration_invite_codes")
        .select("*")
        .eq("code", code_value)
        .limit(1),
        "get_invite_code_record",
    )
    return result.data[0] if result.data else None


def list_registration_invite_codes(limit=100):
    result = execute_query(
        db.table("registration_invite_codes")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit),
        "list_registration_invite_codes",
    )
    records = result.data or []
    users = {u["id"]: u for u in list_all_users()}
    for record in records:
        record["created_by_name"] = users.get(record.get("created_by"), {}).get("display_name", "-")
        record["used_by_name"] = users.get(record.get("used_by"), {}).get("display_name", "-")
    return records


def list_matches(status=None):
    require_db()

    cached = cache_get("_rz_matches_all")
    if cached is None:
        query = db.table("matches").select("*").order("created_at", desc=True)
        result = execute_query(query, "list_matches")
        cached = result.data or []
        cache_set("_rz_matches_all", cached)

    matches = [dict(m) for m in cached if not status or m.get("status") == status]
    users = users_map()

    for match in matches:
        player1 = users.get(match.get("player1_id"), {})
        player2 = users.get(match.get("player2_id"), {})
        match["player1_name"] = player1.get("display_name", "Unknown")
        match["player2_name"] = player2.get("display_name", "Unknown")
        match["player1_avatar_url"] = player1.get("avatar_url")
        match["player2_avatar_url"] = player2.get("avatar_url")
        match["player1_achievement"] = player1.get("featured_achievement")
        match["player2_achievement"] = player2.get("featured_achievement")
        match["submitted_by_name"] = users.get(match.get("submitted_by_id"), {}).get("display_name", "")
        match["winner_name"] = users.get(match.get("winner_id"), {}).get("display_name", "")
        match["loser_name"] = users.get(match.get("loser_id"), {}).get("display_name", "")

    return matches


def match_status_label(status):
    return MATCH_STATUS_LABELS.get(status, str(status or "-").replace("_", " ").title())


def decorate_match_for_view(match, viewer_id=None):
    item = dict(match or {})
    item["status_label"] = match_status_label(item.get("status"))
    item["created_at_display"] = format_vn_datetime(item.get("created_at"))
    item["is_cancelled"] = item.get("status") == "cancelled"
    item["score_display"] = (
        "Không tính"
        if item["is_cancelled"]
        else f'{item.get("score1")} - {item.get("score2")}'
    )

    item["is_mine"] = bool(
        viewer_id
        and viewer_id in {item.get("player1_id"), item.get("player2_id")}
    )
    item["result_code"] = "neutral"
    item["result_label"] = item["status_label"]
    item["my_delta"] = None
    item["opponent_id"] = None
    item["opponent_name"] = None
    item["my_avatar_url"] = None
    item["opponent_avatar_url"] = None
    item["my_achievement"] = None
    item["opponent_achievement"] = None
    item["my_team"] = None
    item["opponent_team"] = None

    if item["is_mine"]:
        as_player1 = item.get("player1_id") == viewer_id
        my_score = item.get("score1") if as_player1 else item.get("score2")
        opponent_score = item.get("score2") if as_player1 else item.get("score1")
        item["my_delta"] = int((item.get("delta1") if as_player1 else item.get("delta2")) or 0)
        item["opponent_id"] = item.get("player2_id") if as_player1 else item.get("player1_id")
        item["opponent_name"] = item.get("player2_name") if as_player1 else item.get("player1_name")
        item["my_avatar_url"] = item.get("player1_avatar_url") if as_player1 else item.get("player2_avatar_url")
        item["opponent_avatar_url"] = item.get("player2_avatar_url") if as_player1 else item.get("player1_avatar_url")
        item["my_achievement"] = item.get("player1_achievement") if as_player1 else item.get("player2_achievement")
        item["opponent_achievement"] = item.get("player2_achievement") if as_player1 else item.get("player1_achievement")
        item["my_team"] = item.get("team1") if as_player1 else item.get("team2")
        item["opponent_team"] = item.get("team2") if as_player1 else item.get("team1")

        if item.get("status") == "confirmed" and my_score is not None and opponent_score is not None:
            if my_score > opponent_score:
                item["result_code"], item["result_label"] = "win", "THẮNG"
            elif my_score < opponent_score:
                item["result_code"], item["result_label"] = "loss", "THUA"
            else:
                item["result_code"], item["result_label"] = "draw", "HÒA"
        elif item.get("status") == "cancelled":
            item["result_code"], item["result_label"] = "cancelled", "ĐÃ HỦY"
        elif item.get("status") == "disputed":
            item["result_code"], item["result_label"] = "disputed", "TRANH CHẤP"
        else:
            item["result_code"] = "pending"

    return item


def build_player_activity_map(rooms=None, matches=None):
    rooms = list_rooms() if rooms is None else rooms
    matches = list_matches() if matches is None else matches
    activity = {}

    def set_status(user_id, code, label):
        if not user_id:
            return
        current = activity.get(user_id)
        if not current or ACTIVITY_PRIORITY.get(code, 0) > ACTIVITY_PRIORITY.get(current.get("code"), 0):
            activity[user_id] = {"code": code, "label": label}

    for room in rooms:
        if not room_is_active(room):
            continue
        if room.get("status") == "waiting_ready":
            code, label = "in_room", "Đang trong phòng"
        elif room.get("status") == "waiting_result_confirm":
            code, label = "waiting_confirm", "Chờ xác nhận"
        else:
            code, label = "playing", "Đang thi đấu"
        set_status(room.get("host_user_id"), code, label)
        set_status(room.get("guest_user_id"), code, label)

    for match in matches:
        if match.get("status") == "waiting_confirm":
            code, label = "waiting_confirm", "Chờ xác nhận"
        elif match.get("status") == "playing":
            code, label = "playing", "Đang thi đấu"
        else:
            continue
        set_status(match.get("player1_id"), code, label)
        set_status(match.get("player2_id"), code, label)

    return activity


def get_match(match_id):
    result = execute_query(
        db.table("matches").select("*").eq("id", match_id).limit(1),
        "get_match",
    )
    return result.data[0] if result.data else None


def get_match_dispute(dispute_id):
    result = execute_query(
        db.table("match_disputes").select("*").eq("id", dispute_id).limit(1),
        "get_match_dispute",
    )
    return dict(result.data[0]) if result.data else None


def get_match_dispute_by_match(match_id, statuses=None):
    query = db.table("match_disputes").select("*").eq("match_id", match_id).order("created_at", desc=True).limit(1)
    if statuses:
        status_list = list(statuses) if not isinstance(statuses, str) else [statuses]
        query = query.in_("status", status_list)
    result = execute_query(query, "get_match_dispute_by_match")
    return dict(result.data[0]) if result.data else None


def list_match_disputes(status=None):
    query = db.table("match_disputes").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    result = execute_query(query, "list_match_disputes")
    return [dict(item) for item in (result.data or [])]


def create_user_notification(user_id, title, message, link_url=None, notification_type="system"):
    if not user_id:
        return None
    try:
        result = execute_query(
            db.table("user_notifications").insert({
                "user_id": user_id,
                "notification_type": str(notification_type)[:50],
                "title": str(title)[:120],
                "message": str(message)[:500],
                "link_url": str(link_url)[:300] if link_url else None,
                "is_read": False,
            }),
            "create_user_notification",
            attempts=2,
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        print(f"create_user_notification warning: {exc}")
        return None


def create_notifications_for_users(user_ids, title, message, link_url=None, notification_type="system"):
    seen = set()
    for user_id in user_ids or []:
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        create_user_notification(user_id, title, message, link_url, notification_type)


def notify_admins(title, message, link_url="/admin#disputes"):
    try:
        admin_ids = [user.get("id") for user in list_all_users() if is_admin_user(user)]
        create_notifications_for_users(admin_ids, title, message, link_url, "dispute")
    except Exception as exc:
        print(f"notify_admins warning: {exc}")


def list_unread_notifications(user_id, limit=5):
    if not user_id:
        return []
    try:
        result = execute_query(
            db.table("user_notifications")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .order("created_at", desc=True)
            .limit(max(1, min(int(limit), 20))),
            "list_unread_notifications",
            attempts=2,
        )
        return [dict(item) for item in (result.data or [])]
    except Exception as exc:
        print(f"list_unread_notifications warning: {exc}")
        return []


def list_user_notifications(user_id, page=1, per_page=20, unread_only=False):
    """Tải lịch sử thông báo của đúng người dùng, có phân trang tại Supabase."""
    if not user_id:
        return [], False
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 20), 50))
    start = (page - 1) * per_page
    try:
        query = (
            db.table("user_notifications")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
        if unread_only:
            query = query.eq("is_read", False)
        result = execute_query(
            query.range(start, start + per_page),
            "list_user_notifications",
            attempts=2,
        )
        rows = [dict(item) for item in (result.data or [])]
        has_next = len(rows) > per_page
        return rows[:per_page], has_next
    except Exception as exc:
        print(f"list_user_notifications warning: {exc}")
        return [], False


def dispute_reason_label(reason_code):
    return DISPUTE_REASON_OPTIONS.get(reason_code, DISPUTE_REASON_OPTIONS["other"])


def create_or_update_match_dispute(
    room,
    raised_by_id,
    reason_code,
    details="",
    source="player",
    evidence_path=None,
):
    if not room or not room.get("match_id"):
        return None

    reason_code = reason_code if reason_code in DISPUTE_REASON_OPTIONS else "other"
    details = (details or "").strip()[:500]
    existing = get_match_dispute_by_match(room.get("match_id"), DISPUTE_PENDING_STATUSES)
    payload = {
        "room_id": room.get("id"),
        "raised_by_id": raised_by_id,
        "reason_code": reason_code,
        "reason_label": dispute_reason_label(reason_code),
        "details": details or None,
        "source": source,
        "submitted_score1": room.get("host_score"),
        "submitted_score2": room.get("guest_score"),
        "status": "pending",
        "updated_at": now_iso(),
    }
    if evidence_path:
        payload.update({
            "evidence_path": evidence_path,
            "evidence_uploaded_at": now_iso(),
        })

    if existing:
        result = execute_query(
            db.table("match_disputes").update(payload).eq("id", existing.get("id")),
            "update_match_dispute",
        )
    else:
        payload["match_id"] = room.get("match_id")
        result = execute_query(
            db.table("match_disputes").insert(payload),
            "create_match_dispute",
        )
    return dict(result.data[0]) if result.data else existing


def decorate_match_dispute(dispute, all_matches=None):
    item = dict(dispute or {})
    match = None
    if item.get("match_id") and all_matches is not None:
        match = next((m for m in all_matches if str(m.get("id")) == str(item.get("match_id"))), None)
    if item.get("match_id") and match is None:
        match = get_match(item.get("match_id"))
    users = users_map()
    player1 = users.get((match or {}).get("player1_id"), {})
    player2 = users.get((match or {}).get("player2_id"), {})
    raised_by = users.get(item.get("raised_by_id"), {})
    resolved_by = users.get(item.get("resolved_by_id"), {})

    item["match"] = match or {}
    item["player1_name"] = player1.get("display_name", "Unknown")
    item["player2_name"] = player2.get("display_name", "Unknown")
    item["player1_username"] = player1.get("username", "-")
    item["player2_username"] = player2.get("username", "-")
    item["player1_points"] = int(player1.get("rank_points", 0) or 0)
    item["player2_points"] = int(player2.get("rank_points", 0) or 0)
    item["raised_by_name"] = raised_by.get("display_name") or ("Hệ thống" if item.get("source") == "timeout" else "Không xác định")
    item["resolved_by_name"] = resolved_by.get("display_name", "")
    item["reason_label"] = item.get("reason_label") or dispute_reason_label(item.get("reason_code"))
    item["evidence_url"] = get_dispute_evidence_signed_url(item.get("evidence_path"))
    if item.get("submitted_score1") is None:
        item["submitted_score1"] = (match or {}).get("score1")
    if item.get("submitted_score2") is None:
        item["submitted_score2"] = (match or {}).get("score2")

    candidates = all_matches if all_matches is not None else list_matches()
    pair = {(match or {}).get("player1_id"), (match or {}).get("player2_id")}
    item["head_to_head"] = [
        other for other in candidates
        if other.get("status") == "confirmed"
        and str(other.get("id")) != str(item.get("match_id"))
        and {other.get("player1_id"), other.get("player2_id")} == pair
    ][:5]
    return item



def invite_expiry_dt(invite):
    explicit = aware_utc(parse_dt(invite.get("expires_at")))
    if explicit:
        return explicit
    created = aware_utc(parse_dt(invite.get("created_at")))
    return created + timedelta(seconds=INVITE_TIMEOUT_SECONDS) if created else None


def expire_invite_if_needed(invite):
    if not invite or invite.get("status") != "pending":
        return invite

    expires_at = invite_expiry_dt(invite)
    invite["expires_at"] = expires_at.isoformat() if expires_at else None
    invite["expires_in_seconds"] = max(0, int((expires_at - now_dt()).total_seconds())) if expires_at else 0

    if expires_at and expires_at <= now_dt():
        try:
            execute_query(
                db.table("match_invites").update({
                    "status": "expired",
                    "updated_at": now_iso(),
                }).eq("id", invite.get("id")).eq("status", "pending"),
                "expire_match_invite",
            )
            invite["status"] = "expired"
            invite["expires_in_seconds"] = 0
        except Exception as exc:
            print(f"expire_invite_if_needed warning: {exc}")
    return invite


def get_invite(invite_id):
    result = execute_query(
        db.table("match_invites").select("*").eq("id", invite_id).limit(1),
        "get_invite",
    )
    invite = dict(result.data[0]) if result.data else None
    return expire_invite_if_needed(invite) if invite else None


def list_invites(status=None):
    cached = cache_get("_rz_invites_all")
    if cached is None:
        shared = ttl_cache_get("invites_raw")
        if shared is None:
            query = db.table("match_invites").select("*").order("created_at", desc=True)
            result = execute_query(query, "list_invites")
            shared = result.data or []
            ttl_cache_set("invites_raw", shared, 3)
        cached = [dict(row) for row in shared]
        cache_set("_rz_invites_all", cached)

    processed = []
    for raw in cached:
        invite = expire_invite_if_needed(dict(raw))
        if status and invite.get("status") != status:
            continue
        processed.append(invite)

    users = users_map()
    for invite in processed:
        from_user = users.get(invite.get("from_user_id"), {})
        to_user = users.get(invite.get("to_user_id"), {})
        invite["from_name"] = from_user.get("display_name", "Unknown")
        invite["from_avatar_url"] = from_user.get("avatar_url")
        invite["from_achievement"] = from_user.get("featured_achievement")
        invite["from_points"] = from_user.get("rank_points", 0)
        invite["from_rank"] = get_rank_display(from_user.get("rank_points", 0))
        invite["to_name"] = to_user.get("display_name", "Unknown")
        invite["to_avatar_url"] = to_user.get("avatar_url")
        invite["to_achievement"] = to_user.get("featured_achievement")
        invite["to_points"] = to_user.get("rank_points", 0)
        invite["to_rank"] = get_rank_display(to_user.get("rank_points", 0))

    return processed


def room_state_expiry_dt(room):
    """Short state-specific deadline such as ready/result/rematch timeout."""
    explicit = aware_utc(parse_dt(room.get("state_expires_at")))
    if explicit:
        return explicit

    updated = aware_utc(parse_dt(room.get("updated_at"))) or aware_utc(parse_dt(room.get("created_at")))
    if not updated:
        return None

    status = room.get("status")
    note = room.get("note") or ""
    if status == "waiting_ready":
        # Phòng chưa bắt đầu được xử lý bằng bộ đếm không hoạt động 30 phút.
        return None
    if status == "waiting_result_confirm":
        return updated + timedelta(seconds=RESULT_CONFIRM_TIMEOUT_SECONDS)
    if status == "confirmed" and note in {REMATCH_HOST_READY_NOTE, REMATCH_GUEST_READY_NOTE}:
        return updated + timedelta(seconds=REMATCH_TIMEOUT_SECONDS)
    return None


def room_inactivity_expiry_dt(room):
    """Đóng phòng chờ sau 30 phút, phòng đã bắt đầu sau 60 phút không hoạt động."""
    active_statuses = {"waiting_ready", "playing", "friendly_playing", "waiting_result_confirm"}
    status = room.get("status")
    note = room.get("note") or ""
    if status == "confirmed" and note in {REMATCH_HOST_READY_NOTE, REMATCH_GUEST_READY_NOTE}:
        active = True
    else:
        active = status in active_statuses
    if not active:
        return None

    last_activity = aware_utc(parse_dt(room.get("updated_at"))) or aware_utc(parse_dt(room.get("created_at")))
    if not last_activity:
        return None
    timeout_seconds = (
        ROOM_EMPTY_INACTIVITY_TIMEOUT_SECONDS
        if status == "waiting_ready"
        else ROOM_MATCH_INACTIVITY_TIMEOUT_SECONDS
    )
    return last_activity + timedelta(seconds=timeout_seconds)


def room_expiry_dt(room):
    state_expiry = room_state_expiry_dt(room)
    inactivity_expiry = room_inactivity_expiry_dt(room)
    candidates = [dt for dt in (state_expiry, inactivity_expiry) if dt]
    return min(candidates) if candidates else None


def apply_room_abandon_penalty(user_id, amount=ROOM_ABANDON_PENALTY):
    """Trừ RP và tính một trận thua do bỏ trận, không cộng thắng cho đối thủ."""
    if not user_id:
        return None
    player = get_user(user_id)
    if not player:
        return None
    penalty = max(0, int(amount or 0))
    old_points = int(player.get("rank_points", 0) or 0)
    new_points = max(0, old_points - penalty)
    execute_query(
        db.table("users").update({
            "rank_points": new_points,
            "total_matches": int(player.get("total_matches", 0) or 0) + 1,
            "losses": int(player.get("losses", 0) or 0) + 1,
            "streak": 0,
        }).eq("id", user_id),
        "apply_room_abandon_penalty",
    )
    return -(old_points - new_points)


def close_room_with_timeout_penalty(room, offender_role, reason):
    """Đóng phòng và phạt ngẫu nhiên 22–25 RP đúng một lần."""
    room_id = room.get("id")
    original_status = room.get("status")
    offender_id = room.get("host_user_id") if offender_role == "host" else room.get("guest_user_id")
    update_data = {
        "status": "cancelled",
        "note": reason,
        "state_expires_at": None,
        "updated_at": now_iso(),
    }
    result = execute_query(
        db.table("match_rooms").update(update_data).eq("id", room_id).eq("status", original_status),
        "close_room_timeout_penalty",
    )
    # Nếu request khác đã đóng phòng trước, không trừ điểm lần thứ hai.
    if not (result.data or []):
        return False

    room.update(update_data)
    penalty_amount = random.SystemRandom().randint(*ROOM_TIMEOUT_PENALTY_RANGE)
    penalty_delta = apply_room_abandon_penalty(offender_id, penalty_amount)
    match_id = room.get("match_id")
    if match_id:
        match_update = {
            "status": "cancelled",
            "note": reason,
            "updated_at": now_iso(),
        }
        if offender_role == "host":
            match_update.update({"delta1": penalty_delta if penalty_delta is not None else -penalty_amount, "delta2": 0})
        else:
            match_update.update({"delta1": 0, "delta2": penalty_delta if penalty_delta is not None else -penalty_amount})
        execute_query(
            db.table("matches").update(match_update).eq("id", match_id),
            "mark_timeout_match_cancelled",
        )

    offender_name = room.get("host_name") if offender_role == "host" else room.get("guest_name")
    other_id = room.get("guest_user_id") if offender_role == "host" else room.get("host_user_id")
    create_user_notification(
        offender_id,
        "⏱️ Trận bị tính là bỏ trận",
        f"Bạn bị trừ {abs(int(penalty_delta or -penalty_amount))} RP vì {reason.lower()}",
        "/matches",
        "room_timeout_penalty",
    )
    create_user_notification(
        other_id,
        "⏱️ Phòng đấu đã tự đóng",
        f"{offender_name or 'Đối thủ'} bị tính là bỏ trận. Bạn không bị cộng hoặc trừ RP.",
        "/matches",
        "room_timeout",
    )
    return True


def expire_room_if_needed(room):
    if not room:
        return room

    expires_at = room_expiry_dt(room)
    room["state_expires_at"] = expires_at.isoformat() if expires_at else None
    room["timeout_seconds"] = max(0, int((expires_at - now_dt()).total_seconds())) if expires_at else 0
    if not expires_at or expires_at > now_dt():
        return room

    status = room.get("status")
    note = room.get("note") or ""
    mode = room.get("match_mode") or MATCH_MODE_RANKED
    state_expiry = room_state_expiry_dt(room)
    inactivity_expiry = room_inactivity_expiry_dt(room)
    inactivity_expired = bool(
        inactivity_expiry
        and inactivity_expiry <= now_dt()
        and (not state_expiry or inactivity_expiry <= state_expiry)
    )

    try:
        # Trận Xếp hạng đã quay đội nhưng chủ không nhập kết quả trong 60 phút.
        if status == "playing" and mode == MATCH_MODE_RANKED and inactivity_expired:
            close_room_with_timeout_penalty(
                room,
                "host",
                "Chủ phòng không nhập kết quả sau 60 phút và bị tính là thoát trận.",
            )
            room["timeout_seconds"] = 0
            return room

        # Chủ đã nhập tỷ số nhưng khách không xác nhận/tranh chấp trong 60 phút.
        if status == "waiting_result_confirm" and mode == MATCH_MODE_RANKED:
            close_room_with_timeout_penalty(
                room,
                "guest",
                "Khách không xác nhận kết quả sau 60 phút và bị tính là thoát trận.",
            )
            room["timeout_seconds"] = 0
            return room

        # Giao hữu hoặc phòng chưa bắt đầu: chỉ đóng, không trừ điểm.
        if inactivity_expired or status == "waiting_ready":
            update_data = {
                "status": "cancelled",
                "note": (
                    "Phòng tự đóng sau 30 phút không hoạt động."
                    if status == "waiting_ready"
                    else "Phòng tự đóng sau 60 phút không hoạt động."
                ),
                "state_expires_at": None,
                "updated_at": now_iso(),
            }
            result = execute_query(
                db.table("match_rooms").update(update_data).eq("id", room.get("id")).eq("status", status),
                "expire_room_inactivity",
            )
            if result.data or []:
                room.update(update_data)
                if room.get("match_id"):
                    execute_query(
                        db.table("matches").update({
                            "status": "cancelled",
                            "note": (
                                "Phòng tự đóng sau 30 phút không hoạt động; không áp dụng phạt RP."
                                if status == "waiting_ready"
                                else "Phòng tự đóng sau 60 phút không hoạt động; không áp dụng phạt RP."
                            ),
                            "updated_at": now_iso(),
                        }).eq("id", room.get("match_id")),
                        "cancel_inactive_room_match",
                    )
            room["timeout_seconds"] = 0
            return room

        if status == "confirmed" and note in {REMATCH_HOST_READY_NOTE, REMATCH_GUEST_READY_NOTE}:
            update_data = {
                "note": REMATCH_EXPIRED_NOTE,
                "state_expires_at": None,
                "updated_at": now_iso(),
            }
            execute_query(
                db.table("match_rooms").update(update_data).eq("id", room.get("id")),
                "expire_rematch_request",
            )
            room.update(update_data)
            room["timeout_seconds"] = 0
    except Exception as exc:
        print(f"expire_room_if_needed warning: {exc}")

    return room


def get_room(room_id):
    result = execute_query(
        db.table("match_rooms").select("*").eq("id", room_id).limit(1),
        "get_room",
    )
    room = dict(result.data[0]) if result.data else None
    if room:
        expire_room_if_needed(room)
        enrich_room(room)
    return room


def enrich_room(room):
    users = users_map()
    host = users.get(room.get("host_user_id"), {})
    guest = users.get(room.get("guest_user_id"), {})

    raw_room_id = str(room.get("id") or "")
    compact_room_id = "".join(ch for ch in raw_room_id.upper() if ch.isalnum())
    room["room_code"] = (compact_room_id[:6] or "ROOM00")

    room["host_name"] = host.get("display_name", "Unknown")
    room["host_avatar_url"] = host.get("avatar_url")
    room["host_achievement"] = host.get("featured_achievement")
    room["host_points"] = host.get("rank_points", 0)
    room["host_rank_info"] = get_rank_info(host.get("rank_points", 0))
    room["host_rank"] = get_rank_display(host.get("rank_points", 0))
    room["host_streak"] = int(host.get("streak", 0) or 0)
    room["host_streak_badge"] = get_win_streak_badge(room["host_streak"])
    room["has_guest"] = bool(room.get("guest_user_id"))
    room["guest_name"] = guest.get("display_name", "Đang chờ đối thủ") if room["has_guest"] else "Đang chờ đối thủ"
    room["guest_avatar_url"] = guest.get("avatar_url") if room["has_guest"] else None
    room["guest_achievement"] = guest.get("featured_achievement") if room["has_guest"] else None
    room["guest_points"] = guest.get("rank_points", 0) if room["has_guest"] else 0
    room["guest_rank_info"] = get_rank_info(guest.get("rank_points", 0)) if room["has_guest"] else None
    room["guest_rank"] = get_rank_display(guest.get("rank_points", 0)) if room["has_guest"] else "Chưa có người chơi"
    room["guest_streak"] = int(guest.get("streak", 0) or 0) if room["has_guest"] else 0
    room["guest_streak_badge"] = get_win_streak_badge(room["guest_streak"]) if room["has_guest"] else None
    room["streak_event"] = parse_win_streak_room_note(room.get("note"))
    if room.get("host_team"):
        info = get_db_team_info(room.get("host_team")) or {}
        room["host_team_overall"] = room.get("host_team_overall") or info.get("overall") or get_team_overall(room.get("host_team"))
        room["host_team_logo_url"] = room.get("host_team_logo_url") or info.get("logo_url")
        room["host_team_league"] = room.get("host_team_league") or info.get("league") or ""
        room["host_team_league_logo_url"] = get_league_logo_url(room["host_team_league"])
        room["host_team_tier"] = info.get("tier") or get_team_tier(room.get("host_team"))
        room["host_team_total_stats"] = int(info.get("total_stats") or 0)
    else:
        room["host_team_total_stats"] = 0
    if room.get("guest_team"):
        info = get_db_team_info(room.get("guest_team")) or {}
        room["guest_team_overall"] = room.get("guest_team_overall") or info.get("overall") or get_team_overall(room.get("guest_team"))
        room["guest_team_logo_url"] = room.get("guest_team_logo_url") or info.get("logo_url")
        room["guest_team_league"] = room.get("guest_team_league") or info.get("league") or ""
        room["guest_team_league_logo_url"] = get_league_logo_url(room["guest_team_league"])
        room["guest_team_tier"] = info.get("tier") or get_team_tier(room.get("guest_team"))
        room["guest_team_total_stats"] = int(info.get("total_stats") or 0)
    else:
        room["guest_team_total_stats"] = 0
    room["smart_random_rule"] = get_smart_random_rule(host, guest)
    room["rematch_host_ready"] = room.get("note") == REMATCH_HOST_READY_NOTE
    room["rematch_guest_ready"] = room.get("note") == REMATCH_GUEST_READY_NOTE
    room["rematch_host_declined"] = room.get("note") == REMATCH_HOST_DECLINED_NOTE
    room["rematch_guest_declined"] = room.get("note") == REMATCH_GUEST_DECLINED_NOTE
    room["rematch_declined"] = room["rematch_host_declined"] or room["rematch_guest_declined"]
    room["match_mode"] = room.get("match_mode") or MATCH_MODE_RANKED
    room["friendly_tier"] = room.get("friendly_tier") or "A"
    room["host_team_league"] = room.get("host_team_league") or ""
    room["guest_team_league"] = room.get("guest_team_league") or ""
    room["host_team_league_logo_url"] = room.get("host_team_league_logo_url") or get_league_logo_url(room["host_team_league"])
    room["guest_team_league_logo_url"] = room.get("guest_team_league_logo_url") or get_league_logo_url(room["guest_team_league"])
    room["rematch_expired"] = room.get("note") == REMATCH_EXPIRED_NOTE
    room["dispute"] = None
    if room.get("status") == "disputed" and room.get("match_id"):
        try:
            dispute = get_match_dispute_by_match(room.get("match_id"), DISPUTE_PENDING_STATUSES)
            if dispute:
                room["dispute"] = decorate_match_dispute(dispute)
        except Exception as exc:
            print(f"enrich_room dispute warning: {exc}")
    room["timeout_seconds"] = seconds_until(room.get("state_expires_at"))
    state_expiry = room_state_expiry_dt(room)
    inactivity_expiry = room_inactivity_expiry_dt(room)
    inactivity_is_next = bool(
        inactivity_expiry
        and (not state_expiry or inactivity_expiry <= state_expiry)
    )
    if inactivity_is_next and room.get("timeout_seconds", 0) > 0:
        room["timeout_label"] = "Phòng sẽ tự đóng nếu không có hoạt động trong"
    elif room.get("status") == "waiting_ready" and room.get("guest_user_id") and not room.get("guest_ready"):
        room["timeout_label"] = "Phòng sẽ tự đóng nếu không có hoạt động trong"
    elif room.get("status") == "waiting_result_confirm":
        room["timeout_label"] = "Khách cần xác nhận hoặc tranh chấp trong"
    elif room.get("status") == "confirmed" and (room.get("rematch_host_ready") or room.get("rematch_guest_ready")):
        room["timeout_label"] = "Yêu cầu đá tiếp sẽ hết hạn trong"
    else:
        room["timeout_label"] = ""

    room["match_mode_label"] = "Xếp hạng (Rank)" if room.get("match_mode") != MATCH_MODE_FRIENDLY else f"Giao hữu Tier {room.get('friendly_tier') or ''}".strip()
    room["battle_label"] = "Trận đấu xếp hạng" if room.get("match_mode") != MATCH_MODE_FRIENDLY else "Trận đấu giao hữu"
    room["start_countdown_seconds"] = 0
    room["match_elapsed_seconds"] = 0
    if room.get("guest_user_id"):
        time_source = room.get("updated_at") or room.get("created_at")
        event_dt = parse_dt(time_source) if time_source else None
        if event_dt:
            elapsed = max(0, int((now_dt() - event_dt).total_seconds()))
            if room.get("status") == "waiting_ready":
                room["start_countdown_seconds"] = max(0, 300 - elapsed)
            elif room.get("status") in {"playing", "friendly_playing", "waiting_result_confirm"}:
                room["match_elapsed_seconds"] = elapsed
    room["guest_ready_label"] = "Đã sẵn sàng" if room.get("guest_ready") else "Chưa sẵn sàng"
    return room


def list_rooms(status=None):
    cached = cache_get("_rz_rooms_all")
    if cached is None:
        shared = ttl_cache_get("rooms_raw")
        if shared is None:
            query = db.table("match_rooms").select("*").order("created_at", desc=True)
            result = execute_query(query, "list_rooms")
            shared = result.data or []
            ttl_cache_set("rooms_raw", shared, 3)
        cached = [dict(row) for row in shared]
        cache_set("_rz_rooms_all", cached)

    rooms = []
    for raw in cached:
        room = expire_room_if_needed(dict(raw))
        if status and room.get("status") != status:
            continue
        enrich_room(room)
        rooms.append(room)
    return rooms



GLOBAL_STREAK_EVENT_SETTING_KEY = "global_win_streak_event"
GLOBAL_STREAK_EVENT_TTL_SECONDS = 24 * 60 * 60
GLOBAL_STREAK_EVENT_MAX_ITEMS = 30


def _normalize_global_streak_events(raw):
    """Chuẩn hóa dữ liệu cũ (1 dict) và dữ liệu mới (danh sách sự kiện)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []

    now = now_dt()
    active = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        event_id = str(item.get("id") or "").strip()
        if not event_id or event_id in seen:
            continue
        expires_at = aware_utc(parse_dt(item.get("expires_at")))
        if not expires_at or expires_at <= now:
            continue
        seen.add(event_id)
        active.append(dict(item))

    # SHUTDOWN ưu tiên trước; trong cùng loại, sự kiện mới hơn đứng trước.
    active.sort(
        key=lambda item: (
            0 if str(item.get("kind")) == "shutdown" else 1,
            str(item.get("published_at") or ""),
        )
    )
    shutdowns = [item for item in active if str(item.get("kind")) == "shutdown"]
    milestones = [item for item in active if str(item.get("kind")) != "shutdown"]
    shutdowns.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    milestones.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    return (shutdowns + milestones)[:GLOBAL_STREAK_EVENT_MAX_ITEMS]


def publish_global_streak_event(event):
    if not isinstance(event, dict) or event.get("kind") not in {"milestone", "shutdown"}:
        return False
    payload = dict(event)
    payload["published_at"] = now_iso()
    payload["expires_at"] = future_iso(GLOBAL_STREAK_EVENT_TTL_SECONDS)
    payload["source"] = "win_streak"
    try:
        result = execute_query(
            db.table("system_settings").select("setting_value")
            .eq("setting_key", GLOBAL_STREAK_EVENT_SETTING_KEY).limit(1),
            "read_global_streak_events", attempts=2,
        )
        raw = ((result.data or [{}])[0]).get("setting_value")
        events = _normalize_global_streak_events(raw)
        events = [item for item in events if str(item.get("id")) != str(payload.get("id"))]
        events.append(payload)
        events = _normalize_global_streak_events(events)
        execute_query(
            db.table("system_settings").upsert({
                "setting_key": GLOBAL_STREAK_EVENT_SETTING_KEY,
                "setting_value": json.dumps(events, ensure_ascii=False),
                "updated_at": now_iso(),
            }, on_conflict="setting_key"),
            "publish_global_streak_event", attempts=2,
        )
        ttl_cache_delete("global_win_streak_events")
        ttl_cache_delete("global_win_streak_event")
        return True
    except Exception as exc:
        print(f"publish_global_streak_event warning: {exc}")
        return False


def get_active_global_streak_events():
    cached = ttl_cache_get("global_win_streak_events")
    if cached is not None:
        return [] if cached is False else cached
    try:
        result = execute_query(
            db.table("system_settings").select("setting_value")
            .eq("setting_key", GLOBAL_STREAK_EVENT_SETTING_KEY).limit(1),
            "get_active_global_streak_events", attempts=2,
        )
        raw = ((result.data or [{}])[0]).get("setting_value")
        events = _normalize_global_streak_events(raw)
        ttl_cache_set("global_win_streak_events", events if events else False, 15)
        return events
    except Exception as exc:
        print(f"get_active_global_streak_events warning: {exc}")
        return []


def get_active_global_streak_event():
    """Tương thích với code cũ: trả sự kiện ưu tiên đầu tiên."""
    events = get_active_global_streak_events()
    return events[0] if events else None


def get_active_announcement():
    try:
        cached = cache_get("_rz_active_announcement")
        if cached is not None:
            return cached

        shared = ttl_cache_get("active_announcement")
        if shared is not None:
            return cache_set("_rz_active_announcement", None if shared is False else shared)
        result = execute_query(
            db.table("admin_announcements")
            .select("*")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(1),
            "get_active_announcement",
        )
        announcement = result.data[0] if result.data else None
        ttl_cache_set("active_announcement", announcement if announcement is not None else False, 15)
        return cache_set("_rz_active_announcement", announcement)
    except Exception:
        return None


def enrich_chat_message(message, users=None):
    if users is None:
        users = users_map()
    user = users.get(message.get("user_id"), {})
    message["user_name"] = user.get("display_name", "Unknown")
    message["user_avatar_url"] = user.get("avatar_url")
    message["user_achievement"] = user.get("featured_achievement")
    message["user_role"] = "admin" if is_admin_user(user) else user.get("role", "player")
    # Giữ timestamp gốc cho logic chưa đọc, đồng thời gửi chuỗi giờ Việt Nam dễ đọc.
    message["created_at_display"] = format_vn_datetime(message.get("created_at"))
    return message


def list_chat_messages(scope="global", room_id=None, limit=20):
    query = db.table("chat_messages").select("*").eq("scope", scope)

    if room_id:
        query = query.eq("room_id", room_id)
    else:
        query = query.is_("room_id", "null")

    result = execute_query(query.order("created_at", desc=True).limit(limit), "list_chat_messages")
    messages = list(reversed(result.data or []))
    users = users_map()
    return [enrich_chat_message(message, users) for message in messages]



def user_can_chat(user_id, scope="global", room_id=None):
    query = db.table("chat_messages").select("*").eq("user_id", user_id).eq("scope", scope)

    if room_id:
        query = query.eq("room_id", room_id)
    else:
        query = query.is_("room_id", "null")

    result = execute_query(query.order("created_at", desc=True).limit(1), "user_can_chat")
    if not result.data:
        return True, ""

    last_time = parse_dt(result.data[0].get("created_at"))
    if not last_time:
        return True, ""

    diff = (now_dt() - last_time).total_seconds()
    if diff < CHAT_COOLDOWN_SECONDS:
        wait = max(1, int(CHAT_COOLDOWN_SECONDS - diff))
        return False, f"Bạn gửi quá nhanh. Chờ {wait} giây."

    return True, ""


def touch_room_activity(room_id):
    """Reset the 60-minute inactivity timer after a meaningful room action."""
    if not room_id:
        return
    try:
        execute_query(
            db.table("match_rooms").update({"updated_at": now_iso()}).eq("id", room_id),
            "touch_room_activity",
            attempts=1,
        )
        cache_delete("_rz_rooms_all")
    except Exception as exc:
        print(f"touch_room_activity warning: {exc}")


def create_chat_message(user_id, message, scope="global", room_id=None):
    message = (message or "").strip()

    if not message:
        return False, "Tin nhắn không được để trống."

    if len(message) > CHAT_MAX_LENGTH:
        return False, f"Tin nhắn tối đa {CHAT_MAX_LENGTH} ký tự."

    ok, error = user_can_chat(user_id, scope, room_id)
    if not ok:
        return False, error

    db.table("chat_messages").insert({
        "user_id": user_id,
        "room_id": room_id,
        "scope": scope,
        "message": message,
    }).execute()

    if scope == "room" and room_id:
        touch_room_activity(room_id)

    return True, ""



def current_user():
    cached = cache_get("_rz_current_user")
    if cached is not None:
        return cached

    user_id = session.get("user_id")
    if not user_id:
        return None

    try:
        shared_user = ttl_cache_get(f"user:{user_id}")
        user = dict(shared_user) if shared_user is not None else get_user(user_id)
        if user:
            decorate_player_achievements(user)
            ttl_cache_set(f"user:{user_id}", dict(user), 8)
            session["username"] = user.get("username", "")
            session["display_name"] = user.get("display_name", "")
            session["avatar_url"] = user.get("avatar_url")
            session["role"] = user.get("role", "player")
            session["account_status"] = user.get("account_status", "approved")
            session["admin_level"] = user.get("admin_level", "none")
            return cache_set("_rz_current_user", user)
    except Exception as exc:
        print(f"current_user warning: {exc}")

    # Fallback để tránh trắng trang khi Supabase ngắt kết nối vài giây.
    fallback_user = {
        "id": user_id,
        "username": session.get("username", "player"),
        "display_name": session.get("display_name", "Player"),
        "avatar_url": session.get("avatar_url"),
        "role": session.get("role", "player"),
        "account_status": session.get("account_status", "approved"),
        "admin_level": session.get("admin_level", "none"),
        "rank_points": 0,
        "is_online": True,
        "matchmaking_cooldown_until": None,
    }
    return cache_set("_rz_current_user", fallback_user)


def is_player_in_cooldown(user):
    cooldown = parse_dt(user.get("matchmaking_cooldown_until"))
    return bool(cooldown and cooldown > now_dt())


def cooldown_text(user):
    cooldown = parse_dt(user.get("matchmaking_cooldown_until"))
    if not cooldown or cooldown <= now_dt():
        return ""
    seconds = int((cooldown - now_dt()).total_seconds())
    minutes = max(1, seconds // 60 + (1 if seconds % 60 else 0))
    return f"{minutes} phút"



def current_pending_invites():
    cached = cache_get("_rz_current_pending_invites")
    if cached is not None:
        return cached
    try:
        user = current_user()
        if not user or user.get("role") == "admin":
            return cache_set("_rz_current_pending_invites", [])
        invites = list_invites("pending")
        return cache_set("_rz_current_pending_invites", [invite for invite in invites if invite["to_user_id"] == user["id"]])
    except Exception as exc:
        print(f"current_pending_invites warning: {exc}")
        return []


def current_pending_invite_count():
    try:
        return len(current_pending_invites())
    except Exception:
        return 0


def room_is_active(room):
    if room.get("status") in {"waiting_ready", "playing", "friendly_playing", "waiting_result_confirm"}:
        return True
    return (
        room.get("status") == "confirmed"
        and (room.get("note") or "") in {REMATCH_HOST_READY_NOTE, REMATCH_GUEST_READY_NOTE}
    )


def active_room_for_user(user_id, exclude_room_id=None):
    rooms = list_rooms()
    for room in rooms:
        if exclude_room_id and str(room.get("id")) == str(exclude_room_id):
            continue
        if room_is_active(room) and user_id in [room.get("host_user_id"), room.get("guest_user_id")]:
            return room
    return None


def build_room_head_to_head(room):
    """Thống kê đối đầu của hai người chơi kể từ lúc phòng hiện tại được tạo."""
    host_id = room.get("host_user_id")
    guest_id = room.get("guest_user_id")
    room_opened_at = parse_dt(room.get("created_at"))

    empty = {
        "available": bool(host_id and guest_id),
        "total": 0,
        "host_wins": 0,
        "guest_wins": 0,
        "draws": 0,
        "host_goals": 0,
        "guest_goals": 0,
        "matches": [],
        "since": format_vn_datetime(room.get("created_at")),
    }
    if not host_id or not guest_id:
        return empty

    pair = {str(host_id), str(guest_id)}
    selected = []
    for match in list_matches("confirmed"):
        if {str(match.get("player1_id")), str(match.get("player2_id"))} != pair:
            continue
        match_time = parse_dt(match.get("created_at"))
        if room_opened_at and match_time and match_time < room_opened_at:
            continue

        item = decorate_match_for_view(match)
        score1 = int(match.get("score1") or 0)
        score2 = int(match.get("score2") or 0)
        host_is_player1 = str(match.get("player1_id")) == str(host_id)
        host_score = score1 if host_is_player1 else score2
        guest_score = score2 if host_is_player1 else score1
        item["host_score"] = host_score
        item["guest_score"] = guest_score
        item["host_delta"] = int((match.get("delta1") if host_is_player1 else match.get("delta2")) or 0)
        item["guest_delta"] = int((match.get("delta2") if host_is_player1 else match.get("delta1")) or 0)
        selected.append(item)

        empty["host_goals"] += host_score
        empty["guest_goals"] += guest_score
        if host_score > guest_score:
            empty["host_wins"] += 1
        elif guest_score > host_score:
            empty["guest_wins"] += 1
        else:
            empty["draws"] += 1

    empty["total"] = len(selected)
    empty["matches"] = selected
    return empty


def active_match_for_user(user_id):
    active_statuses = {"playing", "waiting_confirm"}
    for match in list_matches():
        if match.get("status") in active_statuses and user_id in [match.get("player1_id"), match.get("player2_id")]:
            return match
    return None


def busy_user_ids(rooms=None, matches=None):
    """Trả về tập user đang có phòng hoặc trận chưa hoàn tất."""
    rooms = list_rooms() if rooms is None else rooms
    matches = list_matches() if matches is None else matches
    busy = set()

    for room in rooms:
        if room_is_active(room):
            busy.add(room.get("host_user_id"))
            busy.add(room.get("guest_user_id"))

    for match in matches:
        if match.get("status") in {"playing", "waiting_confirm"}:
            busy.add(match.get("player1_id"))
            busy.add(match.get("player2_id"))

    busy.discard(None)
    return busy


def has_active_room_between(user_a, user_b):
    active_statuses = {"waiting_ready", "playing", "waiting_result_confirm"}
    for room in list_rooms():
        same_pair = {room.get("host_user_id"), room.get("guest_user_id")} == {user_a, user_b}
        if same_pair and room.get("status") in active_statuses:
            return True
    return False


def has_active_match_between(user_a, user_b):
    active_statuses = {"playing", "waiting_confirm"}
    for match in list_matches():
        same_pair = {match.get("player1_id"), match.get("player2_id")} == {user_a, user_b}
        if same_pair and match.get("status") in active_statuses:
            return True
    return False


def has_pending_invite_between(user_a, user_b):
    for invite in list_invites("pending"):
        same_pair = {invite.get("from_user_id"), invite.get("to_user_id")} == {user_a, user_b}
        if same_pair:
            return True
    return False


def matchmaking_snapshot(user_a, user_b=None):
    """Fetch only the small raw state needed by invite actions.

    This avoids loading/enriching every room, match, achievement and team merely
    to decide whether two users are available.
    """
    ids = {str(user_a)}
    if user_b:
        ids.add(str(user_b))
    rooms_result = execute_query(
        db.table("match_rooms")
        .select("id,host_user_id,guest_user_id,status,invite_id")
        .in_("status", ["waiting_ready", "playing", "friendly_playing", "waiting_result_confirm"]),
        "matchmaking_active_rooms",
        attempts=3,
    )
    matches_result = execute_query(
        db.table("matches")
        .select("id,player1_id,player2_id,status")
        .in_("status", ["playing", "waiting_confirm", "processing_result"]),
        "matchmaking_active_matches",
        attempts=3,
    )
    invites_result = execute_query(
        db.table("match_invites")
        .select("id,from_user_id,to_user_id,status")
        .eq("status", "pending"),
        "matchmaking_pending_invites",
        attempts=3,
    )
    rooms = [dict(x) for x in (rooms_result.data or [])]
    matches = [dict(x) for x in (matches_result.data or [])]
    invites = [dict(x) for x in (invites_result.data or [])]

    def room_for(uid):
        uid = str(uid)
        return next((r for r in rooms if uid in {str(r.get("host_user_id")), str(r.get("guest_user_id"))}), None)

    def match_for(uid):
        uid = str(uid)
        return next((m for m in matches if uid in {str(m.get("player1_id")), str(m.get("player2_id"))}), None)

    pair_pending = False
    if user_b:
        target = {str(user_a), str(user_b)}
        pair_pending = any({str(i.get("from_user_id")), str(i.get("to_user_id"))} == target for i in invites)
    return {
        "rooms": rooms,
        "matches": matches,
        "invites": invites,
        "room_a": room_for(user_a),
        "room_b": room_for(user_b) if user_b else None,
        "match_a": match_for(user_a),
        "match_b": match_for(user_b) if user_b else None,
        "pair_pending": pair_pending,
    }


def mark_current_user_active():
    user_id = session.get("user_id")
    if not user_id:
        return

    try:
        db.table("users").update({
            "is_online": True,
            "last_seen_at": now_iso(),
        }).eq("id", user_id).execute()
    except Exception as exc:
        print(f"Heartbeat warning: {exc}")


def ensure_admin():
    global _admin_checked
    if _admin_checked or db is None:
        return

    admin = get_user_by_username("admin")
    if not admin:
        # Không tự tạo/reset mật khẩu owner trong runtime. Tài khoản sở hữu phải
        # được tạo bằng migration hoặc thao tác thủ công an toàn trong Supabase.
        app.logger.warning("Owner account 'admin' is missing; ensure_admin skipped creation for safety.")
    else:
        # Chỉ chuẩn hóa vai trò; tuyệt đối không ghi đè password_hash.
        execute_query(
            db.table("users").update({
                "display_name": "Admin",
                "role": "admin",
                "admin_level": "owner",
                "account_status": "approved",
            }).eq("username", "admin"),
            "ensure_admin_update_role_only",
        )

    _admin_checked = True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Bạn cần đăng nhập trước.", "warning")
            return redirect(url_for("login"))

        user = current_user()
        if not user:
            session.clear()
            flash("Phiên đăng nhập không hợp lệ.", "warning")
            return redirect(url_for("login"))

        status = user.get("account_status", "approved")
        if status != "approved":
            session.clear()
            messages = {
                "pending": "Tài khoản đang chờ Admin duyệt.",
                "rejected": "Tài khoản đã bị từ chối.",
                "banned": "Tài khoản đã bị khóa.",
            }
            flash(messages.get(status, "Tài khoản chưa được phép sử dụng."), "danger")
            return redirect(url_for("login"))

        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        user = None
        if user_id:
            try:
                user = get_user(user_id)
                if user:
                    decorate_player_achievements(user)
                    session["username"] = user.get("username", "")
                    session["display_name"] = user.get("display_name", "")
                    session["avatar_url"] = user.get("avatar_url")
                    session["role"] = user.get("role", "player")
                    session["account_status"] = user.get("account_status", "approved")
                    session["admin_level"] = user.get("admin_level", "none")
                    cache_set("_rz_current_user", user)
            except Exception as exc:
                print(f"admin_required warning: {exc}")

        if not user:
            session.clear()
            flash("Phiên đăng nhập admin không hợp lệ. Vui lòng đăng nhập lại.", "warning")
            return redirect(url_for("admin_login"))

        if not is_admin_user(user):
            flash("Bạn không có quyền admin.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not is_owner_user(user):
            flash("Chỉ chủ hệ thống mới có quyền này.", "danger")
            return redirect(url_for("admin"))
        return view(*args, **kwargs)
    return wrapped


def admin_permission_required(permission_code: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not has_admin_permission(user, permission_code):
                flash("Admin phụ chưa được Chủ hệ thống cấp quyền sử dụng chức năng này.", "danger")
                return redirect_admin("overview")
            return view(*args, **kwargs)
        return wrapped
    return decorator

@app.before_request
def enforce_server_maintenance():
    """Khóa toàn bộ website cho người dùng thường, kể cả /login.

    Admin luôn dùng /admin-login để vào hệ thống khi máy chủ đang bảo trì.
    Static assets và trang đăng nhập Admin được phép để màn hình bảo trì vẫn tải đẹp.
    """
    endpoint = request.endpoint or ""
    allowed_public = {"static", "admin_login"}
    if endpoint in allowed_public:
        return None

    status = get_maintenance_status()
    if not status.get("closed"):
        return None

    if _current_session_is_admin():
        return None

    # Không cho người dùng thường lách qua /login, API, link trực tiếp hoặc phiên cũ.
    if session.get("user_id"):
        session.clear()
    response = make_response(render_template("maintenance.html", maintenance=status), 503)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.before_request
def before_request():
    try:
        # V4.9: chỉ thao tác thật của người dùng mới gia hạn phiên. Heartbeat/polling không gia hạn.
        if session.get("user_id"):
            now_ts = int(time.time())
            last_real = int(session.get("last_real_activity", 0) or 0)
            if not last_real:
                session["last_real_activity"] = now_ts
            elif now_ts - last_real >= IDLE_TIMEOUT_SECONDS and request.endpoint not in {"logout", "static", "api_session_timeout_check"}:
                room = None
                try:
                    room = active_room_for_user(session.get("user_id"))
                except Exception as exc:
                    print(f"idle room check warning: {exc}")
                decision = idle_decision(now_ts=now_ts, last_activity_ts=last_real, room=room)
                if decision.expired:
                    try:
                        execute_query(
                            db.table("users").update({"is_online": False, "last_seen_at": now_iso()}).eq("id", session.get("user_id")),
                            "idle_logout_mark_offline",
                            attempts=1,
                        )
                    except Exception as exc:
                        print(f"idle logout warning: {exc}")
                    session.clear()
                    if request.path.startswith("/api/"):
                        return jsonify({"ok": False, "error": "session_expired", "redirect": url_for("login")}), 401
                    flash("Bạn đã được đăng xuất do không hoạt động trong 60 phút.", "warning")
                    return redirect(url_for("login"))

        # Không gọi ensure_admin() ở mọi request. Trước đây mỗi Vercel instance mới
        # lại đọc + cập nhật bảng users trước khi tải /bxh, tạo thêm kết nối Supabase
        # và có thể gây [Errno 16] Device or resource busy.
        if db is not None and session.get("user_id"):
            # Chỉ cập nhật online tối đa 1 lần/45 giây thay vì ở mọi request
            # (HTML, API, ảnh, heartbeat đều từng tạo một lệnh UPDATE riêng).
            now_ts = int(time.time())
            last_touch = int(session.get("last_activity_touch", 0) or 0)
            if request.endpoint == "heartbeat" or now_ts - last_touch >= 45:
                mark_current_user_active()
                session["last_activity_touch"] = now_ts

            user = current_user()
            allowed = {"change_password", "logout", "static", "heartbeat"}
            if user and user.get("must_change_password") and request.endpoint not in allowed:
                flash("Bạn đang dùng mật khẩu tạm thời. Hãy đổi mật khẩu mới để tiếp tục.", "warning")
                return redirect(url_for("change_password"))
    except Exception as exc:
        # Lỗi cập nhật online không được phép làm hỏng route chính.
        print(f"Before request warning: {exc}")


@app.context_processor

def inject_globals():
    try:
        user = current_user()
    except Exception as exc:
        print(f"inject user warning: {exc}")
        user = None

    if request.endpoint == "change_password":
        return {
            "APP_NAME": APP_NAME,
            "current_user": user,
            "get_rank_name": get_rank_name,
            "get_rank_info": get_rank_info,
            "get_rank_display": get_rank_display,
            "get_team_overall": get_team_overall,
            "get_team_tier": get_team_tier,
        "get_win_streak_title": get_win_streak_title,
        "get_win_streak_badge": get_win_streak_badge,
        "get_league_logo_url": get_league_logo_url,
            "TEAM_COUNT": TEAM_COUNT,
            "APP_VERSION": APP_VERSION,
            "RANKS": load_rank_ranges(),
            "format_vn_datetime": format_vn_datetime,
            "pending_invite_count": 0,
            "incoming_invites": [],
            "active_room": None,
            "cooldown_text": "",
            "active_announcement": None,
            "unread_notifications": [],
        }

    # Tối ưu phản hồi HTML: không chặn render để chờ phòng, lời mời và thông báo
    # hệ thống. Các dữ liệu này đã có API nền trong base.html và sẽ xuất hiện ngay
    # sau khi trang hiển thị. Chỉ giữ thông báo cá nhân vì chưa có API riêng.
    pending_count = 0
    incoming = []
    active_room = None
    cooldown = cooldown_text(user) if user else ""
    announcement = None
    try:
        unread_notifications = list_unread_notifications(user.get("id"), 5) if user else []
    except Exception:
        unread_notifications = []

    return {
        "APP_NAME": APP_NAME,
        "current_user": user,
        "get_rank_name": get_rank_name,
        "get_rank_info": get_rank_info,
        "get_rank_display": get_rank_display,
        "get_team_overall": get_team_overall,
        "get_team_tier": get_team_tier,
        "get_win_streak_title": get_win_streak_title,
        "get_win_streak_badge": get_win_streak_badge,
        "TEAM_COUNT": TEAM_COUNT,
        "APP_VERSION": APP_VERSION,
        "RANKS": load_rank_ranges(),
        "format_vn_datetime": format_vn_datetime,
        "pending_invite_count": pending_count,
        "incoming_invites": incoming,
        "active_room": active_room,
        "cooldown_text": cooldown,
        "active_announcement": announcement,
        "unread_notifications": unread_notifications,
    }


@app.route("/notifications")
@login_required
def notifications():
    user = current_user()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    unread_only = (request.args.get("filter") or "all") == "unread"
    notices, has_next = list_user_notifications(
        user.get("id"), page=page, per_page=20, unread_only=unread_only
    )
    return render_template(
        "notifications.html",
        notifications=notices,
        page=page,
        has_next=has_next,
        notification_filter="unread" if unread_only else "all",
    )


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    user = current_user()
    execute_query(
        db.table("user_notifications").update({
            "is_read": True,
            "read_at": now_iso(),
        }).eq("user_id", user.get("id")).eq("is_read", False),
        "mark_all_notifications_read",
    )
    flash("Đã đánh dấu tất cả thông báo là đã đọc.", "success")
    return redirect(url_for("notifications"))


@app.route("/notification/<notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    user = current_user()
    execute_query(
        db.table("user_notifications").update({
            "is_read": True,
            "read_at": now_iso(),
        }).eq("id", notification_id).eq("user_id", user.get("id")),
        "mark_notification_read",
    )
    next_url = request.form.get("next_url", "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/api/session/activity", methods=["POST"])
@login_required
def api_session_activity():
    """Gia hạn phiên chỉ khi trình duyệt báo có thao tác thật của người dùng."""
    session["last_real_activity"] = int(time.time())
    return jsonify({"ok": True})


@app.route("/api/session/timeout-check")
@login_required
def api_session_timeout_check():
    """Chỉ gọi một lần khi bộ đếm 60 phút hết; không phải polling."""
    user = current_user()
    room = None
    try:
        if user:
            room = active_room_for_user(user.get("id"))
    except Exception as exc:
        print(f"timeout check room warning: {exc}")
    protected = room_blocks_idle_logout(room)
    return jsonify({
        "ok": True,
        "protected": protected,
        "room_url": url_for("room_detail", room_id=room.get("id")) if protected and room else None,
    })


@app.route("/heartbeat", methods=["POST"])
@login_required
def heartbeat():
    mark_current_user_active()
    return jsonify({"ok": True})


@app.route("/api/invites/pending")
@login_required
def api_pending_invites():
    """Truy vấn trực tiếp lời mời của người hiện tại để giảm độ trễ popup."""
    user = current_user()
    if not user or user.get("role") == "admin":
        return jsonify({"invites": []})

    try:
        result = execute_query(
            db.table("match_invites")
              .select("id,from_user_id,to_user_id,tier,status,expires_at,created_at")
              .eq("to_user_id", user["id"])
              .eq("status", "pending")
              .order("created_at", desc=True)
              .limit(3),
            "api_pending_invites_direct",
            attempts=2,
        )
        rows = result.data or []
        data = []
        for row in rows:
            invite = expire_invite_if_needed(dict(row))
            if invite.get("status") != "pending":
                continue
            sender = get_user(invite.get("from_user_id")) or {}
            decorate_player_achievements(sender)
            data.append({
                "id": invite["id"],
                "from_name": sender.get("display_name", "Unknown"),
                "from_avatar_url": sender.get("avatar_url"),
                "from_achievement": sender.get("featured_achievement"),
                "from_rank": get_rank_display(sender.get("rank_points", 0)),
                "from_points": sender.get("rank_points", 0),
                "tier": invite.get("tier") or SMART_RANDOM_MODE,
                "expires_in_seconds": int(invite.get("expires_in_seconds") or 0),
                "accept_url": url_for("respond_invite", invite_id=invite["id"]),
                "reject_url": url_for("respond_invite", invite_id=invite["id"]),
            })
        return jsonify({"invites": data})
    except Exception as exc:
        print(f"api_pending_invites ERROR user={user.get('id')}: {type(exc).__name__}: {exc}")
        return jsonify({"invites": []})



@app.route("/api/active-room")
@login_required

def api_active_room():
    user = current_user()

    if not user or user.get("role") == "admin":
        return jsonify({"ok": True, "has_room": False})

    try:
        room = active_room_for_user(user["id"])
    except Exception:
        return jsonify({"ok": False, "has_room": False, "error": "temporary_db_error"}), 503

    if not room:
        return jsonify({"ok": True, "has_room": False})

    is_host = room.get("host_user_id") == user["id"]
    is_guest = room.get("guest_user_id") == user["id"]
    has_opponent = bool(room.get("guest_user_id"))

    # Chỉ ép quay lại khi trận đã bắt đầu hoặc đang chờ xác nhận.
    # Phòng trống/chờ sẵn sàng vẫn cho phép người dùng xem các trang khác.
    must_finish_statuses = {"playing", "friendly_playing", "waiting_result_confirm"}
    auto_redirect = bool(room.get("status") in must_finish_statuses and has_opponent)

    return jsonify({
        "ok": True,
        "has_room": True,
        "room_id": room["id"],
        "room_url": url_for("room_detail", room_id=room["id"]),
        "status": room.get("status"),
        "is_host": is_host,
        "is_guest": is_guest,
        "has_opponent": has_opponent,
        "auto_redirect": auto_redirect,
    })

def build_room_state_key(room):
    """Tạo khóa trạng thái ổn định dùng chung cho HTML và API phòng đấu."""
    return "|".join([
        str(room.get("status")),
        str(room.get("host_team")),
        str(room.get("guest_team")),
        str(room.get("guest_ready")),
        str(room.get("host_score")),
        str(room.get("guest_score")),
        str(room.get("rematch_host_ready")),
        str(room.get("rematch_guest_ready")),
        str(room.get("rematch_host_declined")),
        str(room.get("rematch_guest_declined")),
        str(room.get("rematch_expired")),
        str(room.get("state_expires_at")),
        str((room.get("dispute") or {}).get("status")),
        str((room.get("dispute") or {}).get("updated_at")),
    ])


@app.route("/api/room/<room_id>/state")
@login_required

def api_room_state(room_id):
    user = current_user()

    try:
        room = get_room(room_id)
    except Exception:
        return jsonify({"ok": False, "error": "temporary_db_error"}), 503

    if not room:
        return jsonify({"ok": False, "error": "room_not_found"}), 404

    if user["id"] not in [room["host_user_id"], room["guest_user_id"]] and not is_admin_user(user):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    state_key = build_room_state_key(room)

    # V4.1: nếu trạng thái chưa đổi, trả response rỗng để giảm dữ liệu truyền.
    # Client vẫn giữ polling nhưng không phải nhận/phân tích JSON lặp lại.
    since_state_key = (request.args.get("since") or "").strip()
    if since_state_key and since_state_key == state_key:
        response = app.response_class(status=204)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["X-Room-State-Unchanged"] = "1"
        return response

    rematch_declined_by_me = (
        (user["id"] == room.get("host_user_id") and room.get("rematch_host_declined"))
        or (user["id"] == room.get("guest_user_id") and room.get("rematch_guest_declined"))
    )

    return jsonify({
        "ok": True,
        "state_key": state_key,
        "status": room.get("status"),
        "rematch_declined": bool(room.get("rematch_declined")),
        "rematch_declined_by_me": bool(rematch_declined_by_me),
        "rematch_expired": bool(room.get("rematch_expired")),
        "timeout_seconds": int(room.get("timeout_seconds") or 0),
        "timeout_label": room.get("timeout_label") or "",
    })

# =========================
# Auth
# =========================
@app.route("/")
def index():
    # Trang chủ công khai luôn mở thẳng Bảng xếp hạng.
    # Người dùng chỉ được chuyển tới màn hình đăng nhập khi chủ động bấm Đăng nhập.
    return redirect(url_for("ranking"))


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    get_device_id()

    existing = current_user() if session.get("user_id") else None
    if existing and is_admin_user(existing):
        return redirect(url_for("admin"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        try:
            user = get_user_by_username(username)
        except Exception as exc:
            app.logger.warning("Admin login database warning: %s", exc)
            flash("Máy chủ dữ liệu đang bận. Vui lòng thử lại sau vài giây.", "warning")
            return redirect(url_for("admin_login"))

        if not user or user.get("password_hash") != hash_password(password):
            flash("Sai tài khoản hoặc mật khẩu Admin.", "danger")
            return redirect(url_for("admin_login"))
        if user.get("account_status", "approved") != "approved" or not is_admin_user(user):
            flash("Tài khoản này không có quyền truy cập trang quản trị.", "danger")
            return redirect(url_for("admin_login"))

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user.get("username", "")
        session["display_name"] = user.get("display_name", "")
        session["avatar_url"] = user.get("avatar_url")
        session["role"] = user.get("role", "player")
        session["account_status"] = user.get("account_status", "approved")
        session["admin_level"] = user.get("admin_level", "none")
        execute_query(
            db.table("users").update({"is_online": True, "last_seen_at": now_iso()}).eq("id", user["id"]),
            "admin_login_mark_online",
            attempts=2,
        )
        return redirect(url_for("admin"))

    return render_template("admin_login.html", auth_only=True)


@app.route("/login", methods=["GET", "POST"])
def login():
    get_device_id()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        try:
            user = get_user_by_username(username)
        except Exception as exc:
            # A temporary Supabase/Vercel socket failure must not become a raw 500.
            print(f"Login database warning: {exc}")
            flash("Máy chủ dữ liệu đang bận. Vui lòng đăng nhập lại sau vài giây.", "warning")
            return redirect(url_for("login"))

        if not user or user["password_hash"] != hash_password(password):
            flash("Sai tên tài khoản hoặc mật khẩu.", "danger")
            return redirect(url_for("login"))

        status = user.get("account_status", "approved")
        if status != "approved":
            messages = {
                "pending": "Tài khoản của bạn đang chờ Admin duyệt.",
                "rejected": "Tài khoản của bạn đã bị từ chối.",
                "banned": "Tài khoản của bạn đã bị khóa. Hãy liên hệ Admin.",
            }
            flash(messages.get(status, "Tài khoản chưa được phép đăng nhập."), "danger")
            return redirect(url_for("login"))

        ok, msg = link_device_to_user(user)
        if not ok:
            flash(msg, "danger")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["username"] = user.get("username", "")
        session["display_name"] = user.get("display_name", "")
        session["avatar_url"] = user.get("avatar_url")
        session["role"] = user.get("role", "player")
        session["account_status"] = status
        session["admin_level"] = user.get("admin_level", "none")
        execute_query(
            db.table("users").update({"is_online": True, "last_seen_at": now_iso()}).eq("id", user["id"]),
            "login_mark_online",
        )

        if user.get("must_change_password"):
            flash("Đăng nhập bằng mật khẩu tạm thành công. Hãy tạo mật khẩu mới.", "warning")
            return redirect(url_for("change_password"))

        return redirect(url_for(post_login_endpoint(get_system_features(), is_admin=is_admin_user(user))))

    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        zalo_name = request.form.get("zalo_name", "").strip()
        user = get_user_by_username(username) if username else None

        matches_identity = bool(
            user
            and zalo_name
            and (user.get("zalo_name") or "").strip().casefold() == zalo_name.casefold()
        )

        if matches_identity:
            existing = execute_query(
                db.table("password_reset_requests")
                .select("id")
                .eq("user_id", user["id"])
                .eq("status", "pending")
                .limit(1),
                "find_pending_password_reset",
            )
            if not existing.data:
                execute_query(
                    db.table("password_reset_requests").insert({
                        "user_id": user["id"],
                        "username_snapshot": user.get("username"),
                        "zalo_name_snapshot": user.get("zalo_name"),
                        "status": "pending",
                        "requested_ip": get_client_ip(),
                    }),
                    "create_password_reset_request",
                )

        flash("Nếu tài khoản và tên Zalo khớp, yêu cầu đã được gửi đến Admin. Hãy liên hệ Admin qua Zalo để nhận mật khẩu tạm.", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    user = current_user()
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        if user.get("password_hash") != hash_password(current_password):
            flash("Mật khẩu tạm hoặc mật khẩu hiện tại không đúng.", "danger")
            return redirect(url_for("change_password"))
        valid_password, password_error = validate_new_password(new_password)
        if not valid_password:
            flash(password_error, "danger")
            return redirect(url_for("change_password"))
        if hash_password(new_password) == user.get("password_hash"):
            flash("Mật khẩu mới phải khác mật khẩu tạm hoặc mật khẩu hiện tại.", "warning")
            return redirect(url_for("change_password"))

        changed_at = now_iso()
        execute_query(
            db.table("users").update({
                "password_hash": hash_password(new_password),
                "must_change_password": False,
                "password_changed_at": changed_at,
            }).eq("id", user["id"]),
            "user_change_password",
        )
        try:
            execute_query(
                db.table("password_reset_requests").update({
                    "status": "resolved",
                    "admin_note": "User đã tự đổi mật khẩu.",
                    "resolved_at": changed_at,
                }).eq("user_id", user["id"]).eq("status", "pending"),
                "close_password_reset_after_user_change",
            )
        except Exception as exc:
            print(f"close password reset warning: {exc}")
        flash("Đã đổi mật khẩu thành công.", "success")
        return redirect(url_for("profile", user_id=user["id"]) + "#account-controls")

    if not user.get("must_change_password"):
        return redirect(url_for("profile", user_id=user["id"]) + "#account-controls")
    return render_template("change_password.html", force_change=True, auth_only=True, minimum_password_length=minimum_password_length())


@app.route("/register", methods=["GET", "POST"])
def register():
    if not system_feature_enabled("registration_codes_enabled"):
        flash("Tính năng đăng ký tài khoản đang tạm tắt.", "warning")
        return redirect(url_for("login"))
    get_device_id()

    if request.method == "POST":
        can_register, msg = device_can_register()
        if not can_register:
            flash(msg, "danger")
            return redirect(url_for("register"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        zalo_name = request.form.get("zalo_name", "").strip()

        if not username or not password or not zalo_name:
            flash("Vui lòng nhập đủ Tên tài khoản, Mật khẩu và Tên Zalo.", "danger")
            return redirect(url_for("register"))

        if len(username) < 3 or len(username) > 30:
            flash("Tên tài khoản phải từ 3 đến 30 ký tự.", "danger")
            return redirect(url_for("register"))

        if len(password) < minimum_password_length():
            flash(f"Mật khẩu phải có ít nhất {minimum_password_length()} ký tự.", "danger")
            return redirect(url_for("register"))

        if len(zalo_name) < 2 or len(zalo_name) > 80:
            flash("Tên Zalo không hợp lệ.", "danger")
            return redirect(url_for("register"))

        if get_user_by_username(username):
            flash("Tên tài khoản đã tồn tại.", "danger")
            return redirect(url_for("register"))

        ip = get_client_ip()
        ua = request.headers.get("User-Agent", "")

        created = execute_query(
            db.table("users").insert({
                "username": username,
                "password_hash": hash_password(password),
                "display_name": username,
                "zalo_name": zalo_name,
                "role": "player",
                "account_status": "pending",
                "invite_code_used": None,
                "rank_points": DEFAULT_POINTS,
                "register_ip": ip,
                "register_user_agent": ua,
            }),
            "register_user",
        )

        user = created.data[0]
        link_device_to_user(user)

        flash("Đăng ký thành công. Tài khoản đang chờ Admin duyệt.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    user_id = session.get("user_id")
    if user_id:
        try:
            execute_query(
                db.table("users").update({"is_online": False, "last_seen_at": now_iso()}).eq("id", user_id),
                "logout_mark_offline",
            )
        except Exception as exc:
            print(f"logout warning: {exc}")
    session.clear()
    if request.args.get("reason") == "inactive":
        flash("Bạn đã được đăng xuất do không hoạt động trong 60 phút.", "warning")
    else:
        flash("Đã đăng xuất.", "success")
    return redirect(url_for("login"))


# =========================
# Chat / Announcements
# =========================
@app.route("/chat")
@login_required
def lobby_chat():
    if not system_feature_enabled("lobby_chat_enabled"):
        return (jsonify({"ok": False, "error": "Tính năng đang tắt"}), 403) if request.path.startswith("/api/") else redirect(url_for("dashboard"))
    return render_template("chat.html", messages=list_chat_messages("global", limit=20))


@app.route("/chat/send", methods=["POST"])
@login_required
def send_global_chat():
    user = current_user()
    message = request.form.get("message", "")

    ok, error = create_chat_message(user["id"], message, scope="global")
    if not ok:
        flash(error, "warning")
    else:
        flash("Đã gửi tin nhắn.", "success")

    return redirect(url_for("lobby_chat"))


@app.route("/api/chat/global")
@login_required
def api_global_chat():
    if not system_feature_enabled("lobby_chat_enabled"):
        return (jsonify({"ok": False, "error": "Tính năng đang tắt"}), 403) if request.path.startswith("/api/") else redirect(url_for("dashboard"))
    messages = list_chat_messages("global", limit=20)
    return jsonify({"ok": True, "messages": messages})


@app.route("/api/chat/global/status")
@login_required
def api_global_chat_status():
    if not system_feature_enabled("lobby_chat_enabled"):
        return (jsonify({"ok": False, "error": "Tính năng đang tắt"}), 403) if request.path.startswith("/api/") else redirect(url_for("dashboard"))
    """Dữ liệu nhẹ để hiển thị số tin chat sảnh chưa đọc khi khung chat đang đóng."""
    user = current_user()
    limit = 100
    query = (
        db.table("chat_messages")
        .select("id,user_id,created_at")
        .eq("scope", "global")
        .is_("room_id", "null")
        .order("created_at", desc=True)
        .limit(limit)
    )
    result = execute_query(query, "api_global_chat_status")
    rows = list(reversed(result.data or []))

    messages = [
        {
            "id": row.get("id"),
            "created_at": row.get("created_at"),
            "is_own": row.get("user_id") == user.get("id"),
        }
        for row in rows
    ]

    return jsonify({
        "ok": True,
        "messages": messages,
        "latest_created_at": messages[-1]["created_at"] if messages else None,
        "limit_reached": len(messages) >= limit,
    })


@app.route("/api/room/<room_id>/chat")
@login_required
def api_room_chat(room_id):
    if not system_feature_enabled("room_chat_enabled"):
        return (jsonify({"ok": False, "error": "Tính năng đang tắt"}), 403) if request.path.startswith("/api/") else redirect(url_for("dashboard"))
    user = current_user()
    room = get_room(room_id)

    if not room:
        return jsonify({"ok": False, "error": "room_not_found"}), 404

    if user["id"] not in [room["host_user_id"], room["guest_user_id"]] and not is_admin_user(user):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    messages = list_chat_messages("room", room_id=room_id, limit=20)
    return jsonify({"ok": True, "messages": messages})


@app.route("/room/<room_id>/chat/send", methods=["POST"])
@login_required
def send_room_chat(room_id):
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("rooms"))

    if user["id"] not in [room["host_user_id"], room["guest_user_id"]] and not is_admin_user(user):
        flash("Bạn không thuộc phòng này.", "danger")
        return redirect(url_for("rooms"))

    message = request.form.get("message", "")
    ok, error = create_chat_message(user["id"], message, scope="room", room_id=room_id)

    if not ok:
        flash(error, "warning")

    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/admin/announcement", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("announcements_manage")
def admin_create_announcement():
    user = current_user()
    title = request.form.get("title", "THÔNG BÁO").strip() or "THÔNG BÁO"
    message = request.form.get("message", "").strip()

    if not message:
        flash("Nội dung thông báo không được để trống.", "danger")
        return redirect_admin("system")

    created = create_admin_announcement(
        title=title[:40],
        message=message[:220],
        admin_user_id=user.get("id"),
    )
    announcement_id = created.data[0].get("id") if created.data else None
    log_admin_action("Đăng thông báo", "announcement", announcement_id, title[:40], message[:220])

    flash("Đã đăng thông báo admin.", "success")
    return redirect_admin("system")


@app.route("/admin/announcement/clear", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("announcements_manage")
def admin_clear_announcement():
    db.table("admin_announcements").update({"is_active": False}).eq("is_active", True).execute()
    log_admin_action("Tắt thông báo", "announcement", details="Đã tắt toàn bộ thông báo đang hoạt động.")
    flash("Đã tắt thông báo admin.", "success")
    return redirect_admin("system")


@app.route("/api/announcement/current")
@login_required
def api_current_announcement():
    events = get_active_global_streak_events()
    if events:
        announcements = []
        for event in events:
            kind = str(event.get("kind") or "milestone")
            announcements.append({
                "id": f"streak:{event.get('id', 'event')}",
                "title": event.get("title") or "DANH HIỆU CHUỖI THẮNG",
                "message": event.get("subtitle") or "Một danh hiệu mới vừa được thiết lập!",
                "created_at": event.get("published_at"),
                "expires_at": event.get("expires_at"),
                "announcement_type": "shutdown" if kind == "shutdown" else "win_streak",
                "icon": "⚡" if kind == "shutdown" else "🏆",
            })
        return jsonify({"ok": True, "announcements": announcements, "announcement": announcements[0]})

    announcement = get_active_announcement()
    if not announcement:
        return jsonify({"ok": True, "announcements": [], "announcement": None})
    admin_item = {
        "id": announcement["id"],
        "title": announcement["title"],
        "message": announcement["message"],
        "created_at": announcement["created_at"],
        "announcement_type": "admin",
        "icon": "📢",
    }
    return jsonify({"ok": True, "announcements": [admin_item], "announcement": admin_item})


@app.route("/api/chat/global/send", methods=["POST"])
@login_required
def api_send_global_chat():
    if not system_feature_enabled("lobby_chat_enabled"):
        return jsonify({"ok": False, "error": "Chat Sảnh đang bị tắt."}), 403
    user = current_user()
    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")

    ok, error = create_chat_message(user["id"], message, scope="global")
    if not ok:
        return jsonify({"ok": False, "error": error}), 400

    return jsonify({"ok": True})


@app.route("/api/admin/announcement/send", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("announcements_manage")
def api_admin_send_announcement():
    if not system_feature_enabled("announcements_enabled"):
        return jsonify({"ok": False, "error": "Thông báo hệ thống đang bị tắt."}), 403
    user = current_user()
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "THÔNG BÁO").strip()[:40] or "THÔNG BÁO"
    message = (payload.get("message") or "").strip()[:220]

    if not message:
        return jsonify({"ok": False, "error": "Nội dung thông báo không được để trống."}), 400

    created = create_admin_announcement(
        title=title,
        message=message,
        admin_user_id=user.get("id"),
    )
    announcement_id = created.data[0].get("id") if created.data else None
    log_admin_action("Đăng thông báo", "announcement", announcement_id, title, message)

    return jsonify({"ok": True})


@app.route("/api/online-count")
@login_required
def api_online_count():
    players = list_players(include_admin=False)
    online_count = sum(1 for player in players if player.get("is_online"))
    return jsonify({"ok": True, "online_count": online_count})


# =========================
# Hướng dẫn người chơi
# =========================
@app.route("/huong-dan")
@login_required
def guide():
    return render_template("guide.html")


# =========================
# Dashboard / players
# =========================
@app.route("/dashboard")
@login_required
def dashboard():
    if not dashboard_is_enabled(get_system_features()):
        return redirect(url_for("ranking"))
    user = current_user()
    try:
        player_rows = list_players()
        matches = list_matches()
        rooms = list_rooms()
        invite_count = current_pending_invite_count()
    except Exception:
        player_rows, matches, rooms = [], [], []
        invite_count = 0
        flash("Dữ liệu đang tải chậm, vui lòng thử lại sau vài giây.", "warning")

    me = next((player for player in player_rows if player.get("id") == user.get("id")), dict(user))
    my_position = next((index for index, player in enumerate(player_rows, 1) if player.get("id") == user.get("id")), None)
    my_rank_info = get_player_rank_info(me, my_position)
    total = int(me.get("total_matches", 0) or 0)
    wins = int(me.get("wins", 0) or 0)
    me["winrate"] = round((wins / total) * 100, 1) if total else 0

    my_matches = [
        decorate_match_for_view(match, user.get("id"))
        for match in matches
        if user.get("id") in {match.get("player1_id"), match.get("player2_id")}
    ]
    recent_matches = my_matches[:5]

    active_room = active_room_for_user(user.get("id"))
    attention = {
        "invites": invite_count,
        "has_room": bool(active_room),
        "waiting_confirm": len([m for m in matches if m.get("status") == "waiting_confirm" and user.get("id") in {m.get("player1_id"), m.get("player2_id")}]),
        "disputed": len([m for m in matches if m.get("status") == "disputed" and user.get("id") in {m.get("player1_id"), m.get("player2_id")}]),
    }

    activity_map = build_player_activity_map(rooms, matches)
    online_players = [p for p in player_rows if p.get("is_online") and p.get("id") != user.get("id")]
    for player in online_players:
        status = activity_map.get(player.get("id"), {"code": "ready", "label": "Sẵn sàng"})
        player["activity_code"] = status["code"]
        player["activity_label"] = status["label"]
        player["is_busy"] = status["code"] != "ready"

    online_players.sort(key=lambda p: (p.get("is_busy", False), _player_ranking_sort_key(p)))

    return render_template(
        "dashboard.html",
        me=me,
        my_position=my_position,
        my_rank_info=my_rank_info,
        attention=attention,
        online_players=online_players,
        recent_matches=recent_matches,
    )


@app.route("/rooms/create", methods=["POST"])
@login_required
def create_open_room():
    user = current_user()
    existing = active_room_for_user(user["id"])
    if existing:
        return redirect(url_for("room_detail", room_id=existing["id"]))
    if active_match_for_user(user["id"]):
        flash("Bạn đang có trận chưa hoàn tất.", "warning")
        return redirect(url_for("dashboard"))

    room = execute_query(
        db.table("match_rooms").insert({
            "invite_id": None,
            "host_user_id": user["id"],
            "guest_user_id": None,
            "team_tier": SMART_RANDOM_MODE,
            "match_mode": MATCH_MODE_RANKED,
            "friendly_tier": "A",
            "status": "waiting_ready",
            "guest_ready": False,
            "note": "Phòng mở đang chờ chủ phòng mời đối thủ.",
            "state_expires_at": None,
            "updated_at": now_iso(),
        }),
        "create_open_room",
    ).data[0]
    flash("Đã tạo phòng đấu. Bạn có thể mời đối thủ từ danh sách Players.", "success")
    return redirect(url_for("room_detail", room_id=room["id"]))


@app.route("/players")
@login_required
def players():
    player_rows = list_players()
    activity_map = build_player_activity_map()
    query = (request.args.get("q") or "").strip().casefold()
    status_filter = (request.args.get("status") or "all").strip()

    for player in player_rows:
        if not player.get("is_online"):
            status = {"code": "offline", "label": "Offline"}
        else:
            status = activity_map.get(player.get("id"), {"code": "ready", "label": "Sẵn sàng"})
        player["activity_code"] = status["code"]
        player["activity_label"] = status["label"]
        player["is_busy"] = status["code"] not in {"ready", "offline"}
        total = int(player.get("total_matches", 0) or 0)
        player["winrate"] = round((int(player.get("wins", 0) or 0) / total) * 100, 1) if total else 0
        player["last_seen_display"] = format_vn_datetime(player.get("last_seen_at"))

    if query:
        player_rows = [
            player for player in player_rows
            if query in str(player.get("display_name") or "").casefold()
            or query in str(player.get("username") or "").casefold()
        ]
    if status_filter != "all":
        player_rows = [player for player in player_rows if player.get("activity_code") == status_filter]

    status_order = {"ready": 0, "in_room": 1, "waiting_confirm": 2, "playing": 3, "offline": 4}
    player_rows.sort(key=lambda p: (status_order.get(p.get("activity_code"), 9), _player_ranking_sort_key(p)))
    return render_template("players.html", players=player_rows, q=request.args.get("q", ""), status_filter=status_filter)


def _build_recent_form_map(matches, player_ids=None, limit=5):
    """Build recent form pills for leaderboard rows using confirmed matches only."""
    tracked_ids = set(player_ids or []) if player_ids else None
    recent_map = {}

    for match in matches or []:
        if match.get("status") != "confirmed":
            continue

        player1_id = match.get("player1_id")
        player2_id = match.get("player2_id")
        score1 = match.get("score1")
        score2 = match.get("score2")
        if not player1_id or not player2_id or score1 is None or score2 is None:
            continue

        for player_id, my_score, opponent_score in (
            (player1_id, score1, score2),
            (player2_id, score2, score1),
        ):
            if tracked_ids is not None and player_id not in tracked_ids:
                continue

            bucket = recent_map.setdefault(player_id, [])
            if len(bucket) >= limit:
                continue

            if my_score > opponent_score:
                bucket.append({"code": "win", "short": "T", "label": "Thắng"})
            elif my_score < opponent_score:
                bucket.append({"code": "loss", "short": "B", "label": "Bại"})
            else:
                bucket.append({"code": "draw", "short": "H", "label": "Hòa"})

    return recent_map


@app.route("/ranking")
@app.route("/bxh")
def ranking():
    # BXH là trang công khai: khách chưa đăng nhập vẫn xem được.
    # Khi đã đăng nhập, hệ thống vẫn hiển thị thêm vị trí cá nhân như trước.
    try:
        player_rows = list_players()
    except Exception as exc:
        # BXH là trang công khai; nếu Supabase chập chờn thì vẫn trả trang thay vì HTTP 500.
        print(f"ranking list_players warning: {exc}")
        player_rows = []

    user = current_user()
    query = (request.args.get("q") or "").strip().casefold()
    rank_filter = (request.args.get("rank") or "all").strip()

    current_player = None
    current_position = None
    if user:
        current_player = next((player for player in player_rows if player.get("id") == user.get("id")), None)
        current_position = current_player.get("position") if current_player else None

    filtered = player_rows
    if query:
        filtered = [
            player for player in filtered
            if query in str(player.get("display_name") or "").casefold()
            or query in str(player.get("username") or "").casefold()
        ]
    if rank_filter != "all":
        filtered = [player for player in filtered if player.get("rank_info", {}).get("slug") == rank_filter]

    top_players = filtered[:100]
    try:
        confirmed_matches = list_matches(status="confirmed")
    except Exception as exc:
        print(f"ranking list_matches warning: {exc}")
        confirmed_matches = []

    recent_form_map = _build_recent_form_map(
        confirmed_matches,
        player_ids={player.get("id") for player in top_players},
        limit=5,
    )

    for player in top_players:
        total_matches = int(player.get("total_matches") or 0)
        wins = int(player.get("wins") or 0)
        draws = int(player.get("draws") or 0)
        losses = int(player.get("losses") or 0)
        player["winrate"] = round((wins / total_matches) * 100, 1) if total_matches else 0
        player["record_text"] = f"{wins}T • {draws}H • {losses}B"
        player["recent_form"] = recent_form_map.get(player.get("id"), [])

    template_name = "ranking.html" if user else "public_ranking.html"
    return render_template(
        template_name,
        players=filtered,
        current_player=current_player,
        current_position=current_position,
        q=request.args.get("q", ""),
        rank_filter=rank_filter,
    )


@app.route("/profile")
@login_required
def my_profile():
    return redirect(url_for("profile", user_id=current_user().get("id")))


@app.route("/profile/avatar", methods=["POST"])
@login_required
def update_profile_avatar():
    user = current_user()
    avatar_file = request.files.get("avatar")
    new_path = None

    try:
        avatar_bytes = prepare_avatar_bytes(avatar_file)
        new_path, new_url = upload_avatar_to_storage(user.get("id"), avatar_bytes)
        old_path = user.get("avatar_path")

        execute_query(
            db.table("users").update({
                "avatar_url": new_url,
                "avatar_path": new_path,
                "avatar_updated_at": now_iso(),
            }).eq("id", user.get("id")),
            "update_profile_avatar",
        )
        session["avatar_url"] = new_url
        if old_path and old_path != new_path:
            remove_avatar_object(old_path)
        flash("Ảnh đại diện đã được cập nhật và sẽ hiển thị trên toàn app.", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        if new_path:
            remove_avatar_object(new_path)
        print(f"update_profile_avatar error: {exc}")
        flash("Không thể cập nhật ảnh đại diện lúc này. Hãy kiểm tra đã chạy SQL V1.6.1 rồi thử lại.", "danger")

    return redirect(url_for("profile", user_id=user.get("id")))


@app.route("/profile/avatar/delete", methods=["POST"])
@login_required
def delete_profile_avatar():
    user = current_user()
    old_path = user.get("avatar_path")
    try:
        execute_query(
            db.table("users").update({
                "avatar_url": None,
                "avatar_path": None,
                "avatar_updated_at": now_iso(),
            }).eq("id", user.get("id")),
            "delete_profile_avatar",
        )
        session["avatar_url"] = None
        remove_avatar_object(old_path)
        flash("Đã xóa ảnh đại diện. App sẽ dùng chữ cái mặc định.", "success")
    except Exception as exc:
        print(f"delete_profile_avatar error: {exc}")
        flash("Không thể xóa ảnh đại diện lúc này.", "danger")
    return redirect(url_for("profile", user_id=user.get("id")))


@app.route("/profile/display-name", methods=["POST"])
@login_required
def update_display_name():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    new_name = " ".join(request.form.get("display_name", "").strip().split())
    current_name = str(user.get("display_name") or "").strip()
    change_count = int(user.get("display_name_change_count", 0) or 0)

    if change_count >= 2:
        flash("Bạn đã sử dụng hết 2 lần đổi tên hiển thị.", "danger")
        return redirect(url_for("profile", user_id=user.get("id")))

    if len(new_name) < 2 or len(new_name) > 40:
        flash("Tên hiển thị phải có từ 2 đến 40 ký tự.", "danger")
        return redirect(url_for("profile", user_id=user.get("id")))

    if new_name.casefold() == current_name.casefold():
        flash("Tên hiển thị mới không khác tên hiện tại.", "warning")
        return redirect(url_for("profile", user_id=user.get("id")))

    # Không cho hai tài khoản có tên hiển thị giống hệt nhau để tránh nhầm lẫn.
    try:
        duplicate = execute_query(
            db.table("users").select("id,display_name").ilike("display_name", new_name).limit(5),
            "check_display_name_duplicate",
        ).data or []
    except Exception:
        duplicate = []
    if any(row.get("id") != user.get("id") and str(row.get("display_name") or "").casefold() == new_name.casefold() for row in duplicate):
        flash("Tên hiển thị này đã được người khác sử dụng.", "danger")
        return redirect(url_for("profile", user_id=user.get("id")))

    try:
        execute_query(
            db.table("users").update({
                "display_name": new_name,
                "display_name_change_count": change_count + 1,
                "display_name_changed_at": now_iso(),
            }).eq("id", user.get("id")),
            "update_display_name",
        )
        session["display_name"] = new_name
        remaining = max(0, 2 - (change_count + 1))
        flash(f"Đã đổi tên hiển thị. Bạn còn {remaining} lần đổi tên.", "success")
    except Exception as exc:
        print(f"update_display_name error: {exc}")
        flash("Không thể đổi tên lúc này. Hãy kiểm tra đã chạy file SQL cập nhật V1.8.47.", "danger")

    return redirect(url_for("profile", user_id=user.get("id")))


@app.route("/profile/<user_id>")
@login_required
def profile(user_id):
    user = get_user(user_id)
    if not user:
        flash("Không tìm thấy player.", "danger")
        return redirect(url_for("players"))

    viewer = current_user()
    all_matches = list_matches()
    player_matches_raw = [
        match for match in all_matches
        if user_id in {match.get("player1_id"), match.get("player2_id")}
    ]
    matches = [decorate_match_for_view(match, user_id) for match in player_matches_raw[:10]]

    form = []
    for match in matches:
        if match.get("status") != "confirmed":
            continue
        form.append(match.get("result_code", "neutral"))
        if len(form) >= 5:
            break

    total = int(user.get("total_matches", 0) or 0)
    wins = int(user.get("wins", 0) or 0)
    user["winrate"] = round((wins / total) * 100, 1) if total else 0
    user["goal_diff"] = int(user.get("goals_for", 0) or 0) - int(user.get("goals_against", 0) or 0)
    ranking_players = list_players()
    position = next((i for i, player in enumerate(ranking_players, 1) if player.get("id") == user_id), None)
    user["rank_info"] = get_player_rank_info(user, position)
    user["position"] = position
    decorate_player_achievements(user, position)
    user["is_online"] = is_user_online_now(user)

    confirmed = [match for match in player_matches_raw if match.get("status") == "confirmed"]
    teams = []
    opponents = []
    users = users_map()
    for match in confirmed:
        as_player1 = match.get("player1_id") == user_id
        teams.append(match.get("team1") if as_player1 else match.get("team2"))
        opponent_id = match.get("player2_id") if as_player1 else match.get("player1_id")
        opponents.append(users.get(opponent_id, {}).get("display_name", "Unknown"))
    user["favorite_team"] = Counter([team for team in teams if team]).most_common(1)[0][0] if any(teams) else "Chưa có"
    user["frequent_opponent"] = Counter([name for name in opponents if name]).most_common(1)[0][0] if opponents else "Chưa có"

    h2h = None
    if viewer.get("id") != user_id:
        h2h_matches = [
            decorate_match_for_view(match, viewer.get("id"))
            for match in all_matches
            if match.get("status") == "confirmed"
            and {match.get("player1_id"), match.get("player2_id")} == {viewer.get("id"), user_id}
        ]
        h2h = {
            "total": len(h2h_matches),
            "wins": len([m for m in h2h_matches if m.get("result_code") == "win"]),
            "draws": len([m for m in h2h_matches if m.get("result_code") == "draw"]),
            "losses": len([m for m in h2h_matches if m.get("result_code") == "loss"]),
            "recent": h2h_matches[:5],
        }

    activity = build_player_activity_map().get(user_id)
    can_invite = bool(
        viewer.get("id") != user_id
        and user.get("is_online")
        and not activity
    )

    profile_active_room = active_room_for_user(viewer.get("id")) if viewer.get("id") == user_id else None

    return render_template(
        "profile.html",
        player=user,
        matches=matches,
        form=form,
        h2h=h2h,
        can_invite=can_invite,
        activity=activity,
        profile_active_room=profile_active_room,
    )


# =========================
# Invites
# =========================
@app.route("/invites")
@login_required
def invites():
    user = current_user()

    # Nếu người chơi đã có phòng active, không để mắc kẹt ở trang mời đấu.
    try:
        active_room = active_room_for_user(user["id"])
        if active_room:
            return redirect(url_for("room_detail", room_id=active_room["id"]))
    except Exception:
        flash("Đang kiểm tra phòng hiện tại hơi chậm, vui lòng thử lại sau vài giây.", "warning")

    all_players = list_players()
    available_players = [
        player for player in all_players
        if player["id"] != user["id"] and player.get("is_online")
    ]

    all_invites = list_invites()
    received = [i for i in all_invites if i["to_user_id"] == user["id"] and i["status"] == "pending"]
    sent = [i for i in all_invites if i["from_user_id"] == user["id"] and i["status"] == "pending"]
    history = [i for i in all_invites if i["from_user_id"] == user["id"] or i["to_user_id"] == user["id"]][:20]

    return render_template(
        "invites.html",
        players=available_players,
        received=received,
        sent=sent,
        history=history,
    )


@app.route("/invites/send", methods=["POST"])
@login_required
def send_invite():
    user = current_user()

    if is_player_in_cooldown(user):
        flash(f"Bạn đang trong thời gian chờ {cooldown_text(user)}.", "warning")
        return redirect(url_for("players"))

    to_user_id = request.form.get("to_user_id")
    tier = SMART_RANDOM_MODE

    if not to_user_id or to_user_id == user["id"]:
        flash("Đối thủ không hợp lệ.", "danger")
        return redirect(url_for("players"))

    opponent = get_user(to_user_id)
    if not opponent:
        flash("Không tìm thấy đối thủ.", "danger")
        return redirect(url_for("players"))

    try:
        state = matchmaking_snapshot(user["id"], to_user_id)
    except Exception as exc:
        print(f"send_invite state ERROR from={user.get('id')} to={to_user_id}: {type(exc).__name__}: {exc}")
        flash("Không thể kiểm tra trạng thái phòng lúc này. Vui lòng thử lại sau vài giây.", "danger")
        return redirect(url_for("players"))

    sender_room = state.get("room_a")
    if state.get("match_a"):
        flash("Bạn đang có trận chưa hoàn tất.", "warning")
        return redirect(url_for("dashboard"))
    if sender_room and not (
        sender_room.get("host_user_id") == user["id"]
        and sender_room.get("status") == "waiting_ready"
        and not sender_room.get("guest_user_id")
    ):
        flash("Bạn đang có phòng chưa hoàn tất.", "warning")
        return redirect(url_for("dashboard"))
    if state.get("room_b") or state.get("match_b"):
        flash("Người chơi này đang ở trong phòng đấu hoặc đang thi đấu. Bạn hãy mời lại sau khi trận của họ kết thúc nhé.", "warning")
        return redirect(url_for("players"))

    if is_player_in_cooldown(opponent):
        flash("Người chơi này đang trong thời gian nghỉ 3 phút. Bạn hãy mời lại sau nhé.", "warning")
        return redirect(url_for("players"))

    if not is_user_online_now(opponent):
        flash("Người chơi này vừa offline. Bạn hãy chọn một đối thủ đang online khác nhé.", "danger")
        return redirect(url_for("players"))

    if state.get("pair_pending"):
        flash("Hai người đang có lời mời chờ xử lý.", "warning")
        return redirect(url_for("players"))

    invite_result = execute_query(
        db.table("match_invites").insert({
            "from_user_id": user["id"],
            "to_user_id": to_user_id,
            "tier": tier,
            "status": "pending",
            "message": f'{user["display_name"]} mời {opponent["display_name"]} thi đấu hạng.',
            "expires_at": future_iso(INVITE_TIMEOUT_SECONDS),
            "updated_at": now_iso(),
        }),
        "send_match_invite",
    )
    invite = invite_result.data[0] if invite_result.data else None
    ttl_cache_delete("invites_raw")
    cache_delete("_rz_invites_all")
    if not invite:
        flash("Không thể gửi lời mời lúc này. Vui lòng thử lại.", "danger")
        return redirect(url_for("players"))

    # Chủ phòng phải được đưa vào phòng ngay sau khi bấm Mời đấu.
    # Nếu đã có phòng trống thì gắn lời mời vào phòng đó; nếu chưa có thì tạo phòng mới.
    if sender_room:
        room_result = execute_query(
            db.table("match_rooms").update({
                "invite_id": invite["id"],
                "note": f'Đã mời {opponent["display_name"]}. Đang chờ đối thủ chấp nhận.',
                "updated_at": now_iso(),
            }).eq("id", sender_room["id"]).eq("status", "waiting_ready"),
            "attach_invite_to_open_room",
        )
        room = room_result.data[0] if room_result.data else sender_room
    else:
        room_result = execute_query(
            db.table("match_rooms").insert({
                "invite_id": invite["id"],
                "host_user_id": user["id"],
                "guest_user_id": None,
                "team_tier": SMART_RANDOM_MODE,
                "match_mode": MATCH_MODE_RANKED,
                "friendly_tier": "A",
                "status": "waiting_ready",
                "guest_ready": False,
                "note": f'Đã mời {opponent["display_name"]}. Đang chờ đối thủ chấp nhận.',
                "state_expires_at": None,
                "updated_at": now_iso(),
            }),
            "create_room_for_invite",
        )
        room = room_result.data[0] if room_result.data else None

    if not room:
        # Tránh để lại lời mời treo nếu tạo phòng thất bại.
        execute_query(
            db.table("match_invites").update({
                "status": "cancelled",
                "updated_at": now_iso(),
            }).eq("id", invite["id"]).eq("status", "pending"),
            "cancel_invite_after_room_error",
        )
        flash("Đã gửi lời mời nhưng không thể tạo phòng. Vui lòng thử lại.", "danger")
        return redirect(url_for("players"))

    flash(f'Đã mời {opponent["display_name"]}. Bạn đang ở trong phòng và chờ đối thủ chấp nhận.', "success")
    return redirect(url_for("room_detail", room_id=room["id"]))


@app.route("/invites/respond/<invite_id>", methods=["POST"])
@login_required
def respond_invite(invite_id):
    user = current_user()
    action = request.form.get("action")
    invite = get_invite(invite_id)

    if not invite:
        flash("Không tìm thấy lời mời.", "danger")
        return redirect(url_for("invites"))

    if invite["to_user_id"] != user["id"]:
        flash("Bạn không có quyền xử lý lời mời này.", "danger")
        return redirect(url_for("invites"))

    if invite["status"] == "expired":
        flash("Lời mời đã hết hạn sau 60 giây. Hãy nhờ đối thủ gửi lời mời mới.", "warning")
        return redirect(url_for("dashboard"))

    if invite["status"] != "pending":
        flash("Lời mời này đã được xử lý.", "warning")
        return redirect(url_for("invites"))

    if action == "reject":
        cooldown_until = (now_dt() + timedelta(minutes=COOLDOWN_MINUTES)).isoformat()
        db.table("users").update({"matchmaking_cooldown_until": cooldown_until}).eq("id", user["id"]).execute()
        db.table("match_invites").update({"status": "rejected", "updated_at": now_iso()}).eq("id", invite_id).execute()
        flash("Đã từ chối lời mời. Bạn sẽ tạm nghỉ 3 phút trước khi mời/nhận trận mới.", "success")
        return redirect(url_for("invites"))

    if action != "accept":
        flash("Hành động không hợp lệ.", "danger")
        return redirect(url_for("invites"))

    if is_player_in_cooldown(user):
        flash(f"Bạn đang trong thời gian chờ {cooldown_text(user)}.", "warning")
        return redirect(url_for("invites"))

    if active_room_for_user(user["id"]) or active_match_for_user(user["id"]):
        flash("Bạn đang có phòng hoặc trận chưa hoàn tất.", "warning")
        return redirect(url_for("dashboard"))

    inviter_id = invite.get("from_user_id")
    inviter_room = active_room_for_user(inviter_id)
    if active_match_for_user(inviter_id) or (inviter_room and not (
        inviter_room.get("host_user_id") == inviter_id
        and inviter_room.get("status") == "waiting_ready"
        and not inviter_room.get("guest_user_id")
    )):
        execute_query(
            db.table("match_invites").update({
                "status": "cancelled",
                "updated_at": now_iso(),
            }).eq("id", invite_id),
            "cancel_stale_invite_busy_sender",
        )
        flash("Người mời đang ở phòng hoặc trận khác. Lời mời này đã hết hiệu lực.", "warning")
        return redirect(url_for("dashboard"))

    if inviter_room:
        room = execute_query(
            db.table("match_rooms").update({
                "invite_id": invite_id,
                "guest_user_id": invite["to_user_id"],
                "guest_ready": False,
                "note": "Đối thủ đã vào phòng. Khách chưa sẵn sàng.",
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", inviter_room["id"]).eq("status", "waiting_ready"),
            "attach_guest_to_open_room",
        ).data[0]
    else:
        room = db.table("match_rooms").insert({
            "invite_id": invite_id,
            "host_user_id": invite["from_user_id"],
            "guest_user_id": invite["to_user_id"],
            "team_tier": SMART_RANDOM_MODE,
            "status": "waiting_ready",
            "guest_ready": False,
            "note": "Đối thủ đã vào phòng. Khách chưa sẵn sàng.",
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).execute().data[0]

    db.table("match_invites").update({"status": "accepted", "updated_at": now_iso()}).eq("id", invite_id).execute()

    flash("Đã chấp nhận lời mời. Hãy bấm Sẵn sàng khi bạn đã chuẩn bị xong.", "success")
    return redirect(url_for("room_detail", room_id=room["id"]))


@app.route("/invites/cancel/<invite_id>", methods=["POST"])
@login_required
def cancel_invite(invite_id):
    user = current_user()
    invite = get_invite(invite_id)

    if not invite:
        flash("Không tìm thấy lời mời.", "danger")
        return redirect(url_for("invites"))

    if invite["from_user_id"] != user["id"]:
        flash("Bạn không có quyền hủy lời mời này.", "danger")
        return redirect(url_for("invites"))

    if invite["status"] != "pending":
        flash("Lời mời này đã được xử lý.", "warning")
        return redirect(url_for("invites"))

    db.table("match_invites").update({"status": "cancelled", "updated_at": now_iso()}).eq("id", invite_id).execute()
    flash("Đã hủy lời mời.", "success")
    return redirect(url_for("invites"))


# =========================
# Rooms
# =========================
@app.route("/rooms")
@login_required
def rooms():
    user = current_user()
    all_rooms = list_rooms()
    my_rooms = [r for r in all_rooms if user["id"] in [r["host_user_id"], r["guest_user_id"]]]
    return render_template("rooms.html", rooms=my_rooms)


@app.route("/room/<room_id>")
@login_required

def room_detail(room_id):
    user = current_user()

    try:
        room = get_room(room_id)
    except Exception:
        flash("Phòng đang tải chậm hoặc Supabase vừa ngắt kết nối. Vui lòng thử lại sau vài giây.", "warning")
        return redirect(url_for("rooms"))

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("rooms"))

    if user["id"] not in [room["host_user_id"], room["guest_user_id"]] and not is_admin_user(user):
        flash("Bạn không thuộc phòng này.", "danger")
        return redirect(url_for("rooms"))

    room_head_to_head = build_room_head_to_head(room)
    return render_template(
        "room_detail.html",
        room=room,
        initial_room_state_key=build_room_state_key(room),
        friendly_tiers=get_available_team_tiers(),
        room_head_to_head=room_head_to_head,
    )


@app.route("/room/<room_id>/leave", methods=["POST"])
@login_required
def room_leave(room_id):
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("dashboard"))

    if user["id"] not in [room.get("host_user_id"), room.get("guest_user_id")]:
        flash("Bạn không thuộc phòng này.", "danger")
        return redirect(url_for("dashboard"))

    if room.get("status") not in {"waiting_ready", "friendly_playing"}:
        flash("Không thể rời phòng khi trận xếp hạng đang thi đấu hoặc đang chờ xác nhận kết quả.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    if user["id"] == room.get("guest_user_id"):
        execute_query(
            db.table("match_rooms").update({
                "guest_user_id": None,
                "guest_ready": False,
                "guest_team": None,
                "guest_team_overall": None,
                "guest_team_logo_url": None,
                "host_team": None,
                "host_team_overall": None,
                "host_team_logo_url": None,
                "host_team_league": None,
                "guest_team_league": None,
                "status": "waiting_ready",
                "match_id": None,
                "invite_id": None,
                "note": f'{user["display_name"]} đã rời phòng. Chủ phòng có thể mời đối thủ khác.',
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id),
            "guest_leave_keep_room",
        )
        flash("Bạn đã rời phòng. Phòng vẫn được giữ cho chủ phòng và không ảnh hưởng điểm rank.", "success")
        return redirect(url_for("dashboard"))

    execute_query(
        db.table("match_rooms").update({
            "status": "cancelled",
            "guest_ready": False,
            "note": f'{user["display_name"]} đã đóng phòng.',
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).eq("id", room_id),
        "host_close_room",
    )
    flash("Bạn đã thoát và đóng phòng đấu.", "success")
    return redirect(url_for("dashboard"))


@app.route("/room/<room_id>/guest-forfeit", methods=["POST"])
@login_required
def room_guest_forfeit(room_id):
    """Khách chủ động bỏ cuộc sau khi đã chấp nhận vào phòng hoặc sau khi quay đội."""
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("dashboard"))

    if user["id"] != room.get("guest_user_id"):
        flash("Chỉ người chơi Sân Khách mới có thể dùng chức năng này.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    allowed_statuses = {"waiting_ready", "playing", "friendly_playing", "waiting_result_confirm"}
    if room.get("status") not in allowed_statuses:
        flash("Phòng hiện không ở trạng thái có thể bỏ cuộc.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    original_status = room.get("status")
    reason = f'{user["display_name"]} đã chủ động bỏ cuộc và bị trừ {ROOM_ABANDON_PENALTY} RP.'
    result = execute_query(
        db.table("match_rooms").update({
            "status": "cancelled",
            "guest_ready": False,
            "note": reason,
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).eq("id", room_id).eq("status", original_status),
        "guest_forfeit_room",
    )

    # Điều kiện status giúp tránh bấm hai lần và bị trừ RP nhiều lần.
    if not (result.data or []):
        flash("Phòng đã được xử lý trước đó. Bạn không bị trừ điểm thêm.", "warning")
        return redirect(url_for("dashboard"))

    penalty_delta = apply_room_abandon_penalty(user["id"])
    if room.get("match_id"):
        execute_query(
            db.table("matches").update({
                "status": "cancelled",
                "delta1": 0,
                "delta2": penalty_delta if penalty_delta is not None else -ROOM_ABANDON_PENALTY,
                "note": reason,
                "updated_at": now_iso(),
            }).eq("id", room.get("match_id")),
            "guest_forfeit_match",
        )

    create_user_notification(
        room.get("host_user_id"),
        "🚪 Đối thủ đã bỏ cuộc",
        f'{user["display_name"]} đã thoát phòng và bị trừ {ROOM_ABANDON_PENALTY} RP. Bạn không bị cộng hoặc trừ RP.',
        "/matches",
        "guest_forfeit",
    )
    create_user_notification(
        user["id"],
        "⚠️ Bạn đã bỏ cuộc",
        f"Bạn bị trừ {ROOM_ABANDON_PENALTY} RP và được tính một trận thua.",
        "/matches",
        "room_forfeit_penalty",
    )
    flash(f"Bạn đã bỏ cuộc và bị trừ {ROOM_ABANDON_PENALTY} RP.", "danger")
    return redirect(url_for("dashboard"))


@app.route("/room/<room_id>/rematch", methods=["POST"])
@login_required
def room_rematch(room_id):
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("dashboard"))

    if user["id"] not in [room["host_user_id"], room["guest_user_id"]]:
        flash("Bạn không thuộc phòng này.", "danger")
        return redirect(url_for("dashboard"))

    if room["status"] != "confirmed":
        flash("Chỉ có thể đá tiếp sau khi kết quả trận trước đã được xác nhận.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    host_active_room = active_room_for_user(room["host_user_id"], exclude_room_id=room_id)
    guest_active_room = active_room_for_user(room["guest_user_id"], exclude_room_id=room_id)
    host_active_match = active_match_for_user(room["host_user_id"])
    guest_active_match = active_match_for_user(room["guest_user_id"])
    if host_active_room or guest_active_room or host_active_match or guest_active_match:
        flash("Một trong hai người đang có phòng hoặc trận khác nên chưa thể đá tiếp từ phòng này.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    is_host = user["id"] == room["host_user_id"]
    my_ready_note = REMATCH_HOST_READY_NOTE if is_host else REMATCH_GUEST_READY_NOTE
    opponent_ready_note = REMATCH_GUEST_READY_NOTE if is_host else REMATCH_HOST_READY_NOTE
    current_note = room.get("note") or ""

    if current_note in {REMATCH_HOST_DECLINED_NOTE, REMATCH_GUEST_DECLINED_NOTE}:
        flash("Đối thủ đã chọn không đá tiếp. Phiên đá tiếp đã kết thúc.", "warning")
        return redirect(url_for("dashboard"))

    if current_note == REMATCH_EXPIRED_NOTE:
        flash("Yêu cầu đá tiếp đã hết hạn sau 60 giây.", "warning")
        return redirect(url_for("dashboard"))

    if current_note == my_ready_note:
        flash("Bạn đã chọn Đá tiếp. Đang chờ đối thủ xác nhận.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    # Khách bấm Đá tiếp: khách được tính là sẵn sàng ngay và chủ phòng thấy nút quay đội Xếp hạng.
    if not is_host:
        execute_query(
            db.table("match_rooms").update({
                "host_team": None,
                "guest_team": None,
                "host_team_overall": None,
                "guest_team_overall": None,
                "host_team_logo_url": None,
                "guest_team_logo_url": None,
                "host_team_league": None,
                "guest_team_league": None,
                "guest_ready": True,
                "status": "waiting_ready",
                "match_id": None,
                "host_score": None,
                "guest_score": None,
                "submitted_by_id": None,
                "confirmed_by_id": None,
                "match_mode": MATCH_MODE_RANKED,
                "team_tier": SMART_RANDOM_MODE,
                "note": "Khách đã chọn đá tiếp và sẵn sàng. Chủ phòng có thể quay đội Xếp hạng.",
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "confirmed"),
            "room_guest_rematch_ready_for_ranked_random",
        )
        flash("Bạn đã chọn Đá tiếp. Chủ phòng có thể quay đội Xếp hạng ngay.", "success")
        return redirect(url_for("room_detail", room_id=room_id))

    # Người đầu tiên bấm Đá tiếp: ghi nhận ngay trong phòng, không tạo lời mời mới.
    if current_note != opponent_ready_note:
        execute_query(
            db.table("match_rooms").update({
                "note": my_ready_note,
                "state_expires_at": future_iso(REMATCH_TIMEOUT_SECONDS),
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "confirmed"),
            "room_rematch_first_ready",
        )
        flash("Bạn đã chọn Đá tiếp. Đang chờ đối thủ bấm Đá tiếp.", "success")
        return redirect(url_for("room_detail", room_id=room_id))

    # Người thứ hai đồng ý: dùng lại chính phòng hiện tại và đưa cả hai về bước random đội.
    host_active_room = active_room_for_user(room["host_user_id"], exclude_room_id=room_id)
    guest_active_room = active_room_for_user(room["guest_user_id"], exclude_room_id=room_id)
    if host_active_room or guest_active_room:
        flash("Một trong hai người đang có phòng khác chưa hoàn tất nên chưa thể đá tiếp.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    # Hủy lời mời chờ cũ giữa hai người (nếu còn từ phiên bản trước), tránh hiện thông báo thừa.
    for from_user_id, to_user_id in [
        (room["host_user_id"], room["guest_user_id"]),
        (room["guest_user_id"], room["host_user_id"]),
    ]:
        try:
            db.table("match_invites").update({
                "status": "cancelled",
                "updated_at": now_iso(),
            }).eq("from_user_id", from_user_id).eq("to_user_id", to_user_id).eq("status", "pending").execute()
        except Exception as exc:
            print(f"Rematch pending invite cleanup warning: {exc}")

    execute_query(
        db.table("match_rooms").update({
            "host_team": None,
            "guest_team": None,
            "guest_ready": True,
            "status": "waiting_ready",
            "match_id": None,
            "host_score": None,
            "guest_score": None,
            "submitted_by_id": None,
            "confirmed_by_id": None,
            "team_tier": SMART_RANDOM_MODE,
            "note": "Hai người đã đồng ý đá tiếp. Đang chờ Chủ Phòng quay đội.",
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).eq("id", room_id).eq("status", "confirmed"),
        "room_rematch_reset_same_room",
    )

    flash("Cả hai đã đồng ý đá tiếp. Đang chờ Chủ Phòng quay đội.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/rematch-decline", methods=["POST"])
@login_required
def room_rematch_decline(room_id):
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("dashboard"))

    if user["id"] not in [room["host_user_id"], room["guest_user_id"]]:
        flash("Bạn không thuộc phòng này.", "danger")
        return redirect(url_for("dashboard"))

    if room["status"] != "confirmed":
        flash("Chỉ có thể từ chối đá tiếp sau khi trận trước đã hoàn tất.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    is_host = user["id"] == room["host_user_id"]
    my_ready_note = REMATCH_HOST_READY_NOTE if is_host else REMATCH_GUEST_READY_NOTE
    opponent_ready_note = REMATCH_GUEST_READY_NOTE if is_host else REMATCH_HOST_READY_NOTE
    decline_note = REMATCH_HOST_DECLINED_NOTE if is_host else REMATCH_GUEST_DECLINED_NOTE
    current_note = room.get("note") or ""

    if current_note in {REMATCH_HOST_DECLINED_NOTE, REMATCH_GUEST_DECLINED_NOTE}:
        flash("Phiên đá tiếp đã được từ chối trước đó.", "warning")
        return redirect(url_for("dashboard"))

    # Cho phép rời phòng ngay sau khi kết quả đã xác nhận, kể cả chưa có ai bấm Đá tiếp.

    execute_query(
        db.table("match_rooms").update({
            "note": decline_note,
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).eq("id", room_id).eq("status", "confirmed"),
        "room_rematch_declined",
    )

    flash("Bạn đã rời phòng và trở về sảnh chính.", "success")
    return redirect(url_for("dashboard"))


@app.route("/room/<room_id>/random-teams", methods=["POST"])
@login_required
def room_random_teams(room_id):
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("rooms"))
    if user["id"] != room["host_user_id"] and not is_admin_user(user):
        flash("Chỉ chủ phòng mới được quay đội.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))
    if room["status"] != "waiting_ready":
        flash("Phòng không còn ở bước chờ quay đội.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    if not room.get("guest_user_id"):
        flash("Phòng chưa có đối thủ. Hãy mời một người chơi vào phòng.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    if not room.get("guest_ready"):
        flash("Đội khách chưa sẵn sàng. Hãy chờ khách bấm Sẵn sàng.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    if room.get("match_id") or room.get("host_team") or room.get("guest_team"):
        flash("Phòng đã được quay đội hoặc đã tạo trận.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    match_mode = (request.form.get("match_mode") or MATCH_MODE_RANKED).strip().lower()
    if match_mode == MATCH_MODE_FRIENDLY and not system_feature_enabled("friendly_enabled"):
        flash("Tính năng Giao hữu đang tạm tắt.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    if match_mode not in {MATCH_MODE_RANKED, MATCH_MODE_FRIENDLY}:
        match_mode = MATCH_MODE_RANKED

    host = get_user(room["host_user_id"])
    guest = get_user(room["guest_user_id"])
    if not host or not guest:
        flash("Không tải được thông tin hai người chơi.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    try:
        if match_mode == MATCH_MODE_FRIENDLY:
            selected_tier = (request.form.get("friendly_tier") or room.get("friendly_tier") or "A").strip().upper()
            result = friendly_random_team_pair(selected_tier)
            execute_query(
                db.table("match_rooms").update({
                    "host_team": result["team_a"],
                    "guest_team": result["team_b"],
                    "host_team_overall": result["overall_a"],
                    "guest_team_overall": result["overall_b"],
                    "host_team_logo_url": result.get("logo_a") or None,
                    "guest_team_logo_url": result.get("logo_b") or None,
                    "host_team_league": result.get("league_a") or None,
                    "guest_team_league": result.get("league_b") or None,
                    "team_tier": selected_tier,
                    "friendly_tier": selected_tier,
                    "match_mode": MATCH_MODE_FRIENDLY,
                    "status": "friendly_playing",
                    "match_id": None,
                    "note": f"Giao hữu Tier {selected_tier}; không lưu lịch sử và không tính RP.",
                    "state_expires_at": None,
                    "updated_at": now_iso(),
                }).eq("id", room_id).eq("status", "waiting_ready"),
                "room_friendly_random",
            )
            flash(
                f'Giao hữu Tier {selected_tier}: {result["team_a"]} ({result.get("league_a") or "Không rõ giải"}) vs '
                f'{result["team_b"]} ({result.get("league_b") or "Không rõ giải"}). Không lưu lịch sử, không tính điểm.',
                "success",
            )
            return redirect(url_for("room_detail", room_id=room_id))

        result = smart_random_team_pair(host, guest)
        match_result = execute_query(
            db.table("matches").insert({
                "player1_id": room["host_user_id"],
                "player2_id": room["guest_user_id"],
                "team1": result["team_a"],
                "team2": result["team_b"],
                "team1_overall": result["overall_a"],
                "team2_overall": result["overall_b"],
                "team1_logo_url": result.get("logo_a") or None,
                "team2_logo_url": result.get("logo_b") or None,
                "team1_league": result.get("league_a") or None,
                "team2_league": result.get("league_b") or None,
                "host_xp_factor": HOST_XP_FACTOR,
                "status": "playing",
                "note": "",
                "updated_at": now_iso(),
            }),
            "room_random_create_match",
        )
        match = match_result.data[0] if match_result.data else None
        if not match:
            flash("Không thể tạo trận sau khi quay đội. Vui lòng thử lại.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

        execute_query(
            db.table("match_rooms").update({
                "host_team": result["team_a"],
                "guest_team": result["team_b"],
                "host_team_overall": result["overall_a"],
                "guest_team_overall": result["overall_b"],
                "host_team_logo_url": result.get("logo_a") or None,
                "guest_team_logo_url": result.get("logo_b") or None,
                "host_team_league": result.get("league_a") or None,
                "guest_team_league": result.get("league_b") or None,
                "team_tier": SMART_RANDOM_MODE,
                "match_mode": MATCH_MODE_RANKED,
                "status": "playing",
                "match_id": match["id"],
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "waiting_ready"),
            "room_random_start_match",
        )
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/reroll-friendly", methods=["POST"])
@login_required
def room_reroll_friendly(room_id):
    if not system_feature_enabled("friendly_enabled"):
        flash("Tính năng Giao hữu đang tạm tắt.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    user = current_user()
    room = get_room(room_id)
    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("dashboard"))
    if user["id"] != room.get("host_user_id") and not is_admin_user(user):
        flash("Chỉ chủ phòng mới được quay lại đội giao hữu.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))
    if room.get("status") != "friendly_playing":
        flash("Phòng không có trận giao hữu đang diễn ra.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    selected_tier = (room.get("friendly_tier") or "A").strip().upper()
    try:
        result = friendly_random_team_pair(
            selected_tier,
            excluded_names=[room.get("host_team"), room.get("guest_team")],
        )
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    execute_query(
        db.table("match_rooms").update({
            "host_team": result["team_a"],
            "guest_team": result["team_b"],
            "host_team_overall": result["overall_a"],
            "guest_team_overall": result["overall_b"],
            "host_team_logo_url": result.get("logo_a") or None,
            "guest_team_logo_url": result.get("logo_b") or None,
            "host_team_league": result.get("league_a") or None,
            "guest_team_league": result.get("league_b") or None,
            "note": f"Đã quay lại đội giao hữu Tier {selected_tier}.",
            "updated_at": now_iso(),
        }).eq("id", room_id).eq("status", "friendly_playing"),
        "reroll_friendly_match",
    )
    flash("Đã tự random tiếp hai CLB giao hữu.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/finish-friendly", methods=["POST"])
@login_required
def room_finish_friendly(room_id):
    if not system_feature_enabled("friendly_enabled"):
        flash("Tính năng Giao hữu đang tạm tắt.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    user = current_user()
    room = get_room(room_id)
    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("dashboard"))
    if user["id"] not in [room.get("host_user_id"), room.get("guest_user_id")] and not is_admin_user(user):
        flash("Bạn không thuộc phòng này.", "danger")
        return redirect(url_for("dashboard"))
    if room.get("status") != "friendly_playing":
        flash("Phòng không có trận giao hữu đang diễn ra.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    execute_query(
        db.table("match_rooms").update({
            "host_team": None,
            "guest_team": None,
            "host_team_overall": None,
            "guest_team_overall": None,
            "host_team_logo_url": None,
            "guest_team_logo_url": None,
            "host_team_league": None,
            "guest_team_league": None,
            "guest_ready": bool(room.get("guest_user_id")),
            "status": "waiting_ready",
            "match_id": None,
            "note": "Trận giao hữu đã kết thúc. Đang chờ Chủ Phòng quay đội tiếp theo.",
            "updated_at": now_iso(),
        }).eq("id", room_id).eq("status", "friendly_playing"),
        "finish_friendly_match",
    )
    flash("Đã kết thúc giao hữu. Không lưu lịch sử và không thay đổi RP.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/guest-unready", methods=["POST"])
@login_required
def room_guest_unready(room_id):
    user = current_user()
    room = get_room(room_id)
    if not room or user.get("id") != room.get("guest_user_id"):
        flash("Bạn không thuộc phòng đấu này.", "danger")
        return redirect(url_for("dashboard"))
    if room.get("status") != "waiting_ready":
        flash("Không thể hủy sẵn sàng ở trạng thái hiện tại.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    execute_query(
        db.table("match_rooms").update({
            "guest_ready": False,
            "note": "Khách đã hủy sẵn sàng.",
        }).eq("id", room_id).eq("status", "waiting_ready"),
        "room_guest_unready",
    )
    cache_delete("_rz_rooms_all")
    ttl_cache_delete("rooms_raw")
    flash("Đã hủy trạng thái sẵn sàng.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/guest-ready", methods=["POST"])
@login_required
def room_guest_ready(room_id):
    user = current_user()
    room = get_room(room_id)
    if not room or user.get("id") != room.get("guest_user_id"):
        flash("Bạn không thuộc phòng đấu này.", "danger")
        return redirect(url_for("dashboard"))
    if room.get("status") != "waiting_ready":
        flash("Không thể đổi trạng thái sẵn sàng lúc này.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    execute_query(
        db.table("match_rooms").update({
            "guest_ready": True,
            "note": "Khách đã sẵn sàng. Chủ phòng có thể quay đội.",
        }).eq("id", room_id).eq("status", "waiting_ready"),
        "room_guest_ready",
    )
    cache_delete("_rz_rooms_all")
    ttl_cache_delete("rooms_raw")
    flash("Bạn đã sẵn sàng.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/start", methods=["POST"])
@login_required
def room_start(room_id):
    # Giữ endpoint để tương thích với trang cũ đang được cache.
    flash("V1.10.0 đã bỏ nút Sẵn sàng và Bắt đầu trận. Chủ phòng chỉ cần quay đội.", "warning")
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/submit-result", methods=["POST"])
@login_required
def room_submit_result(room_id):
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("rooms"))

    if user["id"] != room["host_user_id"] and not is_admin_user(user):
        flash("Chỉ chủ phòng mới được nhập kết quả.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    if room["status"] != "playing":
        flash("Chỉ trận đang đá mới được nhập kết quả.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    try:
        assert_ranking_rebuild_not_running()
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    try:
        host_score = int(request.form.get("host_score", "0"))
        guest_score = int(request.form.get("guest_score", "0"))
    except (TypeError, ValueError):
        flash("Tỉ số phải là số nguyên.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    if host_score < 0 or guest_score < 0:
        flash("Tỉ số không được âm.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    match = get_match(room["match_id"])
    if not match:
        flash("Không tìm thấy match gắn với phòng.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    if host_score > guest_score:
        winner_id = room["host_user_id"]
        loser_id = room["guest_user_id"]
    elif host_score < guest_score:
        winner_id = room["guest_user_id"]
        loser_id = room["host_user_id"]
    else:
        winner_id = None
        loser_id = None

    try:
        saved_match = execute_query(
            db.table("matches").update({
                "score1": host_score,
                "score2": guest_score,
                "submitted_by_id": user["id"],
                "winner_id": winner_id,
                "loser_id": loser_id,
                "status": "waiting_confirm",
                "updated_at": now_iso(),
            }).eq("id", match["id"]).eq("status", "playing"),
            "submit_room_match_result",
        )
        if not (saved_match.data or []):
            raise ValueError("Trạng thái trận vừa thay đổi; kết quả chưa được lưu.")
        execute_query(
            db.table("match_rooms").update({
                "host_score": host_score,
                "guest_score": guest_score,
                "submitted_by_id": user["id"],
                "status": "waiting_result_confirm",
                "state_expires_at": future_iso(RESULT_CONFIRM_TIMEOUT_SECONDS),
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "playing"),
            "submit_room_result_state",
        )
        ttl_cache_delete("rooms_raw")
    except ValueError as exc:
        print(f"room_submit_result validation room={room_id} match={match.get('id')}: {exc}")
        flash(str(exc), "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    except Exception as exc:
        print(f"room_submit_result ERROR room={room_id} match={match.get('id')}: {type(exc).__name__}: {exc}")
        flash("Không thể lưu kết quả do lỗi dữ liệu/kết nối. Vui lòng thử lại; chưa cộng hoặc trừ RP.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    flash("Đã nhập kết quả. Đang chờ người được mời xác nhận.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/confirm-result", methods=["POST"])
@login_required
def room_confirm_result(room_id):
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("rooms"))

    if user["id"] != room["guest_user_id"] and not is_admin_user(user):
        flash("Chỉ người được mời mới được xác nhận kết quả.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    if room["status"] != "waiting_result_confirm":
        flash("Phòng chưa có kết quả cần xác nhận.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    match = get_match(room["match_id"])
    if not match:
        flash("Không tìm thấy trận.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    try:
        users_before_streak_event = users_map()
        delta1, delta2 = apply_match_result(match)
        streak_event = build_win_streak_event(match, room, users_before_streak_event)
        execute_query(
            db.table("match_rooms").update({
                "status": "confirmed",
                "confirmed_by_id": user["id"],
                "note": encode_win_streak_room_note(streak_event),
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "waiting_result_confirm"),
            "confirm_result_room",
        )
        if streak_event:
            publish_global_streak_event(streak_event)
    except ValueError as exc:
        print(f"room_confirm_result validation room={room_id} match={match.get('id')}: {exc}")
        flash(str(exc), "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    except Exception as exc:
        print(f"room_confirm_result ERROR room={room_id} match={match.get('id')}: {type(exc).__name__}: {exc}")
        flash("Không thể xác nhận kết quả do lỗi kết nối dữ liệu. Điểm chưa được xử lý thêm; vui lòng thử lại sau vài giây.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/dispute-result", methods=["POST"])
@login_required
def room_dispute_result(room_id):
    user = current_user()
    room = get_room(room_id)

    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect(url_for("rooms"))

    if user["id"] != room["guest_user_id"]:
        flash("Chỉ người được mời mới được báo tranh chấp.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    if room["status"] != "waiting_result_confirm":
        flash("Phòng chưa có kết quả cần xác nhận.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    try:
        assert_ranking_rebuild_not_running()
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    reason_code = request.form.get("reason_code", "").strip()
    details = request.form.get("details", "").strip()[:500]
    if reason_code not in {"wrong_score", "wrong_winner", "interrupted", "unilateral_entry", "other"}:
        flash("Hãy chọn lý do tranh chấp hợp lệ.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))
    if reason_code == "other" and not details:
        flash("Hãy nhập ghi chú cho lý do khác.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    evidence_path = None
    evidence_file = request.files.get("evidence")
    if evidence_file and getattr(evidence_file, "filename", ""):
        try:
            evidence_bytes = prepare_dispute_evidence_bytes(evidence_file)
            evidence_path = upload_dispute_evidence(room.get("match_id"), user.get("id"), evidence_bytes)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("room_detail", room_id=room_id))
        except Exception as exc:
            print(f"room_dispute_evidence upload error: {exc}")
            flash("Không thể tải ảnh bằng chứng lúc này. Vui lòng thử lại hoặc gửi tranh chấp không kèm ảnh.", "danger")
            return redirect(url_for("room_detail", room_id=room_id))

    reason_label = dispute_reason_label(reason_code)
    note = f"{user.get('display_name', 'Khách')} không đồng ý kết quả: {reason_label}."
    try:
        execute_query(
            db.table("match_rooms").update({
                "status": "disputed",
                "note": note,
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id),
            "room_dispute_update",
        )

        if room.get("match_id"):
            execute_query(
                db.table("matches").update({
                    "status": "disputed",
                    "note": note,
                    "updated_at": now_iso(),
                }).eq("id", room["match_id"]),
                "match_dispute_update",
            )

        dispute = create_or_update_match_dispute(
            room,
            user["id"],
            reason_code,
            details,
            "player",
            evidence_path=evidence_path,
        )
    except Exception as exc:
        if evidence_path:
            remove_dispute_evidence_object(evidence_path)
        try:
            execute_query(
                db.table("match_rooms").update({
                    "status": "waiting_result_confirm",
                    "state_expires_at": future_iso(RESULT_CONFIRM_TIMEOUT_SECONDS),
                    "updated_at": now_iso(),
                }).eq("id", room_id),
                "rollback_room_dispute",
                attempts=1,
            )
            if room.get("match_id"):
                execute_query(
                    db.table("matches").update({
                        "status": "waiting_confirm",
                        "updated_at": now_iso(),
                    }).eq("id", room.get("match_id")),
                    "rollback_match_dispute",
                    attempts=1,
                )
        except Exception as rollback_exc:
            print(f"room_dispute rollback warning: {rollback_exc}")
        print(f"room_dispute create error: {exc}")
        flash("Không thể gửi tranh chấp lúc này. Vui lòng thử lại sau vài giây.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))
    notify_admins(
        "⚠️ Có tranh chấp kết quả mới",
        f"{room.get('host_name')} {room.get('host_score')} - {room.get('guest_score')} {room.get('guest_name')} • {reason_label}",
    )
    create_user_notification(
        room.get("host_user_id"),
        "⚠️ Đối thủ đã mở tranh chấp",
        f"{room.get('guest_name')} không đồng ý kết quả. Lý do: {reason_label}.",
        f"/room/{room_id}",
        "dispute",
    )

    flash("Đã gửi tranh chấp. Trận chưa được tính điểm và cả hai có thể về sảnh trong khi Admin xử lý.", "warning")
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/withdraw-dispute", methods=["POST"])
@login_required
def room_withdraw_dispute(room_id):
    user = current_user()
    room = get_room(room_id)
    if not room or room.get("status") != "disputed":
        flash("Phòng không còn tranh chấp cần rút.", "warning")
        return redirect(url_for("dashboard"))

    dispute = get_match_dispute_by_match(room.get("match_id"), DISPUTE_PENDING_STATUSES)
    if not dispute or dispute.get("raised_by_id") != user.get("id"):
        flash("Chỉ người đã gửi tranh chấp mới có thể rút tranh chấp.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    try:
        resolve_match_dispute_with_result(
            dispute,
            room.get("host_score"),
            room.get("guest_score"),
            user.get("id"),
            "accepted_by_player",
            "Người gửi đã rút tranh chấp và chấp nhận kết quả ban đầu.",
            final_dispute_status="withdrawn",
        )
    except Exception as exc:
        flash(f"Không thể rút tranh chấp: {exc}", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    flash("Đã rút tranh chấp và chấp nhận kết quả. Điểm rank đã được cập nhật.", "success")
    return redirect(url_for("room_detail", room_id=room_id))


# =========================
# Legacy / history routes
# =========================
@app.route("/matches")
@login_required
def matches():
    user = current_user()
    history_view = (request.args.get("view") or "mine").strip()
    status_filter = (request.args.get("status") or "all").strip()
    query = (request.args.get("q") or "").strip().casefold()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 20

    rows = list_matches()
    if history_view != "all":
        history_view = "mine"
        rows = [
            match for match in rows
            if user.get("id") in {match.get("player1_id"), match.get("player2_id")}
        ]

    if status_filter != "all":
        rows = [match for match in rows if match.get("status") == status_filter]

    if query:
        rows = [
            match for match in rows
            if query in " ".join([
                str(match.get("player1_name") or ""),
                str(match.get("player2_name") or ""),
                str(match.get("team1") or ""),
                str(match.get("team2") or ""),
            ]).casefold()
        ]

    total_items = len(rows)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    page_rows = [decorate_match_for_view(match, user.get("id")) for match in rows[start:start + per_page]]

    return render_template(
        "matches.html",
        matches=page_rows,
        history_view=history_view,
        status_filter=status_filter,
        q=request.args.get("q", ""),
        page=page,
        total_pages=total_pages,
        total_items=total_items,
    )



@app.route("/submit-result")
@login_required
def submit_result():
    flash("Từ V1.2, kết quả được nhập trong Phòng đấu.", "warning")
    return redirect(url_for("rooms"))


@app.route("/confirm-result")
@login_required
def confirm_result():
    flash("Từ V1.2, kết quả được xác nhận trong Phòng đấu.", "warning")
    return redirect(url_for("rooms"))


def _safe_int(value, default=0):
    """Convert Supabase/form numeric values to a real integer safely."""
    try:
        return int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return int(default)


def _load_ranking_rebuild_lock(allow_failure=False):
    if db is None:
        return None
    try:
        result = execute_query(
            db.table("system_settings").select("setting_value")
            .eq("setting_key", RANKING_REBUILD_LOCK_KEY).limit(1),
            "load_ranking_rebuild_lock",
            attempts=1,
        )
        row = (result.data or [None])[0]
        value = (row or {}).get("setting_value")
        return dict(value) if isinstance(value, dict) else None
    except Exception as exc:
        app.logger.warning("load ranking rebuild lock failed: %s", exc)
        if allow_failure:
            return None
        raise


def _ranking_rebuild_lock_is_expired(lock_info):
    if not lock_info:
        return True
    expires_at = aware_utc(parse_dt(lock_info.get("expires_at")))
    return not expires_at or expires_at <= aware_utc(now_dt())


def get_active_ranking_rebuild_lock(clean_stale=True):
    lock_info = _load_ranking_rebuild_lock()
    if not lock_info:
        return None
    if _ranking_rebuild_lock_is_expired(lock_info):
        if clean_stale:
            try:
                db.table("system_settings").delete().eq(
                    "setting_key", RANKING_REBUILD_LOCK_KEY
                ).execute()
            except Exception as exc:
                app.logger.warning("cleanup stale ranking lock failed: %s", exc)
        return None
    return lock_info


def assert_ranking_rebuild_not_running():
    lock_info = get_active_ranking_rebuild_lock()
    if lock_info:
        raise ValueError(
            "Admin đang tính lại lịch sử BXH. Vui lòng thử lại sau khi thao tác hoàn tất."
        )


def acquire_ranking_rebuild_lock(actor_id=None, match_id=None):
    """Giành khóa DB duy nhất trước khi sửa lịch sử/RP.

    Dùng INSERT vào setting_key duy nhất thay vì khóa RAM, vì Vercel có thể chạy
    nhiều instance cùng lúc. Khóa hết hạn tự động để tránh kẹt khi request bị dừng.
    """
    require_db()
    existing = get_active_ranking_rebuild_lock()
    if existing:
        raise ValueError("Một thao tác tính lại BXH khác đang chạy. Vui lòng thử lại sau.")

    token = secrets.token_hex(16)
    payload = {
        "token": token,
        "actor_id": actor_id,
        "match_id": match_id,
        "created_at": now_iso(),
        "expires_at": future_iso(RANKING_REBUILD_LOCK_SECONDS),
    }
    try:
        db.table("system_settings").insert({
            "setting_key": RANKING_REBUILD_LOCK_KEY,
            "setting_value": payload,
            "updated_at": now_iso(),
        }).execute()
    except Exception as exc:
        # Có thể instance khác vừa chèn khóa sau lần đọc phía trên.
        active = get_active_ranking_rebuild_lock(clean_stale=False)
        if active:
            raise ValueError("Một thao tác tính lại BXH khác đang chạy. Vui lòng thử lại sau.") from exc
        raise

    try:
        verified = get_active_ranking_rebuild_lock(clean_stale=False)
        if not verified or verified.get("token") != token:
            raise ValueError("Không thể giành khóa tính lại BXH an toàn.")

        # Nếu một request xác nhận đã claim trận trước khi khóa được tạo, không phát lại
        # song song. Request xác nhận sẽ tự trả trạng thái về; Admin chỉ cần thử lại.
        processing = execute_query(
            db.table("matches").select("id").eq("status", "processing_result").limit(1),
            "check_processing_result_before_rebuild",
            attempts=1,
        )
        if processing.data:
            raise ValueError("Có kết quả trận đang được xác nhận. Vui lòng thử lại sau vài giây.")
        return token
    except Exception:
        release_ranking_rebuild_lock(token)
        raise


def release_ranking_rebuild_lock(token):
    if not token or db is None:
        return
    try:
        active = _load_ranking_rebuild_lock(allow_failure=True)
        if active and active.get("token") == token:
            db.table("system_settings").delete().eq(
                "setting_key", RANKING_REBUILD_LOCK_KEY
            ).execute()
    except Exception as exc:
        app.logger.warning("release ranking rebuild lock failed: %s", exc)


def _require_owned_ranking_rebuild_lock(token):
    active = get_active_ranking_rebuild_lock(clean_stale=False)
    if not active or active.get("token") != token:
        raise ValueError("Khóa tính lại BXH đã mất hoặc hết hạn; chưa lưu thay đổi.")


def _match_state_signature(match):
    return (
        str((match or {}).get("status") or ""),
        (match or {}).get("score1"),
        (match or {}).get("score2"),
        str((match or {}).get("updated_at") or ""),
    )


def _payload_differs(current, payload):
    for key, value in dict(payload or {}).items():
        if key in {"created_at", "updated_at"}:
            continue
        if (current or {}).get(key) != value:
            return True
    return False


def _room_status_from_match_status(status):
    return {
        "playing": "playing",
        "waiting_confirm": "waiting_result_confirm",
        "disputed": "disputed",
        "confirmed": "confirmed",
        "cancelled": "cancelled",
    }.get(str(status or ""), str(status or ""))


def sync_room_after_admin_match_change(match, target, actor_id=None):
    """Đồng bộ đúng cột host_score/guest_score mà không sửa created_at."""
    if not match or not match.get("id"):
        return
    result = execute_query(
        db.table("match_rooms").select(
            "id,match_id,host_user_id,guest_user_id,status,host_score,guest_score,note,confirmed_by_id,state_expires_at"
        ).eq("match_id", match.get("id")).limit(1),
        "load_room_for_admin_match_sync",
        attempts=2,
    )
    room = (result.data or [None])[0]
    if not room:
        return

    status = str(target.get("status", match.get("status")) or "")
    score1 = target.get("score1", match.get("score1"))
    score2 = target.get("score2", match.get("score2"))
    p1_id = str(match.get("player1_id") or "")
    p2_id = str(match.get("player2_id") or "")
    host_id = str(room.get("host_user_id") or "")
    if host_id == p2_id:
        host_score, guest_score = score2, score1
    else:
        # Mặc định cấu trúc hiện hành: player1 là chủ phòng.
        host_score, guest_score = score1, score2

    room_payload = {
        "host_score": host_score,
        "guest_score": guest_score,
        "status": _room_status_from_match_status(status),
        "note": target.get("note", match.get("note")),
        "updated_at": now_iso(),
    }
    if status == "confirmed":
        room_payload["confirmed_by_id"] = target.get("confirmed_by_id") or actor_id
        room_payload["state_expires_at"] = None
    elif status == "waiting_confirm":
        room_payload["confirmed_by_id"] = None
        room_payload["state_expires_at"] = future_iso(RESULT_CONFIRM_TIMEOUT_SECONDS)
    elif status == "playing":
        room_payload["confirmed_by_id"] = None
        room_payload["state_expires_at"] = future_iso(ROOM_MATCH_INACTIVITY_TIMEOUT_SECONDS)
    else:
        room_payload["confirmed_by_id"] = None
        room_payload["state_expires_at"] = None

    execute_query(
        db.table("match_rooms").update(room_payload).eq("id", room.get("id")),
        "sync_room_after_admin_match_change",
        attempts=2,
    )


def apply_match_result(match):
    """Apply one ranked result exactly once with clear validation and recovery.

    The match row is claimed by changing its status to ``processing_result``.
    A repeated click cannot apply RP twice, even when requests overlap.
    """
    if not match or not match.get("id"):
        raise ValueError("Thiếu dữ liệu trận đấu.")
    # Không cho request người chơi ghi RP trong lúc Admin đang phát lại lịch sử.
    # Trận confirmed đã có delta vẫn được trả idempotent phía dưới.
    if match.get("status") != "confirmed":
        assert_ranking_rebuild_not_running()
    if match.get("score1") is None or match.get("score2") is None:
        raise ValueError("Trận chưa có tỉ số.")

    # Idempotency: a confirmed match with stored deltas was already applied.
    if match.get("status") == "confirmed" and match.get("delta1") is not None and match.get("delta2") is not None:
        return _safe_int(match.get("delta1")), _safe_int(match.get("delta2"))
    if match.get("status") == "processing_result":
        raise ValueError("Kết quả đang được xử lý. Không cần nhấn xác nhận lần nữa.")

    player1_id = match.get("player1_id")
    player2_id = match.get("player2_id")
    if not player1_id or not player2_id:
        raise ValueError("Trận đấu thiếu ID của một trong hai người chơi.")

    player1 = get_user(player1_id)
    player2 = get_user(player2_id)
    if not player1 or not player2:
        missing = []
        if not player1:
            missing.append("người chơi 1")
        if not player2:
            missing.append("người chơi 2")
        raise ValueError("Không tìm thấy dữ liệu " + " và ".join(missing) + ". Chưa cập nhật RP.")

    score1 = _safe_int(match.get("score1"), -1)
    score2 = _safe_int(match.get("score2"), -1)
    if score1 < 0 or score2 < 0:
        raise ValueError("Tỉ số không hợp lệ.")

    original_status = str(match.get("status") or "waiting_confirm")
    try:
        claim = execute_query(
            db.table("matches").update({
                "status": "processing_result",
                "updated_at": now_iso(),
            }).eq("id", match["id"]).eq("status", original_status),
            "claim_match_result",
        )
        if not (claim.data or []):
            fresh = get_match(match["id"])
            if fresh and fresh.get("status") == "confirmed":
                return _safe_int(fresh.get("delta1")), _safe_int(fresh.get("delta2"))
            raise ValueError("Kết quả đã được một yêu cầu khác xử lý hoặc trạng thái trận đã thay đổi.")

        # Đóng khe race: Admin có thể tạo khóa sau lần kiểm tra đầu nhưng trước khi
        # request này claim được dòng trận. Khi đó trả status về và dừng trước khi ghi RP.
        assert_ranking_rebuild_not_running()

        delta1, delta2 = calculate_deltas(
            player1, player2, score1, score2,
            match.get("team1"), match.get("team2"),
            match.get("team1_overall"), match.get("team2_overall"),
            match.get("team1_tier"), match.get("team2_tier"),
            rng=random.Random(f"{RP_RANDOM_SEED_NAMESPACE}|{match.get('id')}"),
        )
        delta1, delta2 = _safe_int(delta1), _safe_int(delta2)
        # Không còn fallback -20. Nếu engine trả delta sai dấu/0 cho trận thắng-thua,
        # dừng xử lý và ghi lỗi thay vì âm thầm che lỗi bằng một giá trị hợp lệ giả.
        delta1, delta2 = validate_ranked_deltas(score1, score2, delta1, delta2)

        # The 0.95 coefficient belongs to the actual room host, not implicitly player1.
        host_user_id = match.get("host_user_id")
        if not host_user_id:
            try:
                room_row = execute_query(
                    db.table("match_rooms").select("host_user_id").eq("match_id", match["id"]).limit(1),
                    "get_result_host",
                    attempts=2,
                )
                host_user_id = (room_row.data or [{}])[0].get("host_user_id")
            except Exception as exc:
                print(f"get_result_host warning match={match.get('id')}: {type(exc).__name__}: {exc}")
        if str(host_user_id or "") == str(player1_id) and score1 > score2:
            delta1 = _safe_int(apply_host_xp_factor(delta1, match.get("host_xp_factor", HOST_WIN_FACTOR)))
            if _safe_int(player1.get("total_matches")) < PLACEMENT_MATCHES:
                delta1 = max(22, min(29, delta1))
        elif str(host_user_id or "") == str(player2_id) and score2 > score1:
            delta2 = _safe_int(apply_host_xp_factor(delta2, match.get("host_xp_factor", HOST_WIN_FACTOR)))
            if _safe_int(player2.get("total_matches")) < PLACEMENT_MATCHES:
                delta2 = max(22, min(29, delta2))

        update_player_after_match(player1, delta1, score1, score2)
        update_player_after_match(player2, delta2, score2, score1)

        execute_query(
            db.table("matches").update({
                "delta1": int(delta1),
                "delta2": int(delta2),
                "rp_formula_version": RP_FORMULA_VERSION,
                "rp_details": {
                    "source": "modules/rp_formula.py",
                    "formula": formula_summary(),
                    "seed": f"{RP_RANDOM_SEED_NAMESPACE}|{match.get('id')}",
                    "delta1": int(delta1),
                    "delta2": int(delta2),
                },
                "status": "confirmed",
                "note": "Đã xác nhận.",
                "updated_at": now_iso(),
            }).eq("id", match["id"]).eq("status", "processing_result"),
            "finalize_match_result",
        )
    except Exception as exc:
        print(f"apply_match_result ERROR match={match.get('id')} status={original_status}: {type(exc).__name__}: {exc}")
        try:
            execute_query(
                db.table("matches").update({"status": original_status, "updated_at": now_iso()})
                .eq("id", match["id"]).eq("status", "processing_result"),
                "restore_match_after_result_error",
                attempts=2,
            )
        except Exception as restore_exc:
            print(f"apply_match_result RESTORE ERROR match={match.get('id')}: {type(restore_exc).__name__}: {restore_exc}")
        raise

    # Badge synchronization is auxiliary and must never invalidate a confirmed match.
    try:
        sync_achievements_for_users([player1_id, player2_id])
    except Exception as exc:
        print(f"achievement_sync warning match={match.get('id')}: {type(exc).__name__}: {exc}")
    return int(delta1), int(delta2)


def resolve_match_dispute_with_result(
    dispute,
    score1,
    score2,
    resolved_by_id,
    resolution_type,
    resolution_note="",
    final_dispute_status="resolved",
):
    if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
        raise ValueError("Tranh chấp này đã được xử lý hoặc không còn hiệu lực.")

    score1 = parse_score(score1)
    score2 = parse_score(score2)
    if score1 is None or score2 is None:
        raise ValueError("Trận được công nhận phải có đủ hai tỷ số.")

    match_id = dispute.get("match_id")
    lock_token = acquire_ranking_rebuild_lock(resolved_by_id, match_id)
    try:
        match = get_match(match_id)
        if not match or match.get("status") != "disputed":
            raise ValueError("Trận đấu không còn ở trạng thái tranh chấp.")

        final_note = (
            resolution_note or "Tranh chấp đã được xử lý và kết quả được công nhận."
        ).strip()[:500]
        override = {
            "score1": score1,
            "score2": score2,
            "status": "confirmed",
            "confirmed_by_id": resolved_by_id,
            "note": final_note,
        }
        rebuild_rankings_after_admin_change(
            match_id, override, lock_token=lock_token, actor_id=resolved_by_id
        )

        execute_query(
            db.table("match_disputes").update({
                "status": final_dispute_status,
                "resolution_type": resolution_type,
                "resolution_score1": score1,
                "resolution_score2": score2,
                "resolution_note": final_note,
                "resolved_by_id": resolved_by_id,
                "resolved_at": now_iso(),
                "updated_at": now_iso(),
            }).eq("id", dispute.get("id")).in_("status", list(DISPUTE_PENDING_STATUSES)),
            "finish_match_dispute_chronologically",
        )

        resolved_match = get_match(match_id) or {}
        delta1 = _safe_int(resolved_match.get("delta1"))
        delta2 = _safe_int(resolved_match.get("delta2"))
        users = users_map()
        p1_name = users.get(match.get("player1_id"), {}).get("display_name", "Player 1")
        p2_name = users.get(match.get("player2_id"), {}).get("display_name", "Player 2")
        create_notifications_for_users(
            [match.get("player1_id"), match.get("player2_id")],
            "✅ Tranh chấp đã được xử lý",
            f"Trận {p1_name} {score1} - {score2} {p2_name}: {final_note}",
            f"/room/{dispute.get('room_id')}",
            "dispute_resolved",
        )
        return delta1, delta2
    finally:
        release_ranking_rebuild_lock(lock_token)


def cancel_match_dispute(dispute, resolved_by_id, resolution_note=""):
    if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
        raise ValueError("Tranh chấp này đã được xử lý hoặc không còn hiệu lực.")

    match = get_match(dispute.get("match_id"))
    if not match or match.get("status") != "disputed":
        raise ValueError("Trận đấu không còn ở trạng thái tranh chấp.")

    final_note = (resolution_note or "Admin đã hủy trận tranh chấp; không cộng hoặc trừ điểm.").strip()[:500]
    execute_query(
        db.table("matches").update({
            "status": "cancelled",
            "note": final_note,
            "updated_at": now_iso(),
        }).eq("id", match.get("id")),
        "cancel_disputed_match",
    )
    execute_query(
        db.table("match_rooms").update({
            "status": "cancelled",
            "note": final_note,
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).eq("id", dispute.get("room_id")),
        "cancel_disputed_room",
    )
    execute_query(
        db.table("match_disputes").update({
            "status": "resolved",
            "resolution_type": "cancelled",
            "resolution_note": final_note,
            "resolved_by_id": resolved_by_id,
            "resolved_at": now_iso(),
            "updated_at": now_iso(),
        }).eq("id", dispute.get("id")),
        "cancel_match_dispute",
    )

    users = users_map()
    p1_name = users.get(match.get("player1_id"), {}).get("display_name", "Player 1")
    p2_name = users.get(match.get("player2_id"), {}).get("display_name", "Player 2")
    create_notifications_for_users(
        [match.get("player1_id"), match.get("player2_id")],
        "🚫 Trận tranh chấp đã bị hủy",
        f"Trận giữa {p1_name} và {p2_name} đã được Admin hủy. Không ai bị cộng hoặc trừ điểm.",
        "/matches",
        "dispute_cancelled",
    )


def update_player_after_match(player, delta, goals_for, goals_against):
    win = 1 if goals_for > goals_against else 0
    draw = 1 if goals_for == goals_against else 0
    loss = 1 if goals_for < goals_against else 0

    delta = _safe_int(delta)
    goals_for = _safe_int(goals_for)
    goals_against = _safe_int(goals_against)
    new_points = max(0, _safe_int(player.get("rank_points")) + delta)
    current_streak = int(player.get("streak", 0) or 0)
    new_streak = current_streak + 1 if win else 0 if loss else current_streak

    execute_query(
        db.table("users").update({
            "rank_points": new_points,
            "total_matches": _safe_int(player.get("total_matches")) + 1,
            "wins": _safe_int(player.get("wins")) + win,
            "draws": _safe_int(player.get("draws")) + draw,
            "losses": _safe_int(player.get("losses")) + loss,
            "goals_for": _safe_int(player.get("goals_for")) + goals_for,
            "goals_against": _safe_int(player.get("goals_against")) + goals_against,
            "streak": new_streak,
        }).eq("id", player["id"]),
        f"update_player_after_match:{player.get('id')}",
    )
    ttl_cache_delete("players_raw", "achievement_map")




def reverse_player_match_stats(player, delta, goals_for, goals_against):
    """Hoàn tác đúng một trận đã áp dụng, không đụng tới dữ liệu người chơi khác."""
    if not player:
        return

    win = 1 if goals_for > goals_against else 0
    draw = 1 if goals_for == goals_against else 0
    loss = 1 if goals_for < goals_against else 0

    db.table("users").update({
        "rank_points": max(0, int(player.get("rank_points", 0) or 0) - int(delta or 0)),
        "total_matches": max(0, int(player.get("total_matches", 0) or 0) - 1),
        "wins": max(0, int(player.get("wins", 0) or 0) - win),
        "draws": max(0, int(player.get("draws", 0) or 0) - draw),
        "losses": max(0, int(player.get("losses", 0) or 0) - loss),
        "goals_for": max(0, int(player.get("goals_for", 0) or 0) - int(goals_for or 0)),
        "goals_against": max(0, int(player.get("goals_against", 0) or 0) - int(goals_against or 0)),
        # Không thể suy ngược chính xác chuỗi thắng lịch sử nếu có trận mới hơn.
        # Đặt về 0 để tránh giữ chuỗi thắng sai sau khi Admin sửa/xóa trận.
        "streak": 0,
    }).eq("id", player["id"]).execute()


def reverse_confirmed_match_result(match):
    """Hoàn tác một trận confirmed bằng delta đã lưu, không reset toàn bộ BXH."""
    if not match or match.get("status") != "confirmed":
        return False
    if match.get("score1") is None or match.get("score2") is None:
        return False

    player1 = get_user(match.get("player1_id"))
    player2 = get_user(match.get("player2_id"))
    if not player1 or not player2:
        return False

    score1 = int(match.get("score1") or 0)
    score2 = int(match.get("score2") or 0)
    reverse_player_match_stats(player1, int(match.get("delta1", 0) or 0), score1, score2)
    reverse_player_match_stats(player2, int(match.get("delta2", 0) or 0), score2, score1)
    return True



def rebuild_rankings_after_admin_change(
    match_id, override_payload, *, lock_token, actor_id=None
):
    """Phát lại toàn bộ lịch sử confirmed theo ``created_at`` gốc.

    - Không ghi ``created_at`` vào bất kỳ payload nào.
    - Giữ lại RP/thống kê gốc không sinh ra từ bảng matches.
    - Có rollback best-effort nếu một cập nhật giữa chừng thất bại.
    """
    require_db()
    _require_owned_ranking_rebuild_lock(lock_token)

    users_result = execute_query(
        db.table("users").select(
            "id,rank_points,total_matches,wins,draws,losses,goals_for,goals_against,streak,loss_streak"
        ),
        "admin_rebuild_load_users",
    )
    matches_result = execute_query(
        db.table("matches").select("*").order("created_at", desc=False),
        "admin_rebuild_load_matches",
    )
    rooms_result = execute_query(
        db.table("match_rooms").select("match_id,host_user_id"),
        "admin_rebuild_load_hosts",
        attempts=2,
    )
    users_rows = [dict(row) for row in (users_result.data or [])]
    matches_rows = [dict(row) for row in (matches_result.data or [])]
    user_original = {str(row.get("id")): row for row in users_rows if row.get("id")}
    match_original = {str(row.get("id")): row for row in matches_rows if row.get("id")}
    host_by_match = {
        str(row.get("match_id")): row.get("host_user_id")
        for row in (rooms_result.data or []) if row.get("match_id")
    }

    override = {key: value for key, value in dict(override_payload or {}).items() if key != "created_at"}
    user_updates, match_updates = build_replay_plan(
        users=users_rows,
        matches=matches_rows,
        overrides={str(match_id): override},
        calculate_deltas=calculate_ranked_deltas,
        get_rank_level=get_rank_level,
        apply_host_factor=apply_host_xp_factor,
        host_by_match=host_by_match,
        default_points=DEFAULT_POINTS,
        placement_matches=PLACEMENT_MATCHES,
        host_win_factor=HOST_WIN_FACTOR,
        formula_version=RP_FORMULA_VERSION,
        formula_summary=formula_summary,
        seed_namespace=RP_RANDOM_SEED_NAMESPACE,
    )

    changed_matches = {
        current_id: dict(payload)
        for current_id, payload in match_updates.items()
        if _payload_differs(match_original.get(str(current_id)), payload)
    }
    changed_users = {
        user_id: dict(payload)
        for user_id, payload in user_updates.items()
        if _payload_differs(user_original.get(str(user_id)), payload)
    }

    applied_matches = []
    applied_users = []
    try:
        _require_owned_ranking_rebuild_lock(lock_token)
        for current_match_id, payload in changed_matches.items():
            safe_payload = {key: value for key, value in payload.items() if key != "created_at"}
            safe_payload["updated_at"] = now_iso()
            result = execute_query(
                db.table("matches").update(safe_payload).eq("id", current_match_id),
                f"admin_rebuild_match:{current_match_id}",
            )
            if not (result.data or []):
                raise RuntimeError(f"Không cập nhật được trận {current_match_id}.")
            applied_matches.append(str(current_match_id))

        _require_owned_ranking_rebuild_lock(lock_token)
        for user_id, payload in changed_users.items():
            result = execute_query(
                db.table("users").update(payload).eq("id", user_id),
                f"admin_rebuild_user:{user_id}",
            )
            if not (result.data or []):
                raise RuntimeError(f"Không cập nhật được người chơi {user_id}.")
            applied_users.append(str(user_id))

        target_match = dict(match_original.get(str(match_id)) or get_match(match_id) or {})
        target_match.update(override)
        sync_room_after_admin_match_change(
            match_original.get(str(match_id)) or target_match,
            target_match,
            actor_id=actor_id,
        )
    except Exception:
        # Rollback best-effort. Không bao giờ phục hồi/ghi created_at vì nó chưa bị sửa.
        for user_id in reversed(applied_users):
            original = user_original.get(user_id) or {}
            restore = {
                key: original.get(key)
                for key in (
                    "rank_points", "total_matches", "wins", "draws", "losses",
                    "goals_for", "goals_against", "streak", "loss_streak"
                )
            }
            try:
                db.table("users").update(restore).eq("id", user_id).execute()
            except Exception as rollback_exc:
                app.logger.exception("rollback user %s failed: %s", user_id, rollback_exc)
        for current_match_id in reversed(applied_matches):
            original = match_original.get(current_match_id) or {}
            restore = {
                key: original.get(key)
                for key in (
                    "score1", "score2", "status", "note", "delta1", "delta2",
                    "winner_id", "loser_id", "confirmed_by_id",
                    "rp_formula_version", "rp_details", "updated_at"
                )
            }
            try:
                db.table("matches").update(restore).eq("id", current_match_id).execute()
            except Exception as rollback_exc:
                app.logger.exception("rollback match %s failed: %s", current_match_id, rollback_exc)
        raise

    cache_delete("_rz_players_all", "_rz_users_map", "_rz_matches_all", "_rz_rooms_all")
    ttl_cache_delete("players_raw", "achievement_map", "rooms_raw")
    try:
        sync_achievements_for_users(list(user_updates.keys()))
    except Exception as exc:
        app.logger.warning("admin rebuild achievement warning: %s", exc)
    return len(changed_matches), len(changed_users)


def remove_match_dispute_evidence(match_id):
    if not match_id or db is None:
        return
    try:
        result = execute_query(
            db.table("match_disputes").select("evidence_path").eq("match_id", match_id),
            "list_match_evidence_for_cleanup",
            attempts=2,
        )
        for row in result.data or []:
            remove_dispute_evidence_object(row.get("evidence_path"))
    except Exception as exc:
        print(f"remove_match_dispute_evidence warning: {exc}")


def delete_room_safe(room_id):
    room = get_room(room_id)
    if not room:
        return

    if room.get("match_id"):
        delete_match_safe(room.get("match_id"))

    db.table("chat_messages").delete().eq("room_id", room_id).execute()
    db.table("match_rooms").delete().eq("id", room_id).execute()


def delete_match_safe(match_id):
    match = get_match(match_id)
    if match:
        reverse_confirmed_match_result(match)

    remove_match_dispute_evidence(match_id)
    db.table("match_rooms").update({
        "status": "cancelled",
        "match_id": None,
        "note": "Admin đã xóa trận liên kết.",
        "updated_at": now_iso(),
    }).eq("match_id", match_id).execute()

    db.table("matches").delete().eq("id", match_id).execute()


def delete_player_safe(user_id):
    user = get_user(user_id)
    if not user:
        return False, "Không tìm thấy tài khoản."

    if is_admin_user(user):
        return False, "Không được xóa tài khoản admin chính."

    for room in list_rooms():
        if user_id in [room.get("host_user_id"), room.get("guest_user_id")]:
            delete_room_safe(room["id"])

    for match in list_matches():
        if user_id in [match.get("player1_id"), match.get("player2_id")]:
            delete_match_safe(match["id"])

    for invite in list_invites():
        if user_id in [invite.get("from_user_id"), invite.get("to_user_id")]:
            db.table("match_invites").delete().eq("id", invite["id"]).execute()

    db.table("chat_messages").delete().eq("user_id", user_id).execute()
    db.table("user_devices").delete().eq("user_id", user_id).execute()
    db.table("users").delete().eq("id", user_id).execute()
    return True, ""



@app.context_processor
def inject_admin_feature_context():
    user = current_user()
    return {
        "app_name": APP_NAME, "app_version": APP_VERSION,
        "system_features": get_system_features(),
        "can_admin": lambda code: has_admin_permission(user, code),
        "admin_display_role": "Admin" if is_admin_user(user) else "",
        "is_test_mode": is_test_mode(),
        "simple_test_passwords_enabled": simple_test_passwords_enabled(),
        "minimum_password_length": minimum_password_length(),
        "maintenance_status": get_maintenance_status(),
    }

@app.route("/admin/system/maintenance", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("system_features_manage")
def admin_update_maintenance():
    close_at = _normalize_maintenance_input(request.form.get("close_at"))
    open_at = _normalize_maintenance_input(request.form.get("open_at"))
    close_dt = _parse_maintenance_time(close_at)
    open_dt = _parse_maintenance_time(open_at)
    if close_dt and open_dt and open_dt <= close_dt:
        flash("Thời gian mở máy chủ phải sau thời gian đóng máy chủ.", "danger")
        return redirect_admin("system")

    config = {
        "manual_closed": request.form.get("manual_closed") == "1",
        "close_at": close_at,
        "open_at": open_at,
        "message": (request.form.get("message") or "").strip()[:500]
            or _maintenance_default_config()["message"],
        "updated_at": now_iso(),
    }
    execute_query(
        db.table("system_settings").upsert({
            "setting_key": MAINTENANCE_SETTING_KEY,
            "setting_value": config,
            "updated_at": now_iso(),
        }, on_conflict="setting_key"),
        "update_server_maintenance_config",
        attempts=2,
    )
    _maintenance_cache["value"] = dict(config)
    _maintenance_cache["expires_at"] = time.time() + 15
    log_admin_action("Cập nhật trạng thái bảo trì máy chủ", "system", details=config)
    flash("Đã lưu trạng thái và lịch bảo trì máy chủ.", "success")
    return redirect_admin("system")


@app.route("/admin/system/features", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("system_features_manage")
def admin_update_system_features():
    previous_features = get_system_features()
    features = {key: request.form.get(key) == "1" for key in SYSTEM_FEATURE_DEFAULTS}
    execute_query(
        db.table("system_settings").upsert(
            {
                "setting_key": "admin_system_features",
                "setting_value": features,
                "updated_at": now_iso(),
            },
            on_conflict="setting_key",
        ),
        "update_system_features",
    )

    # Khi Admin vừa tắt Giao hữu, đưa các phòng giao hữu đang mở về trạng thái
    # chờ sẵn sàng để người chơi không bị kẹt trong một tính năng đã khóa.
    if previous_features.get("friendly_enabled", True) and not features.get("friendly_enabled", False):
        execute_query(
            db.table("match_rooms").update({
                "status": "waiting_ready",
                "match_mode": "ranked",
                "host_team": None,
                "guest_team": None,
                "host_team_overall": None,
                "guest_team_overall": None,
                "host_team_logo_url": None,
                "guest_team_logo_url": None,
                "host_team_league": None,
                "guest_team_league": None,
                "note": "Giao hữu đã được Admin tắt. Phòng đã trở về trạng thái chờ.",
                "updated_at": now_iso(),
            }).eq("status", "friendly_playing"),
            "disable_active_friendly_rooms",
            attempts=2,
        )

    log_admin_action("Cập nhật công tắc hệ thống", "system", details=features)
    flash("Đã cập nhật các tính năng hệ thống.", "success")
    return redirect_admin("system")



RP_USER_FIELDS = (
    "id", "rank_points", "wins", "draws", "losses", "total_matches",
    "goals_for", "goals_against", "streak", "loss_streak",
)
RP_MATCH_FIELDS = (
    "id", "delta1", "delta2", "rp_formula_version", "rp_details",
)
RP_BACKUP_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
RP_BACKUP_MAX_ROWS = 100000


def _select_all_rows(table_name, columns="*", page_size=1000):
    rows = []
    start = 0
    while True:
        result = execute_query(
            db.table(table_name).select(columns).range(start, start + page_size - 1),
            f"rp_backup_{table_name}_{start}", attempts=2,
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        start += page_size


def _build_rp_backup_payload(actor):
    users = _select_all_rows("users", ",".join(RP_USER_FIELDS))
    matches = _select_all_rows("matches", ",".join(RP_MATCH_FIELDS))
    return {
        "metadata": {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "backup_type": "rp_only",
            "format_version": 1,
            "created_at": now_iso(),
            "created_by_user_id": actor.get("id"),
            "created_by_username": actor.get("username"),
            "environment": APP_ENV,
        },
        "users": users,
        "matches": matches,
    }


@app.route("/admin/rp/backup/download", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("rp_backup_restore")
def admin_download_rp_backup():
    actor = current_user()
    if not is_test_mode() and request.form.get("confirm_text", "").strip() != "SAO LUU RP":
        flash("Trên Production, hãy nhập đúng: SAO LUU RP", "danger")
        return redirect_admin("rp-tools")
    try:
        payload = _build_rp_backup_payload(actor)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_name = f"PES_Arena_RP_Backup_{timestamp}.json"
        zip_name = f"PES_Arena_RP_Backup_{timestamp}.zip"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(json_name, json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            archive.writestr(
                "README.txt",
                "PES Arena RP-only backup. Restores RP/statistics/streaks and stored match deltas only.\n",
            )
        output.seek(0)
        log_admin_action("Sao lưu RP toàn hệ thống", "rp", details={
            "users": len(payload["users"]), "matches": len(payload["matches"]),
        })
        return send_file(output, mimetype="application/zip", as_attachment=True, download_name=zip_name)
    except Exception as exc:
        app.logger.exception("RP backup failed")
        flash(f"Không thể sao lưu RP: {exc}", "danger")
        return redirect_admin("rp-tools")


def _read_rp_backup_upload(upload):
    if not upload or not upload.filename:
        raise ValueError("Hãy chọn file PES Arena RP Backup ZIP hoặc JSON.")
    raw = upload.read(RP_BACKUP_UPLOAD_MAX_BYTES + 1)
    if len(raw) > RP_BACKUP_UPLOAD_MAX_BYTES:
        raise ValueError("File RP Backup vượt quá giới hạn 10 MB.")
    filename = upload.filename.lower().strip()
    if filename.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            candidates = [i for i in archive.infolist() if i.filename.lower().endswith(".json") and not i.is_dir()]
            if len(candidates) != 1:
                raise ValueError("ZIP phải chứa đúng một file JSON RP Backup.")
            if candidates[0].file_size > RP_BACKUP_UPLOAD_MAX_BYTES * 5:
                raise ValueError("JSON giải nén quá lớn.")
            raw = archive.read(candidates[0])
    elif not filename.endswith(".json"):
        raise ValueError("Chỉ chấp nhận file .zip hoặc .json.")
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise ValueError("Không đọc được JSON trong file RP Backup.") from exc
    metadata = payload.get("metadata") or {}
    if metadata.get("app_name") != APP_NAME or metadata.get("backup_type") != "rp_only":
        raise ValueError("Đây không phải file PES Arena RP Backup hợp lệ.")
    users = payload.get("users")
    matches = payload.get("matches")
    if not isinstance(users, list) or not isinstance(matches, list):
        raise ValueError("File thiếu danh sách users hoặc matches.")
    if len(users) + len(matches) > RP_BACKUP_MAX_ROWS:
        raise ValueError("File RP Backup vượt quá 100.000 bản ghi.")
    return payload


def _restore_rp_backup_payload(payload):
    user_count = 0
    match_count = 0
    missing_users = 0
    missing_matches = 0
    for row in payload.get("users", []):
        user_id = row.get("id")
        if not user_id:
            continue
        values = {key: row.get(key) for key in RP_USER_FIELDS if key != "id"}
        result = execute_query(
            db.table("users").update(values).eq("id", user_id),
            "restore_rp_user", attempts=2,
        )
        if result.data:
            user_count += 1
        else:
            missing_users += 1
    for row in payload.get("matches", []):
        match_id = row.get("id")
        if not match_id:
            continue
        values = {key: row.get(key) for key in RP_MATCH_FIELDS if key != "id"}
        result = execute_query(
            db.table("matches").update(values).eq("id", match_id),
            "restore_rp_match", attempts=2,
        )
        if result.data:
            match_count += 1
        else:
            missing_matches += 1
    ttl_cache_delete("players_raw", "rooms_raw", "achievement_map")
    cache_delete("all_users")
    return {
        "users": user_count, "matches": match_count,
        "missing_users": missing_users, "missing_matches": missing_matches,
    }


@app.route("/admin/rp/backup/restore", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("rp_backup_restore")
def admin_restore_rp_backup():
    actor = current_user()
    if not is_test_mode():
        if not is_owner_user(actor):
            flash("Chỉ tài khoản sở hữu được khôi phục RP trên Production.", "danger")
            return redirect_admin("rp-tools")
        if actor.get("password_hash") != hash_password(request.form.get("current_password", "")):
            flash("Mật khẩu hiện tại không đúng.", "danger")
            return redirect_admin("rp-tools")
        if request.form.get("confirm_text", "").strip() != "KHOI PHUC RP":
            flash("Hãy nhập đúng: KHOI PHUC RP", "danger")
            return redirect_admin("rp-tools")
    try:
        payload = _read_rp_backup_upload(request.files.get("backup_file"))
        report = _restore_rp_backup_payload(payload)
        log_admin_action("Khôi phục RP toàn hệ thống", "rp", details={
            "source": payload.get("metadata", {}), "report": report,
        })
        flash(
            f"Đã khôi phục RP cho {report['users']} tài khoản và delta của {report['matches']} trận. "
            f"Không tìm thấy: {report['missing_users']} tài khoản, {report['missing_matches']} trận.",
            "success",
        )
    except Exception as exc:
        app.logger.exception("RP restore failed")
        log_admin_action("Khôi phục RP thất bại", "rp", details={"error": str(exc)[:500]})
        flash(f"Không thể khôi phục RP: {exc}", "danger")
    return redirect_admin("rp-tools")


# Các route Backup toàn bộ dữ liệu từ V1.13.4 đã ngừng sử dụng.
@app.route("/admin/backup/download", methods=["POST"])
@app.route("/admin/backup/preview", methods=["POST"])
@app.route("/admin/backup/restore", methods=["POST"])
@login_required
@admin_required
def retired_full_database_backup_routes():
    abort(404)


@app.route("/admin/ownership/transfer", methods=["POST"])
@login_required
@owner_required
def admin_transfer_ownership():
    abort(404)
    actor = current_user()
    target_id = (request.form.get("target_user_id") or "").strip()
    current_password = request.form.get("current_password", "").strip()
    confirm_text = request.form.get("confirm_text", "").strip()
    if actor.get("password_hash") != hash_password(current_password):
        flash("Mật khẩu hiện tại của tài khoản sở hữu không đúng.", "danger")
        return redirect_admin("overview")
    if confirm_text != "CHUYEN GIAO":
        flash("Hãy nhập đúng CHUYEN GIAO để xác nhận.", "danger")
        return redirect_admin("overview")
    target = get_user(target_id)
    if not target or target.get("account_status") != "approved" or target.get("id") == actor.get("id"):
        flash("Tài khoản nhận chuyển giao không hợp lệ.", "danger")
        return redirect_admin("overview")

    full_permissions = {code: True for codes in ADMIN_PERMISSION_GROUPS.values() for code in codes}
    try:
        execute_query(db.table("users").update({
            "admin_level": "owner", "admin_permissions": full_permissions,
            "updated_at": now_iso(),
        }).eq("id", target["id"]), "transfer_owner_to_target")
        execute_query(db.table("users").update({
            "admin_level": "admin", "admin_permissions": full_permissions,
            "updated_at": now_iso(),
        }).eq("id", actor["id"]), "transfer_owner_from_actor")
    except Exception:
        app.logger.exception("Ownership transfer failed")
        # Best-effort restore the actor as owner if the second write failed.
        execute_query(db.table("users").update({"admin_level": "owner"}).eq("id", actor["id"]), "restore_owner_after_transfer_failure", attempts=2)
        raise
    log_admin_action("Chuyển giao quyền sở hữu", "user", target["id"], target.get("username"), f"Từ {actor.get('username')} sang {target.get('username')}")
    session.clear()
    flash("Đã chuyển giao quyền sở hữu. Hãy đăng nhập lại.", "success")
    return redirect(url_for("login"))


# =========================
# Admin
# =========================
def redirect_admin(tab="overview"):
    return redirect(url_for("admin") + f"#{tab}")


@app.route("/admin")
@login_required
@admin_required
def admin():
    # Trang Admin chứa nhiều khối dữ liệu độc lập. Một truy vấn phụ lỗi không được
    # làm sập toàn bộ trang; khối lỗi sẽ tạm trả danh sách rỗng và ghi log Vercel.
    def admin_safe_load(label, loader, default):
        try:
            value = loader()
            return default if value is None else value
        except Exception as exc:
            app.logger.exception("Admin load failed [%s]: %s", label, exc)
            return default

    all_rooms = admin_safe_load("rooms", list_rooms, [])
    all_matches = admin_safe_load("matches", list_matches, [])
    raw_users = admin_safe_load("users", list_all_users, [])
    admin_users = admin_safe_load(
        "decorate_users", lambda: decorate_admin_users(raw_users), []
    )

    # Ưu tiên nhóm IP trùng lên đầu và đặt các tài khoản cùng IP cạnh nhau.
    admin_users.sort(key=lambda item: (
        0 if item.get("duplicate_ips") else 1,
        (item.get("duplicate_ips") or [item.get("latest_ip") or "~"])[0],
        (item.get("username") or "").lower(),
    ))
    players = [u for u in admin_users if u.get("role") == "player"]
    admins = [u for u in admin_users if is_admin_user(u)]
    pending_users = [u for u in players if u.get("account_status") == "pending"]

    password_reset_requests = admin_safe_load(
        "password_resets", lambda: list_password_reset_requests("pending"), []
    )
    raw_disputes = admin_safe_load(
        "match_disputes", lambda: list_match_disputes("pending"), []
    )
    pending_disputes = []
    for item in raw_disputes:
        try:
            pending_disputes.append(decorate_match_dispute(item, all_matches))
        except Exception as exc:
            app.logger.exception("Admin dispute decoration failed: %s", exc)

    audit_logs = (
        admin_safe_load("audit_logs", list_admin_activity_logs, [])
        if is_owner_user(current_user()) else []
    )
    duplicate_ip_groups = admin_safe_load(
        "duplicate_ips", lambda: build_duplicate_ip_groups(admin_users), []
    )
    duplicate_ip_user_count = len({
        str(account.get("id"))
        for group in duplicate_ip_groups
        for account in group.get("accounts", [])
        if account.get("id")
    })

    return render_template(
        "admin.html",
        admin_users=admin_users,
        players=players,
        admins=admins,
        pending_users=pending_users,
        all_matches=all_matches[:80],
        disputed=[m for m in all_matches if m.get("status") == "disputed"],
        playing=[m for m in all_matches if m.get("status") == "playing"],
        rooms=[r for r in all_rooms if r.get("status") in ["waiting_ready", "playing", "waiting_result_confirm", "disputed"]],
        all_rooms=all_rooms[:80],
        invites=admin_safe_load("invites", lambda: list_invites("pending"), []),
        active_announcement=admin_safe_load("announcement", get_active_announcement, None),
        password_reset_requests=password_reset_requests,
        audit_logs=audit_logs,
        duplicate_ip_groups=duplicate_ip_groups,
        duplicate_ip_user_count=duplicate_ip_user_count,
        pending_disputes=pending_disputes,
        can_create_test_account=has_admin_permission(current_user(), "users_edit"),
        can_import_accounts_csv=has_admin_permission(current_user(), "accounts_import"),
        admin_permission_groups=ADMIN_PERMISSION_GROUPS,
        admin_permission_labels=ADMIN_PERMISSION_LABELS,
        current_admin_permissions=_admin_permissions(current_user()),
        system_features=admin_safe_load("system_features", get_system_features, dict(SYSTEM_FEATURE_DEFAULTS)),
        maintenance_config=admin_safe_load("maintenance_config", get_maintenance_config, _maintenance_default_config()),
        maintenance_status=admin_safe_load("maintenance_status", get_maintenance_status, {"closed": False, "countdown": None}),
    )



def _safe_bounded_int(value, default=0, minimum=0, maximum=999999):
    """Parse integers that must stay inside an explicit range."""
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return int(default)
    return max(minimum, min(maximum, parsed))


def _csv_password_value(row):
    """Đọc mật khẩu từ cột password hoặc pass; chuỗi trống nghĩa là không cung cấp."""
    value = row.get("password")
    if value is None or str(value).strip() == "":
        value = row.get("pass")
    return str(value or "").strip()


def _build_test_user_payload(row, default_password="Test@12345"):
    username = str(row.get("username") or "").strip()
    display_name = str(row.get("display_name") or username).strip() or username
    supplied_password = _csv_password_value(row)
    password = supplied_password or default_password
    zalo_name = str(row.get("zalo_name") or "Tài khoản test").strip() or "Tài khoản test"
    if len(username) < 3 or len(username) > 30:
        raise ValueError("Tên tài khoản phải từ 3 đến 30 ký tự.")
    if len(password) < minimum_password_length():
        raise ValueError(f"Mật khẩu của {username} phải có ít nhất {minimum_password_length()} ký tự.")

    wins = _safe_bounded_int(row.get("wins"), 0)
    draws = _safe_bounded_int(row.get("draws"), 0)
    losses = _safe_bounded_int(row.get("losses"), 0)
    supplied_total = _safe_bounded_int(row.get("total_matches"), wins + draws + losses)
    total_matches = max(supplied_total, wins + draws + losses)

    return {
        "username": username,
        "password_hash": hash_password(password),
        "display_name": display_name[:80],
        "zalo_name": zalo_name[:80],
        "role": "player",
        "account_status": "approved",
        "invite_code_used": None,
        "rank_points": _safe_bounded_int(row.get("rank_points"), DEFAULT_POINTS, -999999, 999999),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "total_matches": total_matches,
        "goals_for": _safe_bounded_int(row.get("goals_for"), 0),
        "goals_against": _safe_bounded_int(row.get("goals_against"), 0),
        "is_online": False,
        "must_change_password": False,
        "register_ip": "ADMIN_TEST_IMPORT",
        "register_user_agent": "PES 2026 Admin Test Data",
    }


@app.route("/admin/test-account/create", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("users_edit")
def admin_create_test_account():
    row = {
        "username": request.form.get("username", ""),
        "display_name": request.form.get("display_name", ""),
        "password": request.form.get("password", ""),
        "zalo_name": request.form.get("zalo_name", "Tài khoản test"),
        "rank_points": request.form.get("rank_points", DEFAULT_POINTS),
    }
    try:
        payload = _build_test_user_payload(row)
        if get_user_by_username(payload["username"]):
            flash("Tên tài khoản test đã tồn tại.", "warning")
            return redirect_admin("test-data")
        execute_query(db.table("users").insert(payload), "admin_create_test_account")
        cache_delete("_rz_players_all")
        cache_delete("_rz_users_map")
        log_admin_action("create_test_account", "user", None, payload["username"], {"rank_points": payload["rank_points"]})
        flash(f"Đã tạo tài khoản test {payload['username']}.", "success")
    except Exception as exc:
        flash(f"Không thể tạo tài khoản test: {exc}", "danger")
    return redirect_admin("test-data")



@app.route("/admin/test-account/sample.csv")
@login_required
@admin_required
@admin_permission_required("accounts_import")
def admin_download_test_account_sample():
    sample_rows = [
        ["username", "display_name", "password", "zalo_name", "rank_points", "wins", "draws", "losses", "total_matches", "goals_for", "goals_against", "register_ip", "last_ip"],
        ["test01", "Test Player 01", "123456", "Test 01", "1200", "5", "2", "3", "10", "12", "9", "", ""],
        ["test02", "Test Player 02", "123456", "Test 02", "-1000", "0", "0", "0", "0", "0", "0", "", ""],
    ]
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(sample_rows)
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="PES_Arena_Import_Tai_Khoan_Mau_v1.13.2.csv"'
    response.headers["Cache-Control"] = "no-store"
    return response

@app.route("/admin/test-account/import", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("accounts_import")
def admin_import_test_accounts():
    upload = request.files.get("csv_file")
    pasted_csv = request.form.get("csv_text", "").strip()
    default_password = request.form.get("default_password", "Test@12345").strip() or "Test@12345"
    if len(default_password) < minimum_password_length():
        flash(f"Mật khẩu mặc định phải có ít nhất {minimum_password_length()} ký tự.", "danger")
        return redirect_admin("test-data")

    if upload and upload.filename:
        if not upload.filename.lower().endswith(".csv"):
            flash("Chỉ hỗ trợ file CSV.", "danger")
            return redirect_admin("test-data")
        raw = upload.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            flash("File CSV tối đa 1 MB.", "danger")
            return redirect_admin("test-data")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            flash("File CSV phải dùng mã hóa UTF-8.", "danger")
            return redirect_admin("test-data")
    else:
        text = pasted_csv

    if not text:
        flash("Hãy chọn file CSV hoặc dán dữ liệu CSV.", "warning")
        return redirect_admin("test-data")

    reader = csv.DictReader(io.StringIO(text))
    required = {"username"}
    normalized_headers = {str(h or "").strip() for h in (reader.fieldnames or [])}
    if not required.issubset(normalized_headers):
        flash("CSV bắt buộc có cột username.", "danger")
        return redirect_admin("test-data")

    created, updated, errors = 0, 0, []
    seen_usernames = set()
    additive_fields = (
        "rank_points",
        "wins",
        "draws",
        "losses",
        "total_matches",
        "goals_for",
        "goals_against",
    )

    for line_no, raw_row in enumerate(reader, start=2):
        if line_no > 502:
            errors.append("Chỉ nhập tối đa 500 tài khoản mỗi lần.")
            break
        row = {str(k or "").strip(): (v or "").strip() for k, v in raw_row.items()}
        username = row.get("username", "").strip()
        if not username:
            continue

        username_key = username.lower()
        if username_key in seen_usernames:
            errors.append(f"Dòng {line_no}: username {username} bị lặp trong cùng file CSV nên không được cộng lần hai.")
            if len(errors) >= 8:
                errors.append("Đã dừng hiển thị thêm lỗi.")
                break
            continue
        seen_usernames.add(username_key)

        try:
            existing_user = get_user_by_username(username)
            if not existing_user:
                payload = _build_test_user_payload(row, default_password)
                execute_query(db.table("users").insert(payload), "admin_import_test_account")
                created += 1
                continue

            increments = {}
            for field in additive_fields:
                raw_value = row.get(field, "")
                if raw_value == "":
                    continue
                # Chỉ rank_points được phép nhập số âm để Admin hoàn tác/trừ RP.
                # Các thống kê trận đấu vẫn bắt buộc không âm để tránh dữ liệu sai.
                if field == "rank_points":
                    increments[field] = _safe_bounded_int(raw_value, 0, -999999, 999999)
                else:
                    increments[field] = _safe_bounded_int(raw_value, 0, 0, 999999)

            # Nếu CSV có thắng/hòa/thua nhưng không có total_matches,
            # tự cộng tổng số trận tương ứng để dữ liệu không bị lệch.
            if row.get("total_matches", "") == "":
                wdl_increment = sum(increments.get(field, 0) for field in ("wins", "draws", "losses"))
                if wdl_increment:
                    increments["total_matches"] = wdl_increment

            if not increments:
                errors.append(f"Dòng {line_no}: tài khoản {username} đã tồn tại nhưng không có chỉ số nào để cộng.")
                if len(errors) >= 8:
                    errors.append("Đã dừng hiển thị thêm lỗi.")
                    break
                continue

            update_payload = {}
            for field, increment in increments.items():
                current_value = _safe_bounded_int(existing_user.get(field), 0, 0, 999999)
                if field == "rank_points":
                    # Cho phép cộng/trừ RP nhưng không để tổng điểm xuống dưới 0.
                    update_payload[field] = max(0, min(999999, current_value + increment))
                else:
                    update_payload[field] = min(999999, current_value + increment)

            # Với tài khoản đã tồn tại: cột password/pass để trống sẽ giữ nguyên mật khẩu cũ.
            # Chỉ cập nhật mật khẩu khi CSV thực sự cung cấp một giá trị hợp lệ.
            supplied_password = _csv_password_value(row)
            if supplied_password:
                if len(supplied_password) < minimum_password_length():
                    raise ValueError(f"Mật khẩu mới của {username} phải có ít nhất {minimum_password_length()} ký tự.")
                update_payload["password_hash"] = hash_password(supplied_password)
                update_payload["must_change_password"] = False
                update_payload["password_changed_at"] = now_iso()

            execute_query(
                db.table("users").update(update_payload).eq("id", existing_user["id"]),
                "admin_import_add_user_stats",
            )
            updated += 1
        except Exception as exc:
            errors.append(f"Dòng {line_no}: {exc}")
            if len(errors) >= 8:
                errors.append("Đã dừng hiển thị thêm lỗi.")
                break

    cache_delete("_rz_players_all")
    cache_delete("_rz_users_map")
    log_admin_action(
        "import_test_accounts_additive",
        "user",
        None,
        "CSV additive import",
        {"created": created, "updated": updated, "errors": len(errors)},
    )
    if created or updated:
        flash(
            f"Import cộng dồn hoàn tất: tạo mới {created} tài khoản, cộng dữ liệu cho {updated} tài khoản đã có.",
            "success",
        )
    else:
        flash("Không có tài khoản nào được tạo mới hoặc cộng dữ liệu.", "warning")
    for message in errors[:8]:
        flash(message, "danger")
    return redirect_admin("test-data")


@app.route("/admin/password-reset/<request_id>/resolve", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("password_reset")
def admin_resolve_password_reset(request_id):
    reset_request = get_password_reset_request(request_id)
    if not reset_request or reset_request.get("status") != "pending":
        flash("Yêu cầu khôi phục không còn hiệu lực.", "warning")
        return redirect_admin("passwords")

    user = get_user(reset_request.get("user_id"))
    temporary_password = request.form.get("temporary_password", "").strip()
    if not user:
        flash("Không tìm thấy tài khoản cần khôi phục.", "danger")
        return redirect_admin("passwords")
    if len(temporary_password) < minimum_password_length():
        flash(f"Mật khẩu tạm phải có ít nhất {minimum_password_length()} ký tự.", "danger")
        return redirect_admin("passwords")

    actor = current_user()
    execute_query(
        db.table("users").update({
            "password_hash": hash_password(temporary_password),
            "must_change_password": True,
            "password_changed_at": now_iso(),
        }).eq("id", user["id"]),
        "admin_issue_temporary_password",
    )
    execute_query(
        db.table("password_reset_requests").update({
            "status": "resolved",
            "admin_user_id": actor["id"],
            "admin_note": "Đã cấp mật khẩu tạm; không lưu mật khẩu gốc.",
            "resolved_at": now_iso(),
        }).eq("id", request_id),
        "resolve_password_reset_request",
    )
    log_admin_action(
        "Cấp mật khẩu tạm",
        "user",
        user.get("id"),
        user.get("username"),
        "User buộc phải đổi mật khẩu sau lần đăng nhập tiếp theo.",
    )
    flash(f"Đã cấp mật khẩu tạm cho {user.get('username')}. Hãy gửi mật khẩu này cho user qua Zalo; hệ thống không lưu lại mật khẩu tạm.", "success")
    return redirect_admin("passwords")


@app.route("/admin/password-reset/<request_id>/reject", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("password_reset")
def admin_reject_password_reset(request_id):
    reset_request = get_password_reset_request(request_id)
    if not reset_request or reset_request.get("status") != "pending":
        flash("Yêu cầu khôi phục không còn hiệu lực.", "warning")
        return redirect_admin("passwords")

    actor = current_user()
    note = request.form.get("note", "").strip()[:250]
    execute_query(
        db.table("password_reset_requests").update({
            "status": "rejected",
            "admin_user_id": actor["id"],
            "admin_note": note or "Admin từ chối yêu cầu.",
            "resolved_at": now_iso(),
        }).eq("id", request_id),
        "reject_password_reset_request",
    )
    log_admin_action(
        "Từ chối khôi phục mật khẩu",
        "user",
        reset_request.get("user_id"),
        reset_request.get("username_snapshot"),
        note or "Không có ghi chú.",
    )
    flash("Đã từ chối yêu cầu khôi phục mật khẩu.", "success")
    return redirect_admin("passwords")


@app.route("/admin/account/<user_id>/approve", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("users_approve")
def admin_approve_account(user_id):
    user = get_user(user_id)
    if not user or user.get("role") != "player":
        flash("Không tìm thấy tài khoản player.", "danger")
        return redirect_admin("overview")

    actor = current_user()
    execute_query(
        db.table("users").update({
            "account_status": "approved",
            "approved_by": actor["id"],
            "approved_at": now_iso(),
            "rejection_reason": None,
        }).eq("id", user_id),
        "approve_account",
    )
    log_admin_action("Duyệt tài khoản", "user", user_id, user.get("username"), "Trạng thái: approved")
    flash(f"Đã duyệt tài khoản {user.get('username')}.", "success")
    return redirect_admin("overview")


@app.route("/admin/account/<user_id>/reject", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("users_approve")
def admin_reject_account(user_id):
    user = get_user(user_id)
    if not user or user.get("role") != "player":
        flash("Không tìm thấy tài khoản player.", "danger")
        return redirect_admin("overview")

    reason = request.form.get("reason", "").strip()[:200]
    execute_query(
        db.table("users").update({
            "account_status": "rejected",
            "is_online": False,
            "rejection_reason": reason or "Admin từ chối tài khoản.",
        }).eq("id", user_id),
        "reject_account",
    )
    log_admin_action("Từ chối tài khoản", "user", user_id, user.get("username"), reason or "Không có lý do.")
    flash("Đã từ chối tài khoản.", "success")
    return redirect_admin("overview")


@app.route("/admin/account/<user_id>/ban", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("users_edit")
def admin_ban_account(user_id):
    user = get_user(user_id)
    actor = current_user()
    if not user or user.get("role") != "player":
        flash("Không tìm thấy tài khoản player.", "danger")
        return redirect_admin("users")
    if is_admin_user(user) and not is_owner_user(actor):
        flash("Chỉ chủ hệ thống mới có thể xử lý tài khoản Admin phụ.", "danger")
        return redirect_admin("users")
    if is_admin_user(user):
        flash("Hãy gỡ quyền Admin trước khi khóa tài khoản.", "danger")
        return redirect_admin("users")

    execute_query(
        db.table("users").update({"account_status": "banned", "is_online": False}).eq("id", user_id),
        "ban_account",
    )
    log_admin_action("Khóa tài khoản", "user", user_id, user.get("username"), "Trạng thái: banned")
    flash("Đã khóa tài khoản.", "success")
    return redirect_admin("users")

@app.route("/admin/account/<user_id>/unban", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("users_edit")
def admin_unban_account(user_id):
    user = get_user(user_id)
    if not user or user.get("role") != "player":
        flash("Không tìm thấy tài khoản player.", "danger")
        return redirect_admin("users")

    execute_query(
        db.table("users").update({"account_status": "approved"}).eq("id", user_id),
        "unban_account",
    )
    log_admin_action("Mở khóa tài khoản", "user", user_id, user.get("username"), "Trạng thái: approved")
    flash("Đã mở khóa tài khoản.", "success")
    return redirect_admin("users")


@app.route("/admin/invite-code/create", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("registration_codes_manage")
def admin_create_invite_code():
    actor = current_user()
    label = request.form.get("label", "").strip()[:80]

    for _ in range(10):
        code_value = generate_invite_code_value()
        if not get_invite_code_record(code_value):
            execute_query(
                db.table("registration_invite_codes").insert({
                    "code": code_value,
                    "created_by": actor["id"],
                    "label": label,
                    "is_active": True,
                }),
                "create_invite_code",
            )
            log_admin_action("Tạo mã mời", "invite_code", target_label=code_value, details=label or "Không có nhãn.")
            flash(f"Đã tạo mã mời: {code_value}", "success")
            return redirect(url_for("admin"))

    flash("Không tạo được mã mời, vui lòng thử lại.", "danger")
    return redirect(url_for("admin"))


@app.route("/admin/invite-code/<code_id>/disable", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("registration_codes_manage")
def admin_disable_invite_code(code_id):
    execute_query(
        db.table("registration_invite_codes").update({"is_active": False}).eq("id", code_id),
        "disable_invite_code",
    )
    log_admin_action("Vô hiệu hóa mã mời", "invite_code", code_id)
    flash("Đã vô hiệu hóa mã mời.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/user/<user_id>/promote", methods=["POST"])
@login_required
@owner_required
def admin_promote_user(user_id):
    user = get_user(user_id)
    if (
        not user
        or user.get("role") != "player"
        or user.get("account_status") != "approved"
        or user.get("admin_level", "none") != "none"
    ):
        flash("Chỉ có thể thêm player đã được duyệt làm admin.", "danger")
        return redirect_admin("users")

    execute_query(
        db.table("users").update({"admin_level": "admin", "admin_permissions": {}, "admin_can_create_test_account": False, "admin_can_import_accounts_csv": False}).eq("id", user_id),
        "promote_admin",
    )
    log_admin_action("Thêm Admin phụ", "user", user_id, user.get("username"), "admin_level: none → admin")
    flash(f"Đã thêm {user.get('username')} làm admin phụ. Người này vẫn có thể thi đấu.", "success")
    return redirect_admin("users")


@app.route("/admin/user/<user_id>/permissions", methods=["POST"])
@login_required
@owner_required
def admin_update_permissions(user_id):
    user = get_user(user_id)
    if not user or user.get("admin_level") != "admin":
        flash("Không tìm thấy Admin phụ.", "danger")
        return redirect_admin("overview")

    payload = {code: request.form.get(code) == "1" for codes in ADMIN_PERMISSION_GROUPS.values() for code in codes}
    db_payload = {
        "admin_permissions": payload,
        "admin_can_create_test_account": payload.get("users_edit", False),
        "admin_can_import_accounts_csv": payload.get("accounts_import", False),
    }
    try:
        execute_query(
            db.table("users").update(db_payload).eq("id", user_id),
            "update_admin_permissions",
        )
    except Exception as exc:
        error_text = str(exc)
        lowered = error_text.lower()
        missing_permission_columns = (
            "admin_can_create_test_account" in lowered
            or "admin_can_import_accounts_csv" in lowered
            or "pgrst204" in lowered
            or "column" in lowered and "schema cache" in lowered
        )
        app.logger.exception("Không thể lưu quyền Admin phụ")
        if missing_permission_columns:
            flash(
                "Supabase chưa có cột quyền Admin phụ. Hãy chạy file "
                "docs/update_admin_permissions_v1_9_1.sql trong Supabase SQL Editor rồi lưu lại.",
                "danger",
            )
        else:
            flash(
                "Không thể lưu quyền Admin phụ do lỗi kết nối dữ liệu. Vui lòng thử lại và kiểm tra Runtime Logs.",
                "danger",
            )
        return redirect_admin("overview")

    cache_delete("_rz_players_all")
    cache_delete("_rz_users_map")
    log_admin_action("Cập nhật quyền Admin phụ", "user", user_id, user.get("username"), payload)
    flash(f"Đã cập nhật quyền cho Admin phụ {user.get('username')}.", "success")
    return redirect_admin("overview")

@app.route("/admin/user/<user_id>/demote", methods=["POST"])
@login_required
@owner_required
def admin_demote_user(user_id):
    user = get_user(user_id)
    if not user or user.get("admin_level") != "admin":
        flash("Không tìm thấy admin phụ.", "danger")
        return redirect_admin("users")

    execute_query(
        db.table("users").update({"admin_level": "none", "admin_permissions": {}, "admin_can_create_test_account": False, "admin_can_import_accounts_csv": False}).eq("id", user_id),
        "demote_admin",
    )
    log_admin_action("Gỡ Admin phụ", "user", user_id, user.get("username"), "admin_level: admin → none")
    flash("Đã gỡ quyền admin phụ.", "success")
    return redirect_admin("users")

@app.route("/admin/dispute/<dispute_id>/accept", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("disputes_manage")
def admin_dispute_accept(dispute_id):
    abort(404)
    dispute = get_match_dispute(dispute_id)
    if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
        flash("Tranh chấp không còn hiệu lực.", "warning")
        return redirect_admin("disputes")
    actor = current_user()
    try:
        delta1, delta2 = resolve_match_dispute_with_result(
            dispute,
            dispute.get("submitted_score1"),
            dispute.get("submitted_score2"),
            actor.get("id"),
            "accepted_original",
            request.form.get("resolution_note", "").strip() or "Admin công nhận kết quả ban đầu.",
        )
    except Exception as exc:
        flash(f"Không thể xử lý tranh chấp: {exc}", "danger")
        return redirect_admin("disputes")
    log_admin_action("Công nhận kết quả tranh chấp", "match", dispute.get("match_id"), details=f"Điểm: {delta1:+d}/{delta2:+d}")
    flash("Đã công nhận kết quả và cập nhật điểm.", "success")
    return redirect_admin("disputes")




@app.route("/admin/dispute/<dispute_id>/cancel", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("disputes_manage")
def admin_dispute_cancel(dispute_id):
    abort(404)
    dispute = get_match_dispute(dispute_id)
    if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
        flash("Tranh chấp không còn hiệu lực.", "warning")
        return redirect_admin("disputes")
    actor = current_user()
    note = request.form.get("resolution_note", "").strip() or "Admin hủy trận tranh chấp; không tính điểm."
    try:
        cancel_match_dispute(dispute, actor.get("id"), note)
    except Exception as exc:
        flash(f"Không thể hủy trận tranh chấp: {exc}", "danger")
        return redirect_admin("disputes")
    log_admin_action("Hủy trận tranh chấp", "match", dispute.get("match_id"), details=note)
    flash("Đã hủy trận tranh chấp. Không ai bị cộng hoặc trừ điểm.", "success")
    return redirect_admin("disputes")



@app.route("/admin/match/<match_id>/update", methods=["POST"])
@login_required
@admin_required
def admin_update_match(match_id):
    """Admin sửa tỷ số/trạng thái và tính lại BXH theo thời gian trận gốc."""
    actor = current_user()
    match = get_match(match_id)
    if not match:
        flash("Không tìm thấy trận.", "danger")
        return redirect_admin("matches")

    old_signature = _match_state_signature(match)
    old_status = str(match.get("status") or "waiting_confirm")
    new_status = str(request.form.get("status") or old_status).strip()
    note = str(request.form.get("note") or "").strip()[:500]
    allowed_statuses = {"playing", "waiting_confirm", "disputed", "confirmed", "cancelled"}
    if new_status not in allowed_statuses:
        flash("Trạng thái không hợp lệ.", "danger")
        return redirect_admin("matches")

    try:
        new_score1 = parse_score(request.form.get("score1"))
        new_score2 = parse_score(request.form.get("score2"))
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect_admin("matches")

    if new_status == "confirmed" and not has_admin_permission(actor, "matches_confirm"):
        abort(403)
    if new_status == "cancelled" and not has_admin_permission(actor, "matches_cancel"):
        abort(403)
    if new_status not in {"confirmed", "cancelled"} and not (
        has_admin_permission(actor, "matches_confirm")
        or has_admin_permission(actor, "matches_cancel")
    ):
        abort(403)
    if new_status == "confirmed" and (new_score1 is None or new_score2 is None):
        flash("Trận xác nhận phải có đủ hai tỷ số.", "danger")
        return redirect_admin("matches")

    changed_score = score_changed(match, new_score1, new_score2)
    changed_status = new_status != old_status
    changed_note = note != str(match.get("note") or "")
    if not (changed_score or changed_status or changed_note):
        flash("Không có thay đổi cần lưu.", "warning")
        return redirect_admin("matches")

    override = {
        "score1": new_score1,
        "score2": new_score2,
        "status": new_status,
        "note": note or match.get("note") or (
            "Đã xác nhận." if new_status == "confirmed" else "Admin đã cập nhật trận."
        ),
    }
    if changed_score or changed_status:
        override["confirmed_by_id"] = actor.get("id") if new_status == "confirmed" else None

    lock_token = None
    try:
        if changed_score or changed_status:
            lock_token = acquire_ranking_rebuild_lock(actor.get("id"), match_id)
            fresh = get_match(match_id)
            if not fresh or _match_state_signature(fresh) != old_signature:
                raise ValueError(
                    "Trận vừa được một luồng khác cập nhật. Hãy tải lại trang trước khi lưu."
                )
            match = fresh
            old_status = str(match.get("status") or old_status)

        affects_ranking = old_status == "confirmed" or new_status == "confirmed"
        if affects_ranking and (changed_score or changed_status):
            match_count, user_count = rebuild_rankings_after_admin_change(
                match_id, override, lock_token=lock_token, actor_id=actor.get("id")
            )
            log_admin_action(
                "Sửa kết quả/trạng thái trận",
                "match",
                match_id,
                details=(
                    f"{match.get('score1')}-{match.get('score2')} / {old_status} → "
                    f"{new_score1}-{new_score2} / {new_status}; phát lại {match_count} trận, "
                    f"tính lại {user_count} tài khoản; giữ nguyên created_at"
                ),
            )
            flash(
                "Đã lưu và tính lại RP, thắng/thua, streak, loss_streak theo đúng mốc thời gian cũ.",
                "success",
            )
            return redirect_admin("matches")

        payload = {key: value for key, value in override.items() if key != "created_at"}
        payload["updated_at"] = now_iso()
        result = execute_query(
            db.table("matches").update(payload).eq("id", match_id).eq("status", old_status),
            "admin_update_match_without_rebuild",
        )
        if not (result.data or []):
            raise ValueError("Trạng thái trận đã thay đổi; chưa ghi đè dữ liệu mới.")
        sync_room_after_admin_match_change(match, override, actor_id=actor.get("id"))
        cache_delete("_rz_matches_all", "_rz_rooms_all")
        ttl_cache_delete("rooms_raw")
        log_admin_action(
            "Cập nhật trận", "match", match_id,
            details=f"{old_status} → {new_status}; giữ nguyên created_at",
        )
        flash("Đã lưu tỷ số, trạng thái và ghi chú. Thời gian trận được giữ nguyên.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception as exc:
        app.logger.exception("admin_update_match failed: %s", exc)
        flash(
            "Không thể cập nhật hoàn chỉnh. Hệ thống đã dừng để tránh cộng/trừ RP sai.",
            "danger",
        )
    finally:
        release_ranking_rebuild_lock(lock_token)
    return redirect_admin("matches")


@app.route("/admin/cancel/<match_id>", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("matches_cancel")
def admin_cancel(match_id):
    actor = current_user()
    lock_token = None
    try:
        lock_token = acquire_ranking_rebuild_lock(actor.get("id"), match_id)
        match = get_match(match_id)
        if not match:
            raise ValueError("Không tìm thấy trận.")

        if match.get("status") == "disputed":
            dispute = get_match_dispute_by_match(match_id, DISPUTE_PENDING_STATUSES)
            if dispute:
                cancel_match_dispute(
                    dispute, actor.get("id"), "Admin hủy trận tranh chấp; không tính điểm."
                )
                log_admin_action("Hủy trận tranh chấp", "match", match_id, details="Không tính điểm.")
                flash("Đã hủy trận tranh chấp. Không ai bị cộng hoặc trừ điểm.", "success")
                return redirect_admin("disputes")

        override = {
            "status": "cancelled",
            "confirmed_by_id": None,
            "note": "Admin đã hủy trận.",
        }
        if match.get("status") == "confirmed":
            rebuild_rankings_after_admin_change(
                match_id, override, lock_token=lock_token, actor_id=actor.get("id")
            )
        else:
            payload = {**override, "delta1": None, "delta2": None,
                       "winner_id": None, "loser_id": None,
                       "rp_formula_version": None, "rp_details": None,
                       "updated_at": now_iso()}
            result = execute_query(
                db.table("matches").update(payload).eq("id", match_id).eq("status", match.get("status")),
                "admin_cancel_match",
            )
            if not (result.data or []):
                raise ValueError("Trạng thái trận đã thay đổi; chưa hủy trận.")
            sync_room_after_admin_match_change(match, override, actor_id=actor.get("id"))

        log_admin_action("Hủy trận", "match", match_id, details=f"Trạng thái cũ: {match.get('status')}")
        flash("Đã hủy trận và tính lại lịch sử liên quan.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception as exc:
        app.logger.exception("admin_cancel failed: %s", exc)
        flash("Không thể hủy trận an toàn; chưa tiếp tục để tránh sai RP.", "danger")
    finally:
        release_ranking_rebuild_lock(lock_token)
    return redirect_admin("matches")


@app.route("/admin/confirm-disputed/<match_id>", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("matches_confirm")
def admin_confirm_disputed(match_id):
    match = get_match(match_id)
    if not match:
        flash("Không tìm thấy trận.", "danger")
        return redirect_admin("matches")

    if match["status"] != "disputed":
        flash("Trận này không phải tranh chấp.", "danger")
        return redirect_admin("matches")

    dispute = get_match_dispute_by_match(match_id, DISPUTE_PENDING_STATUSES)
    if dispute:
        try:
            resolve_match_dispute_with_result(
                dispute,
                match.get("score1"),
                match.get("score2"),
                current_user().get("id"),
                "accepted_original",
                "Admin công nhận kết quả ban đầu.",
            )
        except Exception as exc:
            flash(f"Không thể xử lý tranh chấp: {exc}", "danger")
            return redirect_admin("disputes")
    else:
        lock_token = None
        try:
            lock_token = acquire_ranking_rebuild_lock(current_user().get("id"), match_id)
            rebuild_rankings_after_admin_change(
                match_id,
                {
                    "score1": match.get("score1"),
                    "score2": match.get("score2"),
                    "status": "confirmed",
                    "confirmed_by_id": current_user().get("id"),
                    "note": "Admin công nhận kết quả tranh chấp.",
                },
                lock_token=lock_token,
                actor_id=current_user().get("id"),
            )
        except Exception as exc:
            flash(f"Không thể xử lý tranh chấp: {exc}", "danger")
            return redirect_admin("disputes")
        finally:
            release_ranking_rebuild_lock(lock_token)
    log_admin_action("Xác nhận tranh chấp", "match", match_id, details="Đã phát lại lịch sử và cập nhật điểm.")
    flash("Admin đã xác nhận trận tranh chấp.", "success")
    return redirect_admin("disputes")


@app.route("/admin/toggle-online/<user_id>", methods=["POST"])
@login_required
@admin_required
def admin_toggle_online(user_id):
    user = get_user(user_id)
    if not user:
        flash("Không tìm thấy player.", "danger")
        return redirect(url_for("players"))

    new_online = not bool(user.get("is_online"))
    db.table("users").update({"is_online": new_online}).eq("id", user_id).execute()
    log_admin_action("Đổi trạng thái online", "user", user_id, user.get("username"), f"is_online: {new_online}")
    flash("Đã đổi trạng thái online.", "success")
    return redirect(url_for("players"))


@app.route("/admin/player/<user_id>/update", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("users_edit")
def admin_update_player(user_id):
    player = get_user(user_id)
    actor = current_user()
    if not player:
        flash("Không tìm thấy tài khoản.", "danger")
        return redirect(url_for("admin") + "#users")

    if is_admin_user(player) and not is_owner_user(actor):
        flash("Chỉ Chủ hệ thống mới được sửa tài khoản Admin.", "danger")
        return redirect(url_for("admin") + "#users")

    display_name = request.form.get("display_name", "").strip()
    username = request.form.get("username", "").strip()
    rank_points = request.form.get("rank_points", "").strip()
    zalo_name = request.form.get("zalo_name", "").strip()
    new_password = request.form.get("new_password", "").strip()

    if not display_name or not username:
        flash("Tên hiển thị và username không được để trống.", "danger")
        return redirect_admin("users")

    existing = get_user_by_username(username)
    if existing and existing["id"] != user_id:
        flash("Username này đã tồn tại.", "danger")
        return redirect_admin("users")

    update_data = {
        "display_name": display_name,
        "username": username,
        "zalo_name": zalo_name,
    }

    try:
        update_data["rank_points"] = max(0, int(rank_points))
    except ValueError:
        flash("Điểm rank phải là số.", "danger")
        return redirect_admin("users")

    if new_password:
        if len(new_password) < minimum_password_length():
            flash(f"Mật khẩu mới phải có ít nhất {minimum_password_length()} ký tự.", "danger")
            return redirect(url_for("admin") + "#users")
        update_data["password_hash"] = hash_password(new_password)
        update_data["must_change_password"] = True
        update_data["password_changed_at"] = now_iso()

    db.table("users").update(update_data).eq("id", user_id).execute()
    if new_password:
        try:
            execute_query(
                db.table("password_reset_requests").update({
                    "status": "resolved",
                    "admin_user_id": actor["id"],
                    "admin_note": "Admin đã reset mật khẩu từ danh sách user.",
                    "resolved_at": now_iso(),
                }).eq("user_id", user_id).eq("status", "pending"),
                "close_password_reset_from_user_admin",
            )
        except Exception as exc:
            print(f"close password reset from user admin warning: {exc}")
    changed = ["username", "display_name", "zalo_name", "rank_points"]
    if new_password:
        changed.append("mật khẩu tạm (bắt buộc đổi)")
    log_admin_action(
        "Cập nhật tài khoản",
        "user",
        user_id,
        player.get("username"),
        "Các mục: " + ", ".join(changed),
    )
    flash(f"Đã cập nhật tài khoản {player.get('username')}.", "success")
    return redirect(url_for("admin") + "#users")


@app.route("/admin/player/<user_id>/reset-stats", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("users_edit")
def admin_reset_player_stats(user_id):
    player = get_user(user_id)
    if not player or is_admin_user(player):
        flash("Không tìm thấy player hợp lệ.", "danger")
        return redirect_admin("users")

    db.table("users").update({
        "rank_points": DEFAULT_POINTS,
        "total_matches": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "streak": 0,
    }).eq("id", user_id).execute()

    log_admin_action("Reset chỉ số", "user", user_id, player.get("username"), "Đưa điểm và W-D-L về mặc định.")
    flash("Đã reset chỉ số player.", "success")
    return redirect_admin("users")


@app.route("/admin/player/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("users_delete")
def admin_delete_player(user_id):
    player = get_user(user_id)
    player_label = player.get("username") if player else "Không xác định"
    ok, error = delete_player_safe(user_id)
    if not ok:
        flash(error, "danger")
        return redirect_admin("users")

    log_admin_action("Xóa tài khoản", "user", user_id, player_label, "Đã xóa account và dữ liệu liên quan.")
    flash("Đã xóa account player và dữ liệu liên quan.", "success")
    return redirect_admin("users")




@app.route("/admin/match/<match_id>/delete", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("matches_delete")
def admin_delete_match(match_id):
    actor = current_user()
    lock_token = None
    try:
        lock_token = acquire_ranking_rebuild_lock(actor.get("id"), match_id)
        match = get_match(match_id)
        if not match:
            raise ValueError("Không tìm thấy trận.")

        if match.get("status") == "confirmed":
            rebuild_rankings_after_admin_change(
                match_id,
                {
                    "status": "cancelled",
                    "confirmed_by_id": None,
                    "note": "Admin chuẩn bị xóa trận; đã hoàn tác trong lịch sử.",
                },
                lock_token=lock_token,
                actor_id=actor.get("id"),
            )

        remove_match_dispute_evidence(match_id)
        execute_query(
            db.table("match_rooms").update({
                "status": "cancelled",
                "match_id": None,
                "confirmed_by_id": None,
                "state_expires_at": None,
                "note": "Admin đã xóa trận liên kết.",
                "updated_at": now_iso(),
            }).eq("match_id", match_id),
            "admin_unlink_room_before_delete_match",
            attempts=2,
        )
        execute_query(
            db.table("matches").delete().eq("id", match_id),
            "admin_delete_match_after_rebuild",
        )
        cache_delete("_rz_matches_all", "_rz_rooms_all")
        ttl_cache_delete("rooms_raw")
        log_admin_action(
            "Xóa trận", "match", match_id,
            details=f"Trạng thái cũ: {match.get('status')}; đã phát lại lịch sử trước khi xóa",
        )
        flash("Đã xóa trận và tính lại RP, streak, loss_streak theo lịch sử còn lại.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception as exc:
        app.logger.exception("admin_delete_match failed: %s", exc)
        flash("Không thể xóa trận an toàn; thao tác đã dừng để tránh sai lịch sử.", "danger")
    finally:
        release_ranking_rebuild_lock(lock_token)
    return redirect_admin("matches")


@app.route("/admin/room/<room_id>/cancel", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("rooms_manage")
def admin_cancel_room(room_id):
    room = get_room(room_id)
    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect_admin("rooms")

    db.table("match_rooms").update({
        "status": "cancelled",
        "note": "Admin đã hủy phòng.",
        "state_expires_at": None,
        "updated_at": now_iso(),
    }).eq("id", room_id).execute()

    if room.get("match_id"):
        linked_match = get_match(room.get("match_id"))
        if linked_match and linked_match.get("status") == "confirmed":
            if not reverse_confirmed_match_result(linked_match):
                flash("Không thể hoàn tác RP của trận đã xác nhận; phòng chưa bị hủy.", "danger")
                return redirect_admin("rooms")
        db.table("matches").update({
            "status": "cancelled",
            "delta1": 0,
            "delta2": 0,
            "note": "Admin đã hủy phòng/trận và hoàn tác RP.",
            "updated_at": now_iso(),
        }).eq("id", room["match_id"]).execute()

    log_admin_action("Hủy phòng", "room", room_id, details=f"Trạng thái cũ: {room.get('status')}")
    flash("Đã hủy phòng.", "success")
    return redirect_admin("rooms")


@app.route("/admin/room/<room_id>/delete", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("rooms_manage")
def admin_delete_room(room_id):
    room = get_room(room_id)
    if not room:
        flash("Không tìm thấy phòng.", "danger")
        return redirect_admin("rooms")

    delete_room_safe(room_id)
    log_admin_action("Xóa phòng", "room", room_id, details=f"{room.get('host_name')} vs {room.get('guest_name')}")
    flash("Đã xóa phòng và dữ liệu trận liên quan.", "success")
    return redirect_admin("rooms")


@app.route("/admin/invite/<invite_id>/delete", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("invites_manage")
def admin_delete_invite(invite_id):
    invite = get_invite(invite_id)
    if not invite:
        flash("Không tìm thấy lời mời.", "danger")
        return redirect_admin("rooms")

    db.table("match_invites").delete().eq("id", invite_id).execute()
    log_admin_action("Xóa lời mời", "invite", invite_id, details=f"{invite.get('from_name', '-')} → {invite.get('to_name', '-')}")
    flash("Đã xóa lời mời.", "success")
    return redirect_admin("rooms")



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
