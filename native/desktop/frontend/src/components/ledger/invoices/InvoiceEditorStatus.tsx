import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { InvoiceFiguresPreviewRateSlot } from "../../../shell/ledgerInvoiceContract";
import { useStrings } from "../../../shell/strings";
import type { PlacedFindings, PreviewFinding } from "./invoiceModel";
import { findingText } from "./invoiceWords";
import type { Outcome } from "./useInvoiceEditorWrites";

/** What the ledger could not answer, or found with no field to show it on. */
export function PreviewNotes({
  failed,
  onRetry,
  refusedUnsaid,
  findings,
  slots,
}: {
  failed: boolean;
  onRetry(): void;
  refusedUnsaid: boolean;
  findings: PlacedFindings;
  slots: readonly InvoiceFiguresPreviewRateSlot[];
}) {
  const t = useStrings();
  const lineWarnings: PreviewFinding[] = Object.entries(
    findings.warnings,
  ).flatMap(([place, finding]) => (place.startsWith("line:") ? [finding] : []));
  const notes = [...findings.general, ...lineWarnings];
  return (
    <>
      {failed && (
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-invoice-unavailable"
        >
          <AlertTitle>
            {t("desktop.ledger.invoices.figures_unavailable")}
          </AlertTitle>
          <div className="mt-1">
            <Button size="xs" variant="outline" onClick={onRetry}>
              {t("desktop.ledger.invoices.figures_retry")}
            </Button>
          </div>
        </Alert>
      )}
      {refusedUnsaid && (
        <Alert
          tone="warning"
          icon={<Icon name="alert" />}
          className="ledger-invoice-would-refuse"
        >
          {t("desktop.ledger.invoices.would_refuse")}
        </Alert>
      )}
      {notes.length > 0 && (
        <Alert
          tone="warning"
          icon={<Icon name="alert" />}
          className="ledger-invoice-findings"
        >
          <ul className="flex flex-col gap-0.5 text-sm">
            {notes.map((finding) => (
              <li
                key={`${finding.code}-${finding.line_key ?? ""}`}
                data-finding={finding.code}
              >
                {findingText(t, finding, slots)}
              </li>
            ))}
          </ul>
        </Alert>
      )}
    </>
  );
}

export function OutcomeAlert({
  outcome,
  sending,
  onCheck,
}: {
  outcome: Outcome | null;
  sending: boolean;
  onCheck(): void;
}) {
  const t = useStrings();
  if (!outcome) return null;
  if (outcome.kind === "unknown")
    return (
      <Alert
        tone="danger"
        role="alert"
        icon={<Icon name="unknown" />}
        className="ledger-invoice-unknown"
      >
        <AlertTitle>{t("desktop.ledger.invoices.unknown")}</AlertTitle>
        <AlertDescription>
          {t(
            outcome.checked
              ? "desktop.ledger.invoices.unknown_unread"
              : "desktop.ledger.invoices.unknown_note",
          )}
        </AlertDescription>
        <div className="mt-1">
          <Button
            size="xs"
            variant="outline"
            pending={sending}
            onClick={onCheck}
          >
            {t("desktop.ledger.invoices.check")}
          </Button>
        </div>
      </Alert>
    );
  if (outcome.kind === "not_saved")
    return (
      <Alert
        tone="warning"
        icon={<Icon name="alert" />}
        className="ledger-invoice-not-saved"
      >
        {t("desktop.ledger.invoices.not_saved")}
      </Alert>
    );
  return (
    <Alert
      tone="danger"
      role="alert"
      icon={<Icon name="refused" />}
      className="ledger-invoice-refused"
    >
      {outcome.kind === "refused"
        ? outcome.text
        : t("desktop.ledger.invoices.failed")}
    </Alert>
  );
}
