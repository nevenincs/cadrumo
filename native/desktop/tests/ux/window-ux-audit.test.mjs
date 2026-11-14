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
  pageGeometry,
  setSize,
  sleep,
  start,
  teardown,
} from "./ux-driver.mjs";
import { chooseTab, openDeclaration, tablist } from "./ux-nav.mjs";

const ONLY = process.env.CADRUMO_UX_ONLY;
let world;
const DEFAULT_SIZE = [1441, 923];

before(async () => {
  const runDir =
    process.env.CADRUMO_UX_RUN ?? join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-ux-")), "run");
  ({ world } = await start(runDir));
  await setSize(...DEFAULT_SIZE);
});
after(teardown);

const ux = (name, fn) =>
  test(name, { skip: ONLY && !name.includes(ONLY), timeout: 600_000 }, fn);

const rowOf = (modelo) => world.rows.find((r) => r.modelo === modelo && r.prepared);

/** Open the declaration of `modelo` on the form view at the default size. */
async function open(modelo) {
  await setSize(...DEFAULT_SIZE);
  const open = await exec(() => !!document.querySelector("section.declarations-workspace header h1"));
  if (open) {
    const same = await exec(
      (m) =>
        (document.querySelector("section.declarations-workspace header")?.textContent ?? "").includes(m),
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
      return { left: b.left, top: b.top, right: b.right, bottom: b.bottom, height: b.height };
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

ux("UX-01 declaration form keeps a usable height beside the prior-values offer", async () => {
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
});

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
  await clickText("section[data-prior-values]", "button", ["Ocultar"]).catch(() => false);
  await sleep(500);
}

ux("UX-03 the hidden prior-values offer stays hidden after a view change", async () => {
  await open("100");
  await chooseTab(VIEWS, label("desktop.modelo.view.form"));
  await hidePriorValues();
  const listed = () =>
    exec(() => document.querySelectorAll("section[data-prior-values] li").length);
  assert.equal(await listed(), 0, "the offer is collapsed after Ocultar");
  await chooseTab(VIEWS, label("workspace.modelo.step.review"));
  await chooseTab(VIEWS, label("desktop.modelo.view.form"));
  assert.equal(
    await listed(),
    0,
    "the offer the person hid is open again after switching to Comprobar and back",
  );
});

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

ux("UX-05 the details and side panels beside the form can be resized", async () => {
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
  assert(handles >= 1, `no resize handle (role=separator) in the workspace: ${handles}`);
});

ux("UX-06 the side panel (to do and outline) stays reachable in a narrow pane", async () => {
  await open("100");
  await chooseTab(VIEWS, label("desktop.modelo.view.form"));
  await setSize(900, 600);
  try {
    const reachable = await exec(
      (sel, name) => {
        const side = document.querySelector(`${sel} aside[aria-label=${JSON.stringify(name)}]`);
        const shown = !!side && side.getClientRects().length > 0;
        const opener = [...document.querySelectorAll(`${sel} button`)].some(
          (b) =>
            b.getClientRects().length > 0 &&
            (b.getAttribute("aria-label") ?? "").includes(name),
        );
        return { shown, opener, display: side && getComputedStyle(side).display };
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
});

ux("UX-07 form page tabs are named in words, not registry paths", async () => {
  await open("100");
  await chooseTab(VIEWS, label("desktop.modelo.view.form"));
  const names = await exec(
    (name) => {
      const list = document.querySelector(`[role="tablist"][aria-label=${JSON.stringify(name)}]`);
      return [...(list?.querySelectorAll('[role="tab"]') ?? [])].map((t) =>
        (t.textContent ?? "").replace(/\s+/g, " ").trim(),
      );
    },
    label("desktop.modelo.form.pages"),
  );
  assert(names.length > 0, "the form offers page tabs");
  const raw = names.filter((n) => /[a-z][A-Z]|\w\/\w/.test(n));
  assert.deepEqual(raw, [], `page tabs named by registry path: ${raw.join(" | ")}`);
});
