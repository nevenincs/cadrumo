// What the window does with a batch edit beside planning it: the preview a
// review shows before anything is written, the properties a person copies
// from one movement and pastes onto others, and the undo of a batch just
// written. The ledger answers for every row; the window only shows what it
// answered and stages what the person chose. Copied values live in the page's
// memory only.

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type { LedgerPort } from "./ledger";
import type { OutputLanguage } from "./ledgerClassificationContract";
import type {
  LedgerBatchUpdatePreviewWindowRequest,
  LedgerBatchUpdateResult,
  LedgerPropertySetField,
} from "./ledgerMovementContract";
import { LatestAnswerSession, type LatestAnswer } from "./ledgerLatestAnswer";
import {
  batchRequest,
  batchRequestRow,
  isPropertyField,
  propertyValue,
  splitBatch,
  type BatchRequestRow,
  type PropertySet,
} from "./ledgerPlan";
import type { BatchRowResult, StepReport } from "./ledgerApply";
import { storedFieldValue, type StageCell } from "./ledgerStage";
import type { LedgerTransactionReviewProjection } from "./ledgerReadContract";

// ---- The preview -------------------------------------------------------------

/** What the ledger answered for each batch part's preview, in order. */
export type BatchPreview =
  | { kind: "none" }
  | { kind: "waiting" }
  | { kind: "failed"; retry: () => void }
  | { kind: "answer"; results: LedgerBatchUpdateResult[]; retry: () => void };

/** Asks the ledger what each part would do, one part after another; any
 * part it does not answer leaves the whole preview unanswered. */
async function askPreviews(
  port: LedgerPort,
  requests: readonly LedgerBatchUpdatePreviewWindowRequest[],
): Promise<LatestAnswer<LedgerBatchUpdateResult[]>> {
  const results: LedgerBatchUpdateResult[] = [];
  for (const request of requests) {
    const outcome = await port.submit("ledger.update.batch.preview", request);
    if (
      outcome.kind !== "settled" ||
      outcome.result.outcome !== "previewed" ||
      outcome.result.rows.length !== request.rows.length
    )
      return { kind: "failed" };
    results.push(outcome.result);
  }
  return { kind: "answer", result: results };
}

type PreviewQuestion = {
  requests: readonly LedgerBatchUpdatePreviewWindowRequest[];
  /** The read the requests were made from: a new read asks again even when
   * the requests are the same, since the ledger may have changed beneath
   * them without a new stamp. */
  read: object | null;
};
const sameQuestion = (one: PreviewQuestion, other: PreviewQuestion) =>
  one.read === other.read &&
  JSON.stringify(one.requests) === JSON.stringify(other.requests);

/** The preview of exactly `requests`, made from the read `read`, kept current
 * while the page holds it: a changed request or a new read is asked about
 * again, and only the latest answer counts. */
export function useBatchPreview(
  port: LedgerPort,
  requests: readonly LedgerBatchUpdatePreviewWindowRequest[],
  read: object | null,
): BatchPreview {
  const [session] = useState(
    () =>
      new LatestAnswerSession<PreviewQuestion, LedgerBatchUpdateResult[]>(
        (asked) => askPreviews(port, asked.requests),
        sameQuestion,
        0,
        (asked) => asked.requests.length === 0,
      ),
  );
  const view = useSyncExternalStore(session.subscribe, session.snapshot);
  const key = JSON.stringify(requests);
  useEffect(() => {
    session.start();
    return () => session.stop();
  }, [session]);
  useEffect(() => {
    session.want({
      requests: JSON.parse(key) as LedgerBatchUpdatePreviewWindowRequest[],
      read,
    });
  }, [session, key, read]);
  const none = requests.length === 0;
  return useMemo((): BatchPreview => {
    const retry = () => session.retry();
    if (none) return { kind: "none" };
    if (view.kind === "answer")
      return { kind: "answer", results: view.result, retry };
    if (view.kind === "failed") return { kind: "failed", retry };
    return { kind: "waiting" };
  }, [session, view, none]);
}

/** How many rows took each outcome, over every part. */
export type BatchCounts = LedgerBatchUpdateResult["counts"];

export function batchCounts(
  results: readonly LedgerBatchUpdateResult[],
): BatchCounts {
  const counts: BatchCounts = {
    applied: 0,
    unchanged: 0,
    refused: 0,
    conflict: 0,
  };
  for (const result of results)
    for (const row of result.rows) counts[row.outcome] += 1;
  return counts;
}

/** The rows of every part that will not be written, refused first, in
 * order. */
export function unwrittenRows(
  results: readonly LedgerBatchUpdateResult[],
): BatchRowResult[] {
  const rows = results.flatMap((result) => result.rows);
  return [
    ...rows.filter((row) => row.outcome === "refused"),
    ...rows.filter((row) => row.outcome === "conflict"),
  ];
}

// ---- Copying and pasting properties -----------------------------------------

/** The properties a person can copy from one movement and paste onto others,
 * in the groups the dialog shows them. A property the page does not stage is
 * left out: a paste goes through the page's changes. */
export const PROPERTY_GROUPS = [
  {
    group: "classification",
    fields: [
      "business_classification",
      "business_pct",
      "category_id",
      "usage_ratio_id",
    ],
  },
  { group: "iva", fields: ["iva_category", "iva_rate", "deduction_fact_kind"] },
  { group: "irpf", fields: ["irpf_category"] },
  { group: "counterparty", fields: ["counterparty"] },
  { group: "notes", fields: ["notes"] },
  { group: "group", fields: ["group_label"] },
] as const satisfies readonly {
  group: string;
  fields: readonly (LedgerPropertySetField & string)[];
}[];
export type PropertyGroup = (typeof PROPERTY_GROUPS)[number]["group"];
export type CopyableField = (typeof PROPERTY_GROUPS)[number]["fields"][number];

