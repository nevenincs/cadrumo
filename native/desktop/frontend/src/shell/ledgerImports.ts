// What an import hands the Ledger page when the person asks to see what it
// brought in: the batches it wrote and the days their movements span. The
// page shows the period that holds those days and its movements grid keeps
// to those batches.

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
