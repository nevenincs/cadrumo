import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import {
  servedRefusalWords,
  type LedgerPort,
  type PickedFile,
} from "../../../shell/ledger";
import type { EvidenceKindProposalV1 } from "../../../shell/ledgerDocumentContract";
import { useStrings } from "../../../shell/strings";

/** What the ledger says a picked file is before it is staged: still being
 * read; read, with the kind its bytes support or none; refused as the add
 * would refuse it, with the sentence served for that; or not read, which
 * leaves the choice to the person as it always is. */
export type DocumentProbe =
  | { kind: "reading" }
  | { kind: "read"; proposal: EvidenceKindProposalV1 | null }
  | { kind: "refused"; words: string | null }
  | { kind: "unread" };

/** A file picked while the movement has no purchase invoice, waiting for
 * the person to say what it is. */
export type PendingFile = Pick<PickedFile, "token" | "name"> & {
  probe: DocumentProbe;
};

/** Asks the ledger what the picked file is. Never throws: a read that does
 * not settle is `unread`. */
export async function probeDocument(
  port: LedgerPort,
  file: Pick<PickedFile, "token">,
): Promise<DocumentProbe> {
  try {
    const outcome = await port.submit("ledger.evidence.probe", {
      source_path: file.token,
    });
    if (outcome.kind === "settled")
      return { kind: "read", proposal: outcome.result.kind_proposal };
    if (outcome.kind === "refused")
      return { kind: "refused", words: servedRefusalWords(outcome.detail) };
    return { kind: "unread" };
  } catch {
    return { kind: "unread" };
  }
}

/**
 * The picked file beside the kind choice: its name and a way to drop it,
 * and what the ledger found in its bytes. A kind the bytes support is shown
 * as the ledger's proposal, with one control that makes it the person's
 * choice; nothing is chosen for them. A file the add would refuse says so in
 * the words served for it.
 */
export function PendingDocument({
  file,
  onUseProposal,
  onDrop,
}: {
  file: PendingFile;
  /** Chooses the proposed kind, as choosing it by hand would. */
  onUseProposal: () => void;
  onDrop: () => void;
}) {
  const t = useStrings();
  const probe = file.probe;
  return (
    <div
      className="ledger-document-pending grid gap-1 text-sm"
      data-probe={probe.kind}
    >
      <span className="flex items-start gap-2">
        <Icon name="page" />
        <span className="min-w-0 flex-1 break-words">{file.name}</span>
        <Button variant="ghost" size="xs" onClick={onDrop}>
          {t("desktop.ledger.inspector.drop")}
        </Button>
      </span>
      {probe.kind === "reading" && (
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Spinner className="size-icon-xs" />
          {t("desktop.ledger.inspector.documents.kind.probing")}
        </span>
      )}
      {probe.kind === "read" && probe.proposal && (
        <span className="ledger-document-kind-proposal flex flex-wrap items-center gap-2 text-xs">
          <Icon name="info" size="xs" />
          <span>{t("desktop.ledger.inspector.documents.kind.proposal")}</span>
          <Button variant="outline" size="xs" onClick={onUseProposal}>
            {t("desktop.ledger.inspector.documents.kind.use_proposal")}
          </Button>
        </span>
      )}
      {probe.kind === "unread" && (
        <span className="text-xs text-muted-foreground">
          {t("desktop.ledger.inspector.documents.kind.probe_unread")}
        </span>
      )}
      {probe.kind === "refused" && (
        <Alert tone="warning" role="alert" icon={<Icon name="refused" />}>
          <AlertTitle>
            {t("desktop.ledger.inspector.documents.kind.probe_refused")}
          </AlertTitle>
          {probe.words && <AlertDescription>{probe.words}</AlertDescription>}
        </Alert>
      )}
    </div>
  );
}
