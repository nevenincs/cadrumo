import { useId } from "react";
import { DecimalEditor } from "@/components/editors/DecimalEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { NativeSelect } from "@/components/ui/native-select";
import type { Suggestion } from "@/components/ui/suggestions";
import { useTableView, type ViewColumn } from "@/components/ui/table-view";
import type {
  InvoiceLineSnapshot,
  InvoiceKind,
  InvoiceFiguresPreviewFigure,
  InvoiceFiguresPreviewLineResult,
  InvoiceFiguresPreviewRateSlot,
} from "../../../shell/ledgerInvoiceContract";
import { useStrings, type Translate } from "../../../shell/strings";
import { wordOrToken } from "../../../shell/tokenWords";
import { formatAmount, formatDecimal } from "../../../shared/numbers";
import { vocabularyEmpty } from "../movements/movementWords";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import { formatUnitPrice } from "../unitPrice";
import { lineEntered, type LineDraft, type Problem } from "./invoiceModel";
import { problemText, rateLabel } from "./invoiceWords";

const LINE_FIELDS = [
  "description",
  "quantity",
  "unitPrice",
  "statedSubtotal",
  "rate",
  "statedIva",
] as const;
type LineField = (typeof LINE_FIELDS)[number];

const categoryLabel = (t: Translate, id: string) =>
  wordOrToken(t, "desktop.ledger.category.", id);

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
 * price and rate. The subtotal and IVA are the ledger's, shown as a field's
 * placeholder, and the person may state what the document prints instead.
 * Received invoices also take a spending category per line; issued ones do not.
 */
