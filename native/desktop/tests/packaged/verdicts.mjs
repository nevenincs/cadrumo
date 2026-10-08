// Decisions for the packaged end-to-end test. Each takes observations and
// returns { verdict, detail }, so the decision can be tested against
// observations that must pass and observations that must fail.

export const PASS = "PASS";
export const FAIL = "FAIL";

const pass = (detail, data) => ({
  verdict: PASS,
  detail,
  ...(data && { data }),
});
const fail = (detail, data) => ({
  verdict: FAIL,
  detail,
  ...(data && { data }),
});

/** The host's credit window and its largest read, from the native contract. */
export const CREDIT_WINDOW = 512 * 1024;
export const READ_CHUNK = 8 * 1024;

const CSP_CONSOLE =
  /content security policy|refused to (load|execute|connect|frame|apply|create|evaluate)/i;
const PAGEFIND_FALLBACK = /falling back to main thread/i;

export function originOf(url) {
  try {
    const parsed = new URL(url);
    return parsed.host ? `${parsed.protocol}//${parsed.host}` : null;
  } catch {
    return null;
  }
}

/** The shell is on a shell origin and the documentation frame on the docs origin. */
export function framesVerdict({
  shellUrl,
  shellOrigins,
  docsUrl,
  docsOrigin,
  docsTitle,
  expectedTitle,
}) {
  const problems = [];
  if (!shellOrigins.includes(originOf(shellUrl)))
    problems.push(`shell is on ${shellUrl}`);
  if (!docsUrl) problems.push("no documentation frame");
  else if (originOf(docsUrl) !== docsOrigin)
    problems.push(`documentation frame is on ${docsUrl}, not ${docsOrigin}`);
  if (expectedTitle !== undefined && docsTitle !== expectedTitle)
    problems.push(
      `documentation title ${JSON.stringify(docsTitle)} is not the index title ${JSON.stringify(expectedTitle)}`,
    );
  return problems.length
    ? fail(problems.join("; "))
    : pass(`shell ${originOf(shellUrl)}, documentation ${docsUrl}`);
}

/** No CSP violation event and no CSP console report in any frame. */
export function cspVerdict(frames, consoleTexts = []) {
  const events = frames.flatMap((frame) =>
    (frame.csp ?? []).map((event) => ({ role: frame.role, ...event })),
  );
  const reports = [
    ...frames.flatMap((frame) =>
      (frame.console ?? [])
        .filter((entry) => CSP_CONSOLE.test(entry.text))
        .map((entry) => `${frame.role}: ${entry.text}`),
    ),
    ...consoleTexts.filter((text) => CSP_CONSOLE.test(text)),
  ];
  if (events.length || reports.length)
    return fail(
      `${events.length} violation event(s), ${reports.length} console report(s)`,
      { events: events.slice(0, 20), reports: reports.slice(0, 20) },
    );
  return pass(
    `no violation in ${frames.map((frame) => frame.role).join(", ") || "no frame"}`,
  );
}

/** A Pagefind query returns results and no frame fell back to the main thread. */
export function pagefindVerdict({ results, pageResults, consoleTexts }) {
  const fallback = consoleTexts.filter((text) => PAGEFIND_FALLBACK.test(text));
  if (fallback.length)
    return fail(`Pagefind fell back to the main thread: ${fallback[0]}`);
  if (!(results > 0))
    return fail(`the Pagefind query returned ${results ?? "no"} results`);
  if (pageResults !== undefined && !(pageResults > 0))
    return fail("the search page listed no results");
  return pass(
    `${results} results through the bundle${pageResults !== undefined ? `, ${pageResults} on the search page` : ""}, no fallback`,
  );
}

/**
 * A docs-frame attempt was refused rather than delivered: nothing resolved in
 * the frame and the command's effect did not happen. `refusals` counts host
 * refusals recorded while the attempt ran; with a surface present and none
 * recorded, the attempt was not delivered at all.
 */
export function refusalVerdict({ outcomes, effect, refusals, surface }) {
  const resolved = outcomes.filter((outcome) => outcome.settled === "resolved");
  if (resolved.length)
    return fail(`delivered to the documentation frame: ${resolved[0].value}`, {
      outcomes,
    });
  if (effect) return fail(`the command ran: ${effect}`, { outcomes });
  const absent = outcomes.every((outcome) => outcome.settled === "absent");
  const mode = absent
    ? "the surface is absent in the frame"
    : refusals > 0
      ? `refused by the host (${refusals} refusal record(s))`
      : `not delivered (${[...new Set(outcomes.map((o) => o.settled))].join(", ")})`;
  return pass(mode, { outcomes, surface });
}

/** Channel fetches from the docs frame returned no frame and took none from the shell. */
export function channelFetchVerdict({ outcomes, gaps, outOfOrder }) {
  const resolved = outcomes.filter((outcome) => outcome.settled === "resolved");
  if (resolved.length)
    return fail(
      `${resolved.length} fetch(es) returned data, first id ${resolved[0].id}: ${resolved[0].value}`,
    );
  if (gaps > 0) return fail(`the shell is missing ${gaps} channel frame(s)`);
  const settled = {};
  for (const outcome of outcomes)
    settled[outcome.settled] = (settled[outcome.settled] ?? 0) + 1;
  return pass(
    `${outcomes.length} fetches, none returned data (${JSON.stringify(settled)}); shell frames complete${outOfOrder ? `, ${outOfOrder} arrived out of order` : ""}`,
  );
}

