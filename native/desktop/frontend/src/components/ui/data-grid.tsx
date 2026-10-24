import * as React from "react";
import { cn } from "@/components/ui/cn";
import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icon";
import { inputVariants } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  cellBox,
  columnLayout,
  commitKeyOf,
  displayOrder,
  dropColumn,
  edgeRow,
  exactly,
  headerSelection,
  inBox,
  isPrintable,
  lengthPx,
  MIN_COLUMN_REM,
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
  type CellRange,
  type CommitKey,
  type SelectionCause,
} from "@/components/ui/dataGridModel";

/** What a cell's renderer knows of where it stands. */
type CellContext = { key: string; active: boolean; selected: boolean };

/** What an editor needs: the key that opened it, its accessible name and
 * description, and the two ways out. */
type EditorContext = {
  key: string;
  column: string;
  /** The character typed to open the editor, which replaces the value. */
  initial?: string;
  label: string;
  describedBy?: string;
  commit: (value: unknown, via?: CommitKey) => void;
  /** Drops the edit. Focus goes back to the cell unless `refocus` is false,
   * as when the person pressed somewhere else. */
  cancel: (refocus?: boolean) => void;
};

type GridColumn<R> = {
  /** Stable: widths, order and `aria-colindex` follow it. */
  id: string;
  /** Already localized header content. */
  header: React.ReactNode;
  /** The column's name in words, for announcements, where `header` is not
   * plain text. */
  label?: string;
  /** In rem. */
  width: number;
  minWidth?: number;
  /** A share of the room left once every column has its width. */
  grow?: number;
  /** Pinned at an inline edge while the rest scrolls. */
  sticky?: "start" | "end";
  /** `end` for figures, which also take tabular numerals. */
  align?: "start" | "end";
  sortable?: boolean;
  /** Default true. */
  resizable?: boolean;
  cell: (row: R, context: CellContext) => React.ReactNode;
  /** Null makes the cell read-only for that row. */
  editor?: (row: R, context: EditorContext) => React.ReactNode | null;
  /** Announced when an edit is asked of a cell that cannot take one. */
  readOnlyReason?: (row: R) => string | undefined;
};

/** Props a custom row spreads on each of its focusable cells. */
type CustomCellProps = {
  id: string;
  role: "gridcell";
  tabIndex: number;
  "aria-colindex": number;
  "aria-describedby"?: string;
  "data-slot": "data-grid-cell";
  "data-active"?: true;
  className: string;
  onPointerDown: (event: React.PointerEvent) => void;
  onDoubleClick: () => void;
  onContextMenu: (event: React.MouseEvent) => void;
};

type RowContext = {
  key: string;
  active: boolean;
  /** Which of the row's cells is active, when the row is. */
  activeCell: number | null;
  cellProps: (index: number) => CustomCellProps;
  /** The cell being edited, and the editor to draw in it. */
  editingCell: number | null;
  editor: React.ReactNode;
};

type GridRow<R> =
  | { kind: "data"; key: string; data: R }
  | {
      kind: "section";
      key: string;
      label: React.ReactNode;
      depth?: number;
      collapsed?: boolean;
      /** A quieter line beside the label: what the section holds. */
      hint?: React.ReactNode;
      /** At the trailing edge: a count or a total. */
      summary?: React.ReactNode;
    }
  | {
      kind: "custom";
      key: string;
      render: (context: RowContext) => React.ReactNode;
      /** How many focusable cells it has: one by default, which the grid
       * draws across the row; none for a row that only divides. */
      cells?: number;
    };

/** Where a menu opens: a point, or with a height the edge of a cell. */
type GridMenuAnchor = { x: number; y: number; height?: number };

type RowState = {
  changed?: boolean;
  refused?: boolean;
  locked?: boolean;
  current?: boolean;
};

type CellDescription = {
  text?: string;
  invalid?: boolean;
  readOnlyReason?: string;
};

type DataGridHandle = {
  /** Scrolls the row into view and focuses its cell. */
  focusCell: (key: string, column?: string) => void;
  scrollToKey: (key: string, align?: "nearest" | "start" | "center") => void;
  /** The active cell; `key` is null on the header row. */
  activeCell: () => { key: string | null; column: string } | null;
  edit: (key: string, column: string, initial?: string) => void;
};

type DataGridProps<R> = {
  ref?: React.Ref<DataGridHandle>;
  /** The grid's accessible name. */
  label: string;
  columns: readonly GridColumn<R>[];
  /** Already filtered, sorted and grouped. */
  rows: readonly GridRow<R>[];
  /** "Row 3 of 40": the start of what a keyboard move announces. */
  positionLabel: (row: number, count: number) => string;
  /** In rem; undefined has the row measured once and kept by key. Without
   * it data and section rows take the density's height and custom rows are
   * measured. */
  rowHeight?: (row: GridRow<R>) => number | undefined;
  editorForCell?: (
    key: string,
    index: number,
    context: EditorContext,
  ) => React.ReactNode | null;
  density?: "compact" | "comfortable";
  sort?: { column: string; direction: "asc" | "desc" } | null;
  onSort?: (column: string) => void;
  /** Selected row keys; leave out for a grid without row selection. */
  selection?: ReadonlySet<string>;
  onSelectionChange?: (
    next: ReadonlySet<string>,
    cause: SelectionCause,
  ) => void;
  /** Enter on a cell without an editor, or a double click. */
  onActivate?: (key: string) => void;
  /** An editor's value; null asks for the cell to be cleared. */
  onCommit?: (key: string, column: string, value: unknown) => void;
  onMenu?: (key: string, column: string | null, at: GridMenuAnchor) => void;
  onToggleSection?: (key: string) => void;
  /** The text to put on the clipboard for a range, or null for none. */
  onCopy?: (range: CellRange) => string | null;
  onPaste?: (range: CellRange, text: string) => void;
  onFill?: (range: CellRange, direction: "down" | "right") => void;
  /** In rem. */
  onColumnResize?: (column: string, width: number) => void;
  /** Every column id, in the new drawn order. */
  onColumnOrder?: (order: string[]) => void;
  rowState?: (key: string) => RowState | undefined;
  /** A hidden status for the row, read with each of its cells. */
  describeRow?: (key: string) => string | undefined;
  describeCell?: (key: string, column: string) => CellDescription | undefined;
  empty?: React.ReactNode;
  overscan?: number;
  className?: string;
};

