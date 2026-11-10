// The scenario ledger's reads over its movements: the list's filter, sort,
// group and page, the values the filter offers, and the readiness issues of
// a period. Everything it answers is synthetic.

import { recordedSpan } from "./periodRecording";
import { SCENARIO_LEDGER_PAYMENTS } from "./assetsRegister";
import { isClassification, isDirection } from "../shell/ledgerContract";
import type {
  JsonObject,
  JsonValue,
  LedgerReviewStatus,
  LedgerRow,
  LedgerSortField,
  PublicPeriod,
} from "../shell/ledger";
import {
  type FixtureLedger,
  type FixtureMovement,
  LEDGER_FIXTURE_PROFILE_ID,
} from "./fixtures/ledger";
import { invalid } from "./ledgerRequestFixture";
import { fixtureDay } from "@/dev/fixtureDates";

export function reviewStatus(classification: string): LedgerReviewStatus {
  if (classification === "NOT_YET_PROCESSED") return "pending";
  if (classification === "SKIPPED_BY_RULE") return "skipped";
  if (classification === "REVIEWED_EXCLUDED") return "excluded";
  return "reviewed";
}
/** The purchases the recorded elements own, which the scenario's rows do not
 * hold: the assets register has a ledger of its own, and the identifier each
 * payment answers under is the one the register's recording minted for it. */
export const OWNED_PURCHASES: Readonly<Record<string, string>> =
  Object.fromEntries(
    SCENARIO_LEDGER_PAYMENTS.filter((payment) => payment.asset_id !== null).map(
      (payment) => [payment.transaction_id, payment.description],
    ),
  );

/** What the scenario's records state only outside anything the page draws. */
export const KNOWN_ONLY = {
  counterparty: "Asesoría Antigua, S.L.",
  description: "Cuota del colegio profesional",
  group: "Oficina antigua",
  payer: "PAGADOR-ANTIGUO",
  right: "DERECHO-ANTIGUO",
  reference: "EXPEDIENTE-2019/4",
} as const;

export const row = (movement: FixtureMovement): LedgerRow => ({
  transaction: { ...movement.transaction },
  review_status: reviewStatus(movement.transaction.business_classification),
  group_label: movement.group_label,
  own_account_id: movement.own_account_id,
  withholding: movement.withholding.map((entry) => ({ ...entry })),
});

/** The days of a period, from the recording of what the backend serves; null
 * for a year or a code it holds none of. */
export function periodSpan(
  year: number,
  code: string,
): [string, string] | null {
  const span = recordedSpan(year, code);
  return span ? [span.from, span.to] : null;
}

/** The list's filter clauses, refused as the product refuses them. */
function filterOf(clauses: JsonValue | undefined) {
  if (clauses === undefined) clauses = [];
  if (!Array.isArray(clauses)) return invalid();
  const seen = new Map<string, string>();
  for (const clause of clauses) {
    const found =
      typeof clause === "string"
        ? /^([a-z][a-z0-9_.]*)=(.*)$/s.exec(clause)
        : null;
    if (!found || seen.has(found[1]!)) return invalid();
    seen.set(found[1]!, found[2]!);
  }
  const tests: ((movement: FixtureMovement) => boolean)[] = [];
  for (const [key, value] of seen) {
    if (key === "status") {
      if (!["pending", "reviewed", "skipped", "excluded"].includes(value))
        return invalid();
      tests.push(
        (m) => reviewStatus(m.transaction.business_classification) === value,
      );
    } else if (key === "period" || key === "year") {
      if (!seen.has("period") || !seen.has("year")) return invalid();
      if (key === "year") continue;
      const year = Number(seen.get("year"));
      const span = /^\d{4}$/.test(seen.get("year")!)
        ? periodSpan(year, value)
        : null;
      if (!span) return invalid();
      tests.push(
        (m) => m.transaction.date >= span[0] && m.transaction.date <= span[1],
      );
    } else if (key === "issue") {
      if (!["original-file", "gap", "duplicate", "parser"].includes(value))
        return invalid();
      tests.push((m) => m.issue === value);
    } else if (key === "import") {
      tests.push((m) => m.import_batch_id === value);
    } else if (key === "classification") {
      const wanted = value.toUpperCase();
      if (!isClassification(wanted)) return invalid();
      tests.push((m) => m.transaction.business_classification === wanted);
    } else if (key === "text") {
      if (value.length > 128) return invalid();
      const needle = value.toLowerCase();
      tests.push((m) =>
        [
          m.transaction.description,
          m.transaction.counterparty,
          m.transaction.category_id ?? "",
        ].some((field) => field.toLowerCase().includes(needle)),
      );
    } else if (key === "direction") {
      const wanted = value.toUpperCase();
      if (!isDirection(wanted)) return invalid();
      tests.push((m) => m.transaction.direction === wanted);
    } else if (key === "account") {
      if (!/^acc-[0-9]{2,}$/.test(value)) return invalid();
      tests.push((m) => m.own_account_id === value);
    } else {
      return invalid();
    }
  }
  return (movement: FixtureMovement) => tests.every((test) => test(movement));
}

