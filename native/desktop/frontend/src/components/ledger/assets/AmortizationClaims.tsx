import { useMemo } from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { useTableView } from "@/components/ui/table-view";
import { formatDay } from "../../../shared/dateFormats";
import { facts } from "../../../shell/compose";
import type { PlanClaim, PlanRow } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { Interval } from "./AmortizationFigures";
import { Hint, NotApplicable, NotKnown, Remedy } from "./AssetList";
import { ASSET_KEYS, stateIcon, tokenWord } from "./assetsWords";
import { figureText, isStatedZero, PLAN_KEYS, stateTone } from "./planWords";

/** Every claim a year holds, the replaced ones with the claim that replaced
 * them. Each distinction is a glyph and a word as well as a tone; a claim in
 * effect that no longer matches the figures is marked, and can be corrected. */
export function Claims({
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
export function Status({
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
      : (planned.claimable_refusal_words ?? null);
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
            date: formatDay(locale, first.covered_from),
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
                  from: formatDay(locale, interval.covered_from),
                  until: formatDay(locale, interval.covered_through),
                },
              )}
            </span>
          ))}
          {planned.claimable_intervals.length === 0 &&
            (refusal !== null ? (
              <span className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                {refusal}
                <Remedy
                  words={planned.claimable_refusal_remedy_words}
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

export function Days({
  planned,
  applies,
}: {
  planned: PlanRow;
  applies: boolean;
}) {
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
