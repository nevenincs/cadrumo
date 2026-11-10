import { DataGridRow } from "./data-grid-row";
import { DataGridHeader } from "./data-grid-header";
import { gridColumnPresentation } from "./dataGridPresentation";

import { gridKeyboard } from "./dataGridKeyboard";
import { pasteRange } from "./dataGridClipboard";
import {
  useGridNavigation,
  cellCount,
  columnLabel,
} from "./dataGridNavigation";
import { useGridViewport } from "./dataGridViewport";
import { useGridSelection } from "./dataGridSelection";
import { GridTextTip } from "./data-grid-text";

import { GridSelectionContext } from "./dataGridSelection";
import type {
  Editing,
  GridColumn,
  GridRow,
  DataGridProps,
  EditorContext,
} from "./dataGridTypes";
import * as React from "react";
import { cn } from "@/components/ui/cn";

import {
  columnLayout,
  snappedLeft,
  displayOrder,
  dropColumn,
  MIN_COLUMN_REM,
  nextRow,
  scrollToAlign,
  visibleRange,
  type CommitKey,
} from "@/components/ui/dataGridModel";

const DRAG_SLOP_REM = 0.25;

/**
 * A windowed, keyboard-first grid. It knows rows by a stable key and
 * nothing of what they mean: the caller filters, sorts and groups them and
 * draws each cell. Only the rows in view, and the active one, are in the
 * document; `aria-rowcount` and `aria-rowindex` describe them all.
 *
 * The grid is one tab stop. Arrow keys, Home, End and Page keys move the
 * active cell, with Shift to extend a range; the header row is reached by
 * ArrowUp from the first row. Enter, F2 or a typed character opens the
 * cell's editor, which commits with Enter, Tab or Shift+Tab and cancels with
 * Escape. Clipboard, fill, menu and clearing are left to the caller. It
 * never takes a chord the shell owns.
 *
 * Controls inside a cell take `tabIndex={-1}`, so Tab still leaves the grid.
 */
