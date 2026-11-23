// View links an agent writes, opened in the packaged native window. A real
// provider lane is asked to list Cadrumo's view register through the `views`
// tool and to answer with one link per view. The reply's links must be
// exactly the register's window (gui) elements, and each must open its view
// in the window when a person clicks it, with no refusal toast and nothing
// handed to the system browser. One window serves the whole file.
//
// AVL-01 needs no provider: it asks the package's own cadrumo-mcp, on the
// run's storage and admitted by the window's sign-in, for the same `views`
// rows, and opens each row's link as served through the window's palette,
// which opens links through the same navigator as a reply's link. AVL-02 and
// AVL-03 need a provider lane that reads ready; without one they fail as
// UNMEASURED.
//
// Environment: as ./window-ux-audit.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG,
// CADRUMO_UX_RUN, CADRUMO_UX_STAGED_SHA256), plus
//   CADRUMO_DESKTOP_AGENT_LINKS_PERSON  1: when no provider lane of the run's profile
//                    reads ready, a person signs one in (in the window's agent
//                    settings, or from the console) while the run waits;
//                    otherwise such a run fails as unmeasured, never faked
//   CADRUMO_DESKTOP_AGENT_LINKS_PERSON_MS  (optional) how long the person has;
//                    default 600000
//   CADRUMO_DESKTOP_AGENT_LINKS_REPLY_MS  (optional) how long the agent has to settle
//                    its reply; default 300000
//
// CADRUMO_UX_RUN must lie outside every Git project: the agent service refuses
// a provider home inside one. The run's storage is a copy of the persona
// world's, so the provider sign-in, the conversation and its transcript stay
// in that copy. The run signs out of the profile at the end. Credential-store
// targets are only counted; no target name or secret is printed.
//
// The register is read from the build's generated navigation.json and the
// window's table from its source module, never restated here. Results are
// appended, one JSON object per line, to <run>/agent-view-links.jsonl.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import {
  appendFileSync,
  closeSync,
  mkdtempSync,
  openSync,
  readFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { after, before, test } from "node:test";
import { buildPath } from "../../scripts/build-paths.mjs";
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

const PERSON = process.env.CADRUMO_DESKTOP_AGENT_LINKS_PERSON === "1";
const PERSON_MS = Number(
  process.env.CADRUMO_DESKTOP_AGENT_LINKS_PERSON_MS ?? 600_000,
);
const REPLY_MS = Number(
  process.env.CADRUMO_DESKTOP_AGENT_LINKS_REPLY_MS ?? 300_000,
);
const STAGED_SHA256 = (process.env.CADRUMO_UX_STAGED_SHA256 ?? "")
  .trim()
  .toLowerCase();

// ---------------------------------------------------------------------------
// The register, the window's table and the chrome words: read, not restated.
// ---------------------------------------------------------------------------

const GENERATED = buildPath("desktop_frontend_generated");
const REGISTER = JSON.parse(
  readFileSync(resolve(GENERATED, "navigation.json"), "utf8"),
);
const surfacesOf = (element) =>
  Array.isArray(element.surfaces) ? element.surfaces : [];
/** The register's elements the window implements. */
const GUI_IDS = new Set(
  REGISTER.elements
    .filter((element) => surfacesOf(element).includes("gui"))
    .map((element) => element.id),
);
/** The register's elements the window does not implement. */
const NOT_GUI_IDS = new Set(
  REGISTER.elements
    .filter((element) => !surfacesOf(element).includes("gui"))
    .map((element) => element.id),
);
// The views the window never draws whose links opened nothing: the defect
// this file guards. They must stay out of what the agent is handed.
const NEVER_DRAWN = [
  "home",
  "withholding",
  "operations",
  "installation",
  "reference",
];

const { WINDOW_VIEWS } = await import(
  new URL("../../frontend/src/shell/navigation/windowViews.ts", import.meta.url)
    .href
);

/** What shows a page of the first pane, as the Playwright scenarios find it. */
const PAGE_ROOT = {
  profile: ".user-profile-page",
  calendar: ".calendar-page",
  ledger: ".ledger-page",
  declarations: ".declarations-page",
  docs: ".docs-frame",
  browser: "[data-browser-surface]",
  "aeat-sync": ".aeat-sync-page",
};

const CATALOGUE = JSON.parse(
  readFileSync(resolve(GENERATED, "chrome-strings.json"), "utf8"),
);
const REFUSAL_KEYS = Object.keys(CATALOGUE.en ?? {}).filter((key) =>
  key.startsWith("desktop.navigation.refused."),
);

const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();

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

/** The refusal key a shown toast says, or null. */
function refusalOf(text) {
  for (const key of REFUSAL_KEYS) {
    const said = label(key);
    if (said !== key && templatePattern(said).test(norm(text))) return key;
  }
  return null;
}

/** What the window must show once the link to `id` opened, from its table. */
function expectedView(id) {
  const entry = WINDOW_VIEWS[id];
  if (!entry) return null;
  const view = entry.view;
  switch (view.kind) {
    case "page":
      return {
        kind: "page",
        selector: PAGE_ROOT[view.page],
        section: view.section
          ? label(`desktop.ledger.section.${view.section}`)
          : null,
        dialog:
          view.dialog === "aeat-access"
            ? label("desktop.profile.action.aeat_access")
            : null,
      };
    case "agent":
      return { kind: "agent", selector: ".pane-agent" };
    case "terminal":
      return { kind: "terminal", selector: '[data-terminal="tui"]' };
    case "panel":
      return {
        kind: "panel",
        selector:
          view.tab === null
            ? "#panel-console, #panel-python, #panel-logs"
            : `#panel-${view.tab}`,
      };
  }
  return null;
}

