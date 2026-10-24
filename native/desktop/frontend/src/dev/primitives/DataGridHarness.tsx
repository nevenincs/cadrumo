import { useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Combobox } from "@/components/ui/combobox";
import {
  DataGrid,
  DataGridRowCheckbox,
  DataGridSelectAll,
  DataGridText,
  DataGridTextEditor,
  DataTable,
  type DataGridHandle,
  type GridColumn,
  type GridRow,
  type TableRow,
} from "@/components/ui/data-grid";
import type { CellRange } from "@/components/ui/dataGridModel";
import { EmptyState } from "@/components/ui/empty";
import {
  categoryLabel,
  SAMPLE_CATEGORIES,
  sampleRows,
  type SampleRow,
} from "./gridSample";

declare global {
  interface Window {
    /** What the grid asked of its caller, in order, for the browser tests. */
    __gridEvents?: string[];
  }
}

function record(line: string) {
  (window.__gridEvents ??= []).push(line);
}

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function cellText(row: SampleRow, column: string): string {
  if (column === "date") return row.date;
  if (column === "description") return row.description;
  if (column === "counterparty") return row.counterparty;
  if (column === "category") return categoryLabel(row.category);
  if (column === "amount") return row.amount.toFixed(2);
  return "";
}

/**
 * The data grid over made-up movements: selection, sort, staged edits,
 * column widths and order, and month sections that fold. It answers every
 * request itself and writes what it was asked into `window.__gridEvents`.
 */
