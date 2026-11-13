import { useId } from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useTableView, type ViewColumn } from "@/components/ui/table-view";
import type {
  PublicModeloFormContextFieldBlock,
  PublicModeloFormRepeatingBlock,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { calm, Label } from "./FieldRow";
import { BoxNumber } from "./BoxNumber";

/** Data types the table reads as amounts, aligned to the end of the cell. */
const FIGURES: ReadonlySet<string> = new Set([
  "money",
  "decimal",
  "integer",
  "ratio",
]);

/** Repeated records, read as a table of every column the read serves, in its
 * order and under its headings. A wide table scrolls inside its own region,
 * never the page. The read serves no row's own source or way to change it:
 * the lines are made from the filer's records and are changed there; when
 * those records could not be read the number of lines is unknown, never
 * zero. */
export function RepeatingBlock({
  block,
}: {
  block: PublicModeloFormRepeatingBlock;
}) {
  const t = useStrings();
  const title = useId();
  const columns: ViewColumn<PublicModeloFormRepeatingBlock["rows"][number]>[] =
    block.columns.map((column, index) => ({
      id: column.key,
      // A heading wraps within a bound, so a long official heading does not
      // stretch its column across the table.
      label: (
        <span className="inline-block max-w-48 min-w-16 whitespace-normal">
          <Label text={column.heading} />
        </span>
      ),
      name: calm(column.heading.text),
      align: FIGURES.has(block.column_data_types[index] ?? "")
        ? ("end" as const)
        : ("start" as const),
    }));
  const view = useTableView({
    columns,
    rows: block.rows,
    resizeLabel: (column) => t("desktop.table.resize_column", { column }),
  });
  return (
    <div className="min-w-0 rounded-lg border border-border">
      <div className="flex items-center gap-2 border-b border-border bg-muted px-3 py-2 text-sm">
        <Icon name="sheet" size="sm" className="text-muted-foreground" />
        <span id={title} className="font-medium">
          {block.rows_known
            ? t("workspace.modelo.repeating", { count: block.rows.length })
            : t("workspace.modelo.grid.records_unknown")}
        </span>
      </div>
      <div
        role="group"
        aria-labelledby={title}
        tabIndex={0}
        data-records-scroll=""
        className="overflow-x-auto outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
      >
        <table className="min-w-full" {...view.tableProps}>
          <thead>
            <tr className="align-bottom text-sm text-muted-foreground">
              {view.headers}
            </tr>
          </thead>
          {block.rows_known && (
            <tbody>
              {view.rows.map((row) => {
                const texts = row.value_texts;
                return (
                  <tr key={row.index} className="border-t border-border">
                    {block.columns.map((column, index) => (
                      <td
                        key={column.key}
                        data-casilla={
                          block.column_casilla_ids[index] ?? undefined
                        }
                        data-value-kind={row.values[index]?.kind}
                        data-value={row.values[index]?.text}
                        className={cn(
                          "px-2 py-2 text-sm whitespace-nowrap tabular-nums",
                          columns[index]?.align === "end" && "text-end",
                        )}
                      >
                        {texts[index] ?? "—"}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          )}
        </table>
      </div>
      <p className="px-3 py-3 text-sm text-muted-foreground">
        {t("workspace.modelo.grid.records_read_only")}
      </p>
    </div>
  );
}

/** Facts the form prints about the filer and the period, as a short list;
 * a fact not known yet says so. */
export function ContextSummary({
  items,
}: {
  items: PublicModeloFormContextFieldBlock[];
}) {
  const t = useStrings();
  return (
    // A value keeps the width it needs, up to a bound, and its label wraps
    // instead: a long label must not squeeze an unbreakable value, such as a
    // tax ID, out over the next fact.
    <dl className="grid grid-cols-[minmax(0,1fr)_fit-content(calc(var(--spacing)*72))] gap-x-6 gap-y-1 rounded-lg bg-muted px-4 py-3 text-sm @3xl:grid-cols-[minmax(0,1fr)_fit-content(calc(var(--spacing)*72))_minmax(0,1fr)_fit-content(calc(var(--spacing)*72))]">
      {items.map((item) => {
        const text = item.value_text;
        return (
          <div key={item.id} className="contents">
            <dt className="flex min-w-0 items-start gap-2 text-muted-foreground">
              <BoxNumber box={item.box_number} size="sm" />
              <span className="min-w-0 wrap-anywhere">
                <Label text={item.label} />
              </span>
            </dt>
            <dd
              className={cn(
                "min-w-0 break-words",
                text ? "text-foreground" : "text-faint",
              )}
            >
              {text ?? t("workspace.modelo.value.not_known_yet")}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
