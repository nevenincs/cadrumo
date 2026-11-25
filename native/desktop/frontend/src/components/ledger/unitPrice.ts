import { formatDecimal } from "../../shared/numbers";

/** A unit price or cost as read: at least the cents a total shows, and every
 * digit it was stored with, to six. */
export function formatUnitPrice(locale: string, decimal: string): string {
  return formatDecimal(locale, decimal, { minFraction: 2, maxFraction: 6 });
}
