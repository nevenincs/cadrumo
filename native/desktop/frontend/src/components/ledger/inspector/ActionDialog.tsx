import { useEffect, useId, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  ledgerFailure,
  type LedgerPort,
  type LedgerRemoveResult,
  type LedgerRow,
} from "../../../shell/ledger";
import type { StageEvent } from "../../../shell/ledgerStage";
import { readAnswer } from "../../../shell/ledgerWindow";
import { useStrings } from "../../../shell/strings";
import {
  lifecycleAction,
  lifecycleTakes,
  type LifecycleAction,
} from "./inspectorModel";
import { declarationName, lifecycleName } from "./inspectorWords";

/** The action a dialog stages, on the movements it names. */
export type ActionRequest =
  | {
      kind: LifecycleAction;
      ids: readonly string[];
      /** The reason the dialog starts from, which the person can change. */
      reason?: string;
    }
  | { kind: "remove"; id: string }
  | { kind: "merge"; ids: readonly string[] };

type Preview =
  | { kind: "reading" }
  | { kind: "ready"; report: LedgerRemoveResult["report"] }
  | { kind: "failed"; code: string };

/**
 * Stages a lifecycle change, a removal or a merge, with one reason for
 * all. A removal first asks the ledger what it would take with it and
 * what stops it, which changes nothing; a movement a finalized declaration
 * cites cannot be removed. Nothing is saved here.
 */