// ---------------------------------------------------------------------------
// The credential store: targets counted by class, never printed.
// ---------------------------------------------------------------------------

const SESSION_SUFFIX = "@cadrumo:profile-session:v2";

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
// Page-side readers (serialised into the window: arguments and document only)
// ---------------------------------------------------------------------------

const TARGET = "[data-avl-target]";

/** Mark the first shown icon button whose name starts with `name`; answers
 * "marked", "pressed" (marked, and already pressed), "held" or "absent". */
function pageMarkIconButton(name) {
  for (const old of document.querySelectorAll("[data-avl-target]"))
    old.removeAttribute("data-avl-target");
  const button = [
    ...document.querySelectorAll('button[data-slot="icon-button"]'),
  ].find(
    (el) =>
      el.getClientRects().length > 0 &&
      (el.getAttribute("aria-label") ?? "").startsWith(name),
  );
  if (!button) return "absent";
  if (button.getAttribute("aria-disabled") === "true") return "held";
  button.setAttribute("data-avl-target", "1");
  return button.getAttribute("aria-pressed") === "true" ? "pressed" : "marked";
}

/** Every provider lane the agent settings draw, each group opened. */
function pageLanes() {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const lanes = [];
  for (const group of document.querySelectorAll(
    ".provider-settings li[data-provider]",
  )) {
    const details = group.querySelector(":scope > details");
    if (details && !details.open) details.open = true;
    for (const lane of group.querySelectorAll("li[data-lane]")) {
      const swatch = lane.querySelector('[role="switch"]');
      lanes.push({
        provider: group.getAttribute("data-provider"),
        id: lane.getAttribute("data-lane"),
        transport: lane.getAttribute("data-transport"),
        connection: norm(lane.querySelector("h5")?.textContent),
        hidden: lane.hidden,
        status:
          lane
            .querySelector('[data-slot="provider-status"]')
            ?.getAttribute("data-status") ?? null,
        on: swatch ? swatch.getAttribute("aria-checked") === "true" : null,
      });
    }
  }
  return lanes;
}

const settingsDrawn = () =>
  [...document.querySelectorAll(".provider-settings")].some(
    (el) => el.getClientRects().length > 0,
  );

/** Mark a part of the composer as the click target: its message field, its
 * agent settings button (named by `settings`, a whole-name pattern), or its
 * send button. Answers "marked", "held" or "absent". */
function pageMarkComposer(part, words, settings) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const shown = (el) => !!el && el.getClientRects().length > 0;
  for (const old of document.querySelectorAll("[data-avl-target]"))
    old.removeAttribute("data-avl-target");
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
                pattern.test(norm(el.getAttribute("aria-label"))),
              )
            : buttons.find(
                (el) =>
                  el.getAttribute("data-slot") === "icon-button" &&
                  named(el, words.send),
              );
        break;
      }
      card = card.parentElement;
    }
  }
  if (!target) return "absent";
  if (target.getAttribute("aria-disabled") === "true" || target.disabled)
    return "held";
  target.setAttribute("data-avl-target", "1");
  return "marked";
}

/** The shown transcript: how many turns it lists, and the agent's turns
 * after the person's `message`, each with its state and the addresses of the
 * cadrumo links it draws. `running` is whether the composer offers Stop. */
function pageReply(message, words) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
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
              norm(el.textContent).includes(message),
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
            const says = (word) =>
              [...article.querySelectorAll("p, button, [aria-expanded]")].some(
                (el) => norm(el.textContent) === word,
              );
            return {
              length: norm(article.textContent).length,
              links: [...article.querySelectorAll("a[href]")]
                .map((a) => a.getAttribute("href"))
                .filter((href) => /^cadrumo:/i.test(href)),
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

/** The agent's tool approval card, if one is shown: allow once a call of
 * the views tool, refuse once any other. Marks the button to press and
 * answers what the card asked (its tool line only) and the choice. */
function pageApproval(tool, allow, reject) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  for (const old of document.querySelectorAll("[data-avl-target]"))
    old.removeAttribute("data-avl-target");
  const card = [
    ...document.querySelectorAll(".pane-agent section.agent-approval"),
  ].find((el) => el.getClientRects().length > 0);
  if (!card) return null;
  const asked = norm(card.querySelector("h3")?.textContent).slice(0, 120);
  const wanted = new RegExp(`(^|[^a-z_])${tool}$`, "i").test(asked)
    ? allow
    : reject;
  const button = [...card.querySelectorAll("button")].find(
    (el) => el.getClientRects().length > 0 && norm(el.textContent) === wanted,
  );
  if (!button) return { asked, choice: null };
  button.setAttribute("data-avl-target", "1");
  return { asked, choice: wanted === allow ? "allow_once" : "reject_once" };
}