function DataGrid<R>({
  ref,
  label,
  columns: columnsProp,
  rows,
  positionLabel,
  rowHeight,
  editorForCell,
  density = "compact",
  sort,
  onSort,
  selection,
  onSelectionChange,
  onActivate,
  onCommit,
  onMenu,
  onToggleSection,
  onCopy,
  onPaste,
  clipboard,
  onFill,
  onColumnResize: onColumnResizeProp,
  onColumnOrder,
  rowState,
  describeRow,
  describeCell,
  empty,
  overscan = 6,
  className,
  moreColumnsLabel,
  earlierColumnsLabel,
  onLeast,
}: DataGridProps<R>) {
  const scroller = React.useRef<HTMLDivElement>(null);
  const header = React.useRef<HTMLDivElement>(null);
  const [editing, setEditing] = React.useState<Editing | null>(null);
  const [focused, setFocused] = React.useState(false);
  const [announcement, setAnnouncement] = React.useState("");
  const [drop, setDrop] = React.useState<string | null>(null);
  const suppressClick = React.useRef(false);

  // A caller that does not keep the widths leaves them to the grid: what
  // the person drags a column to lasts as long as the grid does.
  const [dragged, setDragged] = React.useState<
    Readonly<Record<string, number>>
  >({});
  const columns = React.useMemo(
    () =>
      onColumnResizeProp || Object.keys(dragged).length === 0
        ? columnsProp
        : columnsProp.map((column) => {
            const width = dragged[column.id];
            return width === undefined ? column : { ...column, width };
          }),
    [columnsProp, dragged, onColumnResizeProp],
  );
  const onColumnResize = React.useCallback(
    (column: string, width: number) => {
      if (onColumnResizeProp) onColumnResizeProp(column, width);
      else setDragged((held) => ({ ...held, [column]: width }));
    },
    [onColumnResizeProp],
  );
  const ordered = React.useMemo(() => displayOrder(columns), [columns]);
  const index = React.useMemo(
    () => new Map(rows.map((row, at) => [row.key, at])),
    [rows],
  );
  const dataKeys = React.useMemo(
    () => rows.flatMap((row) => (row.kind === "data" ? [row.key] : [])),
    [rows],
  );
  const dataOrdinal = React.useMemo(
    () => new Map(dataKeys.map((key, at) => [key, at])),
    [dataKeys],
  );
  const rowSelection = useGridSelection({
    rows,
    index,
    dataKeys,
    selection,
    onSelectionChange,
  });
  const { rowMode, pickRow, selectionContext } = rowSelection;
  const editable = ordered.some((column) => column.editor);

  const viewport = useGridViewport({
    scroller,
    header,
    rows,
    rowHeight,
    density,
    index,
  });
  const { view, remPx, headerPx, tops, syncView, clearTip, onScroll } =
    viewport;
  const layout = React.useMemo(
    () => columnLayout(ordered, remPx, view.width),
    [ordered, remPx, view.width],
  );
  // A scroll the person ends between columns settles on the nearest column
  // start at the pinned group's edge. A scroll the grid makes itself, to
  // show a cell or the columns a cue names, is left where it put it.
  const layoutRef = React.useRef(layout);
  layoutRef.current = layout;
  const steering = React.useRef(false);
  const restedLeft = React.useRef(0);
  // Whether the scroll last came to rest where the person left it, so a
  // change of the columns' widths settles it again; one the grid steered,
  // to show a cell whole, is left as the grid put it.
  const personRested = React.useRef(true);
  const steerLeft = (element: HTMLElement, left: number) => {
    const before = element.scrollLeft;
    element.scrollLeft = left;
    if (element.scrollLeft !== before) {
      steering.current = true;
      personRested.current = false;
    }
  };
  React.useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const rest = () => {
      const left = element.scrollLeft;
      if (steering.current) {
        steering.current = false;
        restedLeft.current = left;
        return;
      }
      if (Math.abs(left - restedLeft.current) < 1) return;
      personRested.current = true;
      const target = snappedLeft(
        layoutRef.current,
        left,
        element.scrollWidth - element.clientWidth,
        restedLeft.current,
      );
      restedLeft.current = target;
      if (Math.abs(target - left) >= 1) steerLeft(element, target);
    };
    // The person's own scrolling, begun while the grid steered, is theirs
    // to settle when it ends.
    const own = () => {
      steering.current = false;
    };
    const kinds = ["wheel", "touchstart", "pointerdown"] as const;
    for (const kind of kinds)
      element.addEventListener(kind, own, { passive: true });
    element.addEventListener("scrollend", rest);
    return () => {
      for (const kind of kinds) element.removeEventListener(kind, own);
      element.removeEventListener("scrollend", rest);
    };
  }, []);
  React.useEffect(() => {
    const element = scroller.current;
    if (!element || !personRested.current || steering.current) return;
    const left = element.scrollLeft;
    const target = snappedLeft(
      layout,
      left,
      element.scrollWidth - element.clientWidth,
    );
    restedLeft.current = target;
    if (Math.abs(target - left) >= 1) steerLeft(element, target);
    // The person's resting place, kept after the grid steers there.
    personRested.current = true;
  }, [layout]);
  // What the grid draws around its columns: its frame and a scroll bar.
  React.useLayoutEffect(() => {
    const element = scroller.current;
    if (!onLeast || !element?.parentElement) return;
    const frame = element.parentElement.offsetWidth - element.clientWidth;
    onLeast(Math.ceil(layout.least + Math.max(0, frame)));
  }, [onLeast, layout.least, view.width]);

  const bodyHeight = Math.max(0, view.height - headerPx);
  const navigation = useGridNavigation({
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
  });
  const {
    active,
    preferred,
    resolved,
    cellId,
    domId,
    moveTo,
    request,
    columnAt,
    cellIndexOf,
    box,
    currentRange,
  } = navigation;
  const range = visibleRange(tops, view.top, bodyHeight, overscan);
  const shown: number[] = [];
  for (let at = range.start; at < range.end; at += 1) shown.push(at);
  // The active row and the row being edited stay drawn while out of view,
  // so focus and an open editor are never dropped.
  for (const key of [active?.key, editing?.key]) {
    if (key === null || key === undefined) continue;
    const at = index.get(key);
    if (at !== undefined && (at < range.start || at >= range.end))
      shown.push(at);
  }

  // ── Editing ───────────────────────────────────────────────────────────
  const readOnlyReason = (row: GridRow<R>, column: string) => {
    const described = describeCell?.(row.key, column)?.readOnlyReason;
    if (described) return described;
    if (row.kind !== "data") return undefined;
    return ordered
      .find((entry) => entry.id === column)
      ?.readOnlyReason?.(row.data);
  };

  const editorContext = (key: string, column: string, initial?: string) => {
    const at = index.get(key) ?? 0;
    const row = rows[at];
    const named = ordered.find((entry) => entry.id === column);
    const described = [
      describeRow?.(key) ? `${cellId(at, "status")}` : null,
      describeCell?.(key, column)?.text
        ? `${domId(at, row ?? null, column)}-note`
        : null,
    ].filter(Boolean);
    const context: EditorContext = {
      key,
      column,
      initial,
      label: named ? columnLabel(named) : label,
      describedBy: described.length ? described.join(" ") : undefined,
      commit: (value, via = "pointer") => finishEdit(key, column, value, via),
      cancel: (refocus = true) => {
        setEditing(null);
        if (refocus) request({ key, column }, { focus: true, announce: false });
      },
    };
    return context;
  };

  const editorFor = (key: string, column: string, initial?: string) => {
    const row = rows[index.get(key) ?? -1];
    if (!row || row.kind === "section") return null;
    if (readOnlyReason(row, column)) return null;
    const context = editorContext(key, column, initial);
    if (row.kind === "custom")
      return editorForCell?.(key, Number(column) || 0, context) ?? null;
    const named = ordered.find((entry) => entry.id === column);
    return named?.editor?.(row.data, context) ?? null;
  };

  const startEdit = (key: string, column: string, initial?: string) => {
    const row = rows[index.get(key) ?? -1];
    if (!row) return false;
    const reason = readOnlyReason(row, column);
    if (reason) {
      setAnnouncement(reason);
      return false;
    }
    if (editorFor(key, column, initial) === null) return false;
    setEditing({ key, column, initial });
    return true;
  };

  function finishEdit(
    key: string,
    column: string,
    value: unknown,
    via: CommitKey,
  ) {
    onCommit?.(key, column, value);
    setEditing(null);
    if (via === "pointer") return;
    const at = index.get(key);
    const row = at === undefined ? undefined : rows[at];
    if (at === undefined || !row) return;
    if (via === "enter") {
      const below = nextRow(
        rows.length,
        at,
        1,
        (to) => rows[to]?.kind === "data",
      );
      const target = rows[below];
      if (target) moveTo({ key: target.key, column }, { keyboard: true });
      return;
    }
    const count = cellCount(row, ordered.length);
    const cell = cellIndexOf(row, column) + (via === "tab" ? 1 : -1);
    moveTo(
      { key, column: columnAt(row, Math.max(0, Math.min(count - 1, cell))) },
      { keyboard: true },
    );
  }

  const onKeyDown = gridKeyboard({
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
    actions: {
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
    },
    startEdit,
    readOnlyReason,
    editorFor,
  });
  // ── The handle ────────────────────────────────────────────────────────
  React.useImperativeHandle(ref, () => ({
    focusCell: (key, column) => {
      const row = rows[index.get(key) ?? -1];
      if (!row) return;
      moveTo({ key, column: column ?? columnAt(row, preferred.current) });
    },
    scrollToKey: (key, align = "nearest") => {
      const at = index.get(key);
      const element = scroller.current;
      if (at === undefined || !element) return;
      element.scrollTop = scrollToAlign(
        align,
        element.scrollTop,
        element.clientHeight,
        headerPx,
        tops[at] ?? 0,
        tops[at + 1] ?? 0,
      );
      syncView();
    },
    activeCell: () => (resolved ? { ...resolved } : null),
    cellRange: () => (box ? currentRange() : null),
    edit: (key, column, initial) => {
      const row = rows[index.get(key) ?? -1];
      if (!row) return;
      moveTo({ key, column }, { focus: false });
      startEdit(key, column, initial);
    },
    clearAnnouncement: () => setAnnouncement(""),
  }));

  // ── Pointer: columns ──────────────────────────────────────────────────
  const startResize = (
    event: React.PointerEvent<HTMLDivElement>,
    column: GridColumn<R>,
  ) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startWidth =
      layout.byId.get(column.id)?.width ?? column.width * remPx;
    document.body.dataset.resizing = "vertical";
    const move = (moving: PointerEvent) => {
      const width = (startWidth + moving.clientX - startX) / remPx;
      onColumnResize(
        column.id,
        Math.max(column.minWidth ?? MIN_COLUMN_REM, width),
      );
    };
    const end = () => {
      delete document.body.dataset.resizing;
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("lostpointercapture", end);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("lostpointercapture", end);
  };

  // Double click on a column's edge fits it to the widest of what is drawn.
  const fitColumn = (column: GridColumn<R>) => {
    const element = scroller.current;
    if (!element) return;
    let widest = 0;
    for (const cell of element.querySelectorAll<HTMLElement>(
      `[data-column="${CSS.escape(column.id)}"]`,
    )) {
      const style = getComputedStyle(cell);
      const padding =
        parseFloat(style.paddingInlineStart) +
        parseFloat(style.paddingInlineEnd);
      let content = 0;
      for (const child of cell.children)
        content += (child as HTMLElement).scrollWidth;
      widest = Math.max(widest, content + padding);
    }
    if (widest > 0)
      onColumnResize(
        column.id,
        Math.max(column.minWidth ?? MIN_COLUMN_REM, widest / remPx),
      );
  };

  const startReorder = (
    event: React.PointerEvent<HTMLDivElement>,
    column: GridColumn<R>,
  ) => {
    if (event.button !== 0 || !onColumnOrder) return;
    const cell = event.currentTarget;
    const startX = event.clientX;
    const slop = DRAG_SLOP_REM * remPx;
    let dragging = false;
    let over: string | null = null;
    cell.setPointerCapture(event.pointerId);
    const move = (moving: PointerEvent) => {
      if (!dragging && Math.abs(moving.clientX - startX) < slop) return;
      dragging = true;
      const hit = document
        .elementsFromPoint(moving.clientX, moving.clientY)
        .find(
          (element) =>
            element instanceof HTMLElement &&
            element.dataset.headerColumn !== undefined,
        ) as HTMLElement | undefined;
      over = hit?.dataset.headerColumn ?? null;
      setDrop(over && over !== column.id ? over : null);
    };
    const up = () => {
      if (dragging) {
        suppressClick.current = true;
        if (over) {
          const order = dropColumn(ordered, column.id, over);
          if (order) onColumnOrder(order);
        }
      }
    };
    const end = () => {
      setDrop(null);
      cell.removeEventListener("pointermove", move);
      cell.removeEventListener("pointerup", up);
      cell.removeEventListener("lostpointercapture", end);
    };
    cell.addEventListener("pointermove", move);
    cell.addEventListener("pointerup", up);
    cell.addEventListener("lostpointercapture", end);
  };

  // ── Drawing ───────────────────────────────────────────────────────────
  const presentation = gridColumnPresentation(ordered, layout, view);
  const pointerCell = (
    event: React.PointerEvent,
    row: GridRow<R>,
    column: string,
  ) => {
    if (event.button !== 0 && event.button !== 2) return;
    moveTo(
      { key: row.key, column },
      { extend: event.shiftKey && event.button === 0 },
    );
  };
  const clickCell = (event: React.MouseEvent, row: GridRow<R>) => {
    if (row.kind !== "data" || !selection) return;
    const toggle = event.ctrlKey || event.metaKey;
    pickRow(row.key, { toggle, range: event.shiftKey });
  };
  const menuCell = (
    event: React.MouseEvent,
    row: GridRow<R>,
    column: string | null,
  ) => {
    if (!onMenu) return;
    event.preventDefault();
    if (row.kind === "data" && selection && !selection.has(row.key))
      pickRow(row.key, {});
    onMenu(row.key, column, { x: event.clientX, y: event.clientY });
  };
  const doubleCell = (row: GridRow<R>, column: string) => {
    if (row.kind === "section") return onToggleSection?.(row.key);
    if (!startEdit(row.key, column) && !readOnlyReason(row, column))
      onActivate?.(row.key);
  };

  return (
    <GridSelectionContext.Provider value={selectionContext}>
      <GridTextTip clearRef={clearTip}>
        <div
          data-slot="data-grid"
          data-density={density}
          className={cn(
            "relative flex min-h-0 min-w-0 flex-1 flex-col bg-background text-base text-foreground",
            density === "compact"
              ? "[--grid-row:var(--spacing-row-compact)]"
              : "[--grid-row:var(--spacing-row-comfortable)]",
            className,
          )}
        >
          <div
            ref={scroller}
            role="grid"
            aria-label={label}
            aria-rowcount={rows.length + 1}
            aria-colcount={ordered.length}
            aria-multiselectable={selection ? true : undefined}
            className="isolate min-h-0 flex-1 overflow-auto overscroll-contain"
            onScroll={onScroll}
            onKeyDown={onKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={(event) => {
              if (
                !event.currentTarget.contains(
                  event.relatedTarget as Node | null,
                )
              )
                setFocused(false);
            }}
            onCopy={(event) => {
              if (editing || !onCopy) return;
              const target = currentRange();
              const text = target ? onCopy(target) : null;
              if (text === null) return;
              event.preventDefault();
              event.clipboardData.setData("text/plain", text);
            }}
            onPaste={(event) => {
              if (editing || !onPaste) return;
              const target = currentRange();
              if (!target) return;
              event.preventDefault();
              onPaste(
                pasteRange(target, selection, dataKeys),
                event.clipboardData.getData("text/plain"),
              );
            }}
          >
            <DataGridHeader
              header={header}
              scroller={scroller}
              ordered={ordered}
              layout={layout}
              view={view}
              remPx={remPx}
              navigation={navigation}
              presentation={presentation}
              earlierColumnsLabel={earlierColumnsLabel}
              moreColumnsLabel={moreColumnsLabel}
              steerLeft={steerLeft}
              syncView={syncView}
              sort={sort}
              onSort={onSort}
              drop={drop}
              suppressClick={suppressClick}
              startReorder={startReorder}
              startResize={startResize}
              fitColumn={fitColumn}
            />
            <div
              role="rowgroup"
              className="relative"
              style={{ height: tops[rows.length] ?? 0, width: layout.total }}
            >
              {shown.map((at) => (
                <DataGridRow
                  key={rows[at]!.key}
                  at={at}
                  rows={rows}
                  ordered={ordered}
                  layout={layout}
                  viewport={viewport}
                  navigation={navigation}
                  presentation={presentation}
                  selection={selection}
                  focused={focused}
                  editing={editing}
                  editable={editable}
                  describeRow={describeRow}
                  describeCell={describeCell}
                  rowState={rowState}
                  editorFor={editorFor}
                  pointerCell={pointerCell}
                  clickCell={clickCell}
                  menuCell={menuCell}
                  doubleCell={doubleCell}
                  onToggleSection={onToggleSection}
                />
              ))}
            </div>
          </div>
          {rows.length === 0 && empty && (
            <div
              className="absolute inset-x-0 bottom-0 flex"
              style={{ top: headerPx }}
            >
              {empty}
            </div>
          )}
          <div aria-live="polite" aria-atomic="true" className="sr-only">
            {announcement}
          </div>
        </div>
      </GridTextTip>
    </GridSelectionContext.Provider>
  );
}

export { DataGrid };
