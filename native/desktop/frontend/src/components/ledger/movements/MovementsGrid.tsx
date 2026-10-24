import type { ComponentProps, ReactNode, Ref } from "react";
import {
  DataGrid,
  DataGridRowCheckbox,
  type CellDescription,
  type DataGridHandle,
  type EditorContext,
  type GridColumn,
} from "@/components/ui/data-grid";
import { Icon } from "@/components/ui/icon";
import type { LedgerRow } from "../../../shell/ledger";
import { useStrings, type Translate } from "../../../shell/strings";
import {
  AmountCell,
  CountCell,
  DirectionCell,
  EuroCell,
  SelectShownBox,
  StatusCell,
  TextCell,
} from "./MovementCells";
import {
  COLUMN_SPECS,
  type ColumnId,
  type ReadinessSets,
} from "./movementsModel";
import {
  accountLabel,
  amountText,
  categoryLabel,
  classificationText,
  classifiedByLabel,
  dateText,
  ivaCategoryLabel,
  irpfCategoryLabel,
  lifecycleLabel,
  percentText,
  reasonDetail,
  stampText,
  statusLabel,
  statusWord,
} from "./movementWords";

/** What staged editing adds to the columns: each one's editor and why a
 * cell takes none, what a cell draws while a change is staged on it, and
 * what is said of a staged cell or row. */
export type ColumnEditing = {
  editor: (
    column: ColumnId,
  ) =>
    ((row: LedgerRow, context: EditorContext) => ReactNode | null) | undefined;
  readOnlyReason: (
    column: ColumnId,
  ) => ((row: LedgerRow) => string | undefined) | undefined;
  /** Draws a cell over its stored drawing, which `stored` gives. */
  decorate: (
    row: LedgerRow,
    column: ColumnId,
    stored: () => ReactNode,
  ) => ReactNode;
  describeCell: (key: string, column: string) => CellDescription | undefined;
  describeRow: (key: string) => string | undefined;
};

export type ColumnContext = {
  t: Translate;
  locale: string;
  density: "compact" | "comfortable";
  /** The rem widths the person gave columns. */
  widths: Readonly<Record<string, number>>;
  readiness: ReadinessSets;
  /** The column readiness marks, and the reason it marks it for. */
  missing: { column: ColumnId; reason: string } | null;
  /** Dates carry their year: the window spans more than one. */
  withYear: boolean;
  /** How many of the shown movements are selected. */
  extent: "none" | "some" | "all";
  onSelectShown: (how: "replace" | "add" | "remove") => void;
  /** Sorting by this column waits for the whole window. */
  sortable: (column: ColumnId) => boolean;
  /** The register's own accounts, null while unread. */
  accounts: readonly { id: string; label: string }[] | null;
  /** Staged editing, where the grid takes edits. */
  editing?: ColumnEditing;
};

const id = (row: LedgerRow) => row.transaction.transaction_id;

/** Whether readiness found `column` missing on `row`. */
function isMissing(
  context: Pick<ColumnContext, "missing" | "readiness">,
  row: LedgerRow,
  column: string,
): boolean {
  const missing = context.missing;
  return (
    missing !== null &&
    missing.column === column &&
    !!context.readiness.issues.get(id(row))?.includes(missing.reason)
  );
}

function Missing({ t }: { t: Translate }) {
  return (
    <span data-missing="" className="inline-flex items-center gap-1">
      <Icon name="alert" size="xs" className="text-warning" />
      {t("desktop.ledger.missing")}
    </span>
  );
}

/** The grid's columns, in `order`: what each draws from the stored row
 * and how it is laid out. Every cell shows the stored value; a cell
 * readiness found missing says so in words. */
