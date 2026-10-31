import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  ledgerFailure,
  type LedgerLlmReviewMode,
  type LedgerLlmReviewRequest,
  type LedgerLlmSuggestion,
  type LedgerPort,
  type LedgerReview,
  type LedgerRow,
} from "../../../shell/ledger";
import { askReview, releaseReview } from "../../../shell/ledgerApply";
import { parsePercent } from "../../../shell/ledgerGrammar";
import type { StageEvent, StagedAction } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { useWritePause, WriteHold } from "../WritePause";
import { fieldName, refusalText, valueText } from "../editing/editingWords";
import { needsShare, suggestionWrites } from "./inspectorModel";
import { modelFailureText } from "./inspectorWords";
import { formatPercent } from "../../../shared/numbers";

type Ask = "suggest" | "share" | "reject";
type Shown = {
  definition: "ledger.classify.review" | "ledger.split.review";
  mode: LedgerLlmReviewMode;
  review: LedgerReview<LedgerLlmSuggestion>;
  /** Asked again to record a rejection with this reason. */
  rejecting?: string;
};
type State =
  | { kind: "idle" }
  | { kind: "asking"; ask: Ask }
  | { kind: "shown"; shown: Shown }
  /** The runtime's code, or `no_review` or `refused` where it gave none. */
  | { kind: "failed"; code: string };

const ORIGINS: Record<LedgerLlmReviewMode, LedgerLlmReviewRequest["origin"]> = {
  classification: "classify_llm_apply",
  saturated: "classify_llm_saturate_apply",
  auto_split: "classify_auto_split",
  split: "split_llm",
};

/**
 * A model's suggestion for one movement: a proposal from the local model
 * that only the person applies. Asking runs the registered review, which
 * pauses on what the model proposes; approving or rejecting stages the
 * answer to that review, bound to the digest of the review shown here, and
 * nothing is written until the changes are saved. A rejection's reason
 * and a Mixed proposal's share are part of the review's request, so they
 * are asked for again with it, and the new review is the one answered.
 * The runtime holds one waiting review per movement: a review asked again
 * or left for another movement is cancelled, and a new ask waits for that
 * to settle. A staged answer dropped is released where the stage is kept.
 */
