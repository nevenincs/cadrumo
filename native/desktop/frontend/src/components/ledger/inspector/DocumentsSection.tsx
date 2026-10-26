import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Icon } from "@/components/ui/icon";
import type {
  EvidenceListResult,
  LedgerPort,
  LedgerRow,
} from "../../../shell/ledger";
import {
  newIdempotencyKey,
  type StageEvent,
  type StagedAction,
} from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { fileName } from "../documents/documentsModel";
import { stampText } from "../movements/movementWords";
import type { InspectorRead } from "./useInspectorReads";

type DocumentAction = Extract<
  StagedAction,
  { kind: "attach" | "detach" | "attach_file" }
>;

/**
 * The inspector's Documents section: the movement's purchase invoice and
 * other attachments, each of which can be detached, an existing document
 * to attach, and a document from this computer to add and attach. A
 * missing document is advice, never a block. Every change is staged.
 */
export function DocumentsSection({
  port,
  row,
  evidence,
  actions,
  onStage,
  locale,
  say,
}: {
  port: LedgerPort;
  row: LedgerRow;
  evidence: InspectorRead<EvidenceListResult> | null;
  actions: readonly StagedAction[];
  onStage: (event: StageEvent) => void;
  locale: string;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const tx = row.transaction;
  const id = tx.transaction_id;
  const [picking, setPicking] = useState(false);
  const [pickFailed, setPickFailed] = useState(false);
  const records = evidence?.kind === "ready" ? evidence.result.rows : [];
  const linked = tx.purchase_invoice_evidence_id
    ? (records.find(
        (record) => record.evidence_id === tx.purchase_invoice_evidence_id,
      ) ?? null)
    : null;
  const lock =
    tx.lifecycle_state === "ACTIVE"
      ? null
      : t("desktop.ledger.inspector.documents.active_only");
  const staged = actions.filter(
    (action): action is DocumentAction =>
      action.kind === "attach" ||
      action.kind === "detach" ||
      action.kind === "attach_file",
  );
  const detaching = new Set(
    staged.flatMap((action) =>
      action.kind === "detach" ? action.attachmentIds : [],
    ),
  );
  const nameOf = (attachment: string) => {
    const record = records.find((found) => found.attachment_id === attachment);
    return record ? fileName(record.source_path) : attachment.slice(0, 12);
  };
  const needsEvidence =
    tx.lifecycle_state === "ACTIVE" &&
    tx.direction === "OUTGOING" &&
    (tx.business_classification === "BUSINESS" ||
      tx.business_classification === "MIXED") &&
    !tx.purchase_invoice_evidence_id;

  const attachable: ComboboxOption[] = records
    .filter(
      (record) =>
        record.evidence_id !== tx.purchase_invoice_evidence_id &&
        !tx.attachment_ids.includes(record.attachment_id),
    )
    .map((record) => ({
      value: record.evidence_id,
      label: fileName(record.source_path),
      note: [record.supplier, record.invoice_number]
        .filter(Boolean)
        .join(" · "),
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
      const picks = await port.pickFiles(
        "documents",
        "file",
        t("desktop.ledger.import.filter.documents"),
      );
      const file = picks.files[0];
      if (file) {
        onStage({
          type: "stage_action",
          action: {
            id: `attach_file:${id}:${file.token}`,
            kind: "attach_file",
            transactionId: id,
            file: file.token,
            name: file.name,
            idempotencyKey: newIdempotencyKey(),
          },
        });
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
      {tx.attachment_ids.length > 0 ? (
        <ul className="ledger-attachments grid gap-1">
          {tx.attachment_ids.map((attachment) => {
            const evidenceRow =
              linked !== null && linked.attachment_id === attachment;
            return (
              <li key={attachment} className="flex items-center gap-2 text-sm">
                <Icon
                  name={
                    evidenceRow && linked.media_kind === "image"
                      ? "image"
                      : "page"
                  }
                />
                <span className="grid min-w-0 flex-1">
                  <span className="break-words">{nameOf(attachment)}</span>
                  {evidenceRow && (
                    <span className="text-xs text-muted-foreground">
                      {t(
                        "desktop.ledger.inspector.documents.purchase_invoice",
                        {
                          date: stampText(locale, linked.created_at),
                        },
                      )}
                    </span>
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
                      {
                        file: nameOf(attachment),
                      },
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
      ) : needsEvidence ? (
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
                  ? t("desktop.ledger.inspector.documents.adding", {
                      file: action.name,
                    })
                  : action.kind === "attach"
                    ? t("desktop.ledger.inspector.documents.attaching", {
                        file: action.evidenceId
                          ? fileName(
                              records.find(
                                (record) =>
                                  record.evidence_id === action.evidenceId,
                              )?.source_path ?? action.evidenceId,
                            )
                          : action.attachmentIds.map(nameOf).join(", "),
                      })
                    : t("desktop.ledger.inspector.documents.detaching", {
                        file: action.attachmentIds.map(nameOf).join(", "),
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

      <div className="flex flex-wrap gap-2">
        <Combobox
          label={t("desktop.ledger.inspector.documents.attach_existing")}
          value={null}
          options={attachable}
          emptyLabel={
            evidence?.kind === "reading"
              ? t("desktop.ledger.loading")
              : t("desktop.ledger.inspector.documents.no_free")
          }
          onCommit={(chosen) => {
            onStage({
              type: "stage_action",
              action: {
                id: `attach:${id}:${chosen}`,
                kind: "attach",
                transactionId: id,
                evidenceId: chosen,
                attachmentIds: [],
              },
            });
            say(t("desktop.ledger.inspector.documents.attach_staged"));
          }}
        >
          <Button variant="outline" size="sm" disabled={lock !== null}>
            <Icon name="attach" />
            {t("desktop.ledger.inspector.documents.attach_existing")}
          </Button>
        </Combobox>
        <Button
          variant="outline"
          size="sm"
          disabled={lock !== null || picking}
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
