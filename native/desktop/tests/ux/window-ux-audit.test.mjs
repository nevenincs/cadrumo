// UX audit of the packaged native window. Each test asserts the behaviour a
// person expects and fails on the defect recorded under the same UX id in
// WINDOW-UX-DEFECTS.md. One window serves the whole file; each test sets up
// the screen it needs and leaves the window open for the next.
//
// Environment: as ../personas/window-persona.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG), plus
//   CADRUMO_UX_RUN   the run directory the window's storage is copied into
//                    (must be outside the git project; default: a temp dir)
//   CADRUMO_UX_ONLY  (optional) substring: run only tests whose name has it
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import {
  clickSelector,
  clickText,
  exec,
  label,
  pageErrors,
  pageGeometry,
  paneAudit,
  setSize,
  sleep,
  start,
  teardown,
  waitFor,
  win,
} from "./ux-driver.mjs";
import {
  chooseTab,
  closeSettings,
  openDeclaration,
  openLedgerSection,
  openRailPage,
  pageNow,
  pageScrollContainers,
  paneToggleState,
  setPaneToggle,
  tablist,
  wheelContainer,
} from "./ux-nav.mjs";

const ONLY = process.env.CADRUMO_UX_ONLY;
let world;
const DEFAULT_SIZE = [1441, 923];

before(async () => {
  const runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-ux-")), "run");
  ({ world } = await start(runDir));
  await setSize(...DEFAULT_SIZE);
});
after(teardown);

const ux = (name, fn) =>
  test(name, { skip: ONLY && !name.includes(ONLY), timeout: 600_000 }, fn);

const rowOf = (modelo) =>
  world.rows.find((r) => r.modelo === modelo && r.prepared);

/** Open the declaration of `modelo` on the form view at the default size. */
async function open(modelo) {
  await setSize(...DEFAULT_SIZE);
  const open = await exec(
    () => !!document.querySelector("section.declarations-workspace header h1"),
  );
  if (open) {
    const same = await exec(
      (m) =>
        (
          document.querySelector("section.declarations-workspace header")
            ?.textContent ?? ""
        ).includes(m),
      modelo,
    );
    if (same) return;
    await clickText("section.declarations-workspace header", "button", [
      label("workspace.declarations.destination.overview"),
    ]);
    await sleep(1000);
  }
  await openDeclaration(rowOf(modelo));
}

/** Geometry of the open declaration workspace, from the page. */
const workspaceGeometry = () =>
  exec(() => {
    const rect = (e) => {
      const b = e.getBoundingClientRect();
      return {
        left: b.left,
        top: b.top,
        right: b.right,
        bottom: b.bottom,
        height: b.height,
      };
    };
    const section = document.querySelector("section.declarations-workspace");
    if (!section) return null;
    const header = section.querySelector("header");
    const tabs = section.querySelector('[role="tablist"]');
    const form = section.querySelector("[data-modelo-form]");
    return {
      viewport: [innerWidth, innerHeight],
      section: rect(section),
      sectionScrollTop: section.scrollTop,
      sectionOverflowY: getComputedStyle(section).overflowY,
      header: header && rect(header),
      tabs: tabs && rect(tabs),
      form: form && {
        ...rect(form),
        scrollHeight: form.scrollHeight,
        clientHeight: form.clientHeight,
      },
    };
  });

ux(
  "UX-01 declaration form keeps a usable height beside the prior-values offer",
  async () => {
    await open("100");
    await sleep(1500);
    const g = await workspaceGeometry();
    assert(g?.form, "the form of the open declaration is drawn");
    const room = g.section.bottom - g.section.top;
    assert(
      g.form.clientHeight >= Math.min(200, room / 3),
      `the form shows ${g.form.clientHeight}px of a ${Math.round(room)}px pane ` +
        `(form scrollHeight ${g.form.scrollHeight}); the prior-values offer takes the rest`,
    );
  },
);

ux("UX-02 declaration header and view tabs stay in view", async () => {
  await open("100");
  await sleep(1500);
  const g = await workspaceGeometry();
  assert(g?.header, "the declaration header is drawn");
  assert(
    g.header.top >= g.section.top - 1 && g.tabs.top >= g.section.top - 1,
    `header top ${Math.round(g.header.top)}px and tabs top ${Math.round(g.tabs.top)}px ` +
      `are above the pane top ${Math.round(g.section.top)}px; the pane (overflow-y ` +
      `${g.sectionOverflowY}) is scrolled by ${Math.round(g.sectionScrollTop)}px`,
  );
});

const SECTION = "section.declarations-workspace";
const VIEWS = `${SECTION} [role="tablist"]`;

/** Collapse the prior-values offer when it is open, so later checks measure other causes. */
async function hidePriorValues() {
  await clickText("section[data-prior-values]", "button", ["Ocultar"]).catch(
    () => false,
  );
  await sleep(500);
}

