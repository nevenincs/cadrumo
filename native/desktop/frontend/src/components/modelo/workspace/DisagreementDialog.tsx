import { useState } from "react";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import type { CreditResolutionRowProjection } from "../../../shell/modeloContract/modeloWork";
import type { ModeloFormIssueLine } from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { BoxNumber } from "../form/BoxNumber";
import { ScopedWriteHoldNotice } from "../WriteScope";
import { Labelled } from "./CorrectionDialog";

/** The person's answer to one disagreement: an acceptance with its reason,
 * or the revocation of the acceptance stored at `expected_revision`. */
export type DisagreementAnswer =
  | { kind: "accept"; finding_id: string; reason: string }
  | { kind: "revoke"; finding_id: string; expected_revision: string };

/** What sending an answer came to. `done` committed it; `said` carries the
 * application's own words for a refusal; `refused` settled without changing
 * anything and served no words; `not_sent` never reached the runtime;
 * `unknown` may have committed and is never sent again until completion is
 * confirmed and the declaration is read again. */
export type DisagreementResult =
  | { kind: "done" }
  | { kind: "said"; words: string }
  | { kind: "refused" }
  | { kind: "not_sent" }
  | { kind: "unknown" };

/**
 * Answers one source disagreement a check line states, as the line offers:
 * accepts it with the person's reason, or revokes the acceptance stored for
 * it. What the disagreement is, what the acceptance covers and why an answer
 * was refused are the application's words; the dialog adds only its own
 * controls.
 */
export function DisagreementDialog({
  line,
  answer,
  onOpenChange,
  onAnswer,
  disabled = false,
}: {
  /** The line answered; the dialog is closed while it is null. */
  line: ModeloFormIssueLine | null;
  /** For a revocation, the acceptance it takes back as the list served it;
   * null while it is read or where it could not be. */
  answer: CreditResolutionRowProjection | null;
  onOpenChange(open: boolean): void;
  /** Null while an answer cannot be sent from here. */
  onAnswer:
    ((answer: DisagreementAnswer) => Promise<DisagreementResult>) | null;
  disabled?: boolean;
}) {
  const t = useStrings();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<DisagreementResult | null>(null);
  const offered = line?.resolution_answer ?? null;
  const findingId = line?.finding_id ?? null;
  const revoking = offered === "revoke";
  // The application says when the stored acceptance cannot be taken back:
  // its words are shown and nothing offers to revoke it.
  const unrevocable = revoking && answer !== null && !answer.revocable;
  // An outcome nobody saw may have committed: the dialog sends nothing more.
  const held = outcome?.kind === "unknown";
  const ready =
    onAnswer !== null &&
    findingId !== null &&
    !held &&
    (revoking ? answer !== null && answer.revocable : reason.trim() !== "");
  const close = (open: boolean) => {
    if (open) return;
    setReason("");
    setOutcome(null);
    onOpenChange(false);
  };
  const submit = async () => {
    if (disabled || busy || !ready || !onAnswer || findingId === null) return;
    setBusy(true);
    const result = await onAnswer(
      revoking && answer
        ? {
            kind: "revoke",
            finding_id: findingId,
            expected_revision: answer.revision_id,
          }
        : { kind: "accept", finding_id: findingId, reason: reason.trim() },
    );
    setBusy(false);
    if (result.kind === "done") close(false);
    else setOutcome(result);
  };
  const said =
    outcome === null
      ? null
      : outcome.kind === "said"
        ? outcome.words
        : outcome.kind === "refused"
          ? t("workspace.modelo.outcome.refused")
          : outcome.kind === "not_sent"
            ? t("workspace.modelo.outcome.failed")
            : null;
  return (
    <Dialog open={line !== null && offered !== null} onOpenChange={close}>
      <DialogContent
        className="w-palette"
        closeLabel={t("workspace.modelo.key.close")}
        data-disagreement={offered ?? undefined}
        aria-describedby={undefined}
      >
        <DialogHeader>
          <DialogTitle>
            {t(
              revoking
                ? "desktop.modelo.disagreement.revoke_title"
                : "desktop.modelo.disagreement.accept_title",
            )}
          </DialogTitle>
        </DialogHeader>
        {line && (
          <div className="flex flex-col gap-4">
            {line.answer_lead_words && (
              <p className="text-sm text-muted-foreground" data-answer-lead="">
                {line.answer_lead_words}
              </p>
            )}
            <div className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-3 rounded-lg border border-border px-3 py-2">
              <BoxNumber box={line.box} size="sm" />
              <span className="flex flex-col gap-1">
                {line.where && (
                  <span className="text-xs text-faint">{line.where}</span>
                )}
                <span className="text-base text-foreground">
                  {line.message}
                </span>
                <span className="text-sm text-muted-foreground">
                  {line.action}
                </span>
                {line.detail && (
                  <span className="text-sm text-muted-foreground">
                    {line.detail}
                  </span>
                )}
              </span>
            </div>
            {revoking ? (
              answer && (
                <div
                  data-answer=""
                  className="flex flex-col gap-1 text-sm text-muted-foreground"
                >
                  <span className="text-base text-foreground">
                    {answer.answer_words}
                  </span>
                  <span>
                    {t("desktop.modelo.disagreement.your_reason", {
                      reason: answer.reason,
                    })}
                  </span>
                  {unrevocable && answer.revoke_refusal_words && (
                    <span
                      className="text-sm text-foreground"
                      data-answer-unrevocable=""
                    >
                      {answer.revoke_refusal_words}
                    </span>
                  )}
                </div>
              )
            ) : (
              <Labelled label={t("desktop.modelo.disagreement.reason_label")}>
                {(id) => (
                  <TextEditor id={id} value={reason} onChange={setReason} />
                )}
              </Labelled>
            )}
          </div>
        )}
        {said && (
          <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
            {said}
          </Alert>
        )}
        <ScopedWriteHoldNotice />
        <DialogFooter>
          <Button variant="ghost" onClick={() => close(false)}>
            {t("workspace.modelo.editor.cancel")}
          </Button>
          {!unrevocable && (
            <Button
              data-answer-confirm=""
              disabled={disabled || !ready || busy}
              onClick={submit}
            >
              {t(
                revoking
                  ? "desktop.modelo.disagreement.confirm_revoke"
                  : "desktop.modelo.disagreement.confirm_accept",
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
