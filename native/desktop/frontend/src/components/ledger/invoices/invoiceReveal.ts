// What keeps an invoice a link selects out of the catalogue grid: the
// person's own filters, search or the period shown. Each is named exactly,
// so showing the invoice clears only what hides it.

import type { CatalogueInvoice } from "../../../shell/ledger";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import {
  NO_FILTER,
  filterCatalogue,
  type CatalogueFilter,
} from "./invoiceModel";

/** The section's own filters, without the page's period. */
export type SectionFilter = Omit<CatalogueFilter, "period">;

export type InvoiceHiding = {
  /** The filters that each, on its own, leave the invoice out. */
  readonly filters: readonly (keyof SectionFilter)[];
  /** Whether the period shown leaves it out. */
  readonly period: boolean;
};

/** Why `invoice` is not drawn, or null when nothing the person chose hides
 * it. The filters are a conjunction, tried one at a time. */
export function invoiceHiding(
  invoice: CatalogueInvoice,
  filter: SectionFilter,
  period: LedgerPeriod | null,
): InvoiceHiding | null {
  const keeps = (only: Partial<CatalogueFilter>) =>
    filterCatalogue([invoice], { ...NO_FILTER, ...only }).length > 0;
  const filters = (Object.keys(filter) as (keyof SectionFilter)[]).filter(
    (key) => !keeps({ [key]: filter[key] }),
  );
  const byPeriod = period !== null && !keeps({ period });
  return filters.length > 0 || byPeriod ? { filters, period: byPeriod } : null;
}

/** `filter` with those that hide an invoice taken off, and no others. */
export function withoutHiding(
  filter: SectionFilter,
  hiding: InvoiceHiding,
): SectionFilter {
  const next = { ...filter };
  for (const key of hiding.filters)
    Object.assign(next, { [key]: NO_FILTER[key] });
  return next;
}
