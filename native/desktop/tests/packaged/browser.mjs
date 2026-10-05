// Functions that run inside the window's documents. Playwright serializes each
// one, so a function here uses only its argument and browser globals.

/**
 * Instruments every new document of the window before its own scripts run.
 *
 * Every frame records CSP violations, console warnings and errors, framed
 * messages, key and context-menu events (and whether a page prevented their
 * default action), print requests and a load marker. The shell document also
 * records each host IPC request, keeps the launch token it sends out of reach
 * of every other frame, and observes every channel frame Tauri delivers into
 * it. Nothing here changes what a document's own code sees or does, except
 * where the harness explicitly holds acknowledgements, suppresses page
 * handlers for one event, or intercepts an external-open request.
 */
export function instrument(config) {
  if (Object.getOwnPropertyDescriptor(window, "__s10")) return;
  const top = window.top === window;
  const role = top
    ? config.shellOrigins.includes(location.origin)
      ? "shell"
      : "top-other"
    : location.origin === config.docsOrigin
      ? "docs"
      : "frame-other";
  const limit = (list, max, item) => {
    if (list.length < max) list.push(item);
  };
  const text = (value, max = 400) => String(value).slice(0, max);
  const state = {
    role,
    origin: location.origin,
    href: location.href,
    marker: Math.random().toString(36).slice(2),
    startedAt: Date.now(),
    csp: [],
    console: [],
    messages: [],
    keys: [],
    menus: [],
    beforeprint: 0,
    suppressPageHandlers: false,
  };
  Object.defineProperty(window, "__s10", { value: state, enumerable: false });

  document.addEventListener(
    "securitypolicyviolation",
    (event) =>
      limit(state.csp, 500, {
        at: Date.now(),
        directive: event.effectiveDirective,
        blocked: text(event.blockedURI, 200),
        source: text(event.sourceFile, 200),
        line: event.lineNumber,
        disposition: event.disposition,
        sample: text(event.sample, 80),
      }),
    true,
  );
  for (const level of ["warn", "error"]) {
    const original = console[level];
    console[level] = function (...args) {
      limit(state.console, 2000, {
        at: Date.now(),
        level,
        text: args.map((arg) => text(arg?.message ?? arg, 300)).join(" "),
      });
      return original.apply(this, args);
    };
  }
  window.addEventListener("message", (event) => {
    const data = event.data;
    limit(state.messages, 500, {
      at: Date.now(),
      origin: event.origin,
      fromParent: event.source === window.parent && !top,
      channel: data && typeof data === "object" ? text(data.channel, 40) : "",
      type: data && typeof data === "object" ? text(data.type, 40) : "",
    });
  });
  // Registered before any page script, so these listeners run first. When the
  // harness suppresses page handlers, nothing in the page can prevent the
  // default action: only the webview's own settings decide what happens.
  const watch = (type, list) =>
    window.addEventListener(
      type,
      (event) => {
        const suppressed = state.suppressPageHandlers;
        if (suppressed) event.stopImmediatePropagation();
        setTimeout(() =>
          limit(list, 500, {
            at: Date.now(),
            type,
            key:
              event.target?.type === "password"
                ? "<password-key>"
                : (event.key ?? ""),
            code:
              event.target?.type === "password"
                ? "<password-key>"
                : (event.code ?? ""),
            ctrl: !!event.ctrlKey,
            button: event.button ?? null,
            trusted: event.isTrusted,
            prevented: event.defaultPrevented,
            suppressed,
          }),
        );
      },
      true,
    );
  watch("keydown", state.keys);
  watch("contextmenu", state.menus);
  window.addEventListener("beforeprint", () => {
    state.beforeprint += 1;
  });
  if (role !== "shell") return;

  // Shell document only. The token the shell sends with its first command is
  // kept in this closure; only `call` uses it, and it is never recorded.
  let token = null;
  let sequence = 0;
  let held = null;
  const ipc = [];
  const channels = {};
  const sessions = {};
  const logs = { batches: 0, records: [] };
  state.ipc = ipc;
  state.channels = channels;
  state.sessions = sessions;
  state.logs = logs;
  state.external = [];
  state.blockExternal = !!config.blockExternal;
  state.tokenSeen = false;
  state.tokenGetter = null;
  const channelOf = (id) =>
    (channels[id] ??= {
      kind: null,
      session: null,
      frames: 0,
      seen: 0,
      maxIndex: -1,
      outOfOrder: 0,
      next: 0,
      dataBytes: 0,
      dataFrames: 0,
      acked: 0,
      maxUnacked: 0,
      lastDataAt: 0,
      started: null,
      exited: null,
      failed: [],
      altScreen: false,
      tail: "",
    });
  const ALT_SCREEN = "\x1b[?1049h";
  const observe = (id, data) => {
    if (!data || typeof data !== "object" || !("index" in data)) return;
    const message = data.message;
    if (message && typeof message === "object" && "records" in message) {
      logs.batches += 1;
      for (const record of message.records ?? [])
        limit(logs.records, 20000, {
          at: Date.now(),
          seq: record.seq,
          source: text(record.source, 20),
          level: record.level,
          logger: text(record.logger ?? "", 120),
          message: text(record.message, 300),
        });
      return;
    }
    const channel = channelOf(id);
    channel.frames += 1;
    channel.seen += 1;
    if (data.index !== channel.next) channel.outOfOrder += 1;
    channel.next = data.index + 1;
    channel.maxIndex = Math.max(channel.maxIndex, data.index);
    let bytes = null;
    if (message instanceof ArrayBuffer) bytes = new Uint8Array(message);
    else if (ArrayBuffer.isView(message))
      bytes = new Uint8Array(
        message.buffer,
        message.byteOffset,
        message.byteLength,
      );
    else if (Array.isArray(message)) bytes = Uint8Array.from(message);
    if (!bytes || !bytes.length) return;
    const payload = bytes.subarray(1);
    const json = () => {
      try {
        return JSON.parse(new TextDecoder().decode(payload));
      } catch {
        return null;
      }
    };
    switch (bytes[0]) {
      case 0: {
        channel.dataBytes += payload.length;
        channel.dataFrames += 1;
        channel.lastDataAt = Date.now();
        channel.maxUnacked = Math.max(
          channel.maxUnacked,
          channel.dataBytes - channel.acked,
        );
        if (!channel.altScreen) {
          let latin = channel.tail;
          for (let i = 0; i < payload.length; i += 8192)
            latin += String.fromCharCode(...payload.subarray(i, i + 8192));
          channel.altScreen = latin.includes(ALT_SCREEN);
          channel.tail = latin.slice(-ALT_SCREEN.length);
        }
        break;
      }
      case 1:
        channel.started = { at: Date.now(), pid: json()?.pid ?? null };
        break;
      case 2:
        channel.exited = { at: Date.now(), code: json()?.code ?? null };
        break;
      case 3:
        channel.failed.push(text(json()?.error?.code ?? "unknown", 60));
        break;
      default:
    }
  };
  const wrap = () => {
    const callbacks = window.__TAURI_INTERNALS__?.callbacks;
    if (!(callbacks instanceof Map) || callbacks.__s10) return;
    Object.defineProperty(callbacks, "__s10", { value: true });
    const set = callbacks.set.bind(callbacks);
    const watched = (id, callback) => (data) => {
      try {
        observe(id, data);
      } catch (error) {
        limit(state.console, 2000, {
          at: Date.now(),
          level: "harness",
          text: text(error?.message ?? error),
        });
      }
      return callback(data);
    };
    callbacks.set = (id, callback) => set(id, watched(id, callback));
    for (const [id, callback] of [...callbacks.entries()])
      set(id, watched(id, callback));
  };
  const readGetter = () => {
    const shell = window.__CADRUMO_SHELL__;
    const descriptor = shell && Object.getOwnPropertyDescriptor(shell, "token");
    return {
      shellObject: !!shell,
      getter: typeof descriptor?.get === "function",
    };
  };
  wrap();
  state.tokenGetter = readGetter();
  // Module scripts run after the document turns interactive, so this runs
  // after every initialization script and before the shell's own code.
  document.addEventListener("readystatechange", () => {
    if (document.readyState !== "interactive") return;
    wrap();
    state.tokenGetter = readGetter();
  });

  const realFetch = window.fetch.bind(window);
  const prefix = config.ipcPrefix;
  let internal = false;
  const header = (headers, name) => {
    if (!headers) return null;
    if (typeof headers.get === "function") return headers.get(name);
    const key = Object.keys(headers).find(
      (candidate) => candidate.toLowerCase() === name,
    );
    return key ? headers[key] : null;
  };
  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : input?.url;
    if (typeof url !== "string" || !url.startsWith(prefix))
      return realFetch(input, init);
    const by = internal ? "harness" : "shell";
    const entry = {
      seq: (sequence += 1),
      at: Date.now(),
      by,
      cmd: decodeURIComponent(url.slice(prefix.length).split("?")[0]),
      args: null,
      bodyBytes: 0,
      session: null,
      ok: null,
      code: null,
      ms: null,
    };
    limit(ipc, 50000, entry);
    const body = init?.body;
    if (typeof body === "string") {
      entry.bodyBytes = body.length;
      try {
        const parsed = JSON.parse(body);
        if (parsed && typeof parsed === "object") {
          if (typeof parsed.token === "string" && by === "shell") {
            token ??= parsed.token;
            state.tokenSeen = true;
          }
          const args = {};
          for (const [key, value] of Object.entries(parsed))
            if (key !== "token" && key !== "text")
              args[key] = typeof value === "string" ? text(value, 200) : value;
          entry.args = entry.cmd === "sign_in_submit" ? null : args;
          if (typeof args.session === "number") entry.session = args.session;
        }
      } catch {
        entry.args = null;
      }
    } else if (body && typeof body === "object") {
      entry.bodyBytes = body.byteLength ?? body.length ?? 0;
      const presented = header(init?.headers, "x-cadrumo-token");
      if (typeof presented === "string" && by === "shell") {
        token ??= presented;
        state.tokenSeen = true;
      }
      const session = Number(header(init?.headers, "x-cadrumo-session"));
      if (Number.isInteger(session)) entry.session = session;
    }
    if (entry.cmd === "terminal_open" && entry.args) {
      const match = /^__CHANNEL__:(\d+)$/.exec(String(entry.args.frames ?? ""));
      if (match) channelOf(Number(match[1])).kind = entry.args.kind;
      entry.channel = match ? Number(match[1]) : null;
    }
    if (entry.cmd === "terminal_ack" && by === "shell" && held)
      await held.promise;
    if (entry.cmd === "open_external" && by === "shell") {
      state.external.push({ at: Date.now(), url: entry.args?.url ?? null });
      if (state.blockExternal) {
        entry.ok = true;
        entry.code = "intercepted";
        return new Response("null", {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "Tauri-Response": "ok",
          },
        });
      }
    }
    const started = performance.now();
    const response = await realFetch(input, init);
    entry.ms = Math.round(performance.now() - started);
    entry.ok = response.headers.get("Tauri-Response") === "ok";
    const json = (response.headers.get("content-type") || "").startsWith(
      "application/json",
    );
    if (
      json &&
      (!entry.ok ||
        entry.cmd === "terminal_open" ||
        entry.cmd === "sign_in_submit")
    ) {
      try {
        const value = await response.clone().json();
        if (entry.ok && entry.cmd === "terminal_open") {
          entry.session = value?.session ?? null;
          if (entry.channel !== null && entry.channel !== undefined) {
            channelOf(entry.channel).session = entry.session;
            sessions[entry.session] = entry.channel;
          }
        } else if (entry.ok && entry.cmd === "sign_in_submit") {
          entry.answer = {
            kind: text(value?.kind, 40),
            ...(value?.code ? { code: text(value.code, 80) } : {}),
            retryAfterSeconds: value?.retryAfterSeconds ?? null,
          };
        } else entry.code = text(value?.code ?? "unknown", 60);
      } catch {
        entry.code = "unreadable";
      }
    }
    if (
      entry.ok &&
      entry.cmd === "terminal_ack" &&
      by === "shell" &&
      entry.args
    ) {
      const id = sessions[entry.args.session];
      if (id !== undefined)
        channels[id].acked = Math.max(channels[id].acked, entry.args.offset);
    }
    return response;
  };

  /** Invokes a host command as the shell does, with the shell's token. */
  state.call = async (command, args = {}) => {
    if (!token) return { ok: false, error: { code: "no_token" } };
    internal = true;
    let pending;
    try {
      pending = window.__TAURI_INTERNALS__.invoke(command, { ...args, token });
    } finally {
      internal = false;
    }
    try {
      return { ok: true, value: await pending };
    } catch (error) {
      return {
        ok: false,
        error: {
          code: text(error?.code ?? error, 60),
          operation: text(error?.operation ?? "", 40),
        },
      };
    }
  };
  /** Holds the shell's acknowledgements until `release`. */
  state.hold = () => {
    if (held) return;
    let release;
    const promise = new Promise((resolve) => (release = resolve));
    held = { promise, release };
  };
  state.release = () => {
    held?.release();
    held = null;
  };
  state.channelFor = (kind) => {
    const ids = Object.keys(channels)
      .map(Number)
      .filter((id) => channels[id].kind === kind);
    return ids.length ? Math.max(...ids) : null;
  };
}

