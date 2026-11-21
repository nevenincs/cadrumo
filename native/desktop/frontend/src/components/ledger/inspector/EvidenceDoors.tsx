import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { servedRefusalWords, type LedgerPort } from "../../../shell/ledger";
import type { LedgerEvidenceRecordProjection } from "../../../shell/ledgerDocumentContract";
import type { LedgerTransactionProjection } from "../../../shell/ledgerInvoiceContract";
import { useStrings } from "../../../shell/strings";
import { fileName } from "../documents/documentsModel";
import { write, type WriteAnswer } from "../invoices/invoiceWrites";
import { landingSettle, useWritePause, WriteHold } from "../WritePause";
import {
  RELEASE_CAUSE_WORDS,
  RELEASE_STEP_WORDS,
  UNREADABLE_CAUSE_WORDS,
  releaseLanding,
  releaseRefusalOf,
  verifyLanding,
} from "./evidenceDoorWords";

// The Documents section's doors that write at once rather than being
// staged: checking whether a stored document's file can be read, and
// releasing the movement's purchase document. Each is sent once; an outcome
// that was not seen holds the page's writes until the ledger is read again.

/** What the last write of a door came to, where it did not save. */
type Notice =
  /** Refused, in the words of what the ledger served: the cause and the
   * step, or its sentence, or nothing more than that it was not done. */
  { kind: "refused"; lines: string[] } | { kind: "unknown" };

/** The sentence the ledger served for a refusal, where it served one. */
function servedLines(sent: WriteAnswer<unknown>): string[] {
  const words =
    sent.kind === "refused" ? servedRefusalWords(sent.detail) : null;
  return words ? [words] : [];
}

function NoticeAlert({ notice }: { notice: Notice | null }) {
  const t = useStrings();
  if (notice?.kind === "refused")
    return (
      <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
        <AlertTitle>{t("desktop.ledger.documents.not_done")}</AlertTitle>
        {notice.lines.map((line) => (
          <AlertDescription key={line}>{line}</AlertDescription>
        ))}
      </Alert>
    );
  if (notice?.kind === "unknown")
    return (
      <Alert tone="warning" role="alert" icon={<Icon name="unknown" />}>
        <AlertTitle>{t("desktop.ledger.documents.unknown")}</AlertTitle>
        <AlertDescription>
          {t("desktop.ledger.documents.unknown_note")}
        </AlertDescription>
      </Alert>
    );
  return null;
}

/**
 * What the ledger found about a document's stored file: nothing more for a
 * readable one, the cause for an unreadable one, and for one not checked
 * yet a door that checks it now and reads the documents again.
 */
