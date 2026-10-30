// The words the plan and the timeline add to the tab's shared ones: the keys
// only they name, the tone each state is drawn in, and how a value the
// backend states reads. Every figure and date arrives ready; here it is only
// drawn. A token the catalogue has no word for reads as the generic word,
// never raw.

import type { Translate } from "../../../shell/strings";
import { amountText, dateText, percentText } from "../movements/movementWords";
import type { Amount, TimelineChange } from "../../../shell/ledgerSetup";
import { ASSET_KEYS, tokenWord, unindexed, wordOfKey } from "./assetsWords";

/** The labels only the plan and the timeline name directly. */
export const PLAN_KEYS = {
  plan_empty: "desktop.ledger.assets.plan.empty",
  no_claims: "desktop.ledger.assets.plan.no_claims",
  timeline_empty: "desktop.ledger.assets.timeline.empty",
  change_to: "desktop.ledger.assets.timeline.change_to",
  from: "desktop.ledger.assets.from",
  until: "desktop.ledger.assets.until",
  reading: "desktop.ledger.form.reading",
} as const;

/** The colour a claim state's glyph is drawn in. Colour only reinforces the
 * glyph and the word beside it. */
const STATE_TONE: Record<string, string> = {
  claimed: "text-success",
  superseded: "text-success",
  missing: "text-destructive",
  partial: "text-warning",
  not_due: "text-muted-foreground",
};

export const stateTone = (token: string) =>
  Object.hasOwn(STATE_TONE, token)
    ? STATE_TONE[token]!
    : "text-muted-foreground";

/** Whether the backend states this amount as a recorded zero. */
export const isStatedZero = (amount: Amount) =>
  amount !== null && Number(amount.decimal) === 0;

/** An amount drawn to the cent, or null where it is not stated. */
export const figureText = (locale: string, amount: Amount) =>
  amount === null ? null : amountText(locale, amount.decimal);

type ValueKind = "date" | "amount" | "fraction" | "method" | "kind" | "reason";

/** How the value of a changed field is worded when the backend gave it no
 * word, by the field's path without its row index. */
const VALUE_KIND: Record<string, ValueKind> = {
  in_service_date: "date",
  out_of_service_date: "date",
  "disposal.disposal_date": "date",
  "disposal.later_affectation_on": "date",
  "disposal.reason": "reason",
  "disposal.proceeds": "amount",
  "disposal.transmission_costs": "amount",
  "disposal.market_value": "amount",
  residual_value: "amount",
  "basis.basis_amount": "amount",
  "basis.non_deductible_iva": "amount",
  "basis.construction_cost": "amount",
  "basis.land_cost": "amount",
  "opening_history.accumulated_amount": "amount",
  "amortization.used_original_price.original_price": "amount",
  "amortization.small_enterprise.prior_period_net_turnover": "amount",
  "amortization.approved_plan.annual_amounts[].amount": "amount",
  amount: "amount",
  "amortization.linear_coefficient": "fraction",
  "basis.business_use_share": "fraction",
  "basis.ownership_share": "fraction",
  "amortization.method": "method",
  "opening_history.amortization_method": "method",
  asset_kind: "kind",
};

/** Fields whose value is free text the person wrote, which is shown as it is
 * even when it looks like a code. */
const TEXT_FIELDS: ReadonlySet<string> = new Set([
  "name",
  "serial_number",
  "description",
  "document_number",
  "supplier_name",
  "supplier_tax_id",
  "basis.prior_allocation_provenance",
  "amortization.used_original_price.evidence_reference",
  "amortization.low_value.election_reference",
  "amortization.low_value.new_material_evidence_reference",
  "amortization.research_development_evidence_reference",
]);

/** Whether a value reads as a code of the program rather than as something a
 * person wrote: a snake_case or dotted token, or a long hexadecimal digest. */
const looksInternal = (value: string) =>
  /^[a-z0-9]+(?:[_.:-][a-z0-9]+)+$/i.test(value) ||
  /^[0-9a-f]{16,}$/i.test(value);

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * A changed field's before or after value in words. The backend's own label
 * comes first (a share as a percentage, a class by its official name), then
 * the word the catalogue has for the key it served, then the value drawn by
 * what the field is. A value with no word that looks like a code of the
 * program reads "Changed", never raw.
 */
export function changeValueText(
  t: Translate,
  locale: string,
  change: TimelineChange,
  side: "before" | "after",
): string {
  const value = change[side];
  if (value === null) return t(ASSET_KEYS.timeline.value_changed);
  const label = change[`${side}_label`];
  if (label !== null && label.trim() !== "") return label;
  const key = change[`${side}_key`];
  const keyed = wordOfKey(t, key);
  if (keyed !== null) return keyed;
  // The backend named a word for this value and the catalogue has none.
  if (key !== null) return t(ASSET_KEYS.timeline.value_changed);
  const path = unindexed(change.field);
  const kind = Object.hasOwn(VALUE_KIND, path) ? VALUE_KIND[path] : undefined;
  switch (kind) {
    case "date":
      return dateText(locale, value, true);
    case "amount":
      return amountText(locale, value);
    case "fraction":
      return percentText(locale, value);
    case "method":
      return tokenWord(t, "method", value);
    case "kind":
      return tokenWord(t, "asset_kind", value);
    case "reason":
      return tokenWord(t, "disposal_reason", value);
    default:
      break;
  }
  if (DATE.test(value)) return dateText(locale, value, true);
  if (TEXT_FIELDS.has(path) && change.field_key !== null) return value;
  return looksInternal(value) ? t(ASSET_KEYS.timeline.value_changed) : value;
}