/** Mark the first link to `href` in the agent's turns after `message`. */
function pageMarkLink(message, words, href) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  for (const old of document.querySelectorAll("[data-avl-target]"))
    old.removeAttribute("data-avl-target");
  const log = [...document.querySelectorAll('[role="log"]')].find(
    (el) =>
      el.getClientRects().length > 0 &&
      el.getAttribute("aria-label") === words.transcript,
  );
  if (!log) return false;
  const items = [...log.querySelectorAll("ol > li")];
  const asked = items.findLastIndex((li) =>
    [...li.querySelectorAll("[aria-label]")].some(
      (el) =>
        el.getAttribute("aria-label") === words.youSaid &&
        norm(el.textContent).includes(message),
    ),
  );
  if (asked < 0) return false;
  for (const li of items.slice(asked + 1)) {
    const article = li.querySelector(":scope > article");
    if (article?.getAttribute("aria-label") !== words.replied) continue;
    const link = [...article.querySelectorAll("a[href]")].find(
      (a) => a.getAttribute("href") === href,
    );
    if (link) {
      link.setAttribute("data-avl-target", "1");
      return true;
    }
  }
  return false;
}

/** The window's own toasts shown now, as text; a page's own are not. */
function pageToasts() {
  return [
    ...document.querySelectorAll(
      "[data-slot=toast]:not(.ledger-toast):not(.ledger-page-toast)",
    ),
  ]
    .filter((el) => el.getClientRects().length > 0)
    .map((el) => (el.textContent ?? "").replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

/** Whether `expected` is shown: its root, its Ledger section, its dialog. */
function pageShown(expected) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const shown = (el) => !!el && el.getClientRects().length > 0;
  const root = [...document.querySelectorAll(expected.selector)].find(shown);
  if (!root) return { shown: false, why: "root" };
  if (expected.section) {
    // The Ledger's section tabs sit in its pane head, as the palette
    // scenarios find them.
    const tab = [
      ...document.querySelectorAll(
        '.pane-docs .pane-head [role="tab"][aria-selected="true"]',
      ),
    ].find(
      (el) =>
        shown(el) &&
        (norm(el.getAttribute("aria-label")) === expected.section ||
          norm(el.textContent).startsWith(expected.section)),
    );
    const setup = [...document.querySelectorAll("button.ledger-setup")].find(
      (el) => shown(el) && norm(el.textContent).startsWith(expected.section),
    );
    if (!tab && !setup) return { shown: false, why: "section" };
  }
  if (expected.dialog) {
    const named = (el) => {
      const by = el.getAttribute("aria-labelledby");
      return norm(
        el.getAttribute("aria-label") ??
          (by
            ? by
                .split(/\s+/)
                .map((id) => document.getElementById(id)?.textContent ?? "")
                .join(" ")
            : ""),
      );
    };
    const dialog = [...document.querySelectorAll('[role="dialog"]')].find(
      (el) => shown(el) && named(el) === expected.dialog,
    );
    if (!dialog) return { shown: false, why: "dialog" };
  }
  return { shown: true };
}

/** Whether any dialog is shown over the window. */
const pageDialogShown = () =>
  [...document.querySelectorAll('[role="dialog"]')].some(
    (el) => el.getClientRects().length > 0,
  );

// ---------------------------------------------------------------------------
// Window steps
// ---------------------------------------------------------------------------

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

async function showAgentColumn() {
  const pressed = await exec(
    () =>
      document
        .querySelector('[data-rail="agent"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  if (!pressed) await clickSelector('[data-rail="agent"]');
  return waitFor(
    () =>
      exec(() =>
        [...document.querySelectorAll(".pane-agent")].some(
          (el) => el.getClientRects().length > 0,
        ),
      ),
    { timeout: 15_000, what: "the agent column", soft: true },
  );
}

/** Open the agent column's provider settings; answers whether drawn. */
async function openProviderSettings() {
  await dismissSetup();
  if (await exec(settingsDrawn)) return true;
  await showAgentColumn();
  const name = label("desktop.agent.settings");
  for (let round = 0; round < 3; round += 1) {
    const marked = await exec(pageMarkIconButton, name);
    if (marked === "absent" || marked === "held") {
      await sleep(5000);
      continue;
    }
    if (marked === "marked") await clickSelector(TARGET);
    if (
      await waitFor(() => exec(settingsDrawn), {
        timeout: 20_000,
        what: "the provider settings",
        soft: true,
      })
    )
      return true;
  }
  return false;
}

async function closeProviderSettings() {
  if (
    (await exec(pageMarkIconButton, label("desktop.agent.settings"))) ===
    "pressed"
  )
    await clickSelector(TARGET);
  return waitFor(async () => !(await exec(settingsDrawn)), {
    timeout: 10_000,
    what: "the provider settings to close",
    soft: true,
  });
}

const readyLane = (lanes) =>
  lanes.find(
    (lane) =>
      !lane.hidden &&
      lane.on !== false &&
      lane.status === "ready" &&
      lane.provider &&
      lane.transport,
  ) ?? null;

/** A provider lane of the run's profile that reads ready, waiting for a
 * person to sign one in when CADRUMO_DESKTOP_AGENT_LINKS_PERSON is 1. */
async function findReadyLane(line) {
  if (!(await openProviderSettings()))
    return { reason: "the agent column did not draw its provider settings" };
  let last = [];
  const ready = await waitFor(
    async () => {
      last = await exec(pageLanes);
      return readyLane(last);
    },
    { timeout: 90_000, what: "a ready provider lane", soft: true },
  );
  line.lanes = last.map(({ provider, transport, status, on, hidden }) => ({
    provider,
    transport,
    status,
    on,
    hidden,
  }));
  if (ready) return { lane: ready };
  if (!PERSON)
    return {
      reason:
        "no provider lane of the run's profile reads ready, and CADRUMO_DESKTOP_AGENT_LINKS_PERSON is not 1",
    };
  const host = JSON.parse(process.env.CADRUMO_PERSONA_HOST);
  console.info(
    `A PERSON IS NEEDED: sign in to a provider in the open window (agent column, settings, Sign in), ` +
      `or set CADRUMO_STORAGE_ROOT to ${join(runDir, "storage")} and run ` +
      `"${join(host.package, "bin", "cadrumo-agent-service.exe")}" provider-login --provider claude. ` +
      `The run waits ${Math.round(PERSON_MS / 60_000)} minutes.`,
  );
  const signed = await waitFor(
    async () => {
      if (!(await exec(settingsDrawn))) await openProviderSettings();
      last = await exec(pageLanes);
      return readyLane(last);
    },
    {
      timeout: PERSON_MS,
      what: "a provider lane a person signed in",
      soft: true,
      interval: 3000,
    },
  );
  line.person_signed_in = !!signed;
  return signed
    ? { lane: signed }
    : {
        reason: "no provider lane read ready before the person's time ran out",
      };
}

/** Open a new conversation and choose `way` in the composer's settings. */
async function newConversationOn(line, way) {
  const words = agentWords();
  await closeProviderSettings();
  await showAgentColumn();
  const fresh = await waitFor(
    async () => {
      const marked = await exec(
        pageMarkIconButton,
        label("desktop.agent.new_conversation"),
      );
      return marked === "absent" ? null : marked;
    },
    { timeout: 30_000, what: "the new conversation button", soft: true },
  );
  if (!fresh)
    assert.fail("UNMEASURED: the agent column offers no new conversation");
  if (fresh === "marked" || fresh === "pressed") await clickSelector(TARGET);
  const empty = await waitFor(
    async () => {
      const read = await exec(pageReply, null, words);
      return read.found && read.items === 0 ? read : null;
    },
    { timeout: 15_000, what: "an empty new conversation", soft: true },
  );
  assert(empty, "the new conversation's transcript is not empty");

  const settings = templatePattern(
    label("desktop.agent.settings_label"),
  ).source;
  const opened = await waitFor(
    async () =>
      (await exec(pageMarkComposer, "settings", words, settings)) === "marked",
    { timeout: 30_000, what: "the composer's agent settings", soft: true },
  );
  if (!opened)
    assert.fail("UNMEASURED: the composer offers no agent settings button");
  await clickSelector(TARGET);
  await waitFor(
    () =>
      exec(() =>
        [...document.querySelectorAll('[data-slot="provider-select"]')].some(
          (el) => el.getClientRects().length > 0,
        ),
      ),
    { timeout: 15_000, what: "the provider picker" },
  );
  await clickSelector('[data-slot="provider-select"]');
  const entry = await waitFor(
    () =>
      exec((way) => {
        for (const old of document.querySelectorAll("[data-avl-target]"))
          old.removeAttribute("data-avl-target");
        const items = [
          ...document.querySelectorAll('[data-slot="command-item"][data-way]'),
        ].filter((el) => el.getClientRects().length > 0);
        if (items.length === 0) return null;
        const item = items.find((el) => el.getAttribute("data-way") === way);
        if (!item || item.getAttribute("data-disabled") === "true")
          return {
            selectable: false,
            offered: items.map((el) => el.getAttribute("data-way")),
          };
        item.setAttribute("data-avl-target", "1");
        return {
          selectable: true,
          name: (item.querySelector(".font-medium")?.textContent ?? "").trim(),
        };
      }, way),
    { timeout: 30_000, what: "the provider list's entries", soft: true },
  );
  if (!entry?.selectable)
    assert.fail(
      `the composer's provider list offers no selectable "${way}" (entries: ${JSON.stringify(entry?.offered ?? [])})`,
    );
  await clickSelector(TARGET);
  const chosen = await waitFor(
    () =>
      exec(
        (name) =>
          [...document.querySelectorAll('[data-slot="provider-select"]')].some(
            (el) =>
              el.getClientRects().length > 0 &&
              (el.textContent ?? "").includes(name),
          ),
        entry.name,
      ),
    { timeout: 15_000, what: `the chosen lane ${way}`, soft: true },
  );
  assert(chosen, `the provider picker does not show ${entry.name} as chosen`);
  await win.browser.keys(["Escape"]);
  await waitFor(
    () =>
      exec(
        () =>
          ![...document.querySelectorAll('[data-slot="provider-select"]')].some(
            (el) => el.getClientRects().length > 0,
          ),
      ),
    { timeout: 10_000, what: "the agent settings to close", soft: true },
  );
  line.way = way;
}

// ---------------------------------------------------------------------------
// The run
// ---------------------------------------------------------------------------

/** Open the view `line.id` names by `act` (a real click or key press) and
 * judge it: shown as the window's table says, no refusal toast, nothing
 * handed to the system browser. Records the line whatever happens. */
async function openAndJudge(line, act) {
  try {
    const expected = expectedView(line.id);
    if (!expected)
      assert.fail(`the window table draws no ${line.id}; nothing to expect`);
    // A dialog left over the window would take the click.
    if (await exec(pageDialogShown)) {
      await win.browser.keys(["Escape"]);
      await waitFor(async () => !(await exec(pageDialogShown)), {
        timeout: 10_000,
        what: "the dialog to close",
        soft: true,
      });
    }
    // A toast still shown from the last link must not be read as this one's.
    await waitFor(async () => (await exec(pageToasts)).length === 0, {
      timeout: 12_000,
      what: "the last toast to go",
      soft: true,
    });
    line.toasts_before = await exec(pageToasts);
    line.shown_before = (await exec(pageShown, expected)).shown;
    const clicked = Date.now();
    await act(line);
    const opened = Date.now();
    const refusedOrShown = async () => {
      const toasts = await exec(pageToasts);
      if (toasts.some(refusalOf)) return { shown: false };
      return (await exec(pageShown, expected)).shown ? { shown: true } : null;
    };
    let outcome;
    if (expected.dialog) {
      // The page opens its dialog only once its own read has answered, so
      // the read is waited for first, under the bounds the other UX specs
      // give a page root and a profile's content; then the dialog has
      // DIALOG_AFTER_READ_MS.
      const root = await waitFor(() => exec(pageRootShown, expected.selector), {
        timeout: PAGE_ROOT_MS,
        what: "the profile page",
        soft: true,
      });
      const read =
        root &&
        (await waitFor(() => exec(pageSectionsRendered, expected.selector), {
          timeout: PROFILE_READ_MS,
          what: "the profile page's sections",
          soft: true,
        }));
      line.profile_read_ms = read ? Date.now() - opened : null;
      if (!read) {
        line.toasts = await exec(pageToasts);
        line.refused = line.toasts.map(refusalOf).filter(Boolean);
        assert.deepEqual(line.refused, [], `the window refused ${line.id}`);
        assert.fail(
          `UNMEASURED: the profile page ${root ? "did not render its sections" : "did not show"} within its bound`,
        );
      }
      const readAt = Date.now();
      outcome = await waitFor(refusedOrShown, {
        timeout: DIALOG_AFTER_READ_MS,
        what: `the dialog of ${line.id}`,
        soft: true,
      });
      line.dialog_after_read_ms = outcome?.shown ? Date.now() - readAt : null;
    } else
      outcome = await waitFor(refusedOrShown, {
        timeout: 20_000,
        what: `the view ${line.id}`,
        soft: true,
      });
    // A refusal toast can follow the view a moment later.
    await sleep(800);
    const toasts = await exec(pageToasts);
    line.ms = Date.now() - clicked;
    line.toasts = toasts;
    line.refused = toasts.map(refusalOf).filter(Boolean);
    line.shown = outcome?.shown ?? false;
    if (!line.shown) line.why = (await exec(pageShown, expected)).why;
    line.external = (await callsSince(clicked))
      .filter((call) => call.cmd === "open_external")
      .map((call) => call.cmd);
    assert.deepEqual(line.refused, [], `the window refused ${line.id}`);
    assert.deepEqual(line.external, [], `${line.id} left the window`);
    assert(line.shown, `${line.id} did not open (${line.why ?? "unknown"})`);
    line.verdict = "pass";
  } catch (error) {
    line.error = error.message;
    throw error;
  } finally {
    line.verdict ??= String(line.error ?? "").startsWith("UNMEASURED")
      ? "unmeasured"
      : "fail";
    record(line);
  }
}

// openRailPage (ux-nav.mjs) waits this long for a page root, and UX-10
// (window-ux-audit.test.mjs) this long for the profile's content after it.
const PAGE_ROOT_MS = 20_000;
const PROFILE_READ_MS = 15_000;
const DIALOG_AFTER_READ_MS = 5_000;

/** Whether a shown element matches `selector`. */
function pageRootShown(selector) {
  return [...document.querySelectorAll(selector)].some(
    (el) => el.getClientRects().length > 0,
  );
}

/** Whether the page under `selector` has rendered its sections, which it
 * does once its read answered with data. */
function pageSectionsRendered(selector) {
  return [...document.querySelectorAll(`${selector} [data-section]`)].some(
    (el) => el.getClientRects().length > 0,
  );
}

/** The palette's entries now: how many, and the first one marked. */
function pagePaletteEntry() {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  for (const old of document.querySelectorAll("[data-avl-target]"))
    old.removeAttribute("data-avl-target");
  const options = [
    ...document.querySelectorAll('.palette [role="listbox"] [role="option"]'),
  ].filter((el) => el.getClientRects().length > 0);
  if (options.length === 0) return null;
  options[0].setAttribute("data-avl-target", "1");
  return {
    count: options.length,
    found: options.length === 1,
    label: norm(options[0].textContent),
    disabled: options[0].getAttribute("aria-disabled") === "true",
  };
}

const paletteInput = '.palette [role="combobox"]';

let browserNoteTaken = false;

/** Where the keyboard is, and whether the browser page is shown. */
function pageFocus() {
  const active = document.activeElement;
  const shown = (el) => !!el && el.getClientRects().length > 0;
  return {
    browserShown: shown(document.querySelector("[data-browser-surface]")),
    active: active
      ? `${active.tagName.toLowerCase()}${active.id ? `#${active.id}` : ""}`
      : null,
    inBrowser: !!active?.closest?.("[data-browser-surface]"),
    documentFocused: document.hasFocus(),
  };
}

/** Open the palette with its key, enter `link` and answer its entry, marked
 * as the click target. */
async function pasteInPalette(link, line) {
  const opened = async () =>
    exec(
      (selector) =>
        [...document.querySelectorAll(selector)].some(
          (el) => el.getClientRects().length > 0,
        ),
      paletteInput,
    );
  const pressCtrlK = async () => {
    await win.browser.keys(["Control", "k"]);
    await win.browser.keys(["Control"]);
  };
  // While the browser page is shown, Ctrl+K is pressed once where the focus
  // is, and whether the palette opened is kept as a note, not asserted.
  if (!browserNoteTaken && (await exec(pageFocus)).browserShown) {
    browserNoteTaken = true;
    const focus = await exec(pageFocus);
    await pressCtrlK();
    const reached = await waitFor(opened, {
      timeout: 5_000,
      what: "the palette",
      soft: true,
    });
    record({
      case: "AVL-01-note",
      observation: "ctrl_k_while_browser_page_shown",
      before_link: link,
      focus,
      palette_opened: !!reached,
    });
    if (reached) await win.browser.keys(["Escape"]);
    await waitFor(async () => !(await opened()), {
      timeout: 5_000,
      what: "the palette to close",
      soft: true,
    });
  }
  // Focus goes back to the window by a neutral rail page, so the key
  // reaches the window's own handler.
  await clickSelector(`[data-rail="${line.neutral}"]`);
  await sleep(600);
  line.shown_before = (await exec(pageShown, expectedView(line.id))).shown;
  if (!(await opened())) await pressCtrlK();
  assert(
    await waitFor(opened, {
      timeout: 10_000,
      what: "the palette",
      soft: true,
    }),
    "the palette did not open on Ctrl+K",
  );
  await (await win.browser.$(paletteInput)).setValue(link);
  const entry = await waitFor(() => exec(pagePaletteEntry), {
    timeout: 10_000,
    what: "the palette's entry for the link",
    soft: true,
  });
  return entry ?? { found: false, count: 0, label: null, disabled: null };
}

/** The `views` answer for the whole register, from the package's own
 * cadrumo-mcp over stdio on the run's storage, admitted by the window's
 * sign-in as the agent's tool server is. Never composed here. */
async function mcpViews(line) {
  const host = JSON.parse(process.env.CADRUMO_PERSONA_HOST);
  const executable = join(
    host.package,
    "bin",
    `cadrumo-mcp${process.platform === "win32" ? ".exe" : ""}`,
  );
  const environment = Object.fromEntries(
    Object.entries(process.env).filter(
      ([key]) => !/^(CADRUMO_|PYTHON|VIRTUAL_ENV|UV_)/i.test(key),
    ),
  );
  environment.CADRUMO_STORAGE_ROOT = join(runDir, "storage");
  const errors = openSync(join(runDir, "mcp.stderr.log"), "a", 0o600);
  const child = spawn(executable, ["--surface", "full"], {
    cwd: runDir,
    env: environment,
    stdio: ["pipe", "pipe", errors],
  });
  closeSync(errors);
  line.mcp_pid = child.pid;
  const waiting = new Map();
  let pending = "";
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    pending += chunk;
    let at;
    while ((at = pending.indexOf("\n")) >= 0) {
      const text = pending.slice(0, at).trim();
      pending = pending.slice(at + 1);
      if (!text) continue;
      let message;
      try {
        message = JSON.parse(text);
      } catch {
        continue;
      }
      waiting.get(message.id)?.(message);
      waiting.delete(message.id);
    }
  });
  const exited = new Promise((done) => child.once("exit", done));
  let next = 0;
  const ask = (method, params) =>
    new Promise((done, fail) => {
      next += 1;
      const id = next;
      const timer = setTimeout(() => {
        waiting.delete(id);
        fail(new Error(`cadrumo-mcp did not answer ${method} in 150 s`));
      }, 150_000);
      waiting.set(id, (message) => {
        clearTimeout(timer);
        if (message.error)
          fail(new Error(`${method}: ${JSON.stringify(message.error)}`));
        else done(message.result);
      });
      child.stdin.write(
        `${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`,
      );
    });
  const tool = async (name, args) => {
    const result = await ask("tools/call", { name, arguments: args });
    if (result?.structuredContent) return result.structuredContent;
    const text = result?.content?.find((item) => item.type === "text")?.text;
    return text ? JSON.parse(text) : null;
  };
  try {
    await ask("initialize", {
      protocolVersion: "2025-06-18",
      capabilities: {},
      clientInfo: { name: "cadrumo-ux-agent-view-links", version: "1" },
    });
    child.stdin.write(
      `${JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" })}\n`,
    );
    // Every call first asks the person holding the sign-in to admit this
    // connection. The window shows that ask; it is approved only when it
    // names this very process and image, as the person would check it.
    line.attendance = [];
    let settled = false;
    const call = tool("views", { limit: 50 }).finally(() => {
      settled = true;
    });
    while (!settled) {
      const card = await exec(
        pageMarkAttendance,
        label("desktop.attendance.title"),
        child.pid,
        norm(label("desktop.agent.approval_allow_once")),
      );
      if (card) {
        line.attendance.push(card);
        await clickSelector(TARGET);
      }
      await sleep(1000);
    }
    return await call;
  } finally {
    child.stdin.end();
    const ended = await Promise.race([
      exited.then(() => true),
      sleep(10_000).then(() => false),
    ]);
    // Only the process this test started, by its own handle.
    if (!ended) child.kill();
  }
}

/** The window's attendance ask for the process `pid` of cadrumo-mcp, its
 * allow-once button marked; null while none is shown. */
function pageMarkAttendance(title, pid, allow) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  for (const old of document.querySelectorAll("[data-avl-target]"))
    old.removeAttribute("data-avl-target");
  const asks = [...document.querySelectorAll("aside[aria-label]")].filter(
    (el) =>
      el.getAttribute("aria-label") === title && el.getClientRects().length,
  );
  for (const ask of asks)
    for (const card of ask.querySelectorAll("section.agent-approval")) {
      const text = norm(card.textContent);
      if (!new RegExp(`(^|[^0-9])${pid}([^0-9]|$)`).test(text)) continue;
      if (!/cadrumo-mcp(\.exe)?(\s|$)/i.test(text)) continue;
      const button = [...card.querySelectorAll("button")].find(
        (el) => el.getClientRects().length && norm(el.textContent) === allow,
      );
      if (!button) return { pid, choice: null };
      button.setAttribute("data-avl-target", "1");
      return { pid, choice: "allow_once" };
    }
  return null;
}

