// The words the plan and the timeline add to the tab's shared ones: the keys
// only they name, the tone each state is drawn in, and how a value the
// backend states reads. Every figure and date arrives ready; here it is only
// drawn. A token the chrome has no word for reads as "other", never raw.

import type { Translate } from "../../../shell/strings";
import { amountText, dateText } from "../movements/movementWords";
import type { Amount } from "./assetsContract";
import { stateOf } from "./assetsWords";

/** The labels only the plan and the timeline name directly. */
export const PLAN_KEYS = {
  pending: "desktop.ledger.assets.plan.column.pending",
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

/** The colour a state's glyph is drawn in. Colour only reinforces the glyph
 * and the word beside it. */
const STATE_TONE: Record<ReturnType<typeof stateOf>, string> = {
  claimed: "text-success",
  missing: "text-destructive",
  partial: "text-warning",
  incomplete: "text-warning",
  forecast: "text-muted-foreground",
  other: "text-muted-foreground",
};

export const stateTone = (token: string) => STATE_TONE[stateOf(token)];

/**
 * A closed set of tokens worded by a key family: `family` plus the token,
 * and "other" where the chrome has no word for the token. The backend serves
 * the tokens, so no list of them is kept here.
 */
function familyWord(t: Translate, family: string, token: string): string {
  const key = `${family}.${token}`;
  const said = t(key);
  return said === key ? t(`${family}.other`) : said;
}

export const methodWord = (t: Translate, token: string) =>
  familyWord(t, "desktop.ledger.assets.option.method", token);
export const kindWord = (t: Translate, token: string) =>
  familyWord(t, "desktop.ledger.assets.option.kind", token);
export const reasonWord = (t: Translate, token: string) =>
  familyWord(t, "desktop.ledger.assets.option.reason", token);

/** Whether the backend states this amount as a recorded zero. */
export const isStatedZero = (amount: Amount) =>
  amount !== null && Number(amount.decimal) === 0;

/** An amount drawn to the cent, or null where it is not stated. */
export const figureText = (locale: string, amount: Amount) =>
  amount === null ? null : amountText(locale, amount.decimal);

type ValueKind = "date" | "amount" | "method" | "kind" | "reason";

/** How the value of a changed field is worded, by the field. A field this
 * table does not know shows its value as the backend states it. */
const VALUE_KIND: Record<string, ValueKind> = {
  in_service_date: "date",
  baja_date: "date",
  from: "date",
  until: "date",
  basis: "amount",
  amount: "amount",
  residual_value: "amount",
  method: "method",
  kind: "kind",
  baja_reason: "reason",
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
    case "method":
      return methodWord(t, value);
    case "kind":
      return kindWord(t, value);
    case "reason":
      return reasonWord(t, value);
    default:
      return value;
  }
}
