import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent as ReactClipboardEvent,
  type HTMLAttributes,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { clsx as cx } from "clsx";
import { Icon } from "./Icon";
import { isShellChord } from "./Primitives";

/* ── ui/data-grid: a windowed, keyboard-first grid. It knows rows by a
   stable key and nothing of what they mean. Rows may differ in height and
   kind: a 'row' kind renders cells per column, any other kind renders one
   full-width cell (a heading, a group, an official grid). Focus is roving:
   the active cell is the one tab stop, kept mounted while scrolled away.
   The header row is navigable (ArrowUp from the first row): Enter or
   Space sorts, Ctrl+Left/Right reorders, Alt+Left/Right resizes. Tab
   leaves the grid. `describeRow` feeds a hidden per-row description that
   every cell references; `announce` speaks the active cell when it moves.
   `apiRef.current.jumpTo(key, col)` scrolls a row into view and focuses it. */
export const HEAD = "__head";

export type GridColumn = {
  key: string;
  width: number;
  header: ReactNode;
  flex?: number;
  minWidth?: number;
  sticky?: boolean;
  lastSticky?: boolean;
  num?: boolean;
  sortable?: boolean;
  sortDir?: "asc" | "desc" | null;
  skipNav?: boolean;
  resizable?: boolean;
  cellClass?: string;
  headerTip?: string;
};
export type GridItem = {
  key: string;
  kind: string;
  height?: number;
  navigable?: boolean;
};
export type GridApi = {
  jumpTo: (key: string, col?: string) => boolean;
  focus: () => void;
  scrollToTop: () => void;
  element: () => HTMLDivElement | null;
};
export type GridActive = { key: string; col: string };
export type MoveInfo = { via?: string; extend?: boolean };
type DataAttrs = {
  [K in `data-${string}`]?: string | number | boolean | undefined;
};
export type CellAttrs = HTMLAttributes<HTMLDivElement> & DataAttrs;
export type GridRange = { from: string; to: string; c0: string; c1: string };

export type DataGridProps<T extends GridItem> = {
  items: T[];
  columns: GridColumn[];
  rowHeight: number;
  renderCell?: (it: T, c: GridColumn, state: { active: boolean }) => ReactNode;
  renderFull?: (it: T, state: { active: boolean }) => ReactNode;
  cellAttrs?: (it: T, c: GridColumn) => CellAttrs;
  rowAttrs?: (it: T) => CellAttrs;
  active?: GridActive | null;
  onActive: (key: string, col: string, info: MoveInfo) => void;
  onKeyDown?: (
    e: ReactKeyboardEvent<HTMLDivElement>,
    at: { item: T | undefined; col: string | undefined; index: number },
  ) => boolean | void;
  onCellPointerDown?: (
    e: ReactPointerEvent<HTMLDivElement>,
    it: T,
    c: GridColumn | null,
  ) => boolean | void;
  onCellDoubleClick?: (
    e: ReactMouseEvent<HTMLDivElement>,
    it: T,
    c: GridColumn,
  ) => void;
  onHeaderClick?: (
    c: GridColumn,
    e: ReactMouseEvent | ReactKeyboardEvent,
  ) => void;
  onResize?: (key: string, width: number) => void;
  onReorder?: (from: string, to: string, after?: boolean) => void;
  onCopy?: (e: ReactClipboardEvent<HTMLDivElement>) => void;
  onPaste?: (e: ReactClipboardEvent<HTMLDivElement>) => void;
  onContextMenu?: (e: ReactMouseEvent<HTMLDivElement>, it: T) => void;
  apiRef?: RefObject<GridApi | null>;
  label: string;
  overscan?: number;
  headerHeight?: number;
  editing?: boolean;
  className?: string;
  emptyNode?: ReactNode;
  describeRow?: (it: T) => string;
  describeCell?: (it: T, c: GridColumn) => string | null | undefined;
  range?: GridRange | null;
  announce?: (it: T, col: string | undefined, index: number) => void;
};

