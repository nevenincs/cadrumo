// Provider sign-in in the packaged native window, for Claude and then Codex:
// a failure says its cause in the service's closed words with a log
// reference, Retry starts a fresh attempt, a person can complete the browser
// flow (opt-in), each provider's connections are named hosted or local as the
// window names them, and no test sign-in leaves a key in the credential store.
// One window serves the whole file.
//
// Environment: as ./window-ux-audit.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG,
// CADRUMO_UX_RUN, optional CADRUMO_UX_STAGED_SHA256), plus
//   CADRUMO_SIGN_IN_INTERACTIVE  1: a person completes each provider's browser
//                    flow when asked; otherwise the success case is skipped
//                    with its reason, never faked
//   CADRUMO_SIGN_IN_PROVIDERS  (optional) comma-separated provider ids, in
//                    order; default claude,codex
//   CADRUMO_SIGN_IN_PERSON_MS  (optional) how long a person has to finish the
//                    browser flow; default 330000
//
// How a failure is made without a person: the window's start is refused with
// the service's in-flight cause when a second attempt starts while the first
// is still held. The spec opens the sign-in, closes the dialog at once (which
// cancels its attempt only once that attempt's start answers) and opens it
// again: the service still holds the first attempt and refuses the second
// with a cause and a log reference. A person's own Cancel is not used for
// this: the service serves a cancelled attempt without a cause or a reference.
//
// Every attempt the spec starts while no person is asked to finish it is
// cancelled from the dialog, and the run signs out of the profile at the end.
// Credential-store targets are only counted; no target name or secret is
// printed.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import {
  clickSelector,
  exec,
  label,
  runIdentity,
  sleep,
  start,
  teardown,
  waitFor,
  win,
} from "./ux-driver.mjs";
import { callsSince, pageTimeInvokes } from "./ux-calls.mjs";
import { dismissSetup } from "./ux-nav.mjs";

const PROVIDERS = (process.env.CADRUMO_SIGN_IN_PROVIDERS ?? "claude,codex")
  .split(",")
  .map((item) => item.trim())
  .filter(Boolean);
const INTERACTIVE = process.env.CADRUMO_SIGN_IN_INTERACTIVE === "1";
const PERSON_MS = Number(process.env.CADRUMO_SIGN_IN_PERSON_MS ?? 330_000);
const STAGED_SHA256 = (process.env.CADRUMO_UX_STAGED_SHA256 ?? "")
  .trim()
  .toLowerCase();

// ---------------------------------------------------------------------------
// The closed words: read from the generated contract and from the dialog's
// own source, never restated here.
// ---------------------------------------------------------------------------

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

/** The members of `export const NAME = [ ... ] as const;` in the contract. */
function contractList(text, name) {
  const match = new RegExp(
    `export const ${name} = \\[([\\s\\S]*?)\\] as const;`,
  ).exec(text);
  if (!match) throw new Error(`providerSignInContract.ts declares no ${name}`);
  return [...match[1].matchAll(/"([a-z0-9_]+)"/g)].map((item) => item[1]);
}

const CONTRACT = source("../../frontend/src/shell/providerSignInContract.ts");
const SIGN_IN_CAUSES = contractList(CONTRACT, "SIGN_IN_CAUSES");
const CLI_STATE_CAUSES = contractList(CONTRACT, "CLI_STATE_CAUSES");
const NEXT_STEPS = contractList(CONTRACT, "NEXT_STEPS");
const CAUSE_KEY = (cause) => `desktop.providers.sign_in_cause.${cause}`;
const STEP_KEY = (step) => `desktop.providers.next_step.${step}`;

/** Every chrome-string key the sign-in dialog can say, from its source. */
const DIALOG_KEYS = [
  ...new Set(
    [
      ...source(
        "../../frontend/src/components/settings/ProviderSignInDialog.tsx",
      ).matchAll(/"(desktop\.providers\.[a-z0-9_.]+)"/g),
    ].map((item) => item[1]),
  ),
];
// The service names a failure's log line by a whole UUID (sign_in_refusal.py).
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** A served template as a whole-text pattern, each `{slot}` matching words. */
const templatePattern = (template) =>
  new RegExp(
    `^${template
      .split(/\{\w+\}/)
      .map((part) =>
        part
          .replace(/\s+/g, " ")
          .trim()
          .replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
      )
      .join(".+?")}$`,
  );

const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();

/** The catalogue word a shown sentence is, or null: {code, key}. */
function wordOf(text, codes, keyOf) {
  for (const code of codes) {
    const key = keyOf(code);
    const said = label(key);
    if (said !== key && norm(said) === norm(text)) return { code, key };
  }
  return null;
}