function movementColumns(
  order: readonly ColumnId[],
  context: ColumnContext,
): GridColumn<LedgerRow>[] {
  const { t, locale } = context;
  const missingOr =
    (column: ColumnId, draw: (row: LedgerRow) => ReactNode) =>
    (row: LedgerRow) =>
      isMissing(context, row, column) ? <Missing t={t} /> : draw(row);
  const draw: Record<ColumnId, (row: LedgerRow) => ReactNode> = {
    select: (row) => (
      <DataGridRowCheckbox
        rowKey={id(row)}
        label={t("desktop.ledger.select.row", {
          description: row.transaction.description,
        })}
      />
    ),
    status: (row) => (
      <StatusCell
        row={row}
        issues={context.readiness.issues.get(id(row))?.length ?? 0}
        wordy={context.density === "comfortable"}
      />
    ),
    date: missingOr("date", (row) => (
      <span className="tabular-nums">
        {dateText(locale, row.transaction.date, context.withYear)}
      </span>
    )),
    description: (row) => <TextCell text={row.transaction.description} />,
    counterparty: missingOr("counterparty", (row) => (
      <TextCell text={row.transaction.counterparty} />
    )),
    direction: (row) => <DirectionCell direction={row.transaction.direction} />,
    amount: (row) => (
      <AmountCell
        amount={row.transaction.amount}
        currency={row.transaction.currency}
        locale={locale}
      />
    ),
    eur: missingOr("eur", (row) => <EuroCell row={row} locale={locale} />),
    classification: missingOr("classification", (row) => {
      const decided = ["BUSINESS", "PERSONAL", "MIXED"].includes(
        row.transaction.business_classification,
      );
      return (
        <TextCell
          text={classificationText(t, row.transaction)}
          quiet={!decided}
        />
      );
    }),
    category: missingOr("category", (row) => {
      const category = row.transaction.category_id;
      return category ? <TextCell text={categoryLabel(t, category)} /> : null;
    }),
    iva_category: missingOr("iva_category", (row) => {
      const category = row.transaction.iva_category;
      return category ? (
        <TextCell text={ivaCategoryLabel(t, category)} />
      ) : null;
    }),
    taxable_base: missingOr("taxable_base", (row) =>
      row.transaction.taxable_base === null ? null : (
        <span className="tabular-nums">
          {amountText(locale, row.transaction.taxable_base)}
        </span>
      ),
    ),
    iva_rate: missingOr("iva_rate", (row) =>
      row.transaction.iva_rate === null ? null : (
        <span className="tabular-nums">
          {percentText(locale, row.transaction.iva_rate)}
        </span>
      ),
    ),
    iva_amount: missingOr("iva_amount", (row) =>
      row.transaction.iva_amount === null ? null : (
        <span className="tabular-nums">
          {amountText(locale, row.transaction.iva_amount)}
        </span>
      ),
    ),
    irpf_category: (row) => {
      const category = row.transaction.irpf_category;
      return category ? (
        <TextCell text={irpfCategoryLabel(t, category)} />
      ) : null;
    },
    invoice: (row) =>
      row.transaction.invoice_id === null ? null : (
        <span className="inline-flex items-center gap-1">
          <Icon name="link" size="xs" className="text-muted-foreground" />
          {t("desktop.ledger.invoice.linked")}
        </span>
      ),
    documents: (row) => {
      const count =
        (row.transaction.purchase_invoice_evidence_id ? 1 : 0) +
        row.transaction.attachment_ids.length;
      return (
        <CountCell
          icon="attach"
          count={count}
          label={t("desktop.ledger.documents.count", { count })}
        />
      );
    },
    group_label: (row) => <TextCell text={row.group_label} />,
    account: (row) => (
      <TextCell
        text={accountLabel(t, context.accounts, row.own_account_id)}
        quiet={row.own_account_id === null}
      />
    ),
    notes: (row) => <TextCell text={row.transaction.notes} quiet />,
    lifecycle: (row) => (
      <TextCell
        text={lifecycleLabel(t, row.transaction.lifecycle_state)}
        quiet={row.transaction.lifecycle_state === "ACTIVE"}
      />
    ),
    classified_by: (row) => (
      <TextCell
        text={classifiedByLabel(t, row.transaction.classified_by)}
        quiet
      />
    ),
    modified: (row) => (
      <TextCell text={stampText(locale, row.transaction.modified_at)} quiet />
    ),
  };
  const editing = context.editing;
  return order.map((column): GridColumn<LedgerRow> => {
    const spec = COLUMN_SPECS[column];
    const name = t(`desktop.ledger.column.${column}`);
    const width = context.widths[column];
    return {
      id: column,
      label: name,
      header:
        column === "select" ? (
          <SelectShownBox
            label={t("desktop.ledger.select.shown")}
            extent={context.extent}
            onSelect={context.onSelectShown}
          />
        ) : (
          name
        ),
      width: width ?? spec.width,
      ...(spec.minWidth !== undefined ? { minWidth: spec.minWidth } : {}),
      ...(spec.grow !== undefined && width === undefined
        ? { grow: spec.grow }
        : {}),
      ...(spec.sticky ? { sticky: spec.sticky } : {}),
      ...(spec.align ? { align: spec.align } : {}),
      sortable: spec.sortable && context.sortable(column),
      resizable: column !== "select",
      cell: editing
        ? (row) => editing.decorate(row, column, () => draw[column](row))
        : draw[column],
      ...(editing?.editor(column) ? { editor: editing.editor(column) } : {}),
      ...(editing?.readOnlyReason(column)
        ? { readOnlyReason: editing.readOnlyReason(column) }
        : {}),
    };
  });
}