/** The visible rows of one terminal, as text. */
export function terminalRows(kind) {
  const rows = document.querySelector(`[data-terminal="${kind}"] .xterm-rows`);
  if (!rows) return null;
  return [...rows.children].map((row) => row.textContent ?? "").join("\n");
}

/** The shell's view of one terminal kind's latest channel and session. */
export function terminalState(kind) {
  const state = window.__s10;
  const id = state.channelFor(kind);
  if (id === null) return null;
  const { tail: _tail, ...channel } = state.channels[id];
  return { id, ...channel };
}

/** Pastes `text` into a terminal the way a browser paste reaches xterm. */
export function pasteInto({ kind, text }) {
  const area = document.querySelector(
    `[data-terminal="${kind}"] textarea.xterm-helper-textarea`,
  );
  if (!area) return false;
  area.focus();
  const data = new DataTransfer();
  data.setData("text/plain", text);
  area.dispatchEvent(
    new ClipboardEvent("paste", {
      clipboardData: data,
      bubbles: true,
      cancelable: true,
    }),
  );
  return true;
}

/**
 * One adversarial probe from inside the documentation frame. Each probe
 * reports what the frame could reach and how the attempt settled: a probe
 * that resolves has had something delivered to the frame.
 */
export async function docsProbe({ kind, nonce, ids, timeoutMs, ipcOrigin }) {
  const internals = window.__TAURI_INTERNALS__;
  const surface = {
    internals: typeof internals,
    invoke: typeof internals?.invoke,
    ipcPostMessage: typeof window.ipc?.postMessage,
    webviewPostMessage: typeof window.chrome?.webview?.postMessage,
    shellObject: typeof window.__CADRUMO_SHELL__,
  };
  const describe = (value) => {
    if (value === undefined) return "undefined";
    if (value === null) return "null";
    if (value instanceof ArrayBuffer) return `ArrayBuffer(${value.byteLength})`;
    try {
      return JSON.stringify(value).slice(0, 200);
    } catch {
      return String(value).slice(0, 200);
    }
  };
  const settle = (promise) =>
    Promise.race([
      promise.then(
        (value) => ({ settled: "resolved", value: describe(value) }),
        (error) => ({
          settled: "rejected",
          error: String(error?.code ?? error?.message ?? error).slice(0, 200),
        }),
      ),
      new Promise((resolve) =>
        setTimeout(() => resolve({ settled: "timeout" }), timeoutMs),
      ),
    ]);
  const attempt = (run) => {
    try {
      return settle(Promise.resolve(run()));
    } catch (error) {
      return Promise.resolve({
        settled: "threw",
        error: String(error?.name ?? error).slice(0, 200),
      });
    }
  };
  switch (kind) {
    case "surface":
      return { surface };
    case "invoke":
      return {
        surface,
        outcomes: internals?.invoke
          ? [
              await attempt(() =>
                internals.invoke("shell_clipboard_write", { text: nonce }),
              ),
              await attempt(() => internals.invoke("desktop_environment", {})),
            ]
          : [{ settled: "absent" }],
      };
    case "fetch":
      return {
        surface,
        outcomes: [
          await attempt(() =>
            fetch(`${ipcOrigin}/shell_clipboard_write`, {
              method: "POST",
              body: JSON.stringify({ text: nonce }),
              headers: { "Content-Type": "application/json" },
            }).then((response) => response.text()),
          ),
          await attempt(() =>
            fetch(`${ipcOrigin}/desktop_environment`, {
              method: "POST",
              body: "{}",
              headers: { "Content-Type": "application/json" },
            }).then((response) => response.text()),
          ),
        ],
      };
    case "ipc-post-message":
    case "webview-post-message": {
      const post =
        kind === "ipc-post-message"
          ? window.ipc?.postMessage?.bind(window.ipc)
          : window.chrome?.webview?.postMessage?.bind(window.chrome.webview);
      if (!post) return { surface, outcomes: [{ settled: "absent" }] };
      const message = JSON.stringify({
        cmd: "shell_clipboard_write",
        callback: 1,
        error: 2,
        payload: { text: nonce },
        options: {},
      });
      const outcomes = [];
      for (const value of [message, `${nonce} not an IPC message`])
        outcomes.push(
          await attempt(() => {
            post(value);
            return new Promise((resolve) =>
              setTimeout(() => resolve(undefined), 50),
            ).then(() => {
              throw new Error("posted");
            });
          }),
        );
      return { surface, outcomes };
    }
    case "channel-fetch": {
      if (!internals?.invoke)
        return { surface, outcomes: [{ settled: "absent" }], ids: 0 };
      const outcomes = [];
      for (let start = 0; start < ids; start += 64) {
        const batch = [];
        for (let id = start; id < Math.min(ids, start + 64); id += 1)
          batch.push(
            attempt(() =>
              internals.invoke("plugin:__TAURI_CHANNEL__|fetch", null, {
                headers: { "Tauri-Channel-Id": String(id) },
              }),
            ).then((outcome) => ({ id, ...outcome })),
          );
        outcomes.push(...(await Promise.all(batch)));
      }
      return { surface, outcomes, ids };
    }
    case "token": {
      const reach = (read) => {
        try {
          const value = read();
          return value === undefined ? "undefined" : typeof value;
        } catch (error) {
          return String(error?.name ?? "error");
        }
      };
      return {
        surface,
        // Globals this frame defined, not the browser's own (DOMTokenList).
        names: Object.getOwnPropertyNames(window).filter((name) => {
          if (!/cadrumo|token/i.test(name)) return false;
          const value = Object.getOwnPropertyDescriptor(window, name)?.value;
          return !(
            typeof value === "function" &&
            /\[native code\]/.test(Function.prototype.toString.call(value))
          );
        }),
        topShell: reach(() => window.top.__CADRUMO_SHELL__),
        parentShell: reach(() => window.parent.__CADRUMO_SHELL__),
        topDocument: reach(() => window.top.document),
      };
    }
    default:
      throw new Error(`Unknown probe ${kind}`);
  }
}

/** The page's own search, through the Pagefind bundle beside the document. */
export async function pagefindSearch({ query, bundle }) {
  const started = performance.now();
  const pagefind = await import(new URL(bundle, location.href).href);
  if (typeof pagefind.init === "function") await pagefind.init();
  const search = await pagefind.search(query);
  const first = search?.results?.[0] ? await search.results[0].data() : null;
  return {
    results: search?.results?.length ?? 0,
    firstUrl: first?.url ?? null,
    ms: Math.round(performance.now() - started),
  };
}
