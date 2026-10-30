import { useMemo } from "react";
import { Icon } from "@/components/ui/icon";
import { useTableView } from "@/components/ui/table-view";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings, type Translate } from "../../../shell/strings";
import { dateText, stampText } from "../movements/movementWords";
import { CallLine, Reading } from "../setup/SetupParts";
import type { TimelineChange, TimelineEvent } from "./assetsContract";
import { ASSET_KEYS, eventWord, fieldWord, originWord } from "./assetsWords";
import { changeValueText, DASH, PLAN_KEYS } from "./planWords";
import { readTimeline, useAssetRead } from "./planRead";

// One element's history: what was appended, in what order, from where, and
// what it replaced. It is append-only. Events stay in the order the backend
// numbered them and cannot be sorted; an event is never restyled or
// rewritten by a later one, which names what it replaces in a column of its
// own. Before and after values are the backend's, never a difference worked
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
  const { field_key: field, before, after } = change;
  const value = (text: string) => changeValueText(t, locale, field, text);
  return (
    <li className="flex flex-wrap items-center gap-x-1.5">
      <span className="text-muted-foreground">{fieldWord(t, field)}</span>
      {before === null && after !== null && (
        <>
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Icon name="plus" size="xs" />
            {t(ASSET_KEYS.timeline.change_added)}
          </span>
          <span>{value(after)}</span>
        </>
      )}
      {before !== null && after === null && (
        <>
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Icon name="erase" size="xs" />
            {t(ASSET_KEYS.timeline.change_cleared)}
          </span>
          <span>{value(before)}</span>
        </>
      )}
      {before !== null && after !== null && (
        <>
          <span>{value(before)}</span>
          <Icon name="arrow" size="xs" className="text-muted-foreground" />
          <span className="sr-only">{t(PLAN_KEYS.change_to)}</span>
          <span>{value(after)}</span>
        </>
      )}
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
      [
        column.sequence,
        column.recorded,
        column.event,
        column.origin,
        column.effect,
        column.changes,
        column.replaces,
      ].map((key) => ({ id: key, label: t(key), name: t(key) })),
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
              className="border-t border-border align-top"
            >
              <td className="px-2 py-1.5 tabular-nums">{event.sequence}</td>
              <td className="px-2 py-1.5">
                <Recorded t={t} locale={locale} event={event} />
              </td>
              <td className="px-2 py-1.5">
                <span className="block">{eventWord(t, event.type_key)}</span>
                {!event.affects_calculation && (
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <Icon name="info" size="xs" />
                    {t(ASSET_KEYS.timeline.not_in_calculation)}
                  </span>
                )}
              </td>
              <td className="px-2 py-1.5">{originWord(t, event.origin_key)}</td>
              <td className="px-2 py-1.5 tabular-nums">
                {event.effect_date === null ? (
                  <span aria-hidden="true">{DASH}</span>
                ) : (
                  dateText(locale, event.effect_date, true)
                )}
              </td>
              <td className="px-2 py-1.5">
                {event.changes.length === 0 ? (
                  <span aria-hidden="true">{DASH}</span>
                ) : (
                  <ul className="flex flex-col gap-0.5">
                    {event.changes.map((change) => (
                      <Change
                        key={change.field_key}
                        locale={locale}
                        change={change}
                      />
                    ))}
                  </ul>
                )}
              </td>
              <td className="px-2 py-1.5 tabular-nums">
                {event.replaces_sequence === null ? (
                  <span aria-hidden="true">{DASH}</span>
                ) : (
                  event.replaces_sequence
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
  if (read.result.outcome === "refused")
    return (
      <CallLine
        call={{
          kind: "refused",
          reason: read.result.refusal?.code ?? null,
          detail: null,
        }}
      />
    );
  if (read.result.events.length === 0)
    return (
      <p className="p-3 text-sm text-muted-foreground">
        {t(PLAN_KEYS.timeline_empty)}
      </p>
    );
  return <TimelineTable locale={locale} events={read.result.events} />;
}