type Active = { key: string | null; column: string };
type Editing = { key: string; column: string; initial?: string };

const HEADER_INDEX = -1;
const DRAG_SLOP_REM = 0.25;

const GridSelectionContext = React.createContext<{
  isSelected: (key: string) => boolean;
  toggle: (key: string, range: boolean) => void;
  /** The visible rows become the selection, or with `add` join it. */
  toggleAll: (add: boolean) => void;
  extent: "none" | "some" | "all";
} | null>(null);

const CellStateContext = React.createContext({ focused: false });

function rootRemPx(): number {
  return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
}

function columnLabel<R>(column: GridColumn<R>): string {
  return (
    column.label ??
    (typeof column.header === "string" ? column.header : column.id)
  );
}

function cellCount<R>(row: GridRow<R>, columns: number): number {
  if (row.kind === "data") return columns;
  if (row.kind === "section") return 1;
  return row.cells ?? 1;
}

// A cell that is the active one wears the ring inside its own edge: ink
// while the grid holds focus, the secondary text colour while it does not.
const ACTIVE_RING =
  "outline-none data-[active]:outline-(length:--focus-ring) data-[active]:outline-offset-[calc(-1*var(--focus-ring))] data-[active]:outline-muted-foreground data-[active]:outline-solid data-[active]:focus-within:outline-ring";

// A sticky cell hides what scrolls under it, so it takes the grid's surface
// and lays the row's wash over it.
const STICKY_CELL =
  "sticky z-(--layer-grid-sticky) bg-background group-hover/row:group-not-data-[selected]/row:[background-image:linear-gradient(var(--accent),var(--accent))] group-data-[selected]/row:[background-image:linear-gradient(var(--selected),var(--selected))]";

const CELL = cn(
  "relative flex h-full shrink-0 items-center overflow-hidden px-2",
  ACTIVE_RING,
  "data-[in-range]:[&_.text-faint]:text-muted-foreground",
  "forced-colors:data-[in-range]:outline-(length:--hairline) forced-colors:data-[in-range]:outline-offset-[calc(-1*var(--hairline))] forced-colors:data-[in-range]:outline-[Highlight] forced-colors:data-[in-range]:outline-solid",
);

// The first cell carries the selected row's bar on its leading edge.
const LEADING_EDGE =
  "before:absolute before:inset-y-0 before:start-0 before:w-(--selection-edge) before:bg-brand before:opacity-0 group-data-[selected]/row:before:opacity-100 forced-colors:before:bg-[Highlight] forced-colors:before:forced-color-adjust-none";

const ROW = cn(
  "group/row absolute start-0 flex border-b border-border",
  "hover:not-data-[selected]:bg-accent data-[selected]:bg-selected",
  // Faint text has no contrast to spare on a wash.
  "hover:[&_.text-faint]:text-muted-foreground data-[selected]:[&_.text-faint]:text-muted-foreground",
  "forced-colors:data-[selected]:outline-(length:--selection-edge) forced-colors:data-[selected]:outline-offset-[calc(-1*var(--selection-edge))] forced-colors:data-[selected]:outline-[Highlight] forced-colors:data-[selected]:outline-solid",
);

const ROW_HEIGHT = {
  compact: "--spacing-row-compact",
  comfortable: "--spacing-row-comfortable",
} as const;