export function DataGrid<T extends GridItem>(props: DataGridProps<T>) {
  const {
    items,
    columns,
    rowHeight,
    renderCell,
    renderFull,
    cellAttrs,
    rowAttrs,
    active,
    onActive,
    onKeyDown,
    onCellPointerDown,
    onCellDoubleClick,
    onHeaderClick,
    onResize,
    onReorder,
    onCopy,
    onPaste,
    onContextMenu,
    apiRef,
    label,
    overscan = 6,
    headerHeight,
    editing,
    className,
    emptyNode,
    describeRow,
    describeCell,
    range,
  } = props;
  const ref = useRef<HTMLDivElement>(null);
  const [vp, setVp] = useState({ top: 0, h: 600, left: 0, w: 900 });
  const wantFocus = useRef(false);
  const headH = headerHeight || 32;

  const layout = useMemo(() => {
    const tops = new Array<number>(items.length);
    const index = new Map<string, number>();
    let y = 0;
    items.forEach((it, i) => {
      tops[i] = y;
      y += it.height || rowHeight;
      index.set(it.key, i);
    });
    return { tops, total: y, index };
  }, [items, rowHeight]);
  // Flexible columns share what the fixed ones leave, above their minimum.
  const cols = useMemo(() => {
    const fixed = columns.reduce((s, c) => s + (c.flex ? 0 : c.width), 0);
    const flexSum = columns.reduce((s, c) => s + (c.flex || 0), 0);
    const free = Math.max(0, (vp.w || 900) - fixed - 2);
    return columns.map((c) =>
      c.flex
        ? {
            ...c,
            width: Math.max(
              c.minWidth || c.width,
              Math.floor((free * c.flex) / flexSum),
            ),
          }
        : c,
    );
  }, [columns, vp.w]);
  const colLayout = useMemo(() => {
    let x = 0;
    const left: Record<string, number> = {};
    let stickyW = 0;
    cols.forEach((c) => {
      left[c.key] = x;
      x += c.width;
      if (c.sticky) stickyW = x;
    });
    return { left, total: x, stickyW };
  }, [cols]);
  const heightAt = (i: number) => items[i]!.height || rowHeight;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() =>
      setVp((v) => ({ ...v, h: el.clientHeight, w: el.clientWidth })),
    );
    ro.observe(el);
    setVp({
      top: el.scrollTop,
      h: el.clientHeight,
      left: el.scrollLeft,
      w: el.clientWidth,
    });
    return () => ro.disconnect();
  }, []);
  const raf = useRef(0);
  const onScroll = () => {
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => {
      const el = ref.current;
      if (el)
        setVp({
          top: el.scrollTop,
          h: el.clientHeight,
          left: el.scrollLeft,
          w: el.clientWidth,
        });
    });
  };

  const { tops, total } = layout;
  let first = 0,
    lo = 0,
    hi = items.length - 1;
  const top = Math.max(0, vp.top - headH);
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (tops[mid]! + heightAt(mid) <= top) lo = mid + 1;
    else {
      first = mid;
      hi = mid - 1;
    }
  }
  if (lo > items.length - 1) first = items.length;
  let last = first;
  while (last < items.length && tops[last]! < top + vp.h) last++;
  const start = Math.max(0, first - overscan),
    end = Math.min(items.length, last + overscan);
  const shown: number[] = [];
  for (let i = start; i < end; i++) shown.push(i);
  const onHead = active?.key === HEAD;
  const activeIdx =
    active && !onHead ? layout.index.get(active.key) : undefined;
  if (activeIdx != null && (activeIdx < start || activeIdx >= end))
    shown.push(activeIdx);

  const navigable = (i: number) => !!items[i] && items[i].navigable !== false;
  const cellId = (key: string, col: string) =>
    `cell-${key}-${col}`.replace(/[^a-zA-Z0-9_-]/g, "_");
  const descId = (key: string) =>
    `rowdesc-${key}`.replace(/[^a-zA-Z0-9_-]/g, "_");

  const ensureVisible = (i: number | null, colKey: string | undefined) => {
    const el = ref.current;
    if (!el) return;
    if (i != null) {
      const t = tops[i]!,
        b = t + heightAt(i);
      if (t < el.scrollTop) el.scrollTop = t;
      else if (b > el.scrollTop + el.clientHeight - headH)
        el.scrollTop = b - (el.clientHeight - headH);
    }
    const c = cols.find((x) => x.key === colKey);
    if (c && !c.sticky && (i == null || items[i]!.kind === "row")) {
      const l = colLayout.left[c.key]!,
        r = l + c.width;
      if (l < el.scrollLeft + colLayout.stickyW)
        el.scrollLeft = l - colLayout.stickyW;
      else if (r > el.scrollLeft + el.clientWidth)
        el.scrollLeft = r - el.clientWidth;
    }
  };
  const move = (
    i: number | typeof HEAD | null | undefined,
    colKey: string | undefined,
    info: MoveInfo = {},
  ) => {
    if (i === HEAD) {
      wantFocus.current = true;
      ensureVisible(null, colKey);
      onActive(HEAD, colKey ?? "", info);
      return;
    }
    if (i == null || !items[i]) return;
    wantFocus.current = true;
    ensureVisible(i, colKey);
    onActive(items[i].key, colKey ?? "", info);
    if (info.via === "key" && props.announce)
      props.announce(items[i], colKey, i);
  };
  const nextNav = (i: number, d: number) => {
    let j = i + d;
    while (j >= 0 && j < items.length && !navigable(j)) j += d;
    return j >= 0 && j < items.length ? j : i;
  };
  const firstNav = () => items.findIndex((_, k) => navigable(k));

  useEffect(() => {
    if (!active || !wantFocus.current) return;
    wantFocus.current = false;
    if (
      ref.current
        ?.closest(".ledger-proto")
        ?.querySelector('[aria-modal="true"]')
    )
      return;
    const row = activeIdx != null ? items[activeIdx] : undefined;
    const el = document.getElementById(
      onHead
        ? "hcell-" + active.col
        : row?.kind === "row"
          ? cellId(active.key, active.col ?? "")
          : cellId(active.key, "_full"),
    );
    if (el && !editing) el.focus({ preventScroll: true });
  });
  useEffect(() => {
    if (!apiRef) return;
    apiRef.current = {
      jumpTo(key, col) {
        const i = layout.index.get(key);
        if (i == null) return false;
        move(i, col || active?.col || cols[1]?.key, { via: "jump" });
        return true;
      },
      focus() {
        wantFocus.current = true;
        if (active) {
          const i = onHead ? HEAD : layout.index.get(active.key);
          if (i != null) {
            if (i !== HEAD) ensureVisible(i, active.col);
            onActive(active.key, active.col, { via: "focus" });
            return;
          }
        }
        const f = firstNav();
        if (f >= 0) move(f, cols.find((c) => !c.skipNav)?.key);
      },
      scrollToTop() {
        if (ref.current) ref.current.scrollTop = 0;
      },
      element: () => ref.current,
    };
  });

  const handleKey = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (isShellChord(e.nativeEvent)) return; // the window's own chords pass through untouched
    if (editing) return;
    const ctrl = e.ctrlKey || e.metaKey;
    const navCols = cols.filter((c) => !c.skipNav);
    const nci = Math.max(
      0,
      navCols.findIndex((c) => c.key === active?.col),
    );
    if (onHead) {
      const c = navCols[nci]!;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        const f = firstNav();
        if (f >= 0) move(f, c.key, { via: "key" });
      } else if (e.key === "ArrowRight" && !ctrl && !e.altKey) {
        e.preventDefault();
        move(HEAD, navCols[Math.min(navCols.length - 1, nci + 1)]!.key);
      } else if (e.key === "ArrowLeft" && !ctrl && !e.altKey) {
        e.preventDefault();
        move(HEAD, navCols[Math.max(0, nci - 1)]!.key);
      } else if (e.key === "Home") {
        e.preventDefault();
        move(HEAD, navCols[0]!.key);
      } else if (e.key === "End") {
        e.preventDefault();
        move(HEAD, navCols[navCols.length - 1]!.key);
      } else if (
        (e.key === "Enter" || e.key === " ") &&
        c.sortable &&
        onHeaderClick
      ) {
        e.preventDefault();
        onHeaderClick(c, e);
      } else if (
        ctrl &&
        !e.shiftKey &&
        (e.key === "ArrowLeft" || e.key === "ArrowRight") &&
        onReorder &&
        !c.sticky
      ) {
        e.preventDefault();
        const j = nci + (e.key === "ArrowLeft" ? -1 : 1);
        const other = navCols[j];
        if (other && !other.sticky)
          onReorder(c.key, other.key, e.key === "ArrowRight");
      } else if (
        e.altKey &&
        (e.key === "ArrowLeft" || e.key === "ArrowRight") &&
        onResize &&
        c.resizable !== false
      ) {
        e.preventDefault();
        onResize(
          c.key,
          Math.max(
            c.minWidth || 48,
            c.width + (e.key === "ArrowLeft" ? -24 : 24),
          ),
        );
      }
      return;
    }
    const i = activeIdx ?? -1;
    const item = items[i];
    if (onKeyDown && onKeyDown(e, { item, col: active?.col, index: i })) return;
    if (e.defaultPrevented) return;
    const page = Math.max(
      1,
      Math.floor((ref.current!.clientHeight - headH) / rowHeight) - 1,
    );
    const info = { extend: e.shiftKey, via: "key" };
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (i < 0) return move(firstNav(), navCols[0]?.key, info);
        move(nextNav(i, 1), active?.col, info);
        break;
      case "ArrowUp":
        e.preventDefault();
        if (i <= firstNav() && !e.shiftKey) {
          move(HEAD, active?.col || navCols[0]!.key);
          break;
        }
        move(nextNav(Math.max(0, i), -1), active?.col, info);
        break;
      case "ArrowRight":
        if (!item || item.kind !== "row") return;
        e.preventDefault();
        move(i, navCols[Math.min(navCols.length - 1, nci + 1)]!.key, info);
        break;
      case "ArrowLeft":
        if (!item || item.kind !== "row") return;
        e.preventDefault();
        move(i, navCols[Math.max(0, nci - 1)]!.key, info);
        break;
      case "Home":
        e.preventDefault();
        if (ctrl) move(firstNav(), active?.col, info);
        else move(i, navCols[0]!.key, info);
        break;
      case "End":
        e.preventDefault();
        if (ctrl) move(nextNav(items.length, -1), active?.col, info);
        else move(i, navCols[navCols.length - 1]!.key, info);
        break;
      case "PageDown":
        {
          e.preventDefault();
          let j = Math.min(items.length - 1, i + page);
          while (j > i && !navigable(j)) j--;
          move(j, active?.col, info);
        }
        break;
      case "PageUp":
        {
          e.preventDefault();
          let j = Math.max(0, i - page);
          while (j < i && !navigable(j)) j++;
          move(j, active?.col, info);
        }
        break;
      default: // Tab is not taken: it leaves the grid.
    }
  };

  const [dragOver, setDragOver] = useState<string | null>(null);
  const startResize = (e: ReactPointerEvent<HTMLElement>, c: GridColumn) => {
    e.preventDefault();
    e.stopPropagation();
    const x0 = e.clientX,
      w0 = c.width;
    const handle = e.currentTarget;
    handle.classList.add("on");
    document.body.setAttribute("data-resizing", "vertical");
    const mv = (ev: PointerEvent) =>
      onResize &&
      onResize(c.key, Math.max(c.minWidth || 48, w0 + ev.clientX - x0));
    const up = () => {
      handle.classList.remove("on");
      document.body.removeAttribute("data-resizing");
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
  };

  const tabStopKey =
    active && (onHead || activeIdx != null)
      ? active.key
      : items.find((_, k) => navigable(k))?.key;
  const tabStopCol =
    active && (onHead || activeIdx != null)
      ? active.col
      : cols.find((c) => !c.skipNav)?.key;
  const rowDescs = describeRow
    ? shown
        .filter((i) => items[i]!.kind === "row")
        .map((i) => ({
          id: descId(items[i]!.key),
          text: describeRow(items[i]!),
        }))
    : [];

  return (
    <div
      ref={ref}
      className={cx("grid", className)}
      role="grid"
      aria-label={label}
      aria-rowcount={items.length + 1}
      aria-colcount={cols.length}
      aria-multiselectable="true"
      onScroll={onScroll}
      onKeyDown={handleKey}
      onCopy={onCopy}
      onPaste={onPaste}
    >
      <div
        className="g-head"
        role="row"
        aria-rowindex={1}
        style={{ width: colLayout.total, height: headH }}
      >
        {cols.map((c, ci) => (
          <div
            key={c.key}
            id={"hcell-" + c.key}
            role="columnheader"
            aria-colindex={ci + 1}
            aria-sort={
              c.sortDir === "asc"
                ? "ascending"
                : c.sortDir === "desc"
                  ? "descending"
                  : c.sortable
                    ? "none"
                    : undefined
            }
            className={cx(
              "g-hcell",
              c.num && "num",
              c.sticky && "sticky",
              c.lastSticky && "last",
              c.sortable && "sortable",
              dragOver === c.key && "dragover",
            )}
            style={{
              width: c.width,
              left: c.sticky ? colLayout.left[c.key] : undefined,
            }}
            data-tip={c.headerTip}
            draggable={!!(onReorder && !c.sticky)}
            tabIndex={tabStopKey === HEAD && tabStopCol === c.key ? 0 : -1}
            data-active={onHead && active.col === c.key ? "true" : undefined}
            aria-keyshortcuts={
              c.sortable
                ? "Enter Control+ArrowLeft Control+ArrowRight Alt+ArrowLeft Alt+ArrowRight"
                : undefined
            }
            onDragStart={(e) => {
              e.dataTransfer.setData("text/x-col", c.key);
              e.dataTransfer.effectAllowed = "move";
            }}
            onDragOver={(e) => {
              if (
                onReorder &&
                !c.sticky &&
                e.dataTransfer.types.includes("text/x-col")
              ) {
                e.preventDefault();
                setDragOver(c.key);
              }
            }}
            onDragLeave={() => setDragOver(null)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(null);
              const k = e.dataTransfer.getData("text/x-col");
              if (k && k !== c.key) onReorder?.(k, c.key);
            }}
            onClick={(e) => {
              if ((e.target as Element).closest("input")) return;
              if (c.sortable && onHeaderClick) onHeaderClick(c, e);
            }}
          >
            {c.header}
            {c.sortDir ? (
              <Icon
                name={c.sortDir === "asc" ? "sortAsc" : "sortDesc"}
                size="xs"
              />
            ) : null}
            {c.resizable !== false && onResize ? (
              <span
                className="g-resize"
                aria-hidden="true"
                onPointerDown={(e) => startResize(e, c)}
                onClick={(e) => e.stopPropagation()}
              ></span>
            ) : null}
          </div>
        ))}
      </div>
      <div className="g-hidden">
        {rowDescs.map((d) => (
          <span key={d.id} id={d.id}>
            {d.text}
          </span>
        ))}
      </div>
      <div
        className="g-body"
        role="rowgroup"
        style={{ height: total, width: colLayout.total }}
      >
        {shown.map((i) => {
          const it = items[i]!;
          const isActiveRow = active?.key === it.key;
          const ra = rowAttrs ? rowAttrs(it) : {};
          if (it.kind !== "row") {
            const id = cellId(it.key, "_full");
            return (
              <div
                key={it.key}
                role="row"
                aria-rowindex={i + 2}
                {...ra}
                className={cx("g-fullrow", ra.className)}
                style={{
                  top: tops[i],
                  height: heightAt(i),
                  minWidth: colLayout.total,
                }}
              >
                <div
                  role="gridcell"
                  aria-colspan={cols.length}
                  id={id}
                  tabIndex={tabStopKey === it.key ? 0 : -1}
                  data-active={isActiveRow ? "true" : undefined}
                  className="g-fullcell"
                  onPointerDown={(e) => {
                    wantFocus.current = true;
                    onActive(it.key, active?.col || tabStopCol || "", {
                      via: "pointer",
                    });
                    if (onCellPointerDown) onCellPointerDown(e, it, null);
                  }}
                >
                  {renderFull?.(it, { active: isActiveRow })}
                </div>
              </div>
            );
          }
          const desc = describeRow ? descId(it.key) : undefined;
          return (
            <div
              key={it.key}
              role="row"
              aria-rowindex={i + 2}
              {...ra}
              className={cx("g-row", ra.className)}
              style={{
                top: tops[i],
                height: heightAt(i),
                width: colLayout.total,
              }}
              onContextMenu={
                onContextMenu ? (e) => onContextMenu(e, it) : undefined
              }
            >
              {cols.map((c, ci) => {
                const ca = cellAttrs ? cellAttrs(it, c) : {};
                const act = isActiveRow && active.col === c.key;
                const cdesc = describeCell ? describeCell(it, c) : null;
                return (
                  <div
                    key={c.key}
                    id={cellId(it.key, c.key)}
                    role="gridcell"
                    aria-colindex={ci + 1}
                    aria-describedby={
                      [desc, cdesc ? cellId(it.key, c.key) + "-d" : null]
                        .filter(Boolean)
                        .join(" ") || undefined
                    }
                    {...ca}
                    className={cx(
                      "g-cell",
                      c.num && "num",
                      c.sticky && "sticky",
                      c.lastSticky && "last",
                      c.cellClass,
                      ca.className,
                    )}
                    style={{
                      width: c.width,
                      left: c.sticky ? colLayout.left[c.key] : undefined,
                    }}
                    tabIndex={
                      tabStopKey === it.key && tabStopCol === c.key ? 0 : -1
                    }
                    data-active={act ? "true" : undefined}
                    onPointerDown={(e) => {
                      if (e.button !== 0 && e.button !== 2) return;
                      wantFocus.current = true;
                      if (
                        onCellPointerDown &&
                        onCellPointerDown(e, it, c) === false
                      )
                        return;
                      if (!c.skipNav)
                        onActive(it.key, c.key, {
                          via: "pointer",
                          extend: e.shiftKey,
                        });
                    }}
                    onDoubleClick={(e) =>
                      onCellDoubleClick && onCellDoubleClick(e, it, c)
                    }
                  >
                    {renderCell?.(it, c, { active: act })}
                    {cdesc ? (
                      <span
                        id={cellId(it.key, c.key) + "-d"}
                        className="sr-only"
                      >
                        {cdesc}
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </div>
          );
        })}
        {range && layout.index.has(range.from) && layout.index.has(range.to)
          ? (() => {
              /* One rectangle for a range, across sticky columns (V-18). */
              const a = layout.index.get(range.from)!,
                b = layout.index.get(range.to)!,
                i0 = Math.min(a, b),
                i1 = Math.max(a, b);
              const ks = cols.map((c) => c.key),
                x0 = ks.indexOf(range.c0),
                x1 = ks.indexOf(range.c1);
              if (x0 < 0 || x1 < 0) return null;
              const j0 = Math.min(x0, x1),
                j1 = Math.max(x0, x1),
                left = colLayout.left[ks[j0]!]!;
              return (
                <div
                  className="g-range"
                  aria-hidden="true"
                  style={{
                    top: layout.tops[i0],
                    height: layout.tops[i1]! + heightAt(i1) - layout.tops[i0]!,
                    left,
                    width: colLayout.left[ks[j1]!]! + cols[j1]!.width - left,
                  }}
                ></div>
              );
            })()
          : null}
      </div>
      {!items.length && emptyNode ? (
        <div className="g-empty" style={{ width: vp.w }}>
          {emptyNode}
        </div>
      ) : null}
    </div>
  );
}

export type TableColumn<R> = {
  key: string;
  label?: ReactNode;
  srLabel?: string;
  num?: boolean;
  wrap?: boolean;
  sortable?: boolean;
  width?: number | string;
  minWidth?: number | string;
  tip?: string;
  render?: (row: R) => ReactNode;
};
/* ui/data-table: the plain sortable table mode for short lists. */
export function DataTable<R>({
  columns,
  rows,
  rowKey,
  sort,
  onSort,
  onRowClick,
  selectedKey,
  label,
  footer,
  empty,
  rowLabel,
}: {
  columns: TableColumn<R>[];
  rows: R[];
  rowKey: (row: R) => string;
  sort?: { key: string; dir: "asc" | "desc" } | null;
  onSort?: (key: string) => void;
  onRowClick?: (row: R) => void;
  selectedKey?: string | null;
  label: string;
  footer?: ReactNode;
  empty?: ReactNode;
  rowLabel?: (row: R) => string;
}) {
  return (
    <table className="tbl" aria-label={label}>
      <thead>
        <tr>
          {columns.map((c) => (
            <th
              key={c.key}
              scope="col"
              className={cx(
                c.num && "num",
                c.sortable !== false && onSort && "sortable",
              )}
              style={{ width: c.width, minWidth: c.minWidth }}
              aria-sort={
                sort?.key === c.key
                  ? sort.dir === "asc"
                    ? "ascending"
                    : "descending"
                  : undefined
              }
              tabIndex={c.sortable !== false && onSort ? 0 : undefined}
              onClick={() => c.sortable !== false && onSort && onSort(c.key)}
              onKeyDown={(e) => {
                if (
                  (e.key === "Enter" || e.key === " ") &&
                  c.sortable !== false &&
                  onSort
                ) {
                  e.preventDefault();
                  onSort(c.key);
                }
              }}
              data-tip={c.tip}
            >
              {c.label ? (
                <span className={cx("row g1", c.num ? "end" : "start")}>
                  {c.label}
                  {sort?.key === c.key ? (
                    <Icon
                      name={sort.dir === "asc" ? "sortAsc" : "sortDesc"}
                      size="xs"
                    />
                  ) : null}
                </span>
              ) : (
                <span className="sr-only">{c.srLabel || "Actions"}</span>
              )}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr
            key={rowKey(r)}
            className={onRowClick ? "clickable" : ""}
            aria-selected={
              selectedKey != null ? selectedKey === rowKey(r) : undefined
            }
            tabIndex={onRowClick ? 0 : undefined}
            aria-label={onRowClick && rowLabel ? rowLabel(r) : undefined}
            onClick={onRowClick ? () => onRowClick(r) : undefined}
            onKeyDown={
              onRowClick
                ? (e) => {
                    if (e.key === "Enter") onRowClick(r);
                    if (e.key === "ArrowDown") {
                      e.preventDefault();
                      (
                        e.currentTarget.nextElementSibling as HTMLElement | null
                      )?.focus();
                    }
                    if (e.key === "ArrowUp") {
                      e.preventDefault();
                      (
                        e.currentTarget
                          .previousElementSibling as HTMLElement | null
                      )?.focus();
                    }
                  }
                : undefined
            }
          >
            {columns.map((c) => (
              <td key={c.key} className={cx(c.num && "num", c.wrap && "wrapc")}>
                {c.render
                  ? c.render(r)
                  : String((r as Record<string, unknown>)[c.key] ?? "")}
              </td>
            ))}
          </tr>
        ))}
        {!rows.length && empty ? (
          <tr>
            <td colSpan={columns.length} className="tbl-empty">
              {empty}
            </td>
          </tr>
        ) : null}
      </tbody>
      {footer ? <tfoot>{footer}</tfoot> : null}
    </table>
  );
}
export function useSort(initial: { key: string; dir: "asc" | "desc" } | null) {
  const [sort, setSort] = useState(initial);
  const toggle = (key: string) =>
    setSort((s) =>
      s?.key === key
        ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" },
    );
  return [sort, toggle] as const;
}
export function sortRows<R>(
  rows: R[],
  sort: { key: string; dir: "asc" | "desc" } | null,
  get: (row: R, key: string) => string | number | null | undefined,
) {
  if (!sort) return rows;
  const out = [...rows];
  out.sort((a, b) => {
    const va = get(a, sort.key),
      vb = get(b, sort.key);
    if (va == null && vb != null) return 1;
    if (vb == null && va != null) return -1;
    if (va === vb) return 0;
    return (va! < vb! ? -1 : 1) * (sort.dir === "desc" ? -1 : 1);
  });
  return out;
}
