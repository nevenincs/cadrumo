import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type {
  LedgerHistoryTypedResult,
  LedgerRow,
  LedgerTrackResult,
} from "../../../shell/ledger";
import type { StagedRowChanges } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { fieldName } from "../editing/editingWords";
import {
  amountText,
  classificationLabel,
  lifecycleLabel,
  stampText,
} from "../movements/movementWords";
import {
  declarationName,
  eventName,
  revisionStateLabel,
  seals,
} from "./inspectorWords";
import type { InspectorRead } from "./useInspectorReads";

/**
 * The inspector's History section: what is not saved yet, the movement's
 * recorded events with their reasons, the parts of its split, and the
 * declarations that used it. A filed declaration is not the AEAT's
 * confirmation: only its receipt is.
 */
export function HistorySection({
  row,
  changes,
  history,
  track,
  rows,
  locale,
  onShow,
}: {
  row: LedgerRow;
  changes: StagedRowChanges | undefined;
  history: InspectorRead<LedgerHistoryTypedResult> | null;
  track: InspectorRead<LedgerTrackResult> | null;
  /** The window's movements, by id, for the split's other parts. */
  rows: ReadonlyMap<string, LedgerRow>;
  locale: string;
  /** Shows another movement in the inspector. */
  onShow: (id: string) => void;
}) {
  const t = useStrings();
  const id = row.transaction.transaction_id;
  const pending = Object.keys(changes ?? {}) as (keyof StagedRowChanges)[];
  const read = history?.kind === "ready" ? history.result : null;
  const lineage = new Set(
    (track?.kind === "ready" ? track.result.tracking.edit_lineage : []).map(
      (entry) => entry.previous_transaction_id,
    ),
  );
  const relatives = (read?.object_ids ?? []).filter(
    (other) => other !== id && !lineage.has(other) && rows.has(other),
  );
  const parent = relatives.find(
    (other) => rows.get(other)!.transaction.lifecycle_state === "SPLIT",
  );
  const uses =
    track?.kind === "ready" ? track.result.participated_in : undefined;

  return (
    <div className="grid gap-3">
      <ul className="ledger-history grid gap-2">
        {pending.length > 0 && (
          <li className="grid border-l-2 border-dashed border-foreground pl-2 text-sm">
            <span className="font-medium">
              {t("desktop.ledger.inspector.history.unsaved", {
                fields: pending.map((field) => fieldName(t, field)).join(", "),
              })}
            </span>
          </li>
        )}
        {history === null || history.kind === "reading" ? (
          <li className="text-sm text-muted-foreground">
            <span role="status">{t("desktop.ledger.loading")}</span>
          </li>
        ) : history.kind === "failed" ? (
          <li className="text-sm">
            <span role="alert">{t("desktop.ledger.inspector.unread")}</span>
          </li>
        ) : (
          [...history.result.events].reverse().map((event) => {
            const reason =
              event.details.reason ?? event.details.operator_reason;
            const detail = [
              event.details.classification &&
                classificationLabel(t, event.details.classification),
              event.details.lifecycle_state &&
                lifecycleLabel(t, event.details.lifecycle_state),
              event.details.child_count &&
                t("desktop.ledger.inspector.history.parts", {
                  count: event.details.child_count,
                }),
            ].filter(Boolean);
            return (
              <li
                key={event.event_id}
                className="grid border-l-2 border-border pl-2 text-sm"
              >
                <span>
                  {eventName(t, event.event_type)}
                  {detail.length > 0 && ` · ${detail.join(" · ")}`}
                </span>
                {reason && (
                  <span className="text-muted-foreground">“{reason}”</span>
                )}
                {event.model_reason_withheld && !reason && (
                  <span className="text-xs text-muted-foreground">
                    {t("desktop.ledger.inspector.history.reason_withheld")}
                  </span>
                )}
                <span className="text-xs text-muted-foreground">
                  {event.actor} · {stampText(locale, event.occurred_at)}
                </span>
              </li>
            );
          })
        )}
      </ul>

      {relatives.length > 0 && (
        <div className="grid gap-1">
          <h4 className="text-sm font-medium">
            {row.transaction.lifecycle_state === "SPLIT"
              ? t("desktop.ledger.inspector.history.split_parts")
              : t("desktop.ledger.inspector.history.split_siblings")}
          </h4>
          <ul className="grid gap-1">
            {[
              ...(parent ? [parent] : []),
              ...relatives.filter((other) => other !== parent),
            ].map((other) => {
              const found = rows.get(other)!.transaction;
              return (
                <li key={other} className="flex items-center gap-2 text-sm">
                  <span className="min-w-0 flex-1 break-words">
                    {found.description}
                  </span>
                  <span className="tabular-nums">
                    {amountText(locale, found.amount)}
                  </span>
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => onShow(other)}
                  >
                    {t("desktop.ledger.inspector.show")}
                  </Button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="ledger-used-in grid gap-1">
        <h4 className="text-sm font-medium">
          {t("desktop.ledger.inspector.used.title")}
        </h4>
        {uses === undefined ? (
          <p className="text-sm text-muted-foreground">
            {track?.kind === "failed"
              ? t("desktop.ledger.inspector.unread")
              : t("desktop.ledger.loading")}
          </p>
        ) : uses === null ? (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.inspector.used.not_built")}
          </p>
        ) : uses.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.inspector.used.none")}
          </p>
        ) : (
          <ul className="grid gap-1.5">
            {uses.map((use) => (
              <li
                key={use.calculation_revision_id}
                className="flex items-start gap-2 text-sm"
              >
                <Icon
                  name={seals(use) ? "lock" : "page"}
                  size="xs"
                  className="mt-0.5"
                />
                <span className="min-w-0 flex-1 font-medium">
                  {declarationName(
                    t,
                    use.modelo,
                    use.period.filing_year,
                    use.period.code,
                  )}
                </span>
                <Badge variant={seals(use) ? "inverse" : "neutral"}>
                  {revisionStateLabel(t, use)}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
