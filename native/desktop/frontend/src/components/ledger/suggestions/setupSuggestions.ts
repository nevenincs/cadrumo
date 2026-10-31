// What the Setup registers offer a field from their own held rows. Like the
// rest of the page's suggestions, a pick is a draft edit the person sees and
// the register still checks it on save.

import type { Suggestion } from "@/components/ui/suggestions";
import type { LedgerRow } from "../../../shell/ledger";
import { distinctText } from "./ledgerSuggestions";

/** The most words a rule offers, the most used first. */
const MOST_USED_WORDS = 400;

/** Text held once by its folded spelling, the first spelling kept. */
export function textOptions(texts: readonly (string | null)[]): Suggestion[] {
  return distinctText(texts).map((text) => ({ value: text, label: text }));
}

/** The items of a list written with `separator` that the typed text does not
 * hold yet. Each option is the whole text with its last item completed, so a
 * pick keeps what came before it. */
export function listOptions(
  items: readonly string[],
  typed: string,
  separator: "," | " ",
): Suggestion[] {
  const before = typed.slice(0, typed.lastIndexOf(separator) + 1);
  const held = new Set(
    before
      .split(separator)
      .map((item) => item.trim())
      .filter(Boolean),
  );
  return distinctText(items)
    .filter((item) => !held.has(item))
    .map((item) => ({ value: `${before}${item}`, label: `${before}${item}` }));
}

/** The words the held movements' descriptions use, the most used first. */
export function descriptionWords(rows: readonly LedgerRow[]): string[] {
  const uses = new Map<string, { word: string; uses: number }>();
  for (const { transaction } of rows)
    for (const word of transaction.description.match(/[\p{L}\p{N}]{3,}/gu) ??
      []) {
      const key = word.toLocaleLowerCase();
      const held = uses.get(key);
      if (held) held.uses += 1;
      else uses.set(key, { word, uses: 1 });
    }
  return [...uses.values()]
    .sort((left, right) => right.uses - left.uses)
    .slice(0, MOST_USED_WORDS)
    .map(({ word }) => word);
}
