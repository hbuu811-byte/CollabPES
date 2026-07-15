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
from datetime import datetime, timezone, timedelta
from functools import wraps
from collections import Counter
import unicodedata
from threading import Lock, BoundedSemaphore

from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError
from flask import (
    Flask,
    jsonify,
    flash,
    g,
    has_request_context,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from supabase import create_client


load_dotenv()

APP_NAME = "PES 2026"
APP_VERSION = "1.10.66 Hybrid UI"
DEFAULT_POINTS = 1000
DEVICE_COOKIE_NAME = "rankzone_device_id"
COOLDOWN_MINUTES = 3
ONLINE_TIMEOUT_SECONDS = 90
CHAT_COOLDOWN_SECONDS = 5
CHAT_MAX_LENGTH = 200
AVATAR_BUCKET = "avatars"
AVATAR_MAX_BYTES = 8 * 1024 * 1024
AVATAR_OUTPUT_SIZE = 512
AVATAR_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
DISPUTE_EVIDENCE_BUCKET = "dispute-evidence"
DISPUTE_EVIDENCE_MAX_BYTES = 4 * 1024 * 1024
DISPUTE_EVIDENCE_MAX_SIDE = 1600
DISPUTE_EVIDENCE_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

# V1.10.15 - Daily check-in reward economy merged with league logo update.
DAILY_CHECKIN_MIN_ZCOIN = 80
DAILY_CHECKIN_MAX_ZCOIN = 150
GIFT_CODE_DEFAULT_PREFIX = "PES"
GIFT_CODE_MAX_REWARD_ZCOIN = 100000
VN_TIMEZONE = timezone(timedelta(hours=7))

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

INVITE_TIMEOUT_SECONDS = 60
ROOM_READY_TIMEOUT_SECONDS = 60 * 60
RESULT_CONFIRM_TIMEOUT_SECONDS = 60 * 60
REMATCH_TIMEOUT_SECONDS = 60
ROOM_INACTIVITY_TIMEOUT_SECONDS = 60 * 60
ROOM_ABANDON_PENALTY = 20

RANK_K_FACTOR = 32
RANK_SCALE = 400
TEAM_OVR_BASE = 79
TEAM_OVR_WEIGHT = 20

# Rank points system V1.9
BASE_WIN_POINTS = 21
BASE_LOSS_POINTS = -20
PLACEMENT_MATCHES = 10
PLACEMENT_WIN_MULTIPLIER = 1.10
MIN_RANK_ADJUSTED_WIN_POINTS = 19
MAX_RANK_ADJUSTED_WIN_POINTS = 24
MAX_POSITIVE_POINTS_PER_MATCH = 35

# Rank/Tier difficulty system (V1.8.1)
SMART_RANDOM_CORRECT_WEIGHT = 0.70
SMART_RANDOM_STRONGER_WEIGHT = 0.15
SMART_RANDOM_WEAKER_WEIGHT = 0.15
WIN_STREAK_BONUSES = {3: 5, 5: 10, 8: 15, 10: 20}

SUPABASE_PUBLIC_STORAGE_URL = "https://wlnvdfghatgeygecwrqb.supabase.co/storage/v1/object/public/team-logos"

def _league_logo_storage_url(filename):
    return f"{SUPABASE_PUBLIC_STORAGE_URL}/league-logos/{filename}"

# V1.10.18 - League logo aliases/fallbacks.
# Keep several filename candidates because storage filenames may differ between collaborators.
LEAGUE_LOGO_FILE_CANDIDATES = {
    "africa": ["africa.png"],
    "bundesliga": ["bundesliga.png"],
    "europe": ["europe.png"],
    "laliga": ["laliga-ea-sports.png", "laliga.png", "la-liga.png", "la-liga-ea-sports.png"],
    "super_lig": ["super-lig.png", "superlig.png", "süper-lig.png"],
    "serie_bkt": ["serie-bkt.png", "serie-b.png", "serie-b-kt.png"],
    "sky_bet_championship": ["sky-bet-championship.png", "championship.png", "efl-championship.png"],
    "south_america": ["south-america.png", "southamerica.png"],
    "serie_a": ["serie-a.png", "seriea.png"],
    "premier_league": ["premier-league.png", "premierleague.png", "epl.png"],
    "ligue_1": ["ligue-1.png", "ligue1.png", "ligue-1-mcdonalds.png", "ligue-1-uber-eats.png", "france.png"],
}

LEAGUE_LOGO_ALIASES = {
    "africa": "africa",
    "bundesliga": "bundesliga",
    "germany": "bundesliga",
    "german bundesliga": "bundesliga",
    "europe": "europe",
    "uefa": "europe",
    "laliga": "laliga",
    "la liga": "laliga",
    "laliga ea sports": "laliga",
    "la liga ea sports": "laliga",
    "süper lig": "super_lig",
    "super lig": "super_lig",
    "turkish super lig": "super_lig",
    "serie bkt": "serie_bkt",
    "serie b": "serie_bkt",
    "italy serie b": "serie_bkt",
    "sky bet championship": "sky_bet_championship",
    "championship": "sky_bet_championship",
    "efl championship": "sky_bet_championship",
    "south america": "south_america",
    "copa libertadores": "south_america",
    "serie a": "serie_a",
    "italy serie a": "serie_a",
    "premier league": "premier_league",
    "english premier league": "premier_league",
    "epl": "premier_league",
    "ligue 1": "ligue_1",
    "ligue1": "ligue_1",
    "ligue 1 mcdonalds": "ligue_1",
    "ligue 1 mcdonald s": "ligue_1",
    "ligue 1 uber eats": "ligue_1",
    "france ligue 1": "ligue_1",
    "french ligue 1": "ligue_1",
}

def normalize_league_key(league_name):
    raw = str(league_name or "").strip().lower().replace("_", " ").replace("-", " ")
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in raw)
    return " ".join(raw.split())

def get_league_logo_urls(league_name):
    key = normalize_league_key(league_name)
    canonical = LEAGUE_LOGO_ALIASES.get(key)
    if not canonical:
        return []
    return [_league_logo_storage_url(filename) for filename in LEAGUE_LOGO_FILE_CANDIDATES.get(canonical, [])]

def get_league_logo_url(league_name):
    urls = get_league_logo_urls(league_name)
    return urls[0] if urls else ""

def get_league_logo_fallback_urls(league_name):
    urls = get_league_logo_urls(league_name)
    return urls[1:]

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
supabase_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
supabase_anon_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
SUPABASE_REALTIME_ENABLED = (os.getenv("SUPABASE_REALTIME_ENABLED") or "1").strip().lower() not in {"0", "false", "off", "no"}
supabase_key = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or ""
).strip()

db = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Chỉ lấy các cột thật sự cần cho các màn hình đọc nhiều.
# Điều này giảm JSON, Supabase egress, thời gian giải mã và Fast Origin Transfer.
USER_PUBLIC_COLUMNS = ",".join([
    "id", "username", "display_name", "avatar_url", "role", "account_status",
    "admin_level", "rank_points", "wins", "draws", "losses", "total_matches",
    "goals_for", "goals_against", "streak",
    "is_online", "last_seen_at", "matchmaking_cooldown_until", "must_change_password",
    "zcoin_balance", "created_at"
])

# Lưu ý: không chọn cột `mode` ở đây. Trong PostgREST/PostgreSQL, `mode` cũng là
# tên một ordered-set aggregate. Với một số phiên bản PostgREST, chuỗi select bare
# `mode` bị phân tích thành hàm aggregate và phát sinh lỗi 42809 (WITHIN GROUP).
# Luồng hiển thị hiện tại không dùng matches.mode, nên bỏ cột này là an toàn.
MATCH_LIST_COLUMNS = ",".join([
    "id", "player1_id", "player2_id", "score1", "score2", "team1", "team2",
    "status", "winner_id", "loser_id", "delta1", "delta2", "submitted_by_id",
    "note", "created_at", "updated_at"
])


def cache_get(key):
    if not has_request_context():
        return None
    return getattr(g, key, None)


def cache_set(key, value):
    if has_request_context():
        setattr(g, key, value)
    return value


def cache_delete(key):
    if has_request_context() and hasattr(g, key):
        delattr(g, key)


# Cache RAM rất ngắn cho Vercel warm instance. Mục tiêu là gộp các API polling
# cùng lúc, không thay thế Supabase và không giữ dữ liệu lâu.
_ttl_cache = {}
_ttl_cache_lock = Lock()


def ttl_cache_get(key):
    now = time.monotonic()
    with _ttl_cache_lock:
        item = _ttl_cache.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at <= now:
            _ttl_cache.pop(key, None)
            return None
        return value


def ttl_cache_set(key, value, ttl_seconds):
    with _ttl_cache_lock:
        _ttl_cache[key] = (time.monotonic() + max(0.1, float(ttl_seconds)), value)
    return value


def ttl_cache_delete(*keys):
    with _ttl_cache_lock:
        for key in keys:
            _ttl_cache.pop(key, None)


# Giới hạn số kết nối TCP đi Supabase trên cùng một Vercel warm instance.
# Các API polling có thể đổ vào cùng lúc; nếu tất cả cùng mở socket, Linux có thể
# trả [Errno 16] Device or resource busy trước khi request kịp tới Supabase.
_supabase_query_slots = BoundedSemaphore(max(1, int(os.getenv("SUPABASE_MAX_CONCURRENT", "3") or 3)))


def execute_query(query, label="Supabase", attempts=4, delay=0.25):
    """Retry lỗi mạng ngắn hạn và chặn bùng nổ kết nối TCP trên Vercel."""
    last_error = None

    for attempt in range(max(1, attempts)):
        acquired = _supabase_query_slots.acquire(timeout=5)
        if not acquired:
            last_error = RuntimeError("Supabase query queue is busy")
        else:
            try:
                return query.execute()
            except Exception as exc:
                last_error = exc
            finally:
                _supabase_query_slots.release()

        exc = last_error
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
            "query queue is busy",
        ))

        if not transient or attempt >= max(1, attempts) - 1:
            print(f"{label} failed after {attempt + 1} attempt(s): {exc}")
            raise exc

        # Exponential backoff + jitter để các request không retry cùng một nhịp.
        sleep_seconds = delay * (2 ** attempt) + random.uniform(0.05, 0.18)
        time.sleep(sleep_seconds)

    raise last_error



_admin_checked = False


# =========================
# Basic helpers
# =========================
def now_dt():
    return datetime.now(timezone.utc)


def now_iso():
    return now_dt().isoformat()


def future_iso(seconds: int) -> str:
    return (now_dt() + timedelta(seconds=max(0, int(seconds)))).isoformat()


def aware_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def seconds_until(value) -> int:
    dt = aware_utc(parse_dt(value))
    if not dt:
        return 0
    return max(0, int((dt - now_dt()).total_seconds()))


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def format_vn_datetime(value) -> str:
    dt = parse_dt(value)
    if not dt:
        return "-"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    vietnam_time = dt.astimezone(timezone(timedelta(hours=7)))
    return vietnam_time.strftime("%d/%m/%Y %H:%M")


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
        raise ValueError("Ảnh đại diện không được vượt quá 8 MB.")
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


def schedule_achievement_sync(user_ids, match_id=None):
    """Đẩy đồng bộ huy hiệu ra khỏi request xác nhận để giảm thời gian chờ."""
    try:
        from threading import Thread
        ids = [value for value in dict.fromkeys(user_ids or []) if value]
        if not ids:
            return
        def worker():
            try:
                sync_achievements_for_users(ids)
            except Exception as exc:
                print(f"achievement_sync deferred warning match={match_id}: {type(exc).__name__}: {exc}")
        Thread(target=worker, name=f"achievement-sync-{match_id or 'match'}", daemon=True).start()
    except Exception as exc:
        print(f"schedule_achievement_sync warning match={match_id}: {type(exc).__name__}: {exc}")


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
            or (user.get("role") == "admin" and user.get("username") == "admin")
        )
    )


def can_review_room_result(user, room) -> bool:
    """Only the invited opponent can confirm/dispute a submitted room result.

    Admin accounts are powerful elsewhere, but inside a player room an admin who is
    also the host/submitter must not be allowed to confirm their own submitted
    score. A non-participant admin may still help only as a moderation fallback.
    """
    if not user or not room or room.get("status") != "waiting_result_confirm":
        return False
    current_id = str(user.get("id") or "")
    submitted_by_id = str(room.get("submitted_by_id") or "")
    host_id = str(room.get("host_user_id") or "")
    guest_id = str(room.get("guest_user_id") or "")

    if not current_id:
        return False
    if submitted_by_id and current_id == submitted_by_id:
        return False
    if current_id == guest_id:
        return True
    if is_admin_user(user) and current_id not in {host_id, guest_id}:
        return True
    return False




ADMIN_PERMISSION_DEFINITIONS = {
    "view_users": ("Xem người dùng", "Xem danh sách tài khoản và thông tin cơ bản."),
    "approve_users": ("Duyệt tài khoản", "Duyệt hoặc từ chối tài khoản đăng ký mới."),
    "reset_passwords": ("Xử lý quên mật khẩu", "Cấp mật khẩu tạm hoặc từ chối yêu cầu."),
    "edit_users": ("Sửa người dùng", "Khóa/mở khóa, sửa RP, thống kê và trạng thái online."),
    "delete_users": ("Xóa người dùng", "Xóa tài khoản và dữ liệu liên quan."),
    "view_matches": ("Xem trận đấu", "Xem danh sách trận, phòng và thông tin RP."),
    "create_matches": ("Tạo trận thủ công", "Chọn 2 người chơi, nhập tỷ số và cập nhật RP."),
    "edit_matches": ("Sửa trận đấu", "Sửa tỷ số, trạng thái và xác nhận kết quả."),
    "delete_matches": ("Hủy/Xóa trận", "Hủy hoặc xóa trận và tính lại dữ liệu."),
    "manage_rooms": ("Quản lý phòng & lời mời", "Hủy/xóa phòng và lời mời đang chờ."),
    "manage_disputes": ("Xử lý tranh chấp", "Chấp nhận, sửa hoặc hủy tranh chấp."),
    "manage_announcements": ("Quản lý thông báo", "Đăng và xóa thông báo hệ thống."),
    "manage_chat": ("Bật/tắt Chat", "Bật hoặc tắt Chat Sảnh và Chat Phòng."),
    "manage_friendly": ("Bật/tắt Giao hữu", "Bật hoặc khóa tính năng Giao hữu."),
    "manage_gift_codes": ("Quản lý Gift Code", "Tạo và bật/tắt Gift Code."),
    "manage_invite_codes": ("Quản lý mã đăng ký", "Tạo và vô hiệu hóa mã đăng ký."),
    "manage_test_data": ("Tài khoản test & Import", "Tạo tài khoản test và import CSV."),
    "view_logs": ("Xem nhật ký Admin", "Xem lịch sử thao tác của quản trị viên."),
}
ADMIN_PERMISSION_CODES = tuple(ADMIN_PERMISSION_DEFINITIONS.keys())
_admin_permission_cache = {}


def _admin_permission_setting_key(user_id):
    return f"admin_permissions:{str(user_id or '').strip()}"


