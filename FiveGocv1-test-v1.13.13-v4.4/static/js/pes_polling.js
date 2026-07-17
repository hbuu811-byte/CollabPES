(function (global) {
    "use strict";

    function createPoller(options) {
        const task = options && options.task;
        if (typeof task !== "function") throw new Error("PESNet.createPoller requires task");

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
            clearTimeout(timer);
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
            clearTimeout(timer);
            run();
        }

        function stop() {
            stopped = true;
            clearTimeout(timer);
        }

        document.addEventListener("visibilitychange", function () {
            if (stopped) return;
            if (!document.hidden) runNow();
            else schedule();
        });
        global.addEventListener("online", runNow);
        global.addEventListener("pagehide", stop, {once: true});

        if (options.immediate === false) schedule();
        else runNow();

        return {runNow: runNow, stop: stop};
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
            return response.json().then(function (data) {
                return {ok: response.ok, status: response.status, data: data};
            });
        }).finally(function () {
            clearTimeout(timeout);
        });
    }

    global.PESNet = {
        createPoller: createPoller,
        fetchJson: fetchJson
    };
})(window);
