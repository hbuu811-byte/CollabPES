#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Áp dụng nâng cấp Collap_V1.13.3m lên dự án đang ở Collap_V1.13.3k.

Mục tiêu:
- Bộ lọc Đã hủy / Bỏ cuộc nhận mọi bản ghi hủy hoặc bị trừ RP,
  kể cả bản ghi chỉ có một phía người chơi.
- Admin có công tắc bật/tắt Xem lịch sử toàn hệ thống.
- Khi tắt, người chơi chỉ xem lịch sử bản thân; Admin vẫn xem toàn hệ thống.

Cách dùng:
1. Chép file này vào thư mục gốc dự án, cùng cấp app.py.
2. Chạy: python apply_Collap_V1.13.3m.py
3. Commit các file được báo ở cuối.
"""
from __future__ import annotations

from pathlib import Path
import py_compile
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
HISTORY_MODULE = ROOT / "modules" / "match_history_routes.py"
MATCHES_TEMPLATE = ROOT / "templates" / "matches.html"
ADMIN_TEMPLATE = ROOT / "templates" / "admin.html"
BACKUP_DIR = ROOT / ".collap_v1_13_3m_backup"

REQUIRED = [APP, HISTORY_MODULE, MATCHES_TEMPLATE, ADMIN_TEMPLATE]

NEW_HISTORY_MODULE = r'''"""Route lịch sử trận đấu.

