// The Antigravity command-line lane, end to end in the packaged native window
// on a synthetic root: the provider settings name the lane's two connections
// without Gemini key wording, a person signs in through the browser step the
// window shows, and one conversation turn on that lane is answered.
//
// Environment: as ./provider-sign-in.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG,
// CADRUMO_UX_RUN, optional CADRUMO_UX_STAGED_SHA256), plus
//   CADRUMO_UX_SHOTS  directory for the screenshots, the SIGN_IN_ON_SCREEN
//                     marker and antigravity-lane.json (default: none kept)
//   CADRUMO_ANTIGRAVITY_PERSON_MS  (optional) how long a person has to finish
//                     the browser step; default 900000
//   CADRUMO_ANTIGRAVITY_REPLY_MS   (optional) how long the reply may take;
//                     default 240000
//
// The sign-in is attended: the person completes the browser step the window
// offers. The sign-in code and address are never read or printed here. The run
// signs out of the profile at the end through the shared teardown, which also
// refuses a leaked profile-session key.
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
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
import { dismissSetup } from "./ux-nav.mjs";

const SHOTS = process.env.CADRUMO_UX_SHOTS ?? null;
const PERSON_MS = Number(process.env.CADRUMO_ANTIGRAVITY_PERSON_MS ?? 900_000);
const REPLY_MS = Number(process.env.CADRUMO_ANTIGRAVITY_REPLY_MS ?? 240_000);
const STAGED_SHA256 = (process.env.CADRUMO_UX_STAGED_SHA256 ?? "")
  .trim()
  .toLowerCase();
const PROVIDER = "antigravity";
const MESSAGE = "Responde solo: OK";
const TARGET = "[data-ag-target]";
const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();

let runDir;
const found = { lane: null, transport: null, way: null, model: null };
const report = { rows: [], gemini: [], turn: null };

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-antigravity-")), "run");
  await start(runDir);
});
after(async () => {
  if (SHOTS) {
    mkdirSync(SHOTS, { recursive: true });
    writeFileSync(
      join(SHOTS, "antigravity-lane.json"),
      JSON.stringify(report, null, 2),
    );
  }
  await teardown();
});

async function shot(name) {
  if (!SHOTS) return null;
  mkdirSync(SHOTS, { recursive: true });
  const path = join(SHOTS, `${name}.png`);
  await win.browser.saveScreenshot(path);
  return path;
}

// ---------------------------------------------------------------------------
// Page-side readers (serialised into the window: arguments and document only)
// ---------------------------------------------------------------------------

/** The provider settings are drawn. */
const pageSettingsDrawn = () =>
  [...document.querySelectorAll(".provider-settings")].some(
    (el) => el.getClientRects().length > 0,
  );

/** Open every row's details, then read each Antigravity lane. */
function pageLanes(provider, signInWords) {
  const text = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const rows = [
    ...document.querySelectorAll(
      `.provider-settings li[data-provider="${provider}"]`,
    ),
  ];
  for (const row of rows) {
    const expander = row.querySelector('[data-slot="lane-expander"]');
    if (expander?.getAttribute("aria-expanded") === "false") expander.click();
  }
  return rows.map((row) => ({
    id: row.getAttribute("data-lane"),
    transport: row.getAttribute("data-transport"),
    hidden: row.hidden,
    status:
      row
        .querySelector('[data-slot="provider-status"]')
        ?.getAttribute("data-status") ?? null,
    signInState: row.getAttribute("data-sign-in"),
    signIn: [...row.querySelectorAll("button")].some(
      (el) =>
        el.getClientRects().length > 0 && text(el.textContent) === signInWords,
    ),
    text: text(row.innerText),
  }));
}

/** Visible provider-settings text that says "Gemini", outside model ids and
 * names (an element carrying data-model, or inside a model list). */
