(function (global) {
    "use strict";

    const registry = global.__PES_POLLERS__ || (global.__PES_POLLERS__ = Object.create(null));
    const allPollers = global.__PES_ALL_POLLERS__ || (global.__PES_ALL_POLLERS__ = new Set());
    const requestRegistry = global.__PES_REQUESTS__ || (global.__PES_REQUESTS__ = Object.create(null));

    function numericInterval(value, fallback) {
        let resolved = value;
        if (typeof value === "function") {
            try { resolved = value(); } catch (error) { resolved = fallback; }
        }
        return Math.max(1000, Number(resolved || fallback || 10000));
    }

    function abortError(reason) {
        try {
            return new DOMException(String(reason || "Request aborted"), "AbortError");
        } catch (error) {
            const fallback = new Error(String(reason || "Request aborted"));
            fallback.name = "AbortError";
            return fallback;
        }
    }

    function abortRequest(key, reason) {
        const requestKey = String(key || "").trim();
        const entry = requestKey ? requestRegistry[requestKey] : null;
        if (!entry) return false;
        try { entry.controller.abort(reason || "request-aborted"); } catch (error) {}
        return true;
    }

    function abortRequestsByPrefix(prefix, reason) {
        const normalized = String(prefix || "");
        Object.keys(requestRegistry).forEach(function (key) {
            if (key.indexOf(normalized) === 0) abortRequest(key, reason || "prefix-abort");
        });
    }

    function abortAllRequests(reason) {
        Object.keys(requestRegistry).forEach(function (key) {
            abortRequest(key, reason || "abort-all");
        });
    }

    function requestOnce(key, executor, options) {
        const requestKey = String(key || "").trim();
        const settings = options || {};
        if (!requestKey) return Promise.resolve().then(function () { return executor(settings.signal); });

        const existing = requestRegistry[requestKey];
        // Tương thích nếu file script cũ từng lưu trực tiếp Promise trong registry.
        if (existing && typeof existing.then === "function") return existing;
        if (existing && existing.promise) return existing.promise;

        const controller = new AbortController();
        const externalSignal = settings.signal || null;
        let detachExternalAbort = null;

        if (externalSignal) {
            const relayAbort = function () {
                try { controller.abort(externalSignal.reason || "caller-aborted"); } catch (error) {}
            };
            if (externalSignal.aborted) relayAbort();
            else {
                externalSignal.addEventListener("abort", relayAbort, {once: true});
                detachExternalAbort = function () {
                    externalSignal.removeEventListener("abort", relayAbort);
                };
            }
        }

        const entry = {controller: controller, promise: null};
        const tracked = Promise.resolve()
            .then(function () {
                if (controller.signal.aborted) throw abortError(controller.signal.reason);
                return executor(controller.signal);
            })
            .finally(function () {
                if (detachExternalAbort) detachExternalAbort();
                if (requestRegistry[requestKey] === entry) delete requestRegistry[requestKey];
            });

        entry.promise = tracked;
        requestRegistry[requestKey] = entry;
        return tracked;
    }

    function createPoller(options) {
        options = options || {};
        const task = options.task;
        if (typeof task !== "function") throw new Error("PESNet.createPoller requires task");

        const key = String(options.key || "").trim();
        if (key && registry[key] && typeof registry[key].stop === "function") {
            registry[key].stop("replaced");
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
                .then(function () {
                    if (stopped || !requestController) return;
                    return task(requestController.signal);
                })
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

        function stop(reason) {
            if (stopped) return;
            stopped = true;
            rerunRequested = false;
            clearTimeout(timer);
            abortInFlight();

            document.removeEventListener("visibilitychange", onVisibilityChange);
            global.removeEventListener("online", runNow);
            global.removeEventListener("pagehide", onPageHide);
            global.removeEventListener("pageshow", onPageShow);
            global.removeEventListener("beforeunload", onBeforeUnload);

            allPollers.delete(api);
            if (key && registry[key] === api) delete registry[key];

            if (typeof options.onStop === "function") {
                try { options.onStop(reason || "stopped"); } catch (ignored) {}
            }
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

        function onPageHide(event) {
            if (event && event.persisted) {
                rerunRequested = false;
                clearTimeout(timer);
                abortInFlight();
                return;
            }
            stop("pagehide");
        }

        function onPageShow(event) {
            if (event && event.persisted && !stopped) runNow();
        }

        function onBeforeUnload() {
            stop("beforeunload");
        }

        const api = {
            key: key,
            runNow: runNow,
            stop: stop,
            isInFlight: function () { return inFlight; },
            isStopped: function () { return stopped; }
        };

        document.addEventListener("visibilitychange", onVisibilityChange);
        global.addEventListener("online", runNow);
        global.addEventListener("pagehide", onPageHide);
        global.addEventListener("pageshow", onPageShow);
        global.addEventListener("beforeunload", onBeforeUnload);

        allPollers.add(api);
        if (key) registry[key] = api;
        if (options.immediate === false) schedule();
        else runNow();

        return api;
    }

    function stopAll(reason) {
        const stopReason = reason || "stop-all";
        Array.from(allPollers).forEach(function (poller) {
            try { poller.stop(stopReason); } catch (error) {}
        });
        abortAllRequests(stopReason);
    }

    function stopByPrefix(prefix, reason) {
        const normalized = String(prefix || "");
        Object.keys(registry).forEach(function (key) {
            if (key.indexOf(normalized) !== 0) return;
            const poller = registry[key];
            if (poller && typeof poller.stop === "function") {
                poller.stop(reason || "prefix-stop");
            }
        });
    }

    function hasPoller(key) {
        const poller = registry[String(key || "")];
        return Boolean(poller && typeof poller.isStopped === "function" && !poller.isStopped());
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
                return {ok: response.ok, status: response.status, data: null, response: response};
            }

            const contentType = String(response.headers.get("content-type") || "").toLowerCase();
            if (contentType.indexOf("application/json") === -1) {
                return response.text().then(function (text) {
                    return {ok: response.ok, status: response.status, data: null, text: text, response: response};
                });
            }

            return response.json().then(function (data) {
                return {ok: response.ok, status: response.status, data: data, response: response};
            });
        }).finally(function () {
            if (timeout) clearTimeout(timeout);
        });
    }

    function fetchJsonOnce(key, url, options, timeoutMs) {
        const config = Object.assign({}, options || {});
        const callerSignal = config.signal || null;
        delete config.signal;
        return requestOnce(key, function (sharedSignal) {
            config.signal = sharedSignal;
            return fetchJson(url, config, timeoutMs);
        }, {signal: callerSignal});
    }

    function fetchText(url, options, timeoutMs) {
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
                return {ok: response.ok, status: response.status, text: "", response: response};
            }
            return response.text().then(function (text) {
                return {ok: response.ok, status: response.status, text: text, response: response};
            });
        }).finally(function () {
            if (timeout) clearTimeout(timeout);
        });
    }

    function fetchTextOnce(key, url, options, timeoutMs) {
        const config = Object.assign({}, options || {});
        const callerSignal = config.signal || null;
        delete config.signal;
        return requestOnce(key, function (sharedSignal) {
            config.signal = sharedSignal;
            return fetchText(url, config, timeoutMs);
        }, {signal: callerSignal});
    }

    global.PESNet = {
        createPoller: createPoller,
        stopAll: stopAll,
        stopByPrefix: stopByPrefix,
        hasPoller: hasPoller,
        requestOnce: requestOnce,
        abortRequest: abortRequest,
        abortRequestsByPrefix: abortRequestsByPrefix,
        abortAllRequests: abortAllRequests,
        fetchJson: fetchJson,
        fetchJsonOnce: fetchJsonOnce,
        fetchText: fetchText,
        fetchTextOnce: fetchTextOnce
    };
})(window);
