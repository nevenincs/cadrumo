import type {
  JsonObject,
  LedgerDecision,
  LedgerDefinitionId,
  LedgerFailure,
  LedgerOutcome,
  LedgerPort,
  LedgerRow,
  LedgerTransaction,
} from "../../src/shell/ledger";

/** A synthetic movement: an active, unclassified outgoing payment unless
 * `facts` says otherwise. Every value is invented. */
export function movement(
  id: string,
  facts: Partial<LedgerTransaction> = {},
  group: string | null = null,
): LedgerRow {
  const transaction: LedgerTransaction = {
    transaction_id: id,
    date: "2026-10-05",
    booked_date: "2026-10-05",
    value_date: null,
    amount: "36.30",
    currency: "EUR",
    direction: "OUTGOING",
    counterparty: "Papelería Trazo",
    description: "PAPELERIA TRAZO 0045",
    business_classification: "NOT_YET_PROCESSED",
    business_pct: null,
    category_id: null,
    taxable_base: null,
    iva_rate: null,
    iva_amount: null,
    iva_category: null,
    counterparty_country: null,
    counterparty_identification_state: null,
    irpf_category: null,
    m210_income_classification: null,
    usage_ratio_id: null,
    prorrata_reference: null,
    purchase_invoice_evidence_id: null,
    invoice_id: null,
    attachment_ids: [],
    notes: "",
    lifecycle_state: "ACTIVE",
    classified_by: "",
    classified_at: null,
    classification_reason: "",
    classification_confidence: null,
    source_jurisdiction: null,
    value_in_eur: null,
    fx_rate: null,
    created_at: "2026-10-05T08:00:00Z",
    modified_at: "2026-10-05T08:00:00Z",
    ...facts,
  };
  const status =
    transaction.business_classification === "NOT_YET_PROCESSED"
      ? "pending"
      : "reviewed";
  return { transaction, review_status: status, group_label: group };
}

/** A 64-hex-digit id made from a short name, shaped like the product's. */
export const hexId = (name: string) =>
  Array.from(name)
    .map((char) => char.charCodeAt(0).toString(16).padStart(2, "0"))
    .join("")
    .padEnd(64, "0")
    .slice(0, 64);

export type Call =
  | { kind: "submit"; definition: LedgerDefinitionId; payload: JsonObject }
  | {
      kind: "answer";
      operation: string;
      digest: string;
      decision: LedgerDecision;
    };

/** What the fake port does for one call: settle with a result, settle as
 * refused, or reject as the host would. */
export type FakeAnswer =
  | { settle: JsonObject }
  | { refuse: string }
  | { fail: LedgerFailure }
  | { outcome: LedgerOutcome };

/** A ledger port that answers each call from `answer` and records it. Only
 * the calls the models make are answered; the rest are not used. */
export function fakePort(answer: (call: Call, at: number) => FakeAnswer): {
  port: LedgerPort;
  calls: Call[];
} {
  const calls: Call[] = [];
  let operations = 0;
  const settle = async (call: Call): Promise<LedgerOutcome> => {
    calls.push(call);
    const found = answer(call, calls.length - 1);
    operations += 1;
    const operation_id = `op-${operations}`;
    if ("fail" in found) throw found.fail;
    if ("outcome" in found) return found.outcome;
    if ("refuse" in found)
      return {
        kind: "refused",
        operation_id,
        revision: 3,
        reason: found.refuse,
        detail: null,
      };
    return { kind: "settled", operation_id, revision: 3, result: found.settle };
  };
  const unused = () => Promise.reject(new Error("not used by the models"));
  const port: LedgerPort = {
    submit: (definition, payload) =>
      settle({
        kind: "submit",
        definition,
        payload: payload as JsonObject,
      }) as never,
    answer: (operation, digest, decision) =>
      settle({ kind: "answer", operation, digest, decision }),
    observe: unused,
    review: unused,
    cancel: unused,
    pickFiles: unused,
    saveFile: unused,
    forgetFiles: unused,
    observeDrops: unused,
    changeOwnAccount: unused,
  };
  return { port, calls };
}

export const PROFILE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

/** A list page as `ledger.list` answers it for `rows` of `total`. */
export function listPage(
  rows: LedgerRow[],
  total: number,
  offset: number,
  limit: number,
): JsonObject {
  return {
    profile_id: PROFILE,
    rows: rows as unknown as JsonObject[],
    total,
    truncated: offset > 0 || offset + limit < total,
    offset,
    limit,
    by_group: false,
  };
}