// The edges of a range, drawn inside each cell that is on them.
function rangeShadow(
  top: boolean,
  bottom: boolean,
  start: boolean,
  end: boolean,
) {
  const ink = "var(--foreground)";
  const edges = [
    top && `inset 0 var(--hairline) 0 0 ${ink}`,
    bottom && `inset 0 calc(-1 * var(--hairline)) 0 0 ${ink}`,
    start && `inset var(--hairline) 0 0 0 ${ink}`,
    end && `inset calc(-1 * var(--hairline)) 0 0 0 ${ink}`,
  ].filter(Boolean);
  return edges.length ? edges.join(", ") : undefined;
}

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
  columns,
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
  onFill,
  onColumnResize,
  onColumnOrder,
  rowState,
  describeRow,
  describeCell,
  empty,
  overscan = 6,
  className,
}: DataGridProps<R>) {
  const gridId = React.useId();
  const scroller = React.useRef<HTMLDivElement>(null);
  const header = React.useRef<HTMLDivElement>(null);
  const [view, setView] = React.useState({
    top: 0,
    left: 0,
    height: 0,
    width: 0,
  });
  const [remPx, setRemPx] = React.useState(16);
  const [rowPx, setRowPx] = React.useState(28);
  const [headerPx, setHeaderPx] = React.useState(28);
  const [active, setActive] = React.useState<Active | null>(null);
  const [anchor, setAnchor] = React.useState<Active | null>(null);
  const [editing, setEditing] = React.useState<Editing | null>(null);
  const [focused, setFocused] = React.useState(false);
  const [announcement, setAnnouncement] = React.useState("");
  const [drop, setDrop] = React.useState<string | null>(null);
  const [measuredVersion, setMeasuredVersion] = React.useState(0);
  const measured = React.useRef(new Map<string, number>());
  const preferred = React.useRef(0);
  const selectionAnchor = React.useRef<string | null>(null);
  const suppressClick = React.useRef(false);

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
  const editable = ordered.some((column) => column.editor);

  // What the window needs in pixels: the rem, and the density's row height,
  // read from the tokens on the grid itself so a coarse pointer's taller
  // rows reach the arithmetic too.
  const readMetrics = React.useCallback(() => {
    const element = scroller.current;
    if (!element) return;
    const rem = rootRemPx();
    setRemPx(rem);
    const raw = getComputedStyle(element).getPropertyValue(ROW_HEIGHT[density]);
    const px = lengthPx(raw, rem);
    if (px) setRowPx(px);
    if (header.current) setHeaderPx(header.current.offsetHeight);
  }, [density]);

  const syncView = React.useCallback(() => {
    const element = scroller.current;
    if (!element) return;
    setView({
      top: element.scrollTop,
      left: element.scrollLeft,
      height: element.clientHeight,
      width: element.clientWidth,
    });
  }, []);

  React.useLayoutEffect(() => {
    const element = scroller.current;
    if (!element) return;
    readMetrics();
    syncView();
    const observer = new ResizeObserver(() => {
      readMetrics();
      syncView();
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [readMetrics, syncView]);

  const frame = React.useRef(0);
  const onScroll = () => {
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(syncView);
  };
  React.useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const heights = React.useMemo(() => {
    void measuredVersion;
    return rows.map((row) => {
      const declared = rowHeight ? rowHeight(row) : undefined;
      if (declared !== undefined) return declared * remPx;
      if (!rowHeight && row.kind !== "custom") return rowPx;
      return measured.current.get(row.key) ?? rowPx;
    });
  }, [rows, rowHeight, remPx, rowPx, measuredVersion]);
  const tops = React.useMemo(() => prefixSums(heights), [heights]);
  const topsRef = React.useRef(tops);
  topsRef.current = tops;
  const indexRef = React.useRef(index);
  indexRef.current = index;

  const needsMeasure = (row: GridRow<R>) =>
    rowHeight ? rowHeight(row) === undefined : row.kind === "custom";

  // A row measured for the first time, or again after it changed, keeps
  // what is above the view where it was: the scroll moves by the change.
  const observer = React.useRef<ResizeObserver | null>(null);
  const measureRef = React.useCallback((element: HTMLDivElement | null) => {
    if (!element) return;
    observer.current ??= new ResizeObserver((entries) => {
      let changed = false;
      for (const entry of entries) {
        const target = entry.target as HTMLElement;
        const key = target.dataset.key;
        if (key === undefined) continue;
        const height = entry.borderBoxSize[0]?.blockSize ?? target.offsetHeight;
        const before = measured.current.get(key);
        if (before === height) continue;
        measured.current.set(key, height);
        changed = true;
        const at = indexRef.current.get(key);
        const box = scroller.current;
        if (at !== undefined && box && before !== undefined) {
          const top = topsRef.current[at] ?? 0;
          if (top < box.scrollTop) box.scrollTop += height - before;
        }
      }
      if (changed) setMeasuredVersion((version) => version + 1);
    });
    const watcher = observer.current;
    watcher.observe(element);
    return () => watcher.unobserve(element);
  }, []);
  React.useEffect(() => () => observer.current?.disconnect(), []);

  const layout = React.useMemo(
    () => columnLayout(ordered, remPx, view.width),
    [ordered, remPx, view.width],
  );

  const bodyHeight = Math.max(0, view.height - headerPx);
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
      if (box.left < left) element.scrollLeft = box.left - layout.startCover;
      else if (box.left + box.width > right)
        element.scrollLeft =
          box.left + box.width - element.clientWidth + layout.endCover;
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
    } else setAnchor(null);
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
  }, [requested]);

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
    return parts.join(", ");
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

  const changeSelection = (next: Set<string>, cause: SelectionCause) => {
    if (!selection || !onSelectionChange) return;
    onSelectionChange(next, cause);
  };
  const pickRow = (key: string, how: { toggle?: boolean; range?: boolean }) => {
    if (!selection) return;
    if (how.range) {
      changeSelection(
        selectRange(
          dataKeys,
          selectionAnchor.current,
          key,
          how.toggle ? selection : new Set(),
        ),
        "range",
      );
      return;
    }
    selectionAnchor.current = key;
    if (how.toggle) changeSelection(toggleKey(selection, key), "toggle");
    else changeSelection(selectOnly(key), "select");
  };

  const selectionContext = React.useMemo(
    () =>
      selection
        ? {
            isSelected: (key: string) => selection.has(key),
            toggle: (key: string, range: boolean) => {
              if (!onSelectionChange) return;
              if (range)
                onSelectionChange(
                  selectRange(
                    dataKeys,
                    selectionAnchor.current,
                    key,
                    selection,
                  ),
                  "range",
                );
              else {
                selectionAnchor.current = key;
                onSelectionChange(toggleKey(selection, key), "toggle");
              }
            },
            toggleAll: (add: boolean) =>
              onSelectionChange?.(
                headerSelection(dataKeys, selection, add),
                "all",
              ),
            extent: selectionExtent(dataKeys, selection),
          }
        : null,
    [selection, onSelectionChange, dataKeys],
  );

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

  const headerKeys = (event: React.KeyboardEvent, column: string) => {
    const at = ordered.findIndex((entry) => entry.id === column);
    const named = ordered[at];
    if (!named) return false;
    const key = event.key;
    if (
      (key === "ArrowLeft" || key === "ArrowRight") &&
      exactly(event, { alt: true })
    ) {
      if (!onColumnResize || named.resizable === false) return false;
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
      if (target)
        moveTo(
          { key: target.key, column: columnAt(target, preferred.current) },
          { keyboard: true, extend },
        );
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
        if (target)
          moveTo(
            {
              key: target.key,
              column: columnAt(target, key === "Home" ? 0 : ordered.length - 1),
            },
            { keyboard: true, extend: shift },
          );
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
      else if (exactly(event, { shift: true }))
        pickRow(row.key, { range: true });
      else return false;
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
    if (exactly(event, { primary: true }) && event.code === "KeyD" && onFill) {
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
      for (const rowKey of target.rows)
        for (const columnId of target.columns)
          if (editorFor(rowKey, columnId) !== null)
            onCommit(rowKey, columnId, null);
      return true;
    }
    if (key === "Escape" && anchor) {
      setAnchor(null);
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
    edit: (key, column, initial) => {
      const row = rows[index.get(key) ?? -1];
      if (!row) return;
      moveTo({ key, column }, { focus: false });
      startEdit(key, column, initial);
    },
  }));

  // ── Pointer: columns ──────────────────────────────────────────────────
  const startResize = (
    event: React.PointerEvent<HTMLDivElement>,
    column: GridColumn<R>,
  ) => {
    if (event.button !== 0 || !onColumnResize) return;
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
    if (!element || !onColumnResize) return;
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
  // Where columns scroll under a pinned group, the group's inner edge shows,
  // so nothing seems to begin mid-word.
  const lastStart = ordered
    .filter((column) => column.sticky === "start")
    .at(-1)?.id;
  const firstEnd = ordered.find((column) => column.sticky === "end")?.id;
  const pinnedEdge = (id: string) =>
    cn(
      id === lastStart && view.left > 0 && "border-e border-border",
      id === firstEnd &&
        view.left + view.width < layout.total - 1 &&
        "border-s border-border",
    );
  const stickyStyle = (id: string): React.CSSProperties => {
    const placed = layout.byId.get(id);
    if (!placed?.sticky) return {};
    return placed.sticky === "start"
      ? { insetInlineStart: placed.inset }
      : { insetInlineEnd: placed.inset };
  };
  const isStop = (at: number, column: string) =>
    resolvedIndex === at && resolved?.column === column;

  const headerRow = (
    <div
      ref={header}
      role="rowgroup"
      className="sticky top-0 z-(--layer-grid-head) bg-background"
      style={{ width: layout.total }}
    >
      <div
        role="row"
        aria-rowindex={1}
        className="flex h-(--grid-row) border-b border-border-strong"
      >
        {ordered.map((column, at) => {
          const sorted = sort?.column === column.id ? sort.direction : null;
          const width = layout.byId.get(column.id)?.width ?? 0;
          const active = isStop(HEADER_INDEX, column.id);
          return (
            <div
              key={column.id}
              id={cellId(HEADER_INDEX, String(at))}
              role="columnheader"
              aria-colindex={at + 1}
              aria-sort={
                sorted === "asc"
                  ? "ascending"
                  : sorted === "desc"
                    ? "descending"
                    : column.sortable
                      ? "none"
                      : undefined
              }
              tabIndex={active ? 0 : -1}
              data-slot="data-grid-header-cell"
              data-header-column={column.id}
              data-active={active || undefined}
              data-drop={drop === column.id || undefined}
              className={cn(
                "relative flex h-full shrink-0 items-center gap-1 px-2 text-xs font-medium text-muted-foreground select-none",
                ACTIVE_RING,
                column.align === "end" && "justify-end text-end",
                column.sortable &&
                  onSort &&
                  "cursor-pointer hover:text-foreground",
                column.sticky &&
                  "sticky z-(--layer-grid-head-sticky) bg-background",
                pinnedEdge(column.id),
                "data-[drop]:shadow-[inset_var(--selection-edge)_0_0_0_var(--ring)] forced-colors:data-[drop]:outline-[Highlight] forced-colors:data-[drop]:outline-solid",
              )}
              style={{ width, ...stickyStyle(column.id) }}
              onPointerDown={(event) => {
                moveTo({ key: null, column: column.id });
                if (!column.sticky) startReorder(event, column);
              }}
              onClick={() => {
                if (suppressClick.current) {
                  suppressClick.current = false;
                  return;
                }
                if (column.sortable) onSort?.(column.id);
              }}
            >
              <span className="min-w-0 truncate">{column.header}</span>
              {sorted && (
                <Icon
                  name={sorted === "asc" ? "sortAsc" : "sortDesc"}
                  size="xs"
                />
              )}
              {onColumnResize && column.resizable !== false && (
                <div
                  role="separator"
                  aria-orientation="vertical"
                  aria-valuemin={column.minWidth ?? MIN_COLUMN_REM}
                  aria-valuemax={Math.max(100, Math.ceil(width / remPx))}
                  aria-valuenow={Math.round((width / remPx) * 4) / 4}
                  className="absolute inset-y-0 end-0 w-2 cursor-col-resize touch-none after:absolute after:inset-y-1 after:end-0 after:w-px after:bg-border hover:after:bg-ring"
                  onPointerDown={(event) => startResize(event, column)}
                  onClick={(event) => event.stopPropagation()}
                  onDoubleClick={(event) => {
                    event.stopPropagation();
                    fitColumn(column);
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

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

  const statusId = (at: number) => cellId(at, "status");

  const drawRow = (at: number) => {
    const row = rows[at];
    if (!row) return null;
    const top = tops[at] ?? 0;
    const measure = needsMeasure(row);
    const height = measure ? undefined : heights[at];
    const status = describeRow?.(row.key);
    const state = rowState?.(row.key);
    const tokens = state
      ? (["changed", "refused", "locked"] as const).filter(
          (name) => state[name],
        )
      : [];
    const selected = row.kind === "data" && !!selection?.has(row.key);
    const common = {
      role: "row" as const,
      "aria-rowindex": at + 2,
      "aria-selected": row.kind === "data" && selection ? selected : undefined,
      "aria-current": state?.current || undefined,
      "data-slot": "data-grid-row",
      "data-key": row.key,
      "data-kind": row.kind,
      "data-selected": selected || undefined,
      "data-state": tokens.length ? tokens.join(" ") : undefined,
      ref: measure ? measureRef : undefined,
      className: ROW,
      style: { top, height, width: layout.total },
    };
    const statusNode = status ? (
      <span hidden id={statusId(at)}>
        {status}
      </span>
    ) : null;
    const described = (extra?: string) =>
      [status ? statusId(at) : null, extra].filter(Boolean).join(" ") ||
      undefined;

    if (row.kind === "data") {
      return (
        <div key={row.key} {...common}>
          {ordered.map((column, position) => {
            const id = cellId(at, String(position));
            const activeHere = isStop(at, column.id);
            const note = describeCell?.(row.key, column.id);
            const reason =
              note?.readOnlyReason ?? column.readOnlyReason?.(row.data);
            const readOnly = editable && (!!reason || !column.editor);
            const ranged = box ? inBox(box, at, position) : false;
            const isEditing =
              editing?.key === row.key && editing.column === column.id;
            const editor = isEditing
              ? editorFor(row.key, column.id, editing.initial)
              : null;
            const noteId = `${id}-note`;
            const noteText = [note?.text, reason].filter(Boolean).join(", ");
            return (
              <div
                key={column.id}
                id={id}
                role="gridcell"
                aria-colindex={position + 1}
                aria-describedby={described(noteText ? noteId : undefined)}
                aria-invalid={note?.invalid || undefined}
                aria-readonly={readOnly || undefined}
                tabIndex={activeHere ? 0 : -1}
                data-slot="data-grid-cell"
                data-column={column.id}
                data-active={activeHere || undefined}
                data-in-range={ranged || undefined}
                className={cn(
                  CELL,
                  position === 0 && LEADING_EDGE,
                  column.align === "end" && "justify-end text-end tabular-nums",
                  column.sticky && STICKY_CELL,
                  pinnedEdge(column.id),
                )}
                style={{
                  width: layout.byId.get(column.id)?.width,
                  boxShadow:
                    ranged && box
                      ? rangeShadow(
                          at === box.top,
                          at === box.bottom,
                          position === box.start,
                          position === box.end,
                        )
                      : undefined,
                  ...stickyStyle(column.id),
                }}
                onPointerDown={(event) => pointerCell(event, row, column.id)}
                onClick={(event) => clickCell(event, row)}
                onDoubleClick={() => doubleCell(row, column.id)}
                onContextMenu={(event) => menuCell(event, row, column.id)}
              >
                {editor !== null ? (
                  <div className="absolute inset-0 z-(--layer-grid-editor) flex">
                    {editor}
                  </div>
                ) : (
                  <CellStateContext.Provider
                    value={activeHere && focused ? FOCUSED : UNFOCUSED}
                  >
                    {column.cell(row.data, {
                      key: row.key,
                      active: activeHere,
                      selected,
                    })}
                  </CellStateContext.Provider>
                )}
                {noteText && (
                  <span hidden id={noteId}>
                    {noteText}
                  </span>
                )}
              </div>
            );
          })}
          {statusNode}
        </div>
      );
    }

    // A section or a one-cell custom row is one cell across the grid, kept
    // in view while the grid scrolls sideways.
    const count = cellCount(row, ordered.length);
    if (row.kind === "section" || count <= 1) {
      const id = cellId(at, "s");
      const activeHere = isStop(at, "");
      const isEditing = editing?.key === row.key && editing.column === "";
      const editor =
        isEditing && row.kind === "custom"
          ? editorFor(row.key, "0", editing.initial)
          : null;
      return (
        <div key={row.key} {...common}>
          <div
            id={id}
            role="gridcell"
            aria-colindex={1}
            aria-colspan={ordered.length || 1}
            aria-expanded={row.kind === "section" ? !row.collapsed : undefined}
            aria-describedby={described()}
            tabIndex={count > 0 ? (activeHere ? 0 : -1) : undefined}
            data-slot="data-grid-cell"
            data-active={activeHere || undefined}
            className={cn(
              CELL,
              "sticky start-0 z-(--layer-grid-sticky)",
              row.kind === "section" && "gap-2 font-medium",
            )}
            style={{ width: view.width || layout.total }}
            onPointerDown={
              count > 0 ? (event) => pointerCell(event, row, "") : undefined
            }
            onClick={
              row.kind === "section"
                ? () => onToggleSection?.(row.key)
                : undefined
            }
            onDoubleClick={
              row.kind === "custom" ? () => doubleCell(row, "") : undefined
            }
            onContextMenu={(event) => menuCell(event, row, null)}
          >
            {row.kind === "section" ? (
              <>
                <span
                  className="flex min-w-0 flex-1 items-center gap-2"
                  style={{
                    paddingInlineStart: `calc(var(--spacing) * ${4 * (row.depth ?? 0)})`,
                  }}
                >
                  <Icon
                    name={row.collapsed ? "forward" : "chevronDown"}
                    size="xs"
                  />
                  <span className="min-w-0 truncate">{row.label}</span>
                  {row.hint && (
                    <span className="min-w-0 truncate font-normal text-muted-foreground">
                      {row.hint}
                    </span>
                  )}
                </span>
                {row.summary && (
                  <span className="shrink-0 text-muted-foreground">
                    {row.summary}
                  </span>
                )}
              </>
            ) : editor !== null ? (
              <div className="absolute inset-0 z-(--layer-grid-editor) flex">
                {editor}
              </div>
            ) : (
              row.render(customContext(at, row, count))
            )}
          </div>
          {statusNode}
        </div>
      );
    }
    return (
      <div key={row.key} {...common}>
        {row.render(customContext(at, row, count))}
        {statusNode}
      </div>
    );
  };

  function customContext(
    at: number,
    row: Extract<GridRow<R>, { kind: "custom" }>,
    count: number,
  ): RowContext {
    const activeHere = resolvedIndex === at;
    const status = describeRow?.(row.key) ? statusId(at) : undefined;
    const editingCell =
      editing?.key === row.key && count > 1
        ? Number(editing.column) || 0
        : null;
    return {
      key: row.key,
      active: activeHere,
      activeCell:
        activeHere && count > 1 ? Number(resolved?.column) || 0 : null,
      editingCell,
      editor:
        editingCell !== null && editing
          ? editorFor(row.key, editing.column, editing.initial)
          : null,
      cellProps: (cell) => {
        const column = String(cell);
        const here = isStop(at, column);
        return {
          id: cellId(at, `x${column}`),
          role: "gridcell",
          tabIndex: here ? 0 : -1,
          "aria-colindex": cell + 1,
          "aria-describedby": status,
          "data-slot": "data-grid-cell",
          "data-active": here || undefined,
          className: CELL,
          onPointerDown: (event) => pointerCell(event, row, column),
          onDoubleClick: () => doubleCell(row, column),
          onContextMenu: (event) => menuCell(event, row, null),
        };
      },
    };
  }

  return (
    <GridSelectionContext.Provider value={selectionContext}>
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
              !event.currentTarget.contains(event.relatedTarget as Node | null)
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
            onPaste(target, event.clipboardData.getData("text/plain"));
          }}
        >
          {headerRow}
          <div
            role="rowgroup"
            className="relative"
            style={{ height: tops[rows.length] ?? 0, width: layout.total }}
          >
            {shown.map(drawRow)}
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
    </GridSelectionContext.Provider>
  );
}

const FOCUSED = { focused: true };
const UNFOCUSED = { focused: false };

/**
 * Text that ends in an ellipsis where its cell is too narrow, and then shows
 * whole in the shared tooltip under the pointer and while its cell has focus.
 * Text that fits shows no tooltip.
 */
function DataGridText({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const { focused } = React.useContext(CellStateContext);
  const [hover, setHover] = React.useState(false);
  const [truncated, setTruncated] = React.useState(false);
  const [dismissed, setDismissed] = React.useState(false);
  const measure = () => {
    const element = ref.current;
    setTruncated(!!element && element.scrollWidth > element.clientWidth);
  };
  React.useLayoutEffect(() => {
    setDismissed(false);
    if (focused) measure();
  }, [focused, children]);
  const span = (
    <span
      ref={ref}
      data-slot="data-grid-text"
      className={cn("min-w-0 truncate", className)}
      onPointerEnter={() => {
        measure();
        setHover(true);
      }}
      onPointerLeave={() => setHover(false)}
    >
      {children}
    </span>
  );
  if (!truncated || dismissed || !(hover || focused)) return span;
  return (
    <Tooltip
      open
      onOpenChange={(open) => {
        if (open) return;
        setHover(false);
        setDismissed(true);
      }}
    >
      <TooltipTrigger asChild>{span}</TooltipTrigger>
      <TooltipContent>{children}</TooltipContent>
    </Tooltip>
  );
}

/**
 * A text editor for a cell. It opens holding the typed character, or the
 * whole value selected; Enter, Tab and Shift+Tab commit and Escape cancels.
 * Leaving it by the pointer commits a changed value and drops an unchanged
 * one.
 */
function DataGridTextEditor({
  context,
  defaultValue,
  className,
  ...props
}: Omit<
  React.ComponentProps<"input">,
  "defaultValue" | "value" | "onChange" | "onKeyDown" | "onBlur"
> & {
  context: EditorContext;
  defaultValue: string;
}) {
  const input = React.useRef<HTMLInputElement>(null);
  const [value, setValue] = React.useState(context.initial ?? defaultValue);
  const done = React.useRef(false);
  React.useLayoutEffect(() => {
    const element = input.current;
    if (!element) return;
    element.focus({ preventScroll: true });
    if (context.initial === undefined) element.select();
    else element.setSelectionRange(element.value.length, element.value.length);
  }, [context.initial]);
  return (
    <input
      ref={input}
      data-slot="data-grid-editor"
      aria-label={context.label}
      aria-describedby={context.describedBy}
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={(event) => {
        const how = commitKeyOf(event);
        if (!how) return;
        event.preventDefault();
        event.stopPropagation();
        done.current = true;
        if (how === "cancel") context.cancel();
        else context.commit(value, how);
      }}
      onBlur={() => {
        if (done.current) return;
        done.current = true;
        if (value === defaultValue && context.initial === undefined)
          context.cancel(false);
        else context.commit(value, "pointer");
      }}
      className={cn(
        inputVariants({ controlSize: "sm" }),
        "h-full rounded-none border-ring",
        className,
      )}
      {...props}
    />
  );
}

/** A row's selection box, the pointer's way to the keyboard's Space. Shift
 * extends from the last row chosen. */
function DataGridRowCheckbox({
  rowKey,
  label,
}: {
  rowKey: string;
  label: string;
}) {
  const grid = React.useContext(GridSelectionContext);
  if (!grid) return null;
  return (
    <Checkbox
      tabIndex={-1}
      aria-label={label}
      checked={grid.isSelected(rowKey)}
      onClick={(event) => event.stopPropagation()}
      onChange={(event) =>
        grid.toggle(rowKey, (event.nativeEvent as MouseEvent).shiftKey)
      }
    />
  );
}

/** The header's box: every row, or none. */
function DataGridSelectAll({ label }: { label: string }) {
  const grid = React.useContext(GridSelectionContext);
  const box = React.useRef<HTMLInputElement>(null);
  // The change event carries no modifiers; the click before it does.
  const adding = React.useRef(false);
  React.useEffect(() => {
    if (box.current) box.current.indeterminate = grid?.extent === "some";
  }, [grid?.extent]);
  if (!grid) return null;
  return (
    <Checkbox
      ref={box}
      tabIndex={-1}
      aria-label={label}
      checked={grid.extent === "all"}
      onClick={(event) => {
        event.stopPropagation();
        adding.current = exactly(event, { primary: true });
      }}
      onChange={() => {
        grid.toggleAll(adding.current);
        adding.current = false;
      }}
    />
  );
}

type TableColumn<R> = {
  id: string;
  header: React.ReactNode;
  /** In rem; leave out to share what is left. */
  width?: number;
  align?: "start" | "end";
  sortable?: boolean;
  cell: (row: R) => React.ReactNode;
};

type TableRow<R> =
  | { kind: "data"; key: string; data: R }
  | {
      kind: "section";
      key: string;
      label: React.ReactNode;
      /** A quieter line beside the label: what the section holds. */
      hint?: React.ReactNode;
      /** At the trailing edge: a count or a total. */
      summary?: React.ReactNode;
    };

/**
 * The plain table, for a short list that is read and opened rather than
 * edited: real table semantics, sortable headers, sections as row groups.
 * With `onActivate` its rows are one tab stop, moved through with the arrow
 * keys, Home and End; Enter or a click opens a row.
 */
function DataTable<R>({
  label,
  columns,
  rows,
  sort,
  onSort,
  onActivate,
  current,
  empty,
  density = "compact",
  className,
}: {
  label: string;
  columns: readonly TableColumn<R>[];
  rows: readonly TableRow<R>[];
  sort?: { column: string; direction: "asc" | "desc" } | null;
  onSort?: (column: string) => void;
  onActivate?: (key: string) => void;
  /** The key of the row that is open elsewhere. It is marked by key, so the
   * mark stays with the row through a new sort or grouping. */
  current?: string | null;
  empty?: React.ReactNode;
  density?: "compact" | "comfortable";
  className?: string;
}) {
  const tableId = React.useId();
  const [focusKey, setFocusKey] = React.useState<string | null>(null);
  const keys = rows.flatMap((row) => (row.kind === "data" ? [row.key] : []));
  const stop =
    focusKey !== null && keys.includes(focusKey)
      ? focusKey
      : current && keys.includes(current)
        ? current
        : (keys[0] ?? null);
  const rowId = (key: string) => `${tableId}-${keys.indexOf(key)}`;
  const focusRow = (key: string | undefined) => {
    if (key === undefined) return;
    setFocusKey(key);
    document.getElementById(rowId(key))?.focus();
  };

  // Rows before the first section form a group of their own.
  const groups: {
    section: Extract<TableRow<R>, { kind: "section" }> | null;
    rows: Extract<TableRow<R>, { kind: "data" }>[];
  }[] = [];
  for (const row of rows) {
    const last = groups.at(-1);
    if (row.kind === "section") groups.push({ section: row, rows: [] });
    else if (last) last.rows.push(row);
    else groups.push({ section: null, rows: [row] });
  }

  return (
    <table
      data-slot="data-table"
      aria-label={label}
      className={cn(
        "w-full border-collapse text-base text-foreground",
        density === "compact"
          ? "[--grid-row:var(--spacing-row-compact)]"
          : "[--grid-row:var(--spacing-row-comfortable)]",
        className,
      )}
    >
      <colgroup>
        {columns.map((column) => (
          <col
            key={column.id}
            style={
              column.width === undefined
                ? undefined
                : { width: `${column.width}rem` }
            }
          />
        ))}
      </colgroup>
      <thead className="sticky top-0 z-(--layer-grid-head) bg-background">
        <tr>
          {columns.map((column) => {
            const sorted = sort?.column === column.id ? sort.direction : null;
            const sortable = column.sortable && onSort;
            return (
              <th
                key={column.id}
                scope="col"
                aria-sort={
                  sorted === "asc"
                    ? "ascending"
                    : sorted === "desc"
                      ? "descending"
                      : sortable
                        ? "none"
                        : undefined
                }
                className={cn(
                  "h-(--grid-row) border-b border-border-strong px-2 text-start text-xs font-medium text-muted-foreground",
                  column.align === "end" && "text-end",
                )}
              >
                {sortable ? (
                  <button
                    type="button"
                    className="inline-flex cursor-pointer items-center gap-1 rounded-xs hover:text-foreground"
                    onClick={() => onSort(column.id)}
                  >
                    {column.header}
                    {sorted && (
                      <Icon
                        name={sorted === "asc" ? "sortAsc" : "sortDesc"}
                        size="xs"
                      />
                    )}
                  </button>
                ) : (
                  column.header
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      {groups.map((group, at) => (
        <tbody key={group.section?.key ?? `lead-${at}`}>
          {group.section && (
            <tr data-slot="data-table-section">
              <th
                scope="rowgroup"
                colSpan={columns.length}
                className="h-(--grid-row) border-b border-border px-2 text-start text-sm font-medium"
              >
                <span className="flex items-baseline justify-between gap-2">
                  <span className="flex flex-wrap items-baseline gap-x-2">
                    <span>{group.section.label}</span>
                    {group.section.hint && (
                      <span className="font-normal text-muted-foreground">
                        {group.section.hint}
                      </span>
                    )}
                  </span>
                  {group.section.summary && (
                    <span className="font-normal text-muted-foreground">
                      {group.section.summary}
                    </span>
                  )}
                </span>
              </th>
            </tr>
          )}
          {group.rows.map((row) => (
            <tr
              key={row.key}
              id={rowId(row.key)}
              data-slot="data-table-row"
              aria-current={current === row.key || undefined}
              tabIndex={onActivate ? (stop === row.key ? 0 : -1) : undefined}
              className={cn(
                "group/row outline-none",
                onActivate &&
                  "cursor-pointer hover:bg-accent focus-visible:outline-(length:--focus-ring) focus-visible:outline-offset-[calc(-1*var(--focus-ring))] focus-visible:outline-ring focus-visible:outline-solid",
                "aria-[current=true]:bg-selected aria-[current=true]:[&_.text-faint]:text-muted-foreground hover:[&_.text-faint]:text-muted-foreground",
                "forced-colors:aria-[current=true]:outline-(length:--selection-edge) forced-colors:aria-[current=true]:outline-offset-[calc(-1*var(--selection-edge))] forced-colors:aria-[current=true]:outline-[Highlight] forced-colors:aria-[current=true]:outline-solid",
              )}
              onFocus={() => setFocusKey(row.key)}
              onClick={onActivate ? () => onActivate(row.key) : undefined}
              onKeyDown={
                onActivate
                  ? (event) => {
                      if (
                        event.target !== event.currentTarget ||
                        !exactly(event)
                      )
                        return;
                      const at = keys.indexOf(row.key);
                      if (event.key === "ArrowDown") focusRow(keys[at + 1]);
                      else if (event.key === "ArrowUp") focusRow(keys[at - 1]);
                      else if (event.key === "Home") focusRow(keys[0]);
                      else if (event.key === "End") focusRow(keys.at(-1));
                      else if (event.key === "Enter") onActivate(row.key);
                      else return;
                      event.preventDefault();
                    }
                  : undefined
              }
            >
              {columns.map((column, position) => (
                <td
                  key={column.id}
                  className={cn(
                    "relative h-(--grid-row) border-b border-border px-2",
                    column.align === "end" && "text-end tabular-nums",
                    position === 0 &&
                      "before:absolute before:inset-y-0 before:start-0 before:w-(--selection-edge) before:bg-brand before:opacity-0 group-aria-[current=true]/row:before:opacity-100 forced-colors:before:bg-[Highlight] forced-colors:before:forced-color-adjust-none",
                  )}
                >
                  {column.cell(row.data)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      ))}
      {keys.length === 0 && empty && (
        <tbody>
          <tr>
            <td colSpan={columns.length}>{empty}</td>
          </tr>
        </tbody>
      )}
    </table>
  );
}

export {
  DataGrid,
  DataGridRowCheckbox,
  DataGridSelectAll,
  DataGridText,
  DataGridTextEditor,
  DataTable,
  type CellContext,
  type CellDescription,
  type CustomCellProps,
  type DataGridHandle,
  type DataGridProps,
  type EditorContext,
  type GridColumn,
  type GridMenuAnchor,
  type GridRow,
  type RowContext,
  type RowState,
  type TableColumn,
  type TableRow,
};
