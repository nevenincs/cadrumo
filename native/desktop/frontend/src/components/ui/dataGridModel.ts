// The data grid's arithmetic and selection rules, kept apart from the
// component so they can be checked without a page: row offsets by prefix sum,
// the window of rows a viewport needs, column boxes, the keyboard chords the
// grid takes or leaves alone, and the row and cell selections.

import type { ChordKeys } from "@/shared/chords";

/** One column's sizing, in rem. */
export type ColumnMeasure = {
  id: string;
  width: number;
  minWidth?: number;
  /** A share of the room left over once every column has its width. */
  grow?: number;
  sticky?: "start" | "end";
  /** The narrower width, in rem, a pinned column takes where its group
   * would otherwise leave the scrolling columns too narrow a band to show
   * the widest of them whole. */
  narrowWidth?: number;
};

/** Where a column is drawn, in pixels from the inline start of the row. */
export type ColumnBox = {
  id: string;
  left: number;
  width: number;
  sticky?: "start" | "end";
  /** The inset a sticky column keeps from its edge of the viewport. */
  inset: number;
  /** Drawn at its narrower width. */
  narrowed?: true;
};

export type ColumnLayout = {
  boxes: ColumnBox[];
  byId: ReadonlyMap<string, ColumnBox>;
  total: number;
  /** The width the sticky columns cover at each edge. */
  startCover: number;
  endCover: number;
  /** The least width at which any scrolling column can be shown whole
   * beside the pinned groups, drawn at their narrower widths. */
  least: number;
};

/**
 * Where a horizontal scroll that came to rest at `left` settles: the
 * nearest place where a scrolling column's start meets the pinned start
 * group's inner edge, or either end of the scroll, so a column is either
 * whole or under a pinned group, never cut mid-word. A scroll that began at
 * `from` and would settle back there goes on to the next place in the way
 * it moved instead, so even a small scroll moves by a column.
 */
export function snappedLeft(
  layout: Pick<ColumnLayout, "boxes" | "startCover">,
  left: number,
  max: number,
  from: number = left,
): number {
  const end = Math.max(0, max);
  const stops = [
    ...new Set([
      0,
      end,
      ...layout.boxes
        .filter((box) => !box.sticky)
        .map((box) => Math.min(end, Math.max(0, box.left - layout.startCover))),
    ]),
  ].sort((a, b) => a - b);
  const nearest = stops.reduce((best, stop) =>
    Math.abs(stop - left) < Math.abs(best - left) ? stop : best,
  );
  if (Math.abs(nearest - from) >= 1 || Math.abs(left - from) < 1)
    return nearest;
  return left > from
    ? (stops.find((stop) => stop > from + 1) ?? nearest)
    : ([...stops].reverse().find((stop) => stop < from - 1) ?? nearest);
}

/** The smallest a column may be made, in rem, when it names no minimum. */
export const MIN_COLUMN_REM = 3;

/**
 * Sticky columns are drawn at their edge whatever their place in the list:
 * the start ones first, the end ones last, each group in the order given.
 */
export function displayOrder<C extends { sticky?: "start" | "end" }>(
  columns: readonly C[],
): C[] {
  return [
    ...columns.filter((column) => column.sticky === "start"),
    ...columns.filter((column) => !column.sticky),
    ...columns.filter((column) => column.sticky === "end"),
  ];
}

/**
 * Lays columns out at `remPx` pixels to the rem across `available` pixels.
 * Growing columns share what is left over by their `grow`; nothing shrinks
 * below its width, so a narrow viewport scrolls instead, under the
 * pinned groups, which stay pinned however narrow it is. Where their band
 * is narrower than the widest scrolling column, pinned columns with a
 * narrower width take it, so that any one of the rest can be shown whole.
 */
