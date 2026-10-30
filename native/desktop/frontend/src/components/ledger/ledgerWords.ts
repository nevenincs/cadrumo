// Words and names the Ledger page's components share: its sections, and how
// a period is written in the chrome.

import type { IconName } from "@/components/ui/icon";
import { facts } from "@/shell/compose";
import type { LedgerSection } from "../../shell/layout";
import {
  periodGranularity,
  type LedgerPeriod,
} from "../../shell/ledgerGrammar";
import type { Translate } from "../../shell/strings";

/** The sections shown as tabs, and those under the setup menu. */
export const TAB_SECTIONS = [
  "movements",
  "invoices",
  "documents",
  "assets",
] as const satisfies readonly LedgerSection[];
export const SETUP_SECTIONS = [
  "rules",
  "registers",
  "health",
] as const satisfies readonly LedgerSection[];

export const SECTION_ICONS: Record<LedgerSection, IconName> = {
  movements: "ledger",
  invoices: "page",
  documents: "fileArchive",
  assets: "archive",
  rules: "filter",
  registers: "office",
  health: "shield",
};

/** The element id of a section's tab, beside the region it controls. */
export const sectionTabId = (panel: string, section: LedgerSection) =>
  `${panel}-tab-${section}`;

export const sectionName = (t: Translate, section: LedgerSection) =>
  t(`desktop.ledger.section.${section}`);

const months = new Map<string, string[]>();
/** The twelve months' short names in `locale`, January first. */
export function monthNames(locale: string): string[] {
  const held = months.get(locale);
  if (held) return held;
  const format = new Intl.DateTimeFormat(locale, { month: "short" });
  const names = Array.from({ length: 12 }, (_, month) =>
    format.format(new Date(2000, month, 1)),
  );
  months.set(locale, names);
  return names;
}

/** A period as the chrome writes it: `2026`, `2026 · 3T` or `2026 · Oct`.
 * Quarter codes are the tax period's own tokens and are never translated. */
export function periodText(
  t: Translate,
  locale: string,
  period: LedgerPeriod | null,
  mode: "period" | "year" = "period",
): string {
  if (period === null) return t("desktop.ledger.period.all");
  if (mode === "year") return String(period.year);
  const granularity = periodGranularity(period.code);
  if (granularity === "year") return String(period.year);
  if (granularity === "quarter") return facts(t, [period.year, period.code]);
  return facts(t, [
    period.year,
    monthNames(locale)[Number(period.code) - 1] ?? period.code,
  ]);
}