ux(
  "UX-03 the hidden prior-values offer stays hidden after a view change",
  async () => {
    await open("100");
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    await hidePriorValues();
    const listed = () =>
      exec(
        () => document.querySelectorAll("section[data-prior-values] li").length,
      );
    assert.equal(await listed(), 0, "the offer is collapsed after Ocultar");
    await chooseTab(VIEWS, label("workspace.modelo.step.review"));
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    assert.equal(
      await listed(),
      0,
      "the offer the person hid is open again after switching to Comprobar and back",
    );
  },
);

for (const [width, height] of [
  [1280, 800],
  [1024, 640],
  [900, 600],
]) {
  ux(`UX-04 form keeps room to work at ${width}x${height}`, async () => {
    await open("100");
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    await setSize(width, height);
    await hidePriorValues();
    const g = await workspaceGeometry();
    const pane = g.section.bottom - g.section.top;
    assert(
      g.form.clientHeight >= 150,
      `form scroller is ${g.form.clientHeight}px high (scrollHeight ${g.form.scrollHeight}) in a ` +
        `${Math.round(pane)}px pane at ${g.viewport.join("x")}; the header, tabs, notices and ` +
        `details panel are fixed and take the rest`,
    );
    await setSize(...DEFAULT_SIZE);
  });
}

ux(
  "UX-05 the details and side panels beside the form can be resized",
  async () => {
    await open("100");
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    await hidePriorValues();
    const handles = await exec(
      (sel) =>
        [...document.querySelectorAll(`${sel} [role="separator"]`)].filter(
          (e) => e.getClientRects().length > 0,
        ).length,
      SECTION,
    );
    assert(
      handles >= 1,
      `no resize handle (role=separator) in the workspace: ${handles}`,
    );
  },
);

ux(
  "UX-06 the side panel (to do and outline) stays reachable in a narrow pane",
  async () => {
    await open("100");
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    await setSize(900, 600);
    try {
      const reachable = await exec(
        (sel, name) => {
          const side = document.querySelector(
            `${sel} aside[aria-label=${JSON.stringify(name)}]`,
          );
          const shown = !!side && side.getClientRects().length > 0;
          const opener = [...document.querySelectorAll(`${sel} button`)].some(
            (b) =>
              b.getClientRects().length > 0 &&
              (b.getAttribute("aria-label") ?? "").includes(name),
          );
          return {
            shown,
            opener,
            display: side && getComputedStyle(side).display,
          };
        },
        SECTION,
        label("desktop.modelo.side.label"),
      );
      assert(
        reachable.shown || reachable.opener,
        `the "${label("desktop.modelo.side.label")}" panel is display:${reachable.display} at 900x600 ` +
          `and no control opens it`,
      );
    } finally {
      await setSize(...DEFAULT_SIZE);
    }
  },
);

ux("UX-07 form page tabs are named in words, not registry paths", async () => {
  await open("100");
  await chooseTab(VIEWS, label("desktop.modelo.view.form"));
  const names = await exec((name) => {
    const list = document.querySelector(
      `[role="tablist"][aria-label=${JSON.stringify(name)}]`,
    );
    return [...(list?.querySelectorAll('[role="tab"]') ?? [])].map((t) =>
      (t.textContent ?? "").replace(/\s+/g, " ").trim(),
    );
  }, label("desktop.modelo.form.pages"));
  assert(names.length > 0, "the form offers page tabs");
  const raw = names.filter((n) => /[a-z][A-Z]|\w\/\w/.test(n));
  assert.deepEqual(
    raw,
    [],
    `page tabs named by registry path: ${raw.join(" | ")}`,
  );
});

// ---------------------------------------------------------------------------
// Rail pages: resize and clipping. Each probe reports what it measured as a
// test diagnostic (one JSON object per page, probe and size) and asserts
// nothing: a defect is read from the report, and a page the probe cannot reach
// is reported as not reached with the reason.
// ---------------------------------------------------------------------------

const AUDIT_SIZES = [DEFAULT_SIZE, [1280, 800], [1024, 640], [900, 600]];

const report = (t, record) => t.diagnostic(JSON.stringify(record));

/** Measure the page now drawn and report it. */
async function measure(t, page, size, root, options) {
  const audit = await exec(paneAudit, root, options);
  const errors = await exec(pageErrors);
  const geometry = await exec(pageGeometry);
  report(t, {
    page,
    size,
    reached: true,
    audit,
    error: {
      boundary: errors.boundary,
      crash: errors.crash,
      empty: errors.empty,
    },
    geometry: {
      docScroll: geometry.docScroll,
      unreachable: geometry.unreachable.length,
      unreachableFirst: geometry.unreachable.slice(0, 5),
      overflowHidden: geometry.overflowHidden.length,
    },
  });
}

/** Run `probe(size)` at each audit size; a throw is reported as not reached. */
async function atSizes(t, page, probe) {
  try {
    for (const size of AUDIT_SIZES) {
      const inner = await setSize(...size);
      try {
        await probe(inner);
      } catch (error) {
        report(t, {
          page,
          size: inner,
          reached: false,
          reason: `probe failed: ${error.message}`,
        });
      }
    }
  } finally {
    await setSize(...DEFAULT_SIZE);
  }
}