function pageGemini(exceptModels) {
  const out = [];
  const root = [...document.querySelectorAll(".provider-settings")].find(
    (el) => el.getClientRects().length > 0,
  );
  if (!root) return out;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const value = (node.textContent ?? "").replace(/\s+/g, " ").trim();
    const parent = node.parentElement;
    if (!value || !parent || !/gemini/i.test(value)) continue;
    if (parent.getClientRects().length === 0) continue;
    if (
      exceptModels &&
      parent.closest(
        '[data-model], [data-slot^="model"], [data-slot="model-facts"]',
      )
    )
      continue;
    const lane = parent.closest("li[data-lane]");
    out.push({ lane: lane?.getAttribute("data-lane") ?? null, text: value });
  }
  return out;
}

/** Mark the first shown element under `scope` matching `item` whose text is
 * `text` (any when null) as the click target. */
function pageMark(scope, item, text) {
  for (const old of document.querySelectorAll("[data-ag-target]"))
    old.removeAttribute("data-ag-target");
  for (const root of document.querySelectorAll(scope)) {
    for (const el of root.querySelectorAll(item)) {
      if (!el.getClientRects().length) continue;
      if (
        text !== null &&
        (el.textContent ?? "").replace(/\s+/g, " ").trim() !== text
      )
        continue;
      el.setAttribute("data-ag-target", "1");
      return true;
    }
  }
  return false;
}

/** Mark the first shown icon button whose name starts with `name`. */
function pageMarkIconButton(name) {
  for (const old of document.querySelectorAll("[data-ag-target]"))
    old.removeAttribute("data-ag-target");
  const button = [
    ...document.querySelectorAll('button[data-slot="icon-button"]'),
  ].find(
    (el) =>
      el.getClientRects().length > 0 &&
      (el.getAttribute("aria-label") ?? "").startsWith(name),
  );
  if (!button) return "absent";
  if (button.getAttribute("aria-disabled") === "true") return "held";
  button.setAttribute("data-ag-target", "1");
  return "marked";
}

/** The shown sign-in dialog as words; never the code or address a person uses. */
function pageDialog() {
  const text = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const shown = (el) => !!el && el.getClientRects().length > 0;
  const dialog = [
    ...document.querySelectorAll('[data-slot="dialog-content"]'),
  ].find(shown);
  if (!dialog) return { open: false };
  const description = dialog.querySelector('[data-slot="dialog-description"]');
  return {
    open: true,
    attemptId:
      dialog
        .querySelector('[data-slot="sign-in-attempt"]')
        ?.getAttribute("data-attempt-id") || null,
    description: text(description?.textContent),
    alerts: [...dialog.querySelectorAll('[role="alert"]')]
      .filter(shown)
      .map((el) => text(el.textContent)),
    causes: [...dialog.querySelectorAll('[role="alert"][data-cause]')]
      .filter(shown)
      .map((el) => el.getAttribute("data-cause")),
    nextSteps: [...dialog.querySelectorAll('[role="alert"][data-next-step]')]
      .filter(shown)
      .map((el) => el.getAttribute("data-next-step")),
    // The window's own progress while the agent is stopped for the sign-in.
    stopping: [
      ...dialog.querySelectorAll(
        '[role="status"][data-slot="sign-in-agent-stopping"]',
      ),
    ]
      .filter(shown)
      .map((el) => el.getAttribute("data-cause")),
    buttons: [...dialog.querySelectorAll('[data-slot="dialog-footer"] button')]
      .filter(shown)
      .map((el) => text(el.textContent)),
  };
}

/** Mark a part of the composer: its message field, agent settings button
 * (named by the `settings` pattern), or its send or stop button. */
