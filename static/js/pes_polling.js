(function (global) {
    "use strict";

    // Registry bảo đảm mỗi chức năng chỉ có một poller trên một document.
    // Nếu cùng key được khởi tạo lại, poller cũ được dừng trước.
    const pollers = global.__PES_POLLERS__ || new Map();
    global.__PES_POLLERS__ = pollers;

    function createPoller(options) {
        options = options || {};
        const task = options.task;
        if (typeof task !== "function") throw new Error("PESNet.createPoller requires task");

        const key = String(options.key || "").trim();
        if (key && pollers.has(key)) {
            try { pollers.get(key).stop(); } catch (error) {}
        }

        const visibleInterval = Math.max(1000, Number(options.visibleInterval || 10000));
        const hiddenInterval = Math.max(visibleInterval, Number(options.hiddenInterval || 60000));
        const runWhenHidden = options.runWhenHidden === true;
        const jitter = Math.max(0, Number(options.jitter || 0));
        let timer = null;
        let stopped = false;
        let inFlight = false;

        function delayForCurrentState() {
            const base = document.hidden ? hiddenInterval : visibleInterval;
            if (!jitter) return base;
            return Math.max(1000, base + Math.round((Math.random() * 2 - 1) * jitter));
        }

        function schedule(delay) {
            if (stopped) return;
            if (timer) clearTimeout(timer);
            timer = setTimeout(run, typeof delay === "number" ? delay : delayForCurrentState());
        }

        function run() {
            if (stopped) return;
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
            if (stopped || inFlight || !navigator.onLine) return;
            if (timer) clearTimeout(timer);
            timer = null;
            run();
        }

        function stop() {
            if (stopped) return;
            stopped = true;
            if (timer) clearTimeout(timer);
            timer = null;
            if (key && pollers.get(key) === controller) pollers.delete(key);
        }

        function handleVisibility() {
            if (stopped) return;
            if (!document.hidden) runNow();
            else schedule(hiddenInterval);
        }

        const controller = {runNow: runNow, stop: stop, key: key};
        if (key) pollers.set(key, controller);

        document.addEventListener("visibilitychange", handleVisibility);
        global.addEventListener("online", runNow);

        if (options.immediate === false) schedule();
        else runNow();

        return controller;
    }

    function stopAllPollers() {
        Array.from(pollers.values()).forEach(function (poller) {
            try { poller.stop(); } catch (error) {}
        });
        pollers.clear();
    }

    function fetchJson(url, options, timeoutMs) {
        const controller = new AbortController();
        const timeout = setTimeout(function () { controller.abort(); }, Math.max(2000, Number(timeoutMs || 12000)));
        const config = Object.assign({
            credentials: "same-origin",
            cache: "no-store",
            signal: controller.signal
        }, options || {});

        return fetch(url, config).then(function (response) {
            if (response.status === 204) return {ok: response.ok, status: response.status, data: null};
            return response.json().then(function (data) {
                return {ok: response.ok, status: response.status, data: data};
            });
        }).finally(function () {
            clearTimeout(timeout);
        });
    }

    global.addEventListener("pagehide", stopAllPollers, {once: true});

    global.PESNet = {
        createPoller: createPoller,
        stopAll: stopAllPollers,
        fetchJson: fetchJson
    };
})(window);
