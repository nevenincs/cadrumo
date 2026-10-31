import { useMemo } from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useTableView } from "@/components/ui/table-view";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings, type Translate } from "../../../shell/strings";
import { dateText, stampText } from "../movements/movementWords";
import { CallLine, Reading } from "../setup/SetupParts";
import type { TimelineChange, TimelineEvent } from "../../../shell/ledgerSetup";
import {
  ASSET_KEYS,
  changeFieldWord,
  refusalText,
  tokenWord,
} from "./assetsWords";
import { NotKnown } from "./AssetList";
import { changeValueText, PLAN_KEYS } from "./planWords";
import { readTimeline, useAssetRead } from "./planRead";

// One element's history: what was appended, in what order, from where. It is
// append-only. Events stay in the order the backend numbered them and cannot
// be sorted; an event is never restyled or rewritten by a later one, and a
// claim that replaces another states the amount it replaced as its before
// value. Before and after values are the backend's, never a difference worked
// out here. Forecasts, findings and reads are not events.

/** One changed field, as the backend stated its before and after. */
function Change({
  locale,
  change,
}: {
  locale: string;
  change: TimelineChange;
}) {
  const t = useStrings();
  const { before, after } = change;
  // The backend's label, else the word of its key, else what the field is.
  const value = (side: "before" | "after") =>
    changeValueText(t, locale, change, side);
  // The word of the fact is the one the backend served the key of.
  const name = changeFieldWord(t, change.field_key);
  // A value that is added or cleared is one sentence of the catalogue's; one
  // that changes reads before, arrow, after.
  if (before === null && after !== null)
    return (
      <li className="flex items-start gap-1">
        <Icon name="plus" size="xs" className="mt-0.5 text-muted-foreground" />
        {t(ASSET_KEYS.timeline.change_added, {
          field: name,
          after: value("after"),
        })}
      </li>
    );
  if (before !== null && after === null)
    return (
      <li className="flex items-start gap-1">
        <Icon name="erase" size="xs" className="mt-0.5 text-muted-foreground" />
        {t(ASSET_KEYS.timeline.change_cleared, {
          field: name,
          before: value("before"),
        })}
      </li>
    );
  return (
    <li className="flex flex-wrap items-center gap-x-1.5">
      <span className="text-muted-foreground">{name}</span>
      <span>{value("before")}</span>
      <Icon name="arrow" size="xs" className="text-muted-foreground" />
      <span className="sr-only">{t(PLAN_KEYS.change_to)}</span>
      <span>{value("after")}</span>
    </li>
  );
}

function Recorded({
  t,
  locale,
  event,
}: {
  t: Translate;
  locale: string;
  event: TimelineEvent;
}) {
  if (event.recorded_at === null)
    return (
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        <Icon name="unknown" size="xs" />
        {t(ASSET_KEYS.timeline.time_not_recorded)}
      </span>
    );
  return (
    <span className="tabular-nums">{stampText(locale, event.recorded_at)}</span>
  );
}

/** What the rest of the profile makes of a dotación: the year and the span it
 * covers, that a later one replaced it, or else whether it still matches the
 * schedule, why not, and what uses it. A dotación that was replaced is
 * never said to match or to differ: only one in effect can. */
function ClaimUse({ event, locale }: { event: TimelineEvent; locale: string }) {
  const t = useStrings();
  const use = event.claim;
  if (use === null) return null;
  return (
    <span className="flex flex-col gap-0.5 text-xs text-muted-foreground">
      {use.tax_year !== null &&
        use.covered_from !== null &&
        use.covered_through !== null && (
          <span className="tabular-nums">
            {t(ASSET_KEYS.timeline.claim_span, {
              year: use.tax_year,
              from: dateText(locale, use.covered_from, true),
              through: dateText(locale, use.covered_through, true),
            })}
          </span>
        )}
      {use.in_effect ? (
        <span className="inline-flex items-center gap-1">
          <Icon
            name={use.matches_current_schedule ? "check" : "alert"}
            size="xs"
            className={
              use.matches_current_schedule ? "text-success" : "text-warning"
            }
          />
          {use.matches_current_schedule
            ? t(ASSET_KEYS.plan.matches)
            : t(ASSET_KEYS.plan.no_match)}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1">
          <Icon name="refused" size="xs" />
          {t(ASSET_KEYS.plan.replaced)}
        </span>
      )}
      {use.in_effect && use.stale_reason !== null && (
        <span>{tokenWord(t, "stale_reason", use.stale_reason)}</span>
      )}
      {use.used_by.length > 0 && (
        <span className="[overflow-wrap:anywhere]">
          {t(
            use.used_by.length === 1
              ? ASSET_KEYS.timeline.used_by_one
              : ASSET_KEYS.timeline.used_by,
            { count: use.used_by.length },
          )}
        </span>
      )}
    </span>
  );
}

