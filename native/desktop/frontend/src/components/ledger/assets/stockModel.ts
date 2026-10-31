// What the Stock panel decides without drawing: the choices its forms offer,
// the fields they draw, how what the person typed becomes the backend's
// request, which typed values are refused or still to give, and how a read of
// the stock books says whether a write held in doubt landed. The amounts a
// purchase states are the person's own; nothing here adds, rounds or rates
// anything, and a value nobody typed is never made up.

import type { FileToken, PublicDecimal } from "../../../shell/ledger";
import {
  AMOUNT_RULE,
  canonicalDecimal,
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
  InventoryHistoryKind,
  InventoryMovement,
  InventoryMovementAddRequest,
  InventoryMovementCorrectRequest,
  InventoryMovementReverseRequest,
  InventoryOptionsResult,
  InventoryProof,
  InventoryRestoreRequest,
  InventoryRetireRequest,
  ValuationMethod,
} from "../../../shell/ledgerSetup";
import { heldDecimal } from "../../../shared/numbers";
import type { Landing } from "../WritePause";

// ---- What the backend offers -------------------------------------------------
//
// Every closed choice a form offers is read from the backend, which serves
// each with the key of its word. Nothing here lists a method, a kind, a
// reason or a basis.

/** What a form treats specially among the choices the backend serves. */
export type OptionRole =
  "cost_check" | "iva_check" | "count_authority" | "purchase";
/** One choice the backend serves, the key of its word, and the part it plays
 * in a form where it plays one. */
export type Served = {
  value: string;
  label_key: string;
  role?: string | null;
};
/** The choices served, by the family they belong to. */
export type Offers = Readonly<Record<string, readonly Served[]>>;
/** What the builders judge a request by: the values of each family, and the
 * value that plays each role. */
export type Vocabulary = {
  readonly values: Readonly<Record<string, readonly string[]>>;
  readonly roles: Readonly<Partial<Record<OptionRole, string>>>;
};

export const NO_OFFERS: Offers = {};
export const NO_VOCABULARY: Vocabulary = { values: {}, roles: {} };

export const offersOf = (result: InventoryOptionsResult): Offers =>
  Object.fromEntries(
    result.families.map((found) => [found.family, found.options]),
  );

const ROLES: readonly OptionRole[] = [
  "cost_check",
  "iva_check",
  "count_authority",
  "purchase",
];

export const vocabularyOf = (offers: Offers): Vocabulary => ({
  values: Object.fromEntries(
    Object.entries(offers).map(([family, options]) => [
      family,
      options.map((option) => option.value),
    ]),
  ),
  roles: Object.fromEntries(
    ROLES.flatMap((role) => {
      const found = Object.values(offers)
        .flat()
        .find((option) => option.role === role);
      return found ? [[role, found.value]] : [];
    }),
  ),
});

/** Whether a value is the one that plays a role. */
export const plays = (
  vocabulary: Vocabulary,
  role: OptionRole,
  value: string | undefined,
): boolean => value !== undefined && vocabulary.roles[role] === value;

/** What a price, or one of its extra costs, can rest on: the served kinds of
 * proof less the two checks. */
export const priceKinds = (vocabulary: Vocabulary): readonly string[] =>
  (vocabulary.values.acquisition_evidence_kind ?? []).filter(
    (kind) =>
      !plays(vocabulary, "cost_check", kind) &&
      !plays(vocabulary, "iva_check", kind),
  );

/** Where the words of each stored token are kept, by family. */
export const LABEL_FAMILY = {
  valuation_method: "application.inventory.labels.valuation_method.",
  movement_kind: "application.inventory.labels.movement_kind.",
  attributable_cost_kind:
    "application.inventory.labels.attributable_cost_kind.",
  acquisition_evidence_kind:
    "application.inventory.labels.acquisition_evidence_kind.",
  correction_reason: "application.inventory.labels.correction_reason.",
  retirement_reason: "application.inventory.labels.retirement_reason.",
  history_kind: "application.inventory.labels.history_kind.",
  closing_authority: "application.inventory.labels.closing_authority.",
  closing_valuation_basis:
    "application.inventory.labels.closing_valuation_basis.",
  decision_evidence_role:
    "application.inventory.labels.decision_evidence_role.",
  physical_evidence_role:
    "application.inventory.labels.physical_evidence_role.",
} as const;
export type LabelFamily = keyof typeof LABEL_FAMILY;

/** The word for a stored token; a token without one is not named, never
 * shown as the token. */
export function wordOf(
  t: (key: string) => string,
  family: LabelFamily,
  token: string | null | undefined,
): string {
  if (token === null || token === undefined || token === "")
    return t("desktop.ledger.stock.unnamed");
  const key = `${LABEL_FAMILY[family]}${token}`;
  const said = t(key);
  return said === key ? t("desktop.ledger.stock.unnamed") : said;
}

/** The word for a stored token: the one the backend serves for it, else the
 * word of its family, else unknown. */
