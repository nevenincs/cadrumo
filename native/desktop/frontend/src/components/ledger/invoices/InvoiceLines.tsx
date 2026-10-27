import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { useTableView, type ViewColumn } from "@/components/ui/table-view";
import type { CatalogueInvoiceLine, InvoiceKind } from "../../../shell/ledger";
import {
  SPENDING_CATEGORY_FAMILIES,
  isSpendingCategory,
} from "../../../shell/ledgerVocabulary";
import { useStrings, type Translate } from "../../../shell/strings";
import {
  RATE_SLOTS,
  type LineDraft,
  type LineFigures,
  type Problem,
} from "./invoiceModel";
import { figureText, problemText, rateLabel } from "./invoiceWords";

const LINE_FIELDS = ["description", "quantity", "unitPrice", "rate"] as const;
type LineField = (typeof LINE_FIELDS)[number];

const categoryLabel = (t: Translate, id: string) =>
  isSpendingCategory(id) ? t(`desktop.ledger.category.${id}`) : id;

const HEAD_ROW =
  "h-control-sm border-b border-border-strong text-xs text-muted-foreground";
/** A column of lines, in the order the document has them: it has no way to
 * rank its rows. */
const column = (
  id: string,
  label: string,
  align?: "end",
): { id: string; label: string; name: string; align?: "end" } => ({
  id,
  label,
  name: label,
  align,
});
const CELL = "px-1.5 py-1 align-middle";

/**
 * The lines of a new invoice, typed as printed: description, quantity, unit
 * price and rate, with the subtotal and IVA worked out to the cent. Received
 * invoices also take a spending category per line; issued ones do not.
 */