function sortKey(movement: FixtureMovement, field: LedgerSortField): string {
  const t = movement.transaction;
  switch (field) {
    case "date":
      return t.date;
    case "value_date":
      return t.value_date ?? "";
    case "amount":
      return t.amount.padStart(20, "0");
    case "description":
      return t.description;
    case "created_at":
      return t.created_at;
    case "modified_at":
      return t.modified_at;
    case "classified_at":
      return t.classified_at ?? "";
    case "lifecycle_state":
      return t.lifecycle_state;
    case "classification":
      return t.business_classification;
  }
}
export const compare = (left: string, right: string) =>
  left < right ? -1 : left > right ? 1 : 0;

/** Filter, then group selection, then sort, then group partition, then
 * the page: the product's order. */
/** The values the backend would distil from the whole scenario ledger,
 * whatever period the page holds, and the one record the page never draws. */
export function knownValues(
  ledger: FixtureLedger,
  request: JsonObject,
): JsonObject {
  const kinds = request.kinds as readonly string[];
  const newest = [...ledger.movements].sort((a, b) =>
    b.transaction.date.localeCompare(a.transaction.date),
  );
  const distinct = (texts: readonly (string | null)[]) => [
    ...new Set(texts.filter((text): text is string => Boolean(text))),
  ];
  const texts = (kind: string, values: readonly (string | null)[]) =>
    kinds.includes(kind)
      ? distinct(values).map((text) => ({
          text,
          uses: 1,
          last_used: fixtureDay(1, 15, -6),
          counterparty: null,
        }))
      : [];
  return {
    profile_id: LEDGER_FIXTURE_PROFILE_ID,
    counterparties: kinds.includes("counterparty")
      ? distinct([
          ...newest.map((found) => found.transaction.counterparty),
          KNOWN_ONLY.counterparty,
        ]).map((name) => ({
          name,
          tax_id: name === KNOWN_ONLY.counterparty ? "B99999990" : null,
          country: name === KNOWN_ONLY.counterparty ? "ES" : null,
          identification_state: null,
          uses: 1,
          last_used: fixtureDay(1, 15, -6),
        }))
      : [],
    descriptions: texts("description", [
      ...newest.map((found) => found.transaction.description),
      KNOWN_ONLY.description,
    ]),
    group_labels: texts("group_label", [
      ...newest.map((found) => found.group_label),
      KNOWN_ONLY.group,
    ]),
    m210_payers: texts("m210_payer", [KNOWN_ONLY.payer]),
    m210_assets: texts("m210_asset", [KNOWN_ONLY.right]),
    asset_references: texts("asset_reference", [KNOWN_ONLY.reference]),
    truncated: [],
  };
}