function pageMarkComposer(part, words, settings) {
  const text = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const shown = (el) => !!el && el.getClientRects().length > 0;
  for (const old of document.querySelectorAll("[data-ag-target]"))
    old.removeAttribute("data-ag-target");
  const field = [
    ...document.querySelectorAll('textarea[data-slot="textarea"]'),
  ].find((el) => shown(el) && el.getAttribute("aria-label") === words.message);
  if (!field) return "absent";
  let target = null;
  if (part === "field") target = field;
  else {
    const named = (el, name) =>
      (el.getAttribute("aria-label") ?? "").startsWith(name);
    let card = field.parentElement;
    for (let depth = 0; card && depth < 8; depth += 1) {
      const buttons = [...card.querySelectorAll("button")].filter(shown);
      if (
        buttons.some((el) => named(el, words.send) || named(el, words.stop))
      ) {
        const pattern = new RegExp(settings);
        target =
          part === "settings"
            ? buttons.find((el) =>
                pattern.test(text(el.getAttribute("aria-label"))),
              )
            : buttons.find(
                (el) =>
                  el.getAttribute("data-slot") === "icon-button" &&
                  named(el, part === "send" ? words.send : words.stop),
              );
        break;
      }
      card = card.parentElement;
    }
  }
  if (!target) return "absent";
  if (target.getAttribute("aria-disabled") === "true" || target.disabled)
    return "held";
  target.setAttribute("data-ag-target", "1");
  return "marked";
}

/** The open model picker's rows for `way`: those that can be chosen, first
 * first; marks the first one's default cell as the click target. */
function pagePickModel(way) {
  for (const old of document.querySelectorAll("[data-ag-target]"))
    old.removeAttribute("data-ag-target");
  const rows = [
    ...document.querySelectorAll('tr[data-slot="model-matrix-row"]'),
  ].filter((el) => el.getClientRects().length > 0);
  if (rows.length === 0) return null;
  const offered = [...new Set(rows.map((el) => el.getAttribute("data-way")))];
  const mine = rows.filter(
    (el) =>
      el.getAttribute("data-way") === way && !el.hasAttribute("aria-disabled"),
  );
  if (mine.length === 0) return { found: false, offered };
  const cell = mine[0].querySelector('[role="radio"][data-column="default"]');
  if (!cell) return { found: false, offered };
  cell.setAttribute("data-ag-target", "1");
  return { found: true, model: mine[0].getAttribute("data-model"), offered };
}

/** The way and model of the matrix row that reads chosen. */
const pageChosen = () => {
  const row = [
    ...document.querySelectorAll(
      'tr[data-slot="model-matrix-row"] [role="radio"][aria-checked="true"]',
    ),
  ]
    .map((el) => el.closest("tr"))
    .find((el) => el?.getClientRects().length > 0);
  return row
    ? {
        way: row.getAttribute("data-way"),
        model: row.getAttribute("data-model"),
      }
    : null;
};

/** The shown transcript: the agent's turns after the person's `message`, as
 * lengths and states, never their text. */
function pageReply(message, words) {
  const text = (value) => (value ?? "").replace(/\s+/g, " ").trim();
  const shown = (el) => !!el && el.getClientRects().length > 0;
  const log = [...document.querySelectorAll('[role="log"]')].find(
    (el) => shown(el) && el.getAttribute("aria-label") === words.transcript,
  );
  if (!log) return { found: false };
  const running = [
    ...document.querySelectorAll('button[data-slot="icon-button"]'),
  ].some(
    (el) =>
      shown(el) && (el.getAttribute("aria-label") ?? "").startsWith(words.stop),
  );
  const items = [...log.querySelectorAll("ol > li")];
  const asked =
    message === null
      ? -1
      : items.findLastIndex((li) =>
          [...li.querySelectorAll("[aria-label]")].some(
            (el) =>
              el.getAttribute("aria-label") === words.youSaid &&
              [...el.querySelectorAll("p")].some(
                (p) => text(p.textContent) === message,
              ),
          ),
        );
  const replies =
    asked < 0
      ? []
      : items
          .slice(asked + 1)
          .map((li) => li.querySelector(":scope > article"))
          .filter(
            (article) =>
              article && article.getAttribute("aria-label") === words.replied,
          )
          .map((article) => {
            const body = [...article.children]
              .filter(
                (el) =>
                  el.tagName === "DIV" &&
                  el.classList.contains("text-foreground"),
              )
              .map((el) => text(el.textContent))
              .join(" ");
            const says = (word) =>
              [...article.querySelectorAll("p, button, [aria-expanded]")].some(
                (el) => text(el.textContent) === word,
              );
            return {
              length: body.length,
              state: article.querySelector(".text-destructive")
                ? "failed"
                : says(words.working)
                  ? "working"
                  : says(words.waiting)
                    ? "waiting"
                    : says(words.stopped)
                      ? "stopped"
                      : "done",
            };
          });
  return {
    found: true,
    items: items.length,
    asked: asked >= 0,
    replies,
    running,
  };
}