export function DataGridHarness({
  count,
  grouped = false,
}: {
  count: number;
  grouped?: boolean;
}) {
  const grid = useRef<DataGridHandle>(null);
  const [data, setData] = useState(() => sampleRows(count));
  const [selection, setSelection] = useState<ReadonlySet<string>>(new Set());
  const [sort, setSort] = useState<{
    column: string;
    direction: "asc" | "desc";
  } | null>(null);
  const [widths, setWidths] = useState<Record<string, number>>({});
  const [order, setOrder] = useState<string[] | null>(null);
  const [folded, setFolded] = useState<ReadonlySet<string>>(new Set());

  const columns = useMemo(() => {
    const all: GridColumn<SampleRow>[] = [
      {
        id: "select",
        header: <DataGridSelectAll label="Select every movement" />,
        label: "Selection",
        width: 2.5,
        sticky: "start",
        resizable: false,
        cell: (row) => (
          <DataGridRowCheckbox
            rowKey={row.id}
            label={`Select ${row.description}`}
          />
        ),
      },
      {
        id: "date",
        header: "Date",
        width: 5.5,
        sticky: "start",
        sortable: true,
        cell: (row) => <span className="tabular-nums">{row.date}</span>,
      },
      {
        id: "description",
        header: "Description",
        width: 12,
        minWidth: 12,
        grow: 2,
        sortable: true,
        cell: (row) => <DataGridText>{row.description}</DataGridText>,
        editor: (row, context) => (
          <DataGridTextEditor
            context={context}
            defaultValue={row.description}
          />
        ),
      },
      {
        id: "counterparty",
        header: "Counterparty",
        width: 9,
        minWidth: 9,
        grow: 1.5,
        cell: (row) => <DataGridText>{row.counterparty}</DataGridText>,
      },
      {
        id: "category",
        header: "Category",
        width: 9,
        cell: (row) =>
          row.category ? (
            <DataGridText>{categoryLabel(row.category)}</DataGridText>
          ) : (
            <span className="text-faint">Unclassified</span>
          ),
        editor: (row, context) => (
          <Combobox
            label={`Category for ${row.description}`}
            value={row.category}
            options={SAMPLE_CATEGORIES}
            initialQuery={context.initial}
            emptyLabel="No category matches"
            hint="Type to search the categories."
            onCommit={(value, via) => context.commit(value, via)}
            onCancel={(via) => context.cancel(via === "escape")}
          />
        ),
      },
      {
        id: "amount",
        header: "Amount",
        width: 6.5,
        sticky: "end",
        align: "end",
        sortable: true,
        cell: (row) => row.amount.toFixed(2),
        readOnlyReason: (row) =>
          row.locked ? "Sealed by a filed declaration" : undefined,
        editor: (row, context) => (
          <DataGridTextEditor
            context={context}
            defaultValue={row.amount.toFixed(2)}
            inputMode="decimal"
            className="text-end"
          />
        ),
      },
    ];
    const sized = all.map((column) =>
      widths[column.id] === undefined
        ? column
        : { ...column, width: widths[column.id] as number, grow: undefined },
    );
    if (!order) return sized;
    return order.flatMap((id) => sized.filter((column) => column.id === id));
  }, [widths, order]);

  const sorted = useMemo(() => {
    if (!sort) return data;
    const factor = sort.direction === "asc" ? 1 : -1;
    return [...data].sort((a, b) => {
      const left =
        sort.column === "amount" ? a.amount : cellText(a, sort.column);
      const right =
        sort.column === "amount" ? b.amount : cellText(b, sort.column);
      return left < right ? -factor : left > right ? factor : 0;
    });
  }, [data, sort]);

  const rows = useMemo(() => {
    if (!grouped)
      return sorted.map((row): GridRow<SampleRow> => ({
        kind: "data",
        key: row.id,
        data: row,
      }));
    const out: GridRow<SampleRow>[] = [];
    const months = new Map<string, SampleRow[]>();
    for (const row of sorted) {
      const month = row.date.slice(0, 7);
      months.set(month, [...(months.get(month) ?? []), row]);
    }
    for (const [month, members] of months) {
      const key = `month-${month}`;
      const collapsed = folded.has(key);
      out.push({
        kind: "section",
        key,
        label: `${MONTHS[Number(month.slice(5)) - 1]} ${month.slice(0, 4)}`,
        hint: "Movements of the month",
        collapsed,
        summary: `${members.length} movements`,
      });
      if (!collapsed)
        for (const row of members)
          out.push({ kind: "data", key: row.id, data: row });
    }
    return out;
  }, [sorted, grouped, folded]);

  const byId = useMemo(() => new Map(data.map((row) => [row.id, row])), [data]);

  const tsv = (range: CellRange) =>
    range.rows
      .map((key) => {
        const row = byId.get(key);
        return row
          ? range.columns.map((column) => cellText(row, column)).join("\t")
          : "";
      })
      .join("\n");

  return (
    <DataGrid
      ref={grid}
      label="Movements"
      columns={columns}
      rows={rows}
      positionLabel={(row, total) => `Row ${row} of ${total}`}
      sort={sort}
      onSort={(column) => {
        record(`sort ${column}`);
        setSort((current) =>
          current?.column === column
            ? current.direction === "asc"
              ? { column, direction: "desc" }
              : null
            : { column, direction: "asc" },
        );
      }}
      selection={selection}
      onSelectionChange={(next, cause) => {
        record(`select ${cause} ${next.size}`);
        setSelection(next);
      }}
      onActivate={(key) => record(`activate ${key}`)}
      onCommit={(key, column, value) => {
        record(`commit ${key} ${column} ${JSON.stringify(value)}`);
        setData((current) =>
          current.map((row) => {
            if (row.id !== key) return row;
            if (column === "description")
              return {
                ...row,
                description: String(value ?? ""),
                changed: true,
              };
            if (column === "category")
              return {
                ...row,
                category: value === null ? null : String(value),
                changed: true,
              };
            if (column === "amount") {
              const amount = Number(value);
              return Number.isFinite(amount) && value !== null
                ? { ...row, amount, changed: true }
                : row;
            }
            return row;
          }),
        );
      }}
      onMenu={(key, column) => record(`menu ${key} ${column ?? "-"}`)}
      onToggleSection={(key) => {
        record(`toggle ${key}`);
        setFolded((current) => {
          const next = new Set(current);
          if (next.has(key)) next.delete(key);
          else next.add(key);
          return next;
        });
      }}
      onCopy={(range) => {
        record(`copy ${range.rows.length}x${range.columns.length}`);
        return tsv(range);
      }}
      onPaste={(range, text) =>
        record(`paste ${range.rows.length}x${range.columns.length} ${text}`)
      }
      onFill={(range, direction) =>
        record(`fill ${direction} ${range.rows.length}x${range.columns.length}`)
      }
      onColumnResize={(column, width) => {
        record(`resize ${column} ${width.toFixed(2)}`);
        setWidths((current) => ({ ...current, [column]: width }));
      }}
      onColumnOrder={(next) => {
        record(`order ${next.join(",")}`);
        setOrder(next);
      }}
      rowState={(key) => {
        const row = byId.get(key);
        return row
          ? { changed: row.changed, refused: row.refused, locked: row.locked }
          : undefined;
      }}
      describeRow={(key) => {
        const row = byId.get(key);
        if (!row) return undefined;
        const parts = [
          row.locked && "Sealed: Modelo 303 2026 1T",
          row.changed && "Staged change",
          row.refused && "Refused",
        ].filter(Boolean);
        return parts.length ? parts.join(" · ") : undefined;
      }}
      describeCell={(key, column) => {
        const row = byId.get(key);
        if (!row) return undefined;
        if (row.refused && column === "category")
          return {
            text: "Refused: this category does not apply to the period",
            invalid: true,
          };
        if (row.changed && column === "amount")
          return { text: "changed, was 0.00" };
        return undefined;
      }}
      empty={
        <EmptyState
          icon="search"
          heading="No movements"
          description="Nothing matches the filters."
        />
      }
    />
  );
}

