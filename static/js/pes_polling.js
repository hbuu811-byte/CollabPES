(function (global) {
    "use strict";

    const pollerRegistry = Object.create(null);
    const requestRegistry = Object.create(null);

    function isAbortError(error) {
        return Boolean(error && (error.name === "AbortError" || String(error).includes("AbortError")));
    }

    function runLocked(key, task, externalSignal) {
        const lockKey = String(key || "").trim();
        if (!lockKey) return Promise.resolve().then(function () { return task(); });
        if (requestRegistry[lockKey]) return requestRegistry[lockKey].promise;

        const controller = new AbortController();
        let removeExternalAbort = null;
        if (externalSignal) {
            const abortFromExternal = function () { controller.abort(); };
            if (externalSignal.aborted) controller.abort();
            else {
                externalSignal.addEventListener("abort", abortFromExternal, {once: true});
                removeExternalAbort = function () {
                    externalSignal.removeEventListener("abort", abortFromExternal);
                };
            }
        }

        const promise = Promise.resolve()
            .then(function () { return task(controller.signal); })
            .finally(function () {
                if (removeExternalAbort) removeExternalAbort();
                if (requestRegistry[lockKey] && requestRegistry[lockKey].promise === promise) {
                    delete requestRegistry[lockKey];
                }
            });

        requestRegistry[lockKey] = {promise: promise, controller: controller};
        return promise;
    }

    function abortRequest(key) {
        const lockKey = String(key || "").trim();
        const current = requestRegistry[lockKey];
        if (!current) return;
        current.controller.abort();
    }

    function abortAllRequests() {
        Object.keys(requestRegistry).forEach(abortRequest);
    }

    function createPoller(options) {
        const settings = options || {};
        const task = settings.task;
        if (typeof task !== "function") throw new Error("PESNet.createPoller requires task");

        const visibleInterval = Math.max(1000, Number(settings.visibleInterval || 10000));
        const hiddenInterval = Math.max(visibleInterval, Number(settings.hiddenInterval || 60000));
        const runWhenHidden = settings.runWhenHidden === true;
        const jitter = Math.max(0, Number(settings.jitter || 0));
        const key = String(settings.key || "").trim();

        if (key && pollerRegistry[key]) pollerRegistry[key].stop();

        let timer = null;
        let stopped = false;
        let paused = false;
        let inFlight = false;
        let taskController = null;

        function delayForCurrentState() {
            const base = document.hidden ? hiddenInterval : visibleInterval;
            if (!jitter) return base;
            return Math.max(1000, base + Math.round((Math.random() * 2 - 1) * jitter));
        }

        function clearTimer() {
            if (timer) clearTimeout(timer);
            timer = null;
        }

        function abortTask() {
            if (taskController) taskController.abort();
            taskController = null;
        }

        function schedule(delay) {
            if (stopped || paused) return;
            if (document.hidden && !runWhenHidden) {
                clearTimer();
                return;
            }
            clearTimer();
            timer = setTimeout(run, typeof delay === "number" ? delay : delayForCurrentState());
        }

        function run() {
            if (stopped || paused) return Promise.resolve();
            if (!navigator.onLine) {
                schedule();
                return Promise.resolve();
            }
            if (document.hidden && !runWhenHidden) {
                clearTimer();
                return Promise.resolve();
            }
            if (inFlight) return Promise.resolve();

            inFlight = true;
            taskController = new AbortController();
            const signal = taskController.signal;
            const promise = Promise.resolve()
                .then(function () { return task(signal); })
                .catch(function (error) {
                    if (!isAbortError(error)) {
                        // Polling lỗi tạm thời được bỏ qua; chu kỳ sau sẽ thử lại.
                    }
                })
                .finally(function () {
                    inFlight = false;
                    taskController = null;
                    if (!stopped && !paused) schedule();
                });
            return promise;
        }

        function runNow() {
            if (stopped || paused || inFlight || !navigator.onLine) return Promise.resolve();
            if (document.hidden && !runWhenHidden) return Promise.resolve();
            clearTimer();
            return run();
        }

        function pause() {
            if (stopped) return;
            paused = true;
            clearTimer();
            abortTask();
        }

        function resume(immediate) {
            if (stopped) return;
            paused = false;
            if (immediate === false) schedule();
            else runNow();
        }

        function removeListeners() {
            document.removeEventListener("visibilitychange", onVisibilityChange);
            global.removeEventListener("online", onOnline);
            global.removeEventListener("pagehide", onPageHide);
            global.removeEventListener("pageshow", onPageShow);
            global.removeEventListener("beforeunload", onBeforeUnload);
        }

        function stop() {
            if (stopped) return;
            stopped = true;
            paused = false;
            clearTimer();
            abortTask();
            removeListeners();
            if (key && pollerRegistry[key] === api) delete pollerRegistry[key];
        }

        function onVisibilityChange() {
            if (stopped) return;
            if (document.hidden && !runWhenHidden) pause();
            else if (!document.hidden) resume(true);
            else schedule();
        }

        function onOnline() {
            if (!document.hidden || runWhenHidden) resume(true);
        }

        function onPageHide(event) {
            if (event && event.persisted) pause();
            else stop();
        }

        function onPageShow(event) {
            if (event && event.persisted) resume(true);
        }

        function onBeforeUnload() {
            stop();
        }

        const api = {
            runNow: runNow,
            stop: stop,
            pause: pause,
            resume: resume,
            isRunning: function () { return !stopped && !paused; }
        };

        document.addEventListener("visibilitychange", onVisibilityChange);
        global.addEventListener("online", onOnline);
        global.addEventListener("pagehide", onPageHide);
        global.addEventListener("pageshow", onPageShow);
        global.addEventListener("beforeunload", onBeforeUnload);

        if (key) pollerRegistry[key] = api;
        if (settings.immediate === false) schedule();
        else runNow();
        return api;
    }

    function stopPoller(key) {
        const poller = pollerRegistry[String(key || "").trim()];
        if (poller) poller.stop();
    }

    function stopAllPollers() {
        Object.keys(pollerRegistry).forEach(stopPoller);
    }

    function fetchJson(url, options, timeoutMs, lockKey, externalSignal) {
        const task = function (signal) {
            const timeoutController = new AbortController();
            const timeout = setTimeout(function () {
                timeoutController.abort();
            }, Math.max(2000, Number(timeoutMs || 12000)));

            const combinedController = new AbortController();
            const abortCombined = function () { combinedController.abort(); };
            if (signal) {
                if (signal.aborted) combinedController.abort();
                else signal.addEventListener("abort", abortCombined, {once: true});
            }
            if (externalSignal) {
                if (externalSignal.aborted) combinedController.abort();
                else externalSignal.addEventListener("abort", abortCombined, {once: true});
            }
            timeoutController.signal.addEventListener("abort", abortCombined, {once: true});

            const config = Object.assign({
                credentials: "same-origin",
                cache: "no-store",
                signal: combinedController.signal
            }, options || {});

            return fetch(url, config)
                .then(function (response) {
                    if (response.status === 204) {
                        return {ok: response.ok, status: response.status, data: null};
                    }
                    return response.text().then(function (text) {
                        let data = null;
                        try { data = text ? JSON.parse(text) : null; } catch (error) {}
                        return {ok: response.ok, status: response.status, data: data};
                    });
                })
                .finally(function () {
                    clearTimeout(timeout);
                    if (signal) signal.removeEventListener("abort", abortCombined);
                    if (externalSignal) externalSignal.removeEventListener("abort", abortCombined);
                });
        };

        return lockKey ? runLocked(lockKey, task, externalSignal) : task(externalSignal);
    }

    global.PESNet = {
        createPoller: createPoller,
        stopPoller: stopPoller,
        stopAllPollers: stopAllPollers,
        runLocked: runLocked,
        abortRequest: abortRequest,
        abortAllRequests: abortAllRequests,
        fetchJson: fetchJson
    };
})(window);
