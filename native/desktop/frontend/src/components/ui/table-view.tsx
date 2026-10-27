import * as React from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";

/**
 * What a plain `<table>` needs to be read the way a grid is: columns the
 * person can sort and drag to a width, with the header cells that say so.
 * The table keeps its own markup; the view supplies the sorted rows, the
 * widths and the header.
 */

type Direction = "asc" | "desc";
type SortValue = string | number | null;

type ViewColumn<R> = {
  id: string;
  /** Shown in the header. */
  label: React.ReactNode;
  /** The spoken name where `label` is not text, or is read and not shown. */
  name: string;
  align?: "start" | "end";
  /** A column with a way to rank its rows can be sorted. */
  sortValue?: (row: R) => SortValue;
  /** In px; a column cannot be dragged narrower. */
  minWidth?: number;
  /** A column that is only a column of buttons stays as wide as it is. */
  resizable?: boolean;
  /** The header is read, not shown: an actions column. */
  hidden?: boolean;
};

type TableView<R> = {
  rows: readonly R[];
  /** Props for the `<table>`. */
  tableProps: { style?: React.CSSProperties };
  /** The header row's cells, for the table's own `<tr>`. */
  headers: React.ReactNode;
};

const MIN_PX = 48;
const STEP_PX = 16;
const collator = new Intl.Collator(undefined, { numeric: true });

function compare(a: SortValue, b: SortValue): number {
  if (a === null || b === null) return Number(a === null) - Number(b === null);
  if (typeof a === "number" && typeof b === "number") return a - b;
  return collator.compare(String(a), String(b));
}

/**
 * Sorted rows, widths and headers for one table. Clicking a sortable
 * header ranks by it ascending, then descending, then lets go; a column's
 * edge drags it, and with the arrow keys once focused. `rows` come back in
 * the order they were given while no column is ranked.
 */
