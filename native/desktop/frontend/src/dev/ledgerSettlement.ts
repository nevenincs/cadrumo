// The cash an invoice settles for, for the fixtures' invoices: the total less
// the retención withheld at source. The backend states it on every invoice it
// serves (`settlement_amount`); fixtures build their invoices from parts, so
// this stand-in states it for them, and a test holds it to the backend's
// recorded answers.

import type { PublicDecimal } from "../shell/ledger";

const fraction = (text: string) => text.split(".")[1]?.length ?? 0;

/** `total` less `withheld`, spelled to the finer of the two. */
export function settlementOf(
  total: string,
  withheld: string | null,
): PublicDecimal {
  if (withheld === null) return { decimal: total };
  const places = Math.max(fraction(total), fraction(withheld));
  const scaled = (text: string) =>
    BigInt(text.replace(".", "")) * 10n ** BigInt(places - fraction(text));
  const left = scaled(total) - scaled(withheld);
  const sign = left < 0n ? "-" : "";
  const digits = (left < 0n ? -left : left)
    .toString()
    .padStart(places + 1, "0");
  const whole = digits.slice(0, digits.length - places);
  return {
    decimal:
      places === 0
        ? `${sign}${whole}`
        : `${sign}${whole}.${digits.slice(-places)}`,
  };
}