export function DraftLines({
  lines,
  figures,
  kind,
  locale,
  problems,
  shown,
  onChange,
  onAdd,
  onRemove,
}: {
  lines: readonly LineDraft[];
  figures: readonly LineFigures[];
  kind: InvoiceKind | null;
  locale: string;
  /** Problems by `line:<key>:<field>`. */
  problems: Record<string, Problem>;
  /** Whether a line field's problem is shown yet. */
  shown: (key: string, field: LineField) => boolean;
  onChange(
    key: string,
    field: Exclude<keyof LineDraft, "key">,
    value: string,
  ): void;
  onAdd(): void;
  onRemove(key: string): void;
}) {
  const t = useStrings();
  const id = useId();
  const received = kind === "received";
  const problemOf = (line: LineDraft, field: LineField) =>
    figures[lines.indexOf(line)]?.entered && shown(line.key, field)
      ? (problems[`line:${line.key}:${field}`] ?? null)
      : null;
  const errors = lines.flatMap((line, at) =>
    LINE_FIELDS.flatMap((field) => {
      const problem = problemOf(line, field);
      return problem
        ? [
            {
              key: `${line.key}-${field}`,
              cell: `${id}-${line.key}-${field}`,
              text: t("desktop.ledger.invoices.line.problem", {
                line: at + 1,
                field: t(`desktop.ledger.invoices.line.${fieldKey(field)}`),
                problem: problemText(t, problem),
              }),
            },
          ]
        : [];
    }),
  );
  const columns: ViewColumn<LineDraft>[] = [
    column("description", t("desktop.ledger.invoices.line.description")),
    column("quantity", t("desktop.ledger.invoices.line.quantity"), "end"),
    column("unit_price", t("desktop.ledger.invoices.line.unit_price"), "end"),
    column("subtotal", t("desktop.ledger.invoices.line.subtotal"), "end"),
    column("rate", t("desktop.ledger.invoices.line.rate")),
    column("iva", t("desktop.ledger.invoices.line.iva"), "end"),
    ...(received
      ? [column("category", t("desktop.ledger.invoices.line.category"))]
      : []),
    {
      ...column("actions", t("desktop.ledger.invoices.line.actions")),
      hidden: true,
      resizable: false,
    },
  ];
  const view = useTableView({
    columns,
    rows: lines,
    resizeLabel: (name) => t("desktop.table.resize_column", { column: name }),
  });
  const described = (line: LineDraft, field: LineField) =>
    problemOf(line, field) ? `${id}-${line.key}-${field}` : undefined;
  return (
    <div className="flex flex-col gap-2">
      <div
        className="overflow-x-auto"
        role="group"
        tabIndex={0}
        aria-label={t("desktop.ledger.invoices.lines")}
      >
        <table
          className="ledger-invoice-lines w-full border-collapse text-base"
          aria-label={t("desktop.ledger.invoices.lines")}
          {...view.tableProps}
        >
          <thead>
            <tr className={HEAD_ROW}>{view.headers}</tr>
          </thead>
          <tbody>
            {view.rows.map((line, at) => {
              const figure = figures[at];
              const name = (field: string) =>
                t("desktop.ledger.invoices.line.field", {
                  line: at + 1,
                  field: t(`desktop.ledger.invoices.line.${field}`),
                });
              return (
                <tr key={line.key} className="border-b border-border">
                  <td className={CELL}>
                    <Input
                      controlSize="sm"
                      value={line.description}
                      aria-label={name("description")}
                      aria-invalid={
                        problemOf(line, "description") ? true : undefined
                      }
                      aria-describedby={described(line, "description")}
                      onChange={(event) =>
                        onChange(line.key, "description", event.target.value)
                      }
                    />
                  </td>
                  <td className={CELL}>
                    <Input
                      controlSize="sm"
                      className="text-end tabular-nums"
                      inputMode="decimal"
                      value={line.quantity}
                      aria-label={name("quantity")}
                      aria-invalid={
                        problemOf(line, "quantity") ? true : undefined
                      }
                      aria-describedby={described(line, "quantity")}
                      onChange={(event) =>
                        onChange(line.key, "quantity", event.target.value)
                      }
                    />
                  </td>
                  <td className={CELL}>
                    <Input
                      controlSize="sm"
                      className="text-end tabular-nums"
                      inputMode="decimal"
                      value={line.unitPrice}
                      aria-label={name("unit_price")}
                      aria-invalid={
                        problemOf(line, "unitPrice") ? true : undefined
                      }
                      aria-describedby={described(line, "unitPrice")}
                      onChange={(event) =>
                        onChange(line.key, "unitPrice", event.target.value)
                      }
                    />
                  </td>
                  <td className={`${CELL} text-end tabular-nums`}>
                    <Figure locale={locale} value={figure?.subtotal ?? null} />
                  </td>
                  <td className={CELL}>
                    <NativeSelect
                      controlSize="sm"
                      value={line.rate}
                      aria-label={name("rate")}
                      aria-invalid={problemOf(line, "rate") ? true : undefined}
                      aria-describedby={described(line, "rate")}
                      onChange={(event) =>
                        onChange(line.key, "rate", event.target.value)
                      }
                    >
                      <option value="" disabled>
                        {t("desktop.ledger.invoices.line.choose_rate")}
                      </option>
                      {RATE_SLOTS.map(({ slot }) => (
                        <option key={slot} value={slot}>
                          {rateLabel(t, locale, slot)}
                        </option>
                      ))}
                    </NativeSelect>
                  </td>
                  <td className={`${CELL} text-end tabular-nums`}>
                    <Figure locale={locale} value={figure?.iva ?? null} />
                  </td>
                  {received && (
                    <td className={CELL}>
                      <NativeSelect
                        controlSize="sm"
                        value={line.category}
                        aria-label={name("category")}
                        onChange={(event) =>
                          onChange(line.key, "category", event.target.value)
                        }
                      >
                        <option value="">
                          {t("desktop.ledger.invoices.none")}
                        </option>
                        {SPENDING_CATEGORY_FAMILIES.map(([family, members]) => (
                          <optgroup
                            key={family}
                            label={t(
                              `desktop.ledger.category_family.${family}`,
                            )}
                          >
                            {members.map((member) => (
                              <option key={member} value={member}>
                                {categoryLabel(t, member)}
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </NativeSelect>
                    </td>
                  )}
                  <td className={CELL}>
                    <IconButton
                      label={t("desktop.ledger.invoices.line.remove", {
                        line: at + 1,
                      })}
                      aria-disabled={lines.length === 1 ? true : undefined}
                      onClick={() => {
                        if (lines.length > 1) onRemove(line.key);
                      }}
                    >
                      <Icon name="close" />
                    </IconButton>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {errors.length > 0 && (
        <ul className="flex flex-col gap-1">
          {errors.map((error) => (
            <li
              key={error.key}
              id={error.cell}
              className="flex items-start gap-1.5 text-sm text-destructive"
            >
              <Icon name="alert" size="xs" className="mt-0.5" />
              <span>{error.text}</span>
            </li>
          ))}
        </ul>
      )}
      <div>
        <Button variant="ghost" size="xs" onClick={onAdd}>
          <Icon name="plus" />
          {t("desktop.ledger.invoices.line.add")}
        </Button>
      </div>
    </div>
  );
}

const fieldKey = (field: LineField) =>
  field === "unitPrice" ? "unit_price" : field;

function Figure({ locale, value }: { locale: string; value: string | null }) {
  return value === null ? (
    <span className="text-muted-foreground" aria-hidden="true">
      —
    </span>
  ) : (
    <span>{figureText(locale, value)}</span>
  );
}

/** A stored invoice's lines, as they were written: they cannot change. */
export function StoredLines({
  lines,
  kind,
  locale,
}: {
  lines: readonly CatalogueInvoiceLine[];
  kind: InvoiceKind;
  locale: string;
}) {
  const t = useStrings();
  const received = kind === "received";
  const columns: ViewColumn<CatalogueInvoiceLine>[] = [
    column("description", t("desktop.ledger.invoices.line.description")),
    column("quantity", t("desktop.ledger.invoices.line.quantity"), "end"),
    column("unit_price", t("desktop.ledger.invoices.line.unit_price"), "end"),
    column("subtotal", t("desktop.ledger.invoices.line.subtotal"), "end"),
    column("rate", t("desktop.ledger.invoices.line.rate")),
    column("iva", t("desktop.ledger.invoices.line.iva"), "end"),
    ...(received
      ? [column("category", t("desktop.ledger.invoices.line.category"))]
      : []),
  ];
  const view = useTableView({
    columns,
    rows: lines,
    resizeLabel: (name) => t("desktop.table.resize_column", { column: name }),
  });
  return (
    <div
      className="overflow-x-auto"
      role="group"
      tabIndex={0}
      aria-label={t("desktop.ledger.invoices.lines")}
    >
      <table
        className="ledger-invoice-lines w-full border-collapse text-base"
        aria-label={t("desktop.ledger.invoices.lines")}
        {...view.tableProps}
      >
        <thead>
          <tr className={HEAD_ROW}>{view.headers}</tr>
        </thead>
        <tbody>
          {view.rows.map((line, at) => (
            <tr key={at} className="border-b border-border">
              <td className={`${CELL} [overflow-wrap:anywhere]`}>
                {line.description}
              </td>
              <td className={`${CELL} text-end tabular-nums`}>
                {line.quantity.decimal}
              </td>
              <td className={`${CELL} text-end tabular-nums`}>
                {line.unit_price.decimal}
              </td>
              <td className={`${CELL} text-end tabular-nums`}>
                {figureText(locale, line.subtotal.decimal)}
              </td>
              <td className={CELL}>{rateLabel(t, locale, line.iva_rate)}</td>
              <td className={`${CELL} text-end tabular-nums`}>
                {figureText(locale, line.iva_amount.decimal)}
              </td>
              {received && (
                <td className={CELL}>
                  {line.spending_category_id ? (
                    categoryLabel(t, line.spending_category_id)
                  ) : (
                    <span className="text-muted-foreground">
                      {t("desktop.ledger.invoices.none")}
                    </span>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
