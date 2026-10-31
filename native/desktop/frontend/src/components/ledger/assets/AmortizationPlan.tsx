import {
  Fragment,
  useCallback,
  useId,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { useTableView } from "@/components/ui/table-view";
import { facts } from "../../../shell/compose";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings, type Translate } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { dateText, percentText } from "../movements/movementWords";
import { CallLine, Reading } from "../setup/SetupParts";
import type {
  ElectionLimits,
  LegalCitation,
  ListDisposal,
  PlanClaim,
  PlanRow,
} from "../../../shell/ledgerSetup";
import {
  Hint,
  NotApplicable,
  NotKnown,
  NothingRecorded,
  Remedy,
} from "./AssetList";
import {
  ASSET_KEYS,
  bajaText,
  reasonText,
  refusalText,
  fieldWord,
  keyedText,
  stateIcon,
  tokenWord,
} from "./assetsWords";
import {
  recordedMark,
  figureText,
  isStatedZero,
  NO_TABLE_MINIMUM,
  PLAN_KEYS,
  stateTone,
} from "./planWords";
import { readPlan, useAssetRead } from "./planRead";

// One element's amortization plan, a row for each tax year it has. The plan
// is current: it answers what the schedule allows now and what is recorded as
// effective, every figure as the backend states it. Nothing here adds,
// subtracts or derives a date; a figure the backend does not state is a mark
// that says it is not known and why, never zero. The election's method is drawn
// once, on the divider where it starts, and the table scrolls inside its own
// frame with the year pinned, so a narrow panel loses no figure.

/** A year drawn on tables carried forward: its own glyph, distinct from every
 * mark, beside the year and beside each figure worked out from them. */
function Estimated({ year }: { year: number }) {
  const t = useStrings();
  return (
    <Hint words={t(ASSET_KEYS.plan.projected_note, { year })}>
      <Icon name="calendar" size="xs" className="text-muted-foreground" />
    </Hint>
  );
}

/** A figure the backend states, or the mark of why there is none: not known,
 * nothing recorded, or a figure that does not apply. */
function Figure({
  locale,
  amount,
  why,
  absent,
  remedy,
  mark = "not_known",
  estimatedYear,
}: {
  locale: string;
  amount: PlanRow["planned"];
  /** Why the figure is not known, in the mark's tooltip. */
  why?: string;
  /** The reason the backend gives, shown under the mark. */
  absent?: string | null;
  /** The entry to fill in to work the figure out, when that is the remedy. */
  remedy?: ReactNode;
  /** Which state the missing figure is. */
  mark?: "not_known" | "nothing_recorded" | "not_applicable";
  /** The year whose tables are estimated, beside a figure drawn from them. */
  estimatedYear?: number;
}) {
  const text = figureText(locale, amount);
  if (text !== null)
    return (
      <span className="inline-flex items-center justify-end gap-1">
        {estimatedYear !== undefined && <Estimated year={estimatedYear} />}
        <span className="whitespace-nowrap tabular-nums">{text}</span>
      </span>
    );
  const reason = absent ?? why ?? null;
  return (
    <span className="flex flex-col items-end gap-0.5">
      {mark === "nothing_recorded" ? (
        <NothingRecorded why={reason} />
      ) : mark === "not_applicable" ? (
        <NotApplicable why={reason} />
      ) : (
        <NotKnown why={reason ?? ""} />
      )}
      {absent && (
        <span className="w-40 text-end text-xs text-muted-foreground">
          {absent}
        </span>
      )}
      {remedy && <span className="w-40 text-end">{remedy}</span>}
    </span>
  );
}

/** The span a claim covers, from and through the dates the backend states. */
function Interval({
  locale,
  from,
  through,
}: {
  locale: string;
  from: string;
  through: string;
}) {
  const t = useStrings();
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap tabular-nums">
      <span className="sr-only">{t(PLAN_KEYS.from)} </span>
      {dateText(locale, from, true)}
      <Icon name="arrow" size="xs" className="text-muted-foreground" />
      <span className="sr-only">{t(PLAN_KEYS.until)} </span>
      {dateText(locale, through, true)}
    </span>
  );
}

/** Why a year has no planned figure: the typed absence and the reason the
 * backend gives for it where it gives one. */
function absentText(t: Translate, planned: PlanRow): string | null {
  if (planned.absence === null) return null;
  const word = tokenWord(t, "plan_absence", planned.absence);
  const why = reasonText(
    t,
    planned.absence_reason_key,
    planned.absence_reason_facts,
  );
  return facts(t, [word, why]);
}