/** A movement's stored value of `field`, as a property set carries it. */
export const storedProperty = (
  row: LedgerTransactionReviewProjection,
  field: CopyableField,
): string | null => propertyValue(field, storedFieldValue(row, field));

/** The stored values of `fields` on `row`, as one typed property set. */
export function copiedProperties(
  row: LedgerTransactionReviewProjection,
  fields: readonly CopyableField[],
): PropertySet {
  const values: Partial<Record<LedgerPropertySetField, string | null>> = {};
  for (const field of fields) values[field] = storedProperty(row, field);
  return batchRequestRow(
    row.transaction.transaction_id,
    row.transaction.modified_at,
    values,
  ).properties;
}

/** The value a property set carries for `field`, null where it clears it. */
export const propertyOf = (
  set: PropertySet,
  field: LedgerPropertySetField,
): string | null => set[field] ?? null;

/** The preview rows of pasting `set` onto each of `ids` the page holds, with
 * the `modified_at` it read; a movement it does not hold is counted apart. */
export function pasteRequests(
  set: PropertySet,
  ids: readonly string[],
  rows: ReadonlyMap<string, LedgerTransactionReviewProjection>,
  outputLanguage?: OutputLanguage,
): { requests: LedgerBatchUpdatePreviewWindowRequest[]; unread: number } {
  const asked: { request: BatchRequestRow }[] = [];
  let unread = 0;
  const values = Object.fromEntries(
    set.fields.map((field) => [field, propertyOf(set, field)]),
  ) as Partial<Record<LedgerPropertySetField, string | null>>;
  for (const id of ids) {
    const row = rows.get(id);
    if (!row) {
      unread += 1;
      continue;
    }
    asked.push({
      request: batchRequestRow(id, row.transaction.modified_at, values),
    });
  }
  const { parts, tooLarge } = splitBatch(asked, undefined, outputLanguage);
  return {
    requests: parts.map((part) =>
      batchRequest(
        part.map((found) => found.request),
        outputLanguage,
      ),
    ),
    unread: unread + tooLarge.length,
  };
}

/** What a paste would change, as the preview answered: on how many rows each
 * property changes, and the value it takes. */
export function pasteChanges(
  set: PropertySet,
  results: readonly LedgerBatchUpdateResult[],
): { field: LedgerPropertySetField; value: string | null; rows: number }[] {
  const written = results
    .flatMap((result) => result.rows)
    .filter((row) => row.outcome === "applied");
  return set.fields.map((field) => ({
    field,
    value: propertyOf(set, field),
    rows: written.filter((row) => (row.changed_fields ?? []).includes(field))
      .length,
  }));
}

/** The cells a paste stages: on each row the preview would write, each
 * property it would change, as the page's ordinary changes. */
export function pasteCells(
  set: PropertySet,
  results: readonly LedgerBatchUpdateResult[],
  rows: ReadonlyMap<string, LedgerTransactionReviewProjection>,
): StageCell[] {
  const cells: StageCell[] = [];
  for (const row of results.flatMap((result) => result.rows)) {
    const stored = rows.get(row.transaction_id);
    if (row.outcome !== "applied" || !stored) continue;
    for (const field of row.changed_fields ?? []) {
      if (!isPropertyField(field)) continue;
      const value = propertyOf(set, field);
      cells.push({
        id: row.transaction_id,
        field,
        value: value === null ? { kind: "clear" } : { kind: "set", value },
        stored: storedFieldValue(stored, field),
      });
    }
  }
  return cells;
}

// ---- Undo after a save -------------------------------------------------------

/** The cells that write back what each row a batch just wrote held, staged on
 * the movement under the id it now has, and how many written rows the read
 * after the save does not show, which are left out. The undo is a new
 * correction: the history keeps both. */
export function undoCells(
  reports: readonly StepReport[],
  fresh: ReadonlyMap<string, LedgerTransactionReviewProjection> | null,
): { cells: StageCell[]; unread: number } {
  const cells: StageCell[] = [];
  let unread = 0;
  for (const report of reports) {
    if (report.step.kind !== "batch" || report.batch?.outcome !== "applied")
      continue;
    for (const row of report.batch.rows) {
      if (row.outcome !== "applied" || !row.previous) continue;
      const id = row.result_transaction_id ?? row.transaction_id;
      // The undo is sent with the movement as read after the save, so one
      // changed again since is found changed, never written over.
      const now = fresh?.get(id);
      if (!now) {
        unread += 1;
        continue;
      }
      for (const field of row.changed_fields ?? []) {
        if (!isPropertyField(field)) continue;
        const value = propertyOf(row.previous, field);
        cells.push({
          id,
          field,
          value: value === null ? { kind: "clear" } : { kind: "set", value },
          stored: storedFieldValue(now, field),
        });
      }
    }
  }
  return { cells, unread };
}

/** Whether an apply wrote any batch row an undo could write back. */
export const undoable = (reports: readonly StepReport[]): boolean =>
  reports.some(
    (report) =>
      report.step.kind === "batch" &&
      report.batch?.outcome === "applied" &&
      report.batch.rows.some((row) => row.outcome === "applied"),
  );
