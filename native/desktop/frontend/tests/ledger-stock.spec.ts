import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";
import {
  BOOK_FIELDS,
  blankExtra,
  blankMovement,
  blankProof,
  bookListed,
  bookName,
  bookRequest as buildBook,
  bookTouched,
  CLOSING_FIELDS,
  closingLanded,
  closingRequest as buildClosing,
  closingTouched,
  COST_FIELDS,
  COUNT_FIELDS,
  CORRECT_FIELDS,
  correctRequest as buildCorrect,
  DESCRIBE_FIELDS,
  describeRequest,
  changeLanded,
  draftOfMovement,
  EMPTY_BOOK,
  EMPTY_CLOSING,
  historyRows,
  LABEL_FAMILY,
  movementCorrectionRequest as buildMovementCorrection,
  restoreRequest,
  retireRequest as buildRetire,
  reverseRequest as buildReverse,
  EXTRA_FIELDS,
  MOVEMENT_FIELDS,
  movementCounted,
  NO_VOCABULARY,
  movementRequest as buildMovement,
  movementTouched,
  offersOf,
  PRICE_FIELDS,
  plays,
  priceKinds,
  proofFromKept,
  PROOF_SLOTS,
  slotKinds,
  vocabularyOf,
  wordOf,
  type ClosingDraft,
  type Offers,
  type MovementDraft,
  type ProofDraft,
  type StockField,
} from "../src/components/ledger/assets/stockModel";
import type {
  InventoryBook,
  InventoryEvidenceAddResult,
  InventoryBookRow,
  InventoryHistoryEntry,
  InventoryMovement,
  InventoryOptionsResult,
} from "../src/shell/ledgerSetup";

// The Stock panel's requests, and the words its forms use. No page is opened.
// A request is built from the fields of a form and from nothing the person
// cannot see; the backend's own contracts decode the same builders' output in
// a test of theirs.

const catalogue = JSON.parse(
  readFileSync(
    resolve(buildPath("desktop_frontend_generated"), "chrome-strings.json"),
    "utf8",
  ),
) as Record<string, Record<string, string>>;
const LANGUAGES = ["en", "es", "ca", "hu"] as const;

/** A reference minted in order, so a request can be compared whole. */
function minter() {
  let count = 0;
  return () => `reference-${(count += 1)}`;
}

const BOOK = { actividad_id: "Papelería y reprografía", year: 2026 };
const MARK = (character: string) => character.repeat(64);

/** What the options read serves, as it serves it: each closed choice with the
 * key of its word. The backend's own contracts decode the same builders'
 * output against the vocabulary it really serves in a test of theirs. */
const SERVED: Record<string, string[]> = {
  acquisition_evidence_kind: [
    "purchase_invoice",
    "transport_document",
    "insurance_document",
    "customs_declaration",
    "contract",
    "other_acquisition_evidence",
    "attributable_cost_review",
    "iva_recoverability_review",
  ],
  attributable_cost_kind: [
    "freight",
    "insurance",
    "customs_duty",
    "handling",
    "professional_fee",
    "other_directly_attributable",
  ],
  closing_authority: ["movement_derived", "physical_observation"],
  closing_valuation_basis: [
    "fifo_acquisition_price",
    "pmp_acquisition_price",
    "coste_medio_acquisition_price",
  ],
  correction_reason: [
    "keying_error",
    "source_document_corrected",
    "duplicate_entry",
    "operation_did_not_occur",
  ],
  decision_evidence_role: ["authority_reconciliation"],
  history_kind: [
    "described",
    "opening_corrected",
    "movement_corrected",
    "movement_reversed",
    "retired",
    "restored",
  ],
  movement_kind: ["opening", "purchase", "cogs", "count"],
  physical_evidence_role: ["physical_count", "acquisition_price_valuation"],
  retirement_reason: ["created_in_error", "activity_ceased", "no_stock_held"],
  valuation_method: ["fifo", "pmp", "coste_medio"],
};
/** The part the options read gives a member, as it gives it. */
const SERVED_ROLES: Record<string, string> = {
  attributable_cost_review: "cost_check",
  iva_recoverability_review: "iva_check",
  physical_observation: "count_authority",
  purchase: "purchase",
};
const ROLED_FAMILIES = [
  "acquisition_evidence_kind",
  "closing_authority",
  "movement_kind",
];
const OPTIONS: InventoryOptionsResult = {
  profile_id: "synthetic",
  families: Object.entries(SERVED).map(([family, values]) => ({
    family,
    options: values.map((value) => ({
      value,
      label_key: `application.inventory.labels.${family}.${value}`,
      role: ROLED_FAMILIES.includes(family)
        ? (SERVED_ROLES[value] ?? null)
        : null,
    })),
  })),
};
const VOCABULARY = vocabularyOf(offersOf(OPTIONS));

const bookRequest = (year: number, draft: Parameters<typeof buildBook>[1]) =>
  buildBook(year, draft, VOCABULARY);
const movementRequest = (
  book: Parameters<typeof buildMovement>[0],
  id: string,
  draft: MovementDraft,
) => buildMovement(book, id, draft, VOCABULARY);
const correctRequest = (
  book: Parameters<typeof buildCorrect>[0],
  id: string,
  draft: Parameters<typeof buildCorrect>[2],
) => buildCorrect(book, id, draft, VOCABULARY);
const movementCorrectionRequest = (
  book: Parameters<typeof buildMovementCorrection>[0],
  ids: Parameters<typeof buildMovementCorrection>[1],
  target: string,
  reason: string,
  draft: MovementDraft,
) => buildMovementCorrection(book, ids, target, reason, draft, VOCABULARY);
const reverseRequest = (
  book: Parameters<typeof buildReverse>[0],
  id: string,
  target: string,
  reason: string,
) => buildReverse(book, id, target, reason, VOCABULARY);
const retireRequest = (
  book: Parameters<typeof buildRetire>[0],
  id: string,
  reason: string,
) => buildRetire(book, id, reason, VOCABULARY);
const closingRequest = (
  ids: Parameters<typeof buildClosing>[1],
  draft: ClosingDraft,
) => buildClosing(BOOK, ids, draft, VOCABULARY);

