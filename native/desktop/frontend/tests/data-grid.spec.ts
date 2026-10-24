import { expect, test } from "@playwright/test";
import {
  APPLE,
  cellBox,
  columnLayout,
  commitKeyOf,
  displayOrder,
  dropColumn,
  edgeRow,
  exactly,
  inBox,
  isPrintable,
  isShellChord,
  lengthPx,
  nextRow,
  prefixSums,
  rangeOf,
  rowAt,
  scrollToAlign,
  scrollToReveal,
  selectAll,
  selectionExtent,
  selectOnly,
  selectRange,
  stepColumn,
  toggleKey,
  visibleRange,
  type KeyPress,
} from "../src/components/ui/dataGridModel";

// The data grid's arithmetic and rules, checked at their boundaries. No page
// is opened.

const press = (key: string, code: string, mods: Partial<KeyPress> = {}) => ({
  key,
  code,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  altKey: false,
  ...mods,
});
// The platform's primary modifier, as the grid reads it.
const primary = APPLE ? { metaKey: true } : { ctrlKey: true };

test("row offsets are a prefix sum ending at the full height", () => {
  expect(prefixSums([])).toEqual([0]);
  expect(prefixSums([10, 20, 5])).toEqual([0, 10, 30, 35]);
});

test("the row at a height is the last whose top is at or above it", () => {
  const tops = prefixSums([10, 20, 5]);
  expect(rowAt(tops, 0)).toBe(0);
  expect(rowAt(tops, 9.9)).toBe(0);
  expect(rowAt(tops, 10)).toBe(1);
  expect(rowAt(tops, 29)).toBe(1);
  expect(rowAt(tops, 30)).toBe(2);
  expect(rowAt(tops, 1000)).toBe(2);
  expect(rowAt(prefixSums([]), 0)).toBe(-1);
});

test("ten thousand rows draw only the viewport and its overscan", () => {
  const tops = prefixSums(new Array(10_000).fill(28));
  const top = visibleRange(tops, 0, 600, 6);
  expect(top.start).toBe(0);
  // 600 / 28 rounds up to 22 rows in view, then six more.
  expect(top.end).toBe(28);
  const middle = visibleRange(tops, 28 * 5000, 600, 6);
  expect(middle.start).toBe(4994);
  expect(middle.end).toBe(5028);
  const end = visibleRange(tops, 28 * 10_000 - 600, 600, 6);
  expect(end.end).toBe(10_000);
  expect(end.end - end.start).toBeLessThan(40);
  expect(visibleRange(prefixSums([]), 0, 600, 6)).toEqual({
    start: 0,
    end: 0,
  });
});

test("rows of different heights are windowed by their own offsets", () => {
  // A tall row in the middle covers the whole viewport on its own.
  const tops = prefixSums([20, 20, 1000, 20, 20]);
  expect(visibleRange(tops, 100, 300, 0)).toEqual({ start: 2, end: 3 });
  expect(visibleRange(tops, 1045, 50, 0)).toEqual({ start: 3, end: 5 });
});

test("a viewport too short for a row still draws the row it is in", () => {
  const tops = prefixSums([100, 100]);
  expect(visibleRange(tops, 50, 0, 0)).toEqual({ start: 0, end: 1 });
});

test("revealing a row scrolls only when it is out of view, under the header", () => {
  // A viewport of 300 with a 30 pixel sticky header over its top.
  expect(scrollToReveal(100, 300, 30, 150, 180)).toBe(100);
  expect(scrollToReveal(100, 300, 30, 50, 80)).toBe(50);
  expect(scrollToReveal(100, 300, 30, 360, 390)).toBe(120);
  expect(scrollToReveal(0, 300, 30, 270, 300)).toBe(30);
  expect(scrollToAlign("start", 0, 300, 30, 500, 530)).toBe(500);
  expect(scrollToAlign("center", 0, 300, 30, 500, 530)).toBe(380);
  expect(scrollToAlign("nearest", 0, 300, 30, 100, 130)).toBe(0);
});

test("moving between rows skips those that cannot hold focus and stops at the ends", () => {
  const focusable = [true, false, true, true, false];
  const can = (index: number) => focusable[index] ?? false;
  expect(nextRow(5, 0, 1, can)).toBe(2);
  expect(nextRow(5, 2, -1, can)).toBe(0);
  expect(nextRow(5, 3, 1, can)).toBe(3);
  expect(nextRow(5, 0, -1, can)).toBe(0);
  expect(edgeRow(5, "first", can)).toBe(0);
  expect(edgeRow(5, "last", can)).toBe(3);
});

