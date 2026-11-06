// How the movements section says what it stores: every enum by its
// localized label, figures in the chrome language's grouping, dates with the
// year only where the window spans more than one, and an id the page does
// not know as the id itself, never a guess.

import type {
  LedgerReviewStatus,
  LedgerTransaction,
} from "../../../shell/ledger";
import {
  isClassification,
  isDirection,
  isLifecycleState,
} from "../../../shell/ledgerContract";
import { takesBusinessShare } from "../../../shell/ledgerClassifications";
import type { ClassifyBlock } from "../../../shell/ledgerCommands";
import type { ServedVocabulary } from "../../../shell/ledgerServedVocabulary";
import type { Translate } from "../../../shell/strings";
import { wordOrToken } from "../../../shell/tokenWords";
import { formatPercent } from "../../../shared/numbers";

const lower = (token: string) => token.toLowerCase();

export const categoryLabel = (t: Translate, id: string) =>
  wordOrToken(t, "desktop.ledger.category.", id);
export const familyLabel = (t: Translate, family: string) =>
  wordOrToken(t, "desktop.ledger.category_family.", family);
/** The words a category is also found by, such as those a bank statement
 * prints for it, in the catalogue's language. */
export const categoryKeywords = (t: Translate, id: string): string[] => {
  const key = `desktop.ledger.category_keywords.${id}`;
  const said = t(key);
  return said === key ? [] : said.split(/\s+/).filter(Boolean);
};
/** A spending category as a list choice: its name under its family's
 * heading, found by its keywords too. */
export const categoryOption = (t: Translate, family: string, id: string) => ({
  value: id,
  label: categoryLabel(t, id),
  group: familyLabel(t, family),
  keywords: categoryKeywords(t, id),
});
export const ivaCategoryLabel = (t: Translate, id: string) =>
  wordOrToken(t, "desktop.ledger.iva_category.", id);
export const irpfCategoryLabel = (t: Translate, id: string) =>
  wordOrToken(t, "desktop.ledger.irpf_category.", id);
/** What an empty picker of a served list says: that the list is being read
 * or could not be, and `empty` once it was served. */
export const vocabularyEmpty = (
  t: Translate,
  vocabulary: Pick<ServedVocabulary, "state">,
  empty: string,
  offered: number,
) =>
  offered > 0 || vocabulary.state === "ready"
    ? empty
    : vocabulary.state === "loading"
      ? t("desktop.ledger.form.reading")
      : t("desktop.ledger.unavailable");
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
  locale: string,
  transaction: Pick<
    LedgerTransaction,
    "business_classification" | "business_pct"
  >,
): string {
  const fraction = transaction.business_pct;
  if (
    takesBusinessShare(transaction.business_classification) === true &&
    fraction !== null
  )
    return t("desktop.ledger.classification.mixed_share", {
      share: formatPercent(locale, fraction, { unit: "fraction" }),
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

/** Why a classify command cannot run on its target, as said to the person. */
export function blockText(t: Translate, block: ClassifyBlock): string {
  switch (block.kind) {
    case "nothing_selected":
      return t("desktop.ledger.classify.nothing");
    case "hidden":
      return t("desktop.ledger.selection.hidden", {
        hidden: block.hidden,
        selected: block.selected,
      });
    case "transfers_only":
      return t("desktop.ledger.classify.transfers_only");
    case "inactive_only":
      return t("desktop.ledger.classify.inactive_only");
  }
}
