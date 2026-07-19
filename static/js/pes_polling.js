(function (global) {
    "use strict";

    // Một registry chung cho toàn bộ document. Cùng một key luôn chỉ có một
    // poller; poller cũ được dừng trước khi poller mới được đăng ký.
    const pollers = global.__PES_POLLERS__ || new Map();
    const requests = global.__PES_REQUEST_LOCKS__ || new Map();
    global.__PES_POLLERS__ = pollers;
    global.__PES_REQUEST_LOCKS__ = requests;

    let pagePaused = false;

    function resolveInterval(value, fallback) {
        let resolved = value;
        if (typeof resolved === "function") {
            try { resolved = resolved(); } catch (error) { resolved = fallback; }
        }
        resolved = Number(resolved);
        if (!Number.isFinite(resolved)) resolved = Number(fallback || 10000);
        return Math.max(1000, resolved);
    }

    function createPoller(options) {
        options = options || {};
        const task = options.task;
        if (typeof task !== "function") throw new Error("PESNet.createPoller requires task");

        const key = String(options.key || "").trim();
        if (key && pollers.has(key)) {
            try { pollers.get(key).stop(); } catch (error) {}
        }

        const visibleIntervalOption = options.visibleInterval || 10000;
        const hiddenIntervalOption = options.hiddenInterval || 60000;
        const runWhenHidden = options.runWhenHidden === true;
        const jitter = Math.max(0, Number(options.jitter || 0));
        let timer = null;
        let stopped = false;
        let paused = pagePaused;
        let inFlight = false;

        function delayForCurrentState() {
            const visibleInterval = resolveInterval(visibleIntervalOption, 10000);
            const hiddenInterval = Math.max(
                visibleInterval,
                resolveInterval(hiddenIntervalOption, 60000)
            );
            const base = document.hidden ? hiddenInterval : visibleInterval;
            if (!jitter || document.hidden) return base;
            return Math.max(1000, base + Math.round((Math.random() * 2 - 1) * jitter));
        }

        function clearTimer() {
            if (timer) clearTimeout(timer);
            timer = null;
        }

        function schedule(delay) {
            if (stopped || paused) return;
            clearTimer();
            timer = setTimeout(run, typeof delay === "number" ? delay : delayForCurrentState());
        }

        function run() {
            if (stopped || paused) return;
            if (!navigator.onLine || (document.hidden && !runWhenHidden)) {
                schedule();
                return;
            }
            if (inFlight) {
                schedule();
                return;
            }

            inFlight = true;
            Promise.resolve()
                .then(task)
                .catch(function () {})
                .finally(function () {
                    inFlight = false;
                    schedule();
                });
        }

        function runNow() {
            if (stopped || paused || inFlight || !navigator.onLine) return;
            clearTimer();
            run();
        }

        function pause() {
            if (stopped || paused) return;
            paused = true;
            clearTimer();
        }

        function resume(runImmediately) {
            if (stopped) return;
            paused = false;
            if (runImmediately === false) schedule();
            else runNow();
        }

        function stop() {
            if (stopped) return;
            stopped = true;
            paused = true;
            clearTimer();
            document.removeEventListener("visibilitychange", handleVisibility);
            global.removeEventListener("online", handleOnline);
            if (key && pollers.get(key) === controller) pollers.delete(key);
        }

        function handleVisibility() {
            if (stopped || paused) return;
            if (!document.hidden) runNow();
            else if (runWhenHidden) schedule();
            else clearTimer();
        }

        function handleOnline() {
            if (!document.hidden || runWhenHidden) runNow();
        }

        const controller = {
            runNow: runNow,
            stop: stop,
            pause: pause,
            resume: resume,
            key: key,
            get inFlight() { return inFlight; }
        };

        if (key) pollers.set(key, controller);
        document.addEventListener("visibilitychange", handleVisibility);
        global.addEventListener("online", handleOnline);

        if (!paused) {
            if (options.immediate === false) schedule();
            else runNow();
        }

        return controller;
    }

    function stopPoller(key) {
        const normalized = String(key || "").trim();
        const poller = pollers.get(normalized);
        if (!poller) return false;
        try { poller.stop(); } catch (error) {}
        return true;
    }

    function pauseAllPollers() {
        pagePaused = true;
        Array.from(pollers.values()).forEach(function (poller) {
            try { poller.pause(); } catch (error) {}
        });
    }

    function resumeAllPollers() {
        pagePaused = false;
        Array.from(pollers.values()).forEach(function (poller) {
            try { poller.resume(true); } catch (error) {}
        });
    }

    function stopAllPollers() {
        pagePaused = true;
        Array.from(pollers.values()).forEach(function (poller) {
            try { poller.stop(); } catch (error) {}
        });
        pollers.clear();
    }

    // Khóa request dùng chung giữa nhiều script. Nếu cùng key đang chạy, mọi
    // nơi gọi sau đều nhận lại đúng Promise hiện tại thay vì tạo request mới.
    function singleFlight(key, task) {
        const normalized = String(key || "").trim();
        if (!normalized || typeof task !== "function") {
            return Promise.resolve().then(task);
        }
        if (requests.has(normalized)) return requests.get(normalized);

        const promise = Promise.resolve()
            .then(task)
            .finally(function () {
                if (requests.get(normalized) === promise) requests.delete(normalized);
            });
        requests.set(normalized, promise);
        return promise;
    }

    function fetchJson(url, options, timeoutMs) {
        const controller = new AbortController();
        const timeout = setTimeout(function () {
            controller.abort();
        }, Math.max(2000, Number(timeoutMs || 12000)));
        const config = Object.assign({
            credentials: "same-origin",
            cache: "no-store",
            signal: controller.signal
        }, options || {});

        return fetch(url, config).then(function (response) {
            if (response.status === 204 || response.status === 304) {
                return {
                    ok: response.ok,
                    status: response.status,
                    data: null,
                    response: response
                };
            }
            return response.json().then(function (data) {
                return {
                    ok: response.ok,
                    status: response.status,
                    data: data,
                    response: response
                };
            });
        }).finally(function () {
            clearTimeout(timeout);
        });
    }

    global.addEventListener("pagehide", function (event) {
        // BFCache giữ document để quay lại nhanh: chỉ tạm dừng. Khi rời hẳn
        // trang, dừng và tháo toàn bộ listener/timer cũ.
        if (event.persisted) pauseAllPollers();
        else stopAllPollers();
    });
    global.addEventListener("pageshow", function (event) {
        if (event.persisted) resumeAllPollers();
    });
    global.addEventListener("beforeunload", stopAllPollers, {once: true});

    global.PESNet = {
        createPoller: createPoller,
        stop: stopPoller,
        pauseAll: pauseAllPollers,
        resumeAll: resumeAllPollers,
        stopAll: stopAllPollers,
        singleFlight: singleFlight,
        fetchJson: fetchJson
    };
})(window);
