// The words of what a filing handoff leaves out. An element is said by the
// name the list holds for it, never by its id; a list that has no name for
// one of them is said by its number. Nothing here works an amount out.

import { listOf } from "../../../shared/lists";
import type {
  ActivityAssetFilingResult,
  M130Projection,
} from "../../../shell/ledgerSetup";
import type { Translate } from "../../../shell/strings";
import { amountText, dateText } from "../movements/movementWords";
import { ASSET_KEYS, countSentence } from "./assetsWords";

export type Handoff = NonNullable<ActivityAssetFilingResult["filing_handoff"]>;

/** The words of an interval Modelo 100 leaves out, by what can be said of it. */
const GAP_KEYS = {
  accrued: "desktop.ledger.assets.handoff_gap_accrued",
  free_method: "desktop.ledger.assets.handoff_gap_free",
  unavailable: "desktop.ledger.assets.handoff_gap_unavailable",
} as const;

/** The elements a Modelo 130 amount leaves out, by the reason, each worded by
 * their names where every one is known and by their number otherwise. */
const LEFT_OUT_KEYS = {
  free_gap_asset_ids: {
    named: "desktop.ledger.assets.handoff_free_named",
    count: {
      one: "desktop.ledger.assets.handoff_free_count_one",
      other: "desktop.ledger.assets.handoff_free_count",
    },
  },
  agrarian_excluded_asset_ids: {
    named: "desktop.ledger.assets.handoff_agrarian_named",
    count: {
      one: "desktop.ledger.assets.handoff_agrarian_count_one",
      other: "desktop.ledger.assets.handoff_agrarian_count",
    },
  },
  unavailable_asset_ids: {
    named: "desktop.ledger.assets.handoff_unavailable_named",
    count: {
      one: "desktop.ledger.assets.handoff_unavailable_count_one",
      other: "desktop.ledger.assets.handoff_unavailable_count",
    },
  },
} as const;

/** What the handoff leaves out, said about the elements by name. An element
 * the list holds no name for is never said by its id: the sentence that
 * counts is used instead. */
export function leftOutNotes(
  t: Translate,
  locale: string,
  handoff: Handoff,
  names: ReadonlyMap<string, string>,
): string[] {
  const notes: string[] = [];
  let unnamed = 0;
  for (const gap of handoff.m100_gaps) {
    const name = names.get(gap.asset_id);
    if (name === undefined) {
      unnamed += 1;
      continue;
    }
    const kind =
      gap.kind === "accrued" && gap.accrued === null ? "unavailable" : gap.kind;
    notes.push(
      t(GAP_KEYS[kind], {
        name,
        start: dateText(locale, gap.covered_from, true),
        end: dateText(locale, gap.covered_through, true),
        amount: gap.accrued ? amountText(locale, gap.accrued.decimal) : "",
      }),
    );
  }
  if (unnamed > 0)
    notes.push(countSentence(t, ASSET_KEYS.handoff.unnamed, unnamed));
  const quarter = [handoff.material_m130, handoff.intangible_m130].filter(
    (found): found is M130Projection => found !== null,
  );
  for (const field of Object.keys(
    LEFT_OUT_KEYS,
  ) as (keyof typeof LEFT_OUT_KEYS)[]) {
    const ids = [...new Set(quarter.flatMap((found) => found[field]))];
    if (ids.length === 0) continue;
    const known = ids.flatMap((id) => names.get(id) ?? []);
    notes.push(
      known.length === ids.length
        ? t(LEFT_OUT_KEYS[field].named, { names: listOf(locale, known) })
        : countSentence(t, LEFT_OUT_KEYS[field].count, ids.length),
    );
  }
  return notes;
}
