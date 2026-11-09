import { CountryEditor } from "@/components/editors/CountryEditor";
import { DateEditor } from "@/components/editors/DateEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import type { Suggestion } from "@/components/ui/suggestions";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import type { LedgerPort } from "../../../shell/ledger";
import type { CatalogueInvoice } from "../../../shell/ledgerInvoiceOperations";
import {
  PAYMENT_STATUSES,
  type PaymentStatus,
} from "../../../shell/ledgerContract";
import { useStrings } from "../../../shell/strings";
import { ServedOptions } from "../suggestions/ServedOptions";
import {
  useServedCodes,
  useVocabulary,
} from "../suggestions/SuggestionsProvider";
import {
  invoiceCountryOptions,
  invoiceNumberOptions,
  partyNameOptions,
  seriesOptions,
} from "../suggestions/ledgerSuggestions";
import {
  IvaCategoryField,
  OperationTypeField,
  NotesField,
} from "./InvoiceClassificationFields";
import {
  EditorSection,
  FixedField,
  FormField,
  wired,
  type ControlProps,
} from "./InvoiceFields";
import { InvoiceCounterpartyProvincia } from "./InvoiceCounterpartyProvincia";
import { InvoiceDocument } from "./InvoiceDocument";
import { StoredLines } from "./InvoiceLines";
import { TotalsList, Retention } from "./InvoiceTotals";
import { isPaymentId, type CorrectionDraft } from "./invoiceModel";
import type { PreviewView } from "./invoicePreview";
import { classLabel, kindChoice, paymentLabel } from "./invoiceWords";

// ---- A stored invoice --------------------------------------------------------------