export function list(ledger: FixtureLedger, request: JsonObject): JsonObject {
  const keep = filterOf(request.filters);
  const sortBy = request.sort_by ?? null;
  const order = request.sort_order ?? "asc";
  const limit = request.limit ?? null;
  const offset = request.offset ?? 0;
  const SORTS: readonly string[] = [
    "date",
    "value_date",
    "amount",
    "description",
    "created_at",
    "modified_at",
    "classified_at",
    "lifecycle_state",
    "classification",
  ];
  if (
    (sortBy !== null && !SORTS.includes(sortBy as string)) ||
    (order !== "asc" && order !== "desc") ||
    (limit !== null &&
      (typeof limit !== "number" || !Number.isInteger(limit) || limit < 1)) ||
    typeof offset !== "number" ||
    !Number.isInteger(offset) ||
    offset < 0
  )
    return invalid();
  let rows = ledger.movements.filter(
    (movement) =>
      keep(movement) &&
      !(request.exclude_llm_rejected === true && movement.llm_rejected),
  );
  if (typeof request.group === "string") {
    const group = request.group.trim();
    rows = rows.filter((movement) => (movement.group_label ?? "") === group);
  }
  if (sortBy === null) {
    rows.sort(
      (a, b) =>
        compare(a.transaction.date, b.transaction.date) ||
        compare(a.transaction.transaction_id, b.transaction.transaction_id),
    );
  } else {
    const field = sortBy as LedgerSortField;
    const descending = order === "desc";
    rows.sort((a, b) => {
      const left = sortKey(a, field);
      const right = sortKey(b, field);
      // An empty projection sorts last in both directions; ties go by id.
      if ((left === "") !== (right === "")) return left === "" ? 1 : -1;
      const primary = compare(left, right) * (descending ? -1 : 1);
      return (
        primary ||
        compare(a.transaction.transaction_id, b.transaction.transaction_id)
      );
    });
  }
  if (request.by_group === true) {
    const UNGROUPED = "￿";
    rows = rows
      .map((movement, at) => ({ movement, at }))
      .sort(
        (a, b) =>
          compare(
            a.movement.group_label ?? UNGROUPED,
            b.movement.group_label ?? UNGROUPED,
          ) ||
          (sortBy === null
            ? compare(
                a.movement.transaction.transaction_id,
                b.movement.transaction.transaction_id,
              )
            : a.at - b.at),
      )
      .map(({ movement }) => movement);
  }
  const total = rows.length;
  const end =
    limit === null ? total : Math.min(offset + (limit as number), total);
  return {
    profile_id: LEDGER_FIXTURE_PROFILE_ID,
    rows: rows.slice(offset, end).map(row) as unknown as JsonValue,
    total,
    truncated: offset > 0 || end < total,
    offset,
    limit: limit as number | null,
    by_group: request.by_group === true,
  };
}

/** The one movement `prefix` names, as the product resolves an id prefix. */
export function resolve(ledger: FixtureLedger, prefix: JsonValue | undefined) {
  if (typeof prefix !== "string" || prefix.length < 1 || prefix.length > 96)
    return invalid();
  const found = ledger.movements.filter((movement) =>
    movement.transaction.transaction_id.startsWith(prefix),
  );
  if (found.length === 0) throw new Stopped("ERROR_TRANSACTION_NOT_FOUND");
  if (found.length > 1)
    throw new Stopped("REFUSED_FINANCIAL_LEDGER_TRANSACTION_ID_PREFIX");
  return found[0]!;
}
/** An operation the runtime settled without changing anything. */
export class Stopped extends Error {
  constructor(readonly reason: string) {
    super(reason);
  }
}

export function inPeriod(
  movement: FixtureMovement,
  period: JsonValue | undefined,
) {
  if (period === null || period === undefined) return true;
  const { filing_year, code } = period as unknown as PublicPeriod;
  const span = periodSpan(filing_year, code);
  return (
    span !== null &&
    movement.transaction.date >= span[0] &&
    movement.transaction.date <= span[1]
  );
}

/** What the readiness checks find missing for the movements of a period. */
export function issues(ledger: FixtureLedger, period: JsonValue | undefined) {
  const found: { transaction_id: string; reason: string; detail: string }[] =
    [];
  for (const movement of ledger.movements) {
    if (
      !inPeriod(movement, period) ||
      movement.transaction.lifecycle_state !== "ACTIVE"
    )
      continue;
    const t = movement.transaction;
    const id = t.transaction_id;
    if (t.business_classification === "NOT_YET_PROCESSED")
      found.push({
        transaction_id: id,
        reason: "missing_business_classification",
        detail: "Not yet classified.",
      });
    else if (
      t.business_classification === "BUSINESS" ||
      t.business_classification === "MIXED"
    ) {
      // The product's rule: an expense, or an income that refunds one,
      // carrying a purchase invoice, takes a spending category.
      const takesCategory =
        t.direction === "OUTGOING" ||
        (t.direction === "INCOMING" && t.purchase_invoice_evidence_id !== null);
      if (takesCategory && !t.category_id)
        found.push({
          transaction_id: id,
          reason: "missing_category",
          detail: "No expense category.",
        });
      if (t.business_classification === "MIXED" && !t.usage_ratio_id)
        found.push({
          transaction_id: id,
          reason: "missing_proportionality_reference",
          detail: "Mixed without a usage ratio.",
        });
      if (t.currency !== "EUR" && !t.value_in_eur)
        found.push({
          transaction_id: id,
          reason: "unsupported_currency",
          detail: "No euro value.",
        });
    }
  }
  return found;
}
