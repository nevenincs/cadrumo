// The scenario host's ledger: the ledger port answered from the synthetic
// ledger in ./fixtures/ledger.ts, held in this page's memory. It follows the
// registered contracts the page relies on: the list's order of filter, group
// selection, sort, group partition and page; a bulk classification that needs
// a classification on every row; a new id when a movement's amount,
// description, date or own account changes; refusals for rows a finalized
// revision cites; idempotency keys on add; and a model review answered only
// with the digest of the review the page read. What it answers is design and
// test evidence only. Its call lines name a definition, never a value.

import {
  LEDGER_PAYLOAD_LIMIT,
  LEDGER_UPDATE_FIELDS,
  isLedgerDefinition,
  type CatalogueInvoice,
  type FilePicks,
  type FilePurpose,
  type FileToken,
  type JsonObject,
  type JsonValue,
  type LedgerDefinitionId,
  type LedgerDropSignal,
  type LedgerErrorDetail,
  type LedgerFailure,
  type LedgerFailureCode,
  type LedgerOutcome,
  type LedgerPort,
  type LedgerReview,
  type LedgerResult,
  type LedgerReviewStatus,
  type LedgerRow,
  type LedgerSortField,
  type LedgerTransaction,
  type LedgerUpdateField,
  type PublicPeriod,
} from "../shell/ledger";
import {
  LEDGER_FIXTURE_PROFILE_ID,
  LEDGER_FIXTURE_TODAY,
  cents,
  emptyLedger,
  fixtureLedger,
  hex64,
  ledgerOfRows,
  largeLedger,
  money,
  movementId,
  type FixtureAccount,
  type FixtureLedger,
  type FixtureMovement,
} from "./fixtures/ledger";
import { ledgerClassOf } from "./ledgerClassesFixture";
import { evidenceOperations } from "./ledgerEvidenceFixture";
import {
  InvoiceRequestInvalid,
  InvoiceStopped,
  InvoiceUnsettled,
  invoiceOperations,
} from "./ledgerInvoiceFixture";
import {
  MovementActionInvalid,
  MovementActionStopped,
  movementActionOperations,
} from "./ledgerMovementActionFixture";
import {
  SetupRequestInvalid,
  SetupStopped,
  setupOperations,
} from "./ledgerSetupFixture";

/** The longest request line, in bytes, the relay takes: the host refuses a
 * longer one before it is written. */
const REQUEST_LINE_LIMIT = 16_383;
/** The longest reply, in bytes of compact JSON, the host takes from the
 * relay; one longer is lost. */
const REPLY_LIMIT = 16 * 1024 * 1024;
/** What the host puts around a payload on the request line, with the room of
 * the request id it adds. */
const LINE_FRAME = {
  action: "operation_submit",
  subject_ref: "profile:00000000-0000-4000-8000-000000000000",
};
const REQUEST_ID_ROOM = 14 + 36 + 1 + 1;
const encoder = new TextEncoder();

/** Whether the host refuses the request before sending it: the payload's
 * characters of compact JSON, or the request line's bytes. */
export function tooLarge(definition: string, request: JsonObject): boolean {
  if (JSON.stringify(request).length > LEDGER_PAYLOAD_LIMIT) return true;
  const line = JSON.stringify({
    action: LINE_FRAME.action,
    definition_id: definition,
    subject_ref: LINE_FRAME.subject_ref,
    payload: request,
  });
  return encoder.encode(line).length + REQUEST_ID_ROOM > REQUEST_LINE_LIMIT;
}

/** Whether a reply is over the host's bound. */
export function replyTooLarge(result: JsonValue): boolean {
  const text = JSON.stringify(result);
  // Three bytes bound a character here, so only a long text is counted.
  return (
    text.length * 3 > REPLY_LIMIT && encoder.encode(text).length > REPLY_LIMIT
  );
}

/** How the scenario's ledger answers. */
export const LEDGER_SHAPES = [
  "fixture",
  "empty",
  "refused",
  "unknown",
  "unavailable",
  "slow",
  "large",
  "documents",
  // The `documents` ledger on a computer whose local AI is not set up.
  "reader_missing",
] as const;
export type LedgerShape = (typeof LEDGER_SHAPES)[number];

/** Delay added to every answer of the `slow` shape. */
const SLOW_MS = 4000;

declare global {
  interface Window {
    /** Controls for what the scenario's ledger cannot get from a person. */
    __scenarioLedger?: {
      /** Drops files with these names on the window. */
      drop(names: string[]): void;
      /** Changes every pending review, as a model reading again would. */
      changeReviews(): void;
      /** Changes a file's bytes, as editing it on disk between a preview
       * and an import would. */
      changeFile(name: string): void;
      /** Answers the next writes so, one each: `unknown` lands the write
       * and leaves its settlement unobserved, `saved_unread` lands it and
       * loses its answer, `refused` refuses it whole and writes nothing. */
      nextWrites(outcomes: ("unknown" | "saved_unread" | "refused")[]): void;
      /** Answers the next `count` reads of `definition` as unavailable,
       * as a runtime that did not answer them; with `where`, only reads
       * whose request carries each of its values. */
      nextReads(definition: string, count: number, where?: JsonObject): void;
      /** Changes a stored movement's field, as another window saving it
       * would. */
      editElsewhere(id: string, field: string, value: string | null): void;
    };
  }
}

/** How often each made-up file was changed since the page loaded: the
 * made-up computer's, shared by every ledger the page makes. */
const edits = new Map<string, number>();
type Controls = NonNullable<Window["__scenarioLedger"]>;
/** Every ledger the page made. The development entry may make more than one
 * for one run, and the controls reach the one the page uses among them. */
const ledgers = new Set<Omit<Controls, "changeFile">>();

type Options = {
  say: (call: string) => void;
  wait: () => Promise<void>;
  signedIn: () => boolean;
  shape: LedgerShape;
};

const PURPOSE_KINDS: Record<FilePurpose, readonly string[]> = {
  bank_statements: ["csv", "txt", "tsv", "xlsx", "xls", "ofx", "qfx", "pdf"],
  invoice_books: ["csv", "tsv", "xlsx", "xlsm", "xls"],
  documents: [
    "pdf",
    "xml",
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "webp",
    "heic",
    "heif",
  ],
  export: ["csv", "jsonl", "xlsx"],
};
/** What each dialog of the made-up computer offers. */
const PICKABLE: Record<Exclude<FilePurpose, "export">, string[]> = {
  bank_statements: [
    "extracto-cuenta-estudio-2026-10.csv",
    "extracto-cuenta-personal-2026-10.ofx",
    "movimientos-tarjeta.pdf",
    "notas-del-banco.docx",
  ],
  invoice_books: ["libro-facturas-recibidas-2026.xlsx"],
  documents: [
    "ticket-gasolinera-ruta7.jpg",
    "factura-papeleria-trazo.pdf",
    "factura-estudio-lumen.xml",
  ],
};
/** What each made-up statement holds: the own account its rows name, if
 * any, how many rows it has, how many fall on the day and amount of a
 * movement already in the ledger, and whether its dates leave a gap. A name
 * not listed reads as a short statement that names no account. */
type Statement = {
  names: string | null;
  rows: number;
  duplicates: number;
  gap: boolean;
  readable: boolean;
};
const STATEMENTS: Record<string, Statement> = {
  "extracto-cuenta-estudio-2026-10.csv": {
    names: null,
    rows: 14,
    duplicates: 2,
    gap: false,
    readable: true,
  },
  "extracto-cuenta-personal-2026-10.ofx": {
    names: "acc-02",
    rows: 9,
    duplicates: 0,
    gap: true,
    readable: true,
  },
  "movimientos-tarjeta.pdf": {
    names: null,
    rows: 0,
    duplicates: 0,
    gap: false,
    readable: false,
  },
};
const STATEMENT: Statement = {
  names: null,
  rows: 6,
  duplicates: 0,
  gap: false,
  readable: true,
};
/** The rows of each made-up invoice book that its import refuses. */
const BOOK_REFUSALS: Record<
  string,
  { row_number: number; field: string; reason: string }[]