/** The dialog key whose template the shown sentence is, or null. */
function dialogKeyOf(text) {
  for (const key of DIALOG_KEYS) {
    const said = label(key);
    if (said !== key && templatePattern(said).test(norm(text))) return key;
  }
  return null;
}

// ---------------------------------------------------------------------------
// The credential store: targets counted by class, never printed.
// ---------------------------------------------------------------------------

const SESSION_SUFFIX = "@cadrumo:profile-session:v2";

/** Counts of the credential-store targets by class; null off Windows. */
function credentialCounts() {
  if (process.platform !== "win32") return null;
  const listed = spawnSync("cmdkey", ["/list"], { encoding: "utf8" });
  if (listed.status !== 0)
    throw new Error(`cmdkey /list failed with status ${listed.status}`);
  const counts = { profileSession: 0, cadrumo: 0, provider: 0, total: 0 };
  for (const line of listed.stdout.split(/\r?\n/)) {
    const match = /Target:\s*(\S+)/.exec(line);
    if (!match) continue;
    const target = match[1];
    counts.total += 1;
    if (target.endsWith(SESSION_SUFFIX)) counts.profileSession += 1;
    if (/cadrumo/i.test(target)) counts.cadrumo += 1;
    if (/claude|anthropic|codex|openai/i.test(target)) counts.provider += 1;
  }
  return counts;
}

// ---------------------------------------------------------------------------
// Log lines: whether a served reference appears in a log under the run.
// ---------------------------------------------------------------------------

/** "yes", "no" or "unsearched": the reference in a log file under the run. */
function logLineFound(dir, reference) {
  if (!dir || !reference) return "unsearched";
  let files = 0;
  const walk = (path, depth) => {
    if (depth > 10 || files > 4000) return false;
    let entries;
    try {
      entries = readdirSync(path, { withFileTypes: true });
    } catch {
      return false;
    }
    for (const entry of entries) {
      const full = join(path, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        if (walk(full, depth + 1)) return true;
        continue;
      }
      if (!/\.(log|jsonl|txt)$/i.test(entry.name)) continue;
      files += 1;
      try {
        if (statSync(full).size > 32 * 1024 * 1024) continue;
        if (readFileSync(full, "utf8").includes(reference)) return true;
      } catch {
        // An unreadable file is not evidence either way.
      }
    }
    return false;
  };
  return walk(dir, 0) ? "yes" : "no";
}

// ---------------------------------------------------------------------------
// Page-side readers (serialised into the window: arguments and document only)
// ---------------------------------------------------------------------------

/** The shown provider sign-in dialog as words; never a code a person types. */
function pageDialog() {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const shown = (el) => !!el && el.getClientRects().length > 0;
  const dialog = [
    ...document.querySelectorAll('[data-slot="dialog-content"]'),
  ].find(shown);
  if (!dialog) return { open: false };
  const description = dialog.querySelector('[data-slot="dialog-description"]');
  const advice = dialog.querySelector('[data-slot="sign-in-advice"]');
  const reference = dialog.querySelector('[data-slot="sign-in-log-ref"] code');
  const attempt = dialog.querySelector('[data-slot="sign-in-attempt"]');
  return {
    open: true,
    // Shown only once the service has answered the start with an attempt.
    attemptId: attempt?.getAttribute("data-attempt-id") || null,
    title: norm(
      dialog.querySelector('[data-slot="dialog-title"]')?.textContent,
    ),
    description: norm(description?.textContent),
    describing: description?.getAttribute("role") ?? null,
    alerts: [...dialog.querySelectorAll('[role="alert"]')]
      .filter(shown)
      .map((el) => norm(el.textContent)),
    statuses: [...dialog.querySelectorAll('p[role="status"]')]
      .filter(shown)
      .map((el) => norm(el.textContent)),
    // Each sentence of the advice; a console command line is not one.
    advice: advice
      ? [...advice.children]
          .filter((el) => el.tagName === "P" && !el.querySelector("code"))
          .map((el) => norm(el.textContent))
      : [],
    logRef: reference ? norm(reference.textContent) : null,
    buttons: [...dialog.querySelectorAll('[data-slot="dialog-footer"] button')]
      .filter(shown)
      .map((el) => ({
        text: norm(el.textContent),
        disabled: el.disabled || el.getAttribute("aria-disabled") === "true",
      })),
  };
}