export function DocumentReadability({
  port,
  record,
  onWritten,
  say,
}: {
  port: LedgerPort;
  record: LedgerEvidenceRecordProjection;
  onWritten: () => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const name = fileName(record.source_path);

  async function check() {
    setBusy(true);
    setNotice(null);
    const sent = await write(port, "ledger.evidence.verify", {
      evidence_id: record.evidence_id,
    });
    setBusy(false);
    if (sent.kind === "done") {
      if (sent.result.outcome.kind === "refused")
        setNotice({
          kind: "refused",
          lines: [t("desktop.ledger.inspector.documents.readability.gone")],
        });
      else {
        say(t("desktop.ledger.inspector.documents.readability.checked"));
        onWritten();
      }
    } else if (sent.kind === "unknown") {
      setNotice({ kind: "unknown" });
      pause.hold({
        what: name,
        outcome: sent.saved ? "saved_unread" : "unknown",
        settle: landingSettle(t, name, verifyLanding(port, record)),
      });
    } else
      setNotice({
        kind: "refused",
        lines:
          sent.kind === "refused" &&
          sent.reason === "REFUSED_LEDGER_EVIDENCE_NOT_FOUND"
            ? [t("desktop.ledger.inspector.documents.readability.gone")]
            : servedLines(sent),
      });
  }

  if (record.readability === "readable") return null;
  return (
    <span className="ledger-document-readability grid gap-1">
      {record.readability === "unreadable" ? (
        <span
          data-readability="unreadable"
          className="flex items-start gap-1 text-xs"
        >
          <Icon name="alert" size="xs" className="mt-0.5 text-warning" />
          <span>
            {t("desktop.ledger.inspector.documents.readability.unreadable")}
            {record.unreadable_cause && (
              <>
                {" · "}
                {t(UNREADABLE_CAUSE_WORDS[record.unreadable_cause])}
              </>
            )}
          </span>
        </span>
      ) : (
        <span
          data-readability="unchecked"
          className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
        >
          <Icon name="pending" size="xs" />
          {t("desktop.ledger.inspector.documents.readability.unchecked")}
          <WriteHold>
            <Button
              variant="outline"
              size="xs"
              className="ledger-document-check"
              disabled={busy}
              aria-label={t(
                "desktop.ledger.inspector.documents.readability.check_named",
                { file: name },
              )}
              onClick={() => void check()}
            >
              {busy && <Spinner className="size-icon-xs" />}
              {t("desktop.ledger.documents.check")}
            </Button>
          </WriteHold>
        </span>
      )}
      <NoticeAlert notice={notice} />
    </span>
  );
}

/**
 * The two ways back from the movement's purchase document: unlink it, or
 * keep it on the movement as an ordinary document. Each is sent with the
 * evidence and the modification time the opened movement shows, so a
 * movement changed since is refused rather than changed; a refusal says its
 * cause and what to do, and a release reads the movement again.
 */
export function PurchaseRelease({
  port,
  transaction,
  locked,
  onWritten,
  say,
}: {
  port: LedgerPort;
  transaction: Pick<
    LedgerTransactionProjection,
    "transaction_id" | "purchase_invoice_evidence_id" | "modified_at"
  >;
  /** Why the movement takes no document change now, or null. */
  locked: boolean;
  onWritten: () => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const [busy, setBusy] = useState<"detach" | "keep_as_document" | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const evidenceId = transaction.purchase_invoice_evidence_id;
  if (evidenceId === null) return null;

  async function release(disposition: "detach" | "keep_as_document") {
    if (evidenceId === null) return;
    setBusy(disposition);
    setNotice(null);
    const sent = await write(port, "ledger.purchase_evidence.release", {
      transaction_id: transaction.transaction_id,
      expected_purchase_invoice_evidence_id: evidenceId,
      expected_modified_at: transaction.modified_at,
      disposition,
    });
    setBusy(null);
    const refusal =
      sent.kind === "refused"
        ? releaseRefusalOf(sent.detail)
        : sent.kind === "done" && sent.result.outcome === "refused"
          ? sent.result.refusal
          : null;
    if (refusal)
      setNotice({
        kind: "refused",
        lines: [
          t(RELEASE_CAUSE_WORDS[refusal.cause]),
          t(RELEASE_STEP_WORDS[refusal.next_step]),
        ],
      });
    else if (sent.kind === "done") {
      say(
        t(
          disposition === "detach"
            ? "desktop.ledger.inspector.documents.release.detached"
            : "desktop.ledger.inspector.documents.release.kept",
        ),
      );
      onWritten();
    } else if (sent.kind === "unknown") {
      setNotice({ kind: "unknown" });
      const what = t("desktop.ledger.inspector.documents.purchase_linked");
      pause.hold({
        what,
        outcome: sent.saved ? "saved_unread" : "unknown",
        settle: landingSettle(
          t,
          what,
          releaseLanding(port, transaction.transaction_id, evidenceId),
        ),
      });
    } else
      setNotice({
        kind: "refused",
        lines: servedLines(sent),
      });
  }

  return (
    <div className="ledger-purchase-release grid gap-1">
      <div className="flex flex-wrap items-center gap-1">
        {(["detach", "keep_as_document"] as const).map((disposition) => (
          <WriteHold key={disposition}>
            <Button
              variant="ghost"
              size="xs"
              data-release={disposition}
              disabled={locked || busy !== null}
              onClick={() => void release(disposition)}
            >
              {busy === disposition && <Spinner className="size-icon-xs" />}
              {t(
                disposition === "detach"
                  ? "desktop.ledger.inspector.documents.release.detach"
                  : "desktop.ledger.inspector.documents.release.keep",
              )}
            </Button>
          </WriteHold>
        ))}
      </div>
      <NoticeAlert notice={notice} />
    </div>
  );
}
