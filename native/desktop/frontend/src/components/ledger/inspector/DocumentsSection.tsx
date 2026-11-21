import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Icon } from "@/components/ui/icon";
import { facts, listed } from "@/shell/compose";
import type { LedgerEvidenceListProjection } from "../../../shell/ledgerDocumentContract";
import type { LedgerPort } from "../../../shell/ledger";
import type { LedgerStagedRowAnswer } from "../../../shell/ledgerMovementCheckContract";
import {
  newIdempotencyKey,
  type StageEvent,
  type StagedAction,
} from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { fileName } from "../documents/documentsModel";
import type { InspectorRead } from "./useInspectorReads";
import { formatTime } from "../../../shared/dateFormats";
import {
  documentAttachmentReference,
  movementDocuments,
  type DocumentRole,
} from "./movementDocuments";
import type { LedgerTransactionReviewProjection } from "../../../shell/ledgerReadContract";
import { DocumentReadability, PurchaseRelease } from "./EvidenceDoors";

type DocumentAction = Extract<
  StagedAction,
  { kind: "attach" | "detach" | "attach_file" }
>;

/**
 * The inspector's Documents section: the movement's purchase invoice and
 * other attachments, each with what the ledger found about its stored file.
 * Supplementary attachments are detached through the staged changes; the
 * purchase evidence is released at once, unlinked or kept as an ordinary
 * document, against the movement as it was read. An existing document
 * to attach, and a document from this computer to add and attach. While the
 * movement has no purchase invoice, the person says what a document is
 * before it is staged: nothing makes a file the purchase invoice unasked. A
 * missing document is shown with the ledger's advice. Every other change
 * is staged.
 */
