import assert from "node:assert/strict";
import test from "node:test";
import {
  emptyHistory,
  recordPosition,
  samePosition,
  stepIndex,
  viewerPosition,
  type ViewerHistory,
  type ViewerPosition,
} from "../../src/shell/navigation/history.ts";
import { positionUnmounts } from "../../src/shell/navigation/windowViews.ts";

// The window's back and forward stack: positions are places only, recorded
// once each, stepped through, and cut where a new place is shown mid-stack.

const at = (
  page: ViewerPosition["page"],
  more: Partial<ViewerPosition> = {},
): ViewerPosition => ({
  page,
  section: null,
  workUnitId: null,
  view: null,
  ...more,
});

const walk = (...positions: ViewerPosition[]): ViewerHistory =>
  positions.reduce(
    (held, position) => recordPosition(held, position),
    emptyHistory<string>(),
  );

const ledger = at("ledger", { section: "movements" });
const list = at("declarations");
const declaration = at("declarations", { workUnitId: "a" });
const check = at("declarations", { workUnitId: "a", view: "check" });

test("a position holds the page, its section, the declaration and its view only", () => {
  const open = { workUnitId: "a", view: "check" };
  assert.deepEqual(viewerPosition("declarations", "movements", open), check);
  // Another page does not carry the declaration the list holds open.
  assert.deepEqual(viewerPosition("ledger", "movements", open), ledger);
  assert.deepEqual(viewerPosition("profile", "invoices", open), at("profile"));
  assert.deepEqual(
    viewerPosition("declarations", "movements", {
      workUnitId: null,
      view: "check",
    }),
    list,
  );
});

test("the same place shown again is recorded once", () => {
  const history = walk(ledger, ledger, list, { ...list });
  assert.equal(history.entries.length, 2);
  assert.equal(history.index, 1);
  assert.ok(samePosition(history.entries[1]!, list));
});

test("back and forward stop at either end", () => {
  const history = walk(ledger, list, declaration);
  assert.equal(stepIndex(history, 1), null);
  assert.equal(stepIndex(history, -1), 1);
  const first = { ...history, index: 0 };
  assert.equal(stepIndex(first, -1), null);
  assert.equal(stepIndex(first, 1), 1);
  assert.equal(stepIndex(emptyHistory(), -1), null);
});

test("stepping back then showing the place stepped to records nothing", () => {
  const history = walk(ledger, list, declaration);
  const back = { ...history, index: 1 };
  assert.equal(recordPosition(back, list), back);
});

test("a new place shown after a step back replaces what lay ahead", () => {
  const history = walk(ledger, list, declaration);
  const next = recordPosition({ ...history, index: 0 }, check);
  assert.deepEqual(next.entries, [ledger, check]);
  assert.equal(next.index, 1);
  assert.equal(stepIndex(next, 1), null);
});

test("the oldest places go first past the limit", () => {
  const pages = ["profile", "calendar", "ledger", "docs"] as const;
  const history = pages
    .map((page) => at(page))
    .reduce(
      (held, position) => recordPosition(held, position, 3),
      emptyHistory<string>(),
    );
  assert.deepEqual(
    history.entries.map((entry) => entry.page),
    ["calendar", "ledger", "docs"],
  );
  assert.equal(history.index, 2);
});

test("a step takes down what any navigation to that place would", () => {
  const unmounted = (from: ViewerPosition, to: ViewerPosition) => [
    ...positionUnmounts(from, to, "movements"),
  ];
  // Leaving one declaration, for its list or another, takes its work down.
  assert.deepEqual(unmounted(declaration, list), ["declarations"]);
  assert.deepEqual(
    unmounted(declaration, at("declarations", { workUnitId: "b" })),
    ["declarations"],
  );
  // A change of view, or coming into a declaration, takes nothing down.
  assert.deepEqual(unmounted(declaration, check), []);
  assert.deepEqual(unmounted(list, declaration), []);
  // Leaving a page takes the page down, and the Ledger its section too.
  assert.deepEqual(unmounted(ledger, list).sort(), [
    "ledger",
    "ledger/movements",
  ]);
  assert.deepEqual(unmounted(ledger, at("ledger", { section: "invoices" })), [
    "ledger/movements",
  ]);
  assert.deepEqual(unmounted(declaration, ledger), ["declarations"]);
});