export function StoredInvoice({
  port,
  invoice,
  preview,
  invoices,
  correction,
  locale,
  shown,
  touch,
  correct,
  say,
}: {
  port: LedgerPort;
  invoice: CatalogueInvoice;
  preview: PreviewView;
  /** The catalogue, for what a field can offer. */
  invoices: readonly CatalogueInvoice[];
  correction: CorrectionDraft;
  locale: string;
  shown(field: string): string | null;
  touch(field: string): void;
  correct<K extends keyof CorrectionDraft>(
    key: K,
    value: CorrectionDraft[K],
  ): void;
  /** Confirms a write in a toast. */
  say(text: string): void;
}) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  const servedCountries = useServedCodes("country");
  const fixed = t("desktop.ledger.invoices.fixed");
  const bind = (key: keyof CorrectionDraft, field: string) => ({
    value: correction[key] as string,
    onChange: (value: string) => correct(key, value as never),
    onBlur: () => touch(field),
  });
  const text =
    (
      key: keyof CorrectionDraft,
      field: string,
      offered?: { suggestions: readonly Suggestion[]; opensEmpty?: boolean },
    ) =>
    (control: ControlProps) => (
      <TextEditor {...wired(control)} {...bind(key, field)} {...offered} />
    );
  const rectificativa = correction.invoiceClass === vocabulary.correctiveClass;
  return (
    <>
      <Alert icon={<Icon name="lock" />} className="ledger-invoice-identity">
        {t("desktop.ledger.invoices.identity_fixed")}
      </Alert>

      <EditorSection title={t("desktop.ledger.invoices.party")}>
        <div className="grid grid-cols-2 gap-3">
          <FixedField
            label={t("desktop.ledger.invoices.field.kind")}
            value={kindChoice(t, invoice.kind)}
            reason={fixed}
          />
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_name")}
            required
            error={shown("counterparty_name")}
          >
            {text("counterpartyName", "counterparty_name", {
              suggestions: partyNameOptions(invoices, { kind: invoice.kind }),
            })}
          </FormField>
          <FixedField
            label={t("desktop.ledger.invoices.field.counterparty_tax_id")}
            value={
              invoice.counterparty_tax_id ?? t("desktop.ledger.invoices.none")
            }
            reason={fixed}
            mono
          />
          <FormField
            label={t("desktop.ledger.invoices.field.counterparty_country")}
            required
            error={shown("counterparty_country")}
          >
            {(control) => (
              <CountryEditor
                {...wired(control)}
                {...bind("country", "counterparty_country")}
                suggestions={invoiceCountryOptions(
                  invoices,
                  locale,
                  servedCountries,
                )}
              />
            )}
          </FormField>
        </div>
      </EditorSection>

      <InvoiceCounterpartyProvincia
        port={port}
        taxId={invoice.counterparty_tax_id}
        country={invoice.counterparty_country}
      />

      <EditorSection title={t("desktop.ledger.invoices.document")}>
        <div className="grid grid-cols-2 gap-3">
          <FormField label={t("desktop.ledger.invoices.field.invoice_class")}>
            {(control) => (
              <NativeSelect
                {...control}
                value={correction.invoiceClass}
                onChange={(event) =>
                  correct("invoiceClass", event.target.value)
                }
              >
                <ServedOptions
                  values={vocabulary.invoiceClasses}
                  stored={correction.invoiceClass}
                  label={(token) => classLabel(t, token)}
                />
              </NativeSelect>
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.series")}
            required={rectificativa}
            error={shown("series")}
          >
            {text("series", "series", {
              suggestions: seriesOptions(invoices, {
                kind: invoice.kind,
                invoiceClass: correction.invoiceClass,
              }),
              opensEmpty: true,
            })}
          </FormField>
          <FixedField
            label={t("desktop.ledger.invoices.field.invoice_number")}
            value={invoice.invoice_number}
            reason={fixed}
          />
          <FixedField
            label={t("desktop.ledger.invoices.field.issued_at")}
            value={formatDay(locale, invoice.issued_at)}
            reason={fixed}
          />
          <FormField
            label={t("desktop.ledger.invoices.field.operation_date")}
            error={shown("operation_date")}
          >
            {(control) => (
              <DateEditor
                {...wired(control)}
                {...bind("operationDate", "operation_date")}
              />
            )}
          </FormField>
          <FixedField
            label={t("desktop.ledger.invoices.field.currency")}
            value={invoice.currency}
            reason={fixed}
          />
          {rectificativa && (
            <FormField
              label={t(
                "desktop.ledger.invoices.field.rectifies_invoice_number",
              )}
              required
              error={shown("rectifies_invoice_number")}
            >
              {text("rectifies", "rectifies_invoice_number", {
                suggestions: invoiceNumberOptions(
                  invoices.filter(
                    (other) => other.invoice_id !== invoice.invoice_id,
                  ),
                  { kind: invoice.kind, party: correction.counterpartyName },
                  locale,
                ),
              })}
            </FormField>
          )}
          <IvaCategoryField
            value={correction.ivaCategory}
            onChange={(value) => correct("ivaCategory", value)}
            unset={t("desktop.ledger.invoices.none")}
          />
          <OperationTypeField
            value={correction.operationType}
            onChange={(value) => correct("operationType", value)}
          />
        </div>
      </EditorSection>

      <EditorSection
        title={t("desktop.ledger.invoices.lines")}
        aside={
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Icon name="lock" size="xs" />
            {t("desktop.ledger.invoices.lines_fixed")}
          </span>
        }
      >
        <StoredLines
          lines={invoice.lines}
          slots={preview.shown?.rate_slots ?? []}
          kind={invoice.kind}
          locale={locale}
        />
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.totals")}>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-accent p-3">
            <TotalsList
              locale={locale}
              currency={invoice.currency}
              base={invoice.base_total.decimal}
              iva={invoice.iva_total.decimal}
              total={invoice.grand_total.decimal}
              recargo={
                invoice.recargo_amount ? (
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-muted-foreground">
                      {t("desktop.ledger.invoices.field.recargo")}
                    </span>
                    <span className="tabular-nums">
                      {formatAmount(locale, invoice.recargo_amount.decimal)}
                    </span>
                  </div>
                ) : null
              }
            />
          </div>
          <Retention
            locale={locale}
            rate={correction.retentionRate}
            amount={correction.retentionAmount}
            answered={preview.current?.retention ?? null}
            net={preview.current?.totals.net_of_retention?.decimal ?? null}
            withheld={preview.current?.retention.amount?.decimal ?? null}
            rateError={shown("retention_rate")}
            amountError={shown("retention_amount")}
            onRate={(value) => correct("retentionRate", value)}
            onAmount={(value) => correct("retentionAmount", value)}
            onBlur={touch}
          />
        </div>
      </EditorSection>

      <EditorSection title={t("desktop.ledger.invoices.payment_section")}>
        <div className="grid grid-cols-2 gap-3">
          <FormField label={t("desktop.ledger.invoices.field.payment_status")}>
            {(control) => (
              <NativeSelect
                {...control}
                value={correction.paymentStatus}
                onChange={(event) =>
                  correct("paymentStatus", event.target.value as PaymentStatus)
                }
              >
                {PAYMENT_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {paymentLabel(t, status)}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField
            label={t("desktop.ledger.invoices.field.payment_id")}
            hint={t("desktop.ledger.invoices.hint.payment_id")}
            error={shown("payment_id")}
          >
            {(control) => (
              <TextEditor
                {...wired(control)}
                {...bind("paymentId", "payment_id")}
                suggestions={invoice.linked_transaction_ids
                  .filter((id) => isPaymentId(id) === true)
                  .map((id) => ({ value: id, label: id }))}
                mono
              />
            )}
          </FormField>
        </div>
      </EditorSection>

      <NotesField
        value={correction.notes}
        onChange={(value) => correct("notes", value)}
      />

      <InvoiceDocument port={port} invoiceId={invoice.invoice_id} say={say} />

      <EditorSection title={t("desktop.ledger.invoices.linked")}>
        <p className="flex items-center gap-1.5 text-base">
          <Icon name="link" size="xs" />
          {t("desktop.ledger.invoices.linked_count", {
            count: invoice.linked_transaction_ids.length,
          })}
        </p>
        <p className="text-xs text-muted-foreground">
          {t("desktop.ledger.invoices.links_permanent")}
        </p>
      </EditorSection>
    </>
  );
}