// No backticks, brackets or other Markdown: the person's turn is matched by
// the words it shows.
const MESSAGE =
  "Call the Cadrumo views tool exactly once, with limit 50 and no query, id or link, so that it lists every view. " +
  "Then reply with one Markdown link per view it returned, one per line: the link text is the view's label " +
  "and the link target is the row's link field, copied exactly. Write no other links and compose none yourself.";

let runDir;
let results;
let credentialsBefore = null;
let credentialError = null;
const run = { lane: null, links: null, unmeasured: null };

function record(line) {
  appendFileSync(results, `${JSON.stringify(line)}\n`);
  console.info(JSON.stringify(line));
}

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-view-links-")), "run");
  results = join(runDir, "agent-view-links.jsonl");
  try {
    credentialsBefore = credentialCounts();
  } catch (error) {
    credentialError = error.message;
  }
  await start(runDir);
  await dismissSetup();
});
after(async () => {
  if (!win.closed) await teardown();
});

test("AVL-00 the run drives the freshly staged host", () => {
  const line = { case: "AVL-00", exe_sha256: runIdentity.exeSha256 };
  try {
    assert.equal(runIdentity.error, null, runIdentity.error ?? "");
    assert.ok(
      STAGED_SHA256,
      "CADRUMO_UX_STAGED_SHA256 names no freshly staged host",
    );
    assert.equal(runIdentity.exeSha256?.toLowerCase(), STAGED_SHA256);
    line.verdict = "pass";
  } finally {
    line.verdict ??= "fail";
    record(line);
  }
});

