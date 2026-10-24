// How the Setup sections say what they show: a refused value, how a call
// ended, a rule's name, and the product's tokens in the chrome language.
// Nothing here decides anything.

import type { GrammarRefusal } from "../../../shell/ledgerGrammar";
import type { LedgerRuleRow } from "../../../shell/ledgerSetup";
import type { Translate } from "../../../shell/strings";
import { categoryLabel, classificationLabel } from "../movements/movementWords";
import { patternWords, type SetupCall } from "./setupModel";

/** A typed value that was refused, with what it most likely meant. */
export function grammarText(t: Translate, refusal: GrammarRefusal): string {
  const said = t(`desktop.ledger.invoices.refusal.${refusal.key}`, {
    raw: refusal.raw,
    limit: refusal.limit ?? "",
  });
  return refusal.suggestion
    ? `${said} ${t("desktop.ledger.invoices.refusal.meant", { suggestion: refusal.suggestion })}`
    : said;
}

/** How a call that did not succeed ended, in a line. Null for one that
 * did. `refusal` words a refusal the section knows better. */
export function callText<R>(
  t: Translate,
  call: SetupCall<R> | null,
  refusal?: (reason: string | null) => string | null,
): string | null {
  if (!call || call.kind === "done") return null;
  if (call.kind === "unknown") return t("desktop.ledger.form.unknown");
  if (call.kind === "saved_unread")
    return t("desktop.ledger.apply.outcome.saved_unread");
  if (call.kind === "refused")
    return (
      refusal?.(call.reason) ??
      t("desktop.ledger.form.refused", { code: call.reason ?? "refused" })
    );
  return t("desktop.ledger.form.failed", { code: call.reason ?? call.code });
}

/** What a rule matches, in plain words where it was written from them. */
export function ruleMatchText(t: Translate, pattern: string): string {
  const words = patternWords(pattern);
  return words === null
    ? t("desktop.ledger.rules.pattern_match")
    : t("desktop.ledger.rules.contains", { words });
}

/** A rule's name, made from what it matches and what it decides: rules
 * keep no name of their own. */
export function ruleName(t: Translate, rule: LedgerRuleRow): string {
  const target = rule.category_id
    ? `${classificationLabel(t, rule.classification)} · ${categoryLabel(t, rule.category_id)}`
    : classificationLabel(t, rule.classification);
  return `${ruleMatchText(t, rule.description_pattern)} → ${target}`;
}

/** The register tokens the chrome words, each family by its own key. */
const TOKEN_WORDS = {
  "capital.disposal": (t: Translate, token: string) =>
    t(`desktop.ledger.capital.disposal.${token}`),
  "capital.kind": (t: Translate, token: string) =>
    t(`desktop.ledger.capital.kind.${token}`),
  "counterparty.scope": (t: Translate, token: string) =>
    t(`desktop.ledger.counterparty.scope.${token}`),
  "counterparty.source": (t: Translate, token: string) =>
    t(`desktop.ledger.counterparty.source.${token}`),
  "inventory.kind": (t: Translate, token: string) =>
    t(`desktop.ledger.inventory.kind.${token}`),
  "inventory.method": (t: Translate, token: string) =>
    t(`desktop.ledger.inventory.method.${token}`),
  "prorrata.letra": (t: Translate, token: string) =>
    t(`desktop.ledger.prorrata.letra.${token}`),
  "prorrata.provenance": (t: Translate, token: string) =>
    t(`desktop.ledger.prorrata.provenance.${token}`),
  "prorrata.regime": (t: Translate, token: string) =>
    t(`desktop.ledger.prorrata.regime.${token}`),
  "ratios.kind": (t: Translate, token: string) =>
    t(`desktop.ledger.ratios.kind.${token}`),
};
export type TokenFamily = keyof typeof TOKEN_WORDS;

/** A register token said in words where the chrome has them; the token
 * itself otherwise, as the product stores it: the registry may name one
 * the chrome does not know yet. */
export function tokenText(
  t: Translate,
  family: TokenFamily,
  token: string | null,
): string {
  if (token === null) return t("desktop.ledger.form.none");
  const said = TOKEN_WORDS[family](t, token);
  return said.startsWith("desktop.") ? token : said;
}