/** Open a rail page and measure it; report why when it cannot be reached. */
const pageProbe = (t, page, id, root, options, attr) =>
  atSizes(t, page, async (size) => {
    const got = await openRailPage(id, root, attr);
    if (!got.reached)
      return report(t, { page, size, reached: false, reason: got.reason });
    await sleep(700);
    await measure(t, page, size, root, options);
  });

// The ids are the section tokens of the ledger's locale keys
// (desktop.ledger.section.<id>); the words come from label().
const LEDGER_TABS = ["movements", "invoices", "documents", "assets"];
const LEDGER_SETUP = ["rules", "registers", "health"];

ux(
  "UX-08 ledger sections keep their header and scroller at each size",
  async (t) => {
    await atSizes(t, "ledger", async (size) => {
      const got = await openRailPage("ledger", "section.ledger-page");
      if (!got.reached) {
        report(t, { page: "ledger", size, reached: false, reason: got.reason });
        return;
      }
      for (const id of [...LEDGER_TABS, ...LEDGER_SETUP]) {
        const page = `ledger/${id}`;
        const opened = await openLedgerSection(
          id,
          LEDGER_SETUP.includes(id) ? LEDGER_SETUP : null,
        );
        if (!opened.reached) {
          report(t, { page, size, reached: false, reason: opened.reason });
          continue;
        }
        await sleep(700);
        await measure(t, page, size, "section.ledger-page");
      }
    });
  },
);

ux("UX-09 profile keeps its header and scroller at each size", async (t) => {
  await pageProbe(t, "profile", "profile", "section.user-profile-page");
});

ux(
  "UX-10 profile household stays inside the profile pane at each size",
  async (t) => {
    await atSizes(t, "profile/household", async (size) => {
      const got = await openRailPage("profile", "section.user-profile-page");
      if (!got.reached) {
        report(t, {
          page: "profile/household",
          size,
          reached: false,
          reason: got.reason,
        });
        return;
      }
      const found = await waitFor(
        () => exec(() => !!document.querySelector("[data-household]")),
        { timeout: 15_000, what: "the household", soft: true },
      );
      if (!found) {
        report(t, {
          page: "profile/household",
          size,
          reached: false,
          reason:
            "no [data-household]: the host offers no profile companions, a detail search is " +
            "active, or the profile has not loaded",
        });
        return;
      }
      await exec(() =>
        document
          .querySelector("[data-household]")
          ?.scrollIntoView({ block: "end" }),
      );
      await sleep(700);
      await measure(t, "profile/household", size, "[data-household]");
    });
  },
);

ux(
  "UX-11 settings popover keeps its header and fits the window at each size",
  async (t) => {
    await atSizes(t, "settings", async (size) => {
      try {
        const got = await openRailPage(
          "settings",
          ".settings",
          "aria-expanded",
        );
        if (!got.reached) {
          report(t, {
            page: "settings",
            size,
            reached: false,
            reason: got.reason,
          });
          return;
        }
        await sleep(700);
        await measure(t, "settings", size, ".settings", {
          header: ".settings h2",
        });
      } finally {
        await closeSettings();
      }
    });
  },
);

ux("UX-12 AEAT sync keeps its header and scroller at each size", async (t) => {
  await pageProbe(t, "aeat-sync", "aeat-sync", "section.aeat-sync-page");
});

ux("UX-13 back and forward move between the pages visited", async (t) => {
  await setSize(...DEFAULT_SIZE);
  const sequence = [
    ["ledger", "section.ledger-page"],
    ["profile", "section.user-profile-page"],
    ["aeat-sync", "section.aeat-sync-page"],
  ];
  const visited = [];
  for (const [id, root] of sequence) {
    const got = await openRailPage(id, root);
    await sleep(700);
    visited.push({ id, ...got, shown: await exec(pageNow) });
  }
  report(t, { probe: "history", step: "visited", visited });

  const step = async (how, act) => {
    const before = await exec(pageNow);
    let reason = null;
    try {
      await act();
    } catch (error) {
      reason = `${how} not done: ${error.message}`;
    }
    await sleep(1000);
    const after = await exec(pageNow);
    report(t, {
      probe: "history",
      how,
      before,
      after,
      changed: JSON.stringify(before) !== JSON.stringify(after),
      reason,
    });
  };
  const blur = () => exec(() => document.activeElement?.blur?.());
  const chord = (key) => async () => {
    await blur();
    await win.browser.keys(["Alt", key]);
  };
  // The shell binds the pointer's side buttons on the window's mouseup.
  const side = (button) => () =>
    exec((button) => {
      document.body.dispatchEvent(
        new MouseEvent("mouseup", { button, bubbles: true, cancelable: true }),
      );
    }, button);

  // The shell never moves the document's own history (that would unload the
  // window), so it is called only where it cannot leave the page.
  const documentLength = await exec(() => history.length);
  const documentHistory = (call) => async () => {
    if (documentLength > 1 && !process.env.CADRUMO_UX_DOCUMENT_HISTORY)
      throw new Error(
        `history.length is ${documentLength}; set CADRUMO_UX_DOCUMENT_HISTORY to call it`,
      );
    await exec((call) => history[call](), call);
  };
  await step("history.back()", documentHistory("back"));
  await step("history.forward()", documentHistory("forward"));
  await step("Alt+ArrowLeft", chord("ArrowLeft"));
  await step("Alt+ArrowLeft again", chord("ArrowLeft"));
  await step("Alt+ArrowRight", chord("ArrowRight"));
  await step("pointer back button", side(3));
  await step("pointer forward button", side(4));
});

