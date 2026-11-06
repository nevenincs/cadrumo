import { Fragment, type ReactNode } from "react";
import { useTableView } from "@/components/ui/table-view";
import { useStrings } from "../../../shell/strings";
import { formatAmount, formatPercent } from "../../../shared/numbers";
import {
  VALUE_COLUMN_MIN_PX,
  type ReadingField,
  type ReadingRow,
} from "./documentsModel";

/** The reading table: what was read from the document, its provenance and
 * its value, in the document's own order. Its columns can be dragged to a
 * width. */
export function ReadingTable({
  rows,
  renderRow,
}: {
  rows: readonly ReadingRow[];
  renderRow(row: ReadingRow): ReactNode;
}) {
  const t = useStrings();
  const field = t("desktop.ledger.documents.column.field");
  const source = t("desktop.ledger.documents.column.source");
  const value = t("desktop.ledger.documents.column.value");
  const table = useTableView({
    columns: [
      { id: "field", label: field, name: field },
      { id: "source", label: source, name: source, resizable: false },
      {
        id: "value",
        label: value,
        name: value,
        minWidth: VALUE_COLUMN_MIN_PX,
      },
    ],
    rows,
    resizeLabel: (column) => t("desktop.table.resize_column", { column }),
  });
  return (
    <table className="ledger-draft-fields w-full text-sm" {...table.tableProps}>
      <thead>
        <tr className="border-b border-border text-muted-foreground">
          {table.headers}
        </tr>
      </thead>
      <tbody>
        {table.rows.map((row) => (
          <Fragment key={row.field}>{renderRow(row)}</Fragment>
        ))}
      </tbody>
    </table>
  );
}

/** A value as the reading table shows it: rates as percentages. */
export function shownReadingValue(
  locale: string,
  field: ReadingField,
  value: string | null,
) {
  if (value === null) return null;
  if (field === "iva_rate" || field === "retencion_rate")
    return formatPercent(locale, value, { unit: "points" });
  if (
    field === "taxable_base" ||
    field === "iva_amount" ||
    field === "recargo_amount" ||
    field === "retencion_amount" ||
    field === "grand_total"
  )
    return formatAmount(locale, value);
  return value;
}