export function wordFrom(
  t: (key: string) => string,
  offers: Offers,
  family: LabelFamily,
  token: string | null | undefined,
): string {
  const served = (offers[family] ?? []).find((found) => found.value === token);
  return served ? servedWord(t, served) : wordOf(t, family, token);
}

/** The word a served choice carries, by its own key. */
export function servedWord(t: (key: string) => string, served: Served): string {
  const said = t(served.label_key);
  return said === served.label_key ? t("desktop.ledger.stock.unnamed") : said;
}

// ---- The fields a form draws -------------------------------------------------

export type FieldControl =
  "text" | "choice" | "money" | "quantity" | "share" | "date";

/** One field of a form: what it is called, how it is typed and whether the
 * request cannot be made without it. A field's key is where its text and its
 * problem are kept; no field names a reference the window mints. */
export type StockField = {
  key: string;
  label: string;
  hint?: string;
  control: FieldControl;
  required: boolean;
  /** The most characters it takes, where that is not the usual. */
  max?: number;
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
    control: "money",
    required: true,
  },
];

/** What every movement states. */
export const MOVEMENT_FIELDS: readonly StockField[] = [
  {
    key: "date",
    label: "desktop.ledger.inventory.date",
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
    control: "quantity",
    required: true,
  },
];

/** What a movement other than a purchase can state about its cost. */
export const COST_FIELDS: readonly StockField[] = [
  {
    key: "unit_cost",
    label: "desktop.ledger.inventory.unit_cost",
    hint: "desktop.ledger.stock.field.cost_hint",
    control: "money",
    required: false,
  },
  {
    key: "total_cost",
    label: "desktop.ledger.stock.field.total_cost",
    control: "money",
    required: false,
  },
];

/** What a purchase states about its price. */
export const PRICE_FIELDS: readonly StockField[] = [
  {
    key: "price",
    label: "desktop.ledger.stock.field.price",
    control: "money",
    required: true,
  },
  {
    key: "iva",
    label: "desktop.ledger.stock.field.iva",
    control: "money",
    required: true,
  },
  {
    key: "share",
    label: "desktop.ledger.stock.field.share",
    control: "share",
    required: true,
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
    control: "money",
    required: true,
  },
  {
    key: "iva",
    label: "desktop.ledger.stock.extra.iva",
    control: "money",
    required: true,
  },
  {
    key: "share",
    label: "desktop.ledger.stock.extra.share",
    control: "share",
    required: true,
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
    control: "money",
    required: false,
  },
  {
    key: "method",
    label: "desktop.ledger.stock.field.method_new",
    control: "choice",
    required: false,
  },
];

export type ProofSlotKey = "price" | "cost_check" | "iva_check";

/** A file the purchase rests on. */
export type ProofSlot = {
  key: ProofSlotKey;
  label: string;
  hint?: string;
};

export const PROOF_SLOTS: readonly ProofSlot[] = [
  { key: "price", label: "desktop.ledger.stock.proof.price" },
  {
    key: "cost_check",
    label: "desktop.ledger.stock.proof.cost_check",
    hint: "desktop.ledger.stock.proof.check_hint",
  },
  {
    key: "iva_check",
    label: "desktop.ledger.stock.proof.iva_check",
    hint: "desktop.ledger.stock.proof.check_hint",
  },
];

/** The kinds a slot's file can be: a check has the one kind of its own. */
export function slotKinds(
  slot: ProofSlotKey,
  vocabulary: Vocabulary,
): readonly string[] {
  if (slot === "price") return priceKinds(vocabulary);
  const own =
    vocabulary.roles[slot === "cost_check" ? "cost_check" : "iva_check"];
  return own === undefined ? [] : [own];
}

/** What a closing value states. */
export const CLOSING_FIELDS: readonly StockField[] = [
  {
    key: "authority",
    label: "desktop.ledger.stock.closing.authority",
    control: "choice",
    required: true,
  },
  {
    key: "reason",
    label: "desktop.ledger.stock.closing.reason",
    hint: "desktop.ledger.stock.closing.reason_hint",
    control: "text",
    required: true,
    max: 512,
  },
];

/** What a count states, when the closing value is the count's. */
export const COUNT_FIELDS: readonly StockField[] = [
  {
    key: "observed_on",
    label: "desktop.ledger.stock.closing.counted_on",
    control: "date",
    required: true,
  },
  {
    key: "closing_value",
    label: "desktop.ledger.stock.closing.value",
    control: "money",
    required: true,
  },
  {
    key: "basis",
    label: "desktop.ledger.stock.closing.basis",
    control: "choice",
    required: true,
  },
];

// ---- What the person has typed -----------------------------------------------

/** A file a purchase or a closing value rests on: what the backend named it
 * by once it kept it, the kind of proof, and the mark it answered. Both are
 * empty until a file is kept, and neither is drawn. */
export type ProofDraft = {
  reference: string;
  kind: string;
  digest: string;
  /** The file's bare name, where it is known; only ever shown. */
  fileName?: string;
};

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