// ---------------------------------------------------------------------------
// Modelo header, rail reach, details arrangement and field labels. Each check
// reports what it measured as a test diagnostic and then asserts, in one
// closing assert that names the defect.
// ---------------------------------------------------------------------------

const NEXT_ACTIONS = [
  "fill",
  "confirm",
  "resolve",
  "export",
  "export_again",
  "record_after_file",
  "calculate",
  "recalculate",
  "verify",
  "apply",
  "add_receipt",
];

/** Sample the declaration header on every mutation and every 10 ms, in the page. */
function pageStartHeaderSampler(nextLabels, busyText) {
  const state = {
    samples: 0,
    busy: 0,
    busyWithNext: 0,
    nextShown: 0,
    ariaBusy: 0,
    examples: [],
  };
  const sample = () => {
    const header = document.querySelector(
      "section.declarations-workspace header",
    );
    if (!header) return;
    const norm = (t) => (t ?? "").replace(/\s+/g, " ").trim();
    const next = [...header.querySelectorAll("button")]
      .filter((b) => b.getClientRects().length > 0)
      .map((b) => norm(b.textContent))
      .filter((text) => nextLabels.includes(text));
    const busy = [...header.querySelectorAll('[role="status"]')].some(
      (e) =>
        e.getClientRects().length > 0 && norm(e.textContent).includes(busyText),
    );
    const ariaBusy = header.querySelectorAll('[aria-busy="true"]').length;
    state.samples += 1;
    if (busy) state.busy += 1;
    if (next.length > 0) state.nextShown += 1;
    if (ariaBusy > 0) state.ariaBusy += 1;
    if (busy && next.length > 0) {
      state.busyWithNext += 1;
      if (state.examples.length < 5) state.examples.push({ next, ariaBusy });
    }
  };
  const observer = new MutationObserver(sample);
  const header = document.querySelector(
    "section.declarations-workspace header",
  );
  if (header)
    observer.observe(header, {
      subtree: true,
      childList: true,
      attributes: true,
      characterData: true,
    });
  state.timer = setInterval(sample, 10);
  state.observer = observer;
  window.__uxHeaderSampler = state;
}

/** Stop the sampler and answer its counts. */
function pageStopHeaderSampler() {
  const state = window.__uxHeaderSampler;
  if (!state) return null;
  clearInterval(state.timer);
  state.observer.disconnect();
  delete window.__uxHeaderSampler;
  const { samples, busy, busyWithNext, nextShown, ariaBusy, examples } = state;
  return { samples, busy, busyWithNext, nextShown, ariaBusy, examples };
}

ux(
  "UX-14 the Modelo header shows busy and no stale next step while the form is re-read",
  async (t) => {
    await open("100");
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    const nextLabels = NEXT_ACTIONS.map((action) =>
      label(`workspace.modelo.next_button.${action}`),
    );
    await exec(
      pageStartHeaderSampler,
      nextLabels,
      label("desktop.navigation.busy"),
    );
    let result;
    try {
      // No write is triggered: a view change re-reads the form, and the window's
      // own read of a settled write goes through the same header.
      for (let round = 0; round < 3; round += 1) {
        await chooseTab(VIEWS, label("workspace.modelo.step.review"));
        await chooseTab(VIEWS, label("desktop.modelo.view.form"));
      }
    } finally {
      result = await exec(pageStopHeaderSampler);
    }
    report(t, {
      probe: "modelo-header-reread",
      write: "none triggered",
      ...result,
    });
    assert(result, "the header sampler ran");
    assert.equal(
      result.busyWithNext,
      0,
      `the header offered a next step while it said the window was reading: ` +
        `${result.busyWithNext} of ${result.samples} samples (${result.busy} showed busy)`,
    );
  },
);

const RAIL_PAGES = [
  ["declarations", ".declarations-page, section.declarations-workspace"],
  ["ledger", "section.ledger-page"],
  ["profile", "section.user-profile-page"],
  ["aeat-sync", "section.aeat-sync-page"],
];