export function DocumentsSection({
  port,
  row,
  answer,
  evidence,
  actions,
  onStage,
  locale,
  onWritten,
  say,
}: {
  port: LedgerPort;
  row: LedgerTransactionReviewProjection;
  /** The ledger's answer about the movement; absent until it has answered. */
  answer: LedgerStagedRowAnswer | undefined;
  evidence: InspectorRead<LedgerEvidenceListProjection> | null;
  actions: readonly StagedAction[];
  onStage: (event: StageEvent) => void;
  locale: string;
  /** Reads the movement and its documents again after a write that saved. */
  onWritten: () => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const tx = row.transaction;
  const id = tx.transaction_id;
  const [picking, setPicking] = useState(false);
  const [pickFailed, setPickFailed] = useState(false);
  const [chosenRole, setChosenRole] = useState<DocumentRole | null>(null);
  const records = evidence?.kind === "ready" ? evidence.result.rows : [];
  const documents = movementDocuments(tx, records);
  const purchase = documents.purchase;
  const linked = purchase?.record ?? null;
  const lock = !answer
    ? t("desktop.ledger.apply.reading")
    : answer.takes_changes
      ? null
      : t("desktop.ledger.inspector.documents.active_only");
  const staged = actions.filter(
    (action): action is DocumentAction =>
      action.kind === "attach" ||
      action.kind === "detach" ||
      action.kind === "attach_file",
  );
  // Purchase evidence, once linked or staged, is the only one: any further
  // document can only be another document.
  const purchaseOpen =
    tx.purchase_invoice_evidence_id === null &&
    !staged.some(
      (action) =>
        (action.kind === "attach" && action.evidenceId !== null) ||
        (action.kind === "attach_file" && !action.supplementary),
    );
  const role: DocumentRole | null = purchaseOpen ? chosenRole : "other";
  const detaching = new Set(
    staged.flatMap((action) =>
      action.kind === "detach" ? action.attachmentIds : [],
    ),
  );
  const recordOf = (attachment: string) =>
    records.find((found) => found.attachment_id === attachment);
  const nameOf = (attachment: string) => {
    const record = recordOf(attachment);
    return record ? fileName(record.source_path) : attachment.slice(0, 12);
  };
  const needsEvidence = answer?.evidence_advised ?? false;

  const attachable: ComboboxOption[] = records
    .filter(
      (record) =>
        record.evidence_id !== tx.purchase_invoice_evidence_id &&
        !tx.attachment_ids.includes(record.attachment_id),
    )
    .map((record) => ({
      value: record.evidence_id,
      label: fileName(record.source_path),
      note: facts(t, [record.supplier, record.invoice_number]),
      // The number stays whole where the note wraps.
      ...(record.invoice_number ? { whole: record.invoice_number } : {}),
    }));

  const detach = (attachment: string) => {
    onStage({
      type: "stage_action",
      action: {
        id: `detach:${id}:${attachment}`,
        kind: "detach",
        transactionId: id,
        attachmentIds: [attachment],
      },
    });
    say(t("desktop.ledger.inspector.documents.detach_staged"));
  };
  const pick = async () => {
    setPicking(true);
    setPickFailed(false);
    try {
      if (!role) return;
      const picks = await port.pickFiles(
        "documents",
        "file",
        t("desktop.ledger.import.filter.documents"),
      );
      const file = picks.files[0];
      if (file && role) {
        onStage({
          type: "stage_action",
          action: {
            id: `attach_file:${id}:${file.token}`,
            kind: "attach_file",
            transactionId: id,
            file: file.token,
            name: file.name,
            idempotencyKey: newIdempotencyKey(),
            supplementary: role === "other",
          },
        });
        setChosenRole(null);
        say(
          t("desktop.ledger.inspector.documents.add_staged", {
            file: file.name,
          }),
        );
      }
    } catch {
      setPickFailed(true);
    } finally {
      setPicking(false);
    }
  };

  return (
    <div className="grid gap-3">
      {lock && <Alert icon={<Icon name="lock" />}>{lock}</Alert>}
      {purchase && (
        <div className="ledger-purchase-evidence flex items-start gap-2 text-sm">
          <Icon name={linked?.media_kind === "image" ? "image" : "page"} />
          <span className="grid min-w-0 flex-1">
            <span className="break-words">
              {linked
                ? fileName(linked.source_path)
                : t("desktop.ledger.inspector.documents.purchase_linked")}
            </span>
            <span className="text-xs text-muted-foreground">
              {linked
                ? t("desktop.ledger.inspector.documents.purchase_invoice", {
                    date: formatTime(locale, linked.created_at),
                  })
                : evidence?.kind === "reading"
                  ? t("desktop.ledger.loading")
                  : t(
                      "desktop.ledger.inspector.documents.purchase_details_unavailable",
                    )}
            </span>
            {linked && (
              <DocumentReadability
                port={port}
                record={linked}
                onWritten={onWritten}
                say={say}
              />
            )}
            <PurchaseRelease
              port={port}
              transaction={tx}
              locked={lock !== null}
              onWritten={onWritten}
              say={say}
            />
          </span>
        </div>
      )}
      {documents.supplementary.length > 0 ? (
        <ul className="ledger-attachments grid gap-1">
          {documents.supplementary.map((attachment) => {
            const record = recordOf(attachment);
            return (
              <li key={attachment} className="flex items-start gap-2 text-sm">
                <Icon name="page" />
                <span className="grid min-w-0 flex-1">
                  <span className="break-words">{nameOf(attachment)}</span>
                  {record && (
                    <DocumentReadability
                      port={port}
                      record={record}
                      onWritten={onWritten}
                      say={say}
                    />
                  )}
                </span>
                {detaching.has(attachment) ? (
                  <span className="text-xs">
                    {t("desktop.ledger.inspector.documents.detach_pending")}
                  </span>
                ) : (
                  <Button
                    variant="ghost"
                    size="xs"
                    disabled={lock !== null}
                    aria-label={t(
                      "desktop.ledger.inspector.documents.detach_named",
                      { file: nameOf(attachment) },
                    )}
                    onClick={() => detach(attachment)}
                  >
                    {t("desktop.ledger.inspector.documents.detach")}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      ) : purchase ? null : needsEvidence ? (
        <Alert icon={<Icon name="info" />}>
          {t("desktop.ledger.inspector.documents.advisory")}
        </Alert>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.inspector.documents.none")}
        </p>
      )}

      {staged.length > 0 && (
        <ul className="grid gap-1">
          {staged.map((action) => (
            <li key={action.id} className="flex items-center gap-2 text-sm">
              <span
                aria-hidden="true"
                className="h-4 border-l-2 border-dashed border-foreground"
              />
              <span className="min-w-0 flex-1 break-words">
                {action.kind === "attach_file"
                  ? t(
                      action.supplementary
                        ? "desktop.ledger.inspector.documents.adding_other"
                        : "desktop.ledger.inspector.documents.adding_purchase",
                      { file: action.name },
                    )
                  : action.kind === "attach"
                    ? t(
                        action.evidenceId === null
                          ? "desktop.ledger.inspector.documents.attaching_other"
                          : "desktop.ledger.inspector.documents.attaching_purchase",
                        {
                          file: action.evidenceId
                            ? fileName(
                                records.find(
                                  (record) =>
                                    record.evidence_id === action.evidenceId,
                                )?.source_path ?? action.evidenceId,
                              )
                            : listed(t, action.attachmentIds.map(nameOf)),
                        },
                      )
                    : t("desktop.ledger.inspector.documents.detaching", {
                        file: listed(t, action.attachmentIds.map(nameOf)),
                      })}
              </span>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => onStage({ type: "drop_action", id: action.id })}
              >
                {t("desktop.ledger.inspector.drop")}
              </Button>
            </li>
          ))}
        </ul>
      )}

      {purchaseOpen && (
        <div className="grid gap-1">
          <span
            id={`documents-kind-${id}`}
            className="text-xs text-muted-foreground"
          >
            {t("desktop.ledger.inspector.documents.kind.label")}
          </span>
          <div
            role="radiogroup"
            aria-labelledby={`documents-kind-${id}`}
            className="ledger-document-kind flex flex-wrap gap-1"
          >
            {(["purchase", "other"] as const).map((choice) => (
              <Button
                key={choice}
                role="radio"
                aria-checked={chosenRole === choice}
                variant={chosenRole === choice ? "outline" : "ghost"}
                size="xs"
                disabled={lock !== null}
                onClick={() => setChosenRole(choice)}
              >
                {t(
                  choice === "purchase"
                    ? "desktop.ledger.inspector.documents.kind.purchase"
                    : "desktop.ledger.inspector.documents.kind.other",
                )}
              </Button>
            ))}
          </div>
          {!chosenRole && (
            <p className="text-xs text-muted-foreground">
              {t("desktop.ledger.inspector.documents.kind.choose")}
            </p>
          )}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <Combobox
          label={t("desktop.ledger.inspector.documents.attach_existing")}
          value={null}
          options={attachable}
          placeholder={t("desktop.ledger.inspector.documents.search")}
          emptyLabel={
            evidence?.kind === "reading"
              ? t("desktop.ledger.loading")
              : t("desktop.ledger.inspector.documents.no_free")
          }
          onCommit={(chosen) => {
            const record = records.find(
              (record) => record.evidence_id === chosen,
            );
            if (!record || !role) return;
            onStage({
              type: "stage_action",
              action: {
                id: `attach:${id}:${chosen}`,
                kind: "attach",
                transactionId: id,
                ...documentAttachmentReference(record, role),
              },
            });
            setChosenRole(null);
            say(t("desktop.ledger.inspector.documents.attach_staged"));
          }}
        >
          <Button
            variant="outline"
            size="sm"
            disabled={lock !== null || role === null}
          >
            <Icon name="attach" />
            {t("desktop.ledger.inspector.documents.attach_existing")}
          </Button>
        </Combobox>
        <Button
          variant="outline"
          size="sm"
          disabled={lock !== null || picking || role === null}
          onClick={() => void pick()}
        >
          <Icon name="folder" />
          {t("desktop.ledger.inspector.documents.add_file")}
        </Button>
      </div>
      {pickFailed && (
        <p role="alert" className="text-sm">
          {t("desktop.ledger.inspector.documents.pick_failed")}
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        {t("desktop.ledger.inspector.documents.hint")}
      </p>
    </div>
  );
}