test("sticky columns are drawn at their edges, in the order given", () => {
  const order = displayOrder([
    { id: "a" },
    { id: "amount", sticky: "end" as const },
    { id: "b" },
    { id: "date", sticky: "start" as const },
    { id: "select", sticky: "start" as const },
  ]).map((column) => column.id);
  expect(order).toEqual(["date", "select", "a", "b", "amount"]);
});

test("growing columns share the spare room, and nothing shrinks below its width", () => {
  const columns = [
    { id: "select", width: 2, sticky: "start" as const },
    { id: "description", width: 12, grow: 2 },
    { id: "party", width: 9, grow: 1 },
    { id: "amount", width: 6, sticky: "end" as const },
  ];
  // 29 rem at 16 pixels is 464; 160 pixels are left over to share.
  const wide = columnLayout(columns, 16, 624);
  expect(wide.total).toBeCloseTo(624);
  expect(wide.byId.get("description")?.width).toBeCloseTo(
    12 * 16 + 160 * (2 / 3),
  );
  expect(wide.byId.get("party")?.width).toBeCloseTo(9 * 16 + 160 / 3);
  expect(wide.byId.get("select")?.width).toBe(32);
  const narrow = columnLayout(columns, 16, 200);
  expect(narrow.total).toBe(464);
  expect(narrow.byId.get("description")?.width).toBe(192);
  // A minimum above the width wins.
  const floored = columnLayout([{ id: "x", width: 2, minWidth: 5 }], 16, 0);
  expect(floored.byId.get("x")?.width).toBe(80);
});

test("sticky columns know how far from their edge they stick", () => {
  const layout = columnLayout(
    [
      { id: "select", width: 2, sticky: "start" },
      { id: "date", width: 5, sticky: "start" },
      { id: "body", width: 10 },
      { id: "tax", width: 4, sticky: "end" },
      { id: "amount", width: 6, sticky: "end" },
    ],
    10,
    0,
  );
  expect(layout.byId.get("select")?.inset).toBe(0);
  expect(layout.byId.get("date")?.inset).toBe(20);
  expect(layout.byId.get("amount")?.inset).toBe(0);
  expect(layout.byId.get("tax")?.inset).toBe(60);
  expect(layout.startCover).toBe(70);
  expect(layout.endCover).toBe(100);
  expect(layout.byId.get("body")?.left).toBe(70);
});

test("row selection: one alone, one toggled, a span from the anchor, or all", () => {
  const order = ["a", "b", "c", "d", "e"];
  expect([...selectOnly("c")]).toEqual(["c"]);
  expect([...toggleKey(new Set(["a"]), "c")].sort()).toEqual(["a", "c"]);
  expect([...toggleKey(new Set(["a", "c"]), "c")]).toEqual(["a"]);
  expect([...selectRange(order, "b", "d")]).toEqual(["b", "c", "d"]);
  expect([...selectRange(order, "d", "b")].sort()).toEqual(["b", "c", "d"]);
  // A span adds to what was already chosen when asked to.
  expect([...selectRange(order, "d", "e", new Set(["a"]))].sort()).toEqual([
    "a",
    "d",
    "e",
  ]);
  // With no anchor, or one filtered away, the span is the row alone.
  expect([...selectRange(order, null, "c")]).toEqual(["c"]);
  expect([...selectRange(order, "gone", "c")]).toEqual(["c"]);
  expect([...selectRange(order, "a", "gone")]).toEqual([]);
  expect([...selectAll(order)]).toEqual(order);
});

test("the selection's extent is none, some or all of the rows in view", () => {
  const order = ["a", "b"];
  expect(selectionExtent(order, new Set())).toBe("none");
  expect(selectionExtent(order, new Set(["a", "hidden"]))).toBe("some");
  expect(selectionExtent(order, new Set(["a", "b"]))).toBe("all");
  expect(selectionExtent([], new Set())).toBe("none");
});

test("a cell range covers its rectangle and reports only data rows", () => {
  const box = cellBox({ row: 4, column: 3 }, { row: 1, column: 1 });
  expect(box).toEqual({ top: 1, bottom: 4, start: 1, end: 3 });
  expect(inBox(box, 1, 1)).toBe(true);
  expect(inBox(box, 4, 3)).toBe(true);
  expect(inBox(box, 0, 2)).toBe(false);
  expect(inBox(box, 2, 4)).toBe(false);
  const keys = ["m1", null, "m2", "m3", "m4"];
  expect(
    rangeOf(box, (row) => keys[row] ?? null, ["s", "d", "e", "a", "x"]),
  ).toEqual({ rows: ["m2", "m3", "m4"], columns: ["d", "e", "a"] });
});

