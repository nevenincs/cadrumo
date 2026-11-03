import assert from "node:assert/strict";
import { test } from "node:test";
import {
  activateDockPane,
  dockGeometry,
  dockPanes,
  floatDockPane,
  initialDockLayout,
  moveDockPane,
  readDockLayout,
  resizeDockSplit,
  returnDockPane,
  swapDockPane,
  type DockLayout,
  type DockNode,
  type DockPane,
} from "../../src/shell/docking.ts";

const initial = () =>
  initialDockLayout(
    { orientation: "row", order: "docs" },
    { agentRatio: 0.24, splitRatio: 0.56, panelRatio: 0.3, tab: "console" },
  );
const identities = (layout: DockLayout) =>
  [
    ...dockPanes(layout.root),
    ...layout.floating.map((item) => item.pane),
  ].sort();

test("splitting, tabbing, floating and returning move the same six identities", () => {
  let layout = initial();
  const expected = identities(layout);
  for (const side of ["left", "right", "top", "bottom", "tab"] as const) {
    layout = moveDockPane(layout, "console", "docs", side);
    assert.deepEqual(identities(layout), expected);
    layout = swapDockPane(layout, "console");
    layout = floatDockPane(layout, "console");
    layout = floatDockPane(layout, "console");
    assert.equal(layout.floating.length, 1);
    assert.deepEqual(identities(layout), expected);
    layout = returnDockPane(layout, "console");
    assert.deepEqual(identities(layout), expected);
  }
});

test("directional splits place the moved tab on the requested edge", () => {
  for (const side of ["left", "right", "top", "bottom"] as const) {
    const layout = moveDockPane(initial(), "console", "docs", side);
    const { groups } = dockGeometry(layout, ["console", "docs"]);
    const source = groups.find((item) => item.group.active === "console")?.rect;
    const target = groups.find((item) => item.group.active === "docs")?.rect;
    assert.ok(source && target);
    if (side === "left") assert.ok(source.x < target.x);
    if (side === "right") assert.ok(source.x > target.x);
    if (side === "top") assert.ok(source.y < target.y);
    if (side === "bottom") assert.ok(source.y > target.y);
  }
});

test("tabs select a single active pane and hidden branches collapse", () => {
  let layout = moveDockPane(initial(), "tui", "docs", "tab");
  layout = activateDockPane(layout, "docs");
  const { groups, dividers } = dockGeometry(layout, ["docs", "tui"]);
  assert.equal(groups.length, 1);
  assert.equal(dividers.length, 0);
  assert.deepEqual(groups[0]?.group.tabs, ["docs", "tui"]);
  assert.equal(groups[0]?.group.active, "docs");
  assert.deepEqual(groups[0]?.rect, { x: 0, y: 0, width: 1, height: 1 });
  assert.equal(dockGeometry(layout, ["tui"]).groups[0]?.group.active, "tui");
});

test("stored layouts reject foreign identities, duplicate tabs and invalid geometry", () => {
  const restored = readDockLayout({
    version: 1,
    root: {
      kind: "tabs",
      tabs: ["docs", "docs", "secret", "tui"],
      active: "secret",
    },
    floating: [
      { pane: "docs", rect: {} },
      {
        pane: "logs",
        rect: { x: 10, y: -1, width: Number.NaN, height: Infinity },
      },
    ],
  });
  assert.ok(restored);
  assert.deepEqual(identities(restored), ["docs", "logs", "tui"]);
  assert.equal(restored.floating[0]?.rect.x, 0.4);
  assert.equal(restored.floating[0]?.rect.y, 0);
  assert.equal(readDockLayout({ version: 2 }), null);
  assert.deepEqual(readDockLayout(initial()), initial());
});

test("invalid and self drops leave the layout unchanged", () => {
  const layout = floatDockPane(initial(), "docs");
  assert.equal(moveDockPane(layout, "tui", "docs", "tab"), layout);
  assert.equal(moveDockPane(layout, "tui", "tui", "left"), layout);
});

const tab = (pane: DockPane): DockNode => ({
  kind: "tabs",
  tabs: [pane],
  active: pane,
});
const pair = (
  first: DockNode,
  second: DockNode,
  axis: "row" | "column" = "row",
  ratio = 0.7,
): DockNode => ({ kind: "split", axis, ratio, first, second });
const tree = (root: DockNode): DockLayout => ({
  version: 1,
  root,
  floating: [],
  closed: [],
});
const fit = { width: 1200, minimumWidths: { agent: 240, docs: 900 } };