/** Rects of the rail's Settings and panel buttons, and its compactness. */
function pageRailReach() {
  const rem =
    parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  const rect = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return {
      left: Math.round(b.left),
      top: Math.round(b.top),
      right: Math.round(b.right),
      bottom: Math.round(b.bottom),
    };
  };
  const inside = (r) =>
    !!r &&
    r.left >= 0 &&
    r.top >= 0 &&
    r.right <= innerWidth &&
    r.bottom <= innerHeight;
  const settings = rect(document.querySelector('[data-rail="settings"]'));
  const panel = rect(document.querySelector('[data-rail="panel"]'));
  const group = document.querySelector(".rail .rail-group");
  return {
    viewport: [innerWidth, innerHeight],
    settings,
    panel,
    settingsInside: inside(settings),
    panelInside: inside(panel),
    compactExpected: innerHeight <= 48 * rem,
    compactObserved: !!group && getComputedStyle(group).rowGap === "0px",
  };
}

/** The agent composer's rect, or null when it is not drawn. */
function pageComposer(name) {
  const box = [...document.querySelectorAll("textarea")].find(
    (e) =>
      e.getAttribute("aria-label") === name && e.getClientRects().length > 0,
  );
  if (!box) return null;
  const b = box.getBoundingClientRect();
  const r = {
    left: Math.round(b.left),
    top: Math.round(b.top),
    right: Math.round(b.right),
    bottom: Math.round(b.bottom),
  };
  return {
    ...r,
    inside:
      r.left >= 0 &&
      r.top >= 0 &&
      r.right <= innerWidth &&
      r.bottom <= innerHeight,
  };
}

ux(
  "UX-15 the rail's last buttons and the agent composer stay inside the window",
  async (t) => {
    const failures = [];
    const agentPressed = () =>
      exec(
        () =>
          document
            .querySelector('[data-rail="agent"]')
            ?.getAttribute("aria-pressed") === "true",
      );
    const agentWasShown = await agentPressed();
    await atSizes(t, "rail", async (size) => {
      const reach = await exec(pageRailReach);
      report(t, { probe: "rail-reach", size, ...reach });
      if (size[0] <= 1024) {
        if (!reach.settingsInside)
          failures.push(`settings outside at ${size.join("x")}`);
        if (!reach.panelInside)
          failures.push(`panel toggle outside at ${size.join("x")}`);
      }
      if (reach.compactExpected !== reach.compactObserved)
        failures.push(
          `rail compact is ${reach.compactObserved} at ${size.join("x")}, expected ${reach.compactExpected}`,
        );
      for (const [id, root] of RAIL_PAGES) {
        const got = await openRailPage(id, root);
        if (!got.reached) {
          report(t, {
            probe: "composer",
            page: id,
            size,
            reached: false,
            reason: got.reason,
          });
          continue;
        }
        await sleep(700);
        const name = label("desktop.agent.message_label");
        let composer = await exec(pageComposer, name);
        let opened = false;
        if (!composer && !(await agentPressed())) {
          await clickSelector('[data-rail="agent"]');
          opened = true;
          await sleep(1200);
          composer = await exec(pageComposer, name);
        }
        report(t, {
          probe: "composer",
          page: id,
          size,
          composer,
          agentOpenedByCheck: opened,
        });
        if (size[0] === 900 && size[1] === 600) {
          if (!composer) failures.push(`no composer on ${id} at 900x600`);
          else if (!composer.inside)
            failures.push(`composer outside on ${id} at 900x600`);
        }
        if (opened && !agentWasShown) {
          await clickSelector('[data-rail="agent"]');
          await sleep(500);
        }
      }
    });
    assert.deepEqual(
      failures,
      [],
      `the rail's Settings or panel toggle, or the agent composer, lies outside the window, or ` +
        `the rail is not compact under 48rem: ${failures.join("; ")}`,
    );
  },
);

/** Geometry of the details pane, the form and their separator, in the page. */
function pageSplit(detailsName, resizeName, formSel) {
  const workspace = "section.declarations-workspace";
  const area = document.querySelector(
    `${workspace} [role=tabpanel][data-details]`,
  );
  const rect = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return {
      left: Math.round(b.left),
      top: Math.round(b.top),
      right: Math.round(b.right),
      bottom: Math.round(b.bottom),
      width: Math.round(b.width),
      height: Math.round(b.height),
    };
  };
  const inside = (r) =>
    !!r &&
    r.left >= 0 &&
    r.top >= 0 &&
    r.right <= innerWidth &&
    r.bottom <= innerHeight;
  const details = [...document.querySelectorAll(`${workspace} aside`)].find(
    (e) => e.getAttribute("aria-label") === detailsName,
  );
  const line = [
    ...document.querySelectorAll(`${workspace} [role="separator"]`),
  ].find((e) => e.getAttribute("aria-label") === resizeName);
  const formBox = document.querySelector(`${workspace} ${formSel}`);
  const d = rect(details);
  const f = rect(formBox);
  return {
    placement: area?.getAttribute("data-details") ?? null,
    orientation: line?.getAttribute("aria-orientation") ?? null,
    valueNow: line?.getAttribute("aria-valuenow") ?? null,
    details: d,
    form: f,
    detailsInside: inside(d),
    formInside: inside(f),
    beside: !!d && !!f && f.right <= d.left + 1,
    under: !!d && !!f && f.bottom <= d.top + 1,
  };
}