/** One provider's group in the agent settings, opened, and its lanes. */
function pageProviderGroup(provider, words) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const group = document.querySelector(
    `.provider-settings li[data-provider="${provider}"]`,
  );
  if (!group) return { found: false };
  const details = group.querySelector(":scope > details");
  if (details && !details.open) details.open = true;
  return {
    found: true,
    name: norm(group.querySelector("summary h4")?.textContent),
    lanes: [...group.querySelectorAll("li[data-lane]")].map((lane) => {
      const buttons = [...lane.querySelectorAll("button")].filter(
        (el) => el.getClientRects().length > 0,
      );
      const swatch = lane.querySelector('[role="switch"]');
      return {
        id: lane.getAttribute("data-lane"),
        hidden: lane.hidden,
        connection: norm(lane.querySelector("h5")?.textContent),
        status:
          lane
            .querySelector('[data-slot="provider-status"]')
            ?.getAttribute("data-status") ?? null,
        on: swatch ? swatch.getAttribute("aria-checked") === "true" : null,
        // pending while the service's sign-in reads are out; offered or
        // unavailable once they settle.
        signInState: lane.getAttribute("data-sign-in"),
        signIn: buttons.some((el) => norm(el.textContent) === words.signIn),
        unavailable: [...lane.querySelectorAll('p[role="note"]')].some(
          (el) => norm(el.textContent).length > 0,
        ),
        advice: [
          ...lane.querySelectorAll('[data-slot="sign-in-advice"] > p'),
        ].map((el) => norm(el.textContent)),
      };
    }),
  };
}

/** Mark the first shown element under `scope` matching `item` whose text is
 * `text` as the click target; answers whether one was marked. */