test(
  "AVL-01 the packaged MCP service's views rows are the register's window views, and each row's link opens its view",
  { timeout: 1_800_000 },
  async (t) => {
    const line = {
      case: "AVL-01",
      gui: [...GUI_IDS],
      not_gui: [...NOT_GUI_IDS],
    };
    let rows = [];
    try {
      assert.ok(GUI_IDS.size > 0, "the register gives the window no element");
      for (const id of NEVER_DRAWN)
        assert.ok(
          !GUI_IDS.has(id),
          `the register still gives the window ${id}, which it never draws`,
        );
      const unmapped = [...GUI_IDS].filter((id) => !expectedView(id));
      assert.deepEqual(unmapped, [], "gui ids the window table does not draw");
      const answer = await mcpViews(line);
      line.mcp_outcome = answer?.outcome ?? null;
      line.mcp_code = answer?.code ?? null;
      line.mcp_total = answer?.total ?? null;
      assert.equal(
        answer?.outcome,
        "found",
        `the packaged MCP service did not answer views (${answer?.code ?? "no code"})`,
      );
      rows = answer.views;
      const ids = rows.map((row) => row.id);
      line.rows = rows.map((row) => ({
        id: row.id,
        surfaces: row.surfaces,
        link: row.link,
      }));
      line.missing = [...GUI_IDS].filter((id) => !ids.includes(id));
      line.extra = ids.filter((id) => !GUI_IDS.has(id));
      line.never_drawn = ids.filter((id) => NEVER_DRAWN.includes(id));
      assert.deepEqual(
        line.never_drawn,
        [],
        "the service advertises views the window never draws",
      );
      assert.deepEqual(
        line.extra,
        [],
        "rows the register gives no window view",
      );
      assert.deepEqual(line.missing, [], "window views the service omits");
      assert.equal(answer.total, rows.length, "the rows were paged short");
      line.verdict = "pass";
    } finally {
      line.verdict ??= "fail";
      record(line);
    }
    assert(
      await exec(pageTimeInvokes),
      "the window's host calls are not timed",
    );
    // The row's link exactly as the service served it, entered where a person
    // pastes a link: the palette, which opens it through the window's navigator.
    for (const row of rows)
      await t.test(`the served link to ${row.id} opens it`, () =>
        openAndJudge(
          { case: "AVL-01", id: row.id, href: row.link, through: "palette" },
          async (line) => {
            // A rail page the link does not open, to put focus back.
            line.neutral =
              expectedView(row.id)?.selector === PAGE_ROOT.calendar
                ? "declarations"
                : "calendar";
            const entry = await pasteInPalette(row.link, line);
            line.palette_entry = entry.label;
            assert(
              entry.found,
              `the palette offered ${entry.count} entries for the link`,
            );
            line.palette_refused = entry.disabled;
            assert(
              !entry.disabled,
              `the palette refuses the link: ${entry.label}`,
            );
            await clickSelector(TARGET);
          },
        ),
      );
  },
);

