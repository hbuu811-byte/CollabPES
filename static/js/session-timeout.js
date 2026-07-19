(function (global) {
    "use strict";

    const cfg = global.PES_SESSION_CONFIG || {};
    if (!cfg.enabled) return;
    if (global.__PES_SESSION_TIMEOUT_RUNNING__) return;
    global.__PES_SESSION_TIMEOUT_RUNNING__ = true;

    const timeoutMs = Math.max(60_000, Number(cfg.idleTimeoutSeconds || 3600) * 1000);
    const warningMs = Math.max(30_000, Number(cfg.warningSeconds || 300) * 1000);
    const syncMs = Math.max(60_000, Number(cfg.activitySyncSeconds || 300) * 1000);
    const activityUrl = cfg.activityUrl;
    const timeoutCheckUrl = cfg.timeoutCheckUrl;
    const logoutUrl = cfg.logoutUrl;

    let lastActivityAt = Date.now();
    let lastSyncAt = 0;
    let warningTimer = null;
    let logoutTimer = null;
    let countdownTimer = null;
    let checkInFlight = false;
    let activityInFlight = false;
    let lifecyclePaused = false;
    let destroyed = false;

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
        if (destroyed || lifecyclePaused) return;
        const elapsed = Date.now() - lastActivityAt;
        warningTimer = setTimeout(showWarning, Math.max(0, timeoutMs - warningMs - elapsed));
        logoutTimer = setTimeout(checkAndLogout, Math.max(0, timeoutMs - elapsed));
    }

    function syncActivity(force) {
        if (destroyed || lifecyclePaused || !activityUrl || !navigator.onLine || document.hidden || activityInFlight) {
            return Promise.resolve();
        }
        const now = Date.now();
        if (!force && now - lastSyncAt < syncMs) return Promise.resolve();

        activityInFlight = true;
        const task = function () {
            return fetch(activityUrl, {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
                headers: {"X-Requested-With": "XMLHttpRequest"}
            });
        };
        const request = global.PESNet && typeof global.PESNet.singleFlight === "function"
            ? global.PESNet.singleFlight("api:session-activity", task)
            : task();
        return Promise.resolve(request)
            .then(function (response) {
                if (response && response.ok) lastSyncAt = Date.now();
            })
            .catch(function () {})
            .finally(function () { activityInFlight = false; });
    }

    function recordActivity(forceSync) {
        lastActivityAt = Date.now();
        hideModal();
        schedule();
        syncActivity(Boolean(forceSync));
    }

    function checkAndLogout() {
        if (destroyed || lifecyclePaused || checkInFlight || !timeoutCheckUrl) return;
        checkInFlight = true;
        const task = function () {
            return fetch(timeoutCheckUrl, {credentials: "same-origin", cache: "no-store"});
        };
        const request = global.PESNet && typeof global.PESNet.singleFlight === "function"
            ? global.PESNet.singleFlight("api:session-timeout-check", task)
            : task();
        Promise.resolve(request)
            .then(function (res) {
                if (!res || !res.ok) throw new Error("timeout_check_failed");
                return res.json();
            })
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
                if (!destroyed && !lifecyclePaused) logoutTimer = setTimeout(checkAndLogout, 60_000);
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

    const activityEvents = ["pointerdown", "keydown", "touchstart", "submit"];
    activityEvents.forEach(function (name) {
        document.addEventListener(name, onUserActivity, {passive: true, capture: true});
    });

    function onVisibilityChange() {
        if (!document.hidden && !lifecyclePaused && !destroyed) recordActivity(false);
    }
    document.addEventListener("visibilitychange", onVisibilityChange);

    function pauseLifecycle() {
        lifecyclePaused = true;
        clearTimeout(warningTimer);
        clearTimeout(logoutTimer);
        if (countdownTimer) clearInterval(countdownTimer);
        countdownTimer = null;
    }

    function resumeLifecycle() {
        if (destroyed) return;
        lifecyclePaused = false;
        lastActivityAt = Date.now();
        hideModal();
        schedule();
    }

    function destroyLifecycle() {
        if (destroyed) return;
        destroyed = true;
        pauseLifecycle();
        activityEvents.forEach(function (name) {
            document.removeEventListener(name, onUserActivity, {capture: true});
        });
        document.removeEventListener("visibilitychange", onVisibilityChange);
        global.__PES_SESSION_TIMEOUT_RUNNING__ = false;
    }

    global.addEventListener("pagehide", function (event) {
        if (event.persisted) pauseLifecycle();
        else destroyLifecycle();
    });
    global.addEventListener("pageshow", function (event) {
        if (event.persisted) resumeLifecycle();
    });
    global.addEventListener("beforeunload", destroyLifecycle, {once: true});

    schedule();
})(window);
