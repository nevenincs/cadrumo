import type { ReactNode } from "react";
import { Icon } from "@/components/ui/icon";
import { formatDay } from "../../../shared/dateFormats";
import type { PlanRow } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { Hint, NotApplicable, NotKnown, NothingRecorded } from "./AssetList";
import { ASSET_KEYS } from "./assetsWords";
import { figureText, PLAN_KEYS } from "./planWords";

/** A year drawn on tables carried forward: its own glyph, distinct from every
 * mark, beside the year and beside each figure worked out from them. */
export function Estimated({ year }: { year: number }) {
  const t = useStrings();
  return (
    <Hint words={t(ASSET_KEYS.plan.projected_note, { year })}>
      <Icon name="calendar" size="xs" className="text-muted-foreground" />
    </Hint>
  );
}

/** A figure the backend states, or the mark of why there is none: not known,
 * nothing recorded, or a figure that does not apply. */
export function Figure({
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
export function Interval({
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
      {formatDay(locale, from)}
      <Icon name="arrow" size="xs" className="text-muted-foreground" />
      <span className="sr-only">{t(PLAN_KEYS.until)} </span>
      {formatDay(locale, through)}
    </span>
  );
}
