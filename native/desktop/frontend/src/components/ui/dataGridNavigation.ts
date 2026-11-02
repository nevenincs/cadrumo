import * as React from "react";
import {
  cellBox,
  edgeRow,
  rangeOf,
  scrollToReveal,
  type CellRange,
  type ColumnLayout,
} from "./dataGridModel";
import type {
  Active,
  Editing,
  GridColumn,
  GridRow,
  DataGridProps,
} from "./dataGridTypes";
import { listOf } from "@/shared/lists";

export const HEADER_INDEX = -1;

export function columnLabel<R>(column: GridColumn<R>): string {
  return (
    column.label ??
    (typeof column.header === "string" ? column.header : column.id)
  );
}

export function cellCount<R>(row: GridRow<R>, columns: number): number {
  if (row.kind === "data") return columns;
  if (row.kind === "section") return 1;
  return row.cells ?? 1;
}

/** Active-cell resolution, range anchors, focus delivery and live announcements. */
export function useGridNavigation<R>({
  rows,
  ordered,
  index,
  editing,
  layout,
  scroller,
  headerPx,
  tops,
  syncView,
  steerLeft,
  rowMode,
  positionLabel,
  describeCell,
  describeRow,
  dataOrdinal,
  dataKeys,
  setAnnouncement,
}: {
  rows: readonly GridRow<R>[];
  ordered: readonly GridColumn<R>[];
  index: ReadonlyMap<string, number>;
  editing: Editing | null;
  layout: ColumnLayout;
  scroller: React.RefObject<HTMLDivElement | null>;
  headerPx: number;
  tops: readonly number[];
  syncView(): void;
  steerLeft(element: HTMLElement, left: number): void;
  rowMode: React.RefObject<boolean>;
  positionLabel: DataGridProps<R>["positionLabel"];
  describeCell: DataGridProps<R>["describeCell"];
  describeRow: DataGridProps<R>["describeRow"];
  dataOrdinal: ReadonlyMap<string, number>;
  dataKeys: readonly string[];
  setAnnouncement: React.Dispatch<React.SetStateAction<string>>;
}) {
  const gridId = React.useId();
  const [active, setActive] = React.useState<Active | null>(null);
  const [anchor, setAnchor] = React.useState<Active | null>(null);
  const preferred = React.useRef(0);
  const navigable = React.useCallback(
    (at: number) => {
      const row = rows[at];
      return !!row && cellCount(row, ordered.length) > 0;
    },
    [rows, ordered.length],
  );

  // ── Where the active cell is ──────────────────────────────────────────
  const firstStop = (): Active | null => {
    const at = edgeRow(rows.length, "first", navigable);
    const row = rows[at];
    if (!row || !navigable(at))
      return ordered[0] ? { key: null, column: ordered[0].id } : null;
    return { key: row.key, column: columnAt(row, 0) };
  };

  function columnAt(row: GridRow<R> | null, cell: number): string {
    if (!row || row.kind === "data") {
      const column = ordered[Math.min(cell, ordered.length - 1)];
      return column?.id ?? "";
    }
    const count = cellCount(row, ordered.length);
    return count > 1 ? String(Math.min(cell, count - 1)) : "";
  }

  function cellIndexOf(row: GridRow<R> | null, column: string): number {
    if (!row || row.kind === "data") {
      const at = ordered.findIndex((entry) => entry.id === column);
      return Math.max(0, at);
    }
    return Math.max(0, Number(column) || 0);
  }

  const resolved: Active | null = (() => {
    if (active) {
      if (active.key === null) {
        if (ordered.some((column) => column.id === active.column))
          return active;
      } else if (index.has(active.key)) return active;
    }
    return firstStop();
  })();
  const resolvedRow =
    resolved && resolved.key !== null
      ? (rows[index.get(resolved.key) ?? -1] ?? null)
      : null;
  const resolvedIndex =
    resolved === null
      ? null
      : resolved.key === null
        ? HEADER_INDEX
        : (index.get(resolved.key) ?? null);
  // The column a vertical move returns to follows the active column by id,
  // so it stays right when columns are moved.
  if (resolved && (resolved.key === null || resolvedRow?.kind === "data"))
    preferred.current = cellIndexOf(resolvedRow, resolved.column);

  const cellId = (at: number, part: string) =>
    at === HEADER_INDEX ? `${gridId}-h-${part}` : `${gridId}-r${at}-${part}`;
  const domId = (at: number, row: GridRow<R> | null, column: string) => {
    if (at === HEADER_INDEX || !row || row.kind === "data")
      return cellId(
        at,
        String(ordered.findIndex((entry) => entry.id === column)),
      );
    return cellId(at, column === "" ? "s" : `x${column}`);
  };

  const reveal = (at: number, column: string) => {
    const element = scroller.current;
    if (!element) return;
    if (at !== HEADER_INDEX) {
      const top = tops[at] ?? 0;
      const bottom = tops[at + 1] ?? top;
      element.scrollTop = scrollToReveal(
        element.scrollTop,
        element.clientHeight,
        headerPx,
        top,
        bottom,
      );
    }
    const box = layout.byId.get(column);
    if (box && !box.sticky) {
      const left = element.scrollLeft + layout.startCover;
      const right = element.scrollLeft + element.clientWidth - layout.endCover;
      if (box.left < left) steerLeft(element, box.left - layout.startCover);
      else if (box.left + box.width > right)
        steerLeft(
          element,
          box.left + box.width - element.clientWidth + layout.endCover,
        );
    }
    syncView();
  };

  const moveTo = (
    next: Active,
    how: { extend?: boolean; keyboard?: boolean; focus?: boolean } = {},
  ) => {
    const at = next.key === null ? HEADER_INDEX : index.get(next.key);
    if (at === undefined) return;
    if (how.extend && next.key !== null) {
      if (!anchor && resolved && resolved.key !== null) setAnchor(resolved);
    } else {
      setAnchor(null);
      rowMode.current = false;
    }
    const row = next.key === null ? null : (rows[at] ?? null);
    if (
      next.key === null ||
      row?.kind === "data" ||
      (row && cellCount(row, ordered.length) > 1)
    )
      preferred.current = cellIndexOf(row, next.column);
    setActive(next);
    request(next, { focus: how.focus !== false, announce: !!how.keyboard });
    reveal(at, next.column);
  };

  // Focus follows the active cell when the grid asks for it, and a move by
  // keyboard is said once in the live region. Both wait for the render that
  // draws the cell, and read that render's rows and columns.
  const pending = React.useRef<{
    cell: Active;
    focus: boolean;
    announce: boolean;
  } | null>(null);
  const [requested, setRequested] = React.useState(0);
  const request = (
    cell: Active,
    how: { focus: boolean; announce: boolean },
  ) => {
    pending.current = { cell, ...how };
    setRequested((count) => count + 1);
  };
  const locate = (cell: Active) => {
    const at = cell.key === null ? HEADER_INDEX : index.get(cell.key);
    if (at === undefined) return null;
    const row = cell.key === null ? null : (rows[at] ?? null);
    return document.getElementById(domId(at, row, cell.column));
  };
  const latest = React.useRef({ locate, spoken, editing });
  latest.current = { locate, spoken, editing };
  React.useLayoutEffect(() => {
    const next = pending.current;
    if (!next) return;
    pending.current = null;
    const { locate: find, spoken: say, editing: open } = latest.current;
    const element = find(next.cell);
    if (next.focus && !open) element?.focus({ preventScroll: true });
    if (next.announce) setAnnouncement(say(element, next.cell));
  }, [requested, setAnnouncement]);

  function spoken(element: HTMLElement | null, cell: Active): string {
    if (!element) return "";
    const text = element.innerText.replace(/\s+/g, " ").trim();
    if (cell.key === null) return text;
    const at = index.get(cell.key);
    const row = at === undefined ? undefined : rows[at];
    if (at === undefined || !row) return text;
    // The position counts movements, not the section rows between them.
    const ordinal = row.kind === "data" ? dataOrdinal.get(row.key) : undefined;
    const parts =
      ordinal === undefined
        ? []
        : [positionLabel(ordinal + 1, dataKeys.length)];
    const column = ordered.find((entry) => entry.id === cell.column);
    if (row.kind === "data" && column) parts.push(columnLabel(column));
    if (text) parts.push(text);
    const note = describeCell?.(row.key, cell.column);
    if (note?.text) parts.push(note.text);
    if (note?.readOnlyReason) parts.push(note.readOnlyReason);
    const status = describeRow?.(row.key);
    if (status) parts.push(status);
    return listOf(document.documentElement.lang || undefined, parts, "plain");
  }

  // ── Ranges and selection ──────────────────────────────────────────────
  const point = (cell: Active | null) => {
    if (!cell || cell.key === null) return null;
    const row = index.get(cell.key);
    if (row === undefined) return null;
    return { row, column: cellIndexOf(rows[row] ?? null, cell.column) };
  };
  const activePoint = point(resolved);
  const anchorPoint = point(anchor);
  const box =
    activePoint && anchorPoint ? cellBox(anchorPoint, activePoint) : null;
  const currentRange = (): CellRange | null => {
    const corner = activePoint;
    if (!corner) return null;
    return rangeOf(
      box ?? cellBox(corner, corner),
      (at) => {
        const row = rows[at];
        return row?.kind === "data" ? row.key : null;
      },
      ordered.map((column) => column.id),
    );
  };

  return {
    active,
    anchor,
    setAnchor,
    preferred,
    resolved,
    resolvedRow,
    resolvedIndex,
    cellId,
    domId,
    moveTo,
    request,
    navigable,
    columnAt,
    cellIndexOf,
    box,
    currentRange,
  };
}

export type GridNavigation<R> = ReturnType<typeof useGridNavigation<R>>;