export function columnLayout(
  columns: readonly ColumnMeasure[],
  remPx: number,
  available: number,
): ColumnLayout {
  const ordered = displayOrder(columns);
  const place = (narrow: boolean) => {
    const base = ordered.map((column) =>
      narrow && column.sticky && column.narrowWidth !== undefined
        ? Math.min(column.narrowWidth, column.width)
        : Math.max(column.width, column.minWidth ?? 0),
    );
    const fixed = base.reduce((sum, width) => sum + width * remPx, 0);
    const shares = ordered.reduce(
      (sum, column) => sum + Math.max(0, column.grow ?? 0),
      0,
    );
    const spare = Math.max(0, available - fixed);
    const placed: ColumnBox[] = [];
    let end = 0;
    ordered.forEach((column, index) => {
      const grow = Math.max(0, column.grow ?? 0);
      const width =
        (base[index] ?? 0) * remPx + (shares > 0 ? (spare * grow) / shares : 0);
      const narrowed =
        narrow && column.sticky && column.narrowWidth !== undefined;
      placed.push({
        id: column.id,
        left: end,
        width,
        sticky: column.sticky,
        inset: 0,
        ...(narrowed ? { narrowed: true as const } : {}),
      });
      end += width;
    });
    return { placed, end };
  };
  let { placed: boxes, end: left } = place(false);
  const narrowest = place(true).placed;
  const least =
    narrowest.reduce((sum, box) => sum + (box.sticky ? box.width : 0), 0) +
    narrowest.reduce(
      (most, box) => (box.sticky ? most : Math.max(most, box.width)),
      0,
    );
  if (left > available) {
    const pinned = boxes.reduce(
      (sum, box) => sum + (box.sticky ? box.width : 0),
      0,
    );
    const widest = boxes.reduce(
      (most, box) => (box.sticky ? most : Math.max(most, box.width)),
      0,
    );
    if (available - pinned < widest)
      ({ placed: boxes, end: left } = place(true));
  }
  let startCover = 0;
  for (const box of boxes) {
    if (box.sticky !== "start") continue;
    box.inset = startCover;
    startCover += box.width;
  }
  let endCover = 0;
  for (const box of [...boxes].reverse()) {
    if (box.sticky !== "end") continue;
    box.inset = endCover;
    endCover += box.width;
  }
  return {
    boxes,
    byId: new Map(boxes.map((box) => [box.id, box])),
    total: left,
    startCover,
    endCover,
    least,
  };
}

/**
 * Offsets from row heights: `tops[i]` is where row `i` starts and the last
 * entry is the height of them all.
 */
export function prefixSums(heights: readonly number[]): number[] {
  const tops = new Array<number>(heights.length + 1);
  let y = 0;
  for (let index = 0; index < heights.length; index += 1) {
    tops[index] = y;
    y += heights[index] ?? 0;
  }
  tops[heights.length] = y;
  return tops;
}

/** The row that covers `y`: the last whose top is at or above it. */
export function rowAt(tops: readonly number[], y: number): number {
  const count = tops.length - 1;
  if (count <= 0) return -1;
  let low = 0;
  let high = count - 1;
  while (low < high) {
    const middle = (low + high + 1) >> 1;
    if ((tops[middle] ?? 0) <= y) low = middle;
    else high = middle - 1;
  }
  return low;
}

/**
 * The rows a viewport `height` pixels tall at `top` needs drawn, with
 * `overscan` more at each end: `start` inclusive, `end` exclusive.
 */
export function visibleRange(
  tops: readonly number[],
  top: number,
  height: number,
  overscan: number,
): { start: number; end: number } {
  const count = tops.length - 1;
  if (count <= 0) return { start: 0, end: 0 };
  const first = rowAt(tops, Math.max(0, top));
  let last = first;
  const bottom = top + Math.max(0, height);
  while (last < count && (tops[last] ?? 0) < bottom) last += 1;
  return {
    start: Math.max(0, first - overscan),
    end: Math.min(count, Math.max(last, first + 1) + overscan),
  };
}

/**
 * The scroll position that brings the span from `top` to `bottom` into a
 * viewport of `height` at `scroll`, with `cover` pixels at its top hidden
 * under a sticky header. A span already in view keeps the position.
 */
export function scrollToReveal(
  scroll: number,
  height: number,
  cover: number,
  top: number,
  bottom: number,
): number {
  const room = Math.max(0, height - cover);
  if (top < scroll) return top;
  if (bottom > scroll + room) return Math.max(0, bottom - room);
  return scroll;
}

/** Where a span sits in a viewport, as `scrollToKey` asks for it. */
export function scrollToAlign(
  align: "nearest" | "start" | "center",
  scroll: number,
  height: number,
  cover: number,
  top: number,
  bottom: number,
): number {
  const room = Math.max(0, height - cover);
  if (align === "start") return Math.max(0, top);
  if (align === "center") return Math.max(0, top - (room - (bottom - top)) / 2);
  return scrollToReveal(scroll, height, cover, top, bottom);
}

/** The next row from `index` in `step`'s direction that `can` accepts, or
 * `index` itself when there is none. */
export function nextRow(
  count: number,
  index: number,
  step: number,
  can: (index: number) => boolean,
): number {
  let at = index + step;
  while (at >= 0 && at < count && !can(at)) at += step;
  return at >= 0 && at < count ? at : index;
}