/** Visible alerts in the agent column, as lengths only (the words may quote a
 * provider's refusal). */
const pageAgentAlerts = () =>
  [
    ...document.querySelectorAll(
      '.pane-agent [role="alert"], .pane-agent [data-slot="alert"]',
    ),
  ].filter((el) => el.getClientRects().length > 0).length;

const pageErrorBadge = () => {
  const mark = document.querySelector(
    '[data-rail="panel"] [data-slot="badge"]',
  );
  return mark
    ? mark.textContent || mark.getAttribute("data-capped") || "shown"
    : null;
};

// ---------------------------------------------------------------------------
// Window steps
// ---------------------------------------------------------------------------

const signInWords = () => label("desktop.providers.sign_in_action");

async function press(scope, item, text) {
  if (!(await exec(pageMark, scope, item, text))) return false;
  await clickSelector(TARGET);
  return true;
}

/** Show the agent column's provider settings. */
async function openAgentSettings() {
  await dismissSetup();
  if (await exec(pageSettingsDrawn)) return;
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
  for (let round = 0; round < 3; round += 1) {
    const marked = await waitFor(
      async () => {
        const state = await exec(pageMarkIconButton, name);
        return state === "absent" ? null : state;
      },
      { timeout: 20_000, what: "the agent settings door", soft: true },
    );
    if (marked === "marked") await clickSelector(TARGET);
    if (
      await waitFor(() => exec(pageSettingsDrawn), {
        timeout: 20_000,
        what: "the provider settings",
        soft: true,
      })
    )
      return;
  }
  assert.fail("the provider settings were not drawn");
}

async function closeAgentSettings() {
  const pressed = await exec((name) => {
    for (const old of document.querySelectorAll("[data-ag-target]"))
      old.removeAttribute("data-ag-target");
    const button = [
      ...document.querySelectorAll('button[data-slot="icon-button"]'),
    ].find(
      (el) =>
        el.getClientRects().length > 0 &&
        (el.getAttribute("aria-label") ?? "").startsWith(name),
    );
    if (button?.getAttribute("aria-pressed") !== "true") return false;
    button.setAttribute("data-ag-target", "1");
    return true;
  }, label("desktop.agent.settings"));
  if (pressed) await clickSelector(TARGET);
  await waitFor(async () => !(await exec(pageSettingsDrawn)), {
    timeout: 10_000,
    what: "the provider settings to close",
  });
}

/** The Antigravity lanes once the service's sign-in reads have settled. */
async function readLanes() {
  const settled = await waitFor(
    async () => {
      const lanes = await exec(pageLanes, PROVIDER, signInWords());
      if (lanes.length === 0) return null;
      const ready = lanes.every(
        (lane) =>
          lane.signIn ||
          lane.status === "signed_in" ||
          ["offered", "unavailable"].includes(lane.signInState),
      );
      return ready ? lanes : null;
    },
    {
      timeout: 90_000,
      what: "the Antigravity lanes' sign-in reads",
      soft: true,
    },
  );
  const lanes = settled ?? (await exec(pageLanes, PROVIDER, signInWords()));
  assert(lanes.length > 0, "the provider settings list no Antigravity lane");
  return lanes;
}

// ---------------------------------------------------------------------------
// The run
// ---------------------------------------------------------------------------