def _normalize_admin_permissions(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = {}
    if not isinstance(value, dict):
        value = {}
    return {code: bool(value.get(code, False)) for code in ADMIN_PERMISSION_CODES}


def get_admin_permissions(user, force=False):
    if is_owner_user(user):
        return {code: True for code in ADMIN_PERMISSION_CODES}
    if not is_admin_user(user):
        return {code: False for code in ADMIN_PERMISSION_CODES}

    user_id = str((user or {}).get("id") or "")
    now_ts = time.time()
    cached = _admin_permission_cache.get(user_id)
    if not force and cached and cached.get("expires_at", 0) > now_ts:
        return dict(cached.get("value") or {})

    permissions = {code: False for code in ADMIN_PERMISSION_CODES}
    # Giữ tương thích với 2 cột quyền cũ.
    permissions["manage_test_data"] = bool(
        user.get("admin_can_create_test_account") or user.get("admin_can_import_accounts_csv")
    )
    try:
        result = execute_query(
            db.table("system_settings")
            .select("setting_value")
            .eq("setting_key", _admin_permission_setting_key(user_id))
            .limit(1),
            "get_admin_permissions",
            attempts=2,
        )
        rows = result.data or []
        if rows:
            permissions.update(_normalize_admin_permissions(rows[0].get("setting_value")))
    except Exception as exc:
        print(f"get_admin_permissions warning user={user_id}: {type(exc).__name__}: {exc}")

    _admin_permission_cache[user_id] = {"value": dict(permissions), "expires_at": now_ts + 15}
    return permissions


def save_admin_permissions(user_id, permissions):
    normalized = _normalize_admin_permissions(permissions)
    payload = {
        "setting_key": _admin_permission_setting_key(user_id),
        "setting_value": normalized,
        "updated_at": now_iso(),
    }
    execute_query(
        db.table("system_settings").upsert(payload, on_conflict="setting_key"),
        "save_admin_permissions",
    )
    _admin_permission_cache.pop(str(user_id), None)
    return normalized


def has_admin_permission(user, permission_code: str) -> bool:
    if is_owner_user(user):
        return True
    return bool(get_admin_permissions(user).get(permission_code, False))


FRIENDLY_MATCHES_SETTING_KEY = "friendly_matches_enabled"
LOBBY_CHAT_SETTING_KEY = "lobby_chat_enabled"
ROOM_CHAT_SETTING_KEY = "room_chat_enabled"
_friendly_matches_cache = {"value": None, "expires_at": 0.0}
_chat_features_cache = {"value": None, "expires_at": 0.0}


def _setting_to_bool(value, default=True) -> bool:
    """Parse a system_settings value safely from bool/json/text/int."""
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, dict):
        if "enabled" in value:
            return _setting_to_bool(value.get("enabled"), default)
        if "value" in value:
            return _setting_to_bool(value.get("value"), default)
        return bool(default)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on", "enabled", "bật", "bat"}:
            return True
        if lowered in {"false", "0", "no", "n", "off", "disabled", "tắt", "tat"}:
            return False
        try:
            return _setting_to_bool(json.loads(value), default)
        except Exception:
            return bool(default)
    return bool(value)


def friendly_matches_enabled(force=False) -> bool:
    """Global Admin toggle for friendly matches. Defaults to enabled."""
    now = time.time()
    if not force and _friendly_matches_cache["value"] is not None and now < _friendly_matches_cache["expires_at"]:
        return bool(_friendly_matches_cache["value"])
    enabled = True
    if db is not None:
        try:
            result = execute_query(
                db.table("system_settings").select("setting_value,updated_at").eq("setting_key", FRIENDLY_MATCHES_SETTING_KEY).order("updated_at", desc=True).limit(1),
                "load_friendly_matches_enabled",
                attempts=2,
            )
            if result.data:
                enabled = _setting_to_bool(result.data[0].get("setting_value"), True)
            else:
                execute_query(
                    db.table("system_settings").upsert({
                        "setting_key": FRIENDLY_MATCHES_SETTING_KEY,
                        "setting_value": {"enabled": True},
                        "updated_at": now_iso(),
                    }, on_conflict="setting_key"),
                    "seed_friendly_matches_enabled",
                    attempts=2,
                )
        except Exception as exc:
            print(f"friendly_matches_enabled fallback warning: {exc}")
    _friendly_matches_cache.update({"value": enabled, "expires_at": now + 5})
    return bool(enabled)


def set_friendly_matches_enabled(enabled: bool):
    if db is None:
        raise RuntimeError("Chưa cấu hình Supabase.")
    payload = {
        "setting_key": FRIENDLY_MATCHES_SETTING_KEY,
        "setting_value": {"enabled": bool(enabled)},
        "updated_at": now_iso(),
    }
    try:
        execute_query(
            db.table("system_settings").update({
                "setting_value": payload["setting_value"],
                "updated_at": payload["updated_at"],
            }).eq("setting_key", FRIENDLY_MATCHES_SETTING_KEY),
            "update_friendly_matches_enabled",
            attempts=3,
        )
    except Exception as exc:
        print(f"update_friendly_matches_enabled warning: {exc}")
    execute_query(
        db.table("system_settings").upsert(payload, on_conflict="setting_key"),
        "set_friendly_matches_enabled",
        attempts=3,
    )
    _friendly_matches_cache.update({"value": bool(enabled), "expires_at": time.time() + 5})


def chat_features_enabled(force=False):
    """Return global chat feature toggles using one short cached settings query."""
    now = time.time()
    cached = _chat_features_cache.get("value")
    if not force and cached is not None and now < _chat_features_cache.get("expires_at", 0):
        return dict(cached)

    states = {"lobby": True, "room": True}
    if db is not None:
        try:
            result = execute_query(
                db.table("system_settings")
                .select("setting_key,setting_value,updated_at")
                .in_("setting_key", [LOBBY_CHAT_SETTING_KEY, ROOM_CHAT_SETTING_KEY]),
                "load_chat_feature_settings",
                attempts=2,
            )
            found = set()
            for row in result.data or []:
                key = row.get("setting_key")
                found.add(key)
                if key == LOBBY_CHAT_SETTING_KEY:
                    states["lobby"] = _setting_to_bool(row.get("setting_value"), True)
                elif key == ROOM_CHAT_SETTING_KEY:
                    states["room"] = _setting_to_bool(row.get("setting_value"), True)
            missing = []
            if LOBBY_CHAT_SETTING_KEY not in found:
                missing.append({"setting_key": LOBBY_CHAT_SETTING_KEY, "setting_value": {"enabled": True}, "updated_at": now_iso()})
            if ROOM_CHAT_SETTING_KEY not in found:
                missing.append({"setting_key": ROOM_CHAT_SETTING_KEY, "setting_value": {"enabled": True}, "updated_at": now_iso()})
            for payload in missing:
                execute_query(
                    db.table("system_settings").upsert(payload, on_conflict="setting_key"),
                    "seed_chat_feature_setting",
                    attempts=2,
                )
        except Exception as exc:
            print(f"chat_features_enabled fallback warning: {exc}")
    _chat_features_cache.update({"value": dict(states), "expires_at": now + 10})
    return states


def set_chat_feature_enabled(feature: str, enabled: bool):
    if db is None:
        raise RuntimeError("Chưa cấu hình Supabase.")
    key = LOBBY_CHAT_SETTING_KEY if feature == "lobby" else ROOM_CHAT_SETTING_KEY if feature == "room" else None
    if not key:
        raise ValueError("Tính năng chat không hợp lệ.")
    payload = {
        "setting_key": key,
        "setting_value": {"enabled": bool(enabled)},
        "updated_at": now_iso(),
    }
    execute_query(
        db.table("system_settings").upsert(payload, on_conflict="setting_key"),
        "set_chat_feature_enabled",
        attempts=3,
    )
    current = chat_features_enabled(force=False)
    current[feature] = bool(enabled)
    _chat_features_cache.update({"value": current, "expires_at": time.time() + 10})


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
    """Đọc Rank từ Supabase; khi mạng chập chờn dùng cache cũ/DEFAULT_RANKS."""
    now = time.time()
    cached_value = _rank_range_cache.get("value")
    if not force and cached_value is not None and now < _rank_range_cache["expires_at"]:
        return cached_value

    # Không để context processor làm sập toàn bộ HTML chỉ vì cấu hình Rank chưa đọc được.
    fallback = cached_value or _validate_rank_ranges(DEFAULT_RANKS)
    if db is None:
        return fallback

    try:
        result = execute_query(
            db.table("system_settings").select("setting_value").eq("setting_key", RANK_RANGE_SETTING_KEY).limit(1),
            "load_rank_ranges",
            attempts=3,
        )
        if not result.data:
            # Seed là best-effort; trang vẫn dùng DEFAULT_RANKS nếu ghi thất bại.
            try:
                execute_query(
                    db.table("system_settings").upsert({
                        "setting_key": RANK_RANGE_SETTING_KEY,
                        "setting_value": DEFAULT_RANKS,
                        "updated_at": now_iso(),
                    }, on_conflict="setting_key"),
                    "seed_rank_ranges",
                    attempts=2,
                )
            except Exception as exc:
                print(f"seed_rank_ranges warning: {exc}")
            configured = fallback
        else:
            stored = result.data[0].get("setting_value")
            if isinstance(stored, str):
                stored = json.loads(stored)
            configured = _validate_rank_ranges(stored)

        _rank_range_cache.update({"value": configured, "expires_at": now + 60})
        return configured
    except Exception as exc:
        print(f"load_rank_ranges fallback warning: {exc}")
        # Cache fallback ngắn để tránh mỗi request tiếp theo lại mở thêm 3 kết nối.
        _rank_range_cache.update({"value": fallback, "expires_at": now + 15})
        return fallback


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


def get_win_streak_bonus(player, won):
    """Award a one-time bonus when the new streak reaches 3, 5, 8 or 10."""
    if not won:
        return 0
    next_streak = int(player.get("streak", 0) or 0) + 1
    return WIN_STREAK_BONUSES.get(next_streak, 0)


def _rank_adjusted_win_points(winner, loser):
    """Return the V1.9 base win reward before placement/streak bonuses.

    A lower-ranked winner gains +1 per rank level, capped at +24.
    A higher-ranked winner loses 1 point per rank level, floored at +19.
    RP difference inside the same rank is intentionally ignored.
    """
    winner_level = get_rank_level(winner.get("rank_points", 0))
    loser_level = get_rank_level(loser.get("rank_points", 0))
    rank_advantage = loser_level - winner_level
    return max(
        MIN_RANK_ADJUSTED_WIN_POINTS,
        min(MAX_RANK_ADJUSTED_WIN_POINTS, BASE_WIN_POINTS + rank_advantage),
    )


def calculate_deltas(player_a, player_b, score_a: int, score_b: int, team_a=None, team_b=None,
                     team_overall_a=None, team_overall_b=None, team_tier_a=None, team_tier_b=None):
    """Calculate ranked RP using the V1.9 rules.

    Club/Tier, score margin and RP difference inside one rank do not affect RP.
    Draws are neutral (0 RP for both players).
    """
    score_a = int(score_a)
    score_b = int(score_b)

    if score_a == score_b:
        return 0, 0

    a_won = score_a > score_b
    winner = player_a if a_won else player_b
    loser = player_b if a_won else player_a

    winner_matches = int(winner.get("total_matches", 0) or 0)
    loser_matches = int(loser.get("total_matches", 0) or 0)

    # If either participant is still inside the first 10 matches, do not compare
    # rank or RP between the two players.
    if winner_matches < PLACEMENT_MATCHES or loser_matches < PLACEMENT_MATCHES:
        win_points = BASE_WIN_POINTS
    else:
        win_points = _rank_adjusted_win_points(winner, loser)

    # The placement reward belongs to the winner's own first 10 matches.
    if winner_matches < PLACEMENT_MATCHES:
        win_points = round(BASE_WIN_POINTS * PLACEMENT_WIN_MULTIPLIER)

    win_points += get_win_streak_bonus(winner, True)
    win_points = min(MAX_POSITIVE_POINTS_PER_MATCH, max(1, int(win_points)))

    if a_won:
        return enforce_ranked_delta_signs(score_a, score_b, win_points, BASE_LOSS_POINTS)
    return enforce_ranked_delta_signs(score_a, score_b, BASE_LOSS_POINTS, win_points)


def enforce_ranked_delta_signs(score1, score2, delta1, delta2):
    """Guarantee winner-positive / loser-negative RP for ranked matches.

    This is a final guard against bad/old rows or unexpected form/admin flows that
    could otherwise store 0 RP for a non-draw result.
    """
    score1 = _safe_int(score1)
    score2 = _safe_int(score2)
    delta1 = _safe_int(delta1)
    delta2 = _safe_int(delta2)

    if score1 == score2:
        return 0, 0

    if score1 > score2:
        if delta1 <= 0:
            delta1 = BASE_WIN_POINTS
        if delta2 >= 0:
            delta2 = BASE_LOSS_POINTS
    else:
        if delta1 >= 0:
            delta1 = BASE_LOSS_POINTS
        if delta2 <= 0:
            delta2 = BASE_WIN_POINTS

    return int(delta1), int(delta2)


def display_delta_with_result_guard(score_for, score_against, stored_delta):
    """Display fallback for older confirmed rows that were saved with invalid 0 RP."""
    score_for = _safe_int(score_for)
    score_against = _safe_int(score_against)
    stored_delta = _safe_int(stored_delta)
    if score_for == score_against:
        return 0
    if score_for > score_against and stored_delta <= 0:
        return BASE_WIN_POINTS
    if score_for < score_against and stored_delta >= 0:
        return BASE_LOSS_POINTS
    return stored_delta

TEAM_LOGO_BUCKET = "team-logos"
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
        db.table("users").select(USER_PUBLIC_COLUMNS).eq("id", user_id).limit(1),
        "get_user",
    )
    return result.data[0] if result.data else None


def get_users_by_ids(user_ids):
    """Lấy nhiều người chơi trong một request Supabase thay vì gọi get_user tuần tự."""
    ids = [str(value) for value in dict.fromkeys(user_ids or []) if value]
    if not ids:
        return {}
    mapped, missing = {}, []
    for user_id in ids:
        cached = ttl_cache_get(f"user:{user_id}")
        if cached is not None:
            mapped[user_id] = dict(cached)
        else:
            missing.append(user_id)
    if missing:
        result = execute_query(
            db.table("users").select(USER_PUBLIC_COLUMNS).in_("id", missing),
            "get_users_by_ids",
            attempts=2,
        )
        for row in result.data or []:
            item = dict(row)
            user_id = str(item.get("id") or "")
            if user_id:
                mapped[user_id] = item
                ttl_cache_set(f"user:{user_id}", item, 8)
    return mapped


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
                db.table("users").select(USER_PUBLIC_COLUMNS).order("rank_points", desc=True),
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
    # Tài khoản admin không bị giới hạn thiết bị; admin vẫn là player.
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


def list_admin_player_picker(limit=1000):
    """Danh sách player tối thiểu cho form chọn người, không tải thiết bị/IP/admin khác."""
    require_db()
    safe_limit = max(50, min(int(limit or 1000), 2000))
    result = execute_query(
        db.table("users")
        .select(USER_PUBLIC_COLUMNS)
        .eq("role", "player")
        .eq("account_status", "approved")
        .order("display_name")
        .limit(safe_limit),
        "list_admin_player_picker",
    )
    return result.data or []


def decorate_matches(rows):
    """Gắn tên/avatar cho danh sách trận đã có mà không tải lại bảng matches."""
    matches = [dict(row) for row in (rows or [])]
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


def list_recent_matches(limit=80):
    """Query riêng cho Admin: chỉ lấy số trận cần hiển thị, tránh tải cả bảng."""
    require_db()
    safe_limit = max(20, min(int(limit or 80), 200))
    result = execute_query(
        db.table("matches")
        .select(MATCH_LIST_COLUMNS)
        .order("created_at", desc=True)
        .limit(safe_limit),
        "list_recent_matches",
    )
    return decorate_matches(result.data or [])


def list_admin_active_rooms(limit=80):
    """Chỉ lấy phòng còn hoạt động cho Admin thay vì toàn bộ lịch sử phòng."""
    require_db()
    statuses = ["waiting_ready", "playing", "friendly_playing", "waiting_result_confirm", "disputed"]
    result = execute_query(
        db.table("match_rooms")
        .select("*")
        .in_("status", statuses)
        .order("created_at", desc=True)
        .limit(max(20, min(int(limit or 80), 200))),
        "list_admin_active_rooms",
    )
    rooms = []
    for raw in (result.data or []):
        room = expire_room_if_needed(dict(raw))
        enrich_room(room)
        rooms.append(room)
    return rooms