/** A closing value: what is typed, and the files kept, by the role each
 * plays. A document that shows the prior year's closing is one more file. */
export type ClosingDraft = {
  values: Readonly<Record<string, string>>;
  decision: Readonly<Record<string, ProofDraft>>;
  count: Readonly<Record<string, ProofDraft>>;
  prior: readonly { key: string; proof: ProofDraft }[];
};

export const EMPTY_BOOK: BookDraft = { name: "", method: "", opening: "" };
export const EMPTY_CORRECTION: CorrectDraft = {
  reason: "",
  opening: "",
  method: "",
};
export const EMPTY_CLOSING: ClosingDraft = {
  values: {},
  decision: {},
  count: {},
  prior: [],
};

export const blankProof = (kind = ""): ProofDraft => ({
  reference: "",
  kind,
  digest: "",
});

export const blankExtra = (mint: () => string): ExtraDraft => ({
  key: mint(),
  kind: "",
  price: "",
  iva: "",
  share: "",
  proof: blankProof(),
});

/** A movement form's start: nothing typed, nothing kept. */
export function blankMovement(): MovementDraft {
  return {
    values: {},
    extras: [],
    proofs: {
      price: blankProof(),
      cost_check: blankProof(),
      iva_check: blankProof(),
    },
  };
}

const proofKept = (proof: ProofDraft) => proof.digest !== "";

/** Whether anything is typed or chosen that is not yet written. */
export function movementTouched(draft: MovementDraft): boolean {
  return (
    Object.values(draft.values).some((text) => text.trim() !== "") ||
    draft.extras.length > 0 ||
    Object.values(draft.proofs).some(proofKept)
  );
}

export function closingTouched(draft: ClosingDraft): boolean {
  return (
    Object.values(draft.values).some((text) => text.trim() !== "") ||
    Object.values(draft.decision).some(proofKept) ||
    Object.values(draft.count).some(proofKept) ||
    draft.prior.length > 0
  );
}

export const bookTouched = (draft: BookDraft): boolean =>
  Object.values(draft).some((text) => text.trim() !== "");

/** The draft a correction starts from: what the book kept of the movement,
 * so the person changes only what was wrong. */
export function draftOfMovement(
  movement: InventoryMovement,
  vocabulary: Vocabulary,
): MovementDraft {
  const blank = blankMovement();
  const text = (value: { decimal: string } | null | undefined) =>
    value ? heldDecimal(value.decimal) : "";
  const detail = movement.acquisition_detail ?? null;
  const cost = movement.acquisition_cost ?? null;
  const base: Record<string, string> = {
    date: movement.movement_date,
    kind: movement.kind,
    quantity: heldDecimal(movement.quantity.decimal),
  };
  if (!plays(vocabulary, "purchase", movement.kind))
    return {
      ...blank,
      values: {
        ...base,
        ...(movement.unit_cost ? { unit_cost: text(movement.unit_cost) } : {}),
        ...(movement.taxable_base
          ? { total_cost: text(movement.taxable_base) }
          : {}),
      },
    };
  if (cost === null || detail === null) return { ...blank, values: base };
  const held = (reference: string): ProofDraft => {
    const found = detail.documents.find(
      (document) => document.reference === reference,
    );
    return found
      ? {
          reference: found.reference,
          kind: found.evidence_kind,
          digest: found.content_digest,
          ...(found.file_name ? { fileName: found.file_name } : {}),
        }
      : blankProof();
  };
  const share = (fraction: PublicDecimal) =>
    heldDecimal(canonicalDecimal(fraction.decimal) ?? fraction.decimal);
  return {
    values: {
      ...base,
      price: text(cost.consideration_excluding_iva),
      iva: text(detail.consideration_iva_amount),
      share: share(detail.consideration_deductible_iva_ratio),
    },
    extras: detail.components.map((component) => ({
      key: component.component_id,
      kind: component.kind,
      price: text(component.taxable_base),
      iva: text(component.iva_amount),
      share: share(component.deductible_iva_ratio),
      proof: held(component.evidence_references[0] ?? ""),
    })),
    proofs: {
      price: held(detail.consideration_evidence),
      cost_check: held(detail.attributable_cost_review_evidence),
      iva_check: held(detail.iva_recoverability_review_evidence),
    },
  };
}

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
  const name = c.need("name", parseLine(draft.name, 120));
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
  const reason = c.need("reason", parseLine(text("reason"), 512));
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
    | { family: "correction"; token: string }
    | { family: "retirement"; token: string }
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
    if (entry.kind === "described") {
      // The first description displaced nothing, so it has no "before".
      if (entry.prior_descriptor !== null) {
        before.push({ kind: "label", value: entry.prior_descriptor.label });
        before.push({
          kind: "description",
          value: entry.prior_descriptor.description,
        });
      }
      const next = later.find((found) => found.kind === "described");
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
      // A reversal takes the movement out and puts none in its place.
      if (entry.replacement_movement_id === null)
        after.push({ kind: "removed" });
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