export function DraftLines({
  descriptions,
  lines,
  figures,
  slots,
  kind,
  locale,
  problems,
  shown,
  onChange,
  onAdd,
  onRemove,
}: {
  /** What a line's description may be picked from. */
  descriptions: readonly Suggestion[];
  lines: readonly LineDraft[];
  /** The ledger's figures, by line key. */
  figures: readonly InvoiceFiguresPreviewLineResult[];
  /** The ledger's rate slots on the draft's date. */
  slots: readonly InvoiceFiguresPreviewRateSlot[];
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
  const vocabulary = useVocabulary();
  const id = useId();
  const received = kind === "received";
  const problemOf = (line: LineDraft, field: LineField) =>
    lineEntered(line) && shown(line.key, field)
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
              const figure = figures.find(({ key }) => key === line.key);
              const offered = slots.some(({ slot }) => slot === line.rate);
              const name = (field: string) =>
                t("desktop.ledger.invoices.line.field", {
                  line: at + 1,
                  field: t(`desktop.ledger.invoices.line.${field}`),
                });
              return (
                <tr key={line.key} className="border-b border-border">
                  <td className={CELL}>
                    <TextEditor
                      controlSize="sm"
                      value={line.description}
                      suggestions={descriptions}
                      aria-label={name("description")}
                      invalid={Boolean(problemOf(line, "description"))}
                      describedBy={described(line, "description")}
                      onChange={(value) =>
                        onChange(line.key, "description", value)
                      }
                    />
                  </td>
                  <td className={CELL}>
                    <DecimalEditor
                      controlSize="sm"
                      value={line.quantity}
                      aria-label={name("quantity")}
                      invalid={Boolean(problemOf(line, "quantity"))}
                      describedBy={described(line, "quantity")}
                      onChange={(value) =>
                        onChange(line.key, "quantity", value)
                      }
                    />
                  </td>
                  <td className={CELL}>
                    <DecimalEditor
                      controlSize="sm"
                      value={line.unitPrice}
                      aria-label={name("unit_price")}
                      invalid={Boolean(problemOf(line, "unitPrice"))}
                      describedBy={described(line, "unitPrice")}
                      onChange={(value) =>
                        onChange(line.key, "unitPrice", value)
                      }
                    />
                  </td>
                  <td className={CELL}>
                    <FigureEditor
                      locale={locale}
                      figure={figure?.subtotal ?? null}
                      value={line.statedSubtotal}
                      label={name("subtotal")}
                      invalid={Boolean(problemOf(line, "statedSubtotal"))}
                      describedBy={described(line, "statedSubtotal")}
                      onChange={(value) =>
                        onChange(line.key, "statedSubtotal", value)
                      }
                    />
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
                      {line.rate !== "" && !offered && (
                        <option value={line.rate}>{line.rate}</option>
                      )}
                      {slots.map(({ slot, in_force }) => (
                        <option key={slot} value={slot} disabled={!in_force}>
                          {rateLabel(t, slots, slot)}
                        </option>
                      ))}
                    </NativeSelect>
                  </td>
                  <td className={CELL}>
                    <FigureEditor
                      locale={locale}
                      figure={figure?.iva_amount ?? null}
                      value={line.statedIva}
                      label={name("iva")}
                      invalid={Boolean(problemOf(line, "statedIva"))}
                      describedBy={described(line, "statedIva")}
                      onChange={(value) =>
                        onChange(line.key, "statedIva", value)
                      }
                    />
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
                        {line.category !== "" &&
                          !vocabulary.categories.includes(line.category) && (
                            <option value={line.category}>
                              {categoryLabel(t, line.category)}
                            </option>
                          )}
                        {vocabulary.categories.length === 0 &&
                          vocabulary.state !== "ready" && (
                            <option value="" disabled>
                              {vocabularyEmpty(t, vocabulary, "", 0)}
                            </option>
                          )}
                        {vocabulary.categoryFamilies.map(
                          ([family, members]) => (
                            <optgroup
                              key={family}
                              label={wordOrToken(
                                t,
                                "desktop.ledger.category_family.",
                                family,
                              )}
                            >
                              {members.map((member) => (
                                <option key={member} value={member}>
                                  {categoryLabel(t, member)}
                                </option>
                              ))}
                            </optgroup>
                          ),
                        )}
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

const FIELD_KEYS: Record<LineField, string> = {
  description: "description",
  quantity: "quantity",
  unitPrice: "unit_price",
  statedSubtotal: "subtotal",
  rate: "rate",
  statedIva: "iva",
};
const fieldKey = (field: LineField) => FIELD_KEYS[field];

/** A line's figure: blank takes the ledger's, shown as the placeholder; what
 * the document prints may be stated over it, with the ledger's kept in sight. */
function FigureEditor({
  locale,
  figure,
  value,
  label,
  invalid,
  describedBy,
  onChange,
}: {
  locale: string;
  figure: InvoiceFiguresPreviewFigure | null;
  value: string;
  label: string;
  invalid: boolean;
  describedBy: string | undefined;
  onChange(value: string): void;
}) {
  const t = useStrings();
  const computed = figure?.computed?.decimal ?? null;
  const worded = computed === null ? "" : formatAmount(locale, computed);
  const differs = figure?.stated != null && figure.verdict !== "equal";
  return (
    <div className="flex flex-col gap-0.5 text-end">
      <DecimalEditor
        controlSize="sm"
        value={value}
        placeholder={worded}
        aria-label={label}
        invalid={invalid}
        describedBy={describedBy}
        onChange={onChange}
      />
      {differs && worded !== "" && (
        <span className="text-xs text-muted-foreground tabular-nums">
          {t("desktop.ledger.invoices.line.calculated", { amount: worded })}
        </span>
      )}
    </div>
  );
}

/** A stored invoice's lines, as they were written: they cannot change. */
export function StoredLines({
  lines,
  slots,
  kind,
  locale,
}: {
  lines: readonly InvoiceLineSnapshot[];
  /** The ledger's words for the rates, when it has answered. */
  slots: readonly InvoiceFiguresPreviewRateSlot[];
  kind: InvoiceKind;
  locale: string;
}) {
  const t = useStrings();
  const received = kind === "received";
  const columns: ViewColumn<InvoiceLineSnapshot>[] = [
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
                {formatDecimal(locale, line.quantity.decimal)}
              </td>
              <td className={`${CELL} text-end tabular-nums`}>
                {formatUnitPrice(locale, line.unit_price.decimal)}
              </td>
              <td className={`${CELL} text-end tabular-nums`}>
                {formatAmount(locale, line.subtotal.decimal)}
              </td>
              <td className={CELL}>{rateLabel(t, slots, line.iva_rate)}</td>
              <td className={`${CELL} text-end tabular-nums`}>
                {formatAmount(locale, line.iva_amount.decimal)}
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