test("columns move one place at a time, or to a drop target, within their group", () => {
  const columns = [
    { id: "select", sticky: "start" as const },
    { id: "a" },
    { id: "b" },
    { id: "c" },
    { id: "amount", sticky: "end" as const },
  ];
  expect(stepColumn(columns, "b", 1)).toEqual([
    "select",
    "a",
    "c",
    "b",
    "amount",
  ]);
  expect(stepColumn(columns, "a", -1)).toBeNull();
  expect(stepColumn(columns, "c", 1)).toBeNull();
  expect(stepColumn(columns, "missing", 1)).toBeNull();
  expect(dropColumn(columns, "c", "a")).toEqual([
    "select",
    "c",
    "a",
    "b",
    "amount",
  ]);
  expect(dropColumn(columns, "a", "amount")).toBeNull();
  expect(dropColumn(columns, "a", "a")).toBeNull();
});

test("every chord the shell owns is recognised, and the grid's own are not", () => {
  const shell = [
    press("k", "KeyK", primary),
    press("p", "KeyP", primary),
    press(",", "Comma", primary),
    press("F6", "F6"),
    press("F6", "F6", { shiftKey: true }),
    press("`", "Backquote", { ctrlKey: true }),
    ...["KeyA", "KeyT", "KeyH", "KeyM", "KeyL", "KeyD", "KeyK"].map((code) =>
      press(code.slice(3), code, { ...primary, shiftKey: true }),
    ),
    ...["Digit1", "Digit2", "Digit3"].map((code) =>
      press(code.slice(5), code, { ...primary, shiftKey: true }),
    ),
  ];
  for (const chord of shell)
    expect(isShellChord(chord), JSON.stringify(chord)).toBe(true);
  const grid = [
    press("a", "KeyA", primary),
    press("d", "KeyD", primary),
    press("c", "KeyC", primary),
    press("Home", "Home", { ...primary, shiftKey: true }),
    press("ArrowLeft", "ArrowLeft", { altKey: true }),
    press("k", "KeyK"),
    press("k", "KeyK", { ...primary, altKey: true }),
  ];
  for (const chord of grid)
    expect(isShellChord(chord), JSON.stringify(chord)).toBe(false);
});

test("modifiers match exactly, so a chord with Shift is not the chord without it", () => {
  expect(exactly(press("a", "KeyA", primary), { primary: true })).toBe(true);
  expect(
    exactly(press("a", "KeyA", { ...primary, shiftKey: true }), {
      primary: true,
    }),
  ).toBe(false);
  expect(
    exactly(press("a", "KeyA", { ctrlKey: true, metaKey: true }), {
      primary: true,
    }),
  ).toBe(false);
  expect(exactly(press("x", "KeyX"))).toBe(true);
  expect(exactly(press("x", "KeyX", { altKey: true }))).toBe(false);
});

test("a typed character opens an editor; Space and chords do not", () => {
  expect(isPrintable(press("a", "KeyA"))).toBe(true);
  expect(isPrintable(press("A", "KeyA", { shiftKey: true }))).toBe(true);
  expect(isPrintable(press("7", "Digit7"))).toBe(true);
  expect(isPrintable(press(" ", "Space"))).toBe(false);
  expect(isPrintable(press("Enter", "Enter"))).toBe(false);
  expect(isPrintable(press("a", "KeyA", primary))).toBe(false);
  expect(isPrintable(press("a", "KeyA", { isComposing: true }))).toBe(false);
  // AltGr arrives as Control and Alt together, except on Apple systems.
  expect(
    isPrintable(press("@", "Digit2", { ctrlKey: true, altKey: true })),
  ).toBe(!APPLE);
});

test("an editor commits with Enter or Tab either way and cancels with Escape", () => {
  expect(commitKeyOf(press("Enter", "Enter"))).toBe("enter");
  expect(commitKeyOf(press("Tab", "Tab"))).toBe("tab");
  expect(commitKeyOf(press("Tab", "Tab", { shiftKey: true }))).toBe(
    "shift-tab",
  );
  expect(commitKeyOf(press("Escape", "Escape"))).toBe("cancel");
  expect(commitKeyOf(press("Enter", "Enter", { shiftKey: true }))).toBeNull();
  expect(
    commitKeyOf(press("Enter", "Enter", { isComposing: true })),
  ).toBeNull();
  expect(commitKeyOf(press("a", "KeyA"))).toBeNull();
});

test("token lengths resolve to pixels from rem or px only", () => {
  expect(lengthPx("1.75rem", 16)).toBe(28);
  expect(lengthPx(" 2px ", 16)).toBe(2);
  expect(lengthPx("", 16)).toBeNull();
  expect(lengthPx("var(--x)", 16)).toBeNull();
  expect(lengthPx("3em", 16)).toBeNull();
});