/** The token reached the shell once and nothing else can read it. */
export function tokenVerdict({ docs, shell }) {
  const problems = [];
  if (docs.surface.shellObject !== "undefined")
    problems.push(
      `docs frame sees __CADRUMO_SHELL__ (${docs.surface.shellObject})`,
    );
  // The docs assets publish translated chrome strings and search controls.
  // These exact public names carry no shell authority; other names still fail.
  const unexpected = docs.names.filter(
    (name) => !["cadrumoChromeStrings", "CadrumoDocs"].includes(name),
  );
  if (unexpected.length)
    problems.push(`docs frame globals: ${unexpected.join(", ")}`);
  for (const [name, reach] of Object.entries({
    "top.__CADRUMO_SHELL__": docs.topShell,
    "parent.__CADRUMO_SHELL__": docs.parentShell,
    "top.document": docs.topDocument,
  }))
    if (reach !== "SecurityError")
      problems.push(`docs frame reading ${name} gave ${reach}`);
  if (!shell.getterAtStart)
    problems.push(
      "the shell document had no token getter before its scripts ran",
    );
  if (shell.getterNow) problems.push("the shell's token getter was never read");
  if (shell.valueNow !== "undefined")
    problems.push(`a second read in the shell gave ${shell.valueNow}`);
  if (!shell.authorized)
    problems.push("the shell made no command call with its token");
  return problems.length
    ? fail(problems.join("; "))
    : pass(
        "read once by the shell; the docs frame has no getter and cannot reach the shell",
      );
}

/** With acknowledgements held, the host stops within one read of the window. */
export function creditVerdict({
  plateau,
  window = CREDIT_WINDOW,
  chunk = READ_CHUNK,
}) {
  if (plateau >= window && plateau < window + chunk)
    return pass(`paused at ${plateau} unacknowledged bytes`);
  if (plateau < window)
    return fail(
      `output stopped at ${plateau} unacknowledged bytes, below the ${window}-byte window`,
    );
  return fail(
    `${plateau} unacknowledged bytes exceeds the window by more than one ${chunk}-byte read`,
  );
}

/**
 * The shell holds every byte the host delivered: the host accepts an
 * acknowledgement of exactly what the shell counted, refuses one byte more,
 * and no channel index is missing.
 */
export function everyByteVerdict({ received, atReceived, pastReceived, gaps }) {
  const problems = [];
  if (!atReceived?.ok)
    problems.push(
      `acknowledging the ${received} received bytes was refused (${atReceived?.error?.code})`,
    );
  if (pastReceived?.ok)
    problems.push(
      `the host delivered more than the ${received} bytes the shell received`,
    );
  else if (pastReceived?.error?.code !== "invalid_arguments")
    problems.push(`one byte past the count gave ${pastReceived?.error?.code}`);
  if (gaps > 0) problems.push(`${gaps} channel frame(s) missing`);
  return problems.length
    ? fail(problems.join("; "))
    : pass(`all ${received} delivered bytes reached the shell`);
}

/**
 * A key or pointer gesture changed nothing: no document reloaded, no frame
 * navigated, no print started, the zoom did not change and no new window opened.
 */
export function noEffectVerdict(before, after) {
  const effects = [];
  for (const role of Object.keys(before.markers))
    if (before.markers[role] !== after.markers[role])
      effects.push(`${role} document replaced`);
  for (const role of Object.keys(before.urls))
    if (before.urls[role] !== after.urls[role])
      effects.push(`${role} navigated to ${after.urls[role]}`);
  if (after.navigations > before.navigations)
    effects.push(`${after.navigations - before.navigations} navigation(s)`);
  if (after.beforeprint > before.beforeprint) effects.push("printing started");
  if (after.zoom !== before.zoom)
    effects.push(`zoom changed from ${before.zoom} to ${after.zoom}`);
  const known = new Set(before.windows.map((window) => window.hwnd));
  const opened = after.windows.filter((window) => !known.has(window.hwnd));
  if (opened.length)
    effects.push(
      `window(s) opened: ${opened.map((window) => `${window.class} "${window.title}" pid ${window.pid}`).join(", ")}`,
    );
  if (after.targets > before.targets)
    effects.push(`${after.targets - before.targets} new DevTools target(s)`);
  return effects.length ? fail(effects.join("; ")) : pass("no effect");
}

/** Closing the window ended the host in time and left no child process. */
export function closeVerdict({ exitCode, exitMs, limitMs = 10000, survivors }) {
  const problems = [];
  if (exitCode === null)
    problems.push(`the host still runs after ${limitMs} ms`);
  else if (exitCode !== 0) problems.push(`the host exited with ${exitCode}`);
  else if (exitMs > limitMs) problems.push(`the host took ${exitMs} ms`);
  if (survivors.length)
    problems.push(
      `surviving: ${survivors.map((process) => `${process.role ?? process.name} ${process.pid}`).join(", ")}`,
    );
  return problems.length
    ? fail(problems.join("; "))
    : pass(`host exited 0 after ${exitMs} ms; no child survived`);
}

/** Text of a terminal contains every expected pattern. */
export function terminalVerdict(rows, patterns, what) {
  if (rows === null) return fail(`${what}: the terminal is not on screen`);
  const missing = patterns.filter((pattern) =>
    pattern instanceof RegExp ? !pattern.test(rows) : !rows.includes(pattern),
  );
  return missing.length
    ? fail(`${what}: missing ${missing.map(String).join(", ")}`, {
        tail: rows.slice(-600),
      })
    : pass(what);
}
