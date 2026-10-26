// What an import hands the Ledger page when the person asks to see what it
// brought in: the batches it wrote and the days their movements span. The
// page shows the period that holds those days and its movements grid keeps
// to those batches.

import { periodOf, type LedgerPeriod } from "./ledgerGrammar";

/** The import batches one import wrote, one per file that brought rows in,
 * and the first and last day of their movements. */
export type ImportedBatches = {
  batches: string[];
  span: { from: string; to: string };
};

/** Shows the movements of `shown` in the grid. */
export type ShowImportBatch = (shown: ImportedBatches) => void;

/** The list filter clauses that select one batch's movements. */
export const importBatchFilters = (batch: string): string[] => [
  `import=${batch}`,
];

/** The smallest period that holds every day of `span`: its month, quarter
 * or year, or null for every period when it crosses a year. */
export function periodCovering(span: {
  from: string;
  to: string;
}): LedgerPeriod | null {
  for (const granularity of ["month", "quarter", "year"] as const) {
    const first = periodOf(span.from, granularity);
    const last = periodOf(span.to, granularity);
    if (first && last && first.year === last.year && first.code === last.code)
      return first;
  }
  return null;
}