/** A file the backend has kept, as the form holds it: what it named it by,
 * and the mark it answered. */
const kept = (character: string, kind = ""): ProofDraft => ({
  reference: `document-${MARK(character)}`,
  kind,
  digest: MARK(character),
});

/** A purchase of 100 units for 1000.00 with 210.00 of IVA, all deductible. */
function purchase(): MovementDraft {
  return {
    values: {
      date: "2026-03-04",
      kind: "purchase",
      quantity: "100",
      price: "1000.00",
      iva: "210.00",
      share: "100",
    },
    extras: [],
    proofs: {
      price: kept("a", "purchase_invoice"),
      cost_check: kept("b"),
      iva_check: kept("c"),
    },
  };
}

// ---- A book ------------------------------------------------------------------------

test("a book's fields make its request, in the year the panel stands on", () => {
  const made = bookRequest(2026, {
    name: "  Papelería y reprografía ",
    method: "fifo",
    opening: "410.00",
  });

  expect(made.problems).toEqual({});
  expect(made.request).toEqual({
    actividad_id: "Papelería y reprografía",
    year: 2026,
    valuation_method: "fifo",
    opening_stock: { decimal: "410" },
  });
});

test("a book still lacking a field, or with a refused one, makes no request and says which", () => {
  const empty = bookRequest(2026, EMPTY_BOOK);
  expect(empty.request).toBeNull();
  expect([...empty.missing].sort()).toEqual(["method", "name", "opening"]);

  const comma = bookRequest(2026, {
    name: "Papelería",
    method: "pmp",
    opening: "410,00",
  });
  expect(comma.request).toBeNull();
  expect(comma.problems.opening?.key).toBe("comma_decimal");

  // A method outside the enum is not one the form can send.
  expect(
    bookRequest(2026, { name: "Papelería", method: "lifo", opening: "0" })
      .request,
  ).toBeNull();
});

test("an opening value of nothing is a value the person must state, not a default", () => {
  expect(
    bookRequest(2026, { name: "Papelería", method: "fifo", opening: "" })
      .request,
  ).toBeNull();
  expect(
    bookRequest(2026, { name: "Papelería", method: "fifo", opening: "0" })
      .request?.opening_stock,
  ).toEqual({ decimal: "0" });
});

// ---- A movement --------------------------------------------------------------------

test("a movement other than a purchase states a cost per unit, a total, or neither, and no cost evidence", () => {
  const perUnit = movementRequest(BOOK, "movement-1", {
    ...blankMovement(),
    values: {
      date: "2026-01-02",
      kind: "opening",
      quantity: "100",
      unit_cost: "4.10",
    },
  });
  expect(perUnit.request).toEqual({
    actividad_id: BOOK.actividad_id,
    year: 2026,
    movement_id: "movement-1",
    movement_date: "2026-01-02",
    kind: "opening",
    quantity: { decimal: "100" },
    unit_cost: { decimal: "4.1" },
    taxable_base: null,
  });

  const sale = movementRequest(BOOK, "movement-2", {
    ...blankMovement(),
    values: { date: "2026-11-20", kind: "cogs", quantity: "60" },
  });
  expect(sale.request).toMatchObject({ unit_cost: null, taxable_base: null });
  expect(sale.request).not.toHaveProperty("acquisition_cost");
});

test("a purchase states what it cost and what it rests on, and no unit cost, total or sum beside it", () => {
  const made = movementRequest(BOOK, "movement-3", purchase());

  expect(made.problems).toEqual({});
  expect(made.request).not.toHaveProperty("unit_cost");
  expect(made.request).not.toHaveProperty("taxable_base");
  const cost = made.request?.acquisition_cost;
  expect(cost).toEqual({
    consideration_excluding_iva: { decimal: "1000" },
    consideration_iva_amount: { decimal: "210" },
    consideration_deductible_iva_ratio: { decimal: "1" },
    attributable_cost_components: [],
    evidence: [
      {
        reference: { reference: `document-${MARK("a")}` },
        evidence_kind: "purchase_invoice",
        content_digest: MARK("a"),
      },
      {
        reference: { reference: `document-${MARK("b")}` },
        evidence_kind: "attributable_cost_review",
        content_digest: MARK("b"),
      },
      {
        reference: { reference: `document-${MARK("c")}` },
        evidence_kind: "iva_recoverability_review",
        content_digest: MARK("c"),
      },
    ],
    completeness: {
      consideration_evidence: { reference: `document-${MARK("a")}` },
      attributable_cost_review_evidence: {
        reference: `document-${MARK("b")}`,
      },
      iva_recoverability_review_evidence: {
        reference: `document-${MARK("c")}`,
      },
    },
  });
  // What the purchase comes to is the backend's to add up: none of it is sent.
  for (const total of [
    "directly_attributable_cost_total",
    "nonrecoverable_iva_included",
    "recoverable_iva_excluded",
    "total_acquisition_cost",
  ])
    expect(cost, total).not.toHaveProperty(total);
});

test("each extra cost brings its own component and its own file, and no sum", () => {
  const draft = purchase();
  const extra = blankExtra(minter());
  const made = movementRequest(BOOK, "movement-4", {
    ...draft,
    extras: [
      {
        ...extra,
        kind: "freight",
        price: "100.00",
        iva: "21.00",
        share: "100",
        proof: kept("d", "transport_document"),
      },
    ],
  });

  const cost = made.request?.acquisition_cost;
  expect(cost?.attributable_cost_components).toEqual([
    {
      component_id: extra.key,
      kind: "freight",
      taxable_base: { decimal: "100" },
      iva_amount: { decimal: "21" },
      deductible_iva_ratio: { decimal: "1" },
      evidence_references: [{ reference: `document-${MARK("d")}` }],
    },
  ]);
  expect(cost?.evidence.map((proof) => proof.evidence_kind)).toEqual([
    "purchase_invoice",
    "transport_document",
    "attributable_cost_review",
    "iva_recoverability_review",
  ]);
  expect(cost).not.toHaveProperty("total_acquisition_cost");
});

