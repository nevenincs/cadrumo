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
  returnDockPane,
  swapDockPane,
  type DockLayout,
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
