import type { Suggestion } from "@/components/ui/suggestions";
import {
  isPurchaseLedgerRow,
  type PurchaseLedgerRow,
} from "../../../shell/ledgerContract";
import type { FileToken, PublicDecimal } from "../../../shell/ledger";
import {
  AMOUNT_RULE,
  parseDecimal,
  parseFractionPercent,
  parseIsoDate,
  parseLine,
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
  InventoryClosingDocument,
  InventoryClosingValueRequest,
  InventoryCorrectRequest,
  InventoryCreateRequest,
  InventoryDescribeRequest,
  InventoryEvidenceAddRequest,
  InventoryEvidenceAddResult,
  InventoryMovement,
  InventoryMovementAddRequest,
  InventoryMovementClaimRequest,
  InventoryMovementCorrectRequest,
  InventoryMovementReverseRequest,
  InventoryProof,
  InventoryRestoreRequest,
  InventoryRetireRequest,
} from "../../../shell/ledgerSetup";
import type { Landing } from "../WritePause";
import {
  proofKept,
  type BookDraft,
  type ClosingDraft,
  type CorrectDraft,
  type DescribeDraft,
  type MovementDraft,
  type ProofDraft,
} from "./stockDraft";
import { slotKinds } from "./stockVocabulary";
import { plays, priceKinds, type Vocabulary } from "./stockVocabulary";

