// Words and names the Ledger page's components share: its sections, and how
// a period is written in the chrome.

import type { IconName } from "@/components/ui/icon";
import { facts } from "@/shell/compose";
import type { LedgerSection } from "../../shell/layout";
import type { LedgerPeriod } from "../../shell/ledgerGrammar";
import { annualCode, periodWords } from "../../shell/ledgerPeriods";
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

/** A period as the chrome writes it: `2026`, `2026 · 3T` or `2026 · October`,
 * in the words the backend served for it. A period not served, or served in
 * another language than the window shows, is written with its year and its
 * token as it stands: no name is made up for it. */
export function periodText(
  t: Translate,
  locale: string,
  period: LedgerPeriod | null,
  mode: "period" | "year" = "period",
): string {
  if (period === null) return t("desktop.ledger.period.all");
  if (mode === "year") return String(period.year);
  const words = periodWords(period, locale);
  if (words) return words.label;
  if (period.code === annualCode()) return String(period.year);
  return facts(t, [period.year, period.code]);
}