> = {
  "libro-facturas-recibidas-2026.xlsx": [
    {
      row_number: 5,
      field: "counterparty_nif",
      reason: "B0000004 is not a valid tax identification number.",
    },
  ],
};
const UPDATE_REQUIRED: readonly LedgerUpdateField[] = [
  "booked_date",
  "amount",
  "currency",
  "direction",
  "description",
  "notes",
];
const DIRECTIONS = ["INCOMING", "OUTGOING", "INTERNAL_TRANSFER"];
const DECIDED = ["BUSINESS", "PERSONAL", "MIXED"];
const CLASSIFICATIONS = [
  ...DECIDED,
  "NOT_YET_PROCESSED",
  "PROCESSED_UNCLASSIFIED",
  "SKIPPED_BY_RULE",
  "FAILED_VALIDATION",
  "REVIEWED_EXCLUDED",
];
const BULK_COLUMNS = [
  "transaction_id",
  "classification",
  "category_id",
  "business_pct",
  "usage_ratio_id",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "iva_category",
  "irpf_category",
  "notes",
];
const OWN_ACCOUNT_SECRETS = [
  "iban",
  "swift_bic",
  "bank_name",
  "bank_address",
  "bank_city",
  "bank_country_code",
];
const SEALED_MESSAGE =
  "A finalized Modelo 303 revision for 2026 1T cites this movement; correct it through an amendment.";

/** A rejected call, shaped as the host rejects one: its code, operation and
 * reason are the error's own fields, as `ledgerFailure` reads them. */
class Refusal extends Error {
  readonly code: LedgerFailureCode;
  readonly operation_id: string | null;
  readonly reason?: string;
  constructor(readonly failure: LedgerFailure) {
    super(failure.code);
    this.code = failure.code;
    this.operation_id = failure.operation_id;
    if (failure.reason !== undefined) this.reason = failure.reason;
  }
}
const reject = (
  code: LedgerFailureCode,
  extra: Partial<LedgerFailure> = {},
): never => {
  throw new Refusal({ code, operation_id: null, ...extra });
};
/** A request its registered contract would not decode. */
const invalid = () => reject("refused", { reason: "invalid" });

const text = (value: JsonValue | undefined) =>
  typeof value === "string" ? value : null;
const AMOUNT = /^\d{1,12}(\.\d{1,2})?$/;
const FRACTION = /^(0(\.\d{1,4})?|1(\.0{1,4})?)$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
// Single update and classify refuse a decimal that is not in its shortest
// spelling ("40.00", "0.50"), as their request models do; add and the bulk
// re-render what they read.
const shortest = (value: string) => !/\.(\d*0)?$/.test(value);

function reviewStatus(classification: string): LedgerReviewStatus {
  if (classification === "NOT_YET_PROCESSED") return "pending";
  if (classification === "SKIPPED_BY_RULE") return "skipped";
  if (classification === "REVIEWED_EXCLUDED") return "excluded";
  return "reviewed";
}
const row = (movement: FixtureMovement): LedgerRow => ({
  transaction: { ...movement.transaction },
  review_status: reviewStatus(movement.transaction.business_classification),
  group_label: movement.group_label,
  own_account_id: movement.own_account_id,
});

function periodSpan(year: number, code: string): [string, string] | null {
  const quarter = /^([1-4])[TP]$/.exec(code);
  const month = /^(0[1-9]|1[0-2])$/.exec(code);
  const pad = (value: number) => String(value).padStart(2, "0");
  if (quarter) {
    const first = (Number(quarter[1]) - 1) * 3 + 1;
    const last = new Date(Date.UTC(year, first + 2, 0)).getUTCDate();
    return [
      `${year}-${pad(first)}-01`,
      `${year}-${pad(first + 2)}-${pad(last)}`,
    ];
  }
  if (month) {
    const at = Number(month[1]);
    const last = new Date(Date.UTC(year, at, 0)).getUTCDate();
    return [`${year}-${pad(at)}-01`, `${year}-${pad(at)}-${pad(last)}`];
  }
  if (code === "0A") return [`${year}-01-01`, `${year}-12-31`];
  return null;
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
      if (!CLASSIFICATIONS.includes(wanted)) return invalid();
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
      if (!DIRECTIONS.includes(wanted)) return invalid();
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
const compare = (left: string, right: string) =>
  left < right ? -1 : left > right ? 1 : 0;

/** Filter, then group selection, then sort, then group partition, then
 * the page: the product's order. */
function list(ledger: FixtureLedger, request: JsonObject): JsonObject {
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
function resolve(ledger: FixtureLedger, prefix: JsonValue | undefined) {
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
class Stopped extends Error {
  constructor(readonly reason: string) {
    super(reason);
  }
}

function inPeriod(movement: FixtureMovement, period: JsonValue | undefined) {
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
function issues(ledger: FixtureLedger, period: JsonValue | undefined) {
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
          reason: "missing_eur_tax_substrate",
          detail: "No euro value.",
        });
    }
  }
  return found;
}