Collap_V1.13.3m:
- bảo vệ chế độ xem toàn hệ thống bằng công tắc Admin;
- bộ lọc Đã hủy / Bỏ cuộc nhận mọi bản ghi phạt, kể cả thiếu đối thủ.
"""


def register_routes(context):
    """Đăng ký nhóm route vào Flask app hiện tại."""
    globals().update(context)

    def _history_safe_delta(value):
        try:
            return int(round(float(value or 0)))
        except (TypeError, ValueError, OverflowError):
            return 0

    def _is_cancelled_or_forfeit_history(match):
        """Nhận diện trận hủy/bỏ cuộc mà không yêu cầu đủ hai người chơi."""
        if not isinstance(match, dict):
            return False
        if str(match.get("status") or "").strip() == "cancelled":
            return True

        checker = globals().get("is_forfeit_match")
        if callable(checker):
            try:
                if checker(match):
                    return True
            except Exception:
                pass

        note = str(match.get("note") or "").casefold()
        has_forfeit_note = any(token in note for token in (
            "[forfeit:", "bỏ cuộc", "bỏ trận", "bỏ dở", "rời phòng sau khi",
        ))
        has_negative_delta = (
            _history_safe_delta(match.get("delta1")) < 0
            or _history_safe_delta(match.get("delta2")) < 0
        )
        # Không gom trận confirmed thua bình thường vào bộ lọc bỏ cuộc.
        return has_forfeit_note or (
            has_negative_delta and str(match.get("status") or "") != "confirmed"
        )

    @app.route("/matches")
    @login_required
    def matches():
        user = current_user()
        requested_view = (request.args.get("view") or "mine").strip()
        status_filter = (request.args.get("status") or "all").strip()
        query = (request.args.get("q") or "").strip().casefold()
        try:
            page = max(1, int(request.args.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        per_page = 20

        global_history_enabled = bool(
            system_feature_enabled("match_history_all_enabled")
        )
        can_view_all_history = bool(
            global_history_enabled or is_admin_user(user)
        )
        history_view = "all" if requested_view == "all" and can_view_all_history else "mine"

        rows = list_matches()
        if history_view != "all":
            user_id = user.get("id")
            rows = [
                match for match in rows
                if user_id in {match.get("player1_id"), match.get("player2_id")}
            ]

        if status_filter == "cancelled":
            rows = [match for match in rows if _is_cancelled_or_forfeit_history(match)]
        elif status_filter != "all":
            rows = [match for match in rows if match.get("status") == status_filter]

        if query:
            rows = [
                match for match in rows
                if query in " ".join([
                    str(match.get("player1_name") or ""),
                    str(match.get("player2_name") or ""),
                    str(match.get("team1") or ""),
                    str(match.get("team2") or ""),
                    str(match.get("note") or ""),
                ]).casefold()
            ]

        total_items = len(rows)
        total_pages = max(1, (total_items + per_page - 1) // per_page)
        page = min(page, total_pages)
        start = (page - 1) * per_page
        history_viewer_id = user.get("id") if history_view == "mine" else None
        page_rows = [
            decorate_match_for_view(match, history_viewer_id)
            for match in rows[start:start + per_page]
        ]

        return render_template(
            "matches.html",
            matches=page_rows,
            history_view=history_view,
            can_view_all_history=can_view_all_history,
            global_history_enabled=global_history_enabled,
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
'''


def fail(message: str, code: int = 1) -> int:
    print(f"[LỖI] {message}")
    return code


def add_system_feature_default(text: str) -> str:
    if '"match_history_all_enabled"' in text or "'match_history_all_enabled'" in text:
        return text

    match = re.search(r"SYSTEM_FEATURE_DEFAULTS\s*=\s*\{(?P<body>.*?)\n\}", text, re.S)
    if not match:
        raise ValueError("Không tìm thấy SYSTEM_FEATURE_DEFAULTS trong app.py")

    body = match.group("body")
    insertion = '\n    "match_history_all_enabled": True,'
    new_body = body.rstrip() + insertion
    return text[:match.start("body")] + new_body + text[match.end("body"):]


def set_version(text: str) -> str:
    pattern = r'APP_VERSION\s*=\s*["\'][^"\']+["\']'
    replacement = 'APP_VERSION = "Collap_V1.13.3m"'
    if not re.search(pattern, text):
        raise ValueError("Không tìm thấy APP_VERSION trong app.py")
    return re.sub(pattern, replacement, text, count=1)


def patch_matches_template(text: str) -> str:
    if "can_view_all_history" not in text:
        pattern = re.compile(
            r'(?P<indent>\s*)<a class="\{\{ \'active\' if history_view == \'all\' else \'\' \}\}" href="\{\{ url_for\(\'matches\', view=\'all\'\) \}\}">Toàn hệ thống</a>'
        )
        match = pattern.search(text)
        if not match:
            # Chấp nhận cách xuống dòng/nháy khác nhưng vẫn bám đúng chữ Toàn hệ thống.
            pattern = re.compile(r'(?P<line>[^\n]*url_for\(["\']matches["\'],\s*view=["\']all["\']\)[^\n]*>Toàn hệ thống</a>)')
            match = pattern.search(text)
            if not match:
                raise ValueError("Không tìm thấy tab Toàn hệ thống trong templates/matches.html")
            line = match.group("line")
            text = text[:match.start()] + "{% if can_view_all_history %}\n" + line + "\n{% endif %}" + text[match.end():]
        else:
            line = match.group(0).lstrip("\n")
            text = text[:match.start()] + "\n    {% if can_view_all_history %}\n    " + line.strip() + "\n    {% endif %}" + text[match.end():]

    text = re.sub(
        r'(<option\s+value=["\']cancelled["\'][^>]*>)(?:Đã hủy(?:\s*/\s*Bỏ cuộc)?)(</option>)',
        r'\1Đã hủy / Bỏ cuộc\2',
        text,
        count=1,
        flags=re.I,
    )
    return text


def patch_admin_template(text: str) -> str:
    if "match_history_all_enabled" in text:
        return text

    anchors = [
        "'announcements_enabled':'Thông báo'",
        '"announcements_enabled":"Thông báo"',
        "'dashboard_enabled':'Dashboard'",
    ]
    for anchor in anchors:
        if anchor in text:
            if "announcements_enabled" in anchor:
                replacement = anchor + ",'match_history_all_enabled':'Xem lịch sử toàn hệ thống'"
            else:
                replacement = anchor + ",'match_history_all_enabled':'Xem lịch sử toàn hệ thống'"
            return text.replace(anchor, replacement, 1)

    raise ValueError("Không tìm thấy danh sách công tắc hệ thống trong templates/admin.html")


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.exists()]
    if missing:
        return fail("Thiếu file: " + ", ".join(missing))

    originals = {path: path.read_text(encoding="utf-8") for path in REQUIRED}
    try:
        new_app = set_version(add_system_feature_default(originals[APP]))
        new_history = NEW_HISTORY_MODULE
        new_matches = patch_matches_template(originals[MATCHES_TEMPLATE])
        new_admin = patch_admin_template(originals[ADMIN_TEMPLATE])
    except Exception as exc:
        return fail(f"Không thể xác định đúng cấu trúc bản hiện tại: {exc}", 2)

    BACKUP_DIR.mkdir(exist_ok=True)
    for path in REQUIRED:
        destination = BACKUP_DIR / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

    try:
        APP.write_text(new_app, encoding="utf-8")
        HISTORY_MODULE.write_text(new_history, encoding="utf-8")
        MATCHES_TEMPLATE.write_text(new_matches, encoding="utf-8")
        ADMIN_TEMPLATE.write_text(new_admin, encoding="utf-8")

        py_compile.compile(str(APP), doraise=True)
        py_compile.compile(str(HISTORY_MODULE), doraise=True)
    except Exception as exc:
        for path in REQUIRED:
            backup = BACKUP_DIR / path.relative_to(ROOT)
            if backup.exists():
                shutil.copy2(backup, path)
        return fail(f"Kiểm tra thất bại, đã tự khôi phục file cũ: {exc}", 3)

    print("[OK] Đã áp dụng Collap_V1.13.3m.")
    print("[ĐÃ SỬA] app.py")
    print("[ĐÃ SỬA] modules/match_history_routes.py")
    print("[ĐÃ SỬA] templates/matches.html")
    print("[ĐÃ SỬA] templates/admin.html")
    print(f"[BACKUP] {BACKUP_DIR.name}")
    print("[KHÔNG CẦN] SQL Supabase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