def list_admin_pending_invites(limit=100):
    """Chỉ lấy lời mời pending cho trang Admin."""
    require_db()
    result = execute_query(
        db.table("match_invites")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(max(20, min(int(limit or 100), 300))),
        "list_admin_pending_invites",
    )
    rows = []
    for raw in (result.data or []):
        invite = expire_invite_if_needed(dict(raw))
        if invite.get("status") == "pending":
            rows.append(invite)
    users = users_map()
    for invite in rows:
        invite["from_name"] = users.get(invite.get("from_user_id"), {}).get("display_name", "Unknown")
        invite["to_name"] = users.get(invite.get("to_user_id"), {}).get("display_name", "Unknown")
    return rows


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
        shared = ttl_cache_get("matches_raw")
        if shared is None:
            query = db.table("matches").select(MATCH_LIST_COLUMNS).order("created_at", desc=True)
            result = execute_query(query, "list_matches")
            shared = result.data or []
            ttl_cache_set("matches_raw", shared, 8)
        cached = [dict(row) for row in shared]
        cache_set("_rz_matches_all", cached)

    matches = [dict(m) for m in cached if not status or m.get("status") == status]
    return decorate_matches(matches)


def list_user_matches_page(user_id, page=1, page_size=20):
    """Phân trang thật tại Supabase; lấy thêm 1 dòng để biết còn trang sau."""
    require_db()
    safe_page = max(1, int(page or 1))
    safe_size = max(5, min(int(page_size or 20), 50))
    offset = (safe_page - 1) * safe_size
    query = (
        db.table("matches")
        .select(MATCH_LIST_COLUMNS)
        .or_(f"player1_id.eq.{user_id},player2_id.eq.{user_id}")
        .order("created_at", desc=True)
        .range(offset, offset + safe_size)
    )
    result = execute_query(query, "list_user_matches_page")
    rows = [dict(row) for row in (result.data or [])]
    has_next = len(rows) > safe_size
    return decorate_matches(rows[:safe_size]), has_next


def list_user_matches(user_id, limit=200):
    """Chỉ đọc lịch sử của một người thay vì tải toàn bộ bảng matches."""
    require_db()
    safe_limit = max(20, min(int(limit or 200), 500))
    query = (
        db.table("matches")
        .select(MATCH_LIST_COLUMNS)
        .or_(f"player1_id.eq.{user_id},player2_id.eq.{user_id}")
        .order("created_at", desc=True)
        .limit(safe_limit)
    )
    result = execute_query(query, "list_user_matches")
    rows = [dict(row) for row in (result.data or [])]
    users = users_map()
    for match in rows:
        p1 = users.get(match.get("player1_id"), {})
        p2 = users.get(match.get("player2_id"), {})
        match["player1_name"] = p1.get("display_name", "Unknown")
        match["player2_name"] = p2.get("display_name", "Unknown")
        match["player1_avatar_url"] = p1.get("avatar_url")
        match["player2_avatar_url"] = p2.get("avatar_url")
    return rows


def match_status_label(status):
    return MATCH_STATUS_LABELS.get(status, str(status or "-").replace("_", " ").title())