test("AG-00 the run records the live bundle and the host executable", (t) => {
  t.diagnostic(
    JSON.stringify({
      probe: "antigravity-lane",
      bundle: runIdentity.bundle,
      exe: runIdentity.exe,
      exeSha256: runIdentity.exeSha256,
    }),
  );
  assert.equal(runIdentity.error, null, `run identity: ${runIdentity.error}`);
  if (STAGED_SHA256)
    assert.equal(
      runIdentity.exeSha256?.toLowerCase(),
      STAGED_SHA256,
      "the window ran another executable than the freshly staged host",
    );
});

test("AG-01 the provider settings show the Antigravity lanes", async (t) => {
  await openAgentSettings();
  const lanes = await readLanes();
  await shot("antigravity-01-settings");
  await exec(() => {
    document
      .querySelector('.provider-settings li[data-provider="antigravity"]')
      ?.scrollIntoView({ block: "start" });
  });
  await sleep(400);
  await shot("antigravity-02-row");
  report.rows = lanes.map(({ id, transport, status, signInState, text }) => ({
    id,
    transport,
    status,
    signInState,
    text,
  }));
  for (const row of report.rows)
    t.diagnostic(`antigravity row ${row.transport}: ${row.text}`);
  assert(
    lanes.some((lane) => lane.transport === "cli"),
    `no Antigravity command-line lane (lanes: ${JSON.stringify(lanes.map((lane) => lane.transport))})`,
  );
});

test("AG-02 no provider settings text says Gemini outside model names", async () => {
  const offending = await exec(pageGemini, true);
  report.gemini = offending;
  if (offending.length > 0) {
    await shot("antigravity-defect-gemini");
    assert.fail(
      `provider settings text says Gemini: ${JSON.stringify(offending)}`,
    );
  }
});

