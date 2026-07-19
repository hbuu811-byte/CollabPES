#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Áp dụng nâng cấp Collap_V1.13.3n lên dự án đã có Collap_V1.13.3m.

Mục tiêu:
- Admin có công tắc bật/tắt BXH công khai.
- Bật: khách chưa đăng nhập được xem /, /bxh và /ranking.
- Tắt: khách bị đưa về /login; người đã đăng nhập vẫn xem BXH bình thường.
- Khóa ở backend để không thể lách bằng URL trực tiếp.

Cách dùng:
1. Chép file này vào thư mục gốc dự án, cùng cấp app.py.
2. Chạy: python apply_Collap_V1.13.3n.py
3. Commit hai file được báo ở cuối.
"""
from __future__ import annotations

from pathlib import Path
import py_compile
import re
import shutil

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
ADMIN_TEMPLATE = ROOT / "templates" / "admin.html"
BACKUP_DIR = ROOT / ".collap_v1_13_3n_backup"
REQUIRED = [APP, ADMIN_TEMPLATE]

FEATURE_KEY = "public_ranking_enabled"
FEATURE_LABEL = "BXH công khai (không cần đăng nhập)"
VERSION = "Collap_V1.13.3n"


def fail(message: str, code: int = 1) -> int:
    print(f"[LỖI] {message}")
    return code


def set_version(text: str) -> str:
    pattern = r'APP_VERSION\s*=\s*["\'][^"\']+["\']'
    if not re.search(pattern, text):
        raise ValueError("Không tìm thấy APP_VERSION trong app.py")
    return re.sub(pattern, f'APP_VERSION = "{VERSION}"', text, count=1)


def add_system_feature_default(text: str) -> str:
    if re.search(r'["\']public_ranking_enabled["\']\s*:', text):
        return text

    match = re.search(r"SYSTEM_FEATURE_DEFAULTS\s*=\s*\{(?P<body>.*?)\n\}", text, re.S)
    if not match:
        raise ValueError("Không tìm thấy SYSTEM_FEATURE_DEFAULTS trong app.py")

    body = match.group("body")
    comma = "" if body.rstrip().endswith(",") else ","
    insertion = f'{comma}\n    "{FEATURE_KEY}": True,'
    new_body = body.rstrip() + insertion
    return text[:match.start("body")] + new_body + text[match.end("body"):]


def patch_index_route(text: str) -> str:
    """Đổi trang gốc theo trạng thái công khai của BXH."""
    replacement = '''@app.route("/")
def index():
    # Khi BXH công khai bị tắt, khách chưa đăng nhập phải vào màn hình đăng nhập.
    # Người đã đăng nhập vẫn được chuyển thẳng tới BXH như bình thường.
    user = current_user()
    if user or system_feature_enabled("public_ranking_enabled"):
        return redirect(url_for("ranking"))
    return redirect(url_for("login"))

'''

    pattern = re.compile(
        r'@app\.route\(["\']/["\']\)\s*\n'
        r'def\s+index\(\):.*?'
        r'(?=\n@app\.route\(["\']/login["\'])',
        re.S,
    )
    if not pattern.search(text):
        raise ValueError("Không tìm thấy route / và route /login liền sau trong app.py")
    return pattern.sub(replacement, text, count=1)


def patch_ranking_route(text: str) -> str:
    """Thêm bảo vệ backend cho cả /ranking và /bxh."""
    function_match = re.search(r'(^def\s+ranking\(\):\s*$)', text, re.M)
    if not function_match:
        raise ValueError("Không tìm thấy def ranking() trong app.py")

    block_start = function_match.start()
    next_route = re.search(r'^@app\.route\(', text[function_match.end():], re.M)
    block_end = function_match.end() + (next_route.start() if next_route else len(text))
    block = text[block_start:block_end]

    if 'system_feature_enabled("public_ranking_enabled")' in block:
        return text

    # Route cũ thường lấy current_user() ở giữa hàm. Di chuyển lên đầu để dùng
    # cho bước kiểm tra quyền và không tạo thêm một lần đọc người dùng trùng.
    block = re.sub(r'^    user\s*=\s*current_user\(\)\s*\n', '', block, count=1, flags=re.M)

    guard = '''def ranking():
    user = current_user()
    if not user and not system_feature_enabled("public_ranking_enabled"):
        flash("Bảng xếp hạng chỉ dành cho người chơi đã đăng nhập.", "warning")
        return redirect(url_for("login"))
'''
    block = re.sub(r'^def\s+ranking\(\):\s*\n', guard, block, count=1, flags=re.M)
    return text[:block_start] + block + text[block_end:]


def patch_admin_template(text: str) -> str:
    if FEATURE_KEY in text:
        return text

    # Ưu tiên chèn ngay sau công tắc lịch sử của bản 3m.
    variants = [
        "'match_history_all_enabled':'Xem lịch sử toàn hệ thống'",
        '"match_history_all_enabled":"Xem lịch sử toàn hệ thống"',
        "'announcements_enabled':'Thông báo'",
        '"announcements_enabled":"Thông báo"',
    ]
    for anchor in variants:
        if anchor in text:
            quote = '"' if anchor.startswith('"') else "'"
            addition = f",{quote}{FEATURE_KEY}{quote}:{quote}{FEATURE_LABEL}{quote}"
            return text.replace(anchor, anchor + addition, 1)

    # Dự phòng cho template đã xuống dòng hoặc đổi khoảng trắng: tìm dictionary
    # công tắc có dashboard_enabled rồi chèn trước }.items().
    pattern = re.compile(
        r'(?P<body>\{[^{}]*["\']dashboard_enabled["\'][^{}]*?)'
        r'(?P<end>\}\s*\.items\(\))',
        re.S,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError("Không tìm thấy danh sách công tắc hệ thống trong templates/admin.html")

    body = match.group("body").rstrip()
    comma = "" if body.endswith(",") else ","
    new_mapping = body + comma + f"'{FEATURE_KEY}':'{FEATURE_LABEL}'" + match.group("end")
    return text[:match.start()] + new_mapping + text[match.end():]


def validate_result(app_text: str, admin_text: str) -> None:
    required_app_tokens = (
        'APP_VERSION = "Collap_V1.13.3n"',
        '"public_ranking_enabled": True',
        'system_feature_enabled("public_ranking_enabled")',
        'return redirect(url_for("login"))',
    )
    missing = [token for token in required_app_tokens if token not in app_text]
    if missing:
        raise ValueError("Thiếu nội dung sau khi vá app.py: " + ", ".join(missing))
    if FEATURE_KEY not in admin_text or FEATURE_LABEL not in admin_text:
        raise ValueError("Công tắc BXH công khai chưa được thêm đầy đủ vào admin.html")


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.exists()]
    if missing:
        return fail("Thiếu file: " + ", ".join(missing))

    originals = {path: path.read_text(encoding="utf-8") for path in REQUIRED}
    try:
        new_app = set_version(originals[APP])
        new_app = add_system_feature_default(new_app)
        new_app = patch_index_route(new_app)
        new_app = patch_ranking_route(new_app)
        new_admin = patch_admin_template(originals[ADMIN_TEMPLATE])
        validate_result(new_app, new_admin)
    except Exception as exc:
        return fail(f"Không thể xác định đúng cấu trúc bản hiện tại: {exc}", 2)

    BACKUP_DIR.mkdir(exist_ok=True)
    for path in REQUIRED:
        destination = BACKUP_DIR / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(path, destination)

    try:
        APP.write_text(new_app, encoding="utf-8")
        ADMIN_TEMPLATE.write_text(new_admin, encoding="utf-8")
        py_compile.compile(str(APP), doraise=True)
        try:
            from jinja2 import Environment
            Environment().parse(new_admin)
        except ImportError:
            pass
    except Exception as exc:
        for path in REQUIRED:
            backup = BACKUP_DIR / path.relative_to(ROOT)
            if backup.exists():
                shutil.copy2(backup, path)
        return fail(f"Kiểm tra thất bại, đã tự khôi phục file cũ: {exc}", 3)

    print(f"[OK] Đã áp dụng {VERSION}.")
    print("[ĐÃ SỬA] app.py")
    print("[ĐÃ SỬA] templates/admin.html")
    print(f"[BACKUP] {BACKUP_DIR.name}")
    print("[KHÔNG CẦN] SQL Supabase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