test("temporary width fitting restores the preference and respects later explicit resizing", () => {
  const layout = tree(pair(tab("agent"), tab("docs")));
  const before = structuredClone(layout);
  assert.equal(
    dockGeometry(layout, ["agent", "docs"], fit).dividers[0]?.ratio,
    0.25,
  );
  assert.deepEqual(layout, before);
  assert.equal(dockGeometry(layout, ["agent", "docs"]).dividers[0]?.ratio, 0.7);
  const resized = resizeDockSplit(layout, "", 0.22);
  assert.equal(
    dockGeometry(resized, ["agent", "docs"], fit).dividers[0]?.ratio,
    0.22,
  );
  assert.equal(
    dockGeometry(resized, ["agent", "docs"]).dividers[0]?.ratio,
    0.22,
  );
});

test("fitting follows swapped and stacked groups", () => {
  const swapped = dockGeometry(
    tree(pair(tab("docs"), tab("agent"), "row", 0.3)),
    ["agent", "docs"],
    fit,
  );
  assert.equal(swapped.dividers[0]?.ratio, 0.75);
  const stacked = dockGeometry(
    tree(pair(tab("docs"), tab("agent"), "column")),
    ["agent", "docs"],
    fit,
  );
  assert.equal(stacked.dividers[0]?.ratio, 0.7);
  assert.ok(stacked.groups.every((group) => group.rect.width === 1));
});

test("nested row minima reserve room through ancestors while column minima share width", () => {
  const layout = tree(
    pair(
      tab("agent"),
      pair(tab("docs"), pair(tab("tui"), tab("logs"), "column"), "row", 0.8),
      "row",
      0.5,
    ),
  );
  const fitted = dockGeometry(layout, ["agent", "docs", "tui", "logs"], {
    width: 1500,
    minimumWidths: { agent: 240, docs: 700, tui: 250, logs: 300 },
  });
  for (const [pane, required] of [
    ["agent", 240],
    ["docs", 700],
    ["tui", 250],
    ["logs", 300],
  ] as const) {
    const group = fitted.groups.find((item) => item.group.active === pane)!;
    assert.ok(group.rect.width * 1500 >= required - 1e-9, pane);
  }
  for (const divider of fitted.dividers) {
    assert.ok(
      divider.minRatio <= divider.ratio && divider.ratio <= divider.maxRatio,
    );
  }
});

test("inactive tabs, hidden branches and floating panes impose no width requirement", () => {
  const layout = tree(
    pair(tab("agent"), { kind: "tabs", tabs: ["docs", "tui"], active: "tui" }),
  );
  assert.equal(
    dockGeometry(layout, ["agent", "docs", "tui"], fit).dividers[0]?.ratio,
    0.7,
  );
  const active = activateDockPane(layout, "docs");
  assert.equal(
    dockGeometry(active, ["agent", "docs", "tui"], fit).dividers[0]?.ratio,
    0.25,
  );
  assert.equal(
    dockGeometry(active, ["agent", "tui"], fit).dividers[0]?.ratio,
    0.7,
  );
  const floating = floatDockPane(active, "docs");
  assert.equal(
    dockGeometry(floating, ["agent", "docs", "tui"], fit).dividers[0]?.ratio,
    0.7,
  );
  assert.deepEqual(
    dockGeometry(floating, ["agent", "docs", "tui"], fit).groups.find(
      (item) => item.group.active === "docs",
    )?.rect,
    undefined,
  );
});

test("infeasible widths retain the arrangement and exact fits keep valid divider bounds", () => {
  const layout = tree(pair(tab("agent"), tab("docs")));
  const narrow = dockGeometry(layout, ["agent", "docs"], {
    ...fit,
    width: 800,
  });
  assert.equal(narrow.dividers[0]?.ratio, 0.7);
  const exact = dockGeometry(layout, ["agent", "docs"], {
    width: 1000,
    minimumWidths: { agent: 323, docs: 677 },
  }).dividers[0]!;
  assert.ok(exact.minRatio <= exact.ratio && exact.ratio <= exact.maxRatio);
  assert.ok(Math.abs(exact.ratio - 0.323) < 1e-9);
});