test(
  "AG-03 a person signs in to Antigravity through the browser step",
  { timeout: PERSON_MS + 180_000 },
  async (t) => {
    await openAgentSettings();
    const lanes = await readLanes();
    const lane =
      lanes.find((item) => item.signIn && item.transport === "cli") ??
      lanes.find((item) => item.signIn);
    if (!lane) {
      const already = lanes.find((item) => item.status === "signed_in");
      assert(
        already,
        `no Antigravity lane offers "${signInWords()}" (lanes: ${JSON.stringify(lanes.map(({ id, status, signInState }) => ({ id, status, signInState })))})`,
      );
      found.lane = already.id;
      found.transport = already.transport;
      return;
    }
    found.lane = lane.id;
    found.transport = lane.transport;
    assert(
      await press(`li[data-lane="${lane.id}"]`, "button", signInWords()),
      "the sign-in could not be pressed",
    );
    // The browser step is on screen once the dialog's attempt is answered and
    // it waits on the person rather than starting or failing.
    const waiting = [
      "desktop.providers.sign_in_waiting",
      "desktop.providers.sign_in_waiting_device",
      "desktop.providers.sign_in_code_prompt",
    ].map((key) => norm(label(key)));
    // A terminal sign-in first retires the running agent: the attempt is
    // answered busy for the running agent, the dialog says so as progress and
    // starts again on its own once the agent is gone. Only when its own
    // retries pass their bound does it offer the retry button, which a person
    // presses.
    const retryWords = label("desktop.providers.sign_in_retry");
    let retries = 0;
    let sawStopping = false;
    const step = await waitFor(
      async () => {
        const now = await exec(pageDialog);
        if (!now.open) return null;
        if (now.stopping.length > 0 && !sawStopping) {
          sawStopping = true;
          t.diagnostic(
            `antigravity sign-in waits for the agent to stop: ${JSON.stringify(now.stopping)}`,
          );
          await shot("antigravity-03a-agent-stopping");
        }
        if (
          now.alerts.length > 0 &&
          now.causes.length > 0 &&
          now.causes.every((cause) => cause === "agent_tree_running") &&
          retries < 3
        ) {
          if (now.buttons.includes(norm(retryWords))) {
            retries += 1;
            t.diagnostic(
              `antigravity sign-in retry ${retries}: ${JSON.stringify(now.alerts)}`,
            );
            await press(
              '[data-slot="dialog-footer"]',
              "button",
              norm(retryWords),
            );
          }
          return null;
        }
        if (now.alerts.length > 0) return { failed: true, now };
        return waiting.includes(now.description)
          ? { failed: false, now }
          : null;
      },
      { timeout: 120_000, what: "the browser step of the sign-in", soft: true },
    );
    if (!step || step.failed) {
      await shot("antigravity-defect-sign-in");
      assert.fail(
        step
          ? `the sign-in failed: ${JSON.stringify(step.now.alerts)}`
          : "the window showed no browser step within 120 s",
      );
    }
    if (SHOTS) {
      mkdirSync(SHOTS, { recursive: true });
      writeFileSync(
        join(SHOTS, "SIGN_IN_ON_SCREEN"),
        `${new Date().toISOString()}\n`,
      );
    }
    await shot("antigravity-03-sign-in");
    const began = Date.now();
    const codePrompt = norm(label("desktop.providers.sign_in_code_prompt"));
    let codeShown = false;
    const outcome = await waitFor(
      async () => {
        const now = await exec(pageDialog);
        if (now.open && now.description === codePrompt && !codeShown) {
          codeShown = true;
          await shot("antigravity-03b-code-prompt");
        }
        if (now.open && now.alerts.length > 0) return { ok: false };
        if (now.open) return null;
        const read = await exec(pageLanes, PROVIDER, signInWords());
        return read.find((item) => item.id === lane.id)?.status === "signed_in"
          ? { ok: true }
          : null;
      },
      { timeout: PERSON_MS, what: "the person's sign-in", soft: true },
    );
    t.diagnostic(`antigravity sign-in took ${Date.now() - began} ms`);
    if (!outcome?.ok) {
      await shot("antigravity-defect-sign-in");
      assert.fail(
        outcome
          ? "the sign-in failed"
          : "no signed-in lane before the person's time ran out",
      );
    }
    await sleep(500);
    await shot("antigravity-04-signed-in");
  },
);

const agentWords = () => ({
  transcript: label("desktop.agent.transcript"),
  youSaid: label("desktop.agent.you_said"),
  replied: label("desktop.agent.agent_replied"),
  working: label("desktop.agent.working"),
  waiting: label("desktop.agent.waiting_on_you"),
  stopped: label("desktop.agent.stopped"),
  message: label("desktop.agent.message_label"),
  send: label("desktop.agent.send"),
  stop: label("desktop.agent.stop"),
});

const escaped = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
/** A served template as a whole-name pattern source, each `{slot}` open. */
const settingsPattern = () =>
  `^${label("desktop.agent.settings_label")
    .split(/\{\w+\}/)
    .map((part) => escaped(part.replace(/\s+/g, " ").trim()))
    .join(".*?")}`;