export function ActionDialog({
  port,
  request,
  rows,
  sealed,
  onStage,
  onClose,
  onClosed,
  say,
}: {
  port: LedgerPort;
  request: ActionRequest;
  rows: ReadonlyMap<string, LedgerRow>;
  sealed: ReadonlySet<string>;
  onStage: (event: StageEvent) => void;
  onClose: () => void;
  /** Called as the dialog closes, to hand focus back. */
  onClosed?: () => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const reasonId = useId();
  const [reason, setReason] = useState(
    "reason" in request ? (request.reason ?? "") : "",
  );
  const [preview, setPreview] = useState<Preview | null>(
    request.kind === "remove" ? { kind: "reading" } : null,
  );
  const removing = request.kind === "remove" ? request.id : null;
  useEffect(() => {
    if (removing === null) return;
    let active = true;
    void (async () => {
      let next: Preview;
      try {
        const answer = readAnswer(
          await port.submit("ledger.remove", {
            transaction_id: removing,
            dry_run: true,
          }),
        );
        next =
          answer.kind === "answer"
            ? { kind: "ready", report: answer.result.report }
            : {
                kind: "failed",
                code:
                  answer.failure.kind === "unsettled"
                    ? "unsettled"
                    : (answer.failure.reason ?? answer.failure.kind),
              };
      } catch (error) {
        const failure = ledgerFailure(error);
        next = { kind: "failed", code: failure.reason ?? failure.code };
      }
      if (active) setPreview(next);
    })();
    return () => {
      active = false;
    };
  }, [port, removing]);

  const lifecycle = request.kind !== "remove" && request.kind !== "merge";
  const takes = lifecycle
    ? request.ids.filter((id) => {
        const row = rows.get(id);
        return row !== undefined && lifecycleTakes(request.kind, row, sealed);
      })
    : [];
  const skipped = lifecycle ? request.ids.length - takes.length : 0;
  const blocked =
    preview?.kind === "ready" &&
    preview.report.blocking_modelo_references.length > 0;

  let title: string;
  if (request.kind === "remove")
    title = t("desktop.ledger.inspector.remove.title");
  else if (request.kind === "merge")
    title = t("desktop.ledger.inspector.merge.title", {
      count: request.ids.length,
    });
  else
    title = t("desktop.ledger.inspector.lifecycle.title", {
      action: lifecycleName(t, request.kind),
      count: takes.length,
    });

  const ready =
    request.kind === "remove"
      ? preview?.kind === "ready" && !blocked
      : request.kind === "merge"
        ? request.ids.length >= 2
        : takes.length > 0;

  const stage = () => {
    const why = reason.trim();
    if (request.kind === "remove")
      onStage({
        type: "stage_action",
        action: {
          id: `remove:${request.id}`,
          kind: "remove",
          transactionId: request.id,
          reason: why,
        },
      });
    else if (request.kind === "merge")
      onStage({
        type: "stage_action",
        action: {
          id: `merge:${[...request.ids].sort().join(":")}`,
          kind: "merge",
          childIds: [...request.ids],
          reason: why,
        },
      });
    else
      for (const id of takes)
        onStage({
          type: "stage_action",
          action: lifecycleAction(request.kind, id, why),
        });
    say(
      t("desktop.ledger.inspector.action_staged", {
        action: title,
      }),
    );
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="ledger-action-dialog w-dialog-md"
        closeLabel={t("desktop.ledger.inspector.cancel")}
        onCloseAutoFocus={(event) => {
          if (!onClosed) return;
          event.preventDefault();
          onClosed();
        }}
      >
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (ready) stage();
          }}
        >
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>
              {request.kind === "remove"
                ? t("desktop.ledger.inspector.remove.description")
                : request.kind === "merge"
                  ? t("desktop.ledger.inspector.merge.description")
                  : t("desktop.ledger.inspector.lifecycle.description")}
            </DialogDescription>
          </DialogHeader>
          {skipped > 0 && (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.inspector.lifecycle.skipped", {
                count: skipped,
              })}
            </p>
          )}
          {preview?.kind === "reading" && (
            <p role="status" className="flex items-center gap-2 text-sm">
              <Spinner />
              {t("desktop.ledger.inspector.remove.checking")}
            </p>
          )}
          {preview?.kind === "failed" && (
            <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
              <span className="grid gap-0.5">
                {t("desktop.ledger.inspector.remove.unchecked")}
                <code className="font-mono text-xs">{preview.code}</code>
              </span>
            </Alert>
          )}
          {preview?.kind === "ready" && (
            <div className="ledger-remove-preview grid gap-2 text-sm">
              {blocked ? (
                <Alert tone="danger" role="alert" icon={<Icon name="lock" />}>
                  <span className="grid gap-1">
                    {t("desktop.ledger.inspector.remove.blocked")}
                    <ul className="grid gap-0.5">
                      {preview.report.blocking_modelo_references.map(
                        (found) => (
                          <li key={found.calculation_revision_id}>
                            {declarationName(
                              t,
                              found.modelo,
                              found.filing_year,
                              found.period,
                            )}
                          </li>
                        ),
                      )}
                    </ul>
                  </span>
                </Alert>
              ) : (
                <ul className="grid gap-1">
                  <li>
                    {t("desktop.ledger.inspector.remove.evidence", {
                      count:
                        preview.report.cascaded_purchase_invoice_evidence_ids
                          .length,
                    })}
                  </li>
                  <li>
                    {t("desktop.ledger.inspector.remove.attachments", {
                      count: preview.report.cascaded_attachment_ids.length,
                    })}
                  </li>
                  {preview.report.stale_draft_revision_references.length >
                    0 && (
                    <li>
                      {t("desktop.ledger.inspector.remove.stale", {
                        declarations:
                          preview.report.stale_draft_revision_references
                            .map((found) =>
                              declarationName(
                                t,
                                found.modelo,
                                found.filing_year,
                                found.period,
                              ),
                            )
                            .join(", "),
                      })}
                    </li>
                  )}
                </ul>
              )}
            </div>
          )}
          <div className="grid gap-1">
            <label htmlFor={reasonId} className="text-sm">
              {t("desktop.ledger.inspector.reason")}
            </label>
            <Input
              id={reasonId}
              autoFocus
              maxLength={500}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              {t("desktop.ledger.inspector.cancel")}
            </Button>
            <Button
              type="submit"
              variant={request.kind === "remove" ? "destructive" : "primary"}
              disabled={!ready}
            >
              {request.kind === "remove"
                ? t("desktop.ledger.inspector.remove.stage")
                : t("desktop.ledger.inspector.stage")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
