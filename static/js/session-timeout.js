(function (global) {
    "use strict";

    const cfg = global.PES_SESSION_CONFIG || {};
    if (!cfg.enabled) return;

    const timeoutMs = Math.max(60_000, Number(cfg.idleTimeoutSeconds || 3600) * 1000);
    const warningMs = Math.max(30_000, Number(cfg.warningSeconds || 300) * 1000);
    const syncMs = Math.max(60_000, Number(cfg.activitySyncSeconds || 300) * 1000);
    const activityUrl = cfg.activityUrl;
    const timeoutCheckUrl = cfg.timeoutCheckUrl;
    const logoutUrl = cfg.logoutUrl;

    const activityStorageKey = "pes-session-last-activity";
    const syncStorageKey = "pes-session-last-sync";
    let lastActivityAt = Number(sessionStorage.getItem(activityStorageKey) || 0) || Date.now();
    let lastSyncAt = Number(sessionStorage.getItem(syncStorageKey) || 0) || 0;
    let activitySyncInFlight = false;
    let warningTimer = null;
    let logoutTimer = null;
    let countdownTimer = null;
    let checkInFlight = false;

    function ensureModal() {
        let root = document.getElementById("idleTimeoutModal");
        if (root) return root;
        root = document.createElement("div");
        root.id = "idleTimeoutModal";
        root.className = "idle-timeout-backdrop";
        root.hidden = true;
        root.innerHTML = `
            <div class="idle-timeout-card" role="dialog" aria-modal="true" aria-labelledby="idleTimeoutTitle">
                <div class="idle-timeout-icon">⏳</div>
                <h3 id="idleTimeoutTitle">Sắp tự động đăng xuất</h3>
                <p>Bạn chưa thao tác trên hệ thống trong thời gian dài.</p>
                <p>Phiên đăng nhập sẽ kết thúc sau <strong id="idleTimeoutCountdown">05:00</strong>.</p>
                <button id="idleTimeoutContinue" class="btn gold" type="button">Tôi vẫn đang sử dụng</button>
            </div>`;
        document.body.appendChild(root);
        root.querySelector("#idleTimeoutContinue").addEventListener("click", function () {
            recordActivity(true);
        });
        return root;
    }

    function hideModal() {
        const modal = document.getElementById("idleTimeoutModal");
        if (modal) modal.hidden = true;
        if (countdownTimer) clearInterval(countdownTimer);
        countdownTimer = null;
    }

    function showWarning() {
        const modal = ensureModal();
        modal.hidden = false;
        const label = modal.querySelector("#idleTimeoutCountdown");
        function update() {
            const remaining = Math.max(0, timeoutMs - (Date.now() - lastActivityAt));
            const total = Math.ceil(remaining / 1000);
            const minutes = String(Math.floor(total / 60)).padStart(2, "0");
            const seconds = String(total % 60).padStart(2, "0");
            if (label) label.textContent = `${minutes}:${seconds}`;
        }
        update();
        if (countdownTimer) clearInterval(countdownTimer);
        countdownTimer = setInterval(update, 1000);
    }

    function schedule() {
        clearTimeout(warningTimer);
        clearTimeout(logoutTimer);
        const elapsed = Date.now() - lastActivityAt;
        warningTimer = setTimeout(showWarning, Math.max(0, timeoutMs - warningMs - elapsed));
        logoutTimer = setTimeout(checkAndLogout, Math.max(0, timeoutMs - elapsed));
    }

    function syncActivity(force) {
        if (!activityUrl || !navigator.onLine || document.hidden || activitySyncInFlight) return;
        const now = Date.now();
        // Kể cả thao tác cưỡng bức cũng không vượt quá một request mỗi 60 giây.
        if (now - lastSyncAt < syncMs) return;
        activitySyncInFlight = true;
        lastSyncAt = now;
        try { sessionStorage.setItem(syncStorageKey, String(lastSyncAt)); } catch (error) {}
        fetch(activityUrl, {
            method: "POST",
            credentials: "same-origin",
            cache: "no-store",
            headers: {"X-Requested-With": "XMLHttpRequest"}
        }).catch(function () {}).finally(function () {
            activitySyncInFlight = false;
        });
    }

    function recordActivity(forceSync) {
        lastActivityAt = Date.now();
        try { sessionStorage.setItem(activityStorageKey, String(lastActivityAt)); } catch (error) {}
        hideModal();
        schedule();
        syncActivity(Boolean(forceSync));
    }

    function checkAndLogout() {
        if (checkInFlight || !timeoutCheckUrl) return;
        checkInFlight = true;
        fetch(timeoutCheckUrl, {credentials: "same-origin", cache: "no-store"})
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.protected === true) {
                    // Đang có trận cần hoàn tất: gia hạn 10 phút rồi kiểm tra lại.
                    lastActivityAt = Date.now() - Math.max(0, timeoutMs - 10 * 60 * 1000);
                    hideModal();
                    schedule();
                    return;
                }
                global.location.replace(logoutUrl + (logoutUrl.includes("?") ? "&" : "?") + "reason=inactive");
            })
            .catch(function () {
                // Nếu mất mạng, không ép đăng xuất ngay; thử lại sau 60 giây.
                logoutTimer = setTimeout(checkAndLogout, 60_000);
            })
            .finally(function () { checkInFlight = false; });
    }

    let eventThrottle = 0;
    function onUserActivity() {
        const now = Date.now();
        if (now - eventThrottle < 1000) return;
        eventThrottle = now;
        recordActivity(false);
    }

    ["pointerdown", "keydown", "touchstart", "submit"].forEach(function (name) {
        document.addEventListener(name, onUserActivity, {passive: true, capture: true});
    });
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            lastActivityAt = Date.now();
            try { sessionStorage.setItem(activityStorageKey, String(lastActivityAt)); } catch (error) {}
            hideModal();
            schedule();
            syncActivity(true);
        }
    });

    schedule();
})(window);
