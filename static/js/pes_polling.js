(function (global) {
    "use strict";

    const registry = global.__PES_POLLERS__ || (global.__PES_POLLERS__ = Object.create(null));

    function numericInterval(value, fallback) {
        let resolved = value;
        if (typeof value === "function") {
            try { resolved = value(); } catch (error) { resolved = fallback; }
        }
        return Math.max(1000, Number(resolved || fallback || 10000));
    }

    function createPoller(options) {
        options = options || {};
        const task = options.task;
        if (typeof task !== "function") throw new Error("PESNet.createPoller requires task");

        const key = String(options.key || "").trim();
        if (key && registry[key] && typeof registry[key].stop === "function") {
            registry[key].stop();
        }

        const runWhenHidden = options.runWhenHidden === true;
        const jitter = Math.max(0, Number(options.jitter || 0));
        const timeoutMs = Math.max(2000, Number(options.timeoutMs || 15000));
        let timer = null;
        let stopped = false;
        let inFlight = false;
        let rerunRequested = false;
        let requestController = null;
        let requestTimeout = null;

        function visibleInterval() {
            return numericInterval(
                typeof options.interval !== "undefined" ? options.interval : options.visibleInterval,
                10000
            );
        }

        function hiddenInterval() {
            return numericInterval(options.hiddenInterval, Math.max(60000, visibleInterval()));
        }

        function delayForCurrentState() {
            const base = document.hidden ? hiddenInterval() : visibleInterval();
            if (!jitter || document.hidden) return base;
            return Math.max(1000, base + Math.round((Math.random() * 2 - 1) * jitter));
        }

        function clearRequestResources() {
            if (requestTimeout) clearTimeout(requestTimeout);
            requestTimeout = null;
            requestController = null;
        }

        function abortInFlight() {
            if (requestController) {
                try { requestController.abort(); } catch (error) {}
            }
            clearRequestResources();
        }

        function schedule(delay) {
            if (stopped) return;
            clearTimeout(timer);
            timer = setTimeout(run, typeof delay === "number" ? Math.max(0, delay) : delayForCurrentState());
        }

        function finishRun() {
            inFlight = false;
            clearRequestResources();
            if (stopped) return;
            if (rerunRequested && !document.hidden) {
                rerunRequested = false;
                schedule(0);
                return;
            }
            schedule();
        }

        function run() {
            if (stopped) return;
            if (!navigator.onLine || (document.hidden && !runWhenHidden)) {
                schedule();
                return;
            }
            if (inFlight) {
                rerunRequested = true;
                return;
            }

            inFlight = true;
            requestController = new AbortController();
            requestTimeout = setTimeout(function () {
                if (requestController) requestController.abort();
            }, timeoutMs);

            Promise.resolve()
                .then(function () { return task(requestController.signal); })
                .catch(function (error) {
                    if (!error || error.name !== "AbortError") {
                        if (typeof options.onError === "function") {
                            try { options.onError(error); } catch (ignored) {}
                        }
                    }
                })
                .finally(finishRun);
        }

        function runNow() {
            if (stopped || !navigator.onLine || (document.hidden && !runWhenHidden)) return;
            clearTimeout(timer);
            if (inFlight) {
                rerunRequested = true;
                return;
            }
            run();
        }

        function stop() {
            if (stopped) return;
            stopped = true;
            rerunRequested = false;
            clearTimeout(timer);
            abortInFlight();
            if (key && registry[key] === api) delete registry[key];
        }

        function onVisibilityChange() {
            if (stopped) return;
            if (document.hidden) {
                rerunRequested = false;
                if (!runWhenHidden) abortInFlight();
                schedule();
            } else {
                runNow();
            }
        }

        const api = {
            runNow: runNow,
            stop: stop,
            isInFlight: function () { return inFlight; }
        };

        document.addEventListener("visibilitychange", onVisibilityChange);
        global.addEventListener("online", runNow);
        global.addEventListener("pagehide", stop, {once: true});

        if (key) registry[key] = api;
        if (options.immediate === false) schedule();
        else runNow();

        return api;
    }

    function fetchJson(url, options, timeoutMs) {
        const supplied = options && options.signal;
        const controller = supplied ? null : new AbortController();
        const timeout = controller
            ? setTimeout(function () { controller.abort(); }, Math.max(2000, Number(timeoutMs || 12000)))
            : null;
        const config = Object.assign({
            credentials: "same-origin",
            cache: "no-store",
            signal: supplied || controller.signal
        }, options || {});

        return fetch(url, config).then(function (response) {
            if (response.status === 204 || response.status === 304) {
                return {ok: response.ok, status: response.status, data: null};
            }
            return response.json().then(function (data) {
                return {ok: response.ok, status: response.status, data: data};
            });
        }).finally(function () {
            if (timeout) clearTimeout(timeout);
        });
    }

    global.PESNet = {
        createPoller: createPoller,
        fetchJson: fetchJson
    };
})(window);
