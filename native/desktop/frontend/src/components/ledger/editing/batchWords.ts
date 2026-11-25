import { facts } from "@/shell/compose";
import type { BatchRowResult } from "../../../shell/ledgerApply";
import type { BatchCounts } from "../../../shell/ledgerBatch";
import type { Translate } from "../../../shell/strings";

const COUNTED = ["applied", "unchanged", "refused", "conflict"] as const;

/** A batch's counts in words, as a preview foresees them or as a write
 * left them: "To change: 12 · Refused: 1". Outcomes no row took are left
 * out. */
export function batchCountsText(
  t: Translate,
  counts: BatchCounts,
  tense: "preview" | "written" = "preview",
): string {
  return facts(
    t,
    COUNTED.filter((outcome) => counts[outcome] > 0).map((outcome) =>
      tense === "preview"
        ? t(`desktop.ledger.batch.count.${outcome}`, {
            count: counts[outcome],
          })
        : t(`desktop.ledger.batch.written.${outcome}`, {
            count: counts[outcome],
          }),
    ),
  );
}

/** Why the ledger will not write a row, in words: the sentence it said, or
 * for a row changed or gone since the page read it, which of the two. */
export function batchRowWords(t: Translate, row: BatchRowResult): string {
  if (row.outcome === "unchanged")
    return t("desktop.ledger.batch.row.unchanged");
  if (row.outcome === "applied") return t("desktop.ledger.batch.row.applied");
  if (row.cause === "changed_since_seen")
    return t("desktop.ledger.apply.refusal.changed_since_seen");
  if (row.cause === "not_found")
    return t("desktop.ledger.apply.refusal.not_found");
  return (
    row.messages?.[0] ??
    t(`desktop.ledger.batch.cause.${row.cause ?? "invalid"}`)
  );
}
