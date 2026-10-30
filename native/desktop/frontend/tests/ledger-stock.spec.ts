import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";
import {
  BOOK_FIELDS,
  blankExtra,
  blankMovement,
  bookListed,
  bookName,
  bookRequest,
  bookTouched,
  COST_FIELDS,
  COST_KIND_KEYS,
  COST_KINDS,
  EMPTY_BOOK,
  EXTRA_FIELDS,
  fingerprintOf,
  KINDS,
  METHODS,
  MOVEMENT_FIELDS,
  movementCounted,
  movementRequest,
  movementTouched,
  PRICE_FIELDS,
  PROOF_KIND_KEYS,
  PROOF_KINDS,
  PROOF_SLOTS,
  TOTAL_FIELDS,
  type MovementDraft,
  type StockField,
} from "../src/components/ledger/assets/stockModel";
import type { InventoryBookRow } from "../src/shell/ledgerSetup";

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

/** A purchase of 100 units for 1000.00 with 210.00 of IVA, all deductible. */
function purchase(mint = minter()): MovementDraft {
  const start = blankMovement(mint);
  return {
    values: {
      date: "2026-03-04",
      kind: "purchase",
      quantity: "100",
      price: "1000.00",
      iva: "210.00",
      share: "100",
      extra_total: "0",
      recoverable: "210.00",
      unrecoverable: "0",
      total: "1000.00",
    },
    extras: [],
    proofs: {
      price: {
        ...start.proofs.price,
        kind: "purchase_invoice",
        digest: MARK("a"),
      },
      cost_check: { ...start.proofs.cost_check, digest: MARK("b") },
      iva_check: { ...start.proofs.iva_check, digest: MARK("c") },
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
    ...blankMovement(minter()),
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
    ...blankMovement(minter()),
    values: { date: "2026-11-20", kind: "cogs", quantity: "60" },
  });
  expect(sale.request).toMatchObject({ unit_cost: null, taxable_base: null });
  expect(sale.request).not.toHaveProperty("acquisition_cost");
});

test("a purchase states what it cost and what it rests on, and no unit cost or total beside it", () => {
  const made = movementRequest(BOOK, "movement-3", purchase());

  expect(made.problems).toEqual({});
  expect(made.request).not.toHaveProperty("unit_cost");
  expect(made.request).not.toHaveProperty("taxable_base");
  expect(made.request?.acquisition_cost).toEqual({
    consideration_excluding_iva: { decimal: "1000" },
    consideration_iva_amount: { decimal: "210" },
    consideration_deductible_iva_ratio: { decimal: "1" },
    attributable_cost_components: [],
    evidence: [
      {
        reference: { reference: "reference-1" },
        evidence_kind: "purchase_invoice",
        content_digest: MARK("a"),
      },
      {
        reference: { reference: "reference-2" },
        evidence_kind: "attributable_cost_review",
        content_digest: MARK("b"),
      },
      {
        reference: { reference: "reference-3" },
        evidence_kind: "iva_recoverability_review",
        content_digest: MARK("c"),
      },
    ],
    completeness: {
      consideration_evidence: { reference: "reference-1" },
      attributable_cost_review_evidence: { reference: "reference-2" },
      iva_recoverability_review_evidence: { reference: "reference-3" },
    },
    directly_attributable_cost_total: { decimal: "0" },
    nonrecoverable_iva_included: { decimal: "0" },
    recoverable_iva_excluded: { decimal: "210" },
    total_acquisition_cost: { decimal: "1000" },
  });
});