function pageMark(scope, item, text) {
  const norm = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  for (const old of document.querySelectorAll("[data-psi-target]"))
    old.removeAttribute("data-psi-target");
  for (const root of document.querySelectorAll(scope)) {
    for (const el of root.querySelectorAll(item)) {
      if (!el.getClientRects().length) continue;
      if (text !== null && norm(el.textContent) !== text) continue;
      el.setAttribute("data-psi-target", "1");
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Window steps
// ---------------------------------------------------------------------------

const TARGET = "[data-psi-target]";

async function press(scope, item, text) {
  if (!(await exec(pageMark, scope, item, text))) return false;
  await clickSelector(TARGET);
  return true;
}

/** Show the agent column's settings with the provider settings drawn. */
async function openAgentSettings() {
  await dismissSetup();
  const drawn = () =>
    exec(() =>
      [...document.querySelectorAll(".provider-settings")].some(
        (el) => el.getClientRects().length > 0,
      ),
    );
  if (await drawn())
    return { reached: true, rounds: [], column: null, calls: [] };
  // Every host call from here is timed, so a slow first draw names the read it
  // waited on (the panel draws only after its settings and access reads answer).
  const timed = await exec(pageTimeInvokes);
  const since = Date.now();
  await exec(pageMarkDrawn, since);
  const agentShown = await exec(
    () =>
      document
        .querySelector('[data-rail="agent"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  if (!agentShown) {
    await clickSelector('[data-rail="agent"]');
    await sleep(1200);
  }
  const name = label("desktop.agent.settings");
  // The first press can land before the agent column has drawn its settings
  // door, and a door already pressed may show nothing yet: press again.
  // Each round is kept, so a slow first draw names the round it waited in.
  const began = Date.now();
  const rounds = [];
  let last = { reached: false, reason: "the provider settings were not drawn" };
  for (let round = 0; round < 3 && !last.reached; round += 1) {
    last = await pressAgentSettings(name, drawn, round > 0);
    rounds.push({
      door: last.door,
      drawn: last.reached,
      at_ms: Date.now() - began,
    });
  }
  const column = last.reached ? null : await exec(agentColumnText, name);
  // The draw marker polls every 100 ms, so it can trail the check that saw the
  // providers drawn; wait for it as well, or a late draw reads as unmeasured.
  // The access section draws on its own read, possibly after the providers.
  if (last.reached)
    await waitFor(
      () =>
        exec(
          () =>
            window.__uxDrawn?.providers != null &&
            window.__uxDrawn?.access != null,
        ),
      {
        timeout: 30_000,
        what: "the drawn marks of the providers and the agent access section",
        soft: true,
      },
    );
  const calls = timed ? await callsSince(since) : null;
  const drawnMs = await exec(() => window.__uxDrawn ?? null);
  const opened = { ...last, rounds, column, calls, drawnMs };
  coldOpen ??= opened;
  return opened;
}

// The first measured open of the provider settings in this window: the cold
// draw, while the agent service may still be starting.
let coldOpen = null;
// The first draw bound, for a cold open (G4).
const COLD_DRAW_MS = 4000;

/** Close the agent column's settings, so the next open is drawn afresh. */
async function closeAgentSettings() {
  const name = label("desktop.agent.settings");
  const pressed = await exec((name) => {
    for (const old of document.querySelectorAll("[data-psi-target]"))
      old.removeAttribute("data-psi-target");
    const button = [
      ...document.querySelectorAll('button[data-slot="icon-button"]'),
    ].find(
      (el) =>
        el.getClientRects().length > 0 &&
        (el.getAttribute("aria-label") ?? "").startsWith(name),
    );
    if (button?.getAttribute("aria-pressed") !== "true") return false;
    button.setAttribute("data-psi-target", "1");
    return true;
  }, name);
  if (pressed) await clickSelector(TARGET);
  return waitFor(
    () =>
      exec(
        () =>
          ![...document.querySelectorAll(".provider-settings")].some(
            (el) => el.getClientRects().length > 0,
          ),
      ),
    { timeout: 10_000, what: "the provider settings to close", soft: true },
  );
}

/** Record, from `since` (epoch ms), when each agent settings section is first
 * drawn with its read's answer, on the same clock as the timed host calls. */
function pageMarkDrawn(since) {
  const marks = { providers: null, access: null };
  window.__uxDrawn = marks;
  const seen = (selector) =>
    [...document.querySelectorAll(selector)].some(
      (el) => el.getClientRects().length > 0,
    );
  const look = () => {
    if (marks.providers === null && seen(".provider-settings"))
      marks.providers = Date.now() - since;
    if (marks.access === null && seen(".agent-access"))
      marks.access = Date.now() - since;
    if (marks.providers === null || marks.access === null)
      setTimeout(look, 100);
  };
  look();
  return true;
}

/** The visible words around the agent column's settings door, so a run that
 * never drew the provider settings shows what the column offered instead. */
function agentColumnText(name) {
  const door = [
    ...document.querySelectorAll('button[data-slot="icon-button"]'),
  ].find((el) => (el.getAttribute("aria-label") ?? "").startsWith(name));
  const column = door?.closest(
    "aside, section, [data-rail-panel], [role='complementary']",
  );
  return (
    (column?.innerText ?? "").replace(/\s+/g, " ").trim().slice(0, 400) || null
  );
}

async function pressAgentSettings(name, drawn, again) {
  const marked = await exec((name) => {
    for (const old of document.querySelectorAll("[data-psi-target]"))
      old.removeAttribute("data-psi-target");
    const button = [
      ...document.querySelectorAll('button[data-slot="icon-button"]'),
    ].find(
      (el) =>
        el.getClientRects().length > 0 &&
        (el.getAttribute("aria-label") ?? "").startsWith(name),
    );
    if (!button) return "absent";
    if (button.getAttribute("aria-disabled") === "true") return "held";
    button.setAttribute("data-psi-target", "1");
    return button.getAttribute("aria-pressed") === "true" ? "open" : "marked";
  }, name);
  if (marked === "absent" || marked === "held") {
    await sleep(5000);
    return {
      reached: false,
      door: marked,
      reason: `the agent column's "${name}" button is ${marked}`,
    };
  }
  if (marked === "open" && again) {
    await clickSelector(TARGET);
    await sleep(800);
    await clickSelector(TARGET);
  } else if (marked === "marked") await clickSelector(TARGET);
  const ok = await waitFor(drawn, {
    timeout: 20_000,
    what: "the provider settings",
    soft: true,
  });
  return ok
    ? { reached: true, door: marked }
    : {
        reached: false,
        door: marked,
        reason: "the provider settings were not drawn",
      };
}

const signInWords = () => label("desktop.providers.sign_in_action");

async function readGroup(provider) {
  return exec(pageProviderGroup, provider, { signIn: signInWords() });
}

/** The lane of `provider` that offers the window's sign-in, turned on if it
 * is off. Answers { lane } or { reason }. */
async function signInLane(provider) {
  const opened = await openAgentSettings();
  if (!opened.reached) return { reason: opened.reason };
  let group = await waitFor(
    async () => {
      const read = await readGroup(provider);
      return read.found ? read : null;
    },
    { timeout: 30_000, what: `provider group ${provider}`, soft: true },
  );
  if (!group)
    return { reason: `the provider settings list no provider "${provider}"` };
  // The window draws a lane before the service has said how it signs in: judge
  // the lanes only once one offers sign-in or every lane that is on has settled.
  const settled = (read) =>
    read.lanes.some((item) => item.signIn) ||
    read.lanes
      .filter((item) => item.on !== false)
      .every((item) => ["offered", "unavailable"].includes(item.signInState));
  group =
    (await waitFor(
      async () => {
        const read = await readGroup(provider);
        return read.found && settled(read) ? read : null;
      },
      {
        timeout: 60_000,
        what: `the sign-in reads of ${provider}`,
        soft: true,
      },
    )) ?? (await readGroup(provider));
  let lane = group.lanes.find((item) => item.signIn);
  if (!lane) {
    // A sign-in lane that is off offers no sign-in: turn it on, as a person
    // would, in this run's own copy of the profile.
    const off = group.lanes.find((item) => item.on === false);
    if (off) {
      await press(`li[data-lane="${off.id}"]`, '[role="switch"]', null);
      group = await waitFor(
        async () => {
          const read = await readGroup(provider);
          return read.lanes.some((item) => item.signIn) ? read : null;
        },
        { timeout: 30_000, what: `the sign-in of ${provider}`, soft: true },
      );
      lane = group?.lanes.find((item) => item.signIn);
    }
  }
  if (!lane)
    return {
      reason:
        `no lane of "${provider}" offers "${signInWords()}" ` +
        `(lanes: ${JSON.stringify(group.lanes.map(({ id, status, on, signInState, unavailable }) => ({ id, status, on, signInState, unavailable })))})`,
    };
  return { lane };
}

async function pressSignIn(laneId) {
  return press(`li[data-lane="${laneId}"]`, "button", signInWords());
}

/** Close the shown dialog by its corner button (closing cancels a live
 * attempt). */
async function closeDialog() {
  return exec((name) => {
    const button = [
      ...document.querySelectorAll(
        '[data-slot="dialog-content"] [data-slot="icon-button"]',
      ),
    ].find(
      (el) =>
        el.getClientRects().length > 0 &&
        el.getAttribute("aria-label") === name,
    );
    if (!button) return false;
    button.click();
    return true;
  }, label("desktop.providers.sign_in_close"));
}

const ACTIVE_KEYS = [
  "desktop.providers.sign_in_starting",
  "desktop.providers.sign_in_waiting",
  "desktop.providers.sign_in_waiting_device",
  "desktop.providers.sign_in_code_prompt",
  "desktop.providers.sign_in_code_checking",
];
const isActive = (dialog) =>
  dialog.open &&
  dialog.describing === "status" &&
  dialog.alerts.length === 0 &&
  ACTIVE_KEYS.some((key) => norm(label(key)) === dialog.description);
const isSettled = (dialog) =>
  dialog.open &&
  dialog.buttons.some(
    (button) => button.text === norm(label("desktop.providers.sign_in_close")),
  );

const answeredStart = (dialog) => !!dialog.attemptId || isSettled(dialog);

/** Cancel a live attempt from the dialog, then close it; answers how. */
async function cancelAndClose() {
  let dialog = await exec(pageDialog);
  if (!dialog.open) return "closed";
  let how = "closed";
  const cancel = norm(label("desktop.providers.sign_in_cancel"));
  if (dialog.buttons.some((button) => button.text === cancel)) {
    // A cancel before the start is answered leaves the start in flight, and a
    // later sign-out then refuses it.
    const answered = await waitFor(
      async () => {
        const now = await exec(pageDialog);
        return !now.open || now.attemptId || isSettled(now) ? now : null;
      },
      { timeout: 60_000, what: "the start to be answered", soft: true },
    );
    dialog = answered ?? (await exec(pageDialog));
  }
  if (dialog.open && dialog.buttons.some((button) => button.text === cancel)) {
    await press('[data-slot="dialog-footer"]', "button", cancel);
    how = answeredStart(dialog) ? "cancelled" : "start-unanswered";
    dialog = await waitFor(
      async () => {
        const now = await exec(pageDialog);
        return !now.open || isSettled(now) ? now : null;
      },
      { timeout: 60_000, what: "the cancelled attempt to settle", soft: true },
    );
    if (!dialog) how = "cancel-unsettled";
  }
  await closeDialog();
  const gone = await waitFor(async () => !(await exec(pageDialog)).open, {
    timeout: 15_000,
    what: "the dialog to close",
    soft: true,
  });
  if (!gone) throw new Error("the sign-in dialog did not close");
  return how;
}

/** What a failure in the dialog says, judged against the closed words. */
function judgeFailure(dialog) {
  const causes = [];
  const steps = [];
  const foreign = [];
  for (const sentence of dialog.advice) {
    const cause =
      wordOf(sentence, SIGN_IN_CAUSES, CAUSE_KEY) ??
      wordOf(sentence, CLI_STATE_CAUSES, CAUSE_KEY);
    const step = cause ? null : wordOf(sentence, NEXT_STEPS, STEP_KEY);
    if (cause) causes.push(cause.code);
    else if (step) steps.push(step.code);
    else foreign.push(sentence);
  }
  const alertKeys = dialog.alerts.map(dialogKeyOf);
  return {
    causes,
    steps,
    foreign,
    alertKeys,
    logRef: dialog.logRef,
    logRefUuid: !!dialog.logRef && UUID.test(dialog.logRef),
  };
}

// ---------------------------------------------------------------------------
// The run
// ---------------------------------------------------------------------------

let runDir;
let credentialsBefore = null;
let credentialError = null;
const state = new Map();
const stateOf = (provider) => {
  if (!state.has(provider)) state.set(provider, {});
  return state.get(provider);
};

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-sign-in-")), "run");
  try {
    credentialsBefore = credentialCounts();
  } catch (error) {
    credentialError = error.message;
  }
  await start(runDir);
});
after(teardown);

/** One structured line per case. */
function record(t, line) {
  t.diagnostic(JSON.stringify({ probe: "provider-sign-in", ...line }));
}

/** A case: its line is written whatever the outcome. */
const signInCase = (name, provider, kind, fn) =>
  test(name, { timeout: Math.max(PERSON_MS, 300_000) + 120_000 }, async (t) => {
    const line = {
      provider,
      case: kind,
      verdict: "fail",
      cause: null,
      log_ref_present: "no",
      durations_ms: {},
    };
    const began = Date.now();
    try {
      const verdict = await fn(t, line);
      line.verdict = verdict ?? "pass";
    } catch (error) {
      line.reason = error instanceof Error ? error.message : String(error);
      throw error;
    } finally {
      line.durations_ms.total = Date.now() - began;
      record(t, line);
    }
  });

test("PSI-00 the run records the live bundle and the host executable", (t) => {
  record(t, {
    case: "run-identity",
    bundle: runIdentity.bundle,
    exe: runIdentity.exe,
    exeSha256: runIdentity.exeSha256,
    interactive: INTERACTIVE,
    providers: PROVIDERS,
  });
  assert.equal(runIdentity.error, null, `run identity: ${runIdentity.error}`);
  if (STAGED_SHA256)
    assert.equal(
      runIdentity.exeSha256?.toLowerCase(),
      STAGED_SHA256,
      "the window ran another executable than the freshly staged host",
    );
});

for (const provider of PROVIDERS) {
  signInCase(
    `PSI ${provider} model notice: each connection is named hosted or local`,
    provider,
    "model-notice",
    async (t, line) => {
      const opened = await openAgentSettings();
      line.settings_rounds = opened.rounds;
      line.settings_calls = opened.calls;
      line.settings_drawn_ms = opened.drawnMs;
      if (!opened.reached) {
        line.agent_column = opened.column;
        assert.fail(`UNMEASURED: ${opened.reason}`);
      }
      const group = await waitFor(
        async () => {
          const read = await readGroup(provider);
          return read.found && read.lanes.length > 0 ? read : null;
        },
        { timeout: 30_000, what: `provider group ${provider}`, soft: true },
      );
      if (!group)
        assert.fail(`UNMEASURED: the provider settings list no "${provider}"`);
      // A run that names a directory keeps what the person saw: the agent
      // column with its provider settings drawn, from the synthetic world.
      const shots = process.env.CADRUMO_UX_SCREENSHOT_DIR;
      if (shots) {
        line.screenshot = join(shots, `provider-settings-${provider}.png`);
        await win.browser.saveScreenshot(line.screenshot);
      }
      const PLACES = {
        "desktop.providers.connection_api": "hosted",
        "desktop.providers.connection_app": "hosted",
        "desktop.providers.connection_local": "local",
      };
      const lanes = group.lanes.map((lane) => {
        const key = Object.keys(PLACES).find(
          (item) => norm(label(item)) === lane.connection,
        );
        return {
          id: lane.id,
          words_from_catalogue: !!key,
          place: key ? PLACES[key] : null,
          status: lane.status,
        };
      });
      line.lanes = lanes;
      line.name = group.name;
      const unnamed = lanes.filter((lane) => !lane.words_from_catalogue);
      assert.deepEqual(
        unnamed.map((lane) => lane.id),
        [],
        `connections of ${provider} named outside the catalogue's connection words`,
      );
      // Claude and Codex run on their providers' servers: the window must not
      // call any of their connections local.
      const local = lanes.filter((lane) => lane.place === "local");
      assert.deepEqual(
        local.map((lane) => lane.id),
        [],
        `${provider} connections the window calls local`,
      );
    },
  );

  signInCase(
    `PSI ${provider} failure shows its cause words and a log reference`,
    provider,
    "failure",
    async (t, line) => {
      const found = await signInLane(provider);
      if (!found.lane) assert.fail(`UNMEASURED: ${found.reason}`);
      const laneId = found.lane.id;
      line.lane = laneId;
      let failure = null;
      for (let tries = 1; tries <= 4 && !failure; tries += 1) {
        line.tries = tries;
        const began = Date.now();
        // The first attempt: opened, then its dialog closed at once, so its
        // cancel waits on its own start answer and the service still holds it.
        assert(await pressSignIn(laneId), "the sign-in could not be pressed");
        await waitFor(async () => (await exec(pageDialog)).open, {
          timeout: 15_000,
          what: "the sign-in dialog",
        });
        await closeDialog();
        await waitFor(async () => !(await exec(pageDialog)).open, {
          timeout: 15_000,
          what: "the first dialog to close",
        });
        // The second attempt, while the first is held.
        assert(
          await pressSignIn(laneId),
          "the sign-in could not be pressed again",
        );
        const answer = await waitFor(
          async () => {
            const now = await exec(pageDialog);
            if (!now.open) return null;
            if (now.alerts.length > 0 && isSettled(now)) return now;
            if (
              isActive(now) &&
              now.description !== norm(label(ACTIVE_KEYS[0]))
            )
              return now;
            return null;
          },
          { timeout: 45_000, what: "the second attempt's answer", soft: true },
        );
        line.durations_ms[`try${tries}_to_answer`] = Date.now() - began;
        if (answer?.alerts.length > 0) {
          failure = answer;
          break;
        }
        // Not refused (the first attempt was already gone): cancel and again.
        line[`try${tries}`] = answer ? "not-refused" : "no-answer";
        await cancelAndClose();
        await sleep(3000);
      }
      if (!failure)
        assert.fail(
          "UNMEASURED: no attempt was refused while another was held, so no failure was shown",
        );
      const judged = judgeFailure(failure);
      line.cause = judged.causes.join(",") || null;
      line.next_step = judged.steps.join(",") || null;
      line.alert_keys = judged.alertKeys;
      line.log_ref_present = judged.logRef ? "yes" : "no";
      line.log_ref_uuid = judged.logRefUuid;
      line.log_line_found = logLineFound(runDir, judged.logRef);
      stateOf(provider).failure = {
        logRef: judged.logRef,
        laneId,
        attemptId: failure.attemptId,
      };
      assert.deepEqual(
        judged.foreign,
        [],
        "advice sentences that are not the contract's cause or next-step words",
      );
      assert(
        judged.alertKeys.every(Boolean),
        `an alert the dialog's own strings do not say: ${JSON.stringify(failure.alerts)}`,
      );
      assert(
        judged.causes.length > 0,
        "the failure says no cause in the contract's words (no sign-in-advice cause sentence)",
      );
      assert(judged.logRef, "the failure shows no log reference");
      assert(
        judged.logRefUuid,
        "the log reference is not the service's whole-UUID reference",
      );
    },
  );

  signInCase(
    `PSI ${provider} retry starts a fresh attempt`,
    provider,
    "retry",
    async (t, line) => {
      const earlier = stateOf(provider).failure;
      const dialog = await exec(pageDialog);
      if (!earlier || !dialog.open || dialog.alerts.length === 0)
        assert.fail(
          "UNMEASURED: the failure case left no failed attempt in the dialog to retry",
        );
      const retry = norm(label("desktop.providers.sign_in_retry"));
      const seenRefs = new Set([earlier.logRef]);
      const failedId = earlier.attemptId ?? null;
      let fresh = null;
      for (let tries = 1; tries <= 6 && !fresh; tries += 1) {
        line.tries = tries;
        const offered = await waitFor(
          async () =>
            (await exec(pageDialog)).buttons.some(
              (button) => button.text === retry && !button.disabled,
            ),
          { timeout: 60_000, what: "the Retry button", soft: true },
        );
        if (!offered)
          assert.fail(
            `the failed attempt offers no "${retry}" (retry refresh: ${JSON.stringify((await exec(pageDialog)).statuses)})`,
          );
        const began = Date.now();
        await press('[data-slot="dialog-footer"]', "button", retry);
        const answer = await waitFor(
          async () => {
            const now = await exec(pageDialog);
            // Stale dialog state is not a retry: the fresh attempt carries an id
            // the failed one did not.
            if (isActive(now) && now.attemptId && now.attemptId !== failedId)
              return { active: true, now };
            if (
              now.alerts.length > 0 &&
              isSettled(now) &&
              now.logRef &&
              !seenRefs.has(now.logRef)
            )
              return { active: false, now };
            return null;
          },
          { timeout: 120_000, what: "the retried attempt", soft: true },
        );
        line.durations_ms[`try${tries}_to_fresh`] = Date.now() - began;
        if (!answer) continue;
        if (answer.active) {
          fresh = "active";
          break;
        }
        // A new refusal names a new log line: a fresh request, refused.
        const judged = judgeFailure(answer.now);
        seenRefs.add(judged.logRef);
        line.cause = judged.causes.join(",") || null;
        line.log_ref_present = judged.logRef ? "yes" : "no";
        // Still held by the first attempt: wait for it to go and retry.
        if (
          judged.causes.some((cause) => /in_progress|owner_held/.test(cause))
        ) {
          await sleep(5000);
          continue;
        }
        fresh = "refused-fresh";
      }
      line.fresh = fresh;
      line.distinct_log_refs = seenRefs.size;
      const how = await cancelAndClose();
      line.teardown = how;
      assert(
        fresh,
        "Retry started no fresh attempt: the dialog never showed an attempt in progress or a new refusal",
      );
      return fresh === "active" ? "pass" : "pass-refused-fresh";
    },
  );

  signInCase(
    `PSI ${provider} success when a person completes the browser flow`,
    provider,
    "success",
    async (t, line) => {
      if (!INTERACTIVE) {
        line.reason =
          "CADRUMO_SIGN_IN_INTERACTIVE is not 1: no person completes the browser flow";
        t.skip(line.reason);
        return "skipped";
      }
      const found = await signInLane(provider);
      if (!found.lane) assert.fail(`UNMEASURED: ${found.reason}`);
      line.lane = found.lane.id;
      const began = Date.now();
      assert(
        await pressSignIn(found.lane.id),
        "the sign-in could not be pressed",
      );
      record(t, {
        provider,
        case: "success",
        ask: `complete the ${provider} sign-in in the browser the window opened, within ${Math.round(PERSON_MS / 1000)} s`,
      });
      const outcome = await waitFor(
        async () => {
          const now = await exec(pageDialog);
          if (now.open && now.alerts.length > 0 && isSettled(now))
            return { ok: false, now };
          if (now.open) return null;
          const group = await readGroup(provider);
          const lane = group.lanes?.find((item) => item.id === found.lane.id);
          return lane?.status === "ready" ? { ok: true, lane } : { ok: null };
        },
        { timeout: PERSON_MS, what: "the person's sign-in", soft: true },
      );
      line.durations_ms.to_outcome = Date.now() - began;
      if (!outcome || outcome.ok !== true) {
        if (outcome?.now) {
          const judged = judgeFailure(outcome.now);
          line.cause = judged.causes.join(",") || null;
          line.log_ref_present = judged.logRef ? "yes" : "no";
        }
        line.teardown = await cancelAndClose();
        assert.fail(
          outcome?.ok === false
            ? "the sign-in failed"
            : outcome?.ok === null
              ? "the dialog closed but the lane does not read as ready"
              : "no outcome before the person's time ran out",
        );
      }
      // The window offers no provider sign-out for an app connection; the
      // credential the app stored lives under this run's copy of the profile.
      line.teardown = "no-window-sign-out";
    },
  );
}

test("PSI-98 provider settings draw: a cold open within its bound, a warm reopen reported", async (t) => {
  const line = { case: "first-draw", verdict: "fail" };
  try {
    if (!coldOpen)
      assert.fail("UNMEASURED: no case opened the provider settings");
    line.cold = {
      reached: coldOpen.reached,
      drawn_ms: coldOpen.drawnMs,
      rounds: coldOpen.rounds,
      calls: coldOpen.calls,
    };
    if (!(await closeAgentSettings()))
      assert.fail("UNMEASURED: the provider settings did not close");
    const warm = await openAgentSettings();
    line.warm = {
      reached: warm.reached,
      drawn_ms: warm.drawnMs,
      rounds: warm.rounds,
      calls: warm.calls,
    };
    const cold = coldOpen.drawnMs?.providers;
    if (!coldOpen.reached || typeof cold !== "number")
      assert.fail("UNMEASURED: the cold open drew no provider settings");
    assert.ok(
      cold <= COLD_DRAW_MS,
      `the cold open drew the provider settings in ${cold} ms (bound ${COLD_DRAW_MS})`,
    );
    line.verdict = "pass";
  } finally {
    record(t, line);
  }
});

test("PSI-99 every test sign-in is gone: no credential-store growth", async (t) => {
  let teardownError = null;
  let lastDialog = null;
  try {
    // No attempt may be in flight when the profile signs out.
    if ((await exec(pageDialog)).open) lastDialog = await cancelAndClose();
  } catch (error) {
    lastDialog = `close-failed: ${error.message}`;
  }
  try {
    await teardown();
  } catch (error) {
    teardownError = error.message;
  }
  let counts = null;
  try {
    counts = credentialCounts();
  } catch (error) {
    credentialError = credentialError ?? error.message;
  }
  record(t, {
    case: "credential-store",
    before: credentialsBefore,
    after: counts,
    teardown_error: teardownError,
    signed_out: win.closed,
    dialog_before_sign_out: lastDialog,
  });
  if (process.platform !== "win32") {
    t.skip("the credential store is counted on Windows only");
    return;
  }
  assert.equal(credentialError, null, `cmdkey: ${credentialError}`);
  assert.equal(teardownError, null, `teardown: ${teardownError}`);
  for (const kind of ["profileSession", "cadrumo", "provider"])
    assert(
      counts[kind] <= credentialsBefore[kind],
      `the run left ${counts[kind] - credentialsBefore[kind]} more ${kind} credential-store target(s)`,
    );
});
