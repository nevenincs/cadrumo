// What the Stock panel decides without drawing: the choices its forms offer,
// the fields they draw, how what the person typed becomes the backend's
// request, which typed values are refused or still to give, and how a read of
// the stock books says whether a write held in doubt landed. The amounts a
// purchase states are the person's own; nothing here adds, rounds or rates
// anything, and a value nobody typed is never made up.

import type { PublicDecimal } from "../../../shell/ledger";
import {
  AMOUNT_RULE,
  parseDecimal,
  parseIsoDate,
  parseLine,
  parsePercent,
  QUANTITY_RULE,
  TAX_AMOUNT_RULE,
  UNIT_PRICE_RULE,
  type GrammarRefusal,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import type {
  InventoryAcquisitionCostRequest,
  InventoryBook,
  InventoryBookRow,
  InventoryCorrectionReason,
  InventoryCorrectRequest,
  InventoryCostKind,
  InventoryCreateRequest,
  InventoryDescribeRequest,
  InventoryHistoryKind,
  InventoryMovement,
  InventoryMovementAddRequest,
  InventoryMovementCorrectRequest,
  InventoryMovementKind,
  InventoryMovementReverseRequest,
  InventoryProof,
  InventoryProofKind,
  InventoryRestoreRequest,
  InventoryRetireRequest,
  InventoryRetirementReason,
  ValuationMethod,
} from "../../../shell/ledgerSetup";
import type { Landing } from "../WritePause";

// ---- What the backend's enums offer ----------------------------------------
//
// The backend serves no list of these choices, so each list reflects the enum
// it is named for. A test holds every one of them to its enum.

export const METHODS = [
  "fifo",
  "pmp",
  "coste_medio",
] as const satisfies readonly ValuationMethod[];

export const KINDS = [
  "opening",
  "purchase",
  "cogs",
  "count",
] as const satisfies readonly InventoryMovementKind[];

export const COST_KINDS = [
  "freight",
  "insurance",
  "customs_duty",
  "handling",
  "professional_fee",
  "other_directly_attributable",
] as const satisfies readonly InventoryCostKind[];

/** What a purchase's price, or one of its extra costs, can rest on. */
export const PROOF_KINDS = [
  "purchase_invoice",
  "transport_document",
  "insurance_document",
  "customs_declaration",
  "contract",
  "other_acquisition_evidence",
] as const satisfies readonly InventoryProofKind[];

/** The proof that extra costs were checked, and the proof that the
 * recoverable IVA was: each has a kind of its own. */
export const COST_CHECK_KIND = "attributable_cost_review" as const;
export const IVA_CHECK_KIND = "iva_recoverability_review" as const;

/** Why a stock fact is corrected or a movement reversed. */
export const CORRECTION_REASONS = [
  "keying_error",
  "source_document_corrected",
  "duplicate_entry",
  "operation_did_not_occur",
] as const satisfies readonly InventoryCorrectionReason[];

/** Why a stock book is retired. */
export const RETIREMENT_REASONS = [
  "created_in_error",
  "activity_ceased",
  "no_stock_held",
] as const satisfies readonly InventoryRetirementReason[];

/** What a change can be in the history of a book. */
export const HISTORY_KINDS = [
  "described",
  "opening_corrected",
  "movement_corrected",
  "movement_reversed",
  "retired",
  "restored",
] as const satisfies readonly InventoryHistoryKind[];

export type CostKind = (typeof COST_KINDS)[number];
export type ProofKind = (typeof PROOF_KINDS)[number];

/** The words of each choice, by the key that says it. */
export const COST_KIND_KEYS: Record<CostKind, string> = {
  freight: "desktop.ledger.stock.cost_kind.freight",
  insurance: "desktop.ledger.stock.cost_kind.insurance",
  customs_duty: "desktop.ledger.stock.cost_kind.customs_duty",
  handling: "desktop.ledger.stock.cost_kind.handling",
  professional_fee: "desktop.ledger.stock.cost_kind.professional_fee",
  other_directly_attributable:
    "desktop.ledger.stock.cost_kind.other_directly_attributable",
};
export const PROOF_KIND_KEYS: Record<ProofKind, string> = {
  purchase_invoice: "desktop.ledger.stock.proof_kind.purchase_invoice",
  transport_document: "desktop.ledger.stock.proof_kind.transport_document",
  insurance_document: "desktop.ledger.stock.proof_kind.insurance_document",
  customs_declaration: "desktop.ledger.stock.proof_kind.customs_declaration",
  contract: "desktop.ledger.stock.proof_kind.contract",
  other_acquisition_evidence:
    "desktop.ledger.stock.proof_kind.other_acquisition_evidence",
};

/** The words of these come from the backend's own catalogue, which words each
 * member of its enums. */
export const CORRECTION_REASON_KEYS: Record<
  (typeof CORRECTION_REASONS)[number],
  string
> = {
  keying_error: "application.inventory.labels.correction_reason.keying_error",
  source_document_corrected:
    "application.inventory.labels.correction_reason.source_document_corrected",
  duplicate_entry:
    "application.inventory.labels.correction_reason.duplicate_entry",
  operation_did_not_occur:
    "application.inventory.labels.correction_reason.operation_did_not_occur",
};
export const RETIREMENT_REASON_KEYS: Record<
  (typeof RETIREMENT_REASONS)[number],
  string
> = {
  created_in_error:
    "application.inventory.labels.retirement_reason.created_in_error",
  activity_ceased:
    "application.inventory.labels.retirement_reason.activity_ceased",
  no_stock_held: "application.inventory.labels.retirement_reason.no_stock_held",
};
export const HISTORY_KIND_KEYS: Record<(typeof HISTORY_KINDS)[number], string> =
  {
    described: "application.inventory.labels.history_kind.described",
    opening_corrected:
      "application.inventory.labels.history_kind.opening_corrected",
    movement_corrected:
      "application.inventory.labels.history_kind.movement_corrected",
    movement_reversed:
      "application.inventory.labels.history_kind.movement_reversed",
    retired: "application.inventory.labels.history_kind.retired",
    restored: "application.inventory.labels.history_kind.restored",
  };

// ---- The fields a form draws -------------------------------------------------

export type FieldControl = "text" | "choice" | "amount" | "share" | "date";

/** One field of a form: what it is called, how it is typed and whether the
 * request cannot be made without it. A field's key is where its text and its
 * problem are kept; no field names a reference the window mints. */
export type StockField = {
  key: string;
  label: string;
  hint?: string;
  control: FieldControl;
  required: boolean;
  /** For text that is typed as a number: the keyboard it asks for. */
  numeric?: boolean;
};

export const BOOK_FIELDS: readonly StockField[] = [
  {
    key: "name",
    label: "desktop.ledger.stock.field.name",
    hint: "desktop.ledger.stock.field.name_hint",
    control: "text",
    required: true,
  },
  {
    key: "method",
    label: "desktop.ledger.inventory.method_label",
    control: "choice",
    required: true,
  },
  {
    key: "opening",
    label: "desktop.ledger.inventory.opening",
    hint: "desktop.ledger.form.amount_hint",
    control: "amount",
    required: true,
    numeric: true,
  },
];

/** What every movement states. */
export const MOVEMENT_FIELDS: readonly StockField[] = [
  {
    key: "date",
    label: "desktop.ledger.inventory.date",
    hint: "desktop.ledger.form.date_hint",
    control: "date",
    required: true,
  },
  {
    key: "kind",
    label: "desktop.ledger.inventory.kind_label",
    control: "choice",
    required: true,
  },
  {
    key: "quantity",
    label: "desktop.ledger.inventory.quantity",
    control: "amount",
    required: true,
    numeric: true,
  },
];

/** What a movement other than a purchase can state about its cost. */
export const COST_FIELDS: readonly StockField[] = [
  {
    key: "unit_cost",
    label: "desktop.ledger.inventory.unit_cost",
    hint: "desktop.ledger.stock.field.cost_hint",
    control: "amount",
    required: false,
    numeric: true,
  },
  {
    key: "total_cost",
    label: "desktop.ledger.stock.field.total_cost",
    control: "amount",
    required: false,
    numeric: true,
  },
];

/** What a purchase states about its price. */
export const PRICE_FIELDS: readonly StockField[] = [
  {
    key: "price",
    label: "desktop.ledger.stock.field.price",
    hint: "desktop.ledger.form.amount_hint",
    control: "amount",
    required: true,
    numeric: true,
  },
  {
    key: "iva",
    label: "desktop.ledger.stock.field.iva",
    control: "amount",
    required: true,
    numeric: true,
  },
  {
    key: "share",
    label: "desktop.ledger.stock.field.share",
    hint: "desktop.ledger.form.percent_hint",
    control: "share",
    required: true,
    numeric: true,
  },
];

/** What each extra cost of a purchase states. */
export const EXTRA_FIELDS: readonly StockField[] = [
  {
    key: "kind",
    label: "desktop.ledger.stock.extra.kind",
    control: "choice",
    required: true,
  },
  {
    key: "price",
    label: "desktop.ledger.stock.extra.price",
    hint: "desktop.ledger.form.amount_hint",
    control: "amount",
    required: true,
    numeric: true,
  },
  {
    key: "iva",
    label: "desktop.ledger.stock.extra.iva",
    control: "amount",
    required: true,
    numeric: true,
  },
  {
    key: "share",
    label: "desktop.ledger.stock.extra.share",
    hint: "desktop.ledger.form.percent_hint",
    control: "share",
    required: true,
    numeric: true,
  },
];

/** The totals of a purchase, which the person states as the figures come
 * out. The backend checks them against the figures above and refuses a
 * disagreement. */
export const TOTAL_FIELDS: readonly StockField[] = [
  {
    key: "extra_total",
    label: "desktop.ledger.stock.field.extra_total",
    hint: "desktop.ledger.form.amount_hint",
    control: "amount",
    required: true,
    numeric: true,
  },
  {
    key: "recoverable",
    label: "desktop.ledger.stock.field.recoverable",
    control: "amount",
    required: true,
    numeric: true,
  },
  {
    key: "unrecoverable",
    label: "desktop.ledger.stock.field.unrecoverable",
    control: "amount",
    required: true,
    numeric: true,
  },
  {
    key: "total",
    label: "desktop.ledger.stock.field.total",
    control: "amount",
    required: true,
    numeric: true,
  },
];

/** What a change to a book's details states. */
export const DESCRIBE_FIELDS: readonly StockField[] = [
  {
    key: "label",
    label: "desktop.ledger.stock.field.label",
    hint: "desktop.ledger.stock.field.label_hint",
    control: "text",
    required: true,
  },
  {
    key: "description",
    label: "desktop.ledger.stock.field.description",
    control: "text",
    required: false,
  },
];

/** The reason every correction and reversal states. */
export const REASON_FIELD: StockField = {
  key: "reason",
  label: "desktop.ledger.stock.field.reason",
  control: "choice",
  required: true,
};

/** What a correction of the opening stock or the method states. */
export const CORRECT_FIELDS: readonly StockField[] = [
  REASON_FIELD,
  {
    key: "opening",
    label: "desktop.ledger.stock.field.opening_new",
    hint: "desktop.ledger.stock.field.keep_hint",
    control: "amount",
    required: false,
    numeric: true,
  },
  {
    key: "method",
    label: "desktop.ledger.stock.field.method_new",
    control: "choice",
    required: false,
  },
];

export type ProofSlotKey = "price" | "cost_check" | "iva_check";

/** A file the purchase rests on, and the kinds it can be: one kind is fixed
 * and not asked. */
export type ProofSlot = {
  key: ProofSlotKey;
  label: string;
  hint?: string;
  kinds: readonly InventoryProofKind[];
};

export const PROOF_SLOTS: readonly ProofSlot[] = [
  {
    key: "price",
    label: "desktop.ledger.stock.proof.price",
    kinds: PROOF_KINDS,
  },
  {
    key: "cost_check",
    label: "desktop.ledger.stock.proof.cost_check",
    hint: "desktop.ledger.stock.proof.check_hint",
    kinds: [COST_CHECK_KIND],
  },
  {
    key: "iva_check",
    label: "desktop.ledger.stock.proof.iva_check",
    hint: "desktop.ledger.stock.proof.check_hint",
    kinds: [IVA_CHECK_KIND],
  },
];

/** The largest file a proof is taken from. */
export const PROOF_FILE_LIMIT = 50 * 1024 * 1024;

// ---- What the person has typed -----------------------------------------------

/** A file a purchase rests on: the reference minted for it when the form
 * opened, the kind of proof, and the mark taken from the file's bytes, empty
 * until a file is chosen. The reference is never drawn. */
export type ProofDraft = { reference: string; kind: string; digest: string };

/** One extra cost of a purchase. Its key is the reference minted for it. */
export type ExtraDraft = {
  key: string;
  kind: string;
  price: string;
  iva: string;
  share: string;
  proof: ProofDraft;
};

export type BookDraft = { name: string; method: string; opening: string };

export type MovementDraft = {
  /** The text of each field, by its key. */
  values: Readonly<Record<string, string>>;
  extras: readonly ExtraDraft[];
  proofs: Readonly<Record<ProofSlotKey, ProofDraft>>;
};

export type DescribeDraft = { label: string; description: string };
export type CorrectDraft = { reason: string; opening: string; method: string };

export const EMPTY_BOOK: BookDraft = { name: "", method: "", opening: "" };
export const EMPTY_CORRECTION: CorrectDraft = {
  reason: "",
  opening: "",
  method: "",
};

export const blankProof = (mint: () => string, kind = ""): ProofDraft => ({
  reference: mint(),
  kind,
  digest: "",
});

export const blankExtra = (mint: () => string): ExtraDraft => ({
  key: mint(),
  kind: "",
  price: "",
  iva: "",
  share: "",
  proof: blankProof(mint),
});

/** A movement form's start: nothing typed, every reference minted. */
export function blankMovement(mint: () => string): MovementDraft {
  return {
    values: {},
    extras: [],
    proofs: {
      price: blankProof(mint),
      cost_check: blankProof(mint, COST_CHECK_KIND),
      iva_check: blankProof(mint, IVA_CHECK_KIND),
    },
  };
}

/** Whether anything is typed or chosen that is not yet written. */
export function movementTouched(draft: MovementDraft): boolean {
  return (
    Object.values(draft.values).some((text) => text.trim() !== "") ||
    draft.extras.length > 0 ||
    Object.values(draft.proofs).some((proof) => proof.digest !== "")
  );
}

export const bookTouched = (draft: BookDraft): boolean =>
  Object.values(draft).some((text) => text.trim() !== "");

// ---- Building a request ------------------------------------------------------

/** Typed values the grammar refused, by the key of the field. */
export type Problems = Readonly<Record<string, GrammarRefusal>>;

/** What a form's fields make: the request, or null while a value is refused
 * or still to give. */
export type Built<Request> = {
  request: Request | null;
  problems: Problems;
  /** Keys of the fields still to fill in or choose. */
  missing: ReadonlySet<string>;
};

const decimal = (text: string): PublicDecimal => ({ decimal: text });

function collector() {
  const problems: Record<string, GrammarRefusal> = {};
  const missing = new Set<string>();
  return {
    problems,
    missing,
    /** A value the request cannot be made without. */
    need(key: string, parsed: Parsed<string>): string | null {
      if (parsed.kind === "value") return parsed.value;
      if (parsed.kind === "refused") problems[key] = parsed.refusal;
      else missing.add(key);
      return null;
    },
    /** A value that may stay unstated; one stated and refused still stops
     * the request. */
    maybe(key: string, parsed: Parsed<string>): string | null {
      if (parsed.kind === "value") return parsed.value;
      if (parsed.kind === "refused") problems[key] = parsed.refusal;
      return null;
    },
    choice<Option extends string>(
      key: string,
      raw: string | undefined,
      options: readonly Option[],
    ): Option | null {
      const found = options.find((option) => option === raw);
      if (found === undefined) missing.add(key);
      return found ?? null;
    },
    lack(key: string) {
      missing.add(key);
    },
    ready: () => Object.keys(problems).length === 0 && missing.size === 0,
  };
}

type Collector = ReturnType<typeof collector>;

/** The book a form asks for, in the year the panel stands on. */
export function bookRequest(
  year: number,
  draft: BookDraft,
): Built<InventoryCreateRequest> {
  const c = collector();
  const name = c.need("name", parseLine(draft.name, 120));
  const method = c.choice("method", draft.method, METHODS);
  const opening = c.need(
    "opening",
    parseDecimal(draft.opening, TAX_AMOUNT_RULE),
  );
  return {
    request:
      c.ready() && name !== null && method !== null && opening !== null
        ? {
            actividad_id: name,
            year,
            valuation_method: method,
            opening_stock: decimal(opening),
          }
        : null,
    problems: c.problems,
    missing: c.missing,
  };
}

/** The proof a slot states: its kind, and the mark of the file attached. */
function proofOf(
  c: Collector,
  key: string,
  draft: ProofDraft,
  kinds: readonly InventoryProofKind[],
): InventoryProof | null {
  const kind = c.choice(`${key}:kind`, draft.kind, kinds);
  if (draft.digest === "") c.lack(`${key}:file`);
  return kind !== null && draft.digest !== ""
    ? {
        reference: { reference: draft.reference },
        evidence_kind: kind,
        content_digest: draft.digest,
      }
    : null;
}

/** What a purchase cost, and what it rests on, from the fields drawn for it. */
function acquisitionOf(
  c: Collector,
  draft: MovementDraft,
): InventoryAcquisitionCostRequest | null {
  const text = (key: string) => draft.values[key] ?? "";
  const price = c.need("price", parseDecimal(text("price"), TAX_AMOUNT_RULE));
  const iva = c.need("iva", parseDecimal(text("iva"), TAX_AMOUNT_RULE));
  const share = c.need("share", parsePercent(text("share")));
  const totals = Object.fromEntries(
    TOTAL_FIELDS.map((field) => [
      field.key,
      c.need(field.key, parseDecimal(text(field.key), TAX_AMOUNT_RULE)),
    ]),
  );
  const consideration = proofOf(c, "price", draft.proofs.price, PROOF_KINDS);
  const costCheck = proofOf(c, "cost_check", draft.proofs.cost_check, [
    COST_CHECK_KIND,
  ]);
  const ivaCheck = proofOf(c, "iva_check", draft.proofs.iva_check, [
    IVA_CHECK_KIND,
  ]);

  const components = draft.extras.map((extra) => {
    const at = (field: string) => `extra:${extra.key}:${field}`;
    const kind = c.choice(at("kind"), extra.kind, COST_KINDS);
    const base = c.need(at("price"), parseDecimal(extra.price, AMOUNT_RULE));
    const tax = c.need(at("iva"), parseDecimal(extra.iva, TAX_AMOUNT_RULE));
    const ratio = c.need(at("share"), parsePercent(extra.share));
    const proof = proofOf(c, at("proof"), extra.proof, PROOF_KINDS);
    return { extra, kind, base, tax, ratio, proof };
  });

  if (
    !c.ready() ||
    price === null ||
    iva === null ||
    share === null ||
    consideration === null ||
    costCheck === null ||
    ivaCheck === null
  )
    return null;
  const stated = (key: string) => totals[key] ?? null;
  const extraTotal = stated("extra_total");
  const recoverable = stated("recoverable");
  const unrecoverable = stated("unrecoverable");
  const total = stated("total");
  if (
    extraTotal === null ||
    recoverable === null ||
    unrecoverable === null ||
    total === null
  )
    return null;
  const built: InventoryAcquisitionCostRequest["attributable_cost_components"] =
    [];
  const proofs: InventoryProof[] = [consideration];
  for (const part of components) {
    if (
      part.kind === null ||
      part.base === null ||
      part.tax === null ||
      part.ratio === null ||
      part.proof === null
    )
      return null;
    built.push({
      component_id: part.extra.key,
      kind: part.kind,
      taxable_base: decimal(part.base),
      iva_amount: decimal(part.tax),
      deductible_iva_ratio: decimal(part.ratio),
      evidence_references: [{ reference: part.proof.reference.reference }],
    });
    proofs.push(part.proof);
  }
  proofs.push(costCheck, ivaCheck);
  return {
    consideration_excluding_iva: decimal(price),
    consideration_iva_amount: decimal(iva),
    consideration_deductible_iva_ratio: decimal(share),
    attributable_cost_components: built,
    evidence: proofs,
    completeness: {
      consideration_evidence: { reference: consideration.reference.reference },
      attributable_cost_review_evidence: {
        reference: costCheck.reference.reference,
      },
      iva_recoverability_review_evidence: {
        reference: ivaCheck.reference.reference,
      },
    },
    directly_attributable_cost_total: decimal(extraTotal),
    nonrecoverable_iva_included: decimal(unrecoverable),
    recoverable_iva_excluded: decimal(recoverable),
    total_acquisition_cost: decimal(total),
  };
}

/**
 * The movement a form asks for, in a book. `movementId` is the reference the
 * window minted when the form opened. A purchase states what it cost and what
 * it rests on, and no unit cost or total beside it; any other movement states
 * a unit cost, a total, or neither.
 */
export function movementRequest(
  book: { actividad_id: string; year: number },
  movementId: string,
  draft: MovementDraft,
): Built<InventoryMovementAddRequest> {
  const c = collector();
  const text = (key: string) => draft.values[key] ?? "";
  const date = c.need("date", parseIsoDate(text("date")));
  const kind = c.choice("kind", text("kind"), KINDS);
  const quantity = c.need(
    "quantity",
    parseDecimal(text("quantity"), QUANTITY_RULE),
  );
  let unit: string | null = null;
  let total: string | null = null;
  let acquisition: InventoryAcquisitionCostRequest | null = null;
  if (kind === "purchase") acquisition = acquisitionOf(c, draft);
  else if (kind !== null) {
    unit = c.maybe(
      "unit_cost",
      parseDecimal(text("unit_cost"), UNIT_PRICE_RULE),
    );
    total = c.maybe(
      "total_cost",
      parseDecimal(text("total_cost"), TAX_AMOUNT_RULE),
    );
  }
  const ready =
    c.ready() &&
    date !== null &&
    kind !== null &&
    quantity !== null &&
    (kind !== "purchase" || acquisition !== null);
  return {
    request: ready
      ? {
          actividad_id: book.actividad_id,
          year: book.year,
          movement_id: movementId,
          movement_date: date,
          kind,
          quantity: decimal(quantity),
          ...(kind === "purchase"
            ? { acquisition_cost: acquisition }
            : {
                unit_cost: unit === null ? null : decimal(unit),
                taxable_base: total === null ? null : decimal(total),
              }),
        }
      : null,
    problems: c.problems,
    missing: c.missing,
  };
}

// ---- Changing a book ----------------------------------------------------------------

type Book = { actividad_id: string; year: number };

/** What every change to a book names: the book, and the reference the window
 * minted when the form opened, so a change sent twice is one change. */
const changeOf = (book: Book, correction: string) => ({
  actividad_id: book.actividad_id,
  year: book.year,
  correction_id: correction,
});

export function describeRequest(
  book: Book,
  correction: string,
  draft: DescribeDraft,
): Built<InventoryDescribeRequest> {
  const c = collector();
  const label = c.need("label", parseLine(draft.label, 120));
  const description = c.maybe(
    "description",
    parseLine(draft.description, 1024),
  );
  return {
    request:
      c.ready() && label !== null
        ? { ...changeOf(book, correction), label, description }
        : null,
    problems: c.problems,
    missing: c.missing,
  };
}

/** A correction of the opening stock, the method, or both. What is left empty
 * stays as it is. */
export function correctRequest(
  book: Book,
  correction: string,
  draft: CorrectDraft,
): Built<InventoryCorrectRequest> {
  const c = collector();
  const reason = c.choice("reason", draft.reason, CORRECTION_REASONS);
  const opening = c.maybe(
    "opening",
    parseDecimal(draft.opening, TAX_AMOUNT_RULE),
  );
  const method =
    draft.method === "" ? null : c.choice("method", draft.method, METHODS);
  return {
    request:
      c.ready() && reason !== null
        ? {
            ...changeOf(book, correction),
            reason,
            opening_stock: opening === null ? null : decimal(opening),
            valuation_method: method,
          }
        : null,
    problems: c.problems,
    missing: c.missing,
  };
}

/** A movement replaced by another, which the fields of a movement state. */
export function movementCorrectionRequest(
  book: Book,
  ids: { correction: string; movement: string },
  target: string,
  reason: string,
  draft: MovementDraft,
): Built<InventoryMovementCorrectRequest> {
  const made = movementRequest(book, ids.movement, draft);
  const why = CORRECTION_REASONS.find((found) => found === reason) ?? null;
  const missing = new Set(made.missing);
  if (why === null) missing.add("reason");
  if (made.request === null || why === null)
    return { request: null, problems: made.problems, missing };
  const { actividad_id, year, ...movement } = made.request;
  return {
    request: {
      actividad_id,
      year,
      correction_id: ids.correction,
      target_movement_id: target,
      reason: why,
      ...movement,
    },
    problems: made.problems,
    missing,
  };
}

export function reverseRequest(
  book: Book,
  correction: string,
  target: string,
  reason: string,
): Built<InventoryMovementReverseRequest> {
  const c = collector();
  const why = c.choice("reason", reason, CORRECTION_REASONS);
  return {
    request:
      why === null
        ? null
        : {
            ...changeOf(book, correction),
            target_movement_id: target,
            reason: why,
          },
    problems: c.problems,
    missing: c.missing,
  };
}

export function retireRequest(
  book: Book,
  correction: string,
  reason: string,
): Built<InventoryRetireRequest> {
  const c = collector();
  const why = c.choice("reason", reason, RETIREMENT_REASONS);
  return {
    request:
      why === null ? null : { ...changeOf(book, correction), reason: why },
    problems: c.problems,
    missing: c.missing,
  };
}

export const restoreRequest = (
  book: Book,
  correction: string,
): InventoryRestoreRequest => changeOf(book, correction);

/** Whether a change sent under its reference is in the history of the book
 * as read again; untold where the book could not be read. */
export function changeLanded(
  ledger: Pick<InventoryBook, "history"> | null,
  correction: string,
): Landing {
  if (ledger === null) return "untold";
  return (ledger.history ?? []).some(
    (entry) => entry.correction_id === correction,
  )
    ? "saved"
    : "not_saved";
}

// ---- The history of a book ------------------------------------------------------------

/** A fact a change displaced or left in its place. */
export type HistoryFact =
  | { kind: "opening"; value: string }
  | { kind: "method"; value: ValuationMethod }
  | { kind: "label"; value: string }
  | { kind: "description"; value: string | null }
  | { kind: "movement"; value: InventoryMovement }
  | { kind: "removed" };

/** One change, with what it displaced and what stood in its place. */
export type HistoryRow = {
  /** Where the change stands in the history, oldest first. */
  position: number;
  /** The day it was made, year-month-day. */
  day: string;
  kind: InventoryHistoryKind;
  reason:
    | { family: "correction"; token: InventoryCorrectionReason }
    | { family: "retirement"; token: InventoryRetirementReason }
    | null;
  before: HistoryFact[];
  after: HistoryFact[];
};

/**
 * The changes of a book, newest first, each with what it displaced and what
 * took its place. What took its place is found in what was kept: the next
 * change of the same fact states what that change displaced, else the book
 * as it stands. Nothing is worked out.
 */
export function historyRows(ledger: InventoryBook): HistoryRow[] {
  const entries = ledger.history ?? [];
  const movements = [
    ...ledger.period_movements,
    ...entries.flatMap((entry) =>
      entry.superseded_movement ? [entry.superseded_movement] : [],
    ),
  ];
  const rows = entries.map((entry, position): HistoryRow => {
    const later = entries.slice(position + 1);
    const before: HistoryFact[] = [];
    const after: HistoryFact[] = [];
    if (entry.prior_opening_stock !== null) {
      before.push({
        kind: "opening",
        value: entry.prior_opening_stock.decimal,
      });
      const next = later.find((found) => found.prior_opening_stock !== null);
      after.push({
        kind: "opening",
        value: (next?.prior_opening_stock ?? ledger.opening_stock).decimal,
      });
    }
    if (entry.prior_valuation_method !== null) {
      before.push({ kind: "method", value: entry.prior_valuation_method });
      const next = later.find((found) => found.prior_valuation_method !== null);
      after.push({
        kind: "method",
        value: next?.prior_valuation_method ?? ledger.valuation_method,
      });
    }
    if (entry.prior_descriptor !== null) {
      before.push({ kind: "label", value: entry.prior_descriptor.label });
      before.push({
        kind: "description",
        value: entry.prior_descriptor.description,
      });
      const next = later.find((found) => found.prior_descriptor !== null);
      const now = next?.prior_descriptor ?? ledger.descriptor ?? null;
      if (now !== null) {
        after.push({ kind: "label", value: now.label });
        after.push({ kind: "description", value: now.description });
      }
    }
    if (entry.superseded_movement !== null) {
      before.push({ kind: "movement", value: entry.superseded_movement });
      const replacement = movements.find(
        (found) => found.movement_id === entry.replacement_movement_id,
      );
      if (entry.kind === "movement_reversed") after.push({ kind: "removed" });
      else if (replacement)
        after.push({ kind: "movement", value: replacement });
    }
    return {
      position,
      day: entry.recorded_at.slice(0, 10),
      kind: entry.kind,
      reason: entry.correction_reason
        ? { family: "correction", token: entry.correction_reason }
        : entry.retirement_reason
          ? { family: "retirement", token: entry.retirement_reason }
          : null,
      before,
      after,
    };
  });
  return rows.reverse();
}

// ---- Reading the stock books ---------------------------------------------------

/** The name a book is listed under: the one given to it, else the activity
 * it was started for. */
export function bookName(row: {
  actividad_id: string;
  label?: string | null;
}): string {
  const label = row.label?.trim();
  return label ? label : row.actividad_id;
}

/** Whether a book is listed for the activity and year. */
export function bookListed(
  rows: readonly InventoryBookRow[],
  name: string,
  year: number,
): Landing {
  return rows.some((row) => row.actividad_id === name && row.year === year)
    ? "saved"
    : "not_saved";
}

/** Whether a book now holds more movements than it did when one was sent. A
 * movement's reference is refused if sent again, so the count tells it. */
export function movementCounted(
  rows: readonly InventoryBookRow[],
  book: { actividad_id: string; year: number },
  before: number,
): Landing {
  const now = rows.find(
    (row) => row.actividad_id === book.actividad_id && row.year === book.year,
  );
  return now !== undefined && now.movement_count > before
    ? "saved"
    : "not_saved";
}

// ---- Files ---------------------------------------------------------------------

/** The mark of a file's bytes: the lowercase hex of their SHA-256, which the
 * backend holds in place of the file. */
export async function fingerprintOf(bytes: ArrayBuffer): Promise<string> {
  const mark = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(mark), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}