const splitNow = () =>
  exec(
    pageSplit,
    label("desktop.modelo.details.label"),
    label("desktop.modelo.details.resize"),
    "[data-modelo-form]",
  );

/** Put the details in `placement` ("side" or "bottom") by the placement toggle. */
async function arrangeDetails(placement) {
  const now = await splitNow();
  if (now.placement === placement) return now;
  await setPaneToggle("placement", placement === "side");
  await sleep(500);
  return splitNow();
}

/** Focus the details separator and send keys to it. */
async function keyLine(...keys) {
  const focused = await exec((name) => {
    const line = [
      ...document.querySelectorAll(
        'section.declarations-workspace [role="separator"]',
      ),
    ].find((e) => e.getAttribute("aria-label") === name);
    line?.focus();
    return document.activeElement === line;
  }, label("desktop.modelo.details.resize"));
  if (!focused) throw new Error("the details separator takes no focus");
  for (const key of keys) await win.browser.keys(key);
  await sleep(500);
}

const extent = (split) =>
  split.placement === "side" ? split.details?.width : split.details?.height;

ux(
  "UX-16 the details sit beside or under the form by a toggle, keep the choice, and resize either way",
  async (t) => {
    await open("100");
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    const failures = [];
    const original = {
      side: await paneToggleState("side"),
      details: await paneToggleState("details"),
      placement: null,
    };
    try {
      assert(original.details !== null, "the form offers a details toggle");
      await setPaneToggle("details", true);
      original.placement = await paneToggleState("placement");
      assert(
        original.placement !== null,
        `no "${label("desktop.modelo.details.beside")}" toggle with the details shown`,
      );

      // Round trip: on, beside; off, stacked; the choice survives leaving the page.
      const on = await arrangeDetails("side");
      report(t, {
        probe: "placement",
        step: "on",
        pressed: await paneToggleState("placement"),
        ...on,
      });
      if (!on.beside || on.placement !== "side")
        failures.push("pressed on, the details are not beside the form");
      const off = await arrangeDetails("bottom");
      report(t, {
        probe: "placement",
        step: "off",
        pressed: await paneToggleState("placement"),
        ...off,
      });
      if (!off.under || off.placement !== "bottom")
        failures.push("pressed off, the details are not under the form");
      await arrangeDetails("side");
      const away = await openRailPage("ledger", "section.ledger-page");
      await sleep(700);
      const back = await openRailPage("declarations", SECTION);
      if (!back.reached) await openDeclaration(rowOf("100"));
      await sleep(1500);
      await chooseTab(VIEWS, label("desktop.modelo.view.form"));
      const kept = await splitNow();
      report(t, {
        probe: "placement",
        step: "after-navigation",
        away,
        ...kept,
      });
      if (kept.placement !== "side")
        failures.push(
          `the choice did not survive leaving the page (${kept.placement})`,
        );

      // Separator travel in both arrangements, rail shown and hidden, at each size.
      for (const size of AUDIT_SIZES) {
        const inner = await setSize(...size);
        for (const railOn of [true, false]) {
          for (const placement of ["side", "bottom"]) {
            const page = `modelo-split/${placement}/rail-${railOn ? "shown" : "hidden"}`;
            try {
              await setPaneToggle("side", railOn);
              await setPaneToggle("details", true);
              await arrangeDetails(placement);
              const start = await splitNow();
              await keyLine("Home");
              const least = await splitNow();
              await keyLine("End");
              const most = await splitNow();
              await keyLine("Home");
              const shrunk = await splitNow();
              const grew = extent(most) > extent(least);
              const shrank = extent(shrunk) < extent(most);
              const inWindow =
                least.detailsInside &&
                least.formInside &&
                most.detailsInside &&
                most.formInside;
              report(t, {
                page,
                size: inner,
                start: extent(start),
                least: extent(least),
                most: extent(most),
                afterHome: extent(shrunk),
                grew,
                shrank,
                inWindow,
                orientation: most.orientation,
                rects: { least, most },
              });
              if (!grew || !shrank)
                failures.push(
                  `${page} at ${inner.join("x")}: separator does not move both ways`,
                );
              if (!inWindow)
                failures.push(
                  `${page} at ${inner.join("x")}: a pane lies outside the window`,
                );
            } catch (error) {
              failures.push(`${page} at ${inner.join("x")}: ${error.message}`);
              report(t, {
                page,
                size: inner,
                reached: false,
                reason: error.message,
              });
            }
          }
        }
      }
    } finally {
      await setSize(...DEFAULT_SIZE);
      if (original.side !== null)
        await setPaneToggle("side", original.side === "true");
      if (original.placement !== null)
        await setPaneToggle("placement", original.placement === "true");
      if (original.details !== null)
        await setPaneToggle("details", original.details === "true");
    }
    assert.deepEqual(
      failures,
      [],
      `the details toggle or its separator fails a person: ${failures.join("; ")}`,
    );
  },
);