test("a purchase without a file, a kind or a clean number makes no request and says where", () => {
  const whole = purchase();

  const noFile = movementRequest(BOOK, "m", {
    ...whole,
    proofs: {
      ...whole.proofs,
      iva_check: blankProof(),
    },
  });
  expect(noFile.request).toBeNull();
  expect(noFile.missing.has("iva_check:file")).toBe(true);

  const noKind = movementRequest(BOOK, "m", {
    ...whole,
    proofs: { ...whole.proofs, price: { ...whole.proofs.price, kind: "" } },
  });
  expect(noKind.request).toBeNull();
  expect(noKind.missing.has("price:kind")).toBe(true);

  // A kind outside what the backend serves is not one the form can send.
  const foreign = movementRequest(BOOK, "m", {
    ...whole,
    proofs: {
      ...whole.proofs,
      price: { ...whole.proofs.price, kind: "receipt" },
    },
  });
  expect(foreign.request).toBeNull();

  const grouped = movementRequest(BOOK, "m", {
    ...whole,
    values: { ...whole.values, price: "1,000.00" },
  });
  expect(grouped.request).toBeNull();
  expect(grouped.problems.price).toBeDefined();
});

test("a file that is not kept yet is not a proof, whatever kind it is given", () => {
  const whole = purchase();
  const unkept = movementRequest(BOOK, "m", {
    ...whole,
    proofs: {
      ...whole.proofs,
      price: { reference: "", kind: "purchase_invoice", digest: "" },
    },
  });
  expect(unkept.request).toBeNull();
  expect(unkept.missing.has("price:file")).toBe(true);
});

test("a share is a percentage the person writes, sent as the fraction the backend holds", () => {
  const whole = purchase();
  const half = movementRequest(BOOK, "m", {
    ...whole,
    values: { ...whole.values, share: "50" },
  });
  expect(
    half.request?.acquisition_cost?.consideration_deductible_iva_ratio,
  ).toEqual({
    decimal: "0.5",
  });
  // A bare 0.5 could be half or half of a per cent: it is not guessed.
  const fraction = movementRequest(BOOK, "m", {
    ...whole,
    values: { ...whole.values, share: "0.5" },
  });
  expect(fraction.request).toBeNull();
  expect(fraction.problems.share?.key).toBe("percent_as_fraction");
});

test("an unstated cost is unknown, never zero", () => {
  const made = movementRequest(BOOK, "m", {
    ...blankMovement(),
    values: { date: "2026-12-31", kind: "count", quantity: "2" },
  });
  expect(made.request).toMatchObject({ unit_cost: null, taxable_base: null });
  const zero = movementRequest(BOOK, "m", {
    ...blankMovement(),
    values: {
      date: "2026-12-31",
      kind: "count",
      quantity: "2",
      unit_cost: "0",
    },
  });
  expect(zero.request).toMatchObject({ unit_cost: { decimal: "0" } });
});

// ---- What the person sees ------------------------------------------------------------

const ALL_FIELDS: readonly StockField[] = [
  ...BOOK_FIELDS,
  ...MOVEMENT_FIELDS,
  ...COST_FIELDS,
  ...PRICE_FIELDS,
  ...EXTRA_FIELDS,
  ...DESCRIBE_FIELDS,
  ...CORRECT_FIELDS,
  ...CLOSING_FIELDS,
  ...COUNT_FIELDS,
];

test("no field is drawn for a reference the window mints", () => {
  const named =
    /(^|_)(id|ids|reference|references|digest|fingerprint|movement|component)(_|$)/;
  for (const field of ALL_FIELDS) {
    expect(field.key, field.key).not.toMatch(named);
    expect(field.label, field.label).not.toMatch(named);
  }
  for (const slot of PROOF_SLOTS) expect(slot.key).not.toMatch(named);

  // What is typed under any such name changes nothing the request sends.
  const typed: MovementDraft = {
    ...blankMovement(),
    values: {
      movement_id: "typed",
      reference: "typed",
      date: "2026-01-02",
      kind: "opening",
      quantity: "1",
      unit_cost: "1",
    },
  };
  const made = movementRequest(BOOK, "minted", typed);
  expect(made.request?.movement_id).toBe("minted");
  expect(JSON.stringify(made.request)).not.toContain("typed");
});

test("the references a form mints are its own, one for each extra cost, and a file has none until it is kept", () => {
  const mint = minter();
  const draft = blankMovement();
  const first = blankExtra(mint);
  const second = blankExtra(mint);
  expect(first.key).not.toBe(second.key);
  expect(first.key).not.toBe("");
  // The name of a kept file is the backend's to give.
  const proofs = [...Object.values(draft.proofs), first.proof, second.proof];
  expect(proofs.every((proof) => proof.reference === "")).toBe(true);
  expect(proofs.every((proof) => proof.digest === "")).toBe(true);
});

test("a form is touched once something is typed or attached, and not before", () => {
  expect(bookTouched(EMPTY_BOOK)).toBe(false);
  expect(bookTouched({ ...EMPTY_BOOK, name: "Papelería" })).toBe(true);
  const blank = blankMovement();
  expect(movementTouched(blank)).toBe(false);
  expect(movementTouched({ ...blank, extras: [blankExtra(minter())] })).toBe(
    true,
  );
  expect(
    movementTouched({
      ...blank,
      proofs: {
        ...blank.proofs,
        price: { ...blank.proofs.price, digest: MARK("a") },
      },
    }),
  ).toBe(true);
});

/** The words of development a person keeping their books has no use for, in
 * each language the interface speaks. */
const DEVELOPMENT_WORDS: Record<(typeof LANGUAGES)[number], RegExp> = {
  en: /\b(answers?|requests?|operations?|reads?|reading|backend|tokens?|ids?|json|documents?|payloads?|authority|records?|data)\b/i,
  es: /\b(respuestas?|solicitud(es)?|peticion(es)?|peticiones|lectura|leer|documentos?|identificador(es)?|json|backend|tokens?|payload|autoridad)\b/i,
  ca: /\b(resposta(es)?|sol·licitud(s)?|peticions?|lectura|llegir|documents?|identificador(s)?|json|backend|tokens?|payload|autoritat)\b/i,
  // "választ" is to choose, not an answer: a word starts where no letter does.
  hu: /(?<!\p{L})(válasz(?!t)|kérés|olvas|dokumentum|azonosító|json|backend|token|payload|jogosultság)/iu,
};