test("each extra cost brings its own component and its own file, and the figures are the person's", () => {
  const mint = minter();
  const draft = purchase(mint);
  const extra = blankExtra(mint);
  const made = movementRequest(BOOK, "movement-4", {
    ...draft,
    values: {
      ...draft.values,
      extra_total: "100",
      recoverable: "231",
      total: "1100",
    },
    extras: [
      {
        ...extra,
        kind: "freight",
        price: "100.00",
        iva: "21.00",
        share: "100",
        proof: {
          ...extra.proof,
          kind: "transport_document",
          digest: MARK("d"),
        },
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
      evidence_references: [{ reference: extra.proof.reference }],
    },
  ]);
  expect(cost?.evidence.map((proof) => proof.evidence_kind)).toEqual([
    "purchase_invoice",
    "transport_document",
    "attributable_cost_review",
    "iva_recoverability_review",
  ]);
  // The totals are sent as typed; the builder adds nothing up.
  expect(cost?.total_acquisition_cost).toEqual({ decimal: "1100" });
  expect(cost?.directly_attributable_cost_total).toEqual({ decimal: "100" });
});

test("a purchase without a file, a kind, a total or a clean number makes no request and says where", () => {
  const whole = purchase();

  const noFile = movementRequest(BOOK, "m", {
    ...whole,
    proofs: {
      ...whole.proofs,
      iva_check: { ...whole.proofs.iva_check, digest: "" },
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

  const noTotal = movementRequest(BOOK, "m", {
    ...whole,
    values: { ...whole.values, total: "" },
  });
  expect(noTotal.request).toBeNull();
  expect(noTotal.missing.has("total")).toBe(true);

  const grouped = movementRequest(BOOK, "m", {
    ...whole,
    values: { ...whole.values, price: "1,000.00" },
  });
  expect(grouped.request).toBeNull();
  expect(grouped.problems.price).toBeDefined();
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
    ...blankMovement(minter()),
    values: { date: "2026-12-31", kind: "count", quantity: "2" },
  });
  expect(made.request).toMatchObject({ unit_cost: null, taxable_base: null });
  const zero = movementRequest(BOOK, "m", {
    ...blankMovement(minter()),
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
  ...TOTAL_FIELDS,
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
  const mint = minter();
  const typed: MovementDraft = {
    ...blankMovement(mint),
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

test("the references a form mints are its own, one for each file and extra cost, and differ", () => {
  const mint = minter();
  const draft = blankMovement(mint);
  const extra = blankExtra(mint);
  const references = [
    ...Object.values(draft.proofs).map((proof) => proof.reference),
    extra.key,
    extra.proof.reference,
  ];
  expect(new Set(references).size).toBe(references.length);
  expect(references.every((reference) => reference !== "")).toBe(true);
});

test("a form is touched once something is typed or attached, and not before", () => {
  expect(bookTouched(EMPTY_BOOK)).toBe(false);
  expect(bookTouched({ ...EMPTY_BOOK, name: "Papelería" })).toBe(true);
  const blank = blankMovement(minter());
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
    ...source.matchAll(/["'`](desktop\.ledger\.[A-Za-z0-9_.]+)["'`$]/g),
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
    const keys = new Set([
      ...Object.keys(words).filter(owned),
      ...whole,
      ...Object.keys(words).filter((key) =>
        families.some((family) => key.startsWith(family)),
      ),
    ]);
    expect(keys.size).toBeGreaterThan(80);
    for (const key of keys) {
      const text = (words[key] ?? "").replace(/\{\w+\}/g, "");
      expect(text, `${language} ${key}`).not.toMatch(
        DEVELOPMENT_WORDS[language],
      );
    }
  }
});

test("the choices the panel offers are worded in every language", () => {
  const choices = [
    ...METHODS.map((token) => `desktop.ledger.inventory.method.${token}`),
    ...KINDS.map((token) => `desktop.ledger.inventory.kind.${token}`),
    ...COST_KINDS.map((token) => COST_KIND_KEYS[token]),
    ...PROOF_KINDS.map((token) => PROOF_KIND_KEYS[token]),
  ];
  for (const language of LANGUAGES)
    for (const key of choices)
      expect(catalogue[language]?.[key], `${language} ${key}`).toBeTruthy();
  // No two choices of one list read the same.
  for (const language of LANGUAGES) {
    const kinds = COST_KINDS.map(
      (token) => catalogue[language]![COST_KIND_KEYS[token]],
    );
    expect(new Set(kinds).size).toBe(kinds.length);
  }
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

// ---- Files ---------------------------------------------------------------------------

test("a file's mark is the SHA-256 of its bytes, in lowercase hex", async () => {
  const bytes = new TextEncoder().encode("abc");
  expect(await fingerprintOf(bytes.buffer as ArrayBuffer)).toBe(
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
  expect(await fingerprintOf(new ArrayBuffer(0))).toBe(
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  );
});
