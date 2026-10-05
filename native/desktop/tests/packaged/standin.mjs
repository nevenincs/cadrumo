// Stand-in pages for testing the harness itself in a plain Chromium. They are
// fixtures for the harness's detection logic, not a model of the desktop host:
// a shell origin, a documentation origin and an IPC origin, each a loopback
// HTTP server, with a refusing variant and leaking or violating variants that
// the harness must report as failures.
import { readFileSync } from "node:fs";
import { createServer } from "node:http";

const TOKEN_SCRIPT = readFileSync(
  new URL("../../src-tauri/src/shell/token.js", import.meta.url),
  "utf8",
);

/** Mirrors ShellToken::script: JSON literals replace the two placeholders. */
function tokenScript(origins, token) {
  return TOKEN_SCRIPT.replace(
    "__CADRUMO_SHELL_TOKEN__",
    JSON.stringify(token),
  ).replace("__CADRUMO_SHELL_ORIGINS__", JSON.stringify(origins));
}

/** A Tauri-shaped internals object: callbacks, channels and invoke over fetch. */
const INTERNALS = (ipcOrigin) => `
(() => {
  const callbacks = new Map();
  const uid = () => crypto.getRandomValues(new Uint32Array(1))[0];
  const register = (callback, once) => {
    const id = uid();
    callbacks.set(id, (data) => { if (once) callbacks.delete(id); return callback && callback(data); });
    return id;
  };
  const internals = {
    callbacks,
    transformCallback: register,
    unregisterCallback: (id) => callbacks.delete(id),
    runCallback: (id, data) => {
      const callback = callbacks.get(id);
      if (callback) callback(data);
      else console.warn("[TAURI] Couldn't find callback id " + id);
    },
    invoke(cmd, payload = {}, options) {
      return new Promise((resolve, reject) => {
        const raw = payload instanceof Uint8Array || payload instanceof ArrayBuffer;
        const headers = { ...(options && options.headers), "Content-Type": raw ? "application/octet-stream" : "application/json" };
        fetch(${JSON.stringify(ipcOrigin)} + "/" + encodeURIComponent(cmd), {
          method: "POST",
          body: raw ? payload : JSON.stringify(payload),
          headers,
        }).then((response) =>
          response.json().then((value) =>
            response.headers.get("Tauri-Response") === "ok" ? resolve(value) : reject(value)),
        ).catch(reject);
      });
    },
  };
  Object.defineProperty(window, "__TAURI_INTERNALS__", { value: internals });
})();
`;

/** The stand-in shell application, run as a module like the real shell. */
const SHELL_APP = `
const internals = window.__TAURI_INTERNALS__;
const token = window.__CADRUMO_SHELL__ && window.__CADRUMO_SHELL__.token;
const call = (cmd, args = {}) => internals.invoke(cmd, { ...args, token });
const environment = await call("desktop_environment");
let frames = 0;
const channel = internals.transformCallback(() => { frames += 1; });
const opened = await call("terminal_open", { kind: "python", cols: 80, rows: 24, frames: "__CHANNEL__:" + channel });
window.standin = {
  channel,
  session: opened.session,
  frames: () => frames,
  ack: (offset) => call("terminal_ack", { session: opened.session, offset }),
  openExternal: (url) => call("open_external", { url }),
};
window.addEventListener("keydown", (event) => event.preventDefault());
const frame = document.createElement("iframe");
frame.className = "docs-frame";
frame.src = environment.docs.languages[0].entry;
document.body.append(frame);
`;

function listen(server, host) {
  return new Promise((resolve) =>
    server.listen(0, host, () => resolve(server.address().port)),
  );
}

/**
 * Starts the three origins. `variant` is "refusing", "leaking" or "violating".
 * The returned state records what reached the stand-in IPC origin.
 */