type GridProps = ComponentProps<typeof DataGrid<LedgerRow>>;

/**
 * The movements grid: the period's stored movements, in groups where asked,
 * with a hidden status for each row and what readiness found missing in a
 * cell said with that cell. Editing reaches it through the columns'
 * editors, which the caller adds.
 */
export function MovementsGrid({
  gridRef,
  order,
  context,
  byId,
  ...props
}: Omit<
  GridProps,
  "columns" | "describeRow" | "describeCell" | "positionLabel" | "ref"
> & {
  gridRef: Ref<DataGridHandle>;
  order: readonly ColumnId[];
  context: Omit<ColumnContext, "t">;
  byId: ReadonlyMap<string, LedgerRow>;
}) {
  const t = useStrings();
  const full = { ...context, t };
  const columns = movementColumns(order, full);
  const describeRow = (key: string) => {
    const edited = context.editing?.describeRow(key);
    const row = byId.get(key);
    if (!row) return edited;
    const reasons = context.readiness.issues.get(key) ?? [];
    const word = statusWord(row.review_status, reasons.length);
    return [
      statusLabel(t, word, reasons.length),
      reasons.length
        ? t("desktop.ledger.describe.readiness", {
            reasons: reasons
              .map((reason) => reasonDetail(t, reason))
              .join(", "),
          })
        : "",
      row.transaction.lifecycle_state !== "ACTIVE"
        ? lifecycleLabel(t, row.transaction.lifecycle_state)
        : "",
      context.readiness.noRate.has(key) ? t("desktop.ledger.no_rate") : "",
      edited ?? "",
    ]
      .filter(Boolean)
      .join(" · ");
  };
  const describeCell = (key: string, column: string) => {
    const edited = context.editing?.describeCell(key, column);
    if (edited) return edited;
    const row = byId.get(key);
    const missing = context.missing;
    if (!row || !missing || !isMissing(context, row, column)) return undefined;
    return {
      text: t("desktop.ledger.describe.missing", {
        reason: reasonDetail(t, missing.reason),
      }),
    };
  };
  return (
    <DataGrid
      ref={gridRef}
      columns={columns}
      positionLabel={(row, count) =>
        t("desktop.ledger.position", { row, count })
      }
      describeRow={describeRow}
      describeCell={describeCell}
      {...(props as Omit<GridProps, "columns" | "positionLabel">)}
    />
  );
}