def decorate_match_for_view(match, viewer_id=None):
    item = dict(match or {})
    item["status_label"] = match_status_label(item.get("status"))
    item["created_at_display"] = format_vn_datetime(item.get("created_at"))
    item["is_cancelled"] = item.get("status") == "cancelled"
    # Default score keeps database orientation (player1 - player2).
    # When a viewer_id is provided, it is overwritten below to viewer perspective
    # so profile/history rows remain consistent with the THẮNG/THUA badge.
    item["score_display"] = (
        "Không tính"
        if item["is_cancelled"]
        else f'{item.get("score1") if item.get("score1") is not None else "-"} - {item.get("score2") if item.get("score2") is not None else "-"}'
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
        stored_my_delta = int((item.get("delta1") if as_player1 else item.get("delta2")) or 0)
        item["my_delta"] = stored_my_delta
        item["my_delta_was_guarded"] = False
        item["opponent_id"] = item.get("player2_id") if as_player1 else item.get("player1_id")
        item["opponent_name"] = item.get("player2_name") if as_player1 else item.get("player1_name")
        item["my_avatar_url"] = item.get("player1_avatar_url") if as_player1 else item.get("player2_avatar_url")
        item["opponent_avatar_url"] = item.get("player2_avatar_url") if as_player1 else item.get("player1_avatar_url")
        item["my_achievement"] = item.get("player1_achievement") if as_player1 else item.get("player2_achievement")
        item["opponent_achievement"] = item.get("player2_achievement") if as_player1 else item.get("player1_achievement")
        item["my_team"] = item.get("team1") if as_player1 else item.get("team2")
        item["opponent_team"] = item.get("team2") if as_player1 else item.get("team1")

        # Profile/history UI displays the viewed player on the left, so the score
        # must also be displayed from that same perspective. Otherwise a match where
        # the viewed player is player2 can look like "6 - 2" while showing THUA.
        item["score_display"] = (
            "Không tính"
            if item["is_cancelled"]
            else f'{my_score if my_score is not None else "-"} - {opponent_score if opponent_score is not None else "-"}'
        )

        if item.get("status") == "confirmed" and my_score is not None and opponent_score is not None:
            guarded_delta = display_delta_with_result_guard(my_score, opponent_score, stored_my_delta)
            item["my_delta_was_guarded"] = guarded_delta != stored_my_delta
            item["my_delta"] = guarded_delta
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
        # Kể cả đã có người trong phòng, mọi phòng chờ đều dùng chung mốc
        # 60 phút không hoạt động thay vì tự hủy sớm sau vài phút.
        return None
    if status == "waiting_result_confirm":
        return updated + timedelta(seconds=RESULT_CONFIRM_TIMEOUT_SECONDS)
    if status == "confirmed" and note in {REMATCH_HOST_READY_NOTE, REMATCH_GUEST_READY_NOTE}:
        return updated + timedelta(seconds=REMATCH_TIMEOUT_SECONDS)
    return None


def room_inactivity_expiry_dt(room):
    """Close active rooms after 60 minutes without a meaningful update."""
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
    return last_activity + timedelta(seconds=ROOM_INACTIVITY_TIMEOUT_SECONDS)


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
    """Đóng phòng và áp dụng phạt đúng một lần cho trận Xếp hạng bỏ dở."""
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
    penalty_delta = apply_room_abandon_penalty(offender_id)
    match_id = room.get("match_id")
    if match_id:
        match_update = {
            "status": "cancelled",
            "note": reason,
            "updated_at": now_iso(),
        }
        if offender_role == "host":
            match_update.update({"delta1": penalty_delta or -ROOM_ABANDON_PENALTY, "delta2": 0})
        else:
            match_update.update({"delta1": 0, "delta2": penalty_delta or -ROOM_ABANDON_PENALTY})
        execute_query(
            db.table("matches").update(match_update).eq("id", match_id),
            "mark_timeout_match_cancelled",
        )

    offender_name = room.get("host_name") if offender_role == "host" else room.get("guest_name")
    other_id = room.get("guest_user_id") if offender_role == "host" else room.get("host_user_id")
    create_user_notification(
        offender_id,
        "⏱️ Trận bị tính là bỏ trận",
        f"Bạn bị trừ {ROOM_ABANDON_PENALTY} RP vì {reason.lower()}",
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
                "note": "Phòng tự đóng sau 60 phút không hoạt động.",
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
                            "note": "Phòng tự đóng sau 60 phút không hoạt động; không áp dụng phạt RP.",
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


ROOM_ACTION_COLUMNS = ",".join([
    "id", "host_user_id", "guest_user_id", "guest_ready", "status", "note",
    "match_id", "match_mode", "friendly_tier", "team_tier",
    "host_team", "guest_team", "host_score", "guest_score",
    "submitted_by_id", "confirmed_by_id", "state_expires_at", "updated_at",
])


def get_room_action_state(room_id):
    """Room tối giản dành cho POST thao tác; không enrich, không tải toàn bộ BXH."""
    result = execute_query(
        db.table("match_rooms").select(ROOM_ACTION_COLUMNS).eq("id", room_id).limit(1),
        "get_room_action_state",
        attempts=2,
    )
    return dict(result.data[0]) if result.data else None


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
    room["host_streak_badge"] = get_streak_badge(room["host_streak"])
    room["has_guest"] = bool(room.get("guest_user_id"))
    room["guest_name"] = guest.get("display_name", "Đang chờ đối thủ") if room["has_guest"] else "Đang chờ đối thủ"
    room["guest_avatar_url"] = guest.get("avatar_url") if room["has_guest"] else None
    room["guest_achievement"] = guest.get("featured_achievement") if room["has_guest"] else None
    room["guest_points"] = guest.get("rank_points", 0) if room["has_guest"] else 0
    room["guest_rank_info"] = get_rank_info(guest.get("rank_points", 0)) if room["has_guest"] else None
    room["guest_rank"] = get_rank_display(guest.get("rank_points", 0)) if room["has_guest"] else "Chưa có người chơi"
    room["guest_streak"] = int(guest.get("streak", 0) or 0) if room["has_guest"] else 0
    room["guest_streak_badge"] = get_streak_badge(room["guest_streak"]) if room["has_guest"] else None
    if room.get("host_team"):
        info = get_db_team_info(room.get("host_team")) or {}
        room["host_team_overall"] = room.get("host_team_overall") or info.get("overall") or get_team_overall(room.get("host_team"))
        room["host_team_logo_url"] = room.get("host_team_logo_url") or info.get("logo_url")
        room["host_team_league"] = room.get("host_team_league") or info.get("league") or ""
        room["host_team_league_logo"] = get_league_logo_path(room["host_team_league"])
        room["host_team_tier"] = info.get("tier") or get_team_tier(room.get("host_team"))
        room["host_team_total_stats"] = int(info.get("total_stats") or 0)
    else:
        room["host_team_total_stats"] = 0
    if room.get("guest_team"):
        info = get_db_team_info(room.get("guest_team")) or {}
        room["guest_team_overall"] = room.get("guest_team_overall") or info.get("overall") or get_team_overall(room.get("guest_team"))
        room["guest_team_logo_url"] = room.get("guest_team_logo_url") or info.get("logo_url")
        room["guest_team_league"] = room.get("guest_team_league") or info.get("league") or ""
        room["guest_team_league_logo"] = get_league_logo_path(room["guest_team_league"])
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
    room["host_team_league_logo"] = room.get("host_team_league_logo") or get_league_logo_path(room["host_team_league"])
    room["guest_team_league_logo"] = room.get("guest_team_league_logo") or get_league_logo_path(room["guest_team_league"])
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
    query = db.table("chat_messages").select("id,user_id,scope,room_id,message,created_at").eq("scope", scope)

    if room_id:
        query = query.eq("room_id", room_id)
    else:
        query = query.is_("room_id", "null")

    result = execute_query(query.order("created_at", desc=True).limit(limit), "list_chat_messages")
    messages = list(reversed(result.data or []))
    users = users_map()
    return [enrich_chat_message(message, users) for message in messages]



def user_can_chat(user_id, scope="global", room_id=None):
    query = db.table("chat_messages").select("id,created_at").eq("user_id", user_id).eq("scope", scope)

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


def users_have_other_active_game(user_ids, exclude_room_id=None):
    """Kiểm tra xung đột của cả hai người bằng 2 query đã lọc trực tiếp ở Supabase."""
    ids = [str(value) for value in dict.fromkeys(user_ids or []) if value]
    if not ids:
        return False
    try:
        csv_ids = ",".join(ids)
        room_query = (
            db.table("match_rooms")
            .select("id,host_user_id,guest_user_id,status,note")
            .in_("status", ["waiting_ready", "playing", "friendly_playing", "waiting_result_confirm", "disputed"])
            .or_(f"host_user_id.in.({csv_ids}),guest_user_id.in.({csv_ids})")
        )
        if exclude_room_id:
            room_query = room_query.neq("id", exclude_room_id)
        room_result = execute_query(room_query.limit(1), "rematch_other_active_rooms", attempts=2)
        if room_result.data or []:
            return True

        match_result = execute_query(
            db.table("matches")
            .select("id,player1_id,player2_id,status")
            .in_("status", ["playing", "waiting_confirm", "processing_result"])
            .or_(f"player1_id.in.({csv_ids}),player2_id.in.({csv_ids})")
            .limit(1),
            "rematch_other_active_matches",
            attempts=2,
        )
        return bool(match_result.data or [])
    except Exception as exc:
        print(f"users_have_other_active_game warning: {exc}")
        return any(active_room_for_user(uid, exclude_room_id=exclude_room_id) or active_match_for_user(uid) for uid in ids)
    return False

def active_room_for_user(user_id, exclude_room_id=None):
    rooms = list_rooms()
    for room in rooms:
        if exclude_room_id and str(room.get("id")) == str(exclude_room_id):
            continue
        if room_is_active(room) and user_id in [room.get("host_user_id"), room.get("guest_user_id")]:
            return room
    return None


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
    """Create the first owner only when it does not exist.

    Never reset an existing owner's password or role during a cold start. The
    initial password must come from an environment variable instead of source.
    """
    global _admin_checked
    if _admin_checked or db is None:
        return

    admin = get_user_by_username("admin")
    if not admin:
        initial_password = (os.getenv("INITIAL_ADMIN_PASSWORD") or "").strip()
        if len(initial_password) < 8:
            print("ensure_admin skipped: set INITIAL_ADMIN_PASSWORD (minimum 8 characters) to create the first owner.")
            _admin_checked = True
            return
        execute_query(
            db.table("users").insert({
                "username": "admin",
                "password_hash": hash_password(initial_password),
                "display_name": "Admin",
                "role": "admin",
                "admin_level": "owner",
                "account_status": "approved",
                "zalo_name": "Admin",
                "rank_points": DEFAULT_POINTS,
            }),
            "ensure_admin_create",
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
            return redirect(url_for("login"))

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
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

@app.before_request
def before_request():
    try:
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
            "ADMIN_CAPS": get_admin_permissions(user) if user else {},
            "get_rank_name": get_rank_name,
            "get_rank_info": get_rank_info,
            "get_rank_display": get_rank_display,
            "get_team_overall": get_team_overall,
            "get_team_tier": get_team_tier,
            "TEAM_COUNT": TEAM_COUNT,
            "APP_VERSION": APP_VERSION,
            "RANKS": load_rank_ranges(),
            "format_vn_datetime": format_vn_datetime,
            "SUPABASE_PUBLIC_URL": supabase_url or "",
            "SUPABASE_PUBLIC_ANON_KEY": supabase_anon_key or "",
            "SUPABASE_REALTIME_ENABLED": bool(SUPABASE_REALTIME_ENABLED and supabase_url and supabase_anon_key),
            "lobby_chat_enabled": chat_features_enabled().get("lobby", True),
            "room_chat_enabled": chat_features_enabled().get("room", True),
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
        "ADMIN_CAPS": get_admin_permissions(user) if user else {},
        "get_rank_name": get_rank_name,
        "get_rank_info": get_rank_info,
        "get_rank_display": get_rank_display,
        "get_team_overall": get_team_overall,
        "get_team_tier": get_team_tier,
        "TEAM_COUNT": TEAM_COUNT,
        "APP_VERSION": APP_VERSION,
        "RANKS": load_rank_ranges(),
        "format_vn_datetime": format_vn_datetime,
        "SUPABASE_PUBLIC_URL": supabase_url or "",
        "SUPABASE_PUBLIC_ANON_KEY": supabase_anon_key or "",
        "SUPABASE_REALTIME_ENABLED": bool(SUPABASE_REALTIME_ENABLED and supabase_url and supabase_anon_key),
        "lobby_chat_enabled": chat_features_enabled().get("lobby", True),
        "room_chat_enabled": chat_features_enabled().get("room", True),
        "pending_invite_count": pending_count,
        "incoming_invites": incoming,
        "active_room": active_room,
        "cooldown_text": cooldown,
        "active_announcement": announcement,
        "unread_notifications": unread_notifications,
    }


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

    cache_key = f"api_pending_invites:{user['id']}"
    cached = ttl_cache_get(cache_key)
    if cached is not None:
        return jsonify(cached)

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
        payload = {"invites": data}
        ttl_cache_set(cache_key, payload, 3)
        return jsonify(payload)
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

    # Phòng trống do chủ phòng tạo để mời người khác không được ép chuyển trang.
    # Chỉ tự động vào phòng khi đối thủ đã tham gia hoặc người dùng là khách.
    auto_redirect = bool(has_opponent or is_guest)

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

ROOM_STATE_LIGHT_FIELDS = ",".join([
    "id", "host_user_id", "guest_user_id", "status", "host_team", "guest_team",
    "guest_ready", "host_score", "guest_score", "note", "state_expires_at",
    "updated_at", "match_id", "match_mode"
])


def get_room_state_light(room_id):
    """Lấy đúng dữ liệu phục vụ polling; không users_map, CLB, rank, achievement hay tranh chấp."""
    result = execute_query(
        db.table("match_rooms").select(ROOM_STATE_LIGHT_FIELDS).eq("id", room_id).limit(1),
        "get_room_state_light",
        attempts=2,
    )
    room = dict(result.data[0]) if result.data else None
    if not room:
        return None
    # Vẫn giữ cơ chế hết hạn, nhưng chỉ làm giàu các cờ nhỏ cần cho client.
    expire_room_if_needed(room)
    note = room.get("note") or ""
    room["rematch_host_ready"] = note == REMATCH_HOST_READY_NOTE
    room["rematch_guest_ready"] = note == REMATCH_GUEST_READY_NOTE
    room["rematch_host_declined"] = note == REMATCH_HOST_DECLINED_NOTE
    room["rematch_guest_declined"] = note == REMATCH_GUEST_DECLINED_NOTE
    room["rematch_declined"] = room["rematch_host_declined"] or room["rematch_guest_declined"]
    room["rematch_expired"] = note == REMATCH_EXPIRED_NOTE
    room["timeout_seconds"] = seconds_until(room.get("state_expires_at"))
    return room


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

    state_key = "|".join([
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

        return redirect(url_for("dashboard"))

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
        confirm_password = request.form.get("confirm_password", "").strip()

        if user.get("password_hash") != hash_password(current_password):
            flash("Mật khẩu tạm hoặc mật khẩu hiện tại không đúng.", "danger")
            return redirect(url_for("change_password"))
        if len(new_password) < 6:
            flash("Mật khẩu mới phải có ít nhất 6 ký tự.", "danger")
            return redirect(url_for("change_password"))
        if new_password != confirm_password:
            flash("Hai lần nhập mật khẩu mới không khớp.", "danger")
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
        return redirect(url_for("dashboard"))

    return render_template("change_password.html", force_change=bool(user.get("must_change_password")), auth_only=True)


@app.route("/register", methods=["GET", "POST"])
def register():
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

        if len(password) < 6:
            flash("Mật khẩu phải có ít nhất 6 ký tự.", "danger")
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
    flash("Đã đăng xuất.", "success")
    return redirect(url_for("login"))


# =========================
# Chat / Announcements
# =========================
@app.route("/chat")
@login_required
def lobby_chat():
    if not chat_features_enabled().get("lobby", True):
        flash("Chat Sảnh đang được Admin tạm ẩn.", "warning")
        return redirect(url_for("dashboard"))
    return render_template("chat.html", messages=list_chat_messages("global", limit=20))


@app.route("/chat/send", methods=["POST"])
@login_required
def send_global_chat():
    if not chat_features_enabled().get("lobby", True):
        flash("Chat Sảnh đang được Admin tạm ẩn.", "warning")
        return redirect(url_for("dashboard"))
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
    if not chat_features_enabled().get("lobby", True):
        return jsonify({"ok": False, "error": "chat_disabled", "messages": []}), 403
    messages = list_chat_messages("global", limit=20)
    return jsonify({"ok": True, "messages": messages})


@app.route("/api/chat/global/status")
@login_required
def api_global_chat_status():
    if not chat_features_enabled().get("lobby", True):
        return jsonify({"ok": True, "disabled": True, "unread_count": 0, "latest_created_at": None})
    """Trả payload nhỏ: chỉ số tin chưa đọc và mốc mới nhất, không gửi lại 100 bản ghi."""
    user = current_user()
    since = (request.args.get("since") or "").strip()
    limit = 100
    query = (
        db.table("chat_messages")
        .select("id,user_id,created_at")
        .eq("scope", "global")
        .is_("room_id", "null")
        .order("created_at", desc=False)
        .limit(limit)
    )
    if since:
        query = query.gt("created_at", since)
    result = execute_query(query, "api_global_chat_status", attempts=2)
    rows = result.data or []
    latest_created_at = rows[-1].get("created_at") if rows else None
    unread_count = sum(1 for row in rows if row.get("user_id") != user.get("id"))
    return jsonify({
        "ok": True,
        "unread_count": unread_count,
        "latest_created_at": latest_created_at,
        "limit_reached": len(rows) >= limit,
    })


@app.route("/api/room/<room_id>/chat")
@login_required
def api_room_chat(room_id):
    if not chat_features_enabled().get("room", True):
        return jsonify({"ok": False, "error": "chat_disabled", "messages": []}), 403
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
    if not chat_features_enabled().get("room", True):
        flash("Chat Phòng đang được Admin tạm ẩn.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))
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
@admin_permission_required("manage_announcements")
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
    ttl_cache_delete("api_current_announcement")
    log_admin_action("Đăng thông báo", "announcement", announcement_id, title[:40], message[:220])

    flash("Đã đăng thông báo admin.", "success")
    return redirect_admin("system")


@app.route("/admin/announcement/clear", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_announcements")
def admin_clear_announcement():
    db.table("admin_announcements").update({"is_active": False}).eq("is_active", True).execute()
    ttl_cache_delete("api_current_announcement")
    log_admin_action("Tắt thông báo", "announcement", details="Đã tắt toàn bộ thông báo đang hoạt động.")
    flash("Đã tắt thông báo admin.", "success")
    return redirect_admin("system")


@app.route("/admin/settings/friendly-matches", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_friendly")
def admin_toggle_friendly_matches():
    raw_value = (request.form.get("friendly_matches_enabled") or "0").strip().lower()
    enabled = raw_value in {"1", "true", "on", "yes", "enable", "enabled"}
    set_friendly_matches_enabled(enabled)
    log_admin_action(
        "Cập nhật trận giao hữu",
        "system",
        target_label="friendly_matches_enabled",
        details="Bật trận giao hữu" if enabled else "Tắt trận giao hữu",
    )
    flash("Đã bật trận giao hữu." if enabled else "Đã tắt trận giao hữu.", "success")
    return redirect_admin("system")


@app.route("/admin/settings/chat", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_chat")
def admin_toggle_chat_features():
    feature = (request.form.get("feature") or "").strip().lower()
    raw_value = (request.form.get("enabled") or "0").strip().lower()
    enabled = raw_value in {"1", "true", "on", "yes", "enable", "enabled"}
    if feature not in {"lobby", "room"}:
        flash("Loại Chat không hợp lệ.", "danger")
        return redirect_admin("system")
    set_chat_feature_enabled(feature, enabled)
    label = "Chat Sảnh" if feature == "lobby" else "Chat Phòng"
    log_admin_action(
        "Cập nhật tính năng Chat",
        "system",
        target_label=f"{feature}_chat_enabled",
        details=f"{'Bật' if enabled else 'Tắt'} {label}",
    )
    flash(f"Đã {'bật' if enabled else 'tạm ẩn'} {label}.", "success")
    return redirect_admin("system")


@app.route("/api/announcement/current")
@login_required
def api_current_announcement():
    cache_key = "api_current_announcement"
    cached = ttl_cache_get(cache_key)
    if cached is not None:
        return jsonify(cached)
    announcement = get_active_announcement()
    if not announcement:
        payload = {"ok": True, "announcement": None}
        ttl_cache_set(cache_key, payload, 15)
        return jsonify(payload)

    payload = {
        "ok": True,
        "announcement": {
            "id": announcement["id"],
            "title": announcement["title"],
            "message": announcement["message"],
            "created_at": announcement["created_at"],
        },
    }
    ttl_cache_set(cache_key, payload, 15)
    return jsonify(payload)


@app.route("/api/chat/global/send", methods=["POST"])
@login_required
def api_send_global_chat():
    if not chat_features_enabled().get("lobby", True):
        return jsonify({"ok": False, "error": "Chat Sảnh đang được Admin tạm ẩn."}), 403
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
def api_admin_send_announcement():
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
    ttl_cache_delete("api_current_announcement")
    log_admin_action("Đăng thông báo", "announcement", announcement_id, title, message)

    return jsonify({"ok": True})


@app.route("/api/online-count")
@login_required
def api_online_count():
    cache_key = "api_online_count"
    cached = ttl_cache_get(cache_key)
    if cached is not None:
        return jsonify(cached)
    players = list_players(include_admin=False)
    payload = {"ok": True, "online_count": sum(1 for player in players if player.get("is_online"))}
    ttl_cache_set(cache_key, payload, 20)
    return jsonify(payload)


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
    """BXH công khai với cache CDN 45 giây cho khách và cache RAM ngắn cho dữ liệu."""
    user = current_user()
    query_raw = (request.args.get("q") or "").strip()
    rank_filter = (request.args.get("rank") or "all").strip()

    # Chỉ cache HTML cho khách chưa đăng nhập để tuyệt đối không lẫn dữ liệu cá nhân.
    guest_cache_key = f"public_ranking_html:{query_raw.casefold()}:{rank_filter}"
    if not user:
        cached_html = ttl_cache_get(guest_cache_key)
        if cached_html is not None:
            response = make_response(cached_html)
            response.headers["Cache-Control"] = "public, s-maxage=45, stale-while-revalidate=120"
            response.headers["X-Rankzone-Cache"] = "HIT"
            return response

    try:
        player_rows = ttl_cache_get("ranking_players_v11044")
        if player_rows is None:
            player_rows = list_players()
            ttl_cache_set("ranking_players_v11044", player_rows, 45)
    except Exception as exc:
        print(f"ranking list_players warning: {exc}")
        player_rows = []

    query = query_raw.casefold()
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
        confirmed_matches = ttl_cache_get("ranking_confirmed_matches_v11044")
        if confirmed_matches is None:
            confirmed_matches = list_matches(status="confirmed")
            ttl_cache_set("ranking_confirmed_matches_v11044", confirmed_matches, 45)
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

    if is_htmx_request():
        response = make_response(render_template(
            "partials/ranking_results.html",
            players=filtered,
            current_player=current_player,
            current_position=current_position,
            q=query_raw,
            rank_filter=rank_filter,
        ))
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "HX-Request"
        return response

    template_name = "ranking.html" if user else "public_ranking.html"
    html = render_template(
        template_name,
        players=filtered,
        current_player=current_player,
        current_position=current_position,
        q=query_raw,
        rank_filter=rank_filter,
    )
    response = make_response(html)
    if not user:
        ttl_cache_set(guest_cache_key, html, 45)
        response.headers["Cache-Control"] = "public, s-maxage=45, stale-while-revalidate=120"
        response.headers["X-Rankzone-Cache"] = "MISS"
    else:
        response.headers["Cache-Control"] = "private, no-store"
    return response

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
        cache_delete("_rz_current_user")
        cache_delete("_rz_users_map")
        cache_delete("_rz_players_all")
        cache_delete("_rz_matches_all")
        ttl_cache_delete("players_raw", "rooms_raw", "achievement_map", f"user:{user.get('id')}")
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


# =========================
# ZCOIN / Daily check-in helpers
# =========================
def _profile_feature_setup_state():
    return {
        "setup_required": True,
        "balance": 0,
        "transactions": [],
        "can_claim": False,
        "claimed_today": False,
        "streak": 0,
        "total_checkins": 0,
        "today_reward": None,
        "today_key": datetime.now(VN_TIMEZONE).date().isoformat(),
        "reward_min": DAILY_CHECKIN_MIN_ZCOIN,
        "reward_max": DAILY_CHECKIN_MAX_ZCOIN,
    }


def get_profile_reward_state(user_id):
    """Read ZCOIN/check-in state without breaking profile if SQL is not installed yet."""
    state = _profile_feature_setup_state()
    state["setup_required"] = False
    today_key = datetime.now(VN_TIMEZONE).date().isoformat()
    state["today_key"] = today_key

    try:
        user_row = get_user(user_id) or {}
        state["balance"] = _safe_int(user_row.get("zcoin_balance"), 0)
    except Exception as exc:
        print(f"get_profile_reward_state balance warning: {exc}")
        state["setup_required"] = True
        return state

    try:
        tx_result = execute_query(
            db.table("zcoin_transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(12),
            "list_zcoin_transactions",
        )
        state["transactions"] = tx_result.data or []
    except Exception as exc:
        print(f"list_zcoin_transactions warning: {exc}")
        state["setup_required"] = True
        return state

    try:
        today_result = execute_query(
            db.table("daily_checkins")
            .select("*")
            .eq("user_id", user_id)
            .eq("checkin_date", today_key)
            .limit(1),
            "get_today_checkin",
        )
        today_row = (today_result.data or [None])[0]
        state["claimed_today"] = bool(today_row)
        if today_row:
            state["today_reward"] = _safe_int(today_row.get("reward_zcoin"), 0)
            state["streak"] = _safe_int(today_row.get("streak_count"), 0)

        latest_result = execute_query(
            db.table("daily_checkins")
            .select("*")
            .eq("user_id", user_id)
            .order("checkin_date", desc=True)
            .limit(1),
            "get_latest_checkin",
        )
        latest_row = (latest_result.data or [None])[0]
        if latest_row and not today_row:
            state["streak"] = _safe_int(latest_row.get("streak_count"), 0)

        all_result = execute_query(
            db.table("daily_checkins")
            .select("id")
            .eq("user_id", user_id),
            "count_daily_checkins",
        )
        state["total_checkins"] = len(all_result.data or [])
        state["can_claim"] = not state["claimed_today"]
    except Exception as exc:
        print(f"get_profile_reward_state checkin warning: {exc}")
        state["setup_required"] = True

    return state


# =========================
# Shop shell + Gift code helpers (V1.10.23)
# =========================
def normalize_gift_code(raw_code):
    """Normalize gift code safely for DB lookup/create."""
    code = str(raw_code or "").strip().upper()
    code = "".join(ch for ch in code if ch.isalnum() or ch in {"-", "_"})
    return code[:40]


def generate_gift_code(prefix=GIFT_CODE_DEFAULT_PREFIX):
    safe_prefix = normalize_gift_code(prefix) or GIFT_CODE_DEFAULT_PREFIX
    alphabet = string.ascii_uppercase + string.digits
    return f"{safe_prefix}-" + "".join(secrets.choice(alphabet) for _ in range(8))


def list_gift_codes(limit=80):
    try:
        result = execute_query(
            db.table("gift_codes")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit),
            "list_gift_codes",
            attempts=2,
        )
        codes = result.data or []
        now = now_dt()
        for code in codes:
            code["is_expired"] = False
            expires_at = aware_utc(parse_dt(code.get("expires_at"))) if code.get("expires_at") else None
            if expires_at:
                code["is_expired"] = expires_at < now
            max_redemptions = code.get("max_redemptions")
            code["is_sold_out"] = bool(max_redemptions is not None and int(code.get("redeemed_count") or 0) >= int(max_redemptions or 0))
        return codes, False
    except Exception as exc:
        print(f"list_gift_codes warning: {exc}")
        return [], True


def list_gift_code_redemptions(limit=80):
    try:
        result = execute_query(
            db.table("gift_code_redemptions")
            .select("*")
            .order("redeemed_at", desc=True)
            .limit(limit),
            "list_gift_code_redemptions",
            attempts=2,
        )
        rows = result.data or []
        users = users_map()
        for row in rows:
            user = users.get(row.get("user_id"), {})
            row["user_name"] = user.get("display_name") or user.get("username") or "Unknown"
            row["username"] = user.get("username") or "-"
        return rows, False
    except Exception as exc:
        print(f"list_gift_code_redemptions warning: {exc}")
        return [], True



# Profile banner assets for Shop (V1.10.36).
# V1.10.36 opens purchase + inventory ownership for profile banner items.
PROFILE_BANNER_SHOP_ITEMS = [
    {
        "code": "profile_banner_locker_room",
        "name": "Phòng Thay Đồ Elite",
        "rarity": "Thường",
        "rarity_slug": "common",
        "price": 300,
        "file": "shop/profile_banners/profile_banner_locker_room.png",
        "icon": "shop/profile_banner_icons/profile_banner_locker_room_icon.png",
        "desc": "Không gian phòng thay đồ cao cấp, sạch sẽ và chuyên nghiệp cho hồ sơ của bạn.",
    },
    {
        "code": "profile_banner_tactical_master",
        "name": "Bậc Thầy Chiến Thuật",
        "rarity": "Hiếm",
        "rarity_slug": "rare",
        "price": 700,
        "file": "shop/profile_banners/profile_banner_tactical_master.png",
        "icon": "shop/profile_banner_icons/profile_banner_tactical_master_icon.png",
        "desc": "Bản đồ chiến thuật số với cảm hứng huấn luyện đỉnh cao trên sân cỏ hiện đại.",
    },
    {
        "code": "profile_banner_neon_derby",
        "name": "Sân Đấu Neon",
        "rarity": "Sử Thi",
        "rarity_slug": "epic",
        "price": 1400,
        "file": "shop/profile_banners/profile_banner_neon_derby.png",
        "icon": "shop/profile_banner_icons/profile_banner_neon_derby_icon.png",
        "desc": "Bầu không khí derby rực sáng với ánh tím xanh nổi bật và cảm giác cực cháy.",
    },
    {
        "code": "profile_banner_trophy_gallery",
        "name": "Hành Lang Vinh Quang",
        "rarity": "Huyền Thoại",
        "rarity_slug": "legendary",
        "price": 2600,
        "file": "shop/profile_banners/profile_banner_trophy_gallery.png",
        "icon": "shop/profile_banner_icons/profile_banner_trophy_gallery_icon.png",
        "desc": "Phòng trưng bày danh hiệu sang trọng dành cho những người chơi thích chất vương giả.",
    },
    {
        "code": "profile_banner_coronation",
        "name": "Đăng Quang Hoàng Kim",
        "rarity": "Tuyệt Phẩm",
        "rarity_slug": "masterpiece",
        "price": 4500,
        "file": "shop/profile_banners/profile_banner_coronation.png",
        "icon": "shop/profile_banner_icons/profile_banner_coronation_icon.png",
        "desc": "Khoảnh khắc đăng quang trên bục vàng, nổi bật như một nhà vô địch thực thụ.",
    },
]


def profile_banner_shop_items():
    items = []
    for item in PROFILE_BANNER_SHOP_ITEMS:
        prepared = dict(item)
        prepared.setdefault("item_type", "profile_banner")
        prepared.setdefault("is_featured", True)
        items.append(prepared)
    return items


def all_shop_items():
    return profile_banner_shop_items()


def featured_shop_items():
    # Hiện 5 banner đầu tiên trong tab Nổi bật để người chơi thấy vật phẩm thật ngay khi vào Shop.
    return [item for item in all_shop_items() if item.get("is_featured")][:5]


def get_shop_item_by_code(item_code):
    target = str(item_code or "").strip()
    if not target:
        return None
    return next((item for item in all_shop_items() if item.get("code") == target), None)


def list_user_inventory(user_id):
    """Read owned Shop items. If SQL is missing, fail softly so Shop still loads."""
    if not user_id:
        return [], False
    try:
        result = execute_query(
            db.table("user_inventory")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True),
            "list_user_inventory",
            attempts=2,
        )
        return result.data or [], False
    except Exception as exc:
        print(f"list_user_inventory warning: {exc}")
        return [], True


def user_inventory_codes(user_id):
    items, setup_required = list_user_inventory(user_id)
    return {row.get("item_code") for row in items if row.get("item_code")}, setup_required


def get_equipped_profile_banner(user_id):
    """Return the equipped profile banner for a user. Uses existing user_inventory.is_equipped column."""
    if not user_id:
        return None
    try:
        result = execute_query(
            db.table("user_inventory")
            .select("*")
            .eq("user_id", user_id)
            .eq("item_type", "profile_banner")
            .eq("is_equipped", True)
            .limit(1),
            "get_equipped_profile_banner",
            attempts=2,
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        print(f"get_equipped_profile_banner warning: {exc}")
        return None


def shop_shell_sections():
    """Shop tab structure. Featured/Decor now use real profile banner items."""
    return [
        {
            "key": "featured",
            "icon": "🔥",
            "title": "Nổi bật",
            "subtitle": "Trang chủ Cửa Hàng",
            "description": "Các vật phẩm thật đang được đề xuất sẽ được trưng bày tại đây để người chơi mua nhanh bằng ZCOIN.",
            "items": ["Banner nổi bật", "Vật phẩm mới", "Đề xuất", "Giới hạn", "Gift Code"],
        },
        {
            "key": "decor",
            "icon": "🎨",
            "title": "Trang trí",
            "subtitle": "Khung avatar, banner, màu nickname, danh hiệu",
            "description": "Khu làm đẹp hồ sơ, tên hiển thị và nhận diện người chơi trong toàn hệ thống. Banner hồ sơ đã mở bán thử nghiệm bằng ZCOIN.",
            "items": ["Hồ sơ", "Banner", "Khung Avatar", "Aura", "Màu Nickname", "Danh hiệu", "Chat", "Emoji"],
        },
        {
            "key": "utility",
            "icon": "🧰",
            "title": "Tiện ích",
            "subtitle": "Các quyền đổi thông tin và mở rộng tài khoản",
            "description": "Khu tiện ích tài khoản. Các vật phẩm thật sẽ được thêm dần ở những bản sau.",
            "items": ["Đổi tên", "Đổi slogan", "Đổi Avatar", "Đổi CLB", "Reset thống kê", "Slot đội hình"],
        },
        {
            "key": "lucky",
            "icon": "🎁",
            "title": "Lucky Box",
            "subtitle": "Khung chuẩn bị cho hòm quà và vé quay",
            "description": "Khu hòm quà, vé quay, pity và lịch sử quay sẽ phát triển sau khi Shop/Kho đồ ổn định.",
            "items": ["Hòm Đồng", "Hòm Bạc", "Hòm Vàng", "Hòm VIP", "Vé quay", "Pity", "Lịch sử quay"],
        },
    ]


def get_shop_section_by_key(tab_key):
    sections = shop_shell_sections()
    return next((section for section in sections if section.get("key") == tab_key), None)




@app.route("/profile/daily-checkin", methods=["POST"])
@login_required
def claim_daily_checkin_route():
    user = current_user()
    user_id = user.get("id")
    try:
        result = execute_query(
            db.rpc("claim_daily_checkin", {"p_user_id": user_id}),
            "claim_daily_checkin_rpc",
        )
        payload = result.data
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        payload = payload or {}

        if not payload.get("ok"):
            return redirect(url_for("profile", user_id=user_id, daily_result="already") + "#checkin")

        ttl_cache_delete(f"user:{user_id}", "players_raw")
        cache_delete("_rz_current_user")
        reward = _safe_int(payload.get("reward"), 0)
        streak = _safe_int(payload.get("streak"), 0)
        balance_after = _safe_int(payload.get("balance_after"), 0)
        return redirect(
            url_for(
                "profile",
                user_id=user_id,
                daily_result="success",
                reward=reward,
                streak=streak,
                balance=balance_after,
            ) + "#checkin"
        )
    except Exception as exc:
        print(f"claim_daily_checkin_route error: {exc}")
        flash("Không thể điểm danh lúc này. Hãy kiểm tra SQL V1.10.15 đã chạy thành công chưa.", "danger")
        return redirect(url_for("profile", user_id=user_id) + "#checkin")


@app.route("/profile/<user_id>")
@login_required
def profile(user_id):
    user = get_user(user_id)
    if not user:
        flash("Không tìm thấy player.", "danger")
        return redirect(url_for("players"))

    viewer = current_user()
    page = max(1, request.args.get("page", 1, type=int) or 1)
    page_size = 20
    # Phân trang ngay tại Supabase: mỗi lần chỉ lấy 20 trận + 1 dòng kiểm tra trang sau.
    page_rows, has_next = list_user_matches_page(user_id, page=page, page_size=page_size)
    matches = [decorate_match_for_view(match, user_id) for match in page_rows]
    history_pagination = {
        "page": page,
        "page_size": page_size,
        "has_prev": page > 1,
        "has_next": has_next,
        "prev_page": page - 1,
        "next_page": page + 1,
    }

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

    # Dữ liệu tổng hợp hồ sơ cần nhiều hơn 20 trận của trang hiện tại.
    # V1.10.57 đã chuyển lịch sử sang phân trang Supabase nhưng bỏ quên biến raw dùng
    # cho đội yêu thích, đối thủ thường gặp và H2H, gây NameError khi mở Profile.
    player_matches_raw = list_user_matches(user_id, limit=200)
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
            for match in player_matches_raw
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

    is_own_profile = viewer.get("id") == user_id
    reward_state = get_profile_reward_state(user_id) if is_own_profile else _profile_feature_setup_state()
    daily_checkin_event = {
        "status": request.args.get("daily_result", ""),
        "reward": _safe_int(request.args.get("reward"), 0),
        "streak": _safe_int(request.args.get("streak"), 0),
        "balance": _safe_int(request.args.get("balance"), reward_state.get("balance", 0)),
    }
    user["equipped_profile_banner"] = get_equipped_profile_banner(user_id)

    if is_htmx_request():
        return render_template(
            "partials/profile_history.html",
            player=user,
            matches=matches,
            history_pagination=history_pagination,
        )

    return render_template(
        "profile.html",
        player=user,
        matches=matches,
        form=form,
        h2h=h2h,
        can_invite=can_invite,
        activity=activity,
        reward_state=reward_state,
        daily_checkin_event=daily_checkin_event,
        history_pagination=history_pagination,
    )



# =========================
# Shop shell / Inventory / Gift Code (V1.10.23)
# =========================
@app.route("/shop")
@login_required
def shop():
    user = current_user()
    user_id = user.get("id")
    sections = shop_shell_sections()
    tab_keys = [section.get("key") for section in sections]
    active_tab = (request.args.get("tab") or "featured").strip().lower()
    if active_tab not in {*tab_keys, "gift-code"}:
        active_tab = "featured"
    active_section = get_shop_section_by_key(active_tab)
    shop_tabs = [
        {"key": section.get("key"), "icon": section.get("icon"), "title": section.get("title")}
        for section in sections
    ] + [{"key": "gift-code", "icon": "🎟️", "title": "Gift Code"}]
    gift_result = {
        "status": request.args.get("gift_result", ""),
        "reward": _safe_int(request.args.get("reward"), 0),
        "balance": _safe_int(request.args.get("balance"), _safe_int(user.get("zcoin_balance"), 0)),
        "code": request.args.get("code", ""),
    }
    purchase_result = {
        "status": request.args.get("purchase_result", ""),
        "item": request.args.get("item", ""),
        "balance": _safe_int(request.args.get("balance"), _safe_int(user.get("zcoin_balance"), 0)),
    }
    owned_item_codes, inventory_setup_required = user_inventory_codes(user_id)
    return render_template(
        "shop.html",
        sections=sections,
        shop_tabs=shop_tabs,
        active_tab=active_tab,
        active_section=active_section,
        gift_result=gift_result,
        purchase_result=purchase_result,
        inventory_setup_required=inventory_setup_required,
        owned_item_codes=owned_item_codes,
        featured_items=featured_shop_items(),
        profile_banner_items=profile_banner_shop_items(),
    )


@app.route("/shop/buy/<item_code>", methods=["POST"])
@login_required
def buy_shop_item_route(item_code):
    user = current_user()
    user_id = user.get("id")
    tab = (request.form.get("tab") or request.args.get("tab") or "featured").strip().lower()
    item = get_shop_item_by_code(item_code)
    if not item:
        flash("Vật phẩm này không tồn tại hoặc chưa được mở bán.", "danger")
        return redirect(url_for("shop", tab=tab))

    try:
        result = execute_query(
            db.rpc(
                "buy_shop_item",
                {
                    "p_user_id": user_id,
                    "p_item_code": item.get("code"),
                    "p_price": _safe_int(item.get("price"), 0),
                    "p_item_name": item.get("name"),
                    "p_item_type": item.get("item_type", "profile_banner"),
                    "p_item_rarity": item.get("rarity"),
                    "p_item_image": item.get("file"),
                    "p_item_icon": item.get("icon"),
                    "p_metadata": {
                        "rarity_slug": item.get("rarity_slug"),
                        "desc": item.get("desc"),
                        "source": "shop_profile_banner_v1_10_36",
                    },
                },
            ),
            "buy_shop_item_rpc",
        )
        payload = result.data
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        payload = payload or {}

        if not payload.get("ok"):
            error_messages = {
                "item_not_available": "Vật phẩm này chưa được mở bán.",
                "already_owned": "Bạn đã sở hữu vật phẩm này rồi. Hãy vào Kho đồ để xem.",
                "not_enough_zcoin": "Bạn chưa đủ ZCOIN để mua vật phẩm này.",
                "user_not_found": "Không tìm thấy tài khoản mua vật phẩm.",
                "invalid_price": "Giá vật phẩm không hợp lệ.",
            }
            flash(error_messages.get(payload.get("error"), "Không thể mua vật phẩm lúc này."), "danger")
            return redirect(url_for("shop", tab=tab))

        ttl_cache_delete(f"user:{user_id}", "players_raw")
        cache_delete("_rz_current_user")
        flash(f"Đã mua {item.get('name')} thành công! Vật phẩm đã được đưa vào Kho đồ.", "success")
        return redirect(
            url_for(
                "shop",
                tab=tab,
                purchase_result="success",
                item=item.get("name"),
                balance=_safe_int(payload.get("balance_after"), 0),
            )
        )
    except Exception as exc:
        print(f"buy_shop_item_route error: {exc}")
        flash("Không thể mua vật phẩm. Hãy kiểm tra đã chạy SQL V1.10.36 chưa.", "danger")
        return redirect(url_for("shop", tab=tab))


@app.route("/inventory")
@login_required
def inventory():
    user = current_user()
    items, setup_required = list_user_inventory(user.get("id"))
    profile_banners = [item for item in items if item.get("item_type") == "profile_banner"]
    equipped_profile_banner = next((item for item in profile_banners if item.get("is_equipped")), None)
    return render_template(
        "inventory.html",
        inventory_items=items,
        profile_banner_inventory=profile_banners,
        equipped_profile_banner=equipped_profile_banner,
        inventory_setup_required=setup_required,
    )


@app.route("/inventory/equip/<inventory_id>", methods=["POST"])
@login_required
def equip_inventory_item_route(inventory_id):
    user = current_user()
    user_id = user.get("id")
    try:
        result = execute_query(
            db.table("user_inventory")
            .select("*")
            .eq("id", inventory_id)
            .eq("user_id", user_id)
            .limit(1),
            "equip_inventory_fetch_item",
            attempts=2,
        )
        rows = result.data or []
        item = rows[0] if rows else None
        if not item:
            flash("Không tìm thấy vật phẩm trong Kho đồ của bạn.", "danger")
            return redirect(url_for("inventory"))

        if item.get("item_type") != "profile_banner":
            flash("Vật phẩm này chưa hỗ trợ trang bị.", "warning")
            return redirect(url_for("inventory"))

        execute_query(
            db.table("user_inventory")
            .update({"is_equipped": False, "updated_at": now_iso()})
            .eq("user_id", user_id)
            .eq("item_type", "profile_banner"),
            "equip_inventory_clear_profile_banners",
            attempts=2,
        )
        execute_query(
            db.table("user_inventory")
            .update({"is_equipped": True, "updated_at": now_iso()})
            .eq("id", inventory_id)
            .eq("user_id", user_id),
            "equip_inventory_set_profile_banner",
            attempts=2,
        )
        ttl_cache_delete(f"user:{user_id}", "players_raw")
        cache_delete("_rz_current_user")
        flash(f"Đã trang bị {item.get('item_name') or 'banner hồ sơ'} vào hồ sơ.", "success")
        return redirect(url_for("inventory"))
    except Exception as exc:
        print(f"equip_inventory_item_route error: {exc}")
        flash("Không thể trang bị vật phẩm lúc này. Hãy kiểm tra bảng user_inventory đã có cột is_equipped.", "danger")
        return redirect(url_for("inventory"))


@app.route("/inventory/unequip/profile-banner", methods=["POST"])
@login_required
def unequip_profile_banner_route():
    user = current_user()
    user_id = user.get("id")
    try:
        execute_query(
            db.table("user_inventory")
            .update({"is_equipped": False, "updated_at": now_iso()})
            .eq("user_id", user_id)
            .eq("item_type", "profile_banner"),
            "unequip_profile_banner",
            attempts=2,
        )
        ttl_cache_delete(f"user:{user_id}", "players_raw")
        cache_delete("_rz_current_user")
        flash("Đã gỡ banner hồ sơ đang sử dụng.", "success")
        return redirect(url_for("inventory"))
    except Exception as exc:
        print(f"unequip_profile_banner_route error: {exc}")
        flash("Không thể gỡ banner lúc này.", "danger")
        return redirect(url_for("inventory"))


@app.route("/gift-code/redeem", methods=["POST"])
@login_required
def redeem_gift_code_route():
    user = current_user()
    user_id = user.get("id")
    code = normalize_gift_code(request.form.get("gift_code"))
    if not code:
        flash("Hãy nhập gift code.", "warning")
        return redirect(url_for("shop", tab="gift-code"))

    try:
        result = execute_query(
            db.rpc("redeem_gift_code", {"p_user_id": user_id, "p_code": code}),
            "redeem_gift_code_rpc",
        )
        payload = result.data
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        payload = payload or {}

        if not payload.get("ok"):
            reason_messages = {
                "code_not_found": "Gift code không tồn tại.",
                "inactive": "Gift code này đã bị tắt.",
                "expired": "Gift code này đã hết hạn.",
                "sold_out": "Gift code này đã hết lượt sử dụng.",
                "already_redeemed": "Bạn đã sử dụng gift code này rồi.",
                "user_not_found": "Không tìm thấy tài khoản nhận thưởng.",
                "unsupported_reward": "Loại phần thưởng của gift code chưa được hỗ trợ.",
            }
            flash(reason_messages.get(payload.get("error"), "Không thể đổi gift code này."), "danger")
            return redirect(url_for("shop", tab="gift-code"))

        ttl_cache_delete(f"user:{user_id}", "players_raw")
        cache_delete("_rz_current_user")
        reward = _safe_int(payload.get("reward_zcoin"), 0)
        balance_after = _safe_int(payload.get("balance_after"), 0)
        return redirect(url_for("shop", tab="gift-code", gift_result="success", reward=reward, balance=balance_after, code=code))
    except Exception as exc:
        print(f"redeem_gift_code_route error: {exc}")
        flash("Không thể đổi gift code lúc này. Hãy kiểm tra SQL V1.10.23 đã chạy thành công chưa.", "danger")
        return redirect(url_for("shop", tab="gift-code"))


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

    return render_template("room_detail.html", room=room, friendly_tiers=get_available_team_tiers())


def room_view_context(room, room_action_message=None, room_action_category=None):
    return {
        "room": room,
        "friendly_tiers": get_available_team_tiers(),
        "friendly_matches_enabled": friendly_matches_enabled(force=True),
        "room_chat_enabled": chat_features_enabled().get("room", True),
        "room_action_message": room_action_message,
        "room_action_category": room_action_category,
    }


def is_room_fragment_request():
    return (
        request.headers.get("HX-Request", "").lower() == "true"
        or request.headers.get("X-RZ-Fragment", "") == "1"
    )


def room_action_response(room_id, message, category="success", fallback="room_detail"):
    if is_room_fragment_request() and category == "success":
        response = make_response("", 204)
        response.headers["X-RZ-Refresh-Room"] = "1"
        response.headers["X-RZ-Message"] = str(message or "")[:240]
        return response
    if is_room_fragment_request():
        return render_room_dynamic_state(room_id, message, category)
    flash(message, category)
    if fallback == "rooms":
        return redirect(url_for("rooms"))
    if fallback == "dashboard":
        return redirect(url_for("dashboard"))
    return redirect(url_for("room_detail", room_id=room_id))


def render_room_dynamic_state(room_id, message=None, category="success"):
    room = get_room(room_id)
    if not room:
        return '<div id="roomDynamicState" class="panel">Không tìm thấy phòng.</div>', 404
    return render_template(
        "partials/room_dynamic_state.html",
        **room_view_context(room, message, category),
    )


@app.route("/room/<room_id>/state-fragment")
@login_required
def room_state_fragment(room_id):
    user = current_user()
    room = get_room(room_id)
    if not room:
        return '<div id="roomDynamicState" class="panel">Không tìm thấy phòng.</div>', 404
    if user["id"] not in [room["host_user_id"], room["guest_user_id"]] and not is_admin_user(user):
        return '<div id="roomDynamicState" class="panel">Bạn không thuộc phòng này.</div>', 403
    response = make_response(render_template("partials/room_dynamic_state.html", **room_view_context(room)))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


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
                "note": (
                    f"Tạo tự động bằng {SMART_RANDOM_MODE}. "
                    f"Power score {result.get('power_score_a', 0):.2f} vs "
                    f"{result.get('power_score_b', 0):.2f}. Host XP x{HOST_XP_FACTOR:.2f}."
                ),
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

    flash(
        f'Smart Random: {result["team_a"]} ({result.get("league_a") or "Không rõ giải"}) vs '
        f'{result["team_b"]} ({result.get("league_b") or "Không rõ giải"}). '
        'Hai CLB đã được quay. Chúc hai người thi đấu vui vẻ!',
        "success",
    )
    return redirect(url_for("room_detail", room_id=room_id))


@app.route("/room/<room_id>/reroll-friendly", methods=["POST"])
@login_required
def room_reroll_friendly(room_id):
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

    if not is_ranked_room(room):
        flash("Trận giao hữu không nhập kết quả, không tính điểm và không ảnh hưởng chuỗi thắng/thua.", "warning")
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
        execute_query(
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

    if not is_ranked_room(room):
        flash("Chỉ trận Xếp hạng Rank mới được xác nhận kết quả và cập nhật chuỗi thắng/thua.", "warning")
        return redirect(url_for("room_detail", room_id=room_id))

    match = get_match(room["match_id"])
    if not match:
        flash("Không tìm thấy trận.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    try:
        delta1, delta2 = apply_match_result(match)
        execute_query(
            db.table("match_rooms").update({
                "status": "confirmed",
                "confirmed_by_id": user["id"],
                "note": "Khách đã xác nhận kết quả.",
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("id", room_id).eq("status", "waiting_result_confirm"),
            "confirm_result_room",
        )
    except ValueError as exc:
        print(f"room_confirm_result validation room={room_id} match={match.get('id')}: {exc}")
        flash(str(exc), "warning")
        return redirect(url_for("room_detail", room_id=room_id))
    except Exception as exc:
        print(f"room_confirm_result ERROR room={room_id} match={match.get('id')}: {type(exc).__name__}: {exc}")
        flash("Không thể xác nhận kết quả do lỗi kết nối dữ liệu. Điểm chưa được xử lý thêm; vui lòng thử lại sau vài giây.", "danger")
        return redirect(url_for("room_detail", room_id=room_id))

    flash(f"Đã xác nhận. Chủ phòng: {int(delta1):+d}, Khách: {int(delta2):+d}. Hai người có thể bấm Đá tiếp.", "success")
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


def apply_match_result(match, host_user_id=None):
    """Apply one ranked result exactly once with clear validation and recovery.

    The match row is claimed by changing its status to ``processing_result``.
    A repeated click cannot apply RP twice, even when requests overlap.
    """
    if not match or not match.get("id"):
        raise ValueError("Thiếu dữ liệu trận đấu.")
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

    players = get_users_by_ids([player1_id, player2_id])
    player1 = players.get(str(player1_id))
    player2 = players.get(str(player2_id))
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

        delta1, delta2 = calculate_deltas(
            player1, player2, score1, score2,
            match.get("team1"), match.get("team2"),
            match.get("team1_overall"), match.get("team2_overall"),
            match.get("team1_tier"), match.get("team2_tier"),
        )
        delta1, delta2 = _safe_int(delta1), _safe_int(delta2)

        # The 0.95 coefficient belongs to the actual room host, not implicitly player1.
        host_user_id = host_user_id or match.get("host_user_id")
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
        if str(host_user_id or "") == str(player1_id):
            delta1 = _safe_int(apply_host_xp_factor(delta1, match.get("host_xp_factor", HOST_XP_FACTOR)))
        elif str(host_user_id or "") == str(player2_id):
            delta2 = _safe_int(apply_host_xp_factor(delta2, match.get("host_xp_factor", HOST_XP_FACTOR)))

        # Final safety guard: a non-draw ranked match must never save +0/0 RP
        # for the loser or non-positive RP for the winner.
        delta1, delta2 = enforce_ranked_delta_signs(score1, score2, delta1, delta2)

        update_player_after_match(player1, delta1, score1, score2)
        update_player_after_match(player2, delta2, score2, score1)

        execute_query(
            db.table("matches").update({
                "delta1": int(delta1),
                "delta2": int(delta2),
                "status": "confirmed",
                "note": "Đã xác nhận.",
                "updated_at": now_iso(),
            }).eq("id", match["id"]).eq("status", "processing_result"),
            "finalize_match_result",
        )
        cache_delete("_rz_matches_all")
        cache_delete("_rz_players_all")
        cache_delete("_rz_users_map")
        ttl_cache_delete("players_raw", "rooms_raw", "achievement_map", f"user:{player1_id}", f"user:{player2_id}")
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

    # Achievement không được phép chặn phản hồi Xác nhận. Chạy hậu kỳ best-effort.
    schedule_achievement_sync([player1_id, player2_id], match.get("id"))
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

    match = get_match(dispute.get("match_id"))
    if not match or match.get("status") != "disputed":
        raise ValueError("Trận đấu không còn ở trạng thái tranh chấp.")

    score1 = int(score1)
    score2 = int(score2)
    if score1 < 0 or score2 < 0:
        raise ValueError("Tỉ số không được âm.")

    if score1 > score2:
        winner_id, loser_id = match.get("player1_id"), match.get("player2_id")
    elif score2 > score1:
        winner_id, loser_id = match.get("player2_id"), match.get("player1_id")
    else:
        winner_id = loser_id = None

    final_note = (resolution_note or "Tranh chấp đã được xử lý và kết quả được công nhận.").strip()[:500]
    # Không chuyển thẳng sang confirmed trước khi tính RP.
    # Một số database đang đặt matches.delta1/delta2 là NOT NULL, nên luôn giữ 0 tạm thời
    # trong lúc chuẩn bị; apply_match_result sẽ claim sang processing_result rồi ghi delta thật.
    execute_query(
        db.table("matches").update({
            "score1": score1,
            "score2": score2,
            "winner_id": winner_id,
            "loser_id": loser_id,
            "status": "waiting_confirm",
            "delta1": 0,
            "delta2": 0,
            "note": final_note,
            "updated_at": now_iso(),
        }).eq("id", match.get("id")).eq("status", "disputed"),
        "prepare_dispute_resolution_match",
    )

    execute_query(
        db.table("match_rooms").update({
            "host_score": score1,
            "guest_score": score2,
            "status": "confirmed",
            "confirmed_by_id": resolved_by_id,
            "note": final_note,
            "state_expires_at": None,
            "updated_at": now_iso(),
        }).eq("id", dispute.get("room_id")),
        "finish_dispute_resolution_room",
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
        }).eq("id", dispute.get("id")),
        "finish_match_dispute",
    )

    # Chỉ áp dụng kết quả của đúng trận tranh chấp này; không reset toàn bộ BXH.
    resolved_match = get_match(match.get("id")) or {}
    delta1, delta2 = apply_match_result(resolved_match)
    db.table("matches").update({
        "note": final_note,
        "updated_at": now_iso(),
    }).eq("id", match.get("id")).execute()

    users = users_map()
    p1_name = users.get(match.get("player1_id"), {}).get("display_name", "Player 1")
    p2_name = users.get(match.get("player2_id"), {}).get("display_name", "Player 2")
    title = "✅ Tranh chấp đã được xử lý"
    message = f"Trận {p1_name} {score1} - {score2} {p2_name}: {final_note}"
    create_notifications_for_users(
        [match.get("player1_id"), match.get("player2_id")],
        title,
        message,
        f"/room/{dispute.get('room_id')}",
        "dispute_resolved",
    )
    return delta1, delta2


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
        return False, "Không được xóa tài khoản admin."

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


# =========================
# Admin
# =========================
def redirect_admin(tab="overview"):
    return redirect(url_for("admin") + f"#{tab}")


def is_htmx_request():
    """Nhận diện request HTMX; backend vẫn dùng cùng logic xác thực và truy vấn dữ liệu."""
    return request.headers.get("HX-Request", "").lower() == "true"


def htmx_redirect(location):
    response = make_response("", 204)
    response.headers["HX-Redirect"] = location
    return response


@app.route("/admin")
@login_required
@admin_required
def admin():
    user = current_user()
    admin_caps = get_admin_permissions(user)
    owner = is_owner_user(user)

    needs_full_user_admin = owner or any(admin_caps.get(code) for code in (
        "view_users", "approve_users", "reset_passwords", "edit_users", "delete_users",
    ))
    needs_player_picker = bool(admin_caps.get("create_matches") or admin_caps.get("manage_test_data"))
    needs_matches = any(admin_caps.get(code) for code in (
        "view_matches", "create_matches", "edit_matches", "delete_matches", "manage_disputes",
    ))
    needs_rooms = bool(admin_caps.get("manage_rooms"))

    if needs_full_user_admin:
        admin_users = decorate_admin_users(list_all_users())
        admin_users.sort(key=lambda item: (
            0 if item.get("duplicate_ips") else 1,
            (item.get("duplicate_ips") or [item.get("latest_ip") or "~"])[0],
            (item.get("username") or "").lower(),
        ))
        players = [item for item in admin_users if item.get("role") == "player"]
    elif needs_player_picker:
        admin_users = []
        players = list_admin_player_picker()
    else:
        admin_users = []
        players = []

    # Chỉ đưa các tài khoản có admin_level=admin vào khu phân quyền.
    # Owner hiện tại luôn toàn quyền nên không cần render một card rỗng hoặc công tắc quyền.
    admins = [
        item for item in admin_users
        if owner and item.get("admin_level") == "admin"
    ]
    pending_users = [item for item in players if item.get("account_status") == "pending"] if admin_caps.get("approve_users") else []

    all_matches = list_recent_matches(80) if needs_matches else []
    all_rooms = list_admin_active_rooms(80) if needs_rooms else []
    pending_disputes = (
        [decorate_match_dispute(item, all_matches) for item in list_match_disputes("pending")]
        if admin_caps.get("manage_disputes") else []
    )
    password_reset_requests = list_password_reset_requests("pending") if admin_caps.get("reset_passwords") else []
    audit_logs = list_admin_activity_logs() if admin_caps.get("view_logs") else []

    if admin_caps.get("manage_gift_codes"):
        gift_codes, gift_code_setup_required = list_gift_codes()
        gift_redemptions, gift_redemption_setup_required = list_gift_code_redemptions()
        gift_code_setup_required = gift_code_setup_required or gift_redemption_setup_required
    else:
        gift_codes, gift_redemptions, gift_code_setup_required = [], [], False

    duplicate_ip_groups = build_duplicate_ip_groups(admin_users) if admin_caps.get("view_users") else []
    duplicate_ip_user_count = len({
        str(account.get("id"))
        for group in duplicate_ip_groups
        for account in group.get("accounts", [])
        if account.get("id")
    })
    chat_states = chat_features_enabled() if admin_caps.get("manage_chat") else {"lobby": True, "room": True}
    sub_admin_permissions = {
        str(item.get("id")): get_admin_permissions(item)
        for item in admins if item.get("admin_level") == "admin"
    } if owner else {}

    return render_template(
        "admin.html",
        admin_users=admin_users,
        players=players,
        admins=admins,
        pending_users=pending_users,
        all_matches=all_matches,
        disputed=[m for m in all_matches if m.get("status") == "disputed"],
        playing=[m for m in all_matches if m.get("status") in {"playing", "friendly_playing"}],
        rooms=all_rooms,
        all_rooms=all_rooms,
        invites=list_admin_pending_invites(100) if needs_rooms else [],
        active_announcement=get_active_announcement() if admin_caps.get("manage_announcements") else None,
        password_reset_requests=password_reset_requests,
        audit_logs=audit_logs,
        duplicate_ip_groups=duplicate_ip_groups,
        duplicate_ip_user_count=duplicate_ip_user_count,
        pending_disputes=pending_disputes,
        can_create_test_account=bool(admin_caps.get("manage_test_data")),
        can_import_accounts_csv=bool(admin_caps.get("manage_test_data")),
        friendly_matches_enabled=friendly_matches_enabled() if admin_caps.get("manage_friendly") else False,
        lobby_chat_enabled=chat_states.get("lobby", True),
        room_chat_enabled=chat_states.get("room", True),
        gift_codes=gift_codes,
        gift_redemptions=gift_redemptions,
        gift_code_setup_required=gift_code_setup_required,
        admin_caps=admin_caps,
        admin_permission_definitions=ADMIN_PERMISSION_DEFINITIONS,
        sub_admin_permissions=sub_admin_permissions,
    )



def _safe_int_bounded(value, default=0, minimum=0, maximum=999999):
    """Bounded integer parser for admin CSV/import form fields.

    Keep this separate from _safe_int because ranked RP deltas can be negative.
    """
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
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
    if len(password) < 6:
        raise ValueError(f"Mật khẩu của {username} phải có ít nhất 6 ký tự.")

    wins = _safe_int_bounded(row.get("wins"), 0)
    draws = _safe_int_bounded(row.get("draws"), 0)
    losses = _safe_int_bounded(row.get("losses"), 0)
    supplied_total = _safe_int_bounded(row.get("total_matches"), wins + draws + losses)
    total_matches = max(supplied_total, wins + draws + losses)

    return {
        "username": username,
        "password_hash": hash_password(password),
        "display_name": display_name[:80],
        "zalo_name": zalo_name[:80],
        "role": "player",
        "account_status": "approved",
        "invite_code_used": None,
        "rank_points": _safe_int_bounded(row.get("rank_points"), DEFAULT_POINTS, 0, 999999),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "total_matches": total_matches,
        "goals_for": _safe_int_bounded(row.get("goals_for"), 0),
        "goals_against": _safe_int_bounded(row.get("goals_against"), 0),
        "is_online": False,
        "must_change_password": False,
        "register_ip": "ADMIN_TEST_IMPORT",
        "register_user_agent": "PES 2026 Admin Test Data",
    }



@app.route("/admin/gift-code/create", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_gift_codes")
def admin_create_gift_code():
    custom_code = normalize_gift_code(request.form.get("code"))
    code = custom_code or generate_gift_code(request.form.get("prefix") or GIFT_CODE_DEFAULT_PREFIX)
    reward_zcoin = _safe_int_bounded(request.form.get("reward_zcoin"), 0, 1, GIFT_CODE_MAX_REWARD_ZCOIN)
    max_redemptions = _safe_int_bounded(request.form.get("max_redemptions"), 1, 1, 100000)
    note = (request.form.get("note") or "").strip()[:250]
    expires_at = None
    expires_raw = (request.form.get("expires_at") or "").strip()
    if expires_raw:
        try:
            # HTML datetime-local returns YYYY-MM-DDTHH:MM in local time.
            local_dt = datetime.fromisoformat(expires_raw)
            expires_at = local_dt.replace(tzinfo=VN_TIMEZONE).astimezone(timezone.utc).isoformat()
        except Exception:
            flash("Ngày hết hạn gift code không hợp lệ.", "danger")
            return redirect_admin("gift-codes")

    if not code or len(code) < 4:
        flash("Mã gift code phải có ít nhất 4 ký tự hợp lệ.", "danger")
        return redirect_admin("gift-codes")

    actor = current_user()
    payload = {
        "code": code,
        "reward_type": "zcoin",
        "reward_zcoin": reward_zcoin,
        "max_redemptions": max_redemptions,
        "per_user_limit": 1,
        "is_active": True,
        "expires_at": expires_at,
        "created_by": actor.get("id"),
        "created_by_name": actor.get("username") or actor.get("display_name") or "Admin",
        "note": note or None,
        "updated_at": now_iso(),
    }

    try:
        execute_query(db.table("gift_codes").insert(payload), "admin_create_gift_code")
        log_admin_action("Tạo gift code", "gift_code", code, code, {"reward_zcoin": reward_zcoin, "max_redemptions": max_redemptions})
        flash(f"Đã tạo gift code {code} với phần thưởng {reward_zcoin} ZCOIN.", "success")
    except Exception as exc:
        print(f"admin_create_gift_code error: {exc}")
        flash("Không thể tạo gift code. Có thể mã đã tồn tại hoặc chưa chạy SQL V1.10.23.", "danger")
    return redirect_admin("gift-codes")


@app.route("/admin/gift-code/<code_id>/toggle", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_gift_codes")
def admin_toggle_gift_code(code_id):
    action = (request.form.get("action") or "disable").strip()
    is_active = action == "enable"
    try:
        execute_query(
            db.table("gift_codes").update({"is_active": is_active, "updated_at": now_iso()}).eq("id", code_id),
            "admin_toggle_gift_code",
        )
        log_admin_action("Bật gift code" if is_active else "Tắt gift code", "gift_code", code_id, code_id, "")
        flash("Đã cập nhật trạng thái gift code.", "success")
    except Exception as exc:
        print(f"admin_toggle_gift_code error: {exc}")
        flash("Không thể cập nhật gift code lúc này.", "danger")
    return redirect_admin("gift-codes")


@app.route("/admin/test-account/create", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_test_data")
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
@admin_permission_required("manage_test_data")
def admin_download_test_account_sample():
    sample_rows = [
        ["username", "display_name", "password", "zalo_name", "rank_points", "wins", "draws", "losses", "total_matches", "goals_for", "goals_against"],
        ["test01", "Test Player 01", "Test@12345", "Test 01", "1200", "5", "2", "3", "10", "12", "9"],
        ["test02", "Test Player 02", "Test@12345", "Test 02", "1350", "8", "1", "2", "11", "18", "7"],
        ["test03", "Test Player 03", "Test@12345", "Test 03", "1000", "0", "0", "0", "0", "0", "0"],
    ]
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(sample_rows)
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="pes_2026_test_accounts_sample.csv"'
    response.headers["Cache-Control"] = "no-store"
    return response

@app.route("/admin/test-account/import", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_test_data")
def admin_import_test_accounts():
    upload = request.files.get("csv_file")
    pasted_csv = request.form.get("csv_text", "").strip()
    default_password = request.form.get("default_password", "Test@12345").strip() or "Test@12345"
    if len(default_password) < 6:
        flash("Mật khẩu mặc định phải có ít nhất 6 ký tự.", "danger")
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
                    increments[field] = _safe_int_bounded(raw_value, 0, -999999, 999999)
                else:
                    increments[field] = _safe_int_bounded(raw_value, 0, 0, 999999)

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
                current_value = _safe_int_bounded(existing_user.get(field), 0, 0, 999999)
                if field == "rank_points":
                    # Cho phép cộng/trừ RP nhưng không để tổng điểm xuống dưới 0.
                    update_payload[field] = max(0, min(999999, current_value + increment))
                else:
                    update_payload[field] = min(999999, current_value + increment)

            # Với tài khoản đã tồn tại: cột password/pass để trống sẽ giữ nguyên mật khẩu cũ.
            # Chỉ cập nhật mật khẩu khi CSV thực sự cung cấp một giá trị hợp lệ.
            supplied_password = _csv_password_value(row)
            if supplied_password:
                if len(supplied_password) < 6:
                    raise ValueError(f"Mật khẩu mới của {username} phải có ít nhất 6 ký tự.")
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
@admin_permission_required("reset_passwords")
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
    if len(temporary_password) < 6:
        flash("Mật khẩu tạm phải có ít nhất 6 ký tự.", "danger")
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
@admin_permission_required("reset_passwords")
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
@admin_permission_required("approve_users")
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
@admin_permission_required("approve_users")
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
@admin_permission_required("edit_users")
def admin_ban_account(user_id):
    user = get_user(user_id)
    actor = current_user()
    if not user or user.get("role") != "player":
        flash("Không tìm thấy tài khoản player.", "danger")
        return redirect_admin("users")
    if is_admin_user(user) and not is_owner_user(actor):
        flash("Chỉ chủ hệ thống mới có thể xử lý tài khoản Admin.", "danger")
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
@admin_permission_required("edit_users")
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
@admin_permission_required("manage_invite_codes")
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
@admin_permission_required("manage_invite_codes")
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
        db.table("users").update({"admin_level": "admin", "admin_can_create_test_account": False, "admin_can_import_accounts_csv": False}).eq("id", user_id),
        "promote_admin",
    )
    save_admin_permissions(user_id, {code: False for code in ADMIN_PERMISSION_CODES})
    log_admin_action("Thêm Admin", "user", user_id, user.get("username"), "admin_level: none → admin")
    flash(f"Đã thêm {user.get('username')} làm admin. Người này vẫn có thể thi đấu.", "success")
    return redirect_admin("users")


@app.route("/admin/user/<user_id>/permissions", methods=["POST"])
@login_required
@owner_required
def admin_update_permissions(user_id):
    user = get_user(user_id)
    if not user or user.get("admin_level") != "admin":
        flash("Không tìm thấy Admin.", "danger")
        return redirect_admin("overview")

    payload = {
        code: request.form.get(f"permission_{code}") == "1"
        for code in ADMIN_PERMISSION_CODES
    }
    try:
        payload = save_admin_permissions(user_id, payload)
        # Đồng bộ hai cột cũ để các phiên bản cũ hơn vẫn hoạt động hợp lý.
        execute_query(
            db.table("users").update({
                "admin_can_create_test_account": bool(payload.get("manage_test_data")),
                "admin_can_import_accounts_csv": bool(payload.get("manage_test_data")),
            }).eq("id", user_id),
            "sync_legacy_admin_permissions",
            attempts=2,
        )
    except Exception:
        app.logger.exception("Không thể lưu quyền Admin")
        flash("Không thể lưu quyền Admin. Vui lòng kiểm tra Runtime Logs.", "danger")
        return redirect_admin("overview")

    cache_delete("_rz_players_all")
    cache_delete("_rz_users_map")
    log_admin_action("Cập nhật quyền Admin", "user", user_id, user.get("username"), payload)
    flash(f"Đã cập nhật quyền cho Admin {user.get('username')}.", "success")
    return redirect_admin("overview")

@app.route("/admin/user/<user_id>/demote", methods=["POST"])
@login_required
@owner_required
def admin_demote_user(user_id):
    user = get_user(user_id)
    if not user or user.get("admin_level") != "admin":
        flash("Không tìm thấy admin.", "danger")
        return redirect_admin("users")

    execute_query(
        db.table("users").update({"admin_level": "none", "admin_can_create_test_account": False, "admin_can_import_accounts_csv": False}).eq("id", user_id),
        "demote_admin",
    )
    try:
        execute_query(
            db.table("system_settings").delete().eq("setting_key", _admin_permission_setting_key(user_id)),
            "delete_admin_permissions",
            attempts=2,
        )
        _admin_permission_cache.pop(str(user_id), None)
    except Exception as exc:
        print(f"delete_admin_permissions warning: {exc}")
    log_admin_action("Gỡ Admin", "user", user_id, user.get("username"), "admin_level: admin → none")
    flash("Đã gỡ quyền admin.", "success")
    return redirect_admin("users")

@app.route("/admin/dispute/<dispute_id>/accept", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_disputes")
def admin_dispute_accept(dispute_id):
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


@app.route("/admin/dispute/<dispute_id>/edit", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_disputes")
def admin_dispute_edit(dispute_id):
    dispute = get_match_dispute(dispute_id)
    if not dispute or dispute.get("status") not in DISPUTE_PENDING_STATUSES:
        flash("Tranh chấp không còn hiệu lực.", "warning")
        return redirect_admin("disputes")
    try:
        score1 = int(request.form.get("score1", ""))
        score2 = int(request.form.get("score2", ""))
    except ValueError:
        flash("Tỉ số phải là số nguyên.", "danger")
        return redirect_admin("disputes")
    actor = current_user()
    note = request.form.get("resolution_note", "").strip() or "Admin đã sửa tỷ số và xác nhận kết quả tranh chấp."
    try:
        delta1, delta2 = resolve_match_dispute_with_result(
            dispute, score1, score2, actor.get("id"), "edited_result", note
        )
    except Exception as exc:
        flash(f"Không thể xử lý tranh chấp: {exc}", "danger")
        return redirect_admin("disputes")
    log_admin_action("Sửa tỷ số tranh chấp", "match", dispute.get("match_id"), details=f"Tỷ số mới {score1}-{score2}; điểm {delta1:+d}/{delta2:+d}")
    flash("Đã sửa tỷ số, xác nhận trận và cập nhật điểm.", "success")
    return redirect_admin("disputes")


@app.route("/admin/dispute/<dispute_id>/cancel", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_disputes")
def admin_dispute_cancel(dispute_id):
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


@app.route("/admin/cancel/<match_id>", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("delete_matches")
def admin_cancel(match_id):
    match = get_match(match_id)
    if not match:
        flash("Không tìm thấy trận.", "danger")
        return redirect_admin("matches")

    if match["status"] == "confirmed":
        flash("Không thể hủy trận đã xác nhận.", "danger")
        return redirect_admin("matches")

    if match.get("status") == "disputed":
        dispute = get_match_dispute_by_match(match_id, DISPUTE_PENDING_STATUSES)
        if dispute:
            try:
                cancel_match_dispute(dispute, current_user().get("id"), "Admin hủy trận tranh chấp; không tính điểm.")
            except Exception as exc:
                flash(f"Không thể hủy trận tranh chấp: {exc}", "danger")
                return redirect_admin("disputes")
            log_admin_action("Hủy trận tranh chấp", "match", match_id, details="Không tính điểm.")
            flash("Đã hủy trận tranh chấp. Không ai bị cộng hoặc trừ điểm.", "success")
            return redirect_admin("disputes")

    db.table("matches").update({
        "status": "cancelled",
        "note": "Admin đã hủy trận.",
        "updated_at": now_iso(),
    }).eq("id", match_id).execute()

    log_admin_action("Hủy trận", "match", match_id, details=f"Trạng thái cũ: {match.get('status')}")
    flash("Đã hủy trận.", "success")
    return redirect_admin("matches")


@app.route("/admin/confirm-disputed/<match_id>", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_disputes")
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
        apply_match_result(match)
    log_admin_action("Xác nhận tranh chấp", "match", match_id, details="Đã áp dụng kết quả và cập nhật điểm.")
    flash("Admin đã xác nhận trận tranh chấp.", "success")
    return redirect_admin("disputes")


@app.route("/admin/toggle-online/<user_id>", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("edit_users")
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
@admin_permission_required("edit_users")
def admin_update_player(user_id):
    player = get_user(user_id)
    actor = current_user()
    if not player:
        flash("Không tìm thấy tài khoản.", "danger")
        return redirect(url_for("admin") + "#users")

    if is_admin_user(player) and not is_owner_user(actor):
        flash("Chỉ Admin mới được sửa tài khoản Admin.", "danger")
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
        if len(new_password) < 6:
            flash("Mật khẩu mới phải có ít nhất 6 ký tự.", "danger")
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
@admin_permission_required("edit_users")
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
@admin_permission_required("delete_users")
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


def _admin_match_redirect(default_tab="matches"):
    next_url = (request.form.get("return_url") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect_admin(default_tab)


def _normalize_manual_team_name(value):
    return str(value or "").strip()[:80]


@app.route("/admin/matches/create-manual", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("create_matches")
def admin_create_manual_match():
    try:
        player1_id = str(request.form.get("player1_id") or "").strip()
        player2_id = str(request.form.get("player2_id") or "").strip()
        host_side = str(request.form.get("host_side") or "player1").strip().lower()
        score1 = _safe_int(request.form.get("score1"), 0)
        score2 = _safe_int(request.form.get("score2"), 0)
        team1 = _normalize_manual_team_name(request.form.get("team1"))
        team2 = _normalize_manual_team_name(request.form.get("team2"))
        note = (request.form.get("note") or "Admin tạo trận thủ công.").strip()[:500]
    except Exception:
        flash("Dữ liệu tạo trận không hợp lệ.", "danger")
        return redirect_admin("matches")

    if not player1_id or not player2_id:
        flash("Vui lòng chọn đủ 2 người chơi.", "danger")
        return redirect_admin("matches")
    if player1_id == player2_id:
        flash("Không thể tạo trận với cùng một người chơi ở hai bên.", "danger")
        return redirect_admin("matches")
    if score1 < 0 or score2 < 0:
        flash("Tỉ số không được âm.", "danger")
        return redirect_admin("matches")

    player1 = get_user(player1_id)
    player2 = get_user(player2_id)
    if not player1 or not player2:
        flash("Không tìm thấy một trong hai người chơi.", "danger")
        return redirect_admin("matches")
    if is_admin_user(player1) or is_admin_user(player2):
        flash("Chỉ có thể tạo trận thủ công cho tài khoản người chơi.", "danger")
        return redirect_admin("matches")

    winner_id = player1_id if score1 > score2 else player2_id if score2 > score1 else None
    loser_id = player2_id if score1 > score2 else player1_id if score2 > score1 else None
    host_user_id = player1_id if host_side != "player2" else player2_id

    match = None
    room = None
    result_applied = False
    try:
        match_result = execute_query(
            db.table("matches").insert({
                "player1_id": player1_id,
                "player2_id": player2_id,
                "score1": score1,
                "score2": score2,
                "team1": team1 or None,
                "team2": team2 or None,
                "winner_id": winner_id,
                "loser_id": loser_id,
                "delta1": 0,
                "delta2": 0,
                "status": "waiting_confirm",
                "submitted_by_id": current_user().get("id"),
                "note": note,
                "updated_at": now_iso(),
            }),
            "admin_create_manual_match_insert",
        )
        match = (match_result.data or [None])[0]
        if not match:
            raise RuntimeError("Không tạo được bản ghi trận đấu.")

        room_result = execute_query(
            db.table("match_rooms").insert({
                "host_user_id": host_user_id,
                "guest_user_id": player2_id if host_user_id == player1_id else player1_id,
                "team_tier": SMART_RANDOM_MODE,
                "match_mode": MATCH_MODE_RANKED,
                "friendly_tier": "A",
                "status": "waiting_result_confirm",
                "guest_ready": True,
                "match_id": match.get("id"),
                "host_score": score1 if host_user_id == player1_id else score2,
                "guest_score": score2 if host_user_id == player1_id else score1,
                "host_team": team1 if host_user_id == player1_id else team2,
                "guest_team": team2 if host_user_id == player1_id else team1,
                "note": "Admin tạo trận thủ công.",
                "state_expires_at": None,
                "updated_at": now_iso(),
            }),
            "admin_create_manual_room_insert",
            attempts=2,
        )
        room = (room_result.data or [None])[0]
        if not room:
            raise RuntimeError("Không tạo được phòng liên kết cho trận thủ công.")

        refreshed = get_match(match.get("id"))
        if not refreshed:
            raise RuntimeError("Không đọc lại được trận vừa tạo.")
        delta1, delta2 = apply_match_result(refreshed)
        result_applied = True
        execute_query(
            db.table("matches").update({"note": note, "updated_at": now_iso()}).eq("id", match.get("id")),
            "admin_create_manual_match_note",
            attempts=2,
        )
        execute_query(
            db.table("match_rooms").update({
                "status": "confirmed",
                "note": "Admin đã tạo và xác nhận trận thủ công.",
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("match_id", match.get("id")),
            "admin_create_manual_room_finalize",
            attempts=2,
        )
        ttl_cache_delete("rooms_raw", "players_raw", "matches_raw", "achievement_map")
        cache_delete("_rz_matches_all")
        cache_delete("_rz_players_all")
        cache_delete("_rz_users_map")
    except Exception as exc:
        print(f"admin_create_manual_match ERROR: {type(exc).__name__}: {exc}")
        # Best-effort rollback prevents orphan rooms/matches after a partial failure.
        try:
            if result_applied and match:
                fresh_match = get_match(match.get("id"))
                if fresh_match:
                    reverse_confirmed_match_result(fresh_match)
            if room and room.get("id"):
                execute_query(db.table("match_rooms").delete().eq("id", room.get("id")), "rollback_manual_room", attempts=2)
            if match and match.get("id"):
                execute_query(db.table("matches").delete().eq("id", match.get("id")), "rollback_manual_match", attempts=2)
        except Exception as rollback_exc:
            print(f"admin_create_manual_match ROLLBACK ERROR: {type(rollback_exc).__name__}: {rollback_exc}")
        flash(f"Không thể tạo trận thủ công: {exc}", "danger")
        return redirect_admin("matches")

    log_admin_action(
        "Tạo trận thủ công",
        "match",
        match.get("id"),
        details=(
            f"{player1.get('display_name') or player1.get('username')} {score1}-{score2} "
            f"{player2.get('display_name') or player2.get('username')}; "
            f"RP {int(delta1):+d}/{int(delta2):+d}; host={host_user_id}. {note}"
        ),
    )
    flash(
        f"Đã tạo trận thủ công: {(player1.get('display_name') or player1.get('username'))} {score1}-{score2} "
        f"{(player2.get('display_name') or player2.get('username'))}. RP {int(delta1):+d}/{int(delta2):+d}.",
        "success",
    )
    return redirect_admin("matches")


@app.route("/admin/match/<match_id>/update-result", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("edit_matches")
def admin_update_match_result(match_id):
    match = get_match(match_id)
    if not match:
        flash("Không tìm thấy trận.", "danger")
        return _admin_match_redirect("matches")

    try:
        score1 = int(request.form.get("score1", "0"))
        score2 = int(request.form.get("score2", "0"))
    except (TypeError, ValueError):
        flash("Tỉ số phải là số nguyên.", "danger")
        return _admin_match_redirect("matches")
    if score1 < 0 or score2 < 0:
        flash("Tỉ số không được âm.", "danger")
        return _admin_match_redirect("matches")

    if not match.get("player1_id") or not match.get("player2_id"):
        flash("Trận đấu thiếu dữ liệu người chơi nên chưa thể sửa.", "danger")
        return _admin_match_redirect("matches")
    if not get_user(match.get("player1_id")) or not get_user(match.get("player2_id")):
        flash("Không tìm thấy một trong hai người chơi. Chưa thay đổi BXH.", "danger")
        return _admin_match_redirect("matches")

    winner_id = match.get("player1_id") if score1 > score2 else match.get("player2_id") if score2 > score1 else None
    loser_id = match.get("player2_id") if score1 > score2 else match.get("player1_id") if score2 > score1 else None
    note = request.form.get("note", "").strip()[:500] or "Admin đã sửa kết quả."
    target_status = (request.form.get("target_status") or "confirmed").strip().lower()
    if target_status not in {"confirmed", "cancelled"}:
        flash("Admin chỉ được chuyển trạng thái sang confirmed hoặc cancelled.", "danger")
        return _admin_match_redirect("matches")

    if target_status == "cancelled":
        old_match = dict(match)
        try:
            if old_match.get("status") == "confirmed" and not reverse_confirmed_match_result(old_match):
                raise ValueError("Không thể hoàn tác RP của trận đã xác nhận.")
            if old_match.get("status") == "disputed":
                dispute = get_match_dispute_by_match(match_id, DISPUTE_PENDING_STATUSES)
                if dispute:
                    cancel_match_dispute(dispute, current_user().get("id"), note or "Admin chuyển trận sang cancelled.")
                else:
                    execute_query(
                        db.table("matches").update({
                            "status": "cancelled", "delta1": 0, "delta2": 0,
                            "winner_id": None, "loser_id": None, "note": note, "updated_at": now_iso(),
                        }).eq("id", match_id),
                        "admin_cancel_disputed_without_record",
                    )
            else:
                execute_query(
                    db.table("matches").update({
                        "score1": score1, "score2": score2,
                        "status": "cancelled", "delta1": 0, "delta2": 0,
                        "winner_id": None, "loser_id": None, "note": note, "updated_at": now_iso(),
                    }).eq("id", match_id),
                    "admin_change_match_status_cancelled",
                )
            execute_query(
                db.table("match_rooms").update({
                    "status": "cancelled", "note": "Admin đã chuyển trận sang cancelled.",
                    "state_expires_at": None, "updated_at": now_iso(),
                }).eq("match_id", match_id),
                "admin_change_room_status_cancelled",
                attempts=2,
            )
            ttl_cache_delete("rooms_raw", "players_raw", "matches_raw", "achievement_map")
        except Exception as exc:
            print(f"admin_change_match_status_cancelled ERROR match={match_id}: {type(exc).__name__}: {exc}")
            flash(f"Không thể chuyển trận sang cancelled: {exc}", "danger")
            return _admin_match_redirect("matches")
        log_admin_action(
            "Đổi trạng thái trận", "match", match_id,
            details=f"{old_match.get('status')} → cancelled; tỷ số giữ {score1}-{score2}. {note}",
        )
        flash("Đã chuyển trận sang cancelled và hoàn tác RP nếu trước đó đã confirmed.", "success")
        return _admin_match_redirect("matches")

    if match.get("status") == "disputed":
        dispute = get_match_dispute_by_match(match_id, DISPUTE_PENDING_STATUSES)
        if dispute:
            try:
                resolve_match_dispute_with_result(
                    dispute, score1, score2, current_user().get("id"), "edited_result", note,
                )
            except Exception as exc:
                print(f"admin_update_disputed ERROR match={match_id}: {type(exc).__name__}: {exc}")
                flash(f"Không thể xử lý tranh chấp: {exc}", "danger")
                return _admin_match_redirect("disputes")
            log_admin_action("Sửa/Xác nhận tranh chấp", "match", match_id, details=f"Tỷ số mới {score1}-{score2}. {note}")
            flash("Đã sửa tỷ số tranh chấp và cập nhật BXH.", "success")
            return _admin_match_redirect("disputes")

    old_match = dict(match)
    old_was_applied = bool(
        old_match.get("status") == "confirmed"
        and old_match.get("delta1") is not None
        and old_match.get("delta2") is not None
    )
    try:
        if old_was_applied and not reverse_confirmed_match_result(old_match):
            raise ValueError("Không thể hoàn tác kết quả cũ; chưa lưu tỷ số mới.")

        # Không set delta1/delta2 = None vì production có constraint NOT NULL.
        # Dùng 0 làm giá trị tạm; apply_match_result sẽ ghi delta thật sau khi tính RP.
        execute_query(
            db.table("matches").update({
                "score1": score1,
                "score2": score2,
                "winner_id": winner_id,
                "loser_id": loser_id,
                "status": "waiting_confirm",
                "delta1": 0,
                "delta2": 0,
                "note": note,
                "updated_at": now_iso(),
            }).eq("id", match_id),
            "admin_prepare_updated_match",
        )
        execute_query(
            db.table("match_rooms").update({
                "host_score": score1,
                "guest_score": score2,
                "status": "waiting_result_confirm",
                "note": "Admin đang lưu lại kết quả.",
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("match_id", match_id),
            "admin_prepare_updated_room",
            attempts=3,
        )

        updated_match = get_match(match_id)
        if not updated_match:
            raise RuntimeError("Không đọc lại được trận sau khi lưu tỷ số.")
        delta1, delta2 = apply_match_result(updated_match)
        execute_query(
            db.table("matches").update({"note": note, "updated_at": now_iso()}).eq("id", match_id),
            "admin_finish_updated_match_note",
        )
        execute_query(
            db.table("match_rooms").update({
                "status": "confirmed",
                "note": "Admin đã sửa/xác nhận kết quả.",
                "state_expires_at": None,
                "updated_at": now_iso(),
            }).eq("match_id", match_id),
            "admin_finish_updated_room",
            attempts=3,
        )
        ttl_cache_delete("rooms_raw", "players_raw", "achievement_map")
    except Exception as exc:
        print(f"admin_update_match_result ERROR match={match_id}: {type(exc).__name__}: {exc}")
        # Best-effort restoration of the original match row. The detailed log above
        # makes any rare partial failure visible in Vercel instead of a silent 500.
        try:
            execute_query(
                db.table("matches").update({
                    "score1": old_match.get("score1"),
                    "score2": old_match.get("score2"),
                    "winner_id": old_match.get("winner_id"),
                    "loser_id": old_match.get("loser_id"),
                    "delta1": _safe_int(old_match.get("delta1"), 0),
                    "delta2": _safe_int(old_match.get("delta2"), 0),
                    "status": old_match.get("status"),
                    "note": old_match.get("note"),
                    "updated_at": now_iso(),
                }).eq("id", match_id),
                "admin_restore_old_match",
                attempts=2,
            )
            if old_was_applied:
                restored = get_match(match_id)
                if restored:
                    # Only reapply when the rollback had already removed old stats.
                    p1 = get_user(old_match.get("player1_id"))
                    p2 = get_user(old_match.get("player2_id"))
                    if p1 and p2:
                        update_player_after_match(p1, _safe_int(old_match.get("delta1")), _safe_int(old_match.get("score1")), _safe_int(old_match.get("score2")))
                        update_player_after_match(p2, _safe_int(old_match.get("delta2")), _safe_int(old_match.get("score2")), _safe_int(old_match.get("score1")))
        except Exception as rollback_exc:
            print(f"admin_update_match_result ROLLBACK ERROR match={match_id}: {type(rollback_exc).__name__}: {rollback_exc}")
        flash(f"Không thể lưu lại trận đấu: {exc}. Hệ thống đã ghi log chi tiết trên Vercel.", "danger")
        return _admin_match_redirect("matches")

    log_admin_action(
        "Sửa/Xác nhận kết quả", "match", match_id,
        details=f"{old_match.get('score1')}–{old_match.get('score2')} → {score1}–{score2}; RP {int(delta1):+d}/{int(delta2):+d}. {note}",
    )
    if is_htmx_request():
        refreshed = next((item for item in list_recent_matches(80) if item.get("id") == match_id), None)
        if not refreshed:
            return htmx_redirect(url_for("admin") + "#matches")
        return render_template(
            "partials/admin_match_row.html",
            m=refreshed,
            admin_caps=get_admin_permissions(current_user()),
            saved_message=f"Đã lưu • RP {int(delta1):+d}/{int(delta2):+d}",
        )
    flash(f"Đã sửa kết quả và cập nhật lại RP: {int(delta1):+d}/{int(delta2):+d}.", "success")
    return _admin_match_redirect("matches")


@app.route("/admin/match/<match_id>/delete", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("delete_matches")
def admin_delete_match(match_id):
    match = get_match(match_id)
    if not match:
        flash("Không tìm thấy trận.", "danger")
        return redirect_admin("matches")

    delete_match_safe(match_id)
    log_admin_action("Xóa trận", "match", match_id, details=f"Trạng thái cũ: {match.get('status')}")
    flash("Đã xóa trận và hoàn tác đúng thông số của trận này.", "success")
    return redirect_admin("matches")


@app.route("/admin/room/<room_id>/cancel", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_rooms")
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
        db.table("matches").update({
            "status": "cancelled",
            "note": "Admin đã hủy phòng/trận.",
            "updated_at": now_iso(),
        }).eq("id", room["match_id"]).execute()

    log_admin_action("Hủy phòng", "room", room_id, details=f"Trạng thái cũ: {room.get('status')}")
    flash("Đã hủy phòng.", "success")
    return redirect_admin("rooms")


@app.route("/admin/room/<room_id>/delete", methods=["POST"])
@login_required
@admin_required
@admin_permission_required("manage_rooms")
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
@admin_permission_required("manage_rooms")
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
