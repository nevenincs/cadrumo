// Host-call timing shared by the specs: every window call to the host is
// recorded with its command, the definition it carries and when it started and
// answered, so a slow page names the call it waited on.
import { exec } from "./ux-driver.mjs";

/**
 * Wrap the page's fetch, which carries every host call over Tauri's ipc
 * protocol (its invoke is defined read-only), so each call records its
 * command, the definition it carries, and when it started and answered
 * (epoch ms). Answers whether the calls are now timed.
 */
export function pageTimeInvokes() {
  if (window.__uxCalls) return window.fetch === window.__uxFetch;
  const original = window.fetch;
  if (typeof original !== "function") return false;
  const calls = [];
  const wrapped = function (input, init) {
    const url = typeof input === "string" ? input : (input?.url ?? "");
    const ipc = /^ipc:|\/\/ipc\.localhost\//.test(url);
    if (!ipc) return original.call(this, input, init);
    const cmd = decodeURIComponent(url.split("?")[0].split("/").pop() ?? "");
    const body = typeof init?.body === "string" ? init.body : "";
    const definition = /"definition"\s*:\s*"([^"]+)"/.exec(body)?.[1] ?? null;
    const call = { cmd, definition, start: Date.now() };
    calls.push(call);
    const answer = original.call(this, input, init);
    answer.then(
      () => Object.assign(call, { end: Date.now(), ok: true }),
      () => Object.assign(call, { end: Date.now(), ok: false }),
    );
    return answer;
  };
  window.fetch = wrapped;
  window.__uxCalls = calls;
  window.__uxFetch = wrapped;
  return window.fetch === wrapped;
}

/** The calls made since `since` (epoch ms), timed from it. */
export async function callsSince(since) {
  const calls = (await exec(() => window.__uxCalls ?? [])) ?? [];
  return calls
    .filter((call) => call.start >= since)
    .map((call) => ({
      cmd: call.cmd,
      definition: call.definition,
      startMs: Math.round(call.start - since),
      endMs: call.end === undefined ? null : Math.round(call.end - since),
      ok: call.ok ?? null,
    }));
}