/** Widths of the field-row labels of the form drawn, in the page. */
function pageLabelWidths() {
  const widths = [];
  for (const row of document.querySelectorAll(
    "[data-modelo-form] [role=row][data-key]",
  )) {
    if (!row.getClientRects().length) continue;
    const cell = row.querySelector(":scope > [role=gridcell]:nth-child(2)");
    const holder = cell?.querySelector(":scope > span > span.min-w-0") ?? cell;
    if (!holder) continue;
    widths.push(Math.round(holder.getBoundingClientRect().width));
  }
  return widths;
}

ux("UX-17 every field-row label is at least 120 px wide", async (t) => {
  await open("100");
  await chooseTab(VIEWS, label("desktop.modelo.view.form"));
  const narrow = [];
  await atSizes(t, "modelo-field-labels", async (size) => {
    await sleep(500);
    const widths = await exec(pageLabelWidths);
    const min = widths.length ? Math.min(...widths) : null;
    report(t, {
      probe: "field-label-width",
      size,
      rows: widths.length,
      minLabel: min,
    });
    if (widths.length === 0)
      narrow.push(`no field rows measured at ${size.join("x")}`);
    else if (min < 120) narrow.push(`${size.join("x")}: ${min}px`);
  });
  assert.deepEqual(
    narrow,
    [],
    `a field-row label is narrower than 120px (or no row was drawn): ${narrow.join("; ")}`,
  );
});

// ---------------------------------------------------------------------------
// Scrollbars and the mouse wheel; the three pane toggles.
// ---------------------------------------------------------------------------

/**
 * Measure every scroll container under `root` and wheel each one. A container
 * the person can scroll (overflow-y auto or scroll) fails when its content
 * overflows and its scrollbar is not drawn or the wheel does not move it.
 * Containers that clip with overflow-y hidden are reported, not judged: they
 * offer no scrolling by design.
 */
async function auditScrollContainers(t, page, size, root, failures) {
  const found = await exec(pageScrollContainers, root);
  if (!found.found) {
    report(t, {
      probe: "scroll",
      page,
      size,
      reached: false,
      reason: "no root",
    });
    return;
  }
  for (const c of found.containers) {
    const wheel = c.overflows
      ? await wheelContainer(c.id)
      : { moved: null, skipped: "does not overflow" };
    report(t, {
      probe: "scroll",
      page,
      size,
      container: c.el,
      overflowY: c.overflowY,
      overflows: c.overflows,
      scrollHeight: c.scrollHeight,
      clientHeight: c.clientHeight,
      scrollbarVisible: c.barVisible,
      scrollbarNumbers: {
        offsetMinusClient: c.classicWidth,
        scrollbarWidth: c.scrollbarWidth,
        webkitDisplay: c.webkitDisplay,
        webkitWidth: c.webkitWidth,
      },
      wheel,
    });
    if (!c.overflows || !c.scrollable) continue;
    const where = `${page} at ${size.join("x")}: ${c.el}`;
    if (!c.barVisible)
      failures.push(`${where} overflows with no scrollbar drawn`);
    if (!wheel.moved)
      failures.push(
        `${where} did not scroll by wheel${wheel.error ? ` (${wheel.error})` : ""}`,
      );
  }
}

ux(
  "UX-21 every overflowing scroll container shows a scrollbar and scrolls by wheel",
  async (t) => {
    const failures = [];

    await atSizes(t, "profile", async (size) => {
      const got = await openRailPage("profile", "section.user-profile-page");
      if (!got.reached)
        return report(t, {
          page: "profile",
          size,
          reached: false,
          reason: got.reason,
        });
      await sleep(700);
      await auditScrollContainers(
        t,
        "profile",
        size,
        "section.user-profile-page",
        failures,
      );
    });

    await atSizes(t, "ledger", async (size) => {
      const got = await openRailPage("ledger", "section.ledger-page");
      if (!got.reached)
        return report(t, {
          page: "ledger",
          size,
          reached: false,
          reason: got.reason,
        });
      for (const id of [...LEDGER_TABS, ...LEDGER_SETUP]) {
        const page = `ledger/${id}`;
        const opened = await openLedgerSection(
          id,
          LEDGER_SETUP.includes(id) ? LEDGER_SETUP : null,
        );
        if (!opened.reached) {
          report(t, { page, size, reached: false, reason: opened.reason });
          continue;
        }
        await sleep(700);
        await auditScrollContainers(
          t,
          page,
          size,
          "section.ledger-page",
          failures,
        );
      }
    });

    await open("100");
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    await atSizes(t, "modelo", async (size) => {
      await sleep(500);
      await auditScrollContainers(t, "modelo", size, SECTION, failures);
    });

    assert.deepEqual(
      failures,
      [],
      `a container with more content than room shows no scrollbar or ignores the wheel: ${failures.join("; ")}`,
    );
  },
);

const TOGGLES = ["side", "details", "placement"];

