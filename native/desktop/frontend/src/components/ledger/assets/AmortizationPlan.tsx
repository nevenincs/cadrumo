import {
  Fragment,
  useCallback,
  useId,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useTableView } from "@/components/ui/table-view";
import { facts } from "../../../shell/compose";
import type { LedgerPort } from "../../../shell/ledger";
import { useStrings, type Translate } from "../../../shell/strings";
import { dateText, percentText } from "../movements/movementWords";
import { CallLine, Reading } from "../setup/SetupParts";
import type {
  ElectionLimits,
  LegalCitation,
  PlanClaim,
  PlanRow,
} from "../../../shell/ledgerSetup";
import {
  ASSET_KEYS,
  reasonText,
  refusalText,
  fieldWord,
  keyedText,
  stateIcon,
  tokenWord,
} from "./assetsWords";
import {
  DASH,
  figureText,
  isStatedZero,
  PLAN_KEYS,
  stateTone,
} from "./planWords";
import { readPlan, useAssetRead } from "./planRead";

// One element's amortization plan, a row for each tax year it has. The plan
// is current: it answers what the schedule allows now and what is recorded as
// effective, every figure as the backend states it. Nothing here adds,
// subtracts or derives a date; a figure the backend does not state is a dash
// with its reason, never zero.

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

/** Why a year has no planned figure: the typed absence, and the reason the
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
        <div className="overflow-x-auto">
          <table className="w-full">
            <caption className="sr-only">
              {t(ASSET_KEYS.plan.claims, { year: planned.tax_year })}
            </caption>
            <thead>
              <tr className="text-left text-muted-foreground">
                {[
                  PLAN_KEYS.from,
                  PLAN_KEYS.until,
                  column.claimed,
                  column.status,
                  column.replaced_by,
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
                return (
                  <tr
                    key={claim.claim_id}
                    className={cn(
                      "border-t border-border align-top",
                      !claim.effective && "text-muted-foreground",
                    )}
                  >
                    <td className="px-2 py-1 whitespace-nowrap tabular-nums">
                      {dateText(locale, claim.covered_from, true)}
                    </td>
                    <td className="px-2 py-1 whitespace-nowrap tabular-nums">
                      {dateText(locale, claim.covered_until, true)}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums">
                      {figureText(locale, claim.amount)}
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
                    <td className="px-2 py-1">
                      {next ? (
                        <span className="inline-flex flex-wrap items-center gap-x-1">
                          <Icon name="arrow" size="xs" />
                          <Interval
                            locale={locale}
                            from={next.covered_from}
                            until={next.covered_until}
                          />
                          <span className="tabular-nums">
                            {figureText(locale, next.amount)}
                          </span>
                        </span>
                      ) : (
                        <span aria-hidden="true">{DASH}</span>
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

/** What a year's claim state says beyond its glyph and word: the spans still
 * open to claim and the rates it stands on. */
