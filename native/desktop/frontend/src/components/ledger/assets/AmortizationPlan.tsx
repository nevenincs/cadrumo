import { Fragment, useCallback, useId, useMemo, useState } from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useTableView } from "@/components/ui/table-view";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { dateText } from "../movements/movementWords";
import { CallLine, Reading } from "../setup/SetupParts";
import type { AssetBaja, PlanClaim, PlanRow } from "./assetsContract";
import {
  absentWord,
  ASSET_KEYS,
  findingWord,
  STATE_ICON,
  stateOf,
  stateWord,
} from "./assetsWords";
import {
  DASH,
  figureText,
  isStatedZero,
  methodWord,
  PLAN_KEYS,
  reasonWord,
  stateTone,
} from "./planWords";
import { readPlan, useAssetRead } from "./planRead";

// One element's amortization plan, a row for each tax year it has. The plan
// is current: it answers what the schedule allows now, what is recorded as
// effective, and what is still to amortize, every figure as the backend
// states it. Nothing here adds, subtracts or derives a date; a figure the
// backend does not state is a dash with its reason, never zero.

/** A figure the backend states, or a dash with the reason it does not. */
function Figure({
  locale,
  amount,
  absent,
  said,
}: {
  locale: string;
  amount: PlanRow["planned"];
  /** Why the figure is not stated, shown under the dash. */
  absent?: string | null;
  /** What a screen reader hears for a dash with no reason shown. */
  said?: string;
}) {
  const text = figureText(locale, amount);
  if (text !== null) return <span>{text}</span>;
  return (
    <span className="flex flex-col items-end">
      <span aria-hidden="true">{DASH}</span>
      {absent ? (
        <span className="text-xs text-muted-foreground">{absent}</span>
      ) : (
        said && <span className="sr-only">{said}</span>
      )}
    </span>
  );
}

/** The span a claim covers, from and until the dates the backend states. */
function Interval({
  locale,
  from,
  until,
}: {
  locale: string;
  from: string;
  until: string;
}) {
  const t = useStrings();
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap tabular-nums">
      <span className="sr-only">{t(PLAN_KEYS.from)} </span>
      {dateText(locale, from, true)}
      <Icon name="arrow" size="xs" className="text-muted-foreground" />
      <span className="sr-only">{t(PLAN_KEYS.until)} </span>
      {dateText(locale, until, true)}
    </span>
  );
}

/** Every claim a year holds, the replaced ones with the claim that replaced
 * them. Each distinction is a glyph and a word as well as a tone. */
