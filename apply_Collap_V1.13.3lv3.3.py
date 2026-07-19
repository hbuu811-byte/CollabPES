#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Áp dụng tối ưu request Collap_V1.13.3lv3.3 lên Collap_V1.13.3lv3.2.

Chỉ sửa:
- app.py
- templates/base.html
- templates/room_detail.html

Không sửa RP, lịch sử trận, Admin, CSS, Supabase hoặc các module nghiệp vụ.
"""
from __future__ import annotations

import py_compile
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = {
    "app": ROOT / "app.py",
    "base": ROOT / "templates" / "base.html",
    "room": ROOT / "templates" / "room_detail.html",
}
BACKUP = ROOT / ".collap_v1_13_3lv3_3_backup"


class PatchError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PatchError(f"{label}: cần đúng 1 điểm ghép, tìm thấy {count}.")
    return text.replace(old, new, 1)


def regex_replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S | re.M)
    if count != 1:
        raise PatchError(f"{label}: không tìm thấy đúng cấu trúc dự kiến.")
    return updated


def backup_files() -> None:
    if BACKUP.exists():
        shutil.rmtree(BACKUP)
    for path in FILES.values():
        rel = path.relative_to(ROOT)
        target = BACKUP / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def restore_files() -> None:
    if not BACKUP.exists():
        return
    for path in FILES.values():
        rel = path.relative_to(ROOT)
        source = BACKUP / rel
        if source.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, path)


def patch_app(text: str) -> str:
    if 'APP_VERSION = "Collap_V1.13.3lv3.3"' in text:
        return text
    if 'APP_VERSION = "Collap_V1.13.3lv3.2"' not in text:
        raise PatchError("app.py không phải Collap_V1.13.3lv3.2.")
    text = text.replace(
        'APP_VERSION = "Collap_V1.13.3lv3.2"',
        'APP_VERSION = "Collap_V1.13.3lv3.3"',
        1,
    )

    # updated_at đã dư thừa vì mọi trường làm thay đổi giao diện đều nằm trong key.
    # Bỏ nó để các ghi chú/cập nhật phụ không kích hoạt thêm request /view.
    key_line = '        str(room.get("updated_at")),\n'
    if key_line in text:
        text = text.replace(key_line, "", 1)

    # Dùng chính request /state để duy trì online trong phòng, tối đa một lần/phút.
    anchor = '''def api_room_state(room_id):
    user = current_user()

    try:
'''
    replacement = '''def api_room_state(room_id):
    user = current_user()

    # Trang phòng đã gọi /state thường xuyên. Tận dụng request này để duy trì
    # trạng thái online, tránh phải chạy thêm một heartbeat HTTP riêng trong phòng.
    now_ts = int(time.time())
    last_presence_sync = int(session.get("room_state_presence_at", 0) or 0)
    if now_ts - last_presence_sync >= 60:
        try:
            mark_current_user_active()
            session["room_state_presence_at"] = now_ts
        except Exception as exc:
            app.logger.debug("Room state presence sync skipped: %s", exc)

    try:
'''
    text = replace_once(text, anchor, replacement, "gộp heartbeat vào /state")
    return text


def patch_base(text: str) -> str:
    # Thay toàn bộ khối poller toàn cục trong DOMContentLoaded. Ở trang phòng,
    # không chạy heartbeat/lời mời/thông báo vì /state đã duy trì online và người
    # đang thi đấu không cần popup lời mời hay thông báo nền tức thời.
    pattern = r'''    // Heartbeat 45 giây để khớp mốc online 90 giây; dừng hoàn toàn khi tab ẩn\.\n.*?    // Thông báo hệ thống mỗi 60 giây và dừng khi tab ẩn\.\n    PESNet\.createPoller\(\{key: "system-announcement".*?\}\);'''
    replacement = '''    if (!isRoomPage) {
        // Ngoài phòng: heartbeat 60 giây vẫn đủ an toàn với mốc online 90 giây.
        PESNet.createPoller({key: "global-heartbeat", task: postHeartbeat, visibleInterval: 60000, hiddenInterval: 180000, runWhenHidden: false, immediate: false, jitter: 4000, timeoutMs: 12000});

        // Không kiểm tra lời mời trong phòng đấu. Ngoài phòng giữ một poller duy nhất.
        if (!PESNet.hasPoller || !PESNet.hasPoller("pending-invites")) {
            PESNet.createPoller({key: "pending-invites", task: checkPendingInvites, visibleInterval: 18000, hiddenInterval: 180000, runWhenHidden: false, immediate: true, jitter: 1500, timeoutMs: 12000});
        }

        // Không kiểm tra active-room ở chính trang phòng.
        PESNet.createPoller({key: "active-room", task: checkActiveRoom, visibleInterval: isRankingPage ? 45000 : 30000, hiddenInterval: 180000, runWhenHidden: false, immediate: false, jitter: 3000, timeoutMs: 12000});

        // Chat sảnh chỉ chạy khi người dùng thực sự mở khung chat.
        if (typeof isLobbyChatOpen !== "undefined" && isLobbyChatOpen) {
            PESNet.createPoller({key: "lobby-chat", task: loadBottomChatSmart, visibleInterval: 30000, hiddenInterval: 180000, runWhenHidden: false, immediate: true, jitter: 2500, timeoutMs: 12000});
        }

        // Thông báo hệ thống không cần chạy trong lúc đang thi đấu.
        PESNet.createPoller({key: "system-announcement", task: checkAnnouncementSmart, visibleInterval: 90000, hiddenInterval: 240000, runWhenHidden: false, immediate: false, jitter: 5000, timeoutMs: 12000});
    }'''
    return regex_replace_once(text, pattern, replacement, "giảm poller toàn cục trong phòng")


def patch_room(text: str) -> str:
    if "roomStateStablePolls" not in text:
        variable_anchor = "let roomViewRefreshInFlight = false;\n"
        if variable_anchor not in text:
            raise PatchError("Không tìm thấy biến roomViewRefreshInFlight.")
        text = text.replace(
            variable_anchor,
            variable_anchor + "let roomStateStablePolls = 0;\n",
            1,
        )

    # Poll nhanh sau thay đổi, rồi tự giãn khi phòng đứng yên.
    interval_pattern = r'''function getRoomStateInterval\(\) \{\n.*?\n\}'''
    interval_replacement = '''function getRoomStateInterval() {
    let baseInterval = 10000;
    if (currentRoomStatus === "waiting_result_confirm") {
        baseInterval = currentRoomUserIsGuest ? 2200 : 4500;
    } else if (currentRoomStatus === "playing") {
        baseInterval = currentRoomUserIsGuest ? 4000 : 7500;
    } else if (currentRoomStatus === "friendly_playing") {
        baseInterval = 10000;
    } else if (currentRoomStatus === "waiting_ready") {
        baseInterval = currentRoomUserIsGuest ? 4000 : 5000;
    } else if (currentRoomStatus === "confirmed") {
        baseInterval = 7000;
    }

    // Sau nhiều lần không đổi, tự giãn để giảm request. Khi có thay đổi,
    // roomStateStablePolls được đặt lại 0 và tốc độ phản hồi nhanh trở lại.
    if (roomStateStablePolls >= 8) return Math.min(18000, Math.round(baseInterval * 2.4));
    if (roomStateStablePolls >= 4) return Math.min(13000, Math.round(baseInterval * 1.6));
    return baseInterval;
}'''
    text = regex_replace_once(text, interval_pattern, interval_replacement, "polling /state thích ứng")

    old_unchanged = '''        if (!result || result.status === 204 || result.status === 304) return null;
'''
    new_unchanged = '''        if (!result) return null;
        if (result.status === 204 || result.status === 304) {
            roomStateStablePolls = Math.min(20, roomStateStablePolls + 1);
            return null;
        }
'''
    text = replace_once(text, old_unchanged, new_unchanged, "đếm trạng thái phòng không đổi")

    old_changed = '''        if (data.state_key && data.state_key !== currentRoomStateKey) {
            return refreshRoomLiveContent(data.state_key, signal);
        }
'''
    new_changed = '''        if (data.state_key && data.state_key !== currentRoomStateKey) {
            roomStateStablePolls = 0;
            return refreshRoomLiveContent(data.state_key, signal);
        }
'''
    text = replace_once(text, old_changed, new_changed, "đặt lại backoff khi trạng thái đổi")

    # Chat phòng giảm từ 15 giây xuống chu kỳ động 30/60 giây.
    old_chat = '''        visibleInterval: 15000,
        hiddenInterval: 60000,
'''
    new_chat = '''        interval: function () {
            const chatBox = document.getElementById("roomChatBox");
            if (!chatBox) return 60000;
            const rect = chatBox.getBoundingClientRect();
            const visible = rect.bottom > 0 && rect.top < window.innerHeight;
            return visible ? 30000 : 60000;
        },
        hiddenInterval: 120000,
'''
    text = replace_once(text, old_chat, new_chat, "giãn polling chat phòng")

    # Khi người dùng thao tác trong phòng, quay lại chu kỳ nhanh ngay sau trang mới.
    dom_anchor = '''window.addEventListener("DOMContentLoaded", function () {
    bindRoomLiveControls();
    if (!window.PESNet) return;
'''
    dom_replacement = '''window.addEventListener("DOMContentLoaded", function () {
    bindRoomLiveControls();
    const liveContent = document.getElementById("roomLiveContent");
    if (liveContent) {
        liveContent.addEventListener("pointerdown", function () {
            roomStateStablePolls = 0;
        }, {passive: true});
    }
    if (!window.PESNet) return;
'''
    text = replace_once(text, dom_anchor, dom_replacement, "đặt lại polling nhanh khi có thao tác")
    return text


def validate() -> None:
    app_text = FILES["app"].read_text(encoding="utf-8")
    base_text = FILES["base"].read_text(encoding="utf-8")
    room_text = FILES["room"].read_text(encoding="utf-8")

    required = [
        'APP_VERSION = "Collap_V1.13.3lv3.3"',
        'session["room_state_presence_at"]',
    ]
    for marker in required:
        if marker not in app_text:
            raise PatchError(f"Thiếu marker sau vá: {marker}")
    if 'str(room.get("updated_at"))' in app_text:
        raise PatchError("updated_at vẫn còn trong room state key.")
    if 'if (!isRoomPage) {' not in base_text:
        raise PatchError("Poller toàn cục chưa được tắt trong phòng.")
    if 'roomStateStablePolls' not in room_text:
        raise PatchError("Polling thích ứng chưa được áp dụng.")
    if 'visibleInterval: 15000' in room_text:
        raise PatchError("Chat phòng vẫn còn chu kỳ 15 giây.")
    if 'window.location.reload()' in room_text or 'location.reload()' in room_text:
        raise PatchError("Trang phòng xuất hiện reload toàn trang.")

    py_compile.compile(str(FILES["app"]), doraise=True)

    try:
        from jinja2 import Environment
        env = Environment()
        env.parse(base_text)
        env.parse(room_text)
    except ImportError:
        pass


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in FILES.values() if not path.exists()]
    if missing:
        print("[LỖI] Thiếu file:", ", ".join(missing))
        print("Hãy chép bộ vá vào thư mục gốc Collap_V1.13.3lv3.2 rồi chạy lại.")
        return 1

    app_original = FILES["app"].read_text(encoding="utf-8")
    if 'APP_VERSION = "Collap_V1.13.3lv3.3"' in app_original:
        print("[OK] Dự án đã là Collap_V1.13.3lv3.3.")
        return 0

    try:
        backup_files()
        FILES["app"].write_text(patch_app(app_original), encoding="utf-8")
        FILES["base"].write_text(
            patch_base(FILES["base"].read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        FILES["room"].write_text(
            patch_room(FILES["room"].read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        validate()
    except Exception as exc:
        restore_files()
        print(f"[LỖI] {exc}")
        print("Đã tự khôi phục toàn bộ file cũ. Không có code dở dang được giữ lại.")
        return 2

    print("[OK] Đã áp dụng Collap_V1.13.3lv3.3.")
    print("[ĐÃ SỬA] app.py")
    print("[ĐÃ SỬA] templates/base.html")
    print("[ĐÃ SỬA] templates/room_detail.html")
    print("[BACKUP] .collap_v1_13_3lv3_3_backup")
    print("[SQL] Không cần chạy SQL Supabase.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
