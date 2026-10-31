import type { RecordedCalculationNote } from "../shell/modeloContract";

const GAP = "No dotación is recorded for part of the year.";

/** What a calculation noted about the filer's assets: a gap of one kind about
 * each of two elements, and a purchase booked as an expense. The window draws
 * the served sentences as they are, in whatever language they arrive. */
export const ASSET_NOTES: readonly RecordedCalculationNote[] = [
  {
    reason: "activity_asset_claim_gap",
    fact: {
      sentence: "claim_gap_accrued",
      values: [
        ["amount", "412.50"],
        ["box", "0208"],
        ["end", "2026-03-31"],
        ["start", "2026-01-01"],
      ],
      element_refs: ["laptop"],
      row_refs: [],
    },
    element_names: [["laptop", "Laptop"]],
    message: "Laptop: no dotación is recorded from Jan 1 to Mar 31, 2026.",
    detail: GAP,
  },
  {
    reason: "activity_asset_claim_gap",
    fact: {
      sentence: "claim_gap_accrued",
      values: [
        ["amount", "96.00"],
        ["box", "0208"],
        ["end", "2026-03-31"],
        ["start", "2026-02-01"],
      ],
      element_refs: ["printer"],
      row_refs: [],
    },
    element_names: [["printer", "Printer"]],
    message: "Printer: no dotación is recorded from Feb 1 to Mar 31, 2026.",
    detail: GAP,
  },
  {
    reason: "ledger_expense_may_be_durable",
    fact: {
      sentence: "possibly_durable_expense",
      values: [
        ["category", "office"],
        ["row_date", "2026-02-14"],
        ["row_amount", "650.00"],
      ],
      element_refs: [],
      row_refs: ["movement"],
    },
    element_names: [],
    message:
      "The ledger entry of Feb 14, 2026 for 650.00 may be a durable purchase.",
    detail: "A purchase booked as an expense may belong in your register.",
  },
];
