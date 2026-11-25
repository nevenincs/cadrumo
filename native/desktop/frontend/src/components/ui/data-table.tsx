import * as React from "react";
import { cn } from "./cn";
import { Icon } from "./icon";
import { exactly } from "./dataGridModel";

export type TableColumn<R> = {
  id: string;
  header: React.ReactNode;
  /** In rem; leave out to share what is left. */
  width?: number;
  align?: "start" | "end";
  sortable?: boolean;
  cell: (row: R) => React.ReactNode;
};

export type TableRow<R> =
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
export function DataTable<R>({
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
