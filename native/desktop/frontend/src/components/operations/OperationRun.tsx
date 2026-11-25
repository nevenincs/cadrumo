import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatTime } from "../../shared/dateFormats";
import { NAVIGATION } from "../../shell/navigation/projection";
import { elementOf } from "../../shell/navigation/register";
import type {
  OperationEffect,
  OperationHistoryRowV1,
  OperationLifecycle,
  OperationTerminalCondition,
} from "../../shell/operationsContract";
import { useStrings } from "../../shell/strings";

type Tone = "neutral" | "success" | "warning" | "danger";

/** SETTLING and UNKNOWN are said as themselves and flagged apart from the
 * runs that finished cleanly: neither is drawn as a success or a failure. */
const LIFECYCLE_TONE: Record<OperationLifecycle, Tone> = {
  created: "neutral",
  queued: "neutral",
  running: "neutral",
  waiting_for_interaction: "neutral",
  waiting_for_external: "neutral",
  cancellation_requested: "warning",
  settling: "warning",
  terminal: "neutral",
};

const EFFECT_TONE: Record<OperationEffect, Tone> = {
  none: "neutral",
  updated: "neutral",
  partial: "warning",
  unknown: "warning",
};

const OUTCOME_TONE: Record<OperationTerminalCondition, Tone> = {
  succeeded: "success",
  refused: "neutral",
  failed: "danger",
  cancelled: "neutral",
  timed_out: "warning",
  interrupted: "warning",
};

/** The page a run's records show on: the register's own label, as a link that
 * opens the page the way any link to it does. A page the window does not draw
 * is named by its label alone, with no way to open it. */
function PageLink({
  page,
  onOpen,
}: {
  page: string;
  onOpen: (destination: string) => void;
}) {
  const t = useStrings();
  const element = elementOf(NAVIGATION, page);
  if (!element) return <code data-operation-page-token={page}>{page}</code>;
  const label = t(element.label);
  if (!element.surfaces.includes("gui"))
    return <span data-operation-page-label={page}>{label}</span>;
  return (
    <Button
      variant="link"
      size="xs"
      data-operation-page={page}
      onClick={() => onOpen(page)}
    >
      {label}
    </Button>
  );
}

/** One run as the journal recorded it. The definition is the untranslated
 * protocol token the product serves, shown as it is. */
export function OperationRun({
  run,
  locale,
  onOpen,
}: {
  run: OperationHistoryRowV1;
  locale: string;
  onOpen: (destination: string) => void;
}) {
  const t = useStrings();
  const { receipt } = run;
  return (
    <li
      data-operation-run={run.operation_id}
      data-lifecycle={run.lifecycle}
      data-effect={run.effect}
      className="flex flex-col gap-1.5 rounded-lg border bg-card p-3 text-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <code
          data-operation-definition=""
          className="font-mono font-medium text-foreground [overflow-wrap:anywhere]"
        >
          {run.definition_id}
        </code>
        <Badge
          variant={LIFECYCLE_TONE[run.lifecycle]}
          data-operation-lifecycle=""
        >
          {t(`desktop.operations.lifecycle.${run.lifecycle}`)}
        </Badge>
        {run.cancellation_requested && (
          <Badge variant="warning" data-operation-cancellation="">
            {t("desktop.operations.cancellation_requested")}
          </Badge>
        )}
        <Badge variant={EFFECT_TONE[run.effect]} data-operation-effect="">
          {t("desktop.operations.field_effect")}:{" "}
          {t(`desktop.operations.effect.${run.effect}`)}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        <code className="font-mono [overflow-wrap:anywhere]">
          {run.operation_id}
        </code>
      </p>
      <p className="flex flex-wrap gap-x-3 text-muted-foreground">
        <span>
          {t("desktop.operations.started", {
            time: formatTime(locale, run.started_at),
          })}
        </span>
        <span>
          {t("desktop.operations.updated", {
            time: formatTime(locale, run.updated_at),
          })}
        </span>
        {run.phase_code !== null && (
          <span data-operation-phase="">
            {t("desktop.operations.phase", { phase: run.phase_code })}
          </span>
        )}
      </p>
      {run.register_page !== null && (
        <p className="flex flex-wrap items-center gap-1 text-muted-foreground">
          {t("desktop.operations.shown_on")}
          <PageLink page={run.register_page} onOpen={onOpen} />
        </p>
      )}
      {receipt !== null && (
        <div
          data-operation-receipt={receipt.condition}
          className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t pt-1.5 text-muted-foreground"
        >
          <Badge variant={OUTCOME_TONE[receipt.condition]}>
            {t("desktop.operations.field_outcome")}:{" "}
            {t(`desktop.operations.outcome.${receipt.condition}`)}
          </Badge>
          <span>
            {t("desktop.operations.settled", {
              time: formatTime(locale, receipt.settled_at),
            })}
          </span>
          <span>
            {receipt.result_stored
              ? t("desktop.operations.result_stored")
              : t("desktop.operations.result_not_stored")}
          </span>
          {receipt.refusal_ref !== null && (
            <span data-operation-refusal="">
              {t("desktop.operations.refusal_ref", {
                ref: receipt.refusal_ref,
              })}
            </span>
          )}
          {receipt.failure_error_code !== null && (
            <span data-operation-error="">
              {t("desktop.operations.error_code", {
                code: receipt.failure_error_code,
              })}
            </span>
          )}
        </div>
      )}
    </li>
  );
}