function Claims({ locale, planned }: { locale: string; planned: PlanRow }) {
  const t = useStrings();
  const column = ASSET_KEYS.plan.column;
  const replacement = (claim: PlanClaim) =>
    claim.superseded_by === null
      ? undefined
      : planned.claims.find((other) => other.claim_id === claim.superseded_by);
  return (
    <div className="flex flex-col gap-2 py-1 ps-6 text-xs">
      <p className="text-muted-foreground">
        <span className="font-medium text-foreground">
          {t(ASSET_KEYS.plan.claims)}
        </span>{" "}
        {t(ASSET_KEYS.plan.edition)} {planned.authority.edition}
      </p>
      {planned.claims.length === 0 ? (
        <p className="text-muted-foreground">{t(PLAN_KEYS.no_claims)}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <caption className="sr-only">{t(ASSET_KEYS.plan.claims)}</caption>
            <thead>
              <tr className="text-left text-muted-foreground">
                {[
                  PLAN_KEYS.from,
                  PLAN_KEYS.until,
                  column.claimed,
                  column.status,
                  column.revision,
                  column.matches,
                  column.replaced_by,
                  column.used_by,
                ].map((key) => (
                  <th
                    key={key}
                    scope="col"
                    className="px-2 py-0.5 font-normal whitespace-nowrap"
                  >
                    {t(key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {planned.claims.map((claim) => {
                const next = replacement(claim);
                const amount = figureText(locale, claim.amount);
                return (
                  <tr
                    key={claim.claim_id}
                    className={cn(
                      "border-t border-border align-top",
                      !claim.effective && "text-muted-foreground",
                    )}
                  >
                    <td className="px-2 py-1 whitespace-nowrap tabular-nums">
                      {dateText(locale, claim.from, true)}
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap tabular-nums">
                      {dateText(locale, claim.until, true)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums">
                      {amount ?? DASH}
                      {isStatedZero(claim.amount) && (
                        <span className="block text-muted-foreground">
                          {t(ASSET_KEYS.plan.recorded_zero)}
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-1">
                      <span className="inline-flex items-center gap-1 whitespace-nowrap">
                        <Icon
                          name={claim.effective ? "check" : "refused"}
                          size="xs"
                          className={
                            claim.effective
                              ? "text-success"
                              : "text-muted-foreground"
                          }
                        />
                        {claim.effective
                          ? t(ASSET_KEYS.plan.in_effect)
                          : t(ASSET_KEYS.plan.replaced)}
                      </span>
                    </td>
                    <td className="px-2 py-1 tabular-nums">
                      {claim.revision_number}
                    </td>
                    <td className="px-2 py-1">
                      <span className="inline-flex items-center gap-1 whitespace-nowrap">
                        <Icon
                          name={
                            claim.matches_current_schedule ? "check" : "alert"
                          }
                          size="xs"
                          className={
                            claim.matches_current_schedule
                              ? "text-success"
                              : "text-warning"
                          }
                        />
                        {claim.matches_current_schedule
                          ? t(ASSET_KEYS.plan.matches)
                          : t(ASSET_KEYS.plan.no_match)}
                      </span>
                    </td>
                    <td className="px-2 py-1">
                      {next ? (
                        <span className="inline-flex flex-wrap items-center gap-x-1">
                          <Icon name="arrow" size="xs" />
                          <Interval
                            locale={locale}
                            from={next.from}
                            until={next.until}
                          />
                          <span className="tabular-nums">
                            {figureText(locale, next.amount) ?? DASH}
                          </span>
                        </span>
                      ) : (
                        <span aria-hidden="true">{DASH}</span>
                      )}
                    </td>
                    <td className="px-2 py-1 [overflow-wrap:anywhere]">
                      {claim.used_by.length === 0 ? (
                        <span aria-hidden="true">{DASH}</span>
                      ) : (
                        claim.used_by.join(", ")
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** What a year's state says beyond its glyph and word: the findings the
 * backend raised, the span still open to claim, and the rates it stands on. */
function Status({ locale, planned }: { locale: string; planned: PlanRow }) {
  const t = useStrings();
  const state = stateOf(planned.state_key);
  const open = state === "missing" || state === "partial";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="inline-flex items-center gap-1 whitespace-nowrap">
        <Icon
          name={STATE_ICON[state]}
          size="xs"
          className={stateTone(planned.state_key)}
        />
        {stateWord(t, planned.state_key)}
      </span>
      {planned.finding_keys.map((key) => (
        <span
          key={key}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground"
        >
          <Icon name="alert" size="xs" className="text-warning" />
          {findingWord(t, key)}
        </span>
      ))}
      {planned.claimable ? (
        <span className="flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground">
          {state === "partial"
            ? t(ASSET_KEYS.plan.gap)
            : t(ASSET_KEYS.plan.claimable)}
          <Interval
            locale={locale}
            from={planned.claimable.from}
            until={planned.claimable.until}
          />
        </span>
      ) : (
        open && (
          <span className="text-xs text-muted-foreground">
            {t(ASSET_KEYS.plan.claimable_none)}
          </span>
        )
      )}
      {planned.authority.projected && (
        <span className="inline-flex items-start gap-1 text-xs text-muted-foreground">
          <Icon name="arrow" size="xs" className="mt-0.5" />
          <span>
            {t(ASSET_KEYS.plan.projected)}. {t(ASSET_KEYS.plan.projected_note)}
          </span>
        </span>
      )}
    </div>
  );
}

function Days({ planned }: { planned: PlanRow }) {
  if (planned.service_days === null)
    return <span aria-hidden="true">{DASH}</span>;
  return planned.calendar_days === null ? (
    <span>{planned.service_days}</span>
  ) : (
    <span>
      {planned.service_days} / {planned.calendar_days}
    </span>
  );
}

function PlanTable({
  locale,
  rows,
  year,
  baja,
}: {
  locale: string;
  rows: readonly PlanRow[];
  year: number | null;
  baja: AssetBaja | null;
}) {
  const t = useStrings();
  const base = useId();
  const [open, setOpen] = useState<ReadonlySet<number>>(new Set());
  const column = ASSET_KEYS.plan.column;
  // No column has a way to rank its rows: a plan keeps its years in order.
  const columns = useMemo(
    () => [
      { id: "year", label: t(column.year), name: t(column.year) },
      { id: "status", label: t(column.status), name: t(column.status) },
      {
        id: "method",
        label: t(ASSET_KEYS.list.column.method),
        name: t(ASSET_KEYS.list.column.method),
      },
      {
        id: "planned",
        label: t(column.planned),
        name: t(column.planned),
        align: "end" as const,
      },
      {
        id: "claimed",
        label: t(column.claimed),
        name: t(column.claimed),
        align: "end" as const,
      },
      {
        id: "pending",
        label: t(PLAN_KEYS.pending),
        name: t(PLAN_KEYS.pending),
        align: "end" as const,
      },
      {
        id: "days",
        label: t(column.days),
        name: t(column.days),
        align: "end" as const,
      },
    ],
    [t, column],
  );
  const view = useTableView({
    columns,
    rows,
    resizeLabel: (name) => t("desktop.table.resize_column", { column: name }),
  });
  const toggle = (at: number) =>
    setOpen((held) => {
      const next = new Set(held);
      if (!next.delete(at)) next.add(at);
      return next;
    });
  // The year the pane stands on is brought into view in a long plan.
  const bring = useCallback((node: HTMLTableRowElement | null) => {
    node?.scrollIntoView?.({ block: "nearest" });
  }, []);
  const span = columns.length;
  return (
    <div
      role="group"
      tabIndex={0}
      aria-label={t(ASSET_KEYS.detail.plan)}
      className="ledger-assets-plan min-h-0 flex-1 overflow-auto"
    >
      <table {...view.tableProps} className="w-full text-sm">
        <caption className="sr-only">{t(ASSET_KEYS.detail.plan)}</caption>
        <thead className="sticky top-0 z-(--layer-pinned) bg-card">
          <tr className="text-left text-muted-foreground">{view.headers}</tr>
        </thead>
        <tbody>
          {view.rows.map((planned, at) => {
            const before = at === 0 ? undefined : view.rows[at - 1];
            const changed =
              before !== undefined &&
              before.election.fingerprint !== planned.election.fingerprint;
            const shown = open.has(planned.tax_year);
            const detail = `${base}-${planned.tax_year}`;
            const election = (
              <>
                {methodWord(t, planned.election.method_key)}
                <span className="block text-xs text-muted-foreground tabular-nums">
                  {t(column.revision)} {planned.election.revision_number}
                </span>
              </>
            );
            return (
              <Fragment key={planned.tax_year}>
                {changed && (
                  <tr className="border-t border-border bg-accent">
                    <td colSpan={span} className="px-2 py-1 text-xs">
                      <span className="inline-flex flex-wrap items-center gap-x-1.5">
                        <Icon name="swap" size="xs" />
                        <span className="font-medium">
                          {t(ASSET_KEYS.plan.election_changed)}
                        </span>
                        {methodWord(t, planned.election.method_key)}
                        <span className="text-muted-foreground tabular-nums">
                          {t(column.revision)}{" "}
                          {planned.election.revision_number}
                        </span>
                      </span>
                    </td>
                  </tr>
                )}
                <tr
                  ref={year === planned.tax_year ? bring : undefined}
                  aria-current={year === planned.tax_year ? "true" : undefined}
                  className={cn(
                    "border-t border-border align-top",
                    year === planned.tax_year && "bg-selected",
                  )}
                >
                  <td className="px-2 py-1.5">
                    <button
                      type="button"
                      aria-expanded={shown}
                      aria-controls={detail}
                      className="inline-flex cursor-pointer items-center gap-1 rounded-xs tabular-nums hover:text-foreground focus-visible:outline-(length:--focus-ring) focus-visible:outline-ring focus-visible:outline-solid"
                      onClick={() => toggle(planned.tax_year)}
                    >
                      <Icon
                        name={shown ? "chevronUp" : "chevronDown"}
                        size="xs"
                      />
                      <span className="sr-only">
                        {t(ASSET_KEYS.plan.claims)}{" "}
                      </span>
                      {planned.tax_year}
                    </button>
                  </td>
                  <td className="px-2 py-1.5">
                    <Status locale={locale} planned={planned} />
                  </td>
                  <td className="px-2 py-1.5">{election}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Figure
                      locale={locale}
                      amount={planned.planned}
                      absent={absentWord(
                        t,
                        planned.planned_absent_key ?? "not_computed",
                      )}
                    />
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Figure
                      locale={locale}
                      amount={planned.claimed}
                      said={stateWord(t, planned.state_key)}
                    />
                    {isStatedZero(planned.claimed) && (
                      <span className="block text-xs text-muted-foreground">
                        {t(ASSET_KEYS.plan.recorded_zero)}
                      </span>
                    )}
                    {stateOf(planned.state_key) === "partial" &&
                      planned.claims
                        .filter((claim) => claim.effective)
                        .map((claim) => (
                          <span
                            key={claim.claim_id}
                            className="block text-xs text-muted-foreground"
                          >
                            <Interval
                              locale={locale}
                              from={claim.from}
                              until={claim.until}
                            />
                          </span>
                        ))}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Figure
                      locale={locale}
                      amount={planned.pending_end}
                      absent={absentWord(t, "not_computed")}
                    />
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Days planned={planned} />
                  </td>
                </tr>
                <tr id={detail} hidden={!shown}>
                  <td colSpan={span} className="px-2 pb-2">
                    {shown && <Claims locale={locale} planned={planned} />}
                  </td>
                </tr>
              </Fragment>
            );
          })}
          {baja && (
            <tr className="border-t border-border bg-accent">
              <td colSpan={span} className="px-2 py-1.5">
                <span className="inline-flex flex-wrap items-center gap-x-1.5">
                  <Icon name="archive" size="xs" />
                  <span className="font-medium">
                    {t(ASSET_KEYS.list.disposed, {
                      date: dateText(locale, baja.date, true),
                    })}
                  </span>
                  {reasonWord(t, baja.reason_key)}
                </span>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

/**
 * One element's plan, read from the ledger. `year` is the year the pane
 * stands on, which the plan scrolls to and marks. `baja` closes the plan
 * where the element left service: no year follows it.
 */
export function AmortizationPlan({
  port,
  assetId,
  locale,
  year = null,
  reader,
  baja = null,
}: {
  port: LedgerPort;
  assetId: string;
  locale: string;
  year?: number | null;
  /** Whose ledger; null while the account withholds it. */
  reader?: string | null;
  baja?: AssetBaja | null;
}) {
  const t = useStrings();
  const { read } = useAssetRead(readPlan, port, reader, assetId);
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
  if (read.result.rows.length === 0)
    return (
      <p className="p-3 text-sm text-muted-foreground">
        {t(PLAN_KEYS.plan_empty)}
      </p>
    );
  return (
    <PlanTable
      locale={locale}
      rows={read.result.rows}
      year={year}
      baja={baja}
    />
  );
}
