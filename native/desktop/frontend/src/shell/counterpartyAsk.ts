// What a served way out asks of the counterparty journey: the counterparty
// and the kind its action already binds. A way out that binds none of them
// opens the journey empty, and the person names the counterparty.

import type { ActionArgumentSnapshot } from "./modeloContract/modelo";

/** The party kinds a filing name is stated as. */
export const COUNTERPARTY_KINDS = ["natural_person", "entity"] as const;
export type CounterpartyKind = (typeof COUNTERPARTY_KINDS)[number];

/** The arguments of the counterparty filing-name action a way out holds;
 * null where the way out leaves the argument to the person. */
export type CounterpartyAsk = {
  tax_identifier: string | null;
  country_code: string | null;
  kind: CounterpartyKind | null;
};

const resolved = (
  bindings: readonly ActionArgumentSnapshot[],
  name: string,
): string | null => {
  const value = bindings.find(
    (binding) =>
      binding.argument_name === name && binding.status === "resolved",
  )?.value;
  return typeof value === "string" && value.trim() !== "" ? value : null;
};

/** The ask a way out's served argument bindings make: each argument the
 * verdict resolved to text, and nothing the window guesses. */
export function counterpartyAsk(
  bindings: readonly ActionArgumentSnapshot[],
): CounterpartyAsk {
  const kind = resolved(bindings, "kind");
  return {
    tax_identifier: resolved(bindings, "tax_identifier"),
    country_code: resolved(bindings, "country_code"),
    kind: COUNTERPARTY_KINDS.find((known) => known === kind) ?? null,
  };
}