export function ledgerFixture(options: Options): LedgerPort {
  const { say, signedIn, shape } = options;
  // `ledgerRows` in the page's address sets how many movements the fourth
  // quarter of 2026 holds, for measuring the grid at any size.
  const rows = Math.trunc(
    Number(new URLSearchParams(window.location.search).get("ledgerRows")),
  );
  const ledger =
    shape === "empty"
      ? emptyLedger()
      : rows > 0
        ? ledgerOfRows(rows)
        : shape === "large"
          ? largeLedger()
          : fixtureLedger();
  let clock = 0;
  const now = () => {
    clock += 1;
    return `${LEDGER_FIXTURE_TODAY}T12:${String(Math.floor(clock / 60) % 60).padStart(2, "0")}:${String(clock % 60).padStart(2, "0")}Z`;
  };
  let operations = 0;
  const outcomes = new Map<string, LedgerOutcome>();
  type Pending = {
    definition: LedgerDefinitionId;
    request: JsonObject;
    transaction: string;
    version: number;
    shown: string | null;
  };
  const reviews = new Map<string, Pending>();
  // How the next writes are answered, where a scenario asked.
  const queued: ("unknown" | "saved_unread" | "refused")[] = [];
  // How many of the next reads of a definition answer nothing.
  const failingReads = new Map<string, number>();
  // Reads that fail only where their request carries these values.
  const failingWhere: {
    definition: string;
    where: JsonObject;
    count: number;
  }[] = [];
  const files = new Map<FileToken, { name: string; purpose: FilePurpose }>();
  const bytesOf = (name: string) =>
    hex64(`bytes:${name}:${edits.get(name) ?? 0}`);
  const drops = new Set<(signal: LedgerDropSignal) => void>();
  let dropPurpose: Exclude<FilePurpose, "export"> = "bank_statements";

  const answer = async () => {
    await options.wait();
    if (shape === "slow")
      await new Promise((done) => window.setTimeout(done, SLOW_MS));
    if (shape === "unavailable") reject("unavailable");
    if (!signedIn()) reject("not_signed_in");
  };
  const nextOperation = () => {
    operations += 1;
    return hex64(`operation:${operations}`);
  };
  const settle = (operation: string, result: JsonValue): LedgerOutcome => {
    const outcome: LedgerOutcome = {
      kind: "settled",
      operation_id: operation,
      revision: 3,
      result: result as JsonObject,
    };
    outcomes.set(operation, outcome);
    return outcome;
  };
  const events = () => [hex64(`event:${now()}`)];

  const issue = (name: string, purpose: FilePurpose): FileToken => {
    const token =
      `file-${hex64(`file:${files.size}:${name}`).slice(0, 32)}` as FileToken;
    files.set(token, { name, purpose });
    return token;
  };
  const take = (names: string[], purpose: FilePurpose): FilePicks => {
    const picks: FilePicks = { files: [], refused: 0 };
    for (const name of names) {
      const kind = name.split(".").pop()?.toLowerCase() ?? "";
      if (PURPOSE_KINDS[purpose].includes(kind))
        picks.files.push({
          token: issue(name, purpose),
          name,
          bytes: 2048 + name.length * 97,
        });
      else picks.refused += 1;
    }
    return picks;
  };
  const fileOf = (token: JsonValue | undefined, purpose: FilePurpose) => {
    if (typeof token !== "string") return invalid();
    const found = files.get(token as FileToken);
    if (!found) return reject("file_unavailable");
    if (found.purpose !== purpose) return invalid();
    return found;
  };

  ledgers.add({
    drop(names) {
      if (drops.size === 0) return;
      const picks = take(names, dropPurpose);
      drops.forEach((listener) => {
        listener({ kind: "over" });
        listener({ kind: "dropped", ...picks });
      });
    },
    changeReviews() {
      reviews.forEach((pending) => {
        pending.version += 1;
      });
    },
    nextWrites(next) {
      queued.push(...next);
    },
    nextReads(definition, count, where) {
      if (where) failingWhere.push({ definition, where, count });
      else
        failingReads.set(
          definition,
          (failingReads.get(definition) ?? 0) + count,
        );
    },
    editElsewhere(id, field, value) {
      const movement = transactionOf(id);
      if (!movement) return;
      (movement.transaction as unknown as Record<string, string | null>)[
        field
      ] = field === "notes" || field === "counterparty" ? (value ?? "") : value;
      movement.transaction.modified_at = now();
    },
  });
  window.__scenarioLedger = {
    drop: (names) => ledgers.forEach((made) => made.drop(names)),
    changeReviews: () => ledgers.forEach((made) => made.changeReviews()),
    nextWrites: (next) => ledgers.forEach((made) => made.nextWrites(next)),
    nextReads: (definition, count, where) =>
      ledgers.forEach((made) => made.nextReads(definition, count, where)),
    editElsewhere: (id, field, value) =>
      ledgers.forEach((made) => made.editElsewhere(id, field, value)),
    changeFile(name) {
      edits.set(name, (edits.get(name) ?? 0) + 1);
    },
  };

  const transactionOf = (id: string) =>
    ledger.movements.find(
      (movement) => movement.transaction.transaction_id === id,
    );

  function update(request: JsonObject): JsonObject {
    const fields = request.patch_fields;
    const patch = request.patch;
    if (
      !Array.isArray(fields) ||
      fields.length < 1 ||
      fields.length > 14 ||
      new Set(fields).size !== fields.length ||
      typeof patch !== "object" ||
      patch === null ||
      Array.isArray(patch)
    )
      return invalid();
    const values = patch as JsonObject;
    for (const field of fields) {
      if (
        typeof field !== "string" ||
        !(LEDGER_UPDATE_FIELDS as readonly string[]).includes(field)
      )
        return invalid();
      if (
        (UPDATE_REQUIRED as string[]).includes(field) &&
        (values[field] ?? null) === null
      )
        return invalid();
    }
    const movement = resolve(ledger, request.transaction_id);
    const refused = (message: string): JsonObject => ({
      outcome: "validation_error",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      source_transaction_id: null,
      transaction: null,
      review_status: null,
      bucket_event_ids: [],
      group_label: null,
      own_account_id: null,
      validation_messages: [message],
    });
    if (movement.transaction.lifecycle_state !== "ACTIVE")
      return refused("Only an active movement can be updated.");
    if (movement.sealed) return refused(SEALED_MESSAGE);
    const next: LedgerTransaction = { ...movement.transaction };
    let group = movement.group_label;
    let account = movement.own_account_id;
    for (const field of fields as LedgerUpdateField[]) {
      const value = text(values[field]);
      if (field === "amount") {
        if (!value || !AMOUNT.test(value) || !shortest(value))
          return refused("The amount is not a canonical decimal.");
        next.amount = money(cents(value));
      } else if (field === "booked_date" || field === "value_date") {
        if (value !== null && !DATE.test(value))
          return refused("The date is not a calendar day.");
        next[field] = value as string;
      } else if (field === "direction") {
        if (!value || !DIRECTIONS.includes(value.toUpperCase()))
          return refused("Unknown direction.");
        next.direction = value.toUpperCase();
      } else if (field === "currency") {
        if (!value || !/^[A-Z]{3}$/.test(value))
          return refused("Unknown currency.");
        next.currency = value;
      } else if (field === "group_label") {
        group = value === null || value.trim() === "" ? null : value.trim();
      } else if (field === "own_account_id") {
        if (
          value !== null &&
          !ledger.accounts.some((own) => own.own_account_id === value)
        )
          return refused("No own account has that id.");
        account = value;
      } else if (field === "counterparty") {
        next.counterparty = value ?? "";
      } else if (field === "description" || field === "notes") {
        next[field] = value ?? "";
      } else {
        next[field] = value;
      }
    }
    next.date = next.value_date ?? next.booked_date;
    const changed =
      JSON.stringify(next) !== JSON.stringify(movement.transaction) ||
      group !== movement.group_label ||
      account !== movement.own_account_id;
    if (!changed)
      return refused(
        "manual ledger update must change at least one ledger field",
      );
    const source = movement.transaction.transaction_id;
    // The id is the content address of these facts: changing one re-keys.
    if (
      next.amount !== movement.transaction.amount ||
      next.description !== movement.transaction.description ||
      next.date !== movement.transaction.date ||
      account !== movement.own_account_id
    )
      next.transaction_id = movementId({
        date: next.date,
        amount: next.amount,
        description: next.description,
        own_account_id: account,
        salt: source,
      });
    next.modified_at = now();
    movement.transaction = next;
    movement.group_label = group;
    movement.own_account_id = account;
    return {
      outcome: "updated",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      source_transaction_id: source,
      transaction: { ...next } as unknown as JsonValue,
      review_status: reviewStatus(next.business_classification),
      bucket_event_ids: events(),
      group_label: group,
      own_account_id: account,
      validation_messages: [],
    };
  }

  /** One row's classification, shared by the single and bulk writes. */
  function classifyRow(
    movement: FixtureMovement,
    values: Record<string, string | null>,
    by: string,
  ): "applied" | "skipped" {
    const next: LedgerTransaction = { ...movement.transaction };
    for (const [field, value] of Object.entries(values)) {
      if (field === "classification")
        next.business_classification = value ?? next.business_classification;
      else if (field === "notes") next.notes = value ?? "";
      else if (field in next)
        (next as unknown as Record<string, string | null>)[field] = value;
    }
    if (next.business_classification === "PERSONAL") {
      next.category_id = null;
      next.business_pct = null;
    }
    if (JSON.stringify(next) === JSON.stringify(movement.transaction))
      return "skipped";
    next.classified_by = by;
    next.classified_at = now();
    next.classification_reason = by;
    next.modified_at = next.classified_at;
    movement.transaction = next;
    return "applied";
  }
  const checkDecision = (classification: string | null, pct: string | null) => {
    if (!classification || !DECIDED.includes(classification)) return invalid();
    if ((classification === "MIXED") !== (pct !== null)) return invalid();
    if (pct !== null && (!FRACTION.test(pct) || !shortest(pct)))
      return invalid();
  };

  function classify(request: JsonObject): JsonObject {
    const fields = request.patch_fields;
    const patch = request.patch as JsonObject | undefined;
    if (
      !Array.isArray(fields) ||
      !fields.includes("business_classification") ||
      !patch
    )
      return invalid();
    const classification = text(patch.business_classification);
    const pct = text(patch.business_pct);
    checkDecision(classification, pct);
    const rate = text(patch.iva_rate);
    if (rate !== null && (!FRACTION.test(rate) || !shortest(rate)))
      return invalid();
    const movement = resolve(ledger, request.transaction_id);
    if (movement.sealed || movement.transaction.lifecycle_state !== "ACTIVE")
      return {
        outcome: "validation_error",
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        transaction: null,
        deduction_fact_kind: null,
        investment_asset_id: null,
        review_status: null,
        bucket_event_ids: [],
        validation_kind: "input",
        validation_messages: [
          movement.sealed
            ? SEALED_MESSAGE
            : "Only an active movement can be classified.",
        ],
      };
    const values: Record<string, string | null> = {};
    for (const field of fields as string[]) {
      if (field === "m210_income_classification") continue;
      values[field === "business_classification" ? "classification" : field] =
        text(patch[field]);
    }
    classifyRow(movement, values, "operator");
    const transaction = movement.transaction;
    return {
      outcome: "classified",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      transaction: { ...transaction } as unknown as JsonValue,
      deduction_fact_kind: null,
      investment_asset_id: null,
      review_status: reviewStatus(transaction.business_classification),
      bucket_event_ids: events(),
      validation_kind: "none",
      validation_messages: [],
    };
  }

  function bulk(request: JsonObject): JsonObject {
    const csv = text(request.csv_text);
    if (csv === null) return invalid();
    const refused = (message: string): JsonObject => ({
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      outcome: "validation_error",
      result: null,
      validation_messages: [message],
    });
    const lines = parseCsv(csv);
    const header = lines.shift() ?? [];
    if (
      !header.includes("transaction_id") ||
      !header.includes("classification")
    )
      return refused(
        "The CSV needs transaction_id and classification columns.",
      );
    const unknown = header.find((column) => !BULK_COLUMNS.includes(column));
    if (unknown !== undefined)
      return refused(
        "The CSV names a column bulk classification does not take.",
      );
    const failures: JsonValue[] = [];
    let applied = 0;
    let skipped = 0;
    lines.forEach((cells, index) => {
      const value = (column: string) => {
        const at = header.indexOf(column);
        const cell = at < 0 ? "" : (cells[at] ?? "");
        return cell.trim() === "" ? null : cell.trim();
      };
      const id = value("transaction_id") ?? "";
      const fail = (reason: string) =>
        failures.push({ row_index: index, transaction_id: id, reason });
      if (cells.length > header.length)
        return fail("The row has more cells than the header.");
      const classification = value("classification")?.toUpperCase() ?? null;
      const pct = value("business_pct");
      if (!classification) return fail("Every row needs a classification.");
      if (
        !DECIDED.includes(classification) ||
        (classification === "MIXED") !== (pct !== null)
      )
        return fail(
          "The classification is not one a person decides, or its business share is missing.",
        );
      let movement: FixtureMovement;
      try {
        movement = resolve(ledger, id);
      } catch {
        return fail("No single movement has that id.");
      }
      if (movement.transaction.lifecycle_state !== "ACTIVE")
        return fail("Only an active movement can be classified.");
      if (movement.sealed) return fail(SEALED_MESSAGE);
      const values: Record<string, string | null> = { classification };
      for (const column of header)
        if (
          !["transaction_id", "classification"].includes(column) &&
          value(column) !== null
        )
          values[column] = value(column);
      if (classifyRow(movement, values, "operator:bulk") === "applied")
        applied += 1;
      else skipped += 1;
    });
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      outcome: "classified",
      result: {
        total: lines.length,
        applied,
        skipped,
        failures,
        bucket_event_ids: applied ? events() : [],
      },
      validation_messages: [],
    };
  }

  function add(request: JsonObject): JsonObject {
    const booked = text(request.booked_date);
    const amount = text(request.amount);
    const direction = text(request.direction)?.toUpperCase() ?? null;
    const description = text(request.description);
    if (!booked || !DATE.test(booked) || !amount || !direction || !description)
      return invalid();
    const refused = (message: string): JsonObject => ({
      outcome: "validation_error",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      transaction: null,
      review_status: null,
      bucket_event_ids: [],
      advisory_input_classification: null,
      advisory_input_classification_inert: false,
      advisory_sector_id: null,
      advisory_sector_unmatched: false,
      validation_code: "invalid_command",
      validation_messages: [message],
    });
    if (!AMOUNT.test(amount))
      return refused("The amount is not a canonical decimal.");
    if (!DIRECTIONS.includes(direction)) return refused("Unknown direction.");
    const classification =
      text(request.business_classification) ?? "NOT_YET_PROCESSED";
    const key = text(request.idempotency_key);
    const date = text(request.value_date) ?? booked;
    const account = text(request.own_account_id);
    const facts: LedgerTransaction = {
      transaction_id: "",
      date,
      booked_date: booked,
      value_date: text(request.value_date),
      amount: money(cents(amount)),
      currency: text(request.currency) ?? "EUR",
      direction,
      counterparty: text(request.counterparty) ?? "",
      description,
      business_classification: classification,
      business_pct: text(request.business_pct),
      category_id: text(request.category_id),
      taxable_base: text(request.taxable_base),
      iva_rate: text(request.iva_rate),
      iva_amount: text(request.iva_amount),
      iva_category: text(request.iva_category),
      counterparty_country: text(request.counterparty_country),
      counterparty_identification_state: text(
        request.counterparty_identification_state,
      ),
      irpf_category: text(request.irpf_category),
      m210_income_classification: null,
      usage_ratio_id: text(request.usage_ratio_id),
      prorrata_reference: text(request.prorrata_reference),
      purchase_invoice_evidence_id: text(request.purchase_invoice_evidence_id),
      invoice_id: null,
      attachment_ids: [],
      notes: text(request.notes) ?? "",
      lifecycle_state: "ACTIVE",
      classified_by: classification === "NOT_YET_PROCESSED" ? "" : "operator",
      classified_at: null,
      classification_reason: "",
      classification_confidence: null,
      source_jurisdiction: text(request.source_jurisdiction),
      value_in_eur: null,
      fx_rate: null,
      created_at: "",
      modified_at: "",
    };
    const result = (
      transaction: LedgerTransaction,
      written: boolean,
    ): JsonObject => ({
      outcome: "created",
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      transaction: { ...transaction } as unknown as JsonValue,
      review_status: reviewStatus(transaction.business_classification),
      bucket_event_ids: written ? events() : [],
      advisory_input_classification: null,
      advisory_input_classification_inert: false,
      advisory_sector_id: null,
      advisory_sector_unmatched: false,
      validation_code: null,
      validation_messages: [],
    });
    if (key !== null) {
      const stored = ledger.movements.find(
        (movement) => movement.idempotency_key === key,
      );
      if (stored) {
        const same = (Object.keys(facts) as (keyof LedgerTransaction)[])
          .filter(
            (field) =>
              ![
                "transaction_id",
                "created_at",
                "modified_at",
                "classified_at",
              ].includes(field),
          )
          .every(
            (field) =>
              JSON.stringify(facts[field]) ===
              JSON.stringify(stored.transaction[field]),
          );
        // A retry of the same add returns the row it stored and writes nothing.
        return same
          ? result(stored.transaction, false)
          : refused("application.ledger.errors.idempotency_key_conflict");
      }
    }
    const created = now();
    facts.transaction_id = movementId({
      date,
      amount: facts.amount,
      description,
      own_account_id: account,
      salt: key ?? created,
    });
    facts.created_at = created;
    facts.modified_at = created;
    if (classification !== "NOT_YET_PROCESSED") facts.classified_at = created;
    ledger.movements.push({
      transaction: facts,
      group_label: null,
      own_account_id: account,
      import_batch_id: null,
      issue: null,
      sealed: false,
      llm_rejected: false,
      idempotency_key: key,
    });
    return result(facts, true);
  }

  function status(request: JsonObject): JsonObject {
    const period = request.period ?? null;
    const rows = ledger.movements.filter((movement) =>
      inPeriod(movement, period),
    );
    const sum = (direction: string) =>
      money(
        rows
          .filter(
            (movement) =>
              movement.transaction.direction === direction &&
              ["BUSINESS", "MIXED"].includes(
                movement.transaction.business_classification,
              ),
          )
          .reduce(
            (total, movement) =>
              total +
              cents(
                movement.transaction.taxable_base ??
                  movement.transaction.amount,
              ),
            0,
          ),
      );
    const found = issues(ledger, period);
    const by = (state: LedgerReviewStatus) =>
      rows.filter(
        (movement) =>
          reviewStatus(movement.transaction.business_classification) === state,
      ).length;
    const income = sum("INCOMING");
    const expense = sum("OUTGOING");
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      period: period as JsonValue,
      business_income_total: income,
      business_expense_total: expense,
      business_net_total: money(cents(income) - cents(expense)),
      total_count: rows.length,
      active_count: rows.filter(
        (movement) => movement.transaction.lifecycle_state === "ACTIVE",
      ).length,
      archived_count: 0,
      stashed_count: 0,
      split_count: 0,
      pending_review_count: by("pending"),
      reviewed_count: by("reviewed"),
      skipped_count: by("skipped"),
      checked_transaction_count: rows.length,
      readiness_issue_count: found.length,
      unconverted_currency_count: rows.filter(
        (movement) =>
          movement.transaction.currency !== "EUR" &&
          !movement.transaction.value_in_eur,
      ).length,
      ready: rows.length === 0 ? null : found.length === 0,
      readiness_issues: found.map((issue) => ({
        ...issue,
        transaction_present: true,
        business_classification:
          transactionOf(issue.transaction_id)?.transaction
            .business_classification ?? null,
        category_id: null,
        taxable_base: null,
        iva_rate: null,
        iva_amount: null,
      })),
      stale_filings: setupWork.staleFilings(period),
    };
  }

  function preflight(request: JsonObject): JsonObject {
    const period = request.period;
    if (!period || typeof period !== "object" || Array.isArray(period))
      return invalid();
    const found = issues(ledger, period);
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      period,
      bucket_id: LEDGER_FIXTURE_PROFILE_ID,
      checked_transaction_count: ledger.movements.filter((movement) =>
        inPeriod(movement, period),
      ).length,
      issues: found,
      ready: found.length === 0,
    };
  }

  /** The movements already in the ledger that a statement's first rows fall
   * on the day and amount of, chosen once from October 2026. */
  let duplicateTargets: FixtureMovement[] | null = null;
  const targets = () =>
    (duplicateTargets ??= ledger.movements
      .filter(
        (movement) =>
          movement.transaction.date.startsWith("2026-10-") &&
          movement.transaction.lifecycle_state === "ACTIVE",
      )
      .sort((left, right) =>
        compare(left.transaction.date, right.transaction.date),
      )
      .slice(0, 4));

  /** One statement's rows as the product reads them, each bound to `bound`. */
  function statementRows(name: string, bound: string | null) {
    const spec = STATEMENTS[name] ?? STATEMENT;
    const stem = name.replace(/\.[a-z0-9]+$/i, "").toUpperCase();
    return Array.from({ length: spec.rows }, (_, at) => {
      const target = at < spec.duplicates ? targets()[at] : undefined;
      const dayOfMonth = spec.gap && at > 3 ? 18 + (at % 9) : 1 + (at % 9);
      const date = target
        ? target.transaction.date
        : `2026-10-${String(dayOfMonth).padStart(2, "0")}`;
      const amount = target
        ? target.transaction.amount
        : money(1500 + at * 731 + stem.length * 13);
      const description = `${target ? "CARGO" : "MOVIMIENTO"} ${stem.slice(0, 18)} ${String(at + 1).padStart(2, "0")}`;
      const direction = target
        ? target.transaction.direction
        : at % 4 === 0
          ? "INCOMING"
          : "OUTGOING";
      return {
        id: movementId({
          date,
          amount,
          description,
          own_account_id: bound,
          salt: name,
        }),
        date,
        amount,
        description,
        direction,
      };
    });
  }

  /** A bank statement import, as the product's public result tells it: a
   * row already in the ledger is skipped, a row on the day and amount of
   * another is imported and listed as a likely duplicate, and each file
   * read names its digest by its place in the request. */
  function importStatement(request: JsonObject): JsonObject {
    const tokens = request.files;
    if (!Array.isArray(tokens) || tokens.length === 0) return invalid();
    const chosen = tokens.map((token) => fileOf(token, "bank_statements"));
    const expected = request.expected_source_sha256 ?? null;
    if (
      expected !== null &&
      (!Array.isArray(expected) || expected.length !== chosen.length)
    )
      return invalid();
    const account = text(request.own_account_id);
    if (
      account !== null &&
      !ledger.accounts.some((known) => known.own_account_id === account)
    )
      throw new Stopped("ERROR_TRANSACTION_VALIDATION");
    const period = (request.period ?? null) as PublicPeriod | null;
    const span = period ? periodSpan(period.filing_year, period.code) : null;
    if (period && !span) return invalid();
    const dryRun = request.dry_run === true;
    const verify = request.verify === true;
    const profile = LEDGER_FIXTURE_PROFILE_ID;
    const ref = (id: string): JsonObject => ({
      bucket_id: profile,
      transaction_id: id,
    });
    const refused: JsonObject[] = [];
    const digests: JsonObject[] = [];
    const imported: JsonObject[] = [];
    const skipped: JsonObject[] = [];
    const duplicates: JsonObject[] = [];
    const diagnostics: JsonObject[] = [];
    const validations: JsonObject[] = [];
    const batches: string[] = [];
    let rows = 0;
    chosen.forEach((file, index) => {
      const spec = STATEMENTS[file.name] ?? STATEMENT;
      const sha = bytesOf(file.name);
      // Apply takes exactly the files the preview read, unchanged since.
      if (Array.isArray(expected) && expected[index] !== sha) {
        refused.push({ file_name: file.name, reason_code: "source_changed" });
        return;
      }
      if (!spec.readable) {
        refused.push({
          file_name: file.name,
          reason_code: "transaction_validation",
        });
        return;
      }
      // A chosen account that the file's own rows contradict refuses it.
      if (account !== null && spec.names !== null && spec.names !== account) {
        refused.push({
          file_name: file.name,
          reason_code: "own_account_mismatch",
        });
        return;
      }
      const named = ledger.accounts.some(
        (known) => known.own_account_id === spec.names,
      )
        ? spec.names
        : null;
      const bound = account ?? named;
      const read = statementRows(file.name, bound).filter(
        (row) => !span || (row.date >= span[0] && row.date <= span[1]),
      );
      digests.push({ file_index: index, sha256: sha });
      validations.push({ valid: true, warning_count: 0, encoding: "utf-8" });
      rows += read.length;
      const days = new Set<string>();
      const fresh: string[] = [];
      for (const row of read) {
        const day = `${row.date}:${row.amount}`;
        if (transactionOf(row.id)) {
          skipped.push(ref(row.id));
          if (verify)
            diagnostics.push({
              kind: "duplicate",
              severity: "info",
              message: "transactions.import.message_082074",
              affected_transaction_ids: [row.id],
            });
          continue;
        }
        const likely =
          days.has(day) ||
          ledger.movements.some(
            (movement) =>
              `${movement.transaction.date}:${movement.transaction.amount}` ===
              day,
          );
        days.add(day);
        imported.push(ref(row.id));
        fresh.push(row.id);
        if (likely) duplicates.push(ref(row.id));
        if (dryRun) continue;
        const created = now();
        ledger.movements.push({
          transaction: {
            ...fixtureTemplate(),
            transaction_id: row.id,
            date: row.date,
            booked_date: row.date,
            value_date: row.date,
            amount: row.amount,
            direction: row.direction,
            description: row.description,
            created_at: created,
            modified_at: created,
          },
          group_label: null,
          own_account_id: bound,
          import_batch_id: null,
          issue: likely ? "duplicate" : null,
          sealed: false,
          llm_rejected: false,
          idempotency_key: null,
        });
      }
      if (verify && spec.gap && read.length > 0)
        diagnostics.push({
          kind: "gap",
          severity: "warning",
          message: "transactions.import.message_829073",
          affected_transaction_ids: [],
        });
      if (!dryRun && fresh.length > 0) {
        const batch = hex64(`batch:${fresh.join(",")}`);
        batches.push(batch);
        for (const id of fresh) transactionOf(id)!.import_batch_id = batch;
      }
    });
    return {
      profile_id: profile,
      rows,
      imported: imported.length,
      skipped: skipped.length,
      likely_duplicates: duplicates.length,
      dry_run: dryRun,
      verify,
      period: period as unknown as JsonValue,
      bucket_id: profile,
      // Files that each import have no single batch between them.
      import_batch_id: batches.length === 1 ? batches[0]! : null,
      bucket_event_ids: dryRun || imported.length === 0 ? [] : events(),
      imported_transaction_refs: imported,
      skipped_transaction_refs: skipped,
      likely_duplicate_transaction_refs: duplicates,
      validations,
      sources: chosen.map(() => ({ requested: false, sha256: null })),
      diagnostics,
      refused_files: refused,
      source_digests: digests,
    };
  }

  /** An invoice book, row by row: no dry run, a refused row leaves the
   * others, and a row the catalogue already holds is skipped. */
  function importInvoiceBook(request: JsonObject): JsonObject {
    const file = fileOf(request.source_path, "invoice_books");
    const kind = request.kind;
    if (kind !== "issued" && kind !== "received") return invalid();
    const country = text(request.country);
    if (country !== null && !/^[A-Z]{2}$/.test(country)) return invalid();
    const sha = bytesOf(file.name);
    const expected = text(request.source_sha256);
    if (expected !== null && expected !== sha)
      throw new Stopped("ERROR_INVOICE_IMPORT_SOURCE_CHANGED");
    const refusals = BOOK_REFUSALS[file.name] ?? [];
    const rows = 6;
    const created: string[] = [];
    let skippedDuplicate = 0;
    const template = ledger.invoices.find((invoice) => invoice.kind === kind);
    for (let row = 2; row < rows + 2; row += 1) {
      if (refusals.some((refusal) => refusal.row_number === row)) continue;
      // The book's first row repeats an invoice the catalogue holds.
      const id =
        row === 2 && template
          ? template.invoice_id
          : hex64(`book:${file.name}:${kind}:${row}`);
      if (ledger.invoices.some((invoice) => invoice.invoice_id === id)) {
        skippedDuplicate += 1;
        continue;
      }
      const baseCents = 4000 + row * 1250;
      const ivaCents = Math.round(baseCents * 0.21);
      const issued = `2026-${String(1 + (row % 9)).padStart(2, "0")}-1${row % 9}`;
      ledger.invoices.push({
        ...(template ?? ledger.invoices[0]!),
        invoice_id: id,
        kind,
        invoice_number: `LIB-2026-${String(row).padStart(3, "0")}`,
        issued_at: issued,
        operation_date: issued,
        counterparty_name: `Proveedor del libro ${row}, S.L.`,
        counterparty_tax_id: `B0000${String(row).padStart(4, "0")}`,
        counterparty_country: country ?? "ES",
        base_total: { decimal: money(baseCents) },
        iva_total: { decimal: money(ivaCents) },
        grand_total: { decimal: money(baseCents + ivaCents) },
        payment_status: "PENDING",
        linked_transaction_ids: [],
        source_filename: file.name,
        source_sha256: sha,
        source_row_index: row,
        lines: [],
      });
      created.push(id);
    }
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      source_sha256: sha,
      rows,
      created: created.length,
      skipped_duplicate: skippedDuplicate,
      refused: refusals as unknown as JsonValue,
      created_invoice_ids: created,
      unmapped_column_headers: ["Observaciones"],
      mapping_reasons: [],
    };
  }

  /** Documents added as evidence: a PDF or an XML is read at once, an image
   * waits for its reading, and a document already held is left as it is.
   * Where the local AI is not set up, an image cannot be read: it is paused,
   * and the run's pause names the local AI's setup. */
  function addDocuments(request: JsonObject): JsonObject {
    const sources = request.sources;
    const direction = request.direction;
    if (!Array.isArray(sources) || sources.length === 0) return invalid();
    if (direction !== "issued" && direction !== "received") return invalid();
    const items: JsonObject[] = [];
    let writes = 0;
    let paused = false;
    for (const token of sources) {
      const file = fileOf(token, "documents");
      const address = hex64(`document:${bytesOf(file.name)}`);
      const kind = file.name.split(".").pop()?.toLowerCase() ?? "";
      const image = kind !== "pdf" && kind !== "xml";
      const held = ledger.evidence.some(
        (record) => record.source_sha256 === address,
      );
      if (image && !held && shape === "reader_missing") {
        paused = true;
        items.push({
          content_address: address,
          identity: `${address}:${direction}`,
          direction,
          source_name: file.name,
          status: "paused",
          refusal_code: null,
          refusal_verdict: null,
          needed_inference: true,
          label_reading_fallback: null,
        });
        continue;
      }
      if (!held) {
        writes += 1;
        const at = now();
        ledger.evidence.push({
          evidence_id: hex64(`evidence:${address}`),
          bucket_id: LEDGER_FIXTURE_PROFILE_ID,
          source_sha256: address,
          attachment_id: address,
          media_kind: image ? "image" : "pdf",
          supplier: null,
          invoice_number: null,
          invoice_date: null,
          taxable_base: null,
          iva_rate: null,
          iva_amount: null,
          notes: "",
          created_at: at,
          updated_at: at,
          source_path: file.name,
        });
      }
      items.push({
        content_address: address,
        identity: `${address}:${direction}`,
        direction,
        source_name: file.name,
        status: held ? "no_op" : image ? "pending_review" : "ingested",
        refusal_code: null,
        refusal_verdict: null,
        needed_inference: image,
        label_reading_fallback: null,
      });
    }
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      write_count: writes,
      effect: writes > 0 ? "updated" : "none",
      direction,
      run: {
        items,
        unresolved: [],
        inference_pause: paused ? readerPause() : null,
      },
    };
  }

  /** The pause a batch reports when the local AI's program does not answer:
   * its verdict names the local AI's setup. */
  function readerPause(): JsonObject {
    return {
      facts: [{ name: "runtime_reachable", value: false }],
      precondition_verdict: {
        failed_condition_id: "provisioning.runtime.reachable",
        evidence: [],
        action_id: "operator.provision.local_ai",
        argument_bindings: [],
        missing_argument_names: [],
        conditionality: "immediate",
        no_recovery_outcome: null,
      },
    };
  }

  function exportLedger(request: JsonObject): JsonObject {
    const target = fileOf(request.output_path, "export");
    const format = (request.export_format as string | undefined) ?? "csv";
    if (target.name.split(".").pop() !== format) return invalid();
    const rows = ledger.movements.filter(
      (movement) =>
        (request.include_inactive === true ||
          movement.transaction.lifecycle_state === "ACTIVE") &&
        inPeriod(movement, request.period),
    );
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      bucket_id: LEDGER_FIXTURE_PROFILE_ID,
      export_id: hex64(`export:${now()}`),
      export_format: format,
      media_type:
        format === "csv"
          ? "text/csv"
          : format === "jsonl"
            ? "application/x-ndjson"
            : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      filename_extension: format,
      row_count: rows.length,
      byte_size: rows.length * 312,
      sha256: hex64(`export-bytes:${rows.length}`),
      fieldnames: [
        "transaction_id",
        "booked_date",
        "amount",
        "direction",
        "description",
      ],
      rows: [],
      bucket_event_ids: events(),
      output_path: target.name,
    };
  }

  /** Adds an own account or changes its details; the window sees it
   * masked, as the product publishes it. */
  function changeAccount(request: JsonObject): JsonObject {
    const action = request.action;
    const iban = text(request.iban);
    const id =
      action === "add"
        ? `acc-${String(ledger.accounts.length + 1).padStart(2, "0")}`
        : text(request.own_account_id);
    const existing = ledger.accounts.find(
      (account) => account.own_account_id === id,
    );
    if (action === "add" && (!iban || !text(request.label))) return invalid();
    if (action === "update" && !existing)
      throw new Stopped("ERROR_TRANSACTION_VALIDATION");
    const masked = iban
      ? `${iban.slice(0, 2).toUpperCase()}**${iban.slice(-4)}`
      : (existing?.masked_iban ?? "");
    const holding = text(request.holding) ?? existing?.holding ?? "titular";
    const account: FixtureAccount = {
      own_account_id: id!,
      label: text(request.label) ?? existing?.label ?? "",
      holding: holding === "cotitular" ? "cotitular" : "titular",
      masked_iban: masked,
      country_code: masked.slice(0, 2),
      sepa_marca: "1",
      has_swift_bic:
        Boolean(text(request.swift_bic)) || (existing?.has_swift_bic ?? false),
      has_bank_block:
        Boolean(text(request.bank_name)) || (existing?.has_bank_block ?? false),
      currency: text(request.currency) ?? existing?.currency ?? "EUR",
      opened_on: text(request.opened_on) ?? existing?.opened_on ?? null,
      closed_on: existing?.closed_on ?? null,
    };
    if (existing) Object.assign(existing, account);
    else ledger.accounts.push(account);
    return {
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      action: action as string,
      own_account_id: id,
      accounts: [account as unknown as JsonValue],
      designations: [],
      changed: true,
    };
  }
  function ownAccount(request: JsonObject): JsonObject {
    const action = text(request.action);
    const id = text(request.own_account_id);
    const accounts = ledger.accounts;
    if (action === "add" || action === "update") return changeAccount(request);
    if (action === "list")
      return {
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        action,
        own_account_id: null,
        accounts: accounts as unknown as JsonValue,
        designations: [...setupWork.designations()],
        changed: false,
      };
    if (action === "show") {
      const found = accounts.find((account) => account.own_account_id === id);
      if (!found) throw new Stopped("ERROR_TRANSACTION_VALIDATION");
      return {
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        action,
        own_account_id: id,
        accounts: [found as unknown as JsonValue],
        designations: [],
        changed: false,
      };
    }
    return setupWork.ownAccount(request);
  }

  const setupWork = setupOperations(ledger, {
    profileId: LEDGER_FIXTURE_PROFILE_ID,
    today: LEDGER_FIXTURE_TODAY,
    now,
    events,
    hex64,
  });
  const movementWork = movementActionOperations(ledger, {
    profileId: LEDGER_FIXTURE_PROFILE_ID,
    now,
    events,
    hex64,
  });
  const invoiceWork = invoiceOperations(ledger, {
    profileId: LEDGER_FIXTURE_PROFILE_ID,
    events,
    hex64,
  });
  const evidenceWork = evidenceOperations(ledger, {
    profileId: LEDGER_FIXTURE_PROFILE_ID,
    events,
    hex64,
    now,
    fileOf: (token) => fileOf(token, "documents"),
    issuesFor: (period) => issues(ledger, period),
    seed: shape === "documents" || shape === "reader_missing",
    readerMissing: shape === "reader_missing",
  });
  const reads: Partial<
    Record<LedgerDefinitionId, (request: JsonObject) => JsonObject>
  > = {
    ...invoiceWork.reads,
    ...evidenceWork.reads,
    ...movementWork.reads,
    ...setupWork.reads,
    "ledger.list": (request) => list(ledger, request),
    "ledger.view": (request) => {
      const movement = resolve(ledger, request.transaction_prefix);
      return {
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        transaction_prefix: request.transaction_prefix as string,
        transaction: { ...movement.transaction } as unknown as JsonValue,
        review_status: reviewStatus(
          movement.transaction.business_classification,
        ),
        latest_llm_rejection: movement.llm_rejected
          ? {
              occurred_at: "2026-10-02T09:30:00Z",
              operator_reason: "La propuesta no reconoce el proveedor.",
            }
          : null,
      };
    },
    "ledger.invoice.list": (request) => ({
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      kind: (request.kind as string | null | undefined) ?? null,
      invoices: ledger.invoices.filter((invoice: CatalogueInvoice) =>
        request.kind ? invoice.kind === request.kind : true,
      ) as unknown as JsonValue,
    }),
    "ledger.status": status,
    "ledger.preflight": preflight,
    "ledger.rule.list": () => ({
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      rules: ledger.rules as unknown as JsonValue,
    }),
  };
  const writes: Partial<
    Record<LedgerDefinitionId, (request: JsonObject) => JsonObject>
  > = {
    "ledger.update": update,
    "ledger.classify.single": classify,
    "ledger.classify.bulk": bulk,
    "ledger.add": add,
    "ledger.import": importStatement,
    "ledger.export": exportLedger,
    "ledger.invoice.import": importInvoiceBook,
    "ledger.evidence.batch": addDocuments,
    ...invoiceWork.writes,
    ...evidenceWork.writes,
    ...movementWork.writes,
    ...setupWork.writes,
    "ledger.remove": movementWork.remove,
  };

  function suggestion(pending: Pending, operation: string) {
    const movement = transactionOf(pending.transaction);
    const t = movement?.transaction;
    const mode = text(pending.request.mode) ?? "classification";
    // A household supply is proposed as Mixed, with the share the person
    // asked with or none; anything else as an office expense.
    const mixed =
      t !== undefined &&
      (t.business_classification === "MIXED" ||
        /FIBRA|LUZ|ELECTRICA/.test(t.description));
    const share = text(pending.request.business_pct);
    const gross = t ? cents(t.amount) : 0;
    const base = Math.round(gross / 1.21);
    const saturated = mode === "saturated";
    const halves = [Math.floor(gross / 2), gross - Math.floor(gross / 2)];
    return {
      projection_version: 1,
      profile_id: LEDGER_FIXTURE_PROFILE_ID,
      reviewed_proposal_digest: hex64(
        `proposal:${operation}:${pending.version}`,
      ),
      suggestion: {
        kind:
          mode === "split" || mode === "auto_split"
            ? "split"
            : saturated
              ? "saturated"
              : "classification",
        transaction_id: pending.transaction,
        provenance: "llm:local-medium",
        reason:
          pending.version === 0
            ? "The counterparty and the description match an office supplier."
            : "Read again: the description matches an office supplier.",
        evidence_id: t?.purchase_invoice_evidence_id ?? null,
        classification: mixed ? "MIXED" : "BUSINESS",
        category: mixed ? (t?.category_id ?? null) : "material_oficina",
        confidence: pending.version === 0 ? "0.82" : "0.79",
        multiple_components: mode === "split" || mode === "auto_split",
        business_pct: mixed ? share : null,
        iva_category: "domestic_general",
        iva_rate: saturated ? "0.21" : null,
        taxable_base: saturated ? money(base) : null,
        iva_amount: saturated ? money(gross - base) : null,
        rate_derivable: saturated,
        derivation_note: saturated ? "Registry rate for domestic_general." : "",
        evidence_advisory: "",
        parent_amount: mode === "split" && t ? t.amount : null,
        children:
          mode === "split" && t
            ? halves.map((part, at) => ({
                proportion: "0.5",
                amount: money(part),
                description: `${t.description} · ${at + 1}`,
                category: "material_oficina",
                iva_category: "domestic_general",
                iva_rate: null,
                taxable_base: null,
                iva_amount: null,
                rate_derivable: false,
                derivation_note: "",
                evidence_citation: "",
              }))
            : [],
      },
    };
  }

  /** Whether settling `definition` may change records: the host's class of
   * the definition alone decides it, whatever the request names. */
  const changes = (definition: LedgerDefinitionId) =>
    ledgerClassOf(definition) !== "read";

  async function run(
    definition: string,
    payload: unknown,
  ): Promise<LedgerOutcome> {
    say(`ledger ${definition}`);
    await answer();
    if (!isLedgerDefinition(definition)) return reject("not_admitted");
    if (
      typeof payload !== "object" ||
      payload === null ||
      Array.isArray(payload)
    )
      return reject("invalid");
    const request = payload as JsonObject;
    if ("profile_id" in request || "source_directory" in request)
      return reject("invalid");
    if (
      definition === "ledger.own_account" &&
      OWN_ACCOUNT_SECRETS.some((field) => field in request)
    )
      return reject("invalid");
    if (tooLarge(definition, request)) return reject("too_large");
    const mutation = changes(definition);
    if (mutation && shape === "refused")
      return reject("refused", { reason: "operation_unavailable" });
    const narrowed = mutation
      ? undefined
      : failingWhere.find(
          (found) =>
            found.definition === definition &&
            found.count > 0 &&
            Object.entries(found.where).every(
              ([key, value]) =>
                JSON.stringify(request[key]) === JSON.stringify(value),
            ),
        );
    if (narrowed) {
      narrowed.count -= 1;
      return reject("unavailable");
    }
    const failing = mutation ? 0 : (failingReads.get(definition) ?? 0);
    if (failing > 0) {
      failingReads.set(definition, failing - 1);
      return reject("unavailable");
    }
    const operation = nextOperation();
    try {
      if (ledgerClassOf(definition) === "review") {
        const movement = resolve(ledger, request.transaction_id);
        reviews.set(operation, {
          definition: definition as LedgerDefinitionId,
          request,
          transaction: movement.transaction.transaction_id,
          version: 0,
          shown: null,
        });
        const paused: LedgerOutcome = {
          kind: "review",
          operation_id: operation,
          revision: 2,
          cancellable: false,
        };
        outcomes.set(operation, paused);
        return paused;
      }
      const handle =
        definition === "ledger.own_account"
          ? ownAccount
          : (writes[definition] ?? reads[definition]);
      if (!handle) return reject("unavailable");
      const asked = mutation ? queued.shift() : undefined;
      if (asked === "refused") {
        // Refused whole, as a revision-guarded save that found the ledger
        // changed: nothing was written.
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason: "precondition_failed",
          detail: null,
        };
        outcomes.set(operation, refused);
        return refused;
      }
      const result = handle(request);
      // The write landed; its settlement was not observed, but it can be:
      // observing the operation answers what it settled.
      if (mutation && (shape === "unknown" || asked === "unknown")) {
        settle(operation, result);
        return reject("unknown", { operation_id: operation });
      }
      // The write landed and its answer was lost after it settled.
      if (mutation && asked === "saved_unread") {
        settle(operation, result);
        return reject("saved_unread", { operation_id: operation });
      }
      // A reply over the bound is lost: a write may have landed, a read
      // answered nothing.
      if (replyTooLarge(result)) {
        if (!mutation) return reject("unavailable");
        settle(operation, result);
        return reject("unknown", { operation_id: operation });
      }
      return settle(operation, result);
    } catch (error) {
      if (
        error instanceof InvoiceRequestInvalid ||
        error instanceof MovementActionInvalid
      )
        return invalid();
      if (error instanceof SetupRequestInvalid) return invalid();
      if (error instanceof SetupStopped) {
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason: error.reason,
          detail: error.detail as unknown as LedgerErrorDetail | null,
        };
        outcomes.set(operation, refused);
        return refused;
      }
      if (error instanceof MovementActionStopped) {
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason: error.reason,
          detail: null,
        };
        outcomes.set(operation, refused);
        return refused;
      }
      if (error instanceof InvoiceUnsettled)
        return reject("unknown", { operation_id: operation });
      if (error instanceof InvoiceStopped) {
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason: error.reason,
          detail: error.detail as unknown as LedgerErrorDetail,
        };
        outcomes.set(operation, refused);
        return refused;
      }
      if (!(error instanceof Stopped)) throw error;
      const stopped: LedgerOutcome = {
        kind: "refused",
        operation_id: operation,
        revision: 3,
        reason: error.reason,
        detail: null,
      };
      outcomes.set(operation, stopped);
      return stopped;
    }
  }

  return {
    async submit(definition, payload) {
      const outcome = await run(definition, payload);
      return outcome as LedgerOutcome<LedgerResult<typeof definition>>;
    },
    async observe(operation) {
      say("ledger observe");
      await answer();
      return outcomes.get(operation) ?? reject("not_admitted");
    },
    async review<Review>(operation: string) {
      say("ledger review");
      await answer();
      const pending = reviews.get(operation);
      if (!outcomes.has(operation)) return reject("not_admitted");
      if (!pending) return reject("review_changed", { reason: "not_pending" });
      const review = suggestion(pending, operation);
      pending.shown = hex64(JSON.stringify(review));
      const shown: LedgerReview<Review> = {
        operation_id: operation,
        revision: 2 + pending.version,
        review_digest: pending.shown,
        expires_at: null,
        review: review as Review,
      };
      return shown;
    },
    async answer(operation, reviewDigest, decision) {
      say(`ledger answer ${decision}`);
      await answer();
      const pending = reviews.get(operation);
      if (!pending || pending.shown !== reviewDigest)
        return reject("review_changed");
      // The review may have changed since the page read it.
      if (
        hex64(JSON.stringify(suggestion(pending, operation))) !== reviewDigest
      )
        return reject("review_changed", { reason: "review_changed" });
      if (shape === "refused")
        return reject("refused", { reason: "operation_unavailable" });
      const movement = transactionOf(pending.transaction);
      const proposal = suggestion(pending, operation).suggestion;
      const refuse = (reason: string): LedgerOutcome => {
        reviews.delete(operation);
        const refused: LedgerOutcome = {
          kind: "refused",
          operation_id: operation,
          revision: 3,
          reason,
          detail: null,
        };
        outcomes.set(operation, refused);
        return refused;
      };
      // An explicit rejection cannot apply; a Mixed proposal applies only
      // with a share.
      if (
        decision === "apply" &&
        (pending.request.origin === "classify_llm_reject" ||
          (proposal.classification === "MIXED" &&
            proposal.business_pct === null))
      )
        return refuse("ERROR_TRANSACTION_VALIDATION");
      if (
        movement &&
        (movement.sealed || movement.transaction.lifecycle_state !== "ACTIVE")
      )
        return refuse("ERROR_TRANSACTION_VALIDATION");
      reviews.delete(operation);
      if (decision === "apply" && movement) {
        if (proposal.kind === "split")
          movementWork.writes["ledger.split.manual"]!({
            transaction_id: pending.transaction,
            children: proposal.children.map((child) => ({
              amount: child.amount,
              description: child.description,
            })),
          });
        else
          classifyRow(
            movement,
            {
              classification: proposal.classification,
              category_id: proposal.category,
              business_pct: proposal.business_pct,
              iva_category: proposal.iva_category,
              ...(proposal.rate_derivable
                ? {
                    iva_rate: proposal.iva_rate,
                    taxable_base: proposal.taxable_base,
                    iva_amount: proposal.iva_amount,
                  }
                : {}),
            },
            "llm:local-medium",
          );
      }
      if (decision === "reject" && movement) movement.llm_rejected = true;
      movementWork.noteReview(
        pending.transaction,
        decision,
        text(pending.request.reason) ?? "",
      );
      if (shape === "unknown")
        return reject("unknown", { operation_id: operation });
      return settle(operation, {
        identity: {
          operation_id: operation,
          definition_id: pending.definition,
          subject_ref: `profile:${LEDGER_FIXTURE_PROFILE_ID}`,
        },
        request: { ...pending.request, profile_id: LEDGER_FIXTURE_PROFILE_ID },
        response: decision,
        result: {
          profile_id: LEDGER_FIXTURE_PROFILE_ID,
          reviewed_proposal_digest: suggestion(pending, operation)
            .reviewed_proposal_digest,
          outcome: decision === "apply" ? "classified" : "rejected",
          transaction_id: pending.transaction,
          provenance: proposal.provenance,
          operator_reason: text(pending.request.reason) ?? "",
        },
      });
    },
    async cancel(operation) {
      say("ledger cancel");
      await answer();
      if (!outcomes.has(operation)) return reject("not_admitted");
      return reject("refused", {
        operation_id: operation,
        reason: "cancellation_unsupported",
      });
    },
    async pickFiles(purpose, pick) {
      say(`ledger pickFiles ${purpose} ${pick}`);
      await answer();
      const offered = PICKABLE[purpose];
      return take(pick === "file" ? offered.slice(0, 1) : offered, purpose);
    },
    async saveFile(format, _filterLabel, suggestedName) {
      say(`ledger saveFile ${format}`);
      await answer();
      const name = suggestedName ?? `movimientos-2026.${format}`;
      return name.split(".").pop() === format
        ? take([name], "export")
        : { files: [], refused: 1 };
    },
    async forgetFiles(tokens) {
      say("ledger forgetFiles");
      tokens.forEach((token) => files.delete(token));
    },
    async observeDrops(purpose, listener) {
      say(`ledger observeDrops ${purpose}`);
      dropPurpose = purpose;
      drops.add(listener);
      return () => {
        drops.delete(listener);
      };
    },
    async changeOwnAccount(change) {
      say("ledger changeOwnAccount");
      try {
        await answer();
        let request: JsonObject;
        try {
          request = JSON.parse(new TextDecoder().decode(change)) as JsonObject;
        } catch {
          return reject("invalid");
        }
        if (request.action !== "add" && request.action !== "update")
          return reject("invalid");
        if (shape === "refused")
          return reject("refused", { reason: "operation_unavailable" });
        const operation = nextOperation();
        try {
          const result = changeAccount(request);
          if (shape === "unknown")
            return reject("unknown", { operation_id: operation });
          return settle(operation, result);
        } catch (error) {
          if (!(error instanceof Stopped)) throw error;
          return {
            kind: "refused",
            operation_id: operation,
            revision: 3,
            reason: error.reason,
            detail: null,
          };
        }
      } finally {
        change.fill(0);
      }
    },
  };
}

/** A blank imported movement the import fills in. */
function fixtureTemplate(): LedgerTransaction {
  return {
    transaction_id: "",
    date: "",
    booked_date: "",
    value_date: null,
    amount: "0.00",
    currency: "EUR",
    direction: "OUTGOING",
    counterparty: "",
    description: "",
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
    created_at: "",
    modified_at: "",
  };
}

/** Rows of RFC 4180 CSV: quoted cells may hold commas, quotes and breaks. */
function parseCsv(source: string): string[][] {
  const rows: string[][] = [];
  let cells: string[] = [];
  let cell = "";
  let quoted = false;
  for (let at = 0; at < source.length; at += 1) {
    const char = source[at]!;
    if (quoted) {
      if (char === '"' && source[at + 1] === '"') {
        cell += '"';
        at += 1;
      } else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") {
      cells.push(cell);
      cell = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && source[at + 1] === "\n") at += 1;
      cells.push(cell);
      rows.push(cells);
      cells = [];
      cell = "";
    } else cell += char;
  }
  if (cell !== "" || cells.length) {
    cells.push(cell);
    rows.push(cells);
  }
  return rows.filter((line) => line.some((value) => value.trim() !== ""));
}