/** Every chrome key the panel names, whole in its source, and the families the
 * panel builds a key from. */
function namedKeys(): { whole: string[]; families: string[] } {
  const source = ["StockPane.tsx", "stockModel.ts"]
    .map((file) =>
      readFileSync(
        fileURLToPath(
          new URL(`../src/components/ledger/assets/${file}`, import.meta.url),
        ),
        "utf8",
      ),
    )
    .join("\n");
  const found = [
    ...source.matchAll(
      /["'`]((?:desktop\.ledger|application\.inventory\.labels)\.[A-Za-z0-9_.]+)["'`$]/g,
    ),
  ].map((match) => match[1]!);
  return {
    whole: [...new Set(found.filter((key) => !key.endsWith(".")))],
    families: [...new Set(found.filter((key) => key.endsWith(".")))],
  };
}

test("every word the panel names exists in all four languages", () => {
  const { whole } = namedKeys();
  expect(whole.length).toBeGreaterThan(40);
  for (const language of LANGUAGES)
    for (const key of whole)
      expect(catalogue[language]?.[key], `${language} ${key}`).toBeTruthy();
});

test("no word the person can see, in any language, is development language", () => {
  const { whole, families } = namedKeys();
  const owned = (key: string) =>
    key.startsWith("desktop.ledger.stock.") ||
    key.startsWith("desktop.ledger.inventory.");
  for (const language of LANGUAGES) {
    const words = catalogue[language] ?? {};
    // The panel's own words and the inventory words it keeps, whole families
    // included, and the words it borrows from the other parts of the ledger.
    // The reasons and kinds the backend words itself are its catalogue's, not
    // this panel's to reword; its "source document" is the invoice or receipt
    // a bookkeeper calls by that name.
    const keys = new Set(
      [
        ...Object.keys(words).filter(owned),
        ...whole,
        ...Object.keys(words).filter((key) =>
          families.some((family) => key.startsWith(family)),
        ),
      ].filter((key) => !key.startsWith("application.")),
    );
    expect(keys.size).toBeGreaterThan(80);
    for (const key of keys) {
      const text = (words[key] ?? "").replace(/\{\w+\}/g, "");
      expect(text, `${language} ${key}`).not.toMatch(
        DEVELOPMENT_WORDS[language],
      );
    }
  }
});

test("every choice the backend serves is worded in every language", () => {
  const families = Object.entries(LABEL_FAMILY);
  for (const language of LANGUAGES)
    for (const [family, prefix] of families) {
      const served = SERVED[family] ?? [];
      for (const token of served)
        expect(
          catalogue[language]?.[`${prefix}${token}`],
          `${language} ${prefix}${token}`,
        ).toBeTruthy();
      // No two choices of one list read the same.
      const words = served.map(
        (token) => catalogue[language]![`${prefix}${token}`],
      );
      expect(new Set(words).size, `${language} ${family}`).toBe(words.length);
    }
});

test("a stored token is worded, and one without a word is unknown, never the token", () => {
  const t = (key: string) => catalogue.en?.[key] ?? key;
  expect(wordOf(t, "valuation_method", "fifo")).toBe(
    catalogue.en?.["application.inventory.labels.valuation_method.fifo"],
  );
  expect(wordOf(t, "valuation_method", "lifo")).toBe(
    catalogue.en?.["desktop.ledger.stock.unnamed"],
  );
  expect(wordOf(t, "valuation_method", null)).toBe(
    catalogue.en?.["desktop.ledger.stock.unnamed"],
  );
});

test("the panel holds no list of the choices the backend serves", () => {
  const source = ["StockPane.tsx", "stockModel.ts"]
    .map((file) =>
      readFileSync(
        fileURLToPath(
          new URL(`../src/components/ledger/assets/${file}`, import.meta.url),
        ),
        "utf8",
      ),
    )
    .join("\n");
  // The parts a form treats specially are read from the roles the options
  // read gives, so no value is named. ``physical_count`` is also the name of
  // a field of the closing request.
  const named = new Set(["physical_count"]);
  for (const [family, tokens] of Object.entries(SERVED))
    for (const token of tokens)
      if (
        !named.has(token) &&
        (token.includes("_") ||
          ["fifo", "pmp", "cogs", "freight"].includes(token))
      )
        expect(source, `${family} ${token}`).not.toMatch(
          new RegExp(`["'\`]${token}["'\`]`),
        );
});

test("the choices the options read serves are the vocabulary the builders judge by", () => {
  expect(VOCABULARY.values.valuation_method).toEqual(SERVED.valuation_method);
  expect(priceKinds(VOCABULARY)).toEqual([
    "purchase_invoice",
    "transport_document",
    "insurance_document",
    "customs_declaration",
    "contract",
    "other_acquisition_evidence",
  ]);
  expect(slotKinds("cost_check", VOCABULARY)).toEqual([
    "attributable_cost_review",
  ]);
  expect(slotKinds("iva_check", VOCABULARY)).toEqual([
    "iva_recoverability_review",
  ]);
  // Nothing is chosen until the choices are served.
  expect(
    bookRequest(2026, { name: "A", method: "fifo", opening: "0" }).request,
  ).not.toBeNull();
  expect(
    buildBook(2026, { name: "A", method: "fifo", opening: "0" }, NO_VOCABULARY)
      .request,
  ).toBeNull();
});

// ---- The books ---------------------------------------------------------------------

const row = (
  name: string,
  year: number,
  movements: number,
  label: string | null = null,
): InventoryBookRow => ({
  actividad_id: name,
  year,
  valuation_method: "fifo",
  opening_stock: { decimal: "0" },
  movement_count: movements,
  label,
});

test("a book is listed under the name given to it, else the activity it was started for", () => {
  expect(bookName(row("Papelería", 2026, 0))).toBe("Papelería");
  expect(bookName(row("Papelería", 2026, 0, "Tienda del centro"))).toBe(
    "Tienda del centro",
  );
  expect(bookName(row("Papelería", 2026, 0, "  "))).toBe("Papelería");
});

test("a book write held in doubt is judged on the books listed again", () => {
  const books = [row("Papelería", 2026, 3), row("Enmarcado", 2025, 0)];
  expect(bookListed(books, "Papelería", 2026)).toBe("saved");
  expect(bookListed(books, "Papelería", 2025)).toBe("not_saved");
  expect(bookListed([], "Papelería", 2026)).toBe("not_saved");
});

test("a movement write held in doubt landed only if its book now holds more movements", () => {
  const book = { actividad_id: "Papelería", year: 2026 };
  expect(movementCounted([row("Papelería", 2026, 4)], book, 3)).toBe("saved");
  expect(movementCounted([row("Papelería", 2026, 3)], book, 3)).toBe(
    "not_saved",
  );
  // A book that is not listed cannot be judged to hold more.
  expect(movementCounted([], book, 3)).toBe("not_saved");
});

// ---- Changing a book -----------------------------------------------------------------

const MOVEMENT_ID = "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32";

test("a change names its book and the reference minted for it, and nothing the person cannot see", () => {
  const book = { actividad_id: "Papelería", year: 2025 };

  expect(
    describeRequest(book, "change-1", {
      label: " Tienda del centro ",
      description: "",
    }).request,
  ).toEqual({
    actividad_id: "Papelería",
    year: 2025,
    correction_id: "change-1",
    label: "Tienda del centro",
    description: null,
  });
  expect(restoreRequest(book, "change-2")).toEqual({
    actividad_id: "Papelería",
    year: 2025,
    correction_id: "change-2",
  });
  expect(retireRequest(book, "change-3", "activity_ceased").request).toEqual({
    actividad_id: "Papelería",
    year: 2025,
    correction_id: "change-3",
    reason: "activity_ceased",
  });
  expect(
    reverseRequest(book, "change-4", MOVEMENT_ID, "duplicate_entry").request,
  ).toEqual({
    actividad_id: "Papelería",
    year: 2025,
    correction_id: "change-4",
    target_movement_id: MOVEMENT_ID,
    reason: "duplicate_entry",
  });
});

test("a reason is chosen from the backend's own list, and a change is not made without one", () => {
  const book = { actividad_id: "Papelería", year: 2025 };

  for (const made of [
    retireRequest(book, "c", ""),
    retireRequest(book, "c", "keying_error"),
    reverseRequest(book, "c", MOVEMENT_ID, ""),
    reverseRequest(book, "c", MOVEMENT_ID, "created_in_error"),
    correctRequest(book, "c", { reason: "", opening: "10", method: "" }),
  ]) {
    expect(made.request).toBeNull();
    expect(made.missing.has("reason")).toBe(true);
  }
  expect(
    describeRequest(book, "c", { label: " ", description: "" }).request,
  ).toBeNull();
});

test("a correction states what changes and leaves the rest as it is", () => {
  const book = { actividad_id: "Papelería", year: 2025 };

  expect(
    correctRequest(book, "c", {
      reason: "keying_error",
      opening: "380.00",
      method: "",
    }).request,
  ).toEqual({
    actividad_id: "Papelería",
    year: 2025,
    correction_id: "c",
    reason: "keying_error",
    opening_stock: { decimal: "380" },
    valuation_method: null,
  });
  expect(
    correctRequest(book, "c", {
      reason: "keying_error",
      opening: "",
      method: "pmp",
    }).request,
  ).toMatchObject({ opening_stock: null, valuation_method: "pmp" });
  // A value typed and refused is not turned into leaving it as it is.
  const refused = correctRequest(book, "c", {
    reason: "keying_error",
    opening: "38o",
    method: "",
  });
  expect(refused.request).toBeNull();
  expect(refused.problems.opening).toBeDefined();
});

test("a corrected movement is a movement of its own under a new reference, and names the one it replaces", () => {
  const book = { actividad_id: "Papelería", year: 2026 };
  const draft: MovementDraft = {
    ...blankMovement(),
    values: { date: "2026-11-20", kind: "cogs", quantity: "50" },
  };
  const made = movementCorrectionRequest(
    book,
    { correction: "change-5", movement: "movement-new" },
    MOVEMENT_ID,
    "source_document_corrected",
    draft,
  );

  expect(made.request).toEqual({
    actividad_id: "Papelería",
    year: 2026,
    correction_id: "change-5",
    target_movement_id: MOVEMENT_ID,
    reason: "source_document_corrected",
    movement_id: "movement-new",
    movement_date: "2026-11-20",
    kind: "cogs",
    quantity: { decimal: "50" },
    unit_cost: null,
    taxable_base: null,
  });
  const noReason = movementCorrectionRequest(
    book,
    { correction: "c", movement: "m" },
    MOVEMENT_ID,
    "",
    draft,
  );
  expect(noReason.request).toBeNull();
  expect(noReason.missing.has("reason")).toBe(true);
});

test("a change held in doubt landed only if the book's history now holds its reference", () => {
  const entry = (id: string): InventoryHistoryEntry => ({
    correction_id: id,
    kind: "retired",
    recorded_at: "2025-12-31T18:20:00Z",
    actor: "runtime",
    correction_reason: null,
    retirement_reason: "activity_ceased",
    superseded_movement: null,
    replacement_movement_id: null,
    prior_opening_stock: null,
    prior_valuation_method: null,
    prior_descriptor: null,
  });
  expect(changeLanded({ history: [entry("a"), entry("b")] }, "b")).toBe(
    "saved",
  );
  expect(changeLanded({ history: [entry("a")] }, "b")).toBe("not_saved");
  expect(changeLanded({ history: [] }, "b")).toBe("not_saved");
  // A book that could not be read cannot say.
  expect(changeLanded(null, "b")).toBe("untold");
});

// ---- The history ----------------------------------------------------------------------

const movement = (id: string, quantity: string): InventoryMovement => ({
  movement_id: id,
  movement_date: "2025-11-20",
  kind: "cogs",
  sku: "papel-a3",
  quantity: { decimal: quantity },
  unit_cost: null,
  taxable_base: null,
  iva_rate: { decimal: "0.21" },
  iva_amount: null,
  deductible_iva_ratio: { decimal: "1" },
});

const change = (
  id: string,
  day: string,
  kind: InventoryHistoryEntry["kind"],
  facts: Partial<InventoryHistoryEntry> = {},
): InventoryHistoryEntry => ({
  correction_id: id,
  kind,
  recorded_at: `${day}T09:30:00Z`,
  actor: "runtime",
  correction_reason: null,
  retirement_reason: null,
  superseded_movement: null,
  replacement_movement_id: null,
  prior_opening_stock: null,
  prior_valuation_method: null,
  prior_descriptor: null,
  ...facts,
});

const ledgerOf = (history: InventoryHistoryEntry[]): InventoryBook => ({
  actividad_id: "Papelería",
  year: 2025,
  valuation_method: "pmp",
  opening_stock: { decimal: "400" },
  period_movements: [movement("current", "60")],
  closing_authority_fingerprints: null,
  schema_version: "1",
  descriptor: { label: "Tienda", description: null },
  history,
});

test("the history lists the newest change first, with what each displaced and what took its place", () => {
  const rows = historyRows(
    ledgerOf([
      change("a", "2025-02-10", "opening_corrected", {
        correction_reason: "keying_error",
        prior_opening_stock: { decimal: "308" },
      }),
      change("b", "2025-03-01", "opening_corrected", {
        correction_reason: "keying_error",
        prior_opening_stock: { decimal: "380" },
        prior_valuation_method: "fifo",
      }),
      change("c", "2025-11-24", "movement_corrected", {
        correction_reason: "source_document_corrected",
        superseded_movement: movement("old", "50"),
        replacement_movement_id: "current",
      }),
      change("d", "2025-11-25", "movement_reversed", {
        correction_reason: "duplicate_entry",
        superseded_movement: movement("gone", "5"),
      }),
      change("e", "2025-12-01", "described", {
        prior_descriptor: { label: "Papel", description: "Antes" },
      }),
      change("f", "2025-12-31", "retired", {
        retirement_reason: "activity_ceased",
      }),
    ]),
  );

  expect(rows.map((row) => row.kind)).toEqual([
    "retired",
    "described",
    "movement_reversed",
    "movement_corrected",
    "opening_corrected",
    "opening_corrected",
  ]);
  expect(rows[0]).toMatchObject({
    day: "2025-12-31",
    reason: { family: "retirement", token: "activity_ceased" },
    before: [],
    after: [],
  });
  // Each opening value is found in the next change of it, else in the book.
  const second = rows[4];
  const first = rows[5];
  expect(first?.before).toEqual([{ kind: "opening", value: "308" }]);
  expect(first?.after).toEqual([{ kind: "opening", value: "380" }]);
  expect(second?.before).toEqual([
    { kind: "opening", value: "380" },
    { kind: "method", value: "fifo" },
  ]);
  expect(second?.after).toEqual([
    { kind: "opening", value: "400" },
    { kind: "method", value: "pmp" },
  ]);
  // What replaced a movement is the movement the book holds under its reference.
  expect(rows[3]?.after).toEqual([
    { kind: "movement", value: movement("current", "60") },
  ]);
  expect(rows[2]?.after).toEqual([{ kind: "removed" }]);
  expect(rows[1]?.before).toEqual([
    { kind: "label", value: "Papel" },
    { kind: "description", value: "Antes" },
  ]);
  expect(rows[1]?.after).toEqual([
    { kind: "label", value: "Tienda" },
    { kind: "description", value: null },
  ]);
});

test("a book never changed has no history, and the history carries no reference to show", () => {
  expect(historyRows(ledgerOf([]))).toEqual([]);
  const rows = historyRows(
    ledgerOf([
      change("secret-reference", "2025-02-10", "opening_corrected", {
        prior_opening_stock: { decimal: "308" },
      }),
    ]),
  );
  expect(JSON.stringify(rows)).not.toContain("secret-reference");
});

// ---- A closing value ---------------------------------------------------------------

const DECISION = {
  decision: "decision-1",
  decidedAt: "2026-12-31T10:00:00.000Z",
};

/** A closing value worked out from the movements, with the document that
 * shows it. */
function closing(): ClosingDraft {
  return {
    values: {
      authority: "movement_derived",
      reason: "Checked against the year's movements",
    },
    decision: {
      authority_reconciliation: kept("e", "authority_reconciliation"),
    },
    count: {},
    prior: [],
  };
}

test("a closing value states its facts, its documents and the reference minted for it, and no fingerprint", () => {
  const made = closingRequest(DECISION, closing());

  expect(made.problems).toEqual({});
  expect(made.request).toEqual({
    actividad_id: BOOK.actividad_id,
    year: 2026,
    facts: {
      decision_id: "decision-1",
      decided_at: "2026-12-31T10:00:00.000Z",
      authority: "movement_derived",
      reason: "Checked against the year's movements",
      decision_evidence: [
        {
          reference: { reference: `document-${MARK("e")}` },
          role: "authority_reconciliation",
          content_digest: MARK("e"),
        },
      ],
      physical_count: null,
      prior_evidence: [],
    },
  });
  expect(JSON.stringify(made.request)).not.toMatch(/fingerprint/);
});

test("a closing value from a count brings the count and a document for each part of it", () => {
  const draft: ClosingDraft = {
    ...closing(),
    values: {
      authority: "physical_observation",
      reason: "Counted on the last day",
      observed_on: "2026-12-31",
      closing_value: "410.00",
      basis: "fifo_acquisition_price",
    },
    count: {
      physical_count: kept("f", "physical_count"),
      acquisition_price_valuation: kept("1", "acquisition_price_valuation"),
    },
  };
  const made = closingRequest(DECISION, draft);

  expect(made.problems).toEqual({});
  expect(made.request?.facts.physical_count).toEqual({
    observed_on: "2026-12-31",
    closing_value: { decimal: "410" },
    valuation_basis: "fifo_acquisition_price",
    evidence: [
      {
        reference: { reference: `document-${MARK("f")}` },
        role: "physical_count",
        content_digest: MARK("f"),
      },
      {
        reference: { reference: `document-${MARK("1")}` },
        role: "acquisition_price_valuation",
        content_digest: MARK("1"),
      },
    ],
  });

  // A part of the count without its document is not a count.
  const short = closingRequest(DECISION, {
    ...draft,
    count: { physical_count: kept("f", "physical_count") },
  });
  expect(short.request).toBeNull();
  expect(short.missing.has("count:acquisition_price_valuation:file")).toBe(
    true,
  );
});

test("a closing value that is not yet complete makes no request and says what is missing", () => {
  const empty = closingRequest(DECISION, EMPTY_CLOSING);
  expect(empty.request).toBeNull();
  expect([...empty.missing].sort()).toEqual([
    "authority",
    "decision:authority_reconciliation:file",
    "reason",
  ]);
  // A document of last year's closing that is not kept stops the request.
  const prior = closingRequest(DECISION, {
    ...closing(),
    prior: [{ key: "p1", proof: blankProof() }],
  });
  expect(prior.request).toBeNull();
  expect(prior.missing.has("prior:p1:file")).toBe(true);
  const withPrior = closingRequest(DECISION, {
    ...closing(),
    prior: [{ key: "p1", proof: kept("2") }],
  });
  expect(withPrior.request?.facts.prior_evidence).toEqual([
    {
      reference: { reference: `document-${MARK("2")}` },
      content_digest: MARK("2"),
    },
  ]);
  expect(closingTouched(EMPTY_CLOSING)).toBe(false);
  expect(closingTouched(closing())).toBe(true);
});

test("a closing value held in doubt landed only if the book now holds one", () => {
  expect(closingLanded(null)).toBe("untold");
  expect(closingLanded({ closing_authority_fingerprints: null })).toBe(
    "not_saved",
  );
  expect(
    closingLanded({ closing_authority_fingerprints: { record: "x" } }),
  ).toBe("saved");
});

// ---- What a purchase was kept as ----------------------------------------------------

test("correcting a purchase starts from what the book kept of it, so only what was wrong is stated again", () => {
  const invoice = MARK("a");
  const transport = MARK("d");
  const costCheck = MARK("b");
  const ivaCheck = MARK("c");
  const kind = (digest: string, evidence_kind: "purchase_invoice") => ({
    reference: `attachment:${digest}`,
    evidence_kind,
    content_digest: digest,
  });
  const bought: InventoryMovement = {
    ...movement("p1", "100"),
    kind: "purchase",
    movement_date: "2026-03-04",
    acquisition_cost: {
      consideration_excluding_iva: { decimal: "1000" },
      directly_attributable_cost_total: { decimal: "100.00" },
      nonrecoverable_iva_included: { decimal: "0.00" },
      recoverable_iva_excluded: { decimal: "231.00" },
      total_acquisition_cost: { decimal: "1100.00" },
      component_count: 1,
      evidence_count: 4,
      complete: true,
    },
    acquisition_detail: {
      consideration_iva_amount: { decimal: "210" },
      consideration_deductible_iva_ratio: { decimal: "1" },
      components: [
        {
          component_id: "freight-1",
          kind: "freight",
          taxable_base: { decimal: "100" },
          iva_amount: { decimal: "21" },
          deductible_iva_ratio: { decimal: "0.5" },
          evidence_references: [`attachment:${transport}`],
        },
      ],
      documents: [
        kind(invoice, "purchase_invoice"),
        {
          reference: `attachment:${transport}`,
          evidence_kind: "transport_document",
          content_digest: transport,
        },
        {
          reference: `attachment:${costCheck}`,
          evidence_kind: "attributable_cost_review",
          content_digest: costCheck,
        },
        {
          reference: `attachment:${ivaCheck}`,
          evidence_kind: "iva_recoverability_review",
          content_digest: ivaCheck,
        },
      ],
      consideration_evidence: `attachment:${invoice}`,
      attributable_cost_review_evidence: `attachment:${costCheck}`,
      iva_recoverability_review_evidence: `attachment:${ivaCheck}`,
    },
  };

  const draft = draftOfMovement(bought, VOCABULARY);
  expect(draft.values).toMatchObject({
    kind: "purchase",
    price: "1000",
    iva: "210",
    share: "100",
  });
  // A share comes back as the percentage the person writes.
  expect(draft.extras[0]).toMatchObject({
    key: "freight-1",
    kind: "freight",
    price: "100",
    share: "50",
  });
  const sent = movementRequest(BOOK, "movement-new", draft);
  expect(sent.problems).toEqual({});
  expect(sent.request?.acquisition_cost?.evidence).toHaveLength(4);
  expect(
    sent.request?.acquisition_cost?.attributable_cost_components[0]
      ?.evidence_references,
  ).toEqual([{ reference: `attachment:${transport}` }]);
});

// ---- Roles, refused files and the names of kept files --------------------------------

test("the parts a form treats specially are read from the roles the options serve", () => {
  expect(VOCABULARY.roles).toEqual({
    cost_check: "attributable_cost_review",
    iva_check: "iva_recoverability_review",
    count_authority: "physical_observation",
    purchase: "purchase",
  });
  expect(plays(VOCABULARY, "purchase", "purchase")).toBe(true);
  expect(plays(VOCABULARY, "purchase", "cogs")).toBe(false);

  // The same choices under other values: the forms follow the roles.
  const renamed: Offers = offersOf({
    profile_id: "synthetic",
    families: [
      {
        family: "movement_kind",
        options: [
          { value: "alta", label_key: "k.alta", role: null },
          { value: "compra", label_key: "k.compra", role: "purchase" },
        ],
      },
      {
        family: "acquisition_evidence_kind",
        options: [
          { value: "factura", label_key: "k.factura", role: null },
          { value: "nota_costes", label_key: "k.nc", role: "cost_check" },
          { value: "nota_iva", label_key: "k.ni", role: "iva_check" },
        ],
      },
    ],
  });
  const vocabulary = vocabularyOf(renamed);
  expect(slotKinds("cost_check", vocabulary)).toEqual(["nota_costes"]);
  expect(slotKinds("iva_check", vocabulary)).toEqual(["nota_iva"]);
  expect(priceKinds(vocabulary)).toEqual(["factura"]);
  const draft: MovementDraft = {
    ...purchase(),
    values: { ...purchase().values, kind: "compra" },
    proofs: {
      price: kept("a", "factura"),
      cost_check: kept("b"),
      iva_check: kept("c"),
    },
  };
  const made = buildMovement(BOOK, "m", draft, vocabulary);
  expect(made.problems).toEqual({});
  expect(
    made.request?.acquisition_cost?.evidence.map(
      (proof) => proof.evidence_kind,
    ),
  ).toEqual(["factura", "nota_costes", "nota_iva"]);
  // A value no role names is not a purchase, whatever it is called.
  const plain = buildMovement(
    BOOK,
    "m",
    { ...draft, values: { ...draft.values, kind: "purchase" } },
    vocabulary,
  );
  expect(plain.request).toBeNull();
});

test("a count is the closing authority the options give that role", () => {
  const draft: ClosingDraft = {
    ...closing(),
    values: {
      authority: "physical_observation",
      reason: "Counted",
      observed_on: "2026-12-31",
      closing_value: "10",
      basis: "fifo_acquisition_price",
    },
    count: {
      physical_count: kept("f", "physical_count"),
      acquisition_price_valuation: kept("1", "acquisition_price_valuation"),
    },
  };
  expect(
    closingRequest(DECISION, draft).request?.facts.physical_count,
  ).not.toBeNull();
  // Without the role served, nothing marks a count and none is stated.
  const unmarked = buildClosing(BOOK, DECISION, draft, {
    ...VOCABULARY,
    roles: {},
  });
  expect(unmarked.request?.facts.physical_count).toBeNull();
});

test("a file the book did not keep makes no proof, and one it kept makes one under the name the person saw", () => {
  const stored: InventoryEvidenceAddResult = {
    outcome: "stored",
    profile_id: "synthetic",
    reference: `document-${MARK("a")}`,
    content_digest: MARK("a"),
    refusal: null,
  };
  expect(proofFromKept(stored, "factura.pdf")).toEqual({
    reference: `document-${MARK("a")}`,
    kind: "",
    digest: MARK("a"),
    fileName: "factura.pdf",
  });
  const refused: InventoryEvidenceAddResult = {
    outcome: "refused",
    profile_id: "synthetic",
    reference: null,
    content_digest: null,
    refusal: {
      code: "REFUSED_INVENTORY_SERVICE_INPUT",
      reason: "evidence_file_not_admitted",
      actividad_id: null,
      year: null,
      movement_id: null,
      valuation_method: null,
      reason_key:
        "application.inventory.service.errors.evidence_file_not_admitted",
      reason_facts: [],
    },
  };
  expect(proofFromKept(refused, "nota.docx")).toBeNull();
  // A result that claims to be kept but names nothing is not one.
  expect(proofFromKept({ ...stored, reference: null }, "x.pdf")).toBeNull();
  // The sentence for a refused file reaches the shell in every language.
  for (const language of LANGUAGES)
    expect(
      catalogue[language]?.[
        "application.inventory.service.errors.evidence_file_not_admitted"
      ],
    ).toBeTruthy();
});

test("a purchase's files come back named where the book knows the name, and as an opaque reference either way", () => {
  const named = MARK("a");
  const unnamed = MARK("b");
  const bought: InventoryMovement = {
    ...movement("p2", "10"),
    kind: "purchase",
    movement_date: "2026-03-04",
    acquisition_cost: {
      consideration_excluding_iva: { decimal: "100" },
      directly_attributable_cost_total: { decimal: "0.00" },
      nonrecoverable_iva_included: { decimal: "0.00" },
      recoverable_iva_excluded: { decimal: "21.00" },
      total_acquisition_cost: { decimal: "100.00" },
      component_count: 0,
      evidence_count: 3,
      complete: true,
    },
    acquisition_detail: {
      consideration_iva_amount: { decimal: "21" },
      consideration_deductible_iva_ratio: { decimal: "1" },
      components: [],
      documents: [
        {
          // A purchase kept before the form of a reference changed.
          reference: `attachment:${named}`,
          evidence_kind: "purchase_invoice",
          content_digest: named,
          file_name: "factura-papeleria.pdf",
        },
        {
          reference: `document-${unnamed}`,
          evidence_kind: "attributable_cost_review",
          content_digest: unnamed,
          file_name: null,
        },
        {
          reference: `document-${MARK("c")}`,
          evidence_kind: "iva_recoverability_review",
          content_digest: MARK("c"),
        },
      ],
      consideration_evidence: `attachment:${named}`,
      attributable_cost_review_evidence: `document-${unnamed}`,
      iva_recoverability_review_evidence: `document-${MARK("c")}`,
    },
  };
  const draft = draftOfMovement(bought, VOCABULARY);

  expect(draft.proofs.price.fileName).toBe("factura-papeleria.pdf");
  expect(draft.proofs.cost_check.fileName).toBeUndefined();
  expect(draft.proofs.iva_check.fileName).toBeUndefined();
  // Whatever its form, the reference is sent back as it was served.
  const sent = movementRequest(BOOK, "movement-new", draft);
  expect(sent.problems).toEqual({});
  expect(
    sent.request?.acquisition_cost?.completeness.consideration_evidence,
  ).toEqual({ reference: `attachment:${named}` });
  expect(
    sent.request?.acquisition_cost?.completeness
      .attributable_cost_review_evidence,
  ).toEqual({ reference: `document-${unnamed}` });
  // A name is shown and never sent.
  expect(JSON.stringify(sent.request)).not.toContain("factura-papeleria");
});