// Inventory request grammar and write settlement checks. The amounts a
// purchase states are the person's own; nothing here adds, rounds or rates
// anything, and a value nobody typed is never made up.

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
    /** A choice among the values the backend serves. */
    choice(
      key: string,
      raw: string | undefined,
      options: readonly string[] | undefined,
    ): string | null {
      const found = (options ?? []).find((option) => option === raw);
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
  vocabulary: Vocabulary,
): Built<InventoryCreateRequest> {
  const c = collector();
  const name = c.need("name", parseLine(draft.name));
  const method = c.choice(
    "method",
    draft.method,
    vocabulary.values.valuation_method,
  );
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

/** The proof a file states: its kind, and what the backend named it by once
 * it kept it. A slot with one kind asks for no choice of it. */
function proofOf(
  c: Collector,
  key: string,
  draft: ProofDraft,
  kinds: readonly string[],
): InventoryProof | null {
  const kind = c.choice(
    `${key}:kind`,
    draft.kind === "" && kinds.length === 1 ? kinds[0] : draft.kind,
    kinds,
  );
  if (!proofKept(draft)) c.lack(`${key}:file`);
  return kind !== null && proofKept(draft)
    ? {
        reference: { reference: draft.reference },
        evidence_kind: kind,
        content_digest: draft.digest,
      }
    : null;
}

/** What a purchase cost, and what it rests on, from the fields drawn for it.
 * Its totals are left to the backend, which adds the figures up. */
function acquisitionOf(
  c: Collector,
  draft: MovementDraft,
  vocabulary: Vocabulary,
): InventoryAcquisitionCostRequest | null {
  const text = (key: string) => draft.values[key] ?? "";
  const price = c.need("price", parseDecimal(text("price"), TAX_AMOUNT_RULE));
  const iva = c.need("iva", parseDecimal(text("iva"), TAX_AMOUNT_RULE));
  const share = c.need("share", parseFractionPercent(text("share")));
  const consideration = proofOf(
    c,
    "price",
    draft.proofs.price,
    slotKinds("price", vocabulary),
  );
  const costCheck = proofOf(
    c,
    "cost_check",
    draft.proofs.cost_check,
    slotKinds("cost_check", vocabulary),
  );
  const ivaCheck = proofOf(
    c,
    "iva_check",
    draft.proofs.iva_check,
    slotKinds("iva_check", vocabulary),
  );

  const components = draft.extras.map((extra) => {
    const at = (field: string) => `extra:${extra.key}:${field}`;
    const kind = c.choice(
      at("kind"),
      extra.kind,
      vocabulary.values.attributable_cost_kind,
    );
    const base = c.need(at("price"), parseDecimal(extra.price, AMOUNT_RULE));
    const tax = c.need(at("iva"), parseDecimal(extra.iva, TAX_AMOUNT_RULE));
    const ratio = c.need(at("share"), parseFractionPercent(extra.share));
    const proof = proofOf(c, at("proof"), extra.proof, priceKinds(vocabulary));
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
  vocabulary: Vocabulary,
): Built<InventoryMovementAddRequest> {
  const c = collector();
  const text = (key: string) => draft.values[key] ?? "";
  const date = c.need("date", parseIsoDate(text("date")));
  const kind = c.choice("kind", text("kind"), vocabulary.values.movement_kind);
  const quantity = c.need(
    "quantity",
    parseDecimal(text("quantity"), QUANTITY_RULE),
  );
  let unit: string | null = null;
  let total: string | null = null;
  let acquisition: InventoryAcquisitionCostRequest | null = null;
  const purchase = plays(vocabulary, "purchase", kind ?? undefined);
  if (purchase) acquisition = acquisitionOf(c, draft, vocabulary);
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
    (!purchase || acquisition !== null);
  return {
    request: ready
      ? {
          actividad_id: book.actividad_id,
          year: book.year,
          movement_id: movementId,
          movement_date: date,
          kind,
          quantity: decimal(quantity),
          ...(purchase
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

/** The request that has the backend keep a file the person chose: the token
 * of the file, and nothing else; the host names the folder and the profile. */
export const evidenceRequest = (
  token: FileToken,
): InventoryEvidenceAddRequest => ({ source_path: token });

/** The proof a result of keeping a file makes, with the name the person saw it
 * under; null for a file the backend did not keep. */
export function proofFromKept(
  result: InventoryEvidenceAddResult,
  fileName: string,
): ProofDraft | null {
  if (
    result.outcome !== "stored" ||
    !result.reference ||
    !result.content_digest
  )
    return null;
  return {
    reference: result.reference,
    kind: "",
    digest: result.content_digest,
    fileName,
  };
}

/** A document of a closing value, with the role it plays. */
function documentOf(
  c: Collector,
  key: string,
  draft: ProofDraft | undefined,
  role: string,
): InventoryClosingDocument | null {
  if (draft === undefined || !proofKept(draft)) {
    c.lack(`${key}:file`);
    return null;
  }
  return {
    reference: { reference: draft.reference },
    role,
    content_digest: draft.digest,
  };
}

/**
 * A closing value from plain facts: the method, the reason, the documents
 * that show it, and a count when the count is the value. The fingerprints are
 * the backend's to make. `ids` are minted when the form opens, so a closing
 * sent twice is one closing.
 */
export function closingRequest(
  book: { actividad_id: string; year: number },
  ids: { decision: string },
  draft: ClosingDraft,
  vocabulary: Vocabulary,
): Built<InventoryClosingValueRequest> {
  const c = collector();
  const text = (key: string) => draft.values[key] ?? "";
  const authority = c.choice(
    "authority",
    text("authority"),
    vocabulary.values.closing_authority,
  );
  const reason = c.need("reason", parseLine(text("reason")));
  const decision = (vocabulary.values.decision_evidence_role ?? []).map(
    (role) => documentOf(c, `decision:${role}`, draft.decision[role], role),
  );
  if (decision.length === 0) c.lack("decision:file");
  let count: NonNullable<
    InventoryClosingValueRequest["facts"]["physical_count"]
  > | null = null;
  if (plays(vocabulary, "count_authority", authority ?? undefined)) {
    const observedOn = c.need("observed_on", parseIsoDate(text("observed_on")));
    const value = c.need(
      "closing_value",
      parseDecimal(text("closing_value"), TAX_AMOUNT_RULE),
    );
    const basis = c.choice(
      "basis",
      text("basis"),
      vocabulary.values.closing_valuation_basis,
    );
    const evidence = (vocabulary.values.physical_evidence_role ?? []).map(
      (role) => documentOf(c, `count:${role}`, draft.count[role], role),
    );
    if (evidence.length === 0) c.lack("count:file");
    const documents = evidence.filter((found) => found !== null);
    if (
      observedOn !== null &&
      value !== null &&
      basis !== null &&
      documents.length === evidence.length
    )
      count = {
        observed_on: observedOn,
        closing_value: decimal(value),
        valuation_basis: basis,
        evidence: documents,
      };
  }
  const prior = draft.prior.map((entry) => {
    if (proofKept(entry.proof))
      return {
        reference: { reference: entry.proof.reference },
        content_digest: entry.proof.digest,
      };
    c.lack(`prior:${entry.key}:file`);
    return null;
  });
  const documents = decision.filter((found) => found !== null);
  const earlier = prior.filter((found) => found !== null);
  const ready =
    c.ready() &&
    authority !== null &&
    reason !== null &&
    (!plays(vocabulary, "count_authority", authority ?? undefined) ||
      count !== null);
  return {
    request: ready
      ? {
          actividad_id: book.actividad_id,
          year: book.year,
          facts: {
            decision_id: ids.decision,
            authority,
            reason,
            decision_evidence: documents,
            physical_count: count,
            prior_evidence: earlier,
          },
        }
      : null,
    problems: c.problems,
    missing: c.missing,
  };
}

/** Whether a closing value is in the book as read again; untold where the
 * book could not be read. */
export function closingLanded(
  ledger: Pick<InventoryBook, "closing_authority_fingerprints"> | null,
): Landing {
  if (ledger === null) return "untold";
  return ledger.closing_authority_fingerprints !== null ? "saved" : "not_saved";
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
  const label = c.need("label", parseLine(draft.label));
  const description = c.maybe("description", parseLine(draft.description));
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
  vocabulary: Vocabulary,
): Built<InventoryCorrectRequest> {
  const c = collector();
  const reason = c.choice(
    "reason",
    draft.reason,
    vocabulary.values.correction_reason,
  );
  const opening = c.maybe(
    "opening",
    parseDecimal(draft.opening, TAX_AMOUNT_RULE),
  );
  const method =
    draft.method === ""
      ? null
      : c.choice("method", draft.method, vocabulary.values.valuation_method);
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
  vocabulary: Vocabulary,
): Built<InventoryMovementCorrectRequest> {
  const made = movementRequest(book, ids.movement, draft, vocabulary);
  const why =
    (vocabulary.values.correction_reason ?? []).find(
      (found) => found === reason,
    ) ?? null;
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
  vocabulary: Vocabulary,
): Built<InventoryMovementReverseRequest> {
  const c = collector();
  const why = c.choice("reason", reason, vocabulary.values.correction_reason);
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

/** What a purchase states about the ledger transaction that books it. */
export type PurchaseClaim = {
  row: PurchaseLedgerRow;
  /** The transaction a claimed purchase names; null otherwise. */
  transaction: string | null;
};

/** The statement the read served for a purchase, or null where the read
 * served none: an unserved statement is not shown as any of the three. */
export function claimOf(movement: InventoryMovement): PurchaseClaim | null {
  const served = movement as InventoryMovement & {
    ledger_row?: string | null;
    claimed_transaction_id?: string | null;
  };
  const row = served.ledger_row;
  if (typeof row !== "string" || !isPurchaseLedgerRow(row)) return null;
  return { row, transaction: served.claimed_transaction_id ?? null };
}

/** The statement a form makes: that a transaction books the purchase, that
 * none does, or that nothing is stated. A transaction is named exactly when
 * it is claimed. */
export function claimRequest(
  book: Book,
  correction: string,
  movement: string,
  row: string,
  transaction: string,
): Built<InventoryMovementClaimRequest> {
  const c = collector();
  const stated = c.choice("row", row, ["unstated", "claimed", "none"]);
  if (stated === "claimed" && transaction === "") c.lack("transaction");
  return {
    request:
      c.ready() && stated !== null && isPurchaseLedgerRow(stated)
        ? {
            ...changeOf(book, correction),
            movement_id: movement,
            ledger_row: stated,
            claimed_transaction_id: stated === "claimed" ? transaction : null,
          }
        : null,
    problems: c.problems,
    missing: c.missing,
  };
}

export function retireRequest(
  book: Book,
  correction: string,
  reason: string,
  vocabulary: Vocabulary,
): Built<InventoryRetireRequest> {
  const c = collector();
  const why = c.choice("reason", reason, vocabulary.values.retirement_reason);
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

/** The activities books are held for in other years, each once and none that
 * has its book for `year` already. A book is named by its activity, so a
 * changed spelling would start another book. */
export function bookNameOptions(
  rows: readonly InventoryBookRow[],
  year: number,
): Suggestion[] {
  const held = new Set(
    rows.filter((row) => row.year === year).map((row) => row.actividad_id),
  );
  const named = new Map<string, InventoryBookRow>();
  for (const row of rows)
    if (!held.has(row.actividad_id) && !named.has(row.actividad_id))
      named.set(row.actividad_id, row);
  return [...named.values()].map((row) => ({
    value: row.actividad_id,
    label: row.actividad_id,
    note: bookName(row) === row.actividad_id ? undefined : bookName(row),
  }));
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