type Declaration = { id: string; model: string; period: string; due: string };

const DECLARATIONS: Declaration[] = [
  { id: "303-1T", model: "303", period: "2026 1T", due: "2026-04-20" },
  { id: "130-1T", model: "130", period: "2026 1T", due: "2026-04-20" },
  { id: "111-03", model: "111", period: "2026 03", due: "2026-04-20" },
  { id: "390-0A", model: "390", period: "2025", due: "2026-01-30" },
  { id: "347-0A", model: "347", period: "2025", due: "2026-02-28" },
];

/** The plain table over made-up declarations, sorted and grouped by
 * deadline, with one of them open elsewhere. */
export function DataTableHarness({ current = "130-1T" }: { current?: string }) {
  const [sort, setSort] = useState<{
    column: string;
    direction: "asc" | "desc";
  }>({ column: "model", direction: "asc" });
  const [open, setOpen] = useState(current);
  const sorted = [...DECLARATIONS].sort((a, b) => {
    const field = sort.column as keyof Declaration;
    const factor = sort.direction === "asc" ? 1 : -1;
    return a[field] < b[field] ? -factor : a[field] > b[field] ? factor : 0;
  });
  const soon = sorted.filter((row) => row.due >= "2026-04-01");
  const past = sorted.filter((row) => row.due < "2026-04-01");
  const rows: TableRow<Declaration>[] = [
    {
      kind: "section",
      key: "soon",
      label: "Due soon",
      hint: "Due within a week, or stopped",
      summary: <Badge>{soon.length}</Badge>,
    },
    ...soon.map((row) => ({ kind: "data" as const, key: row.id, data: row })),
    {
      kind: "section",
      key: "past",
      label: "Filed or past",
      summary: <Badge>{past.length}</Badge>,
    },
    ...past.map((row) => ({ kind: "data" as const, key: row.id, data: row })),
  ];
  return (
    <DataTable
      label="Declarations"
      columns={[
        {
          id: "model",
          header: "Modelo",
          width: 6,
          sortable: true,
          cell: (row) => row.model,
        },
        {
          id: "period",
          header: "Period",
          sortable: true,
          cell: (row) => row.period,
        },
        {
          id: "due",
          header: "Due",
          width: 7,
          align: "end",
          sortable: true,
          cell: (row) => row.due,
        },
      ]}
      rows={rows}
      sort={sort}
      onSort={(column) =>
        setSort((now) => ({
          column,
          direction:
            now.column === column && now.direction === "asc" ? "desc" : "asc",
        }))
      }
      current={open}
      onActivate={(key) => {
        record(`activate ${key}`);
        setOpen(key);
      }}
    />
  );
}
