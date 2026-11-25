import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { LedgerEvidenceRecordProjection } from "../../../shell/ledgerDocumentContract";
import type { CatalogueInvoiceSnapshot } from "../../../shell/ledgerInvoiceContract";
import type { InvoiceDuplicateView } from "../../../shell/ledgerInvoiceDuplicate";
import type { StageEvent, StagedAction } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { seriesAndNumber } from "../invoices/invoiceModel";
import { invoiceLine } from "../matching/matchingWords";
import type { DocumentReference } from "./documentsModel";

/**
 * The catalogue invoice the reading would repeat, or a duplicate check that
 * failed: the document can be attached to the invoice's movement instead,
 * or confirmed anyway.
 */
export function DuplicateNotice({
  duplicateCheck,
  asked,
  duplicate,
  record,
  reference,
  actions,
  anyway,
  onAnyway,
  locale,
  onStage,
  say,
}: {
  duplicateCheck: InvoiceDuplicateView;
  /** The reading states enough to ask about a duplicate. */
  asked: boolean;
  duplicate: CatalogueInvoiceSnapshot | null;
  record: LedgerEvidenceRecordProjection | null;
  reference: DocumentReference;
  actions: StagedAction[];
  anyway: boolean;
  onAnyway(anyway: boolean): void;
  locale: string;
  onStage(event: StageEvent): void;
  say(text: string): void;
}) {
  const t = useStrings();
  const attachTarget =
    duplicate && record && reference.kind === "evidence"
      ? (duplicate.linked_transaction_ids[0] ?? null)
      : null;
  const attachId = attachTarget
    ? `attach:${attachTarget}:${reference.id}`
    : null;
  const attachStaged = actions.some((action) => action.id === attachId);
  return (
    <>
      {duplicateCheck.kind === "failed" && asked && (
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="unknown" />}
          className="ledger-draft-duplicate-failed"
        >
          <span>{t("desktop.ledger.documents.duplicate_check_failed")}</span>{" "}
          <Button variant="ghost" onClick={duplicateCheck.retry}>
            {t("desktop.ledger.documents.duplicate_check_retry")}
          </Button>
        </Alert>
      )}
      {duplicate && (
        <Alert
          tone="warning"
          icon={<Icon name="alert" />}
          className="ledger-draft-duplicate"
        >
          <AlertTitle>
            {t("desktop.ledger.documents.duplicate", {
              number: seriesAndNumber(duplicate),
            })}
          </AlertTitle>
          <AlertDescription className="grid gap-2">
            <span>{invoiceLine(t, locale, duplicate)}</span>
            <span className="flex flex-wrap items-center gap-2">
              {attachTarget && record && !attachStaged && (
                <Button
                  size="xs"
                  className="ledger-draft-attach"
                  onClick={() => {
                    onStage({
                      type: "stage_action",
                      action: {
                        id: attachId!,
                        kind: "attach",
                        transactionId: attachTarget,
                        evidenceId: record.evidence_id,
                        attachmentIds: [record.attachment_id],
                      },
                    });
                    say(t("desktop.ledger.documents.attach_staged"));
                  }}
                >
                  {t("desktop.ledger.documents.attach_to", {
                    number: seriesAndNumber(duplicate),
                  })}
                </Button>
              )}
              {attachStaged && (
                <span className="text-sm">
                  {t("desktop.ledger.documents.attach_staged")}
                </span>
              )}
              {!attachTarget && (
                <span className="text-sm">
                  {t("desktop.ledger.documents.no_movement_to_attach")}
                </span>
              )}
              <Button
                size="xs"
                variant="outline"
                className="ledger-draft-anyway"
                aria-pressed={anyway}
                onClick={() => onAnyway(!anyway)}
              >
                {t("desktop.ledger.documents.confirm_anyway")}
              </Button>
            </span>
          </AlertDescription>
        </Alert>
      )}
    </>
  );
}
