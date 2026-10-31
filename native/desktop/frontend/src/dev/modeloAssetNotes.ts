import type { RecordedCalculationNote } from "../shell/modeloContract";

/** What a calculation noted about the filer's assets: a gap of one kind about
 * each of two elements, and a purchase booked as an expense. The values are
 * the text each sentence prints. */
export const ASSET_NOTES: readonly RecordedCalculationNote[] = [
  {
    reason: "activity_asset_claim_gap",
    fact: {
      sentence: "claim_gap_accrued",
      values: [
        ["amount", "412.50"],
        ["box", "0208"],
        ["element", "Laptop"],
        ["end", "2026-03-31"],
        ["start", "2026-01-01"],
      ],
    },
  },
  {
    reason: "activity_asset_claim_gap",
    fact: {
      sentence: "claim_gap_accrued",
      values: [
        ["amount", "96.00"],
        ["box", "0208"],
        ["element", "Printer"],
        ["end", "2026-03-31"],
        ["start", "2026-02-01"],
      ],
    },
  },
  {
    reason: "ledger_expense_may_be_durable",
    fact: {
      sentence: "possibly_durable_expense",
      values: [
        ["category", "office"],
        ["row", "4f1c9a07b2d3"],
      ],
    },
  },
];