export function ModelSuggestion({
  port,
  row,
  staged,
  onStage,
  locked,
  locale,
  rejectedBefore,
  say,
}: {
  port: LedgerPort;
  row: LedgerRow;
  /** The answer staged for this movement, if any. */
  staged: Extract<StagedAction, { kind: "suggestion" }> | undefined;
  onStage: (event: StageEvent) => void;
  locked: string | null;
  locale: string;
  rejectedBefore: boolean;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const { held: paused } = useWritePause();
  const id = row.transaction.transaction_id;
  const fieldId = useId();
  const [state, setState] = useState<State>({ kind: "idle" });
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [share, setShare] = useState("");
  const [shareError, setShareError] = useState<string | null>(null);
  // The review shown and not yet staged, and which ask is the latest: an
  // answer to an earlier ask is not shown.
  const pending = useRef<{ operation: string; movement: string } | null>(null);
  const asking = useRef(0);
  // Cancelling follows the port without making a new port a new movement.
  const portRef = useRef(port);
  useEffect(() => {
    portRef.current = port;
  }, [port]);
  const abandon = useCallback(() => {
    const shown = pending.current;
    pending.current = null;
    if (shown)
      void releaseReview(portRef.current, shown.operation, shown.movement);
  }, []);
  // Another movement's review is not this one's.
  useEffect(() => {
    setState({ kind: "idle" });
    setRejecting(null);
    setShare("");
    setShareError(null);
    return () => {
      asking.current += 1;
      abandon();
    };
  }, [id, abandon]);

  async function ask(
    mode: LedgerLlmReviewMode,
    purpose: Ask,
    extra: { business_pct?: string; reason?: string } = {},
  ) {
    // Asking runs the registered review, a write the page's pause holds.
    if (paused !== null) return;
    const turn = (asking.current += 1);
    const superseded = () => turn !== asking.current;
    // Asking again, with a share or a reason, replaces the review shown:
    // it is cancelled, and the ask waits for that to settle.
    abandon();
    setState({ kind: "asking", ask: purpose });
    const definition =
      mode === "split" ? "ledger.split.review" : "ledger.classify.review";
    const request: LedgerLlmReviewRequest = {
      transaction_id: id,
      mode,
      origin: purpose === "reject" ? "classify_llm_reject" : ORIGINS[mode],
      ...(extra.business_pct ? { business_pct: extra.business_pct } : {}),
      ...(extra.reason ? { reason: extra.reason } : {}),
    };
    let asked: string | null = null;
    try {
      const outcome = await askReview(port, definition, request);
      if (outcome.kind === "review" || outcome.kind === "running")
        asked = outcome.operation_id;
      if (superseded()) {
        if (asked) void releaseReview(port, asked, id);
        return;
      }
      if (outcome.kind === "refused") {
        setState({ kind: "failed", code: outcome.reason ?? "refused" });
        return;
      }
      if (outcome.kind !== "review") {
        // A review still being asked is not one the page can show.
        if (asked) void releaseReview(port, asked, id);
        setState({ kind: "failed", code: "no_review" });
        return;
      }
      const review = await port.review<LedgerLlmSuggestion>(
        outcome.operation_id,
      );
      if (superseded()) {
        void releaseReview(port, outcome.operation_id, id);
        return;
      }
      pending.current = { operation: outcome.operation_id, movement: id };
      // The reason now travels with the review it was asked with.
      setRejecting(null);
      setState({
        kind: "shown",
        shown: {
          definition,
          mode,
          review,
          ...(purpose === "reject" && extra.reason
            ? { rejecting: extra.reason }
            : {}),
        },
      });
    } catch (error) {
      // A review that could not be read is one the page cannot answer.
      if (asked) void releaseReview(port, asked, id);
      if (superseded()) return;
      const failure = ledgerFailure(error);
      setState({ kind: "failed", code: failure.reason ?? failure.code });
    }
  }

  const stageAnswer = (shown: Shown, decision: "apply" | "reject") => {
    const suggestion = shown.review.review.suggestion;
    // The staged answer now holds the review.
    pending.current = null;
    onStage({
      type: "stage_action",
      action: {
        id: `suggestion:${id}`,
        kind: "suggestion",
        transactionId: id,
        operationId: shown.review.operation_id,
        reviewDigest: shown.review.review_digest,
        decision,
        reason: shown.rejecting ?? "",
        ...(decision === "apply"
          ? { writes: suggestionWrites(suggestion) }
          : {}),
      },
    });
    setState({ kind: "idle" });
    setRejecting(null);
    say(
      decision === "apply"
        ? t("desktop.ledger.inspector.model.approval_staged")
        : t("desktop.ledger.inspector.model.rejection_staged"),
    );
  };

  const heading = (
    <h4 className="flex items-center gap-1 text-sm font-medium">
      {t("desktop.ledger.inspector.model.title")}
      <IconButton
        label={t("desktop.ledger.inspector.model.about")}
        size="xs"
        className="size-control-xs"
      >
        <Icon name="info" size="xs" />
      </IconButton>
    </h4>
  );

  if (staged)
    return (
      <div className="ledger-model grid gap-2">
        {heading}
        <Alert icon={<Icon name="agent" />} role="status">
          <span className="grid gap-1">
            {staged.decision === "apply"
              ? t("desktop.ledger.inspector.model.approval_staged")
              : t("desktop.ledger.inspector.model.rejection_staged")}
            <Button
              variant="link"
              size="xs"
              className="w-fit"
              onClick={() => onStage({ type: "drop_action", id: staged.id })}
            >
              {t("desktop.ledger.inspector.drop")}
            </Button>
          </span>
        </Alert>
      </div>
    );

  const askButtons = (
    <div className="flex">
      <WriteHold>
        <Button
          variant="outline"
          size="sm"
          className="rounded-r-none"
          disabled={locked !== null || state.kind === "asking"}
          onClick={() => void ask("classification", "suggest")}
        >
          {state.kind === "asking" ? <Spinner /> : <Icon name="agent" />}
          {t("desktop.ledger.inspector.model.ask")}
        </Button>
      </WriteHold>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="icon-sm"
            className="-ml-px rounded-l-none"
            aria-label={t("desktop.ledger.inspector.model.ask_how")}
            disabled={locked !== null || state.kind === "asking"}
          >
            <Icon name="chevronDown" size="xs" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            disabled={paused !== null}
            onSelect={() => void ask("classification", "suggest")}
          >
            {t("desktop.ledger.inspector.model.mode.classification")}
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={paused !== null}
            onSelect={() => void ask("saturated", "suggest")}
          >
            {t("desktop.ledger.inspector.model.mode.saturated")}
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={paused !== null}
            onSelect={() => void ask("split", "suggest")}
          >
            {t("desktop.ledger.inspector.model.mode.split")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );

  let body = askButtons;
  if (state.kind === "failed") {
    const failure = modelFailureText(t, state.code);
    body = (
      <div className="grid gap-2">
        <Alert
          tone="warning"
          role="alert"
          icon={
            <Icon name={state.code === "subject_busy" ? "pause" : "unplug"} />
          }
          data-code={state.code}
        >
          {failure}
        </Alert>
        {askButtons}
      </div>
    );
  } else if (state.kind === "shown") {
    const { shown } = state;
    const suggestion = shown.review.review.suggestion;
    const writes = suggestionWrites(suggestion);
    const held = needsShare(suggestion);
    body = (
      <div className="ledger-suggestion grid gap-2 rounded-md bg-accent p-2.5">
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <Icon name="agent" size="xs" />
          <span className="font-medium">{suggestion.provenance}</span>
          {suggestion.confidence !== null && (
            <span className="text-muted-foreground tabular-nums">
              {t("desktop.ledger.inspector.model.confidence", {
                value: formatPercent(locale, suggestion.confidence, {
                  unit: "fraction",
                }),
              })}
            </span>
          )}
        </p>
        {shown.rejecting !== undefined && (
          <p className="text-sm font-medium">
            {t("desktop.ledger.inspector.model.rejecting", {
              reason: shown.rejecting,
            })}
          </p>
        )}
        {writes.length > 0 && (
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
            {writes.map((write) => (
              <div key={write.field} className="contents">
                <dt className="text-muted-foreground">
                  {fieldName(t, write.field)}
                </dt>
                <dd>
                  {valueText(t, locale, write.field, write.value)}
                  {write.derived && (
                    <span className="block text-xs text-muted-foreground">
                      {t("desktop.ledger.inspector.model.derived")}
                    </span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        )}
        {suggestion.kind === "split" && (
          <ul className="grid gap-0.5 text-sm">
            {suggestion.children.map((child, at) => (
              <li key={at} className="flex gap-2">
                <span className="min-w-0 flex-1 break-words">
                  {child.description}
                </span>
                <span className="tabular-nums">
                  {valueText(t, locale, "amount", child.amount)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {suggestion.reason && (
          <p className="text-sm text-muted-foreground">{suggestion.reason}</p>
        )}
        {held && shown.rejecting === undefined && (
          <div className="grid gap-1">
            <label htmlFor={fieldId} className="text-sm">
              {t("desktop.ledger.inspector.model.share_needed")}
            </label>
            <div className="flex gap-2">
              <Input
                id={fieldId}
                controlSize="sm"
                inputMode="decimal"
                value={share}
                aria-invalid={shareError ? true : undefined}
                aria-describedby={shareError ? `${fieldId}-error` : undefined}
                onChange={(event) => {
                  setShare(event.target.value);
                  setShareError(null);
                }}
              />
              <WriteHold>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const parsed = parsePercent(share);
                    if (parsed.kind !== "value") {
                      setShareError(
                        parsed.kind === "refused"
                          ? refusalText(t, parsed.refusal)
                          : t("desktop.ledger.inspector.model.share_needed"),
                      );
                      return;
                    }
                    void ask(shown.mode, "share", {
                      business_pct: parsed.value,
                    });
                  }}
                >
                  {t("desktop.ledger.inspector.model.ask_with_share")}
                </Button>
              </WriteHold>
            </div>
            {shareError && (
              <span id={`${fieldId}-error`} className="text-sm">
                {shareError}
              </span>
            )}
          </div>
        )}
        {rejecting !== null ? (
          <div className="grid gap-1">
            <label htmlFor={`${fieldId}-reason`} className="text-sm">
              {t("desktop.ledger.inspector.model.reason")}
            </label>
            <Input
              id={`${fieldId}-reason`}
              controlSize="sm"
              autoFocus
              maxLength={500}
              value={rejecting}
              onChange={(event) => setRejecting(event.target.value)}
            />
            <div className="flex gap-2">
              <WriteHold>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={rejecting.trim() === ""}
                  onClick={() =>
                    void ask(shown.mode, "reject", { reason: rejecting.trim() })
                  }
                >
                  {t("desktop.ledger.inspector.model.continue_reject")}
                </Button>
              </WriteHold>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRejecting(null)}
              >
                {t("desktop.ledger.inspector.cancel")}
              </Button>
            </div>
          </div>
        ) : shown.rejecting !== undefined ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => stageAnswer(shown, "reject")}
            >
              {t("desktop.ledger.inspector.model.stage_rejection")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                abandon();
                setState({ kind: "idle" });
              }}
            >
              {t("desktop.ledger.inspector.cancel")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={locked !== null || held}
              onClick={() => stageAnswer(shown, "apply")}
            >
              <Icon name="tick" />
              {t("desktop.ledger.inspector.model.approve")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={locked !== null}
              onClick={() =>
                // A split's review takes no rejection reason: its
                // rejection is the answer alone.
                shown.mode === "split"
                  ? stageAnswer(shown, "reject")
                  : setRejecting("")
              }
            >
              {t("desktop.ledger.inspector.model.reject")}
            </Button>
          </div>
        )}
      </div>
    );
  } else if (state.kind === "asking")
    body = (
      <p role="status" className="flex items-center gap-2 text-sm">
        <Spinner />
        {t("desktop.ledger.inspector.model.asking")}
      </p>
    );

  return (
    <div className="ledger-model grid gap-2">
      {heading}
      {body}
      {rejectedBefore && (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.inspector.model.rejected_before")}
        </p>
      )}
    </div>
  );
}