/** The first row from the start, or from the end, that `can` accepts. */
export function edgeRow(
  count: number,
  edge: "first" | "last",
  can: (index: number) => boolean,
): number {
  return edge === "first"
    ? nextRow(count, -1, 1, can)
    : nextRow(count, count, -1, can);
}

// ── Row selection ──────────────────────────────────────────────────────

/** Why the row selection changed: one row chosen alone, one row added or
 * taken away, a span from the anchor, or every row. */
export type SelectionCause = "select" | "toggle" | "range" | "all";

export function selectOnly(key: string): Set<string> {
  return new Set([key]);
}

export function toggleKey(
  selected: ReadonlySet<string>,
  key: string,
): Set<string> {
  const next = new Set(selected);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

/**
 * The rows from `anchor` to `key` in `order`, added to `base`. With no
 * anchor, or one no longer in the list, the span starts at `key`.
 */
export function selectRange(
  order: readonly string[],
  anchor: string | null,
  key: string,
  base: ReadonlySet<string> = new Set(),
): Set<string> {
  const to = order.indexOf(key);
  if (to < 0) return new Set(base);
  const found = anchor === null ? -1 : order.indexOf(anchor);
  const from = found < 0 ? to : found;
  const next = new Set(base);
  for (let index = Math.min(from, to); index <= Math.max(from, to); index += 1)
    next.add(order[index] as string);
  return next;
}

export function selectAll(order: readonly string[]): Set<string> {
  return new Set(order);
}

/**
 * The header checkbox's choice. Alone it makes the rows in view the whole
 * selection, or clears it when they all are; with `add` it puts the rows in
 * view into the selection, or takes them out, and keeps the rest.
 */
export function headerSelection(
  order: readonly string[],
  selected: ReadonlySet<string>,
  add: boolean,
): Set<string> {
  const every = selectionExtent(order, selected) === "all";
  if (!add) return every ? new Set() : selectAll(order);
  const next = new Set(selected);
  for (const key of order)
    if (every) next.delete(key);
    else next.add(key);
  return next;
}

/** Whether none, some or every row of `order` is selected. */
export function selectionExtent(
  order: readonly string[],
  selected: ReadonlySet<string>,
): "none" | "some" | "all" {
  let count = 0;
  for (const key of order) if (selected.has(key)) count += 1;
  if (count === 0) return "none";
  return count === order.length ? "all" : "some";
}

// ── Cell ranges ────────────────────────────────────────────────────────

/** A cell by its row's place in the grid and its column's place in the
 * drawn order. */
export type CellPoint = { row: number; column: number };

/** The rectangle two corners span, inclusive at both ends. */
export type CellBox = {
  top: number;
  bottom: number;
  start: number;
  end: number;
};

export function cellBox(anchor: CellPoint, focus: CellPoint): CellBox {
  return {
    top: Math.min(anchor.row, focus.row),
    bottom: Math.max(anchor.row, focus.row),
    start: Math.min(anchor.column, focus.column),
    end: Math.max(anchor.column, focus.column),
  };
}

export function inBox(box: CellBox, row: number, column: number): boolean {
  return (
    row >= box.top &&
    row <= box.bottom &&
    column >= box.start &&
    column <= box.end
  );
}

/** A range as the caller receives it: the keys of the data rows it covers,
 * in order, and the ids of its columns, in drawn order. */
export type CellRange = { rows: string[]; columns: string[] };

export function rangeOf(
  box: CellBox,
  dataKeyAt: (row: number) => string | null,
  columnIds: readonly string[],
): CellRange {
  const rows: string[] = [];
  for (let row = box.top; row <= box.bottom; row += 1) {
    const key = dataKeyAt(row);
    if (key !== null) rows.push(key);
  }
  return { rows, columns: columnIds.slice(box.start, box.end + 1) };
}

// ── Column order ───────────────────────────────────────────────────────

/**
 * Moves column `id` by `step` places among the columns that share its
 * stickiness, and returns the full order of ids, or null when it cannot
 * move that way.
 */
export function stepColumn(
  columns: readonly { id: string; sticky?: "start" | "end" }[],
  id: string,
  step: -1 | 1,
): string[] | null {
  const ordered = displayOrder(columns);
  const at = ordered.findIndex((column) => column.id === id);
  const to = at + step;
  if (at < 0 || to < 0 || to >= ordered.length) return null;
  if (ordered[to]?.sticky !== ordered[at]?.sticky) return null;
  const ids = ordered.map((column) => column.id);
  ids.splice(to, 0, ...ids.splice(at, 1));
  return ids;
}

/** Moves column `id` to stand where `target` stands, within its group. */
export function dropColumn(
  columns: readonly { id: string; sticky?: "start" | "end" }[],
  id: string,
  target: string,
): string[] | null {
  const ordered = displayOrder(columns);
  const at = ordered.findIndex((column) => column.id === id);
  const to = ordered.findIndex((column) => column.id === target);
  if (at < 0 || to < 0 || at === to) return null;
  if (ordered[to]?.sticky !== ordered[at]?.sticky) return null;
  const ids = ordered.map((column) => column.id);
  ids.splice(to, 0, ...ids.splice(at, 1));
  return ids;
}

// ── Keys ───────────────────────────────────────────────────────────────

/** The modifier state of a key press, as both DOM and React events have it. */
export type KeyPress = {
  key: string;
  code: string;
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
  isComposing?: boolean;
  getModifierState?: (key: "AltGraph") => boolean;
};

const platform =
  typeof navigator === "undefined"
    ? ""
    : ((navigator as Navigator & { userAgentData?: { platform?: string } })
        .userAgentData?.platform ?? navigator.platform);

/** Command is the primary modifier on Apple systems, Control elsewhere. */
export const APPLE = /mac|iphone|ipad/i.test(platform);

export type Modifiers = {
  primary?: boolean;
  shift?: boolean;
  alt?: boolean;
};

/**
 * Whether a press carries exactly these modifiers and no others. The
 * primary modifier is Command on Apple systems and Control elsewhere, and
 * the other one of the pair must be up.
 */
export function exactly(
  press: Pick<KeyPress, "ctrlKey" | "metaKey" | "shiftKey" | "altKey">,
  wanted: Modifiers = {},
): boolean {
  const primary = APPLE ? press.metaKey : press.ctrlKey;
  const other = APPLE ? press.ctrlKey : press.metaKey;
  return (
    primary === !!wanted.primary &&
    !other &&
    press.shiftKey === !!wanted.shift &&
    press.altKey === !!wanted.alt
  );
}

/** Fill down: the grid runs it, and a menu that offers it shows it. */
export const FILL_DOWN_CHORD: ChordKeys = { code: "KeyD", key: "D", mod: true };

/** The character a key gives unshifted on a US layout, for a letter or digit. */
function ownCharacter(code: string): string | null {
  const letter = /^Key([A-Z])$/.exec(code);
  if (letter) return letter[1]!.toLowerCase();
  const digit = /^Digit([0-9])$/.exec(code);
  return digit ? digit[1]! : null;
}

/**
 * Whether a press types a character, which opens a cell's editor seeded
 * with it. Space is left out: it toggles the row's selection. A character
 * typed with AltGr arrives with Control and Alt both down on Windows; a
 * Ctrl+Alt press that gives the key's own letter is a chord, not text.
 */
export function isPrintable(press: KeyPress): boolean {
  if (press.isComposing || press.key.length !== 1 || press.key === " ")
    return false;
  if (press.metaKey) return false;
  if (!press.ctrlKey && !press.altKey) return true;
  if (APPLE || !press.ctrlKey || !press.altKey) return false;
  if (press.getModifierState?.("AltGraph")) return true;
  return press.key.toLowerCase() !== ownCharacter(press.code);
}

/** How a value left its editor: by Enter, by Tab one way or the other, or
 * by the pointer. The grid moves on from the cell to match. */
export type CommitKey = "enter" | "tab" | "shift-tab" | "pointer";

/** What an editor's key press asks for: to commit, to cancel or nothing. */
export function commitKeyOf(press: KeyPress): CommitKey | "cancel" | null {
  if (press.isComposing) return null;
  if (press.key === "Escape" && exactly(press)) return "cancel";
  if (press.key === "Enter" && exactly(press)) return "enter";
  if (press.key === "Tab" && exactly(press)) return "tab";
  if (press.key === "Tab" && exactly(press, { shift: true }))
    return "shift-tab";
  return null;
}

/** A resolved CSS length in rem or px as pixels, or null when it is neither. */
export function lengthPx(raw: string, remPx: number): number | null {
  const text = raw.trim();
  const value = parseFloat(text);
  if (!Number.isFinite(value)) return null;
  if (text.endsWith("rem")) return value * remPx;
  if (text.endsWith("px")) return value;
  return null;
}