test(
  "AG-04 a conversation turn on the Antigravity lane is answered",
  { timeout: REPLY_MS + 240_000 },
  async (t) => {
    assert(found.lane, "AG-03 reached no Antigravity lane to send from");
    const words = agentWords();
    await closeAgentSettings();
    const agentShown = await exec(
      () =>
        document
          .querySelector('[data-rail="agent"]')
          ?.getAttribute("aria-pressed") === "true",
    );
    if (!agentShown) await clickSelector('[data-rail="agent"]');
    const fresh = await waitFor(
      async () => {
        const state = await exec(
          pageMarkIconButton,
          label("desktop.agent.new_conversation"),
        );
        return state === "absent" ? null : state;
      },
      { timeout: 30_000, what: "the new conversation button", soft: true },
    );
    assert(fresh, "the agent column offers no new conversation");
    if (fresh === "marked") await clickSelector(TARGET);
    await waitFor(
      async () => {
        const read = await exec(pageReply, null, words);
        return read.found && read.items === 0;
      },
      { timeout: 15_000, what: "an empty new conversation" },
    );

    // The real picker: the composer's settings, then the first model offered
    // under the Antigravity command-line lane.
    const way = `${PROVIDER}/${found.transport}`;
    found.way = way;
    const opened = await waitFor(
      async () =>
        (await exec(pageMarkComposer, "settings", words, settingsPattern())) ===
        "marked",
      { timeout: 30_000, what: "the composer's agent settings", soft: true },
    );
    assert(opened, "the composer offers no agent settings button");
    await clickSelector(TARGET);
    const pick = await waitFor(() => exec(pagePickModel, way), {
      timeout: 30_000,
      what: "the model picker's rows",
      soft: true,
    });
    assert(pick, "the model picker drew no model rows");
    assert(
      pick.found,
      `the model picker offers no choosable model for ${way} (ways offered: ${JSON.stringify(pick.offered)})`,
    );
    found.model = pick.model;
    await clickSelector(TARGET);
    const chosen = await waitFor(
      async () => {
        const now = await exec(pageChosen);
        return now?.way === way && now.model === pick.model ? now : null;
      },
      { timeout: 15_000, what: "the chosen Antigravity model", soft: true },
    );
    assert(chosen, `the picker does not show ${way} / ${pick.model} as chosen`);
    t.diagnostic(`antigravity picker: way=${way} model=${pick.model}`);
    await win.browser.keys(["Escape"]);
    await waitFor(async () => (await exec(pagePickModel, way)) === null, {
      timeout: 10_000,
      what: "the model picker to close",
      soft: true,
    });

    assert(
      await waitFor(
        async () =>
          (await exec(pageMarkComposer, "field", words, "")) === "marked",
        { timeout: 30_000, what: "the message field", soft: true },
      ),
      "the composer offers no message field",
    );
    await (await win.browser.$(TARGET)).setValue(MESSAGE);
    assert(
      await waitFor(
        async () =>
          (await exec(pageMarkComposer, "send", words, "")) === "marked",
        { timeout: 15_000, what: "the send button", soft: true },
      ),
      "the composer does not offer Send for the typed message",
    );
    const badgeBefore = await exec(pageErrorBadge);
    const sent = Date.now();
    await clickSelector(TARGET);
    const last = await waitFor(
      async () => {
        const read = await exec(pageReply, MESSAGE, words);
        if (!read.found || !read.asked) return null;
        const length = read.replies.reduce((sum, item) => sum + item.length, 0);
        const states = read.replies.map((item) => item.state);
        const settled =
          !read.running &&
          read.replies.length > 0 &&
          states.every((state) => state === "done") &&
          length > 0;
        return states.includes("failed") || settled ? { length, states } : null;
      },
      { timeout: REPLY_MS, what: "the settled reply", soft: true },
    );
    const alerts = await exec(pageAgentAlerts);
    const badgeAfter = await exec(pageErrorBadge);
    await shot("antigravity-05-turn");
    report.turn = {
      way,
      model: pick.model,
      reply_ms: Date.now() - sent,
      reply_length: last?.length ?? null,
      states: last?.states ?? null,
      alerts,
      badge_before: badgeBefore,
      badge_after: badgeAfter,
    };
    t.diagnostic(JSON.stringify({ probe: "antigravity-lane", ...report.turn }));
    // No run is left in flight.
    if ((await exec(pageMarkComposer, "stop", words, "")) === "marked")
      await clickSelector(TARGET);
    assert(last, `no settled reply within ${REPLY_MS / 1000} s`);
    assert(
      !last.states.includes("failed"),
      "the agent's reply was drawn failed",
    );
    assert(last.length > 0, "the agent's reply has no text");
    assert.equal(alerts, 0, "the agent column shows an error banner");
    assert.equal(
      badgeAfter,
      badgeBefore,
      `the window counts new session errors: ${badgeAfter}`,
    );
  },
);
