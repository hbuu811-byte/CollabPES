#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Áp dụng cập nhật phòng theo sự kiện cho Collap_V1.13.3lv3.3.

Chỉ sửa:
- app.py
- templates/room_detail.html

Không sửa RP, lịch sử, Admin, CSS, Supabase hoặc module nghiệp vụ.
"""
from __future__ import annotations

import py_compile
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
ROOM = ROOT / "templates" / "room_detail.html"
FILES = (APP, ROOM)
BACKUP = ROOT / ".collap_v1_13_3lv3_4_backup"


class PatchError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PatchError(f"{label}: cần đúng 1 điểm ghép, tìm thấy {count}.")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S | re.M)
    if count != 1:
        raise PatchError(f"{label}: không tìm thấy đúng cấu trúc dự kiến.")
    return updated


def backup() -> None:
    if BACKUP.exists():
        shutil.rmtree(BACKUP)
    for path in FILES:
        rel = path.relative_to(ROOT)
        target = BACKUP / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def restore() -> None:
    if not BACKUP.exists():
        return
    for path in FILES:
        source = BACKUP / path.relative_to(ROOT)
        if source.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, path)


def patch_app(text: str) -> str:
    if 'APP_VERSION = "Collap_V1.13.3lv3.4"' in text:
        return text
    if 'APP_VERSION = "Collap_V1.13.3lv3.3"' not in text:
        raise PatchError("app.py không phải Collap_V1.13.3lv3.3.")
    text = text.replace(
        'APP_VERSION = "Collap_V1.13.3lv3.3"',
        'APP_VERSION = "Collap_V1.13.3lv3.4"',
        1,
    )

    # Chuyển redirect của các POST trong phòng thành JSON + HTML động. Nhờ đó
    # trình duyệt không tải lại base.html, CSS, JS và toàn bộ trang.
    after_anchor = '''@app.after_request
def set_device_cookie(response):
    device_id = getattr(g, "new_device_id", None)
'''
    after_replacement = '''@app.after_request
def set_device_cookie(response):
    # Request thao tác phòng bằng AJAX không đi theo redirect để tải lại toàn
    # trang. Server trả thẳng HTML động mới nhất và thông báo cần thiết.
    if (
        request.headers.get("X-PES-Room-Action") == "1"
        and response.status_code in {301, 302, 303, 307, 308}
    ):
        location = response.headers.get("Location") or ""
        path_parts = [part for part in str(request.path or "").split("/") if part]
        room_id = path_parts[1] if len(path_parts) >= 2 and path_parts[0] == "room" else None
        flash_rows = session.pop("_flashes", []) or []
        flash_messages = [
            {"category": str(row[0] or "info"), "message": str(row[1] or "")}
            for row in flash_rows
            if isinstance(row, (list, tuple)) and len(row) >= 2
        ]

        payload = {
            "ok": True,
            "redirect_url": location,
            "stay_in_room": False,
            "messages": flash_messages,
        }

        if room_id and f"/room/{room_id}" in location:
            try:
                room = get_room(room_id)
                if room:
                    payload.update({
                        "stay_in_room": True,
                        "redirect_url": None,
                        "state_key": build_room_state_key(room),
                        "html": render_template(
                            "_room_live_content.html",
                            **build_room_template_context(room),
                        ),
                    })
                else:
                    payload.update({"ok": False, "error": "room_not_found"})
            except Exception as exc:
                app.logger.warning("Room AJAX response render failed room=%s: %s", room_id, exc)
                payload.update({
                    "ok": False,
                    "error": "temporary_render_error",
                    "retry_url": url_for("api_room_view", room_id=room_id),
                })

        response = make_response(jsonify(payload), 200 if payload.get("ok") else 503)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["X-PES-Room-Action"] = "1"

    device_id = getattr(g, "new_device_id", None)
'''
    text = replace_once(text, after_anchor, after_replacement, "AJAX hóa redirect phòng")

    # Chat chỉ gửi danh sách khi có tin mới. 204 giữ nguyên DOM và cache hiện tại.
    chat_pattern = r'''@app\.route\("/api/room/<room_id>/chat"\)\n@login_required\ndef api_room_chat\(room_id\):\n.*?\n\n@app\.route\("/room/<room_id>/chat/send", methods=\["POST"\]\)'''
    chat_replacement = '''@app.route("/api/room/<room_id>/chat")
@login_required
def api_room_chat(room_id):
    """Chat phòng chỉ trả dữ liệu khi danh sách tin nhắn thật sự thay đổi."""
    user = current_user()
    if not system_feature_enabled("room_chat_enabled"):
        return jsonify({"ok": True, "messages": [], "disabled": True})

    try:
        result = execute_query(
            db.table("match_rooms")
            .select("id,host_user_id,guest_user_id,status")
            .eq("id", room_id)
            .limit(1),
            "api_room_chat_membership",
            attempts=2,
        )
    except Exception as exc:
        app.logger.warning("Room chat membership load failed room=%s: %s", room_id, exc)
        return jsonify({"ok": False, "error": "temporary_db_error"}), 503

    room = dict(result.data[0]) if result.data else None
    if not room:
        return jsonify({"ok": True, "messages": [], "closed": True})

    is_room_member = (
        _same_user_id(user.get("id"), room.get("host_user_id"))
        or _same_user_id(user.get("id"), room.get("guest_user_id"))
    )
    if not is_room_member and not is_admin_user(user):
        if not room.get("guest_user_id") or room.get("status") == "cancelled":
            return jsonify({"ok": True, "messages": [], "closed": True})
        return jsonify({"ok": False, "error": "forbidden"}), 403

    messages = list_chat_messages("room", room_id=room_id, limit=20)
    latest = messages[-1] if messages else {}
    chat_key = "|".join([
        str(len(messages)),
        str(latest.get("id") or ""),
        str(latest.get("created_at") or ""),
        str(latest.get("message") or ""),
    ])
    since = (request.args.get("since") or "").strip()
    if since and since == chat_key:
        response = app.response_class(status=204)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    response = jsonify({"ok": True, "messages": messages, "chat_key": chat_key})
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.route("/room/<room_id>/chat/send", methods=["POST"])'''
    text = regex_once(text, chat_pattern, chat_replacement, "chat theo sự kiện")
    return text


def patch_room(text: str) -> str:
    # Các biến quản lý sự kiện/cache; không tạo thêm poller.
    variable_anchor = '''let roomViewRefreshInFlight = false;
let roomStateStablePolls = 0;
'''
    variable_replacement = '''let roomViewRefreshInFlight = false;
let roomStateStablePolls = 0;
let roomEventSyncInFlight = false;
let roomEventSyncController = null;
let roomSafetySyncTimer = null;
let roomChatSafetyTimer = null;
let currentRoomChatServerKey = "";
const roomHtmlCacheKey = "pes-room-html-cache:{{ room.id }}";
const roomStateCacheKey = "pes-room-state-cache:{{ room.id }}";
const roomEventChannel = typeof BroadcastChannel === "function"
    ? new BroadcastChannel("pes-room-events:{{ room.id }}")
    : null;
'''
    text = replace_once(text, variable_anchor, variable_replacement, "biến event/cache phòng")

    # Thay innerHTML bằng bộ vá DOM đệ quy. Chỉ node/thuộc tính/text đổi mới bị cập nhật.
    refresh_pattern = r'''function refreshRoomLiveContent\(nextStateKey, signal\) \{\n.*?\n\}\n\nfunction checkRoomState\(signal\) \{'''
    refresh_replacement = r'''function roomNodeKey(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return "";
    if (node.id) return "id:" + node.id;
    const fragmentKey = node.getAttribute("data-room-fragment");
    if (fragmentKey) return "fragment:" + fragmentKey;
    if (node.tagName === "FORM") {
        const action = node.getAttribute("action") || "";
        if (action) return "form:" + action + ":" + (node.getAttribute("method") || "get");
    }
    return "";
}

function syncRoomAttributes(current, incoming) {
    const incomingNames = new Set(Array.from(incoming.attributes || []).map(function (attr) { return attr.name; }));
    Array.from(current.attributes || []).forEach(function (attr) {
        if (!incomingNames.has(attr.name)) current.removeAttribute(attr.name);
    });
    Array.from(incoming.attributes || []).forEach(function (attr) {
        if (current.getAttribute(attr.name) !== attr.value) current.setAttribute(attr.name, attr.value);
    });
}

function morphRoomNode(current, incoming) {
    if (!current || !incoming) return;
    if (current.nodeType !== incoming.nodeType) {
        current.replaceWith(incoming.cloneNode(true));
        return;
    }
    if (current.nodeType === Node.TEXT_NODE || current.nodeType === Node.COMMENT_NODE) {
        if (current.nodeValue !== incoming.nodeValue) current.nodeValue = incoming.nodeValue;
        return;
    }
    if (current.tagName !== incoming.tagName) {
        current.replaceWith(incoming.cloneNode(true));
        return;
    }

    const active = current === document.activeElement;
    const oldValue = active && "value" in current ? current.value : null;
    const oldSelectionStart = active && typeof current.selectionStart === "number" ? current.selectionStart : null;
    const oldSelectionEnd = active && typeof current.selectionEnd === "number" ? current.selectionEnd : null;
    const wasOpen = current.tagName === "DETAILS" && current.open;

    syncRoomAttributes(current, incoming);

    const oldChildren = Array.from(current.childNodes);
    const keyedOld = new Map();
    oldChildren.forEach(function (child) {
        const key = roomNodeKey(child);
        if (key && !keyedOld.has(key)) keyedOld.set(key, child);
    });

    Array.from(incoming.childNodes).forEach(function (incomingChild, index) {
        const key = roomNodeKey(incomingChild);
        let currentChild = key ? keyedOld.get(key) : current.childNodes[index];
        if (currentChild && currentChild !== current.childNodes[index]) {
            current.insertBefore(currentChild, current.childNodes[index] || null);
        }
        if (!currentChild) {
            current.appendChild(incomingChild.cloneNode(true));
            return;
        }
        const currentKey = roomNodeKey(currentChild);
        if (key && currentKey && key !== currentKey) {
            current.insertBefore(incomingChild.cloneNode(true), currentChild);
            return;
        }
        morphRoomNode(currentChild, incomingChild);
    });

    while (current.childNodes.length > incoming.childNodes.length) {
        current.removeChild(current.lastChild);
    }

    if (wasOpen && current.tagName === "DETAILS") current.open = true;
    if (active && oldValue !== null && "value" in current) {
        current.value = oldValue;
        current.focus({preventScroll: true});
        if (oldSelectionStart !== null && typeof current.setSelectionRange === "function") {
            try { current.setSelectionRange(oldSelectionStart, oldSelectionEnd); } catch (error) {}
        }
    }
}

function patchRoomLiveContent(html) {
    const target = document.getElementById("roomLiveContent");
    if (!target || !html) return false;
    const cached = sessionStorage.getItem(roomHtmlCacheKey) || "";
    if (cached === html) return false;

    const template = document.createElement("template");
    template.innerHTML = String(html).trim();
    const incomingRoot = document.createElement("div");
    Array.from(target.attributes || []).forEach(function (attr) {
        incomingRoot.setAttribute(attr.name, attr.value);
    });
    incomingRoot.appendChild(template.content.cloneNode(true));
    const snapshot = captureRoomFormState();

    morphRoomNode(target, incomingRoot);
    restoreRoomFormState(snapshot);
    bindRoomLiveControls();
    sessionStorage.setItem(roomHtmlCacheKey, html);
    return true;
}

function refreshRoomLiveContent(nextStateKey, signal) {
    if (roomViewRefreshInFlight) return Promise.resolve(false);
    const target = document.getElementById("roomLiveContent");
    if (!target) return Promise.resolve(false);

    roomViewRefreshInFlight = true;
    return fetch("{{ url_for('api_room_view', room_id=room.id) }}", {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: {"X-Requested-With": "XMLHttpRequest"},
        signal: signal
    })
    .then(function (response) {
        if (response.status === 401 || response.status === 403 || response.status === 404) {
            stopAllRoomPolling("room-view-closed");
            window.location.href = "{{ url_for('dashboard') }}";
            return "";
        }
        if (!response.ok) throw new Error("room_view_" + response.status);
        return response.text();
    })
    .then(function (html) {
        if (!html) return false;
        const changed = patchRoomLiveContent(html);
        if (typeof currentRoomChatKey !== "undefined") currentRoomChatKey = "";
        currentRoomStateKey = nextStateKey || currentRoomStateKey;
        sessionStorage.setItem(roomStateCacheKey, currentRoomStateKey || "");
        return changed;
    })
    .finally(function () {
        roomViewRefreshInFlight = false;
    });
}

function checkRoomState(signal) {'''
    text = regex_once(text, refresh_pattern, refresh_replacement, "vá DOM thay vì innerHTML")

    # Không dùng poller liên tục. Sự kiện người dùng/focus/online chạy ngay; watchdog rất thưa.
    bootstrap_pattern = r'''window\.addEventListener\("DOMContentLoaded", function \(\) \{\n    bindRoomLiveControls\(\);\n.*?\n\}\);\n\nwindow\.addEventListener\("pagehide", function \(\) \{\n    stopAllRoomPolling\("room-pagehide"\);\n\}, \{once: true\}\);'''
    bootstrap_replacement = r'''function getRoomSafetyInterval() {
    if (currentRoomStatus === "waiting_result_confirm") return currentRoomUserIsGuest ? 8000 : 15000;
    if (currentRoomStatus === "waiting_ready") return 15000;
    if (currentRoomStatus === "confirmed") return 15000;
    if (currentRoomStatus === "playing" || currentRoomStatus === "friendly_playing") return 60000;
    return 30000;
}

function scheduleRoomSafetySync() {
    if (roomSafetySyncTimer) window.clearTimeout(roomSafetySyncTimer);
    if (document.hidden) return;
    roomSafetySyncTimer = window.setTimeout(function () {
        requestRoomEventSync("safety-watchdog");
    }, getRoomSafetyInterval());
}

function requestRoomEventSync(reason) {
    if (document.hidden || !navigator.onLine || roomEventSyncInFlight) {
        scheduleRoomSafetySync();
        return Promise.resolve(false);
    }
    roomEventSyncInFlight = true;
    if (roomEventSyncController) roomEventSyncController.abort();
    roomEventSyncController = new AbortController();
    return checkRoomState(roomEventSyncController.signal)
        .catch(function (error) {
            if (!error || error.name !== "AbortError") return false;
            return false;
        })
        .finally(function () {
            roomEventSyncInFlight = false;
            roomEventSyncController = null;
            scheduleRoomSafetySync();
        });
}

function broadcastRoomEvent(reason) {
    if (!roomEventChannel) return;
    try { roomEventChannel.postMessage({type: "room-change", reason: reason || "action", at: Date.now()}); } catch (error) {}
}

function bootRoomEventMode() {
    bindRoomLiveControls();
    const target = document.getElementById("roomLiveContent");
    if (target) sessionStorage.setItem(roomHtmlCacheKey, target.innerHTML);
    sessionStorage.setItem(roomStateCacheKey, currentRoomStateKey || "");

    if (typeof PESNet !== "undefined" && typeof PESNet.stopByPrefix === "function") {
        PESNet.stopByPrefix("room-state:", "event-mode");
        PESNet.stopByPrefix("room-chat:", "event-mode");
    }
    requestRoomEventSync("initial");
}

if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", bootRoomEventMode, {once: true});
} else {
    bootRoomEventMode();
}

if (roomEventChannel) {
    roomEventChannel.addEventListener("message", function (event) {
        if (event.data && event.data.type === "room-change") requestRoomEventSync("broadcast");
    });
}

document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
        if (roomSafetySyncTimer) window.clearTimeout(roomSafetySyncTimer);
        if (roomEventSyncController) roomEventSyncController.abort();
    } else {
        requestRoomEventSync("visible");
        requestRoomChatSync("visible");
    }
});
window.addEventListener("focus", function () { requestRoomEventSync("focus"); });
window.addEventListener("online", function () { requestRoomEventSync("online"); });
window.addEventListener("pageshow", function (event) {
    if (event.persisted) requestRoomEventSync("pageshow");
});
window.addEventListener("pagehide", function () {
    if (roomSafetySyncTimer) window.clearTimeout(roomSafetySyncTimer);
    if (roomChatSafetyTimer) window.clearTimeout(roomChatSafetyTimer);
    if (roomEventChannel) roomEventChannel.close();
    stopAllRoomPolling("room-pagehide");
}, {once: true});'''
    text = regex_once(text, bootstrap_pattern, bootstrap_replacement, "khởi động event mode")

    # Chat: gửi since, 204 nếu không đổi, chỉ kiểm tra ngay sau sự kiện/focus + watchdog.
    chat_function_pattern = r'''function loadRoomChat\(signal\) \{\n.*?\n\}\n\nwindow\.addEventListener\("DOMContentLoaded", function \(\) \{\n.*?window\.PESRoomChatPoller = PESNet\.createPoller\(\{.*?\n    \}\);\n\}\);'''
    chat_function_replacement = r'''function loadRoomChat(signal) {
    if (document.hidden) return Promise.resolve(false);

    const url = new URL("{{ url_for('api_room_chat', room_id=room.id) }}", window.location.origin);
    if (currentRoomChatServerKey) url.searchParams.set("since", currentRoomChatServerKey);
    const options = {credentials: "same-origin", cache: "no-store", signal: signal};
    const request = window.PESNet && typeof PESNet.fetchJsonOnce === "function"
        ? PESNet.fetchJsonOnce("request:room-chat:{{ room.id }}", url.toString(), options, 12000)
        : fetch(url.toString(), options).then(function (res) {
            if (res.status === 204) return {ok: true, status: 204, data: null};
            return res.json().then(function (data) { return {ok: res.ok, status: res.status, data: data}; });
        });

    return request.then(function (result) {
        if (!result || result.status === 204 || result.status === 304) return false;
        const data = result.data || {};
        if (data.disabled || data.closed || result.status === 404) {
            stopRoomChatPolling();
            return false;
        }
        if (result.status === 401 || result.status === 403) {
            stopRoomChatPolling();
            return false;
        }
        if (!result.ok) throw new Error("room_chat_" + result.status);
        if (data.chat_key) currentRoomChatServerKey = data.chat_key;
        if (data.ok) renderRoomChat(data.messages || []);
        return true;
    }).catch(function (error) {
        if (!error || error.name !== "AbortError") return false;
        return false;
    });
}

function scheduleRoomChatSafetySync() {
    if (roomChatSafetyTimer) window.clearTimeout(roomChatSafetyTimer);
    if (document.hidden) return;
    roomChatSafetyTimer = window.setTimeout(function () {
        requestRoomChatSync("chat-watchdog");
    }, 60000);
}

function requestRoomChatSync(reason) {
    return loadRoomChat().finally(scheduleRoomChatSafetySync);
}

if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", function () { requestRoomChatSync("initial"); }, {once: true});
} else {
    requestRoomChatSync("initial");
}'''
    text = regex_once(text, chat_function_pattern, chat_function_replacement, "chat theo sự kiện")

    # Thay submit thường bằng AJAX. POST trả HTML mới, không reload trang.
    submit_pattern = r'''document\.addEventListener\("submit", function \(event\) \{\n    const form = event\.target;\n    if \(!form \|\| form\.classList\.contains\("room-exit-confirm-form"\)\) return;\n.*?\n\}, true\);'''
    submit_replacement = r'''function showRoomActionMessage(payload) {
    const messages = payload && Array.isArray(payload.messages) ? payload.messages : [];
    const important = messages.find(function (item) {
        return ["danger", "warning", "error"].includes(String(item.category || "").toLowerCase());
    });
    if (!important) return;
    if (window.PESRoomActionModal && typeof window.PESRoomActionModal.showNotice === "function") {
        window.PESRoomActionModal.showNotice({
            tone: important.category === "danger" || important.category === "error" ? "danger" : "warning",
            icon: important.category === "danger" || important.category === "error" ? "×" : "⚠",
            title: "Thông báo phòng đấu",
            message: important.message || "Không thể hoàn tất thao tác.",
            confirmLabel: "Đã hiểu"
        });
    }
}

function submitRoomAction(form) {
    if (!form || form.dataset.roomSubmitting === "1") return Promise.resolve(false);
    form.dataset.roomSubmitting = "1";
    const buttons = Array.from(form.querySelectorAll("button, input[type='submit']"));
    buttons.forEach(function (button) { button.disabled = true; });

    if (window.PESNet && typeof PESNet.abortRequestsByPrefix === "function") {
        PESNet.abortRequestsByPrefix("request:room-state:", "room-action");
        PESNet.abortRequestsByPrefix("request:room-chat:", "room-action");
    }

    return fetch(form.action || window.location.href, {
        method: String(form.method || "POST").toUpperCase(),
        body: new FormData(form),
        credentials: "same-origin",
        cache: "no-store",
        redirect: "follow",
        headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-PES-Room-Action": "1",
            "Accept": "application/json"
        }
    })
    .then(function (response) {
        const contentType = String(response.headers.get("content-type") || "").toLowerCase();
        if (contentType.indexOf("application/json") === -1) throw new Error("room_action_non_json");
        return response.json().then(function (payload) {
            if (!response.ok && !payload) throw new Error("room_action_" + response.status);
            return payload || {};
        });
    })
    .then(function (payload) {
        showRoomActionMessage(payload);
        if (payload.redirect_url && !payload.stay_in_room) {
            stopAllRoomPolling("room-action-redirect");
            window.location.href = payload.redirect_url;
            return true;
        }
        if (!payload.ok) {
            if (payload.retry_url) return refreshRoomLiveContent(currentRoomStateKey).then(function () { return false; });
            return false;
        }
        if (payload.html) patchRoomLiveContent(payload.html);
        if (payload.state_key) {
            currentRoomStateKey = payload.state_key;
            sessionStorage.setItem(roomStateCacheKey, currentRoomStateKey);
        }
        roomStateStablePolls = 0;
        broadcastRoomEvent("room-action");
        scheduleRoomSafetySync();
        requestRoomChatSync("room-action");
        return true;
    })
    .catch(function () {
        showRoomActionMessage({messages: [{category: "warning", message: "Kết nối vừa bị gián đoạn. Giao diện hiện tại được giữ nguyên; hãy thử lại."}]});
        return false;
    })
    .finally(function () {
        delete form.dataset.roomSubmitting;
        buttons.forEach(function (button) { button.disabled = false; });
    });
}

document.addEventListener("submit", function (event) {
    const form = event.target;
    if (!form || form.classList.contains("room-exit-confirm-form")) return;
    let actionPath = "";
    try { actionPath = new URL(form.action || window.location.href, window.location.origin).pathname; } catch (error) {}
    if (actionPath.indexOf("/room/{{ room.id }}/") !== 0) return;
    event.preventDefault();
    submitRoomAction(form);
}, true);'''
    text = regex_once(text, submit_pattern, submit_replacement, "AJAX hóa form phòng")

    # Modal thoát dùng cùng AJAX; chỉ chuyển trang khi backend thật sự yêu cầu.
    native_submit = '''        stopAllRoomPolling("confirmed-room-exit");
        window.setTimeout(function () {
            HTMLFormElement.prototype.submit.call(formToSubmit);
        }, 120);
'''
    ajax_submit = '''        window.setTimeout(function () {
            submitRoomAction(formToSubmit).finally(function () {
                submitting = false;
            });
        }, 120);
'''
    text = replace_once(text, native_submit, ajax_submit, "thoát phòng không reload trung gian")
    return text


def validate() -> None:
    app_text = APP.read_text(encoding="utf-8")
    room_text = ROOM.read_text(encoding="utf-8")
    markers = [
        'APP_VERSION = "Collap_V1.13.3lv3.4"',
        'X-PES-Room-Action',
        'chat_key',
        'patchRoomLiveContent',
        'submitRoomAction',
        'requestRoomEventSync',
    ]
    combined = app_text + "\n" + room_text
    for marker in markers:
        if marker not in combined:
            raise PatchError(f"Thiếu marker sau vá: {marker}")
    if 'window.location.reload()' in room_text or 'location.reload()' in room_text:
        raise PatchError("room_detail.html vẫn có reload toàn trang.")
    if 'target.innerHTML = html' in room_text:
        raise PatchError("Vẫn còn thay toàn bộ roomLiveContent bằng innerHTML.")
    if 'PESNet.createPoller({\n        key: "room-state:' in room_text:
        raise PatchError("Poller /state cũ vẫn còn hoạt động.")
    py_compile.compile(str(APP), doraise=True)
    try:
        from jinja2 import Environment
        Environment().parse(room_text)
    except ImportError:
        pass


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in FILES if not path.exists()]
    if missing:
        print("[LỖI] Thiếu file:", ", ".join(missing))
        print("Hãy chép bộ vá vào thư mục gốc Collap_V1.13.3lv3.3 rồi chạy lại.")
        return 1

    if 'APP_VERSION = "Collap_V1.13.3lv3.4"' in APP.read_text(encoding="utf-8"):
        print("[OK] Dự án đã là Collap_V1.13.3lv3.4.")
        return 0

    try:
        backup()
        APP.write_text(patch_app(APP.read_text(encoding="utf-8")), encoding="utf-8")
        ROOM.write_text(patch_room(ROOM.read_text(encoding="utf-8")), encoding="utf-8")
        validate()
    except Exception as exc:
        restore()
        print(f"[LỖI] {exc}")
        print("Đã tự khôi phục toàn bộ file cũ. Không giữ code dở dang.")
        return 2

    print("[OK] Đã áp dụng Collap_V1.13.3lv3.4.")
    print("[ĐÃ SỬA] app.py")
    print("[ĐÃ SỬA] templates/room_detail.html")
    print("[BACKUP] .collap_v1_13_3lv3_4_backup")
    print("[SQL] Không cần chạy SQL Supabase.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