/** The three pane toggles now: presence, rect, whether inside the window, icons. */
function pageToggles(names) {
  const out = {};
  for (const name of names) {
    const el = document.querySelector(
      `section.declarations-workspace [data-pane-toggle="${name}"]`,
    );
    if (!el) {
      out[name] = { present: false };
      continue;
    }
    const b = el.getBoundingClientRect();
    const drawn = el.getClientRects().length > 0 && b.width > 0 && b.height > 0;
    out[name] = {
      present: true,
      visible:
        drawn &&
        b.left >= 0 &&
        b.top >= 0 &&
        b.right <= innerWidth &&
        b.bottom <= innerHeight,
      rect: [b.left, b.top, b.right, b.bottom].map(Math.round),
      pressed: el.getAttribute("aria-pressed"),
      icons: [...el.querySelectorAll("[data-icon]")].map((i) =>
        i.getAttribute("data-icon"),
      ),
    };
  }
  return out;
}

/** Report the toggles after `step` and answer the defects found in them. */
async function snapshotToggles(t, size, step, extra = {}) {
  const toggles = await exec(pageToggles, TOGGLES);
  const vanished = TOGGLES.filter((n) => !toggles[n].present);
  const outside = TOGGLES.filter(
    (n) => toggles[n].present && !toggles[n].visible,
  );
  const icons = TOGGLES.filter((n) => toggles[n].present).map((n) => [
    n,
    toggles[n].icons.join("+"),
  ]);
  const repeated = icons
    .filter(([, icon], at) => icons.some(([, o], i) => i !== at && o === icon))
    .map(([n, icon]) => `${n}:${icon}`);
  report(t, {
    probe: "pane-toggles",
    size,
    step,
    ...extra,
    toggles,
    vanished,
    outside,
    repeatedIcons: repeated,
  });
  const where = `${step} at ${size.join("x")}`;
  return [
    ...vanished.map((n) => `${n} toggle vanished after ${where}`),
    ...outside.map((n) => `${n} toggle outside the window after ${where}`),
    ...(repeated.length
      ? [`icons repeated after ${where}: ${repeated.join(", ")}`]
      : []),
  ];
}

ux(
  "UX-19 the three pane toggles stay visible with their own icons and the stacked line moves",
  async (t) => {
    await open("100");
    await chooseTab(VIEWS, label("desktop.modelo.view.form"));
    const failures = [];
    const original = {
      side: await paneToggleState("side"),
      details: await paneToggleState("details"),
      placement: null,
    };
    try {
      await setPaneToggle("details", true);
      original.placement = await paneToggleState("placement");
      for (const size of AUDIT_SIZES) {
        const inner = await setSize(...size);
        const step = async (name, act) => {
          let error = null;
          try {
            await act();
          } catch (failure) {
            error = failure.message;
            failures.push(`${name} at ${inner.join("x")}: ${failure.message}`);
          }
          await sleep(500);
          failures.push(...(await snapshotToggles(t, inner, name, { error })));
        };
        await step("form view", async () => {
          await chooseTab(VIEWS, label("desktop.modelo.view.form"));
          await setPaneToggle("side", true);
          await setPaneToggle("details", true);
        });
        await step("side off", () => setPaneToggle("side", false));
        await step("side on", () => setPaneToggle("side", true));
        await step("details off", () => setPaneToggle("details", false));
        await step("details on", () => setPaneToggle("details", true));
        await step("placement off", () => setPaneToggle("placement", false));
        await step("placement on", () => setPaneToggle("placement", true));
        await step("other view and back", async () => {
          await chooseTab(VIEWS, label("workspace.modelo.step.review"));
          await chooseTab(VIEWS, label("desktop.modelo.view.form"));
        });

        // The stacked line: keyboard Home and End, pane heights before and after.
        try {
          await setPaneToggle("details", true);
          await arrangeDetails("bottom");
          const start = await splitNow();
          await keyLine("Home");
          const least = await splitNow();
          await keyLine("End");
          const most = await splitNow();
          const moved = extent(most) > extent(least);
          report(t, {
            probe: "stacked-separator",
            size: inner,
            placement: most.placement,
            start: extent(start),
            least: extent(least),
            most: extent(most),
            moved,
            orientation: most.orientation,
          });
          if (!moved)
            failures.push(
              `the stacked separator does not move at ${inner.join("x")} ` +
                `(${extent(least)} -> ${extent(most)})`,
            );
        } catch (error) {
          failures.push(
            `stacked separator at ${inner.join("x")}: ${error.message}`,
          );
          report(t, {
            probe: "stacked-separator",
            size: inner,
            reached: false,
            reason: error.message,
          });
        }
      }
    } finally {
      await setSize(...DEFAULT_SIZE);
      await setPaneToggle("details", true);
      if (original.placement !== null)
        await setPaneToggle("placement", original.placement === "true");
      if (original.side !== null)
        await setPaneToggle("side", original.side === "true");
      if (original.details !== null)
        await setPaneToggle("details", original.details === "true");
    }
    assert.deepEqual(
      failures,
      [],
      `the pane toggles fail a person: ${failures.join("; ")}`,
    );
  },
);
