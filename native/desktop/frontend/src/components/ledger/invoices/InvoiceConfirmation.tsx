import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount, formatPercent } from "../../../shared/numbers";
import { facts, labelGap } from "../../../shell/compose";
import type {
  CatalogueInvoice,
  InvoiceAddRequest,
} from "../../../shell/ledgerInvoiceOperations";
import type { InvoiceUpdateField } from "../../../shell/ledgerContract";
import { useStrings } from "../../../shell/strings";
import { ivaCategoryLabel } from "../movements/movementWords";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import {
  correctionOf,
  retentionRate,
  type CorrectionDraft,
} from "./invoiceModel";
import { classLabel, kindLabel, paymentLabel } from "./invoiceWords";

// ---- Confirmations ----------------------------------------------------------------

const FIELD_LABELS: Record<InvoiceUpdateField, string> = {
  counterparty_name: "counterparty_name",
  counterparty_country: "counterparty_country",
  notes: "notes",
  payment_status: "payment_status",
  iva_category: "iva_category",
  operation_type: "operation_type",
  operation_date: "operation_date",
  retention_rate: "retention_rate",
  retention_amount: "retention_amount",
  series: "series",
  invoice_class: "invoice_class",
  rectifies_invoice_number: "rectifies_invoice_number",
  payment_id: "payment_id",
};

export function Confirmation({
  isNew,
  draftRequest,
  total,
  stored,
  correction,
  changed,
  locale,
}: {
  isNew: boolean;
  draftRequest: InvoiceAddRequest | null;
  total: string;
  stored: CatalogueInvoice | null;
  correction: CorrectionDraft | null;
  changed: readonly InvoiceUpdateField[];
  locale: string;
}) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  if (isNew && draftRequest)
    return (
      <Alert icon={<Icon name="info" />} className="ledger-invoice-confirm">
        <AlertTitle>
          {facts(t, [
            kindLabel(t, draftRequest.kind),
            draftRequest.invoice_number,
            formatDay(locale, draftRequest.issued_at),
            draftRequest.counterparty_name,
            formatAmount(locale, total, {
              currency: draftRequest.currency,
            }),
          ])}
        </AlertTitle>
        <AlertDescription>
          {t("desktop.ledger.invoices.confirm_new")}
        </AlertDescription>
      </Alert>
    );
  if (!stored || !correction) return null;
  const before = correctionOf(stored);
  const value = (draft: CorrectionDraft, field: InvoiceUpdateField): string => {
    switch (field) {
      case "counterparty_name":
        return draft.counterpartyName;
      case "counterparty_country":
        return draft.country.toUpperCase();
      case "notes":
        return draft.notes;
      case "payment_status":
        return paymentLabel(t, draft.paymentStatus);
      case "iva_category":
        return draft.ivaCategory ? ivaCategoryLabel(t, draft.ivaCategory) : "";
      case "operation_type":
        return draft.operationType;
      case "operation_date":
        return draft.operationDate
          ? formatDay(locale, draft.operationDate)
          : "";
      case "retention_rate": {
        const rate = retentionRate(draft.retentionRate);
        return rate.kind === "value"
          ? formatPercent(locale, rate.value, { unit: "fraction" })
          : draft.retentionRate;
      }
      case "retention_amount":
        return draft.retentionAmount;
      case "series":
        return draft.series;
      case "invoice_class":
        return classLabel(t, draft.invoiceClass);
      case "rectifies_invoice_number":
        return draft.invoiceClass === vocabulary.correctiveClass
          ? draft.rectifies
          : "";
      case "payment_id":
        return draft.paymentId;
    }
  };
  const blank = t("desktop.ledger.invoices.none");
  return (
    <Alert icon={<Icon name="info" />} className="ledger-invoice-confirm">
      <AlertTitle>
        {t("desktop.ledger.invoices.confirm_changes", {
          count: changed.length,
        })}
      </AlertTitle>
      <ul className="flex flex-col gap-0.5 text-sm">
        {changed.map((field) => (
          <li key={field} data-field={field}>
            <span className="font-medium">
              {t(`desktop.ledger.invoices.field.${FIELD_LABELS[field]}`)}
            </span>
            {labelGap(t)}
            {field === "payment_id" ? null : (
              <>
                <span className="text-muted-foreground">
                  {value(before, field) || blank}
                </span>
                {" → "}
              </>
            )}
            <span>{value(correction, field) || blank}</span>
          </li>
        ))}
      </ul>
    </Alert>
  );
}

export function RemoveConfirmation({ invoice }: { invoice: CatalogueInvoice }) {
  const t = useStrings();
  const linked = invoice.linked_transaction_ids.length;
  return linked > 0 ? (
    <Alert
      tone="danger"
      role="alert"
      icon={<Icon name="lock" />}
      className="ledger-invoice-remove"
    >
      <AlertTitle>{t("desktop.ledger.invoices.remove_linked")}</AlertTitle>
      <AlertDescription>
        {t("desktop.ledger.invoices.remove_linked_note", { count: linked })}
      </AlertDescription>
    </Alert>
  ) : (
    <Alert
      tone="warning"
      icon={<Icon name="trash" />}
      className="ledger-invoice-remove"
    >
      <AlertTitle>{t("desktop.ledger.invoices.remove_question")}</AlertTitle>
      <AlertDescription>
        {t("desktop.ledger.invoices.remove_note")}
      </AlertDescription>
    </Alert>
  );
}

/** Asks before dismissing an edited invoice; the controller owns the decision. */
export function InvoiceDiscardConfirmation({
  isNew,
  onKeep,
  onDiscard,
}: {
  isNew: boolean;
  onKeep(): void;
  onDiscard(): void;
}) {
  const t = useStrings();
  return (
    <Alert
      tone="warning"
      role="alertdialog"
      aria-labelledby="ledger-invoice-discard"
      icon={<Icon name="alert" />}
      className="ledger-invoice-discard"
    >
      <AlertTitle id="ledger-invoice-discard">
        {t(
          isNew
            ? "desktop.ledger.invoices.discard_new"
            : "desktop.ledger.invoices.discard_changes",
        )}
      </AlertTitle>
      <AlertDescription>
        {t("desktop.ledger.invoices.discard_note")}
      </AlertDescription>
      <div className="mt-1 flex gap-2">
        <Button size="xs" autoFocus onClick={onKeep}>
          {t("desktop.ledger.invoices.keep_editing")}
        </Button>
        <Button size="xs" variant="destructive" onClick={onDiscard}>
          {t("desktop.ledger.invoices.discard")}
        </Button>
      </div>
    </Alert>
  );
}
