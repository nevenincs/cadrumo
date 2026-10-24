// How the movements section says what it stores: every enum by its
// localized label, figures in the chrome language's grouping, dates with the
// year only where the window spans more than one, and an id the page does
// not know as the id itself, never a guess.

import type {
  LedgerReviewStatus,
  LedgerTransaction,
} from "../../../shell/ledger";
import { percentOf } from "../../../shell/ledgerGrammar";
import {
  isClassification,
  isDirection,
  isIrpfCategory,
  isIvaCategory,
  isLifecycleState,
  isSpendingCategory,
  type SpendingCategoryFamily,
} from "../../../shell/ledgerVocabulary";
import type { Translate } from "../../../shell/strings";
import { dateFormats } from "../../../shared/dateFormats";

const lower = (token: string) => token.toLowerCase();

export const categoryLabel = (t: Translate, id: string) =>
  isSpendingCategory(id) ? t(`desktop.ledger.category.${id}`) : id;
export const familyLabel = (t: Translate, family: SpendingCategoryFamily) =>
  t(`desktop.ledger.category_family.${family}`);
export const ivaCategoryLabel = (t: Translate, id: string) =>
  isIvaCategory(id) ? t(`desktop.ledger.iva_category.${id}`) : id;
export const irpfCategoryLabel = (t: Translate, id: string) =>
  isIrpfCategory(id) ? t(`desktop.ledger.irpf_category.${id}`) : id;
export const directionLabel = (t: Translate, direction: string) =>
  isDirection(direction)
    ? t(`desktop.ledger.direction.${lower(direction)}`)
    : direction;
export const lifecycleLabel = (t: Translate, state: string) =>
  isLifecycleState(state)
    ? t(`desktop.ledger.lifecycle.${lower(state)}`)
    : state;
export const classificationLabel = (t: Translate, classification: string) =>
  isClassification(classification)
    ? t(`desktop.ledger.classification.${lower(classification)}`)
    : classification;

/** The classification as the grid writes it: Mixed with its share. */
export function classificationText(
  t: Translate,
  transaction: Pick<
    LedgerTransaction,
    "business_classification" | "business_pct"
  >,
): string {
  const share =
    transaction.business_pct === null
      ? null
      : percentOf(transaction.business_pct);
  if (transaction.business_classification === "MIXED" && share !== null)
    return t("desktop.ledger.classification.mixed_share", {
      share: `${share}%`,
    });
  return classificationLabel(t, transaction.business_classification);
}

/** Who made the stored classification. */
export function classifiedByLabel(t: Translate, source: string): string {
  if (source.startsWith("rule:")) return t("desktop.ledger.classified_by.rule");
  if (source.startsWith("llm:")) return t("desktop.ledger.classified_by.model");
  if (source.startsWith("derived:"))
    return t("desktop.ledger.classified_by.derived");
  if (source === "manual") return t("desktop.ledger.classified_by.manual");
  return t("desktop.ledger.classified_by.auto");
}

/** What the status cell says: the review status, with what readiness found
 * on a reviewed movement. `issues` is null while readiness is not measured:
 * a reviewed movement is then unmeasured, never done. */
export type StatusWord =
  "pending" | "needs_fixing" | "done" | "unmeasured" | "skipped" | "excluded";
export function statusWord(
  status: LedgerReviewStatus,
  issues: number | null,
): StatusWord {
  if (status === "pending") return "pending";
  if (status === "skipped") return "skipped";
  if (status === "excluded") return "excluded";
  if (issues === null) return "unmeasured";
  return issues > 0 ? "needs_fixing" : "done";
}
export function statusLabel(
  t: Translate,
  word: StatusWord,
  issues: number | null,
): string {
  if (word === "unmeasured") return t("desktop.ledger.readiness.not_measured");
  return word === "needs_fixing"
    ? t("desktop.ledger.status.needs_fixing_count", { count: issues ?? 0 })
    : t(`desktop.ledger.status.${word}`);
}

/** A readiness reason as a short noun, for a chip, and as a sentence. */
export const reasonShort = (t: Translate, reason: string) =>
  t(`desktop.ledger.reason.${reason}`);
export const reasonDetail = (t: Translate, reason: string) =>
  t(`desktop.ledger.reason_detail.${reason}`);

const figures = new Map<string, Intl.NumberFormat>();
function figureFormat(locale: string): Intl.NumberFormat {
  let held = figures.get(locale);
  if (!held) {
    held = new Intl.NumberFormat(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    figures.set(locale, held);
  }
  return held;
}

/** An amount in the chrome language's grouping, to the cent. The text is
 * canonical decimal; it is drawn, never computed with. */
export function amountText(locale: string, amount: string): string {
  // A stored amount has at most two decimals and twelve whole digits, which
  // a double holds exactly enough to draw to the cent.
  return figureFormat(locale).format(Number(amount));
}

const percents = new Map<string, Intl.NumberFormat>();
/** A stored fraction as a percentage: `0.21` is `21%`. */
export function percentText(locale: string, fraction: string): string {
  const percent = percentOf(fraction);
  if (percent === null) return fraction;
  let format = percents.get(locale);
  if (!format) {
    format = new Intl.NumberFormat(locale, { maximumFractionDigits: 4 });
    percents.set(locale, format);
  }
  return `${format.format(Number(percent))}%`;
}

const days = new Map<string, string>();
/** How many drawn dates are kept: a few periods' worth. */
const DAYS_KEPT = 4096;

/** A calendar date, with its year only where `withYear`. */
export function dateText(
  locale: string,
  day: string,
  withYear: boolean,
): string {
  const key = `${locale} ${withYear ? "y" : "-"} ${day}`;
  const held = days.get(key);
  if (held !== undefined) return held;
  const text = drawDate(locale, day, withYear);
  if (days.size >= DAYS_KEPT) days.clear();
  days.set(key, text);
  return text;
}

function drawDate(locale: string, day: string, withYear: boolean): string {
  const found = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!found) return day;
  const date = new Date(
    Number(found[1]),
    Number(found[2]) - 1,
    Number(found[3]),
  );
  date.setFullYear(Number(found[1]));
  const formats = dateFormats(locale);
  return (withYear ? formats.medium : formats.short).format(date);
}

/** A moment, as the person's clock reads it. */
export function stampText(locale: string, stamp: string): string {
  const time = Date.parse(stamp);
  return Number.isNaN(time)
    ? stamp
    : dateFormats(locale).dateTime.format(new Date(time));
}

/** An own account by its label in the register, its id where the register
 * was not read or does not hold it, and "No account" for none. */
export function accountLabel(
  t: Translate,
  accounts: readonly { id: string; label: string }[] | null,
  id: string | null,
): string {
  if (id === null) return t("desktop.ledger.account.none");
  return accounts?.find((account) => account.id === id)?.label ?? id;
}