export async function startStandin({ variant = "refusing" } = {}) {
  const token = "0123456789abcdef".repeat(4);
  const state = {
    variant,
    clipboard: "",
    refusals: 0,
    delivered: 0,
    acks: [],
    commands: [],
  };
  const servers = [];
  const shell = createServer();
  const docs = createServer();
  const ipc = createServer();
  servers.push(shell, docs, ipc);
  const shellPort = await listen(shell, "127.0.0.1");
  const docsPort = await listen(docs, "127.0.0.1");
  const ipcPort = await listen(ipc, "127.0.0.1");
  const shellOrigin = `http://127.0.0.1:${shellPort}`;
  const docsOrigin = `http://localhost:${docsPort}`;
  const ipcOrigin = `http://127.0.0.1:${ipcPort}`;
  const tokenOrigins = [shellOrigin];

  const send = (response, status, type, body, headers = {}) => {
    response.writeHead(status, {
      "Content-Type": type,
      "Cache-Control": "no-store",
      ...headers,
    });
    response.end(body);
  };

  shell.on("request", (request, response) => {
    const policy = `default-src 'self'; script-src 'self'; connect-src ${ipcOrigin}; frame-src ${docsOrigin}`;
    const path = new URL(request.url, shellOrigin).pathname;
    if (path === "/index.html")
      return send(
        response,
        200,
        "text/html",
        `<!doctype html><title>Stand-in shell</title><script src="/token.js"></script><script src="/internals.js"></script><script type="module" src="/app.js"></script><body></body>`,
        { "Content-Security-Policy": policy },
      );
    if (path === "/token.js")
      return send(
        response,
        200,
        "text/javascript",
        tokenScript(tokenOrigins, token),
      );
    if (path === "/internals.js")
      return send(response, 200, "text/javascript", INTERNALS(ipcOrigin));
    if (path === "/app.js")
      return send(response, 200, "text/javascript", SHELL_APP);
    if (path === "/nav-204") return send(response, 204, "text/plain", "");
    if (path === "/nav-200")
      return send(
        response,
        200,
        "text/html",
        "<title>replaced</title>replaced",
      );
    return send(response, 404, "text/plain", "");
  });

  docs.on("request", (request, response) => {
    const path = new URL(request.url, docsOrigin).pathname;
    const strict = `default-src 'self'; script-src 'self'; connect-src 'self'; frame-src 'none'; frame-ancestors ${shellOrigin}`;
    const headers =
      variant === "leaking" ? {} : { "Content-Security-Policy": strict };
    if (path === "/index.html" || path === "/other.html") {
      const extra =
        variant === "violating"
          ? `<script>window.inlineRan = true;</script><script src="/fallback.js"></script>`
          : variant === "leaking"
            ? `<script src="/leak.js"></script>`
            : `<script src="/internals.js"></script>`;
      return send(
        response,
        200,
        "text/html",
        `<!doctype html><title>Stand-in docs ${path}</title><script src="/token.js"></script>${extra}<body><h1>Stand-in documentation</h1><p>Body text.</p></body>`,
        headers,
      );
    }
    if (path === "/token.js")
      return send(
        response,
        200,
        "text/javascript",
        tokenScript(tokenOrigins, token),
        headers,
      );
    if (path === "/internals.js")
      return send(
        response,
        200,
        "text/javascript",
        INTERNALS(ipcOrigin),
        headers,
      );
    if (path === "/fallback.js")
      return send(
        response,
        200,
        "text/javascript",
        `console.warn("Pagefind: Worker failed, falling back to main thread");`,
        headers,
      );
    if (path === "/leak.js")
      // A frame that can run commands as the shell: what the barriers prevent.
      return send(
        response,
        200,
        "text/javascript",
        `${INTERNALS(ipcOrigin)}
         const internals = window.__TAURI_INTERNALS__;
         const invoke = internals.invoke.bind(internals);
         Object.defineProperty(internals, "invoke", { value: (cmd, payload = {}, options) => invoke(cmd, { ...(payload || {}), token: ${JSON.stringify(token)} }, options) });
         window.ipc = { postMessage: (text) => { try { const m = JSON.parse(text); internals.invoke(m.cmd, m.payload); } catch {} } };
         window.__CADRUMO_SHELL__ = { token: ${JSON.stringify(token)} };`,
        headers,
      );
    return send(response, 404, "text/plain", "", headers);
  });

  ipc.on("request", (request, response) => {
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "*",
      "Access-Control-Expose-Headers": "Tauri-Response",
    };
    if (request.method === "OPTIONS")
      return send(response, 204, "text/plain", "", cors);
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      const command = decodeURIComponent(
        new URL(request.url, ipcOrigin).pathname.slice(1),
      );
      state.commands.push(command);
      let args = {};
      try {
        args = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}") ?? {};
      } catch {
        args = {};
      }
      const answer = (ok, value) =>
        send(response, 200, "application/json", JSON.stringify(value), {
          ...cors,
          "Tauri-Response": ok ? "ok" : "error",
        });
      const refuse = (code = "invalid_arguments") =>
        answer(false, { code, operation: "webview" });
      if (command === "plugin:__TAURI_CHANNEL__|fetch")
        return variant === "leaking"
          ? answer(true, [0, 1, 2, 3])
          : refuse("not_found");
      if (args.token !== token) {
        state.refusals += 1;
        return refuse();
      }
      switch (command) {
        case "desktop_environment":
          return answer(true, {
            outputLanguage: "en",
            docs: {
              origin: docsOrigin,
              languages: [{ code: "en", entry: `${docsOrigin}/index.html` }],
            },
          });
        case "terminal_open":
          return answer(true, { session: 7 });
        case "terminal_ack":
          state.acks.push(args.offset);
          return args.offset > state.delivered ? refuse() : answer(true, {});
        case "shell_clipboard_write":
          state.clipboard = String(args.text);
          return answer(true, {});
        case "shell_clipboard_read":
          return answer(true, { text: state.clipboard });
        case "diagnostics_snapshot":
          return answer(true, {
            events: Array.from({ length: state.refusals }, () => ({
              kind: "failure",
              failure: { code: "invalid_arguments", operation: "webview" },
            })),
            processes: [],
            output: [],
          });
        case "open_external":
          return answer(true, null);
        default:
          return refuse();
      }
    });
  });

  return {
    state,
    shellOrigin,
    docsOrigin,
    ipcOrigin,
    shellUrl: `${shellOrigin}/index.html`,
    close: () =>
      Promise.all(
        servers.map((server) => new Promise((done) => server.close(done))),
      ),
  };
}
