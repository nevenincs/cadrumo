// The words the plan and the timeline add to the tab's shared ones: the keys
// only they name, the tone each state is drawn in, and how a value the
// backend states reads. Every figure and date arrives ready; here it is only
// drawn. A token the catalogue has no word for reads as the generic word,
// never raw.

import type { Translate } from "../../../shell/strings";
import { amountText, dateText, percentText } from "../movements/movementWords";
import type { Amount } from "../../../shell/ledgerSetup";
import { tokenWord } from "./assetsWords";

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

/** The dash a figure that is not stated is drawn as. */
export const DASH = "—";

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

type ValueKind =
  | "date"
  | "amount"
  | "fraction"
  | "method"
  | "kind"
  | "disposal_reason"
  | "prior_regime"
  | "document_kind";

/** How the value of a changed field is worded, by the field's path. A field
 * this table does not know shows its value as the backend states it. */
const VALUE_KIND: Record<string, ValueKind> = {
  in_service_date: "date",
  out_of_service_date: "date",
  "disposal.disposal_date": "date",
  "disposal.reason": "disposal_reason",
  "disposal.proceeds": "amount",
  "disposal.transmission_costs": "amount",
  "disposal.market_value": "amount",
  "disposal.later_affectation_on": "date",
  "disposal.prior_free_depreciation_regime": "prior_regime",
  residual_value: "amount",
  "basis.basis_amount": "amount",
  "basis.non_deductible_iva": "amount",
  "amortization.linear_coefficient": "fraction",
  amount: "amount",
  "amortization.method": "method",
  asset_kind: "kind",
  document_kind: "document_kind",
};

/** A changed field's before or after value in words, as the backend stated
 * it. Nothing is worked out from it. */
export function changeValueText(
  t: Translate,
  locale: string,
  field: string,
  value: string,
): string {
  const kind = Object.hasOwn(VALUE_KIND, field) ? VALUE_KIND[field] : undefined;
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
    case "disposal_reason":
      return tokenWord(t, "disposal_reason", value);
    case "prior_regime":
      return tokenWord(t, "prior_free_depreciation_regime", value);
    case "document_kind":
      return tokenWord(t, "document_kind", value);
    default:
      return value;
  }
}