test(
  "AVL-02 a ready lane's agent answers with exactly the register's window links",
  { timeout: PERSON_MS + REPLY_MS + 300_000 },
  async () => {
    const line = { case: "AVL-02", durations_ms: {} };
    try {
      const found = await findReadyLane(line);
      if (!found.lane) {
        run.unmeasured = found.reason;
        assert.fail(`UNMEASURED: ${found.reason}`);
      }
      run.lane = `${found.lane.provider}/${found.lane.transport}`;
      await newConversationOn(line, run.lane);

      const words = agentWords();
      const field = await waitFor(
        async () =>
          (await exec(pageMarkComposer, "field", words, "")) === "marked",
        { timeout: 30_000, what: "the composer's message field", soft: true },
      );
      if (!field)
        assert.fail("UNMEASURED: the composer offers no message field");
      await (await win.browser.$(TARGET)).setValue(MESSAGE);
      const sendable = await waitFor(
        async () =>
          (await exec(pageMarkComposer, "send", words, "")) === "marked",
        { timeout: 15_000, what: "the send button", soft: true },
      );
      assert(sendable, "the composer does not offer Send for the message");
      const sent = Date.now();
      await clickSelector(TARGET);
      const approvals = [];
      const settled = await waitFor(
        async () => {
          const card = await exec(
            pageApproval,
            "views",
            norm(label("desktop.agent.approval_allow_once")),
            norm(label("desktop.agent.approval_reject_once")),
          );
          if (card?.choice) {
            approvals.push(card);
            await clickSelector(TARGET);
            return null;
          }
          const read = await exec(pageReply, MESSAGE, words);
          if (!read.found || !read.asked) return null;
          const states = read.replies.map((item) => item.state);
          if (states.includes("failed")) return { ...read, states };
          return !read.running &&
            read.replies.length > 0 &&
            states.every((state) => state === "done")
            ? { ...read, states }
            : null;
        },
        { timeout: REPLY_MS, what: "the agent's settled reply", soft: true },
      );
      line.durations_ms.to_settled = settled ? Date.now() - sent : null;
      line.approvals = approvals;
      const read = settled ?? (await exec(pageReply, MESSAGE, words));
      line.reply_states = (read.replies ?? []).map((item) => item.state);
      assert(settled, `no settled agent reply within ${REPLY_MS / 1000} s`);
      assert(
        !line.reply_states.includes("failed"),
        "the agent's reply was drawn failed",
      );

      const hrefs = read.replies.flatMap((item) => item.links);
      const ids = [];
      const foreign = [];
      for (const href of hrefs) {
        const match = /^cadrumo:\/\/view\/([^?#]+)/.exec(href);
        if (match) ids.push(match[1]);
        else foreign.push(href);
      }
      const unique = new Set(ids);
      line.links = hrefs;
      line.duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
      line.missing = [...GUI_IDS].filter((id) => !unique.has(id));
      line.extra = [...unique].filter((id) => !GUI_IDS.has(id));
      line.not_gui = [...unique].filter((id) => NOT_GUI_IDS.has(id));
      line.foreign = foreign;
      run.links = [...new Set(hrefs.filter((href) => !foreign.includes(href)))];
      assert.deepEqual(
        line.not_gui,
        [],
        "the agent was handed views the window does not draw",
      );
      assert.deepEqual(
        line.extra,
        [],
        "links to ids the register gives no window view",
      );
      assert.deepEqual(
        line.missing,
        [],
        "window views the agent was not handed",
      );
      assert.deepEqual(foreign, [], "cadrumo links that are not view links");
      line.verdict = "pass";
    } finally {
      line.verdict ??= run.unmeasured ? "unmeasured" : "fail";
      record(line);
    }
  },
);

test(
  "AVL-03 each view link in the agent's reply opens its view in the window with no refusal",
  { timeout: 1_800_000 },
  async (t) => {
    if (!run.links?.length)
      assert.fail(
        `UNMEASURED: the reply carried no view link to click (${run.unmeasured ?? "AVL-02 did not settle a reply"})`,
      );
    const words = agentWords();
    assert(
      await exec(pageTimeInvokes),
      "the window's host calls are not timed",
    );
    for (const href of run.links) {
      const id = /^cadrumo:\/\/view\/([^?#]+)/.exec(href)[1];
      await t.test(`the reply's link to ${id} opens it`, () =>
        openAndJudge({ case: "AVL-03", id, href }, async () => {
          assert(await showAgentColumn(), "the agent column is not shown");
          assert(
            await exec(pageMarkLink, MESSAGE, words, href),
            "the reply no longer draws the link",
          );
          await clickSelector(TARGET);
        }),
      );
    }
  },
);

test("AVL-99 the run signs out and leaves no credential-store target", async (t) => {
  let teardownError = null;
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
  record({
    case: "AVL-99",
    lane: run.lane,
    before: credentialsBefore,
    after: counts,
    teardown_error: teardownError,
  });
  assert.equal(teardownError, null, `teardown: ${teardownError}`);
  if (process.platform !== "win32") {
    t.skip("the credential store is counted on Windows only");
    return;
  }
  assert.equal(credentialError, null, `cmdkey: ${credentialError}`);
  for (const kind of ["profileSession", "cadrumo", "provider"])
    assert(
      counts[kind] <= credentialsBefore[kind],
      `the run left ${counts[kind] - credentialsBefore[kind]} more ${kind} credential-store target(s)`,
    );
});