/** Every claim a year holds, the replaced ones with the claim that replaced
 * them. Each distinction is a glyph and a word as well as a tone; a claim in
 * effect that no longer matches the figures is marked, and can be corrected. */
function Claims({
  locale,
  planned,
  onCorrectClaim,
}: {
  locale: string;
  planned: PlanRow;
  onCorrectClaim?: (claimId: string, year: number) => void;
}) {
  const t = useStrings();
  const column = ASSET_KEYS.plan.column;
  const replacement = (claim: PlanClaim) =>
    claim.superseded_by === null
      ? undefined
      : planned.claims.find((other) => other.claim_id === claim.superseded_by);
  const columns = useMemo(
    () => [
      { id: "period", label: t(column.period), name: t(column.period) },
      {
        id: "claimed",
        label: t(column.claimed),
        name: t(column.claimed),
        align: "end" as const,
      },
      { id: "status", label: t(column.status), name: t(column.status) },
      {
        id: "actions",
        label: t(ASSET_KEYS.action.correct),
        name: t(ASSET_KEYS.action.correct),
        hidden: true,
        resizable: false,
      },
    ],
    [t, column],
  );
  const view = useTableView({
    columns,
    rows: planned.claims,
    resizeLabel: (name) => t("desktop.table.resize_column", { column: name }),
  });
  return (
    <div className="flex flex-col gap-2 py-1 ps-6 text-xs">
      <p className="text-muted-foreground">
        <span className="font-medium text-foreground">
          {t(ASSET_KEYS.plan.claims, { year: planned.tax_year })}
        </span>
        {planned.edition && (
          <>
            {" "}
            {t(ASSET_KEYS.plan.edition, {
              edition: planned.edition.authored_filing_year,
            })}
          </>
        )}
      </p>
      {planned.claims.length === 0 ? (
        <p className="text-muted-foreground">{t(PLAN_KEYS.no_claims)}</p>
      ) : (
        <table {...view.tableProps} className="w-full">
          <caption className="sr-only">
            {t(ASSET_KEYS.plan.claims, { year: planned.tax_year })}
          </caption>
          <thead>
            <tr className="text-left text-muted-foreground">{view.headers}</tr>
          </thead>
          <tbody>
            {view.rows.map((claim) => {
              const next = replacement(claim);
              const stale = claim.effective && !claim.matches_current_schedule;
              return (
                <tr
                  key={claim.claim_id}
                  className={cn(
                    "border-t border-border align-top",
                    !claim.effective && "text-muted-foreground",
                  )}
                >
                  <td className="px-2 py-1">
                    <Interval
                      locale={locale}
                      from={claim.covered_from}
                      through={claim.covered_through}
                    />
                  </td>
                  <td className="px-2 py-1 text-right tabular-nums">
                    <span className="whitespace-nowrap">
                      {figureText(locale, claim.amount)}
                    </span>
                    {isStatedZero(claim.amount) && (
                      <span className="block text-muted-foreground">
                        {t(ASSET_KEYS.plan.recorded_zero)}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1">
                    <span className="inline-flex items-center gap-1 whitespace-nowrap">
                      <Icon
                        name={
                          stale
                            ? "alert"
                            : claim.effective
                              ? "check"
                              : "refused"
                        }
                        size="xs"
                        className={
                          stale
                            ? "text-warning"
                            : claim.effective
                              ? "text-success"
                              : "text-muted-foreground"
                        }
                      />
                      {claim.effective
                        ? t(ASSET_KEYS.plan.in_effect)
                        : t(ASSET_KEYS.plan.replaced)}
                    </span>
                    {stale && (
                      <span className="mt-0.5 flex flex-col gap-0.5">
                        {claim.stale_reason !== null && (
                          <span>
                            {tokenWord(t, "stale_reason", claim.stale_reason)}
                          </span>
                        )}
                        <span className="font-medium">
                          {t(ASSET_KEYS.plan.stale_fix)}
                        </span>
                      </span>
                    )}
                    {next && (
                      <span className="mt-0.5 flex flex-wrap items-center gap-x-1">
                        <span>{t(column.replaced_by)}</span>
                        <Interval
                          locale={locale}
                          from={next.covered_from}
                          through={next.covered_through}
                        />
                        <span className="whitespace-nowrap tabular-nums">
                          {figureText(locale, next.amount)}
                        </span>
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1 text-right">
                    {claim.effective && onCorrectClaim && (
                      <WriteHold>
                        <IconButton
                          label={t(ASSET_KEYS.plan.correct_this)}
                          onClick={() =>
                            onCorrectClaim(claim.claim_id, planned.tax_year)
                          }
                        >
                          <Icon name="edit" />
                        </IconButton>
                      </WriteHold>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** What a year's claim state says beyond its glyph: the glyph carries the
 * state's word in its name and tooltip, and the spans still open to claim are
 * written out beside it. A year not yet due says only from when. */
function Status({
  locale,
  planned,
  onCorrectElement,
}: {
  locale: string;
  planned: PlanRow;
  onCorrectElement?: () => void;
}) {
  const t = useStrings();
  const state = planned.claim_state;
  const open = state === "missing" || state === "partial";
  // The planned figure's own cell already says a reason it shares.
  const refusal =
    planned.claimable_refusal_key !== null &&
    planned.claimable_refusal_key === planned.absence_reason_key
      ? null
      : reasonText(
          t,
          planned.claimable_refusal_key,
          planned.claimable_refusal_facts,
        );
  // A claim in effect that no longer matches the plan is a warning, never a
  // tick, whatever the year's state says.
  const stale = planned.claims.some(
    (claim) => claim.effective && !claim.matches_current_schedule,
  );
  const first = planned.claimable_intervals[0];
  const notYet = state === "not_due" && first !== undefined;
  return (
    <div className="flex min-w-28 flex-col gap-0.5">
      {notYet ? (
        <span className="inline-flex items-start gap-1 text-xs text-muted-foreground">
          <Icon name="clock" size="xs" className="mt-0.5" />
          {t(ASSET_KEYS.plan.from_date, {
            date: dateText(locale, first.covered_from, true),
          })}
        </span>
      ) : (
        <>
          <span>
            <Hint
              words={facts(t, [
                tokenWord(t, "claim_state", state),
                stale ? t(ASSET_KEYS.plan.no_match) : null,
              ])}
            >
              <Icon
                name={stale ? "alert" : stateIcon(state)}
                size="xs"
                className={stale ? "text-warning" : stateTone(state)}
              />
            </Hint>
          </span>
          {planned.claimable_intervals.map((interval) => (
            <span
              key={`${interval.covered_from}/${interval.covered_until}`}
              className="text-xs text-muted-foreground"
            >
              {t(
                state === "partial"
                  ? ASSET_KEYS.plan.gap
                  : ASSET_KEYS.plan.claimable,
                {
                  from: dateText(locale, interval.covered_from, true),
                  until: dateText(locale, interval.covered_through, true),
                },
              )}
            </span>
          ))}
          {planned.claimable_intervals.length === 0 &&
            (refusal !== null ? (
              <span className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                {refusal}
                <Remedy
                  fieldKey={planned.claimable_refusal_remedy_field_key}
                  onCorrect={onCorrectElement}
                />
              </span>
            ) : (
              open &&
              planned.claimable_refusal_key === null && (
                <span className="text-xs text-muted-foreground">
                  {t(ASSET_KEYS.plan.claimable_none)}
                </span>
              )
            ))}
        </>
      )}
    </div>
  );
}

function Days({ planned, applies }: { planned: PlanRow; applies: boolean }) {
  const t = useStrings();
  if (planned.service_days === null)
    return applies ? (
      <NotKnown why={t(ASSET_KEYS.plan.days_missing)} />
    ) : (
      <NotApplicable why={t(ASSET_KEYS.plan.days_missing)} />
    );
  return (
    <span className="whitespace-nowrap tabular-nums">
      {planned.calendar_days === null
        ? planned.service_days
        : `${planned.service_days} / ${planned.calendar_days}`}
    </span>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 [overflow-wrap:anywhere] tabular-nums">
        {children}
      </dd>
    </>
  );
}

/** The provisions behind the limits, behind a disclosure with their count,
 * each as its own text. Where the window can open an address, the text is a
 * link to the official publication. A list the backend could not resolve whole
 * says so, with or without a list to show. */
function Citations({
  citations,
  complete,
  onOpenLink,
}: {
  citations: readonly LegalCitation[];
  complete: boolean;
  onOpenLink?: (url: string) => void;
}) {
  const t = useStrings();
  const list = useId();
  const [open, setOpen] = useState(false);
  const text = ASSET_KEYS.plan.limits;
  const partial = !complete && (
    <p className="ledger-assets-citations-partial flex items-start gap-1 text-xs text-muted-foreground">
      <Icon name="alert" size="xs" className="mt-0.5" />
      <span>{t(text.citations_partial)}</span>
    </p>
  );
  if (citations.length === 0) return partial || null;
  return (
    <div className="ledger-assets-citations flex flex-col gap-1">
      <Button
        variant="ghost"
        size="xs"
        className="-ms-2 w-fit"
        aria-expanded={open}
        aria-controls={list}
        onClick={() => setOpen(!open)}
      >
        <Icon name={open ? "chevronUp" : "chevronDown"} size="xs" />
        {t(text.citations, { count: citations.length })}
      </Button>
      <ul id={list} hidden={!open} className="flex flex-col gap-0.5 ps-4">
        {citations.map((citation) => (
          <li
            key={`${citation.text}\u0000${citation.permalink}`}
            className="[overflow-wrap:anywhere]"
          >
            {onOpenLink ? (
              <Button
                variant="link"
                size="xs"
                className="h-auto min-w-0 p-0 text-start whitespace-normal text-primary"
                // The window never leaves the app: the address opens in the browser.
                onClick={() => onOpenLink(citation.permalink)}
              >
                {citation.text}
                <Icon name="external" size="xs" />
              </Button>
            ) : (
              citation.text
            )}
          </li>
        ))}
      </ul>
      {partial}
    </div>
  );
}

/** What the registry allows the element's election: a table method's class
 * and corridor, or the limit it has instead and why. Each figure is the
 * backend's; a limit it does not state is not drawn. */
function Limits({
  locale,
  limits,
  onOpenLink,
}: {
  locale: string;
  limits: ElectionLimits;
  onOpenLink?: (url: string) => void;
}) {
  const t = useStrings();
  const text = ASSET_KEYS.plan.limits;
  const why = reasonText(
    t,
    limits.unavailable_reason_key,
    limits.unavailable_reason_facts,
  );
  return (
    <section
      aria-label={t(text.title)}
      className="ledger-assets-limits flex flex-col gap-1 border-b px-3 py-2 text-sm"
    >
      <h4 className="font-medium">{t(text.title)}</h4>
      {limits.not_table_bound !== null && (
        <p className="text-muted-foreground">
          {facts(t, [
            tokenWord(t, "not_table_bound", limits.not_table_bound),
            why,
          ])}
        </p>
      )}
      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-0.5">
        {limits.class_label !== null && (
          <Fact label={fieldWord(t, "amortization.authority_class_key")}>
            {limits.class_label}
          </Fact>
        )}
        {limits.maximum_coefficient !== null && (
          <Fact label={t(text.maximum_coefficient)}>
            {percentText(locale, limits.maximum_coefficient.decimal)}
          </Fact>
        )}
        {limits.minimum_coefficient !== null && (
          <Fact label={t(text.minimum_coefficient)}>
            {percentText(locale, limits.minimum_coefficient.decimal)}
          </Fact>
        )}
        {limits.maximum_period_years !== null && (
          <Fact label={t(text.maximum_period)}>
            {t(text.period_years, {
              years: limits.maximum_period_years.decimal,
            })}
          </Fact>
        )}
        {limits.maximum_period_last_day !== null && (
          <Fact label={t(text.ends_on)}>
            {dateText(locale, limits.maximum_period_last_day, true)}
          </Fact>
        )}
      </dl>
      <Citations
        citations={limits.legal_citations}
        complete={limits.legal_citations_complete}
        onOpenLink={onOpenLink}
      />
    </section>
  );
}

function PlanTable({
  locale,
  rows,
  year,
  onCorrectClaim,
  onCorrectElement,
}: {
  locale: string;
  rows: readonly PlanRow[];
  year: number | null;
  onCorrectClaim?: (claimId: string, year: number) => void;
  onCorrectElement?: () => void;
}) {
  const t = useStrings();
  const base = useId();
  const [open, setOpen] = useState<ReadonlySet<number>>(new Set());
  const column = ASSET_KEYS.plan.column;
  // No column has a way to rank its rows: a plan keeps its years in order.
  // The method is not a column: it is said once where it starts.
  const columns = useMemo(
    () => [
      { id: "year", label: t(column.year), name: t(column.year) },
      { id: "status", label: t(column.status), name: t(column.status) },
      {
        id: "rate",
        label: t(column.rate),
        name: t(column.rate),
        align: "end" as const,
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
        id: "minimum",
        // The figure runs from entry to the year's end, so the heading says it
        // is accumulated and explains what it is for.
        label: (
          <span className="inline-flex items-center gap-1">
            {t(column.minimum)}
            <Hint words={t(column.minimum_note)}>
              <Icon name="info" size="xs" className="text-muted-foreground" />
            </Hint>
          </span>
        ),
        name: t(column.minimum),
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
      className="ledger-assets-plan scroll-cue-x @container min-h-0 flex-1 overflow-auto"
    >
      <table
        {...view.tableProps}
        className="w-full text-sm [&_thead_th:first-child]:sticky [&_thead_th:first-child]:start-0 [&_thead_th:first-child]:z-(--layer-pinned) [&_thead_th:first-child]:bg-card"
      >
        <caption className="sr-only">{t(ASSET_KEYS.detail.plan)}</caption>
        <thead className="sticky top-0 z-(--layer-pinned) bg-card">
          <tr className="text-left text-muted-foreground">{view.headers}</tr>
        </thead>
        <tbody>
          {view.rows.map((planned, at) => {
            const before = at === 0 ? undefined : view.rows[at - 1];
            const changed =
              before !== undefined && before.method !== planned.method;
            const shown = open.has(planned.tax_year);
            const detail = `${base}-${planned.tax_year}`;
            const current = year === planned.tax_year;
            const kept = planned.claims.some((claim) => claim.effective);
            const estimated = planned.edition?.projected === true;
            const applies = planned.applies;
            return (
              <Fragment key={planned.tax_year}>
                {(before === undefined || changed) && (
                  <tr className="border-t border-border bg-accent">
                    <td colSpan={span} className="px-2 py-1 text-xs">
                      <span className="sticky start-2 inline-flex flex-wrap items-center gap-x-1.5">
                        {changed && (
                          <>
                            <Icon name="swap" size="xs" />
                            <span className="font-medium">
                              {t(ASSET_KEYS.plan.election_changed)}
                            </span>
                          </>
                        )}
                        <span className={changed ? undefined : "font-medium"}>
                          {tokenWord(t, "method", planned.method)}
                        </span>
                      </span>
                    </td>
                  </tr>
                )}
                <tr
                  ref={current ? bring : undefined}
                  aria-current={current ? "true" : undefined}
                  className={cn(
                    "border-t border-border align-top",
                    current && "bg-selected",
                  )}
                >
                  <td
                    className={cn(
                      "sticky start-0 px-2 py-1.5",
                      current ? "bg-selected" : "bg-card",
                    )}
                  >
                    <span className="inline-flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="xs"
                        className="-mx-1 gap-1 text-foreground tabular-nums"
                        aria-expanded={shown}
                        aria-controls={detail}
                        onClick={() => toggle(planned.tax_year)}
                      >
                        <Icon
                          name={shown ? "chevronUp" : "chevronDown"}
                          size="xs"
                        />
                        <span className="sr-only">
                          {t(ASSET_KEYS.plan.claims, {
                            year: planned.tax_year,
                          })}{" "}
                        </span>
                        {planned.tax_year}
                      </Button>
                      {estimated && <Estimated year={planned.tax_year} />}
                    </span>
                  </td>
                  <td className="px-2 py-1.5">
                    <Status
                      locale={locale}
                      planned={planned}
                      onCorrectElement={onCorrectElement}
                    />
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {planned.coefficient === null ? (
                      applies ? (
                        <NotKnown why={t(ASSET_KEYS.plan.rate_missing)} />
                      ) : (
                        <NotApplicable why={t(ASSET_KEYS.plan.rate_missing)} />
                      )
                    ) : (
                      <span className="inline-flex items-center gap-1">
                        {estimated && <Estimated year={planned.tax_year} />}
                        <span className="whitespace-nowrap">
                          {percentText(locale, planned.coefficient.decimal)}
                        </span>
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Figure
                      locale={locale}
                      amount={planned.planned}
                      why={t(ASSET_KEYS.plan.planned_missing)}
                      absent={absentText(t, planned)}
                      remedy={
                        <Remedy
                          fieldKey={planned.absence_remedy_field_key}
                          onCorrect={onCorrectElement}
                        />
                      }
                      mark={applies ? "not_known" : "not_applicable"}
                      estimatedYear={estimated ? planned.tax_year : undefined}
                    />
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {/* No claim in effect is no figure to draw: it is a year with
                        nothing recorded, or one where nothing applies. A year
                        with a span still open is one with nothing recorded,
                        whatever its absence is. */}
                    <Figure
                      locale={locale}
                      amount={kept ? planned.claimed : null}
                      mark={recordedMark(planned)}
                    />
                    {kept && isStatedZero(planned.claimed) && (
                      <span className="block text-xs text-muted-foreground">
                        {t(ASSET_KEYS.plan.recorded_zero)}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Figure
                      locale={locale}
                      amount={planned.minimum_through}
                      why={
                        reasonText(t, planned.minimum_reason_key) ??
                        t(ASSET_KEYS.plan.minimum_missing)
                      }
                      mark={
                        planned.minimum_reason_key === NO_TABLE_MINIMUM
                          ? "not_applicable"
                          : "not_known"
                      }
                      estimatedYear={estimated ? planned.tax_year : undefined}
                    />
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Days planned={planned} applies={applies} />
                  </td>
                </tr>
                <tr id={detail} hidden={!shown}>
                  <td colSpan={span} className="p-0 pb-2">
                    {/* The claims keep the width of the frame, so they stay in
                        view while the figures beside them scroll. */}
                    {shown && (
                      <div className="sticky start-0 w-[100cqw] px-2">
                        <Claims
                          locale={locale}
                          planned={planned}
                          onCorrectClaim={onCorrectClaim}
                        />
                      </div>
                    )}
                  </td>
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * One element's plan, read from the ledger, with the limits the registry puts
 * on its election above it. `year` is the year the pane stands on, which the
 * plan scrolls to and marks. The element's history is read beside it, only to
 * mark a claim in effect that no longer matches the figures.
 */
export function AmortizationPlan({
  port,
  assetId,
  locale,
  year = null,
  reader,
  onOpenLink,
  onCorrectClaim,
  onCorrectElement,
  disposal = null,
}: {
  port: LedgerPort;
  assetId: string;
  locale: string;
  /** The baja the element's current revision records, said above the plan. */
  disposal?: ListDisposal | null;
  year?: number | null;
  /** Whose ledger; null while the account withholds it. */
  reader?: string | null;
  /** Opens an official address in the system browser. */
  onOpenLink?: (url: string) => void;
  /** Asks to correct one claim of a year; offered on each claim in effect. */
  onCorrectClaim?: (claimId: string, year: number) => void;
  /** Opens the form that corrects the element, where a figure says which
   * entry to fill in. */
  onCorrectElement?: () => void;
}) {
  const t = useStrings();
  const { read } = useAssetRead(readPlan, port, reader, assetId);
  if (read === null) return <Reading label={t(PLAN_KEYS.reading)} />;
  if (read.kind !== "done") return <CallLine call={read} />;
  const { outcome, refusal, rows, limits, advisories } = read.result;
  if (outcome === "refused" || rows === null)
    return (
      <div className="p-3">
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-assets-plan-refused"
        >
          {refusalText(t, refusal)}
        </Alert>
      </div>
    );
  if (rows.length === 0)
    return (
      <p className="p-3 text-sm text-muted-foreground">
        {t(PLAN_KEYS.plan_empty)}
      </p>
    );
  const estimated = rows.some((row) => row.edition?.projected);
  return (
    <>
      {(advisories.length > 0 || estimated) && (
        <div className="flex flex-col gap-2 border-b p-3">
          {advisories.map((advisory) => (
            <Alert
              key={advisory.kind}
              icon={<Icon name="info" />}
              className="ledger-assets-advisory"
            >
              {keyedText(
                t,
                advisory.label_key,
                tokenWord(t, "plan_advisory", advisory.kind),
              )}
            </Alert>
          ))}
          {estimated && (
            <Alert
              icon={<Icon name="calendar" />}
              className="ledger-assets-estimated"
            >
              {t(ASSET_KEYS.plan.projected_summary)}
            </Alert>
          )}
        </div>
      )}
      {limits && (
        <Limits locale={locale} limits={limits} onOpenLink={onOpenLink} />
      )}
      {disposal !== null && (
        <p className="ledger-assets-baja flex items-center gap-1.5 border-b px-3 py-2 text-sm">
          <Icon name="archive" size="xs" className="shrink-0" />
          {bajaText(t, locale, disposal)}
        </p>
      )}
      <PlanTable
        locale={locale}
        rows={rows}
        year={year}
        onCorrectClaim={onCorrectClaim}
        onCorrectElement={onCorrectElement}
      />
    </>
  );
}
