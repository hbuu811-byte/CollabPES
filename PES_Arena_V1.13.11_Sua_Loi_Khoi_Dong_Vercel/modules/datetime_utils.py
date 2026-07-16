"""Hàm thời gian UTC và định dạng giờ Việt Nam."""
from datetime import datetime, timezone, timedelta

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

def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

def seconds_until(value) -> int:
    dt = aware_utc(parse_dt(value))
    if not dt:
        return 0
    return max(0, int((dt - now_dt()).total_seconds()))

def format_vn_datetime(value) -> str:
    dt = parse_dt(value)
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    vietnam_time = dt.astimezone(timezone(timedelta(hours=7)))
    return vietnam_time.strftime("%d/%m/%Y %H:%M")