function Status({ locale, planned }: { locale: string; planned: PlanRow }) {
  const t = useStrings();
  const state = planned.claim_state;
  const open = state === "missing" || state === "partial";
  const refusal = reasonText(t, planned.claimable_refusal_key);
  return (
    <div className="flex flex-col gap-0.5">
      <span className="inline-flex items-center gap-1 whitespace-nowrap">
        <Icon name={stateIcon(state)} size="xs" className={stateTone(state)} />
        {tokenWord(t, "claim_state", state)}
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
              until: dateText(locale, interval.covered_until, true),
            },
          )}
        </span>
      ))}
      {planned.claimable_intervals.length === 0 &&
        (refusal !== null ? (
          <span className="text-xs text-muted-foreground">{refusal}</span>
        ) : (
          open && (
            <span className="text-xs text-muted-foreground">
              {t(ASSET_KEYS.plan.claimable_none)}
            </span>
          )
        ))}
      {planned.edition?.projected && (
        <span className="inline-flex items-start gap-1 text-xs text-muted-foreground">
          <Icon name="arrow" size="xs" className="mt-0.5" />
          <span>
            {t(ASSET_KEYS.plan.projected)}.{" "}
            {t(ASSET_KEYS.plan.projected_note, { year: planned.tax_year })}
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
 * says so. */
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
      <details>
        <summary className="cursor-pointer text-muted-foreground">
          {t(text.citations, { count: citations.length })}
        </summary>
        <ul className="mt-1 flex flex-col gap-0.5 ps-4">
          {citations.map((citation) => (
            <li key={citation.permalink} className="[overflow-wrap:anywhere]">
              {onOpenLink ? (
                <a
                  href={citation.permalink}
                  title={citation.permalink}
                  className="text-primary underline underline-offset-2 hover:text-primary/80"
                  // The window never leaves the app: the address opens in the browser.
                  onClick={(event) => {
                    event.preventDefault();
                    onOpenLink(citation.permalink);
                  }}
                  onAuxClick={(event) => event.preventDefault()}
                >
                  {citation.text}
                </a>
              ) : (
                citation.text
              )}
            </li>
          ))}
        </ul>
      </details>
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
  const why = reasonText(t, limits.unavailable_reason_key);
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
        {limits.maximum_period_ends_on !== null && (
          <Fact label={t(text.ends_on)}>
            {dateText(locale, limits.maximum_period_ends_on, true)}
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
}: {
  locale: string;
  rows: readonly PlanRow[];
  year: number | null;
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
        label: t(column.minimum),
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
              before !== undefined && before.method !== planned.method;
            const shown = open.has(planned.tax_year);
            const detail = `${base}-${planned.tax_year}`;
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
                        {tokenWord(t, "method", planned.method)}
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
                        {t(ASSET_KEYS.plan.claims, {
                          year: planned.tax_year,
                        })}{" "}
                      </span>
                      {planned.tax_year}
                    </button>
                  </td>
                  <td className="px-2 py-1.5">
                    <Status locale={locale} planned={planned} />
                  </td>
                  <td className="px-2 py-1.5">
                    {tokenWord(t, "method", planned.method)}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {planned.coefficient === null ? (
                      <span aria-hidden="true">{DASH}</span>
                    ) : (
                      percentText(locale, planned.coefficient.decimal)
                    )}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Figure
                      locale={locale}
                      amount={planned.planned}
                      absent={absentText(t, planned)}
                    />
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {/* No claim in effect is no figure to draw: the state says why. */}
                    <Figure
                      locale={locale}
                      amount={
                        planned.claims.some((claim) => claim.effective)
                          ? planned.claimed
                          : null
                      }
                      said={tokenWord(t, "claim_state", planned.claim_state)}
                    />
                    {planned.claims.some((claim) => claim.effective) &&
                      isStatedZero(planned.claimed) && (
                        <span className="block text-xs text-muted-foreground">
                          {t(ASSET_KEYS.plan.recorded_zero)}
                        </span>
                      )}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <Figure
                      locale={locale}
                      amount={planned.minimum_through}
                      absent={
                        planned.minimum_complete
                          ? null
                          : t(ASSET_KEYS.plan.minimum_incomplete)
                      }
                    />
                    {!planned.minimum_complete &&
                      planned.minimum_through !== null && (
                        <span className="block text-xs text-muted-foreground">
                          {t(ASSET_KEYS.plan.minimum_incomplete)}
                        </span>
                      )}
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
        </tbody>
      </table>
    </div>
  );
}

/**
 * One element's plan, read from the ledger, with the limits the registry puts
 * on its election above it. `year` is the year the pane stands on, which the
 * plan scrolls to and marks.
 */
export function AmortizationPlan({
  port,
  assetId,
  locale,
  year = null,
  reader,
  onOpenLink,
}: {
  port: LedgerPort;
  assetId: string;
  locale: string;
  year?: number | null;
  /** Whose ledger; null while the account withholds it. */
  reader?: string | null;
  /** Opens an official address in the system browser. */
  onOpenLink?: (url: string) => void;
}) {
  const t = useStrings();
  const { read } = useAssetRead(readPlan, port, reader, assetId);
  if (read === null) return <Reading label={t(PLAN_KEYS.reading)} />;
  if (read.kind !== "done") return <CallLine call={read} />;
  const { outcome, refusal, rows, limits, advisories } = read.result;
  if (outcome === "refused" || rows === null)
    return (
      <p role="alert" className="p-3 text-sm text-destructive">
        {refusalText(t, refusal)}
      </p>
    );
  if (rows.length === 0)
    return (
      <p className="p-3 text-sm text-muted-foreground">
        {t(PLAN_KEYS.plan_empty)}
      </p>
    );
  return (
    <>
      {advisories.map((advisory) => (
        <p
          key={advisory.kind}
          className="ledger-assets-advisory flex items-start gap-1 border-b px-3 py-2 text-sm text-muted-foreground"
        >
          <Icon name="info" size="xs" className="mt-0.5" />
          <span>
            {keyedText(
              t,
              advisory.label_key,
              tokenWord(t, "plan_advisory", advisory.kind),
            )}
          </span>
        </p>
      ))}
      {limits && (
        <Limits locale={locale} limits={limits} onOpenLink={onOpenLink} />
      )}
      <PlanTable locale={locale} rows={rows} year={year} />
    </>
  );
}
