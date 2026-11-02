import { Fragment, useCallback, useId, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useTableView } from "@/components/ui/table-view";
import { formatPercent } from "../../../shared/numbers";
import type { PlanRow } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { Claims, Status, Days } from "./AmortizationClaims";
import { Estimated, Figure } from "./AmortizationFigures";
import { Hint, NotApplicable, NotKnown, Remedy } from "./AssetList";
import { ASSET_KEYS, reasonText, tokenWord } from "./assetsWords";
import {
  absentText,
  recordedMark,
  isStatedZero,
  NO_TABLE_MINIMUM,
} from "./planWords";

export function AmortizationTable({
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
                          {formatPercent(locale, planned.coefficient.decimal, {
                            unit: "fraction",
                          })}
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