function useTableView<R>({
  columns,
  rows,
  resizeLabel,
  initialSort,
}: {
  columns: readonly ViewColumn<R>[];
  rows: readonly R[];
  /** Names a column's edge for a screen reader. */
  resizeLabel: (column: string) => string;
  initialSort?: { column: string; direction: Direction };
}): TableView<R> {
  const [sort, setSort] = React.useState<{
    column: string;
    direction: Direction;
  } | null>(initialSort ?? null);
  const [widths, setWidths] = React.useState<Readonly<
    Record<string, number>
  > | null>(null);
  // What each header is drawn at, to start a drag from and to name the
  // edge's value; the layout itself follows `widths` once one is dragged.
  const [measured, setMeasured] = React.useState<
    Readonly<Record<string, number>>
  >({});
  const [watcher] = React.useState(
    () =>
      new ResizeObserver((entries) =>
        setMeasured((held) => {
          let next: Record<string, number> | null = null;
          for (const entry of entries) {
            const id = (entry.target as HTMLElement).dataset.column;
            const width = Math.round(
              entry.borderBoxSize[0]?.inlineSize ??
                entry.target.getBoundingClientRect().width,
            );
            if (id === undefined || held[id] === width) continue;
            next ??= { ...held };
            next[id] = width;
          }
          return next ?? held;
        }),
      ),
  );

  const sorted = React.useMemo(() => {
    const value = columns.find(
      (column) => column.id === sort?.column,
    )?.sortValue;
    if (!sort || !value) return rows;
    const sign = sort.direction === "asc" ? 1 : -1;
    // Array sort is stable, so equal rows keep the order they came in.
    return [...rows].sort((a, b) => sign * compare(value(a), value(b)));
  }, [columns, rows, sort]);

  const toggle = (column: string) =>
    setSort((held) =>
      held?.column !== column
        ? { column, direction: "asc" }
        : held.direction === "asc"
          ? { column, direction: "desc" }
          : null,
    );

  // The first drag fixes every column at the width it is drawn, so one
  // column moves and the others stay where they are.
  const resize = (column: string, width: number) =>
    setWidths((held) => {
      const base =
        held ??
        Object.fromEntries(
          columns.map((each) => [each.id, measured[each.id] ?? MIN_PX]),
        );
      const floor = columns.find((each) => each.id === column)?.minWidth;
      return { ...base, [column]: Math.max(floor ?? MIN_PX, width) };
    });

  const drawn = (column: string) =>
    widths?.[column] ?? measured[column] ?? MIN_PX;

  const startDrag = (
    event: React.PointerEvent<HTMLDivElement>,
    column: string,
  ) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const start = drawn(column);
    document.body.dataset.resizing = "vertical";
    const move = (moving: PointerEvent) =>
      resize(column, start + moving.clientX - startX);
    const end = () => {
      delete document.body.dataset.resizing;
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("lostpointercapture", end);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("lostpointercapture", end);
  };

  const keyResize = (
    event: React.KeyboardEvent<HTMLDivElement>,
    column: string,
  ) => {
    const direction =
      event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
    if (direction === 0 || event.altKey || event.ctrlKey || event.metaKey)
      return;
    event.preventDefault();
    resize(
      column,
      drawn(column) + direction * STEP_PX * (event.shiftKey ? 4 : 1),
    );
  };

  const headers = columns.map((column) => {
    const ranked = sort?.column === column.id ? sort.direction : null;
    const sortable = column.sortValue !== undefined;
    const resizable = column.resizable !== false;
    const width = widths?.[column.id];
    const label = column.hidden ? (
      <span className="sr-only">{column.label}</span>
    ) : (
      column.label
    );
    return (
      <th
        key={column.id}
        ref={(element) => {
          if (!element) return;
          watcher.observe(element);
          return () => watcher.unobserve(element);
        }}
        data-column={column.id}
        scope="col"
        aria-sort={
          ranked === "asc"
            ? "ascending"
            : ranked === "desc"
              ? "descending"
              : sortable
                ? "none"
                : undefined
        }
        style={width === undefined ? undefined : { width }}
        data-slot="table-view-header"
        className={cn(
          "relative px-2 py-1 font-normal whitespace-nowrap",
          column.align === "end" ? "text-end" : "text-start",
        )}
      >
        {sortable ? (
          <button
            type="button"
            className="inline-flex cursor-pointer items-center gap-1 rounded-xs hover:text-foreground focus-visible:outline-(length:--focus-ring) focus-visible:outline-ring focus-visible:outline-solid"
            onClick={() => toggle(column.id)}
          >
            {label}
            {ranked && (
              <Icon
                name={ranked === "asc" ? "sortAsc" : "sortDesc"}
                size="xs"
              />
            )}
          </button>
        ) : (
          label
        )}
        {resizable && (
          <div
            role="separator"
            tabIndex={0}
            aria-orientation="vertical"
            aria-label={resizeLabel(column.name)}
            aria-valuemin={column.minWidth ?? MIN_PX}
            aria-valuenow={Math.round(drawn(column.id))}
            className="absolute inset-y-0 end-0 w-2 cursor-col-resize touch-none after:absolute after:inset-y-1 after:end-0 after:w-px after:bg-border hover:after:bg-ring focus-visible:outline-(length:--focus-ring) focus-visible:outline-ring focus-visible:outline-solid"
            onPointerDown={(event) => startDrag(event, column.id)}
            onKeyDown={(event) => keyResize(event, column.id)}
          />
        )}
      </th>
    );
  });

  const total =
    widths === null
      ? null
      : columns.reduce((sum, column) => sum + (widths[column.id] ?? 0), 0);
  return {
    rows: sorted,
    tableProps:
      total === null ? {} : { style: { tableLayout: "fixed", width: total } },
    headers,
  };
}

export {
  useTableView,
  type Direction,
  type SortValue,
  type TableView,
  type ViewColumn,
};