function TimelineTable({
  locale,
  events,
}: {
  locale: string;
  events: readonly TimelineEvent[];
}) {
  const t = useStrings();
  const column = ASSET_KEYS.timeline.column;
  // No column has a way to rank its rows: history keeps its sequence.
  const columns = useMemo(
    () =>
      [column.recorded, column.event, column.effect, column.changes].map(
        (key) => ({ id: key, label: t(key), name: t(key) }),
      ),
    [t, column],
  );
  const view = useTableView({
    columns,
    rows: events,
    resizeLabel: (name) => t("desktop.table.resize_column", { column: name }),
  });
  return (
    <div
      role="group"
      tabIndex={0}
      aria-label={t(ASSET_KEYS.detail.timeline)}
      className="ledger-assets-timeline min-h-0 flex-1 overflow-auto"
    >
      <table {...view.tableProps} className="w-full text-sm">
        <caption className="sr-only">{t(ASSET_KEYS.detail.timeline)}</caption>
        <thead className="sticky top-0 z-(--layer-pinned) bg-card">
          <tr className="text-left text-muted-foreground">{view.headers}</tr>
        </thead>
        <tbody>
          {view.rows.map((event) => (
            <tr
              key={event.sequence}
              className={cn(
                "border-t border-border align-top",
                event.claim !== null &&
                  !event.claim.in_effect &&
                  "text-muted-foreground",
              )}
            >
              <td className="px-2 py-1.5">
                <Recorded t={t} locale={locale} event={event} />
              </td>
              <td className="px-2 py-1.5">
                <span className="block">
                  {tokenWord(t, "event_kind", event.event_kind)}
                </span>
                {!event.affects_calculation && (
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <Icon name="info" size="xs" />
                    {t(ASSET_KEYS.timeline.not_in_calculation)}
                  </span>
                )}
                <ClaimUse event={event} locale={locale} />
              </td>
              <td className="px-2 py-1.5 tabular-nums">
                {event.effect_date === null ? (
                  // A described event has no effective date by nature: the
                  // cell stays empty rather than saying it is not known.
                  event.event_kind === "described" ? null : (
                    <NotKnown why={t(ASSET_KEYS.timeline.effect_missing)} />
                  )
                ) : (
                  <span className="whitespace-nowrap">
                    {dateText(locale, event.effect_date, true)}
                  </span>
                )}
              </td>
              <td className="px-2 py-1.5">
                {event.changes.length === 0 ? (
                  <span className="text-muted-foreground">
                    {t(ASSET_KEYS.timeline.no_changes)}
                  </span>
                ) : (
                  <ul className="flex flex-col gap-0.5">
                    {event.changes.map((change) => (
                      <Change
                        key={change.field}
                        locale={locale}
                        change={change}
                      />
                    ))}
                  </ul>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One element's append-only history, read from the ledger. */
export function AssetTimeline({
  port,
  assetId,
  locale,
  reader,
}: {
  port: LedgerPort;
  assetId: string;
  locale: string;
  /** Whose ledger; null while the account withholds it. */
  reader?: string | null;
}) {
  const t = useStrings();
  const { read } = useAssetRead(readTimeline, port, reader, assetId);
  if (read === null) return <Reading label={t(PLAN_KEYS.reading)} />;
  if (read.kind !== "done") return <CallLine call={read} />;
  const { outcome, refusal, events } = read.result;
  if (outcome === "refused" || events === null)
    return (
      <p role="alert" className="p-3 text-sm text-destructive">
        {refusalText(t, refusal)}
      </p>
    );
  if (events.length === 0)
    return (
      <p className="p-3 text-sm text-muted-foreground">
        {t(PLAN_KEYS.timeline_empty)}
      </p>
    );
  return <TimelineTable locale={locale} events={events} />;
}
