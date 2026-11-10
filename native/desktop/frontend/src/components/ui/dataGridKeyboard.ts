import type * as React from "react";
import {
  exactly,
  FILL_DOWN_CHORD,
  edgeRow,
  isPrintable,
  lengthPx,
  MIN_COLUMN_REM,
  nextRow,
  rowAt,
  selectAll,
  selectOnly,
  stepColumn,
  type CellRange,
  type ColumnLayout,
} from "./dataGridModel";
import {
  HEADER_INDEX,
  cellCount,
  type GridNavigation,
} from "./dataGridNavigation";
import type {
  DataGridProps,
  Editing,
  GridColumn,
  GridMenuAnchor,
  GridRow,
} from "./dataGridTypes";
import type { useGridSelection } from "./dataGridSelection";
import { chordMatches } from "@/shared/chords";
import { clipboardChord, pasteRange } from "./dataGridClipboard";

/** Maps grid-owned keyboard gestures to navigation, selection and edit actions. */
export function gridKeyboard<R>({
  navigation,
  rowSelection,
  ordered,
  rows,
  layout,
  remPx,
  scroller,
  tops,
  bodyHeight,
  dataKeys,
  selection,
  editing,
  actions,
  startEdit,
  readOnlyReason,
  editorFor,
}: {
  navigation: GridNavigation<R>;
  rowSelection: ReturnType<typeof useGridSelection<R>>;
  ordered: readonly GridColumn<R>[];
  rows: readonly GridRow<R>[];
  layout: ColumnLayout;
  remPx: number;
  scroller: React.RefObject<HTMLDivElement | null>;
  tops: readonly number[];
  bodyHeight: number;
  dataKeys: readonly string[];
  selection: DataGridProps<R>["selection"];
  editing: Editing | null;
  actions: Pick<
    DataGridProps<R>,
    | "onColumnOrder"
    | "onSort"
    | "onToggleSection"
    | "onFill"
    | "onMenu"
    | "onActivate"
    | "onCommit"
    | "onCopy"
    | "onPaste"
    | "clipboard"
  > & { onColumnResize(column: string, width: number): void };
  startEdit(key: string, column: string, initial?: string): boolean;
  readOnlyReason(row: GridRow<R>, column: string): string | undefined;
  editorFor(
    key: string,
    column: string,
    initial?: string,
  ): React.ReactNode | null;
}) {
  const {
    preferred,
    anchor,
    setAnchor,
    resolved,
    resolvedIndex,
    resolvedRow,
    moveTo,
    request,
    navigable,
    columnAt,
    cellIndexOf,
    domId,
    currentRange,
  } = navigation;
  const { selectionAnchor, rowMode, changeSelection, pickRow, extendRows } =
    rowSelection;
  const {
    onColumnResize,
    onColumnOrder,
    onSort,
    onToggleSection,
    onFill,
    onMenu,
    onActivate,
    onCommit,
    onCopy,
    onPaste,
    clipboard,
  } = actions;
  // ── The keyboard ──────────────────────────────────────────────────────
  const menuAt = (element: HTMLElement | null): GridMenuAnchor => {
    const rect = element?.getBoundingClientRect();
    return rect
      ? { x: rect.left, y: rect.top, height: rect.height }
      : { x: 0, y: 0 };
  };

  const resizeStep = () => {
    const raw = scroller.current
      ? getComputedStyle(scroller.current).getPropertyValue("--resize-step")
      : "";
    return (lengthPx(raw, remPx) ?? remPx) / remPx;
  };

  /** Asks every cell of the range that has an editor to clear. */
  const clearRange = (target: CellRange) => {
    if (!onCommit) return;
    for (const rowKey of target.rows)
      for (const columnId of target.columns)
        if (editorFor(rowKey, columnId) !== null)
          onCommit(rowKey, columnId, null);
  };

  const headerKeys = (event: React.KeyboardEvent, column: string) => {
    const at = ordered.findIndex((entry) => entry.id === column);
    const named = ordered[at];
    if (!named) return false;
    const key = event.key;
    if (
      (key === "ArrowLeft" || key === "ArrowRight") &&
      exactly(event, { alt: true })
    ) {
      if (named.resizable === false) return false;
      const box = layout.byId.get(column);
      const width = (box?.width ?? named.width * remPx) / remPx;
      const step = resizeStep() * (key === "ArrowLeft" ? -1 : 1);
      onColumnResize(
        column,
        Math.max(named.minWidth ?? MIN_COLUMN_REM, width + step),
      );
      return true;
    }
    if (
      (key === "ArrowLeft" || key === "ArrowRight") &&
      exactly(event, { primary: true })
    ) {
      if (!onColumnOrder) return false;
      const order = stepColumn(ordered, column, key === "ArrowLeft" ? -1 : 1);
      if (order) onColumnOrder(order);
      request({ key: null, column }, { focus: true, announce: false });
      return true;
    }
    if (!exactly(event)) return false;
    if ((key === "Enter" || key === " ") && named.sortable && onSort) {
      onSort(column);
      return true;
    }
    if (
      key === "ArrowLeft" ||
      key === "ArrowRight" ||
      key === "Home" ||
      key === "End"
    ) {
      const to =
        key === "Home"
          ? 0
          : key === "End"
            ? ordered.length - 1
            : Math.max(
                0,
                Math.min(
                  ordered.length - 1,
                  at + (key === "ArrowLeft" ? -1 : 1),
                ),
              );
      moveTo(
        { key: null, column: ordered[to]?.id ?? column },
        { keyboard: true },
      );
      return true;
    }
    if (key === "ArrowDown") {
      const first = edgeRow(rows.length, "first", navigable);
      const row = rows[first];
      if (row && navigable(first))
        moveTo(
          { key: row.key, column: columnAt(row, preferred.current) },
          { keyboard: true },
        );
      return true;
    }
    return key === "ArrowUp";
  };

  const bodyKeys = (
    event: React.KeyboardEvent,
    at: number,
    row: GridRow<R>,
    column: string,
  ) => {
    const key = event.key;
    const shift = event.shiftKey;
    const plain = exactly(event) || exactly(event, { shift: true });
    const count = cellCount(row, ordered.length);
    const cell = cellIndexOf(row, column);
    const vertical = (to: number, extend: boolean) => {
      const target = rows[to];
      if (!target) return;
      moveTo(
        { key: target.key, column: columnAt(target, preferred.current) },
        { keyboard: true, extend },
      );
      if (extend) extendRows(target.key);
    };
    if (plain && (key === "ArrowDown" || key === "ArrowUp")) {
      if (
        key === "ArrowUp" &&
        at === edgeRow(rows.length, "first", navigable) &&
        !shift
      ) {
        const head = ordered[Math.min(preferred.current, ordered.length - 1)];
        if (head) moveTo({ key: null, column: head.id }, { keyboard: true });
        return true;
      }
      vertical(
        nextRow(rows.length, at, key === "ArrowDown" ? 1 : -1, navigable),
        shift,
      );
      return true;
    }
    if (plain && (key === "ArrowLeft" || key === "ArrowRight")) {
      if (row.kind === "section") {
        const wantsOpen = key === "ArrowRight";
        if (!!row.collapsed === wantsOpen) onToggleSection?.(row.key);
        return true;
      }
      const to = Math.max(
        0,
        Math.min(count - 1, cell + (key === "ArrowLeft" ? -1 : 1)),
      );
      moveTo(
        { key: row.key, column: columnAt(row, to) },
        { keyboard: true, extend: shift },
      );
      return true;
    }
    if (key === "Home" || key === "End") {
      const corner =
        exactly(event, { primary: true }) ||
        exactly(event, { primary: true, shift: true });
      if (!plain && !corner) return false;
      if (corner) {
        const to = edgeRow(
          rows.length,
          key === "Home" ? "first" : "last",
          navigable,
        );
        const target = rows[to];
        if (target) {
          moveTo(
            {
              key: target.key,
              column: columnAt(target, key === "Home" ? 0 : ordered.length - 1),
            },
            { keyboard: true, extend: shift },
          );
          if (shift) extendRows(target.key);
        }
        return true;
      }
      moveTo(
        { key: row.key, column: columnAt(row, key === "Home" ? 0 : count - 1) },
        { keyboard: true, extend: shift },
      );
      return true;
    }
    if (plain && (key === "PageDown" || key === "PageUp")) {
      const top = tops[at] ?? 0;
      const y = key === "PageDown" ? top + bodyHeight : top - bodyHeight;
      let to = rowAt(tops, Math.max(0, y));
      if (!navigable(to))
        to = nextRow(rows.length, to, key === "PageDown" ? -1 : 1, navigable);
      vertical(to, shift);
      return true;
    }
    if (key === " " && row.kind === "data" && selection) {
      if (exactly(event)) pickRow(row.key, { toggle: true });
      else if (exactly(event, { shift: true })) {
        // As a spreadsheet does: the active row alone, which row mode then
        // extends from, so the range and the selection grow together.
        selectionAnchor.current = row.key;
        setAnchor(null);
        changeSelection(selectOnly(row.key), "select");
        rowMode.current = true;
      } else return false;
      return true;
    }
    if (
      exactly(event, { primary: true }) &&
      event.code === "KeyA" &&
      selection
    ) {
      changeSelection(selectAll(dataKeys), "all");
      return true;
    }
    if (chordMatches(FILL_DOWN_CHORD, event) && onFill) {
      const target = currentRange();
      if (target) onFill(target, "down");
      return true;
    }
    if (
      (key === "ContextMenu" && exactly(event)) ||
      (key === "F10" && exactly(event, { shift: true }))
    ) {
      if (!onMenu) return false;
      const element = document.getElementById(domId(at, row, column));
      onMenu(row.key, row.kind === "data" ? column : null, menuAt(element));
      return true;
    }
    const chord = clipboard
      ? clipboardChord(event, exactly(event, { primary: true }))
      : null;
    if (chord && clipboard) {
      const target = currentRange();
      if (!target) return false;
      if (chord === "paste") {
        if (!onPaste) return false;
        const into = pasteRange(target, selection, dataKeys);
        void clipboard.read().then((text) => {
          if (text !== null) onPaste(into, text);
        });
        return true;
      }
      const text = onCopy?.(target) ?? null;
      if (text === null) return false;
      clipboard.write(text);
      if (chord === "cut") clearRange(target);
      return true;
    }
    if (!exactly(event)) {
      if (isPrintable(event) && row.kind !== "section")
        return startEdit(row.key, column, event.key);
      return false;
    }
    if (key === "Enter") {
      if (row.kind === "section") {
        onToggleSection?.(row.key);
        return true;
      }
      if (startEdit(row.key, column)) return true;
      if (!readOnlyReason(row, column)) onActivate?.(row.key);
      return true;
    }
    if (key === "F2") {
      if (row.kind !== "section") startEdit(row.key, column);
      return true;
    }
    if (key === "Delete" && onCommit) {
      const target = currentRange();
      if (!target) return false;
      clearRange(target);
      return true;
    }
    if (key === "Escape" && anchor) {
      setAnchor(null);
      rowMode.current = false;
      return true;
    }
    if (isPrintable(event) && row.kind !== "section")
      return startEdit(row.key, column, event.key);
    return false;
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (editing || event.defaultPrevented || event.nativeEvent.isComposing)
      return;
    const target = event.target as HTMLElement;
    // A field inside a cell keeps its own keys.
    if (target.closest("input, textarea, select, [contenteditable=true]"))
      return;
    if (!resolved || resolvedIndex === null) return;
    const handled =
      resolvedIndex === HEADER_INDEX
        ? headerKeys(event, resolved.column)
        : resolvedRow
          ? bodyKeys(event, resolvedIndex, resolvedRow, resolved.column)
          : false;
    if (handled) {
      event.preventDefault();
      event.stopPropagation();
    }
  };

  return onKeyDown;
}
