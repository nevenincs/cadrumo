// The scenario ledger's inventory books: their movements, closing values,
// corrections and retirements, and the options and valuations the books
// are read through. Everything it answers is synthetic.

import type {
  JsonObject,
  JsonValue,
  LedgerDefinitionId,
} from "../shell/ledger";
import { SCENARIO_TODAY } from "./assetsRegister";
import {
  DATE,
  SetupStopped,
  decimal,
  decimalOf,
  fromKeys,
  invalid,
  required,
  servedRefusal,
  whole,
  type Handler,
  type Tools,
} from "./ledgerSetupSupport";
import { fixtureDay, fixtureInstant } from "@/dev/fixtureDates";

/** The year the scenario stands in, and the one before it: the two years the
 * books are kept for. */
const SCENARIO_YEAR = Number(SCENARIO_TODAY.slice(0, 4));
const PRIOR_YEAR = SCENARIO_YEAR - 1;

/** Reasons the catalogue names otherwise than the typed reason is. */
const REASON_KEY_NAMES: Record<string, string> = {
  activity_conflict: "actividad_conflict",
  activity_not_found: "actividad_not_found",
};
const VALUATION = ["fifo", "pmp", "coste_medio"];
const MOVEMENT_KINDS = ["opening", "purchase", "cogs", "count"];
const CLOSING_AUTHORITIES = ["movement_derived", "physical_observation"];
const DECISION_ROLES = ["authority_reconciliation"];
const PHYSICAL_ROLES = ["physical_count", "acquisition_price_valuation"];
const CLOSING_BASES = [
  "fifo_acquisition_price",
  "pmp_acquisition_price",
  "coste_medio_acquisition_price",
];
/** The part a member plays in a form, where it plays one. */
const OPTION_ROLES: Record<string, string> = {
  attributable_cost_review: "cost_check",
  iva_recoverability_review: "iva_check",
  physical_observation: "count_authority",
  purchase: "purchase",
};
/** The closed choices the options read serves, each with its members. */
const OPTION_FAMILIES: Record<string, readonly string[]> = {
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
  closing_authority: CLOSING_AUTHORITIES,
  closing_valuation_basis: CLOSING_BASES,
  correction_reason: [
    "keying_error",
    "source_document_corrected",
    "duplicate_entry",
    "operation_did_not_occur",
  ],
  decision_evidence_role: DECISION_ROLES,
  history_kind: [
    "described",
    "opening_corrected",
    "movement_corrected",
    "movement_reversed",
    "ledger_row_stated",
    "retired",
    "restored",
  ],
  movement_kind: MOVEMENT_KINDS,
  physical_evidence_role: PHYSICAL_ROLES,
  retirement_reason: ["created_in_error", "activity_ceased", "no_stock_held"],
  valuation_method: VALUATION,
};

type Book = {
  actividad_id: string;
  year: number;
  valuation_method: string;
  opening_stock: string;
  movements: JsonObject[];
  closing: JsonObject | null;
  /** The details given to the book. */
  label?: string;
  description?: string | null;
  retired?: boolean;
  retirement?: string | null;
  /** A closing value is recorded for the year, so its stock cannot change. */
  closingRecorded?: boolean;
  /** The decision the recorded closing value was made under. */
  closingDecision?: string;
  /** Every change, oldest first, with what it displaced. */
  history: JsonObject[];
};

/** The scenario ledger's inventory answers. */
export function inventoryOperations(
  tools: Tools,
  /** The active ledger transactions a purchase may name, with the currency
   * each is kept in. */
  transactions: () => readonly { id: string; currency: string }[] = () => [],
) {
  const { profileId, hex64, events, now } = tools;
  const served = servedRefusal(tools.language);
  const books: Book[] = [
    {
      actividad_id: "Papelería y reprografía",
      year: SCENARIO_YEAR,
      valuation_method: "fifo",
      opening_stock: "410",
      movements: [
        {
          movement_id: "b1f7c6d2-5f0e-4a43-9d53-2c9a6c1e7a10",
          movement_date: fixtureDay(1, 2),
          kind: "opening",
          sku: "papel-a3",
          quantity: decimal("100"),
          unit_cost: decimal("4.1"),
          taxable_base: decimal("410"),
          iva_rate: decimal("0.21"),
          iva_amount: decimal("86.1"),
          deductible_iva_ratio: decimal("1"),
        },
      ],
      closing: null,
      history: [],
    },
    {
      actividad_id: "Venta en línea de material de dibujo",
      year: SCENARIO_YEAR,
      valuation_method: "pmp",
      opening_stock: "0",
      movements: [
        {
          movement_id: "e3a9c5d1-4b72-4f08-9d16-5a2c7e0b8f43",
          movement_date: fixtureDay(3, 4),
          kind: "purchase",
          sku: "papel-a3",
          quantity: decimal("100"),
          unit_cost: null,
          taxable_base: decimal("1000"),
          iva_rate: decimal("0.21"),
          iva_amount: null,
          deductible_iva_ratio: decimal("1"),
          ledger_row: "unstated",
          claimed_transaction_id: null,
          acquisition_cost: {
            consideration_excluding_iva: decimal("1000"),
            directly_attributable_cost_total: decimal("100.00"),
            nonrecoverable_iva_included: decimal("0.00"),
            recoverable_iva_excluded: decimal("231.00"),
            total_acquisition_cost: decimal("1100.00"),
            component_count: 1,
            evidence_count: 4,
            complete: true,
          },
          acquisition_detail: {
            consideration_iva_amount: decimal("210"),
            consideration_deductible_iva_ratio: decimal("1"),
            components: [
              {
                component_id: "c1d2e3f4-0a1b-4c2d-8e3f-4a5b6c7d8e9f",
                kind: "freight",
                taxable_base: decimal("100"),
                iva_amount: decimal("21"),
                deductible_iva_ratio: decimal("1"),
                evidence_references: [
                  "attachment:" + hex64("seed-document:transport"),
                ],
              },
            ],
            documents: [
              {
                reference: "document-" + hex64("seed-document:invoice"),
                evidence_kind: "purchase_invoice",
                content_digest: hex64("seed-document:invoice"),
                file_name: "factura-papeleria-trazo.pdf",
              },
              {
                reference: "attachment:" + hex64("seed-document:transport"),
                evidence_kind: "transport_document",
                content_digest: hex64("seed-document:transport"),
              },
              {
                reference: "attachment:" + hex64("seed-document:cost-check"),
                evidence_kind: "attributable_cost_review",
                content_digest: hex64("seed-document:cost-check"),
              },
              {
                reference: "attachment:" + hex64("seed-document:iva-check"),
                evidence_kind: "iva_recoverability_review",
                content_digest: hex64("seed-document:iva-check"),
              },
            ],
            consideration_evidence:
              "document-" + hex64("seed-document:invoice"),
            attributable_cost_review_evidence:
              "attachment:" + hex64("seed-document:cost-check"),
            iva_recoverability_review_evidence:
              "attachment:" + hex64("seed-document:iva-check"),
          },
        },
      ],
      closing: null,
      history: [],
    },
    {
      actividad_id: "Papelería y reprografía",
      year: PRIOR_YEAR,
      valuation_method: "fifo",
      opening_stock: "380",
      movements: [
        {
          movement_id: "0c4a6b8e-93d1-4e0b-8a3f-6f1d2b7c5e21",
          movement_date: fixtureDay(1, 3, -1),
          kind: "opening",
          sku: "papel-a3",
          quantity: decimal("100"),
          unit_cost: decimal("3.8"),
          taxable_base: decimal("380"),
          iva_rate: decimal("0.21"),
          iva_amount: decimal("79.8"),
          deductible_iva_ratio: decimal("1"),
        },
        {
          movement_id: "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32",
          movement_date: fixtureDay(11, 20, -1),
          kind: "cogs",
          sku: "papel-a3",
          quantity: decimal("60"),
          unit_cost: null,
          taxable_base: null,
          iva_rate: decimal("0.21"),
          iva_amount: null,
          deductible_iva_ratio: decimal("1"),
        },
      ],
      closing: {
        record: hex64("closing:papeleria:2025"),
        decision: hex64("closing-decision:papeleria:2025"),
        physical_observation: null,
        prior_closing_link: hex64("closing-prior:papeleria:2025"),
      },
      closingDecision: "closing-papeleria-2025",
      closingRecorded: true,
      history: [
        {
          correction_id: "3e6a1f90-2b4d-4c7e-9a15-8d0c7b2f4e61",
          kind: "opening_corrected",
          recorded_at: fixtureInstant(2, 10, "09:30:00Z", -1),
          actor: "runtime",
          correction_reason: "keying_error",
          retirement_reason: null,
          superseded_movement: null,
          replacement_movement_id: null,
          prior_opening_stock: decimal("308"),
          prior_valuation_method: null,
          prior_descriptor: null,
        },
        {
          correction_id: "a94b0d7c-5e12-4f38-b6a9-1c3e7d5f2a80",
          kind: "movement_corrected",
          recorded_at: fixtureInstant(11, 24, "17:05:00Z", -1),
          actor: "runtime",
          correction_reason: "source_document_corrected",
          retirement_reason: null,
          superseded_movement: {
            movement_id: "c8f1d3a5-7b29-4e60-a4d2-9f0b6e8c1a73",
            movement_date: fixtureDay(11, 20, -1),
            kind: "cogs",
            sku: "papel-a3",
            quantity: decimal("50"),
            unit_cost: null,
            taxable_base: null,
            iva_rate: decimal("0.21"),
            iva_amount: null,
            deductible_iva_ratio: decimal("1"),
          },
          replacement_movement_id: "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32",
          prior_opening_stock: null,
          prior_valuation_method: null,
          prior_descriptor: null,
        },
      ],
    },
    {
      actividad_id: "Taller de enmarcado",
      year: PRIOR_YEAR,
      valuation_method: "coste_medio",
      opening_stock: "90",
      movements: [],
      closing: null,
      label: "Enmarcado (cerrado en 2025)",
      description: "Marcos y molduras a medida",
      retired: true,
      retirement: "activity_ceased",
      history: [
        {
          correction_id: "5b8d2e41-9c07-4a63-8f1e-6d3a0c9b7e52",
          kind: "described",
          recorded_at: fixtureInstant(3, 2, "11:00:00Z", -1),
          actor: "runtime",
          correction_reason: null,
          retirement_reason: null,
          superseded_movement: null,
          replacement_movement_id: null,
          prior_opening_stock: null,
          prior_valuation_method: null,
          prior_descriptor: null,
        },
        {
          correction_id: "d07c4a92-1e58-4b36-a2f9-4e8b5c0d3a17",
          kind: "retired",
          recorded_at: fixtureInstant(12, 31, "18:20:00Z", -1),
          actor: "runtime",
          correction_reason: null,
          retirement_reason: "activity_ceased",
          superseded_movement: null,
          replacement_movement_id: null,
          prior_opening_stock: null,
          prior_valuation_method: null,
          prior_descriptor: null,
        },
      ],
    },
  ];

  // ---- Inventory -----------------------------------------------------------

  /** The bare name of each file the book kept, by its mark: what the worker
   * records beside the bytes. */
  const keptNames = new Map<string, string>();
  const bookOf = (request: JsonObject) => {
    const actividad = required(request.actividad_id);
    const year = whole(request.year);
    return {
      actividad,
      year,
      book: books.find(
        (found) => found.actividad_id === actividad && found.year === year,
      ),
    };
  };
  /** The notice the backend gives for a retired book that still holds
   * entries: the key of its sentence and the year it is about. */
  const advisoriesOf = (book: Book): JsonObject[] =>
    book.retired &&
    (book.movements.length > 0 || Number(book.opening_stock) !== 0)
      ? [
          {
            code: "retired_book_leaves_year_unresolved",
            key: "application.inventory.advisories.retired_book_leaves_year_unresolved",
            year: book.year,
          },
        ]
      : [];
  /** A book as the backend projects it. What a purchase rests on is served
   * by the inspect read alone. */
  const bookProjection = (book: Book, detailed = false): JsonObject => ({
    actividad_id: book.actividad_id,
    year: book.year,
    valuation_method: book.valuation_method,
    opening_stock: decimal(book.opening_stock),
    opening_layers: [],
    closing_authority_fingerprints: book.closing,
    period_movements: book.movements.map((movement) => {
      const { acquisition_detail: detail, ...rest } = movement;
      return detailed && detail !== undefined
        ? { ...rest, acquisition_detail: detail }
        : rest;
    }),
    schema_version: "1",
    descriptor:
      book.label === undefined
        ? null
        : { label: book.label, description: book.description ?? null },
    retired: book.retired === true,
    retirement_reason: book.retired ? (book.retirement ?? null) : null,
    history: book.history,
    advisories: advisoriesOf(book),
  });
  const inventoryRefusal = (
    code: string,
    reason: string,
    extra: JsonObject,
    shape: JsonObject,
  ): never => {
    throw new SetupStopped(code, {
      ...shape,
      outcome: "refused",
      refusal: {
        code,
        reason,
        actividad_id: null,
        year: null,
        movement_id: null,
        valuation_method: null,
        // The sentence the backend's catalogue has for the reason, and the
        // facts that fill it in.
        reason_key:
          reason === "inventory_validation"
            ? "errors.refused.refused_profile_inventory_validation"
            : `application.inventory.service.errors.${REASON_KEY_NAMES[reason] ?? reason}`,
        reason_facts: Object.entries(extra)
          .filter(
            ([key, fact]) =>
              key !== "actividad_id" &&
              fact !== null &&
              typeof fact !== "object",
          )
          .map(([key, fact]) => ({ key, value: String(fact) })),
        ...extra,
        ...served("inventory", reason, extra),
      },
    });
  };
  const notFound = (actividad: string, year: number, shape: JsonObject) =>
    inventoryRefusal(
      "REFUSED_INVENTORY_ACTIVIDAD_NOT_FOUND",
      "activity_not_found",
      { actividad_id: actividad, year },
      shape,
    );
  function valuation(book: Book) {
    const lots: { quantity: number; cost: number }[] = [];
    let cogs = 0;
    const units = (value: JsonValue | undefined) =>
      Number((value as { decimal: string } | null)?.decimal ?? 0);
    for (const movement of book.movements) {
      const quantity = units(movement.quantity);
      if (movement.kind === "opening" || movement.kind === "purchase") {
        const total = (
          movement.acquisition_cost as { total_acquisition_cost?: JsonValue }
        )?.total_acquisition_cost;
        lots.push({
          quantity,
          cost:
            movement.kind === "purchase" && quantity > 0
              ? units(total) / quantity
              : units(movement.unit_cost),
        });
      } else if (movement.kind === "cogs") {
        let left = quantity;
        while (left > 0 && lots.length) {
          const lot = lots[0]!;
          const taken = Math.min(left, lot.quantity);
          cogs += taken * lot.cost;
          lot.quantity -= taken;
          left -= taken;
          if (lot.quantity === 0) lots.shift();
        }
      }
    }
    const closing = lots.reduce(
      (total, lot) => total + lot.quantity * lot.cost,
      0,
    );
    const text = (value: number) =>
      value.toFixed(2).replace(/\.?0+$/, "") || "0";
    return { closing: text(closing), cogs: text(cogs) };
  }
  const object = (value: JsonValue | undefined): JsonObject =>
    typeof value === "object" && value !== null && !Array.isArray(value)
      ? value
      : invalid();
  const cents = (value: number) => value.toFixed(2);
  /** A purchase as the ledger keeps it: its cost as the list shows it, and
   * the facts the inspect read serves besides. Totals left out are added up
   * as the backend adds them, and totals stated must agree. The request's
   * shape is checked as the registered contract would. */
  const acquisitionOf = (
    cost: JsonValue | undefined,
  ): { summary: JsonObject; detail: JsonObject } | null => {
    if (cost === undefined || cost === null) return null;
    const request = object(cost);
    fromKeys(request, [
      "consideration_excluding_iva",
      "consideration_iva_amount",
      "consideration_deductible_iva_ratio",
      "attributable_cost_components",
      "evidence",
      "completeness",
      "directly_attributable_cost_total",
      "nonrecoverable_iva_included",
      "recoverable_iva_excluded",
      "total_acquisition_cost",
    ]);
    const components = request.attributable_cost_components;
    const evidence = request.evidence;
    if (!Array.isArray(components) || !Array.isArray(evidence))
      return invalid();
    if (evidence.length === 0) return invalid();
    const documents = evidence.map((proof) => {
      const found = object(proof);
      fromKeys(found, ["reference", "evidence_kind", "content_digest"]);
      if (!/^[0-9a-f]{64}$/.test(String(found.content_digest))) invalid();
      return {
        reference: required(object(found.reference).reference),
        evidence_kind: required(found.evidence_kind),
        content_digest: required(found.content_digest),
      };
    });
    const price = Number(decimalOf(request.consideration_excluding_iva));
    const iva = Number(decimalOf(request.consideration_iva_amount));
    const ratio = Number(decimalOf(request.consideration_deductible_iva_ratio));
    const parts = components.map((component) => {
      const part = object(component);
      return {
        component_id: required(part.component_id),
        kind: required(part.kind),
        taxable_base: decimalOf(part.taxable_base),
        iva_amount: decimalOf(part.iva_amount),
        deductible_iva_ratio: decimalOf(part.deductible_iva_ratio),
        evidence_references: (part.evidence_references as JsonValue[]).map(
          (reference) => required(object(reference).reference),
        ),
      };
    });
    const attributable = parts.reduce(
      (sum, part) => sum + Number(part.taxable_base),
      0,
    );
    const recoverable =
      Math.round(iva * ratio * 100) / 100 +
      parts.reduce(
        (sum, part) =>
          sum +
          Math.round(
            Number(part.iva_amount) * Number(part.deductible_iva_ratio) * 100,
          ) /
            100,
        0,
      );
    const totalIva =
      iva + parts.reduce((sum, part) => sum + Number(part.iva_amount), 0);
    const derived = {
      directly_attributable_cost_total: cents(attributable),
      recoverable_iva_excluded: cents(recoverable),
      nonrecoverable_iva_included: cents(totalIva - recoverable),
      total_acquisition_cost: cents(
        price + attributable + totalIva - recoverable,
      ),
    };
    // A total the request states is checked against the figures, never
    // trusted over them.
    for (const [name, expected] of Object.entries(derived))
      if (
        request[name] !== undefined &&
        Number(decimalOf(request[name])) !== Number(expected)
      )
        invalid();
    const completeness = object(request.completeness);
    return {
      summary: {
        consideration_excluding_iva: decimal(
          decimalOf(request.consideration_excluding_iva),
        ),
        directly_attributable_cost_total: decimal(
          derived.directly_attributable_cost_total,
        ),
        nonrecoverable_iva_included: decimal(
          derived.nonrecoverable_iva_included,
        ),
        recoverable_iva_excluded: decimal(derived.recoverable_iva_excluded),
        total_acquisition_cost: decimal(derived.total_acquisition_cost),
        component_count: components.length,
        evidence_count: evidence.length,
        complete: true,
      },
      detail: {
        consideration_iva_amount: decimal(
          decimalOf(request.consideration_iva_amount),
        ),
        consideration_deductible_iva_ratio: decimal(
          decimalOf(request.consideration_deductible_iva_ratio),
        ),
        components: parts.map((part) => ({
          component_id: part.component_id,
          kind: part.kind,
          taxable_base: decimal(part.taxable_base),
          iva_amount: decimal(part.iva_amount),
          deductible_iva_ratio: decimal(part.deductible_iva_ratio),
          evidence_references: part.evidence_references,
        })),
        documents: documents.map((document) => ({
          ...document,
          file_name: keptNames.get(document.content_digest) ?? null,
        })),
        consideration_evidence: required(
          object(completeness.consideration_evidence).reference,
        ),
        attributable_cost_review_evidence: required(
          object(completeness.attributable_cost_review_evidence).reference,
        ),
        iva_recoverability_review_evidence: required(
          object(completeness.iva_recoverability_review_evidence).reference,
        ),
      },
    };
  };
  /** The movement a request states, checked as the registered contract would. */
  const movementOf = (request: JsonObject): JsonObject => {
    const id = required(request.movement_id);
    const date = required(request.movement_date);
    const kind = required(request.kind);
    if (!DATE.test(date) || !MOVEMENT_KINDS.includes(kind)) invalid();
    const quantity = decimalOf(request.quantity);
    const unit =
      request.unit_cost == null ? null : decimalOf(request.unit_cost);
    const base =
      request.taxable_base == null ? null : decimalOf(request.taxable_base);
    // A purchase states its cost and what proves it, and no unit cost or base
    // beside it; any other kind states no cost evidence.
    const acquisition = acquisitionOf(request.acquisition_cost);
    if ((kind === "purchase") !== (acquisition !== null)) invalid();
    if (kind === "purchase" && (unit !== null || base !== null)) invalid();
    return {
      movement_id: id,
      movement_date: date,
      kind,
      sku: "papel-a3",
      quantity: decimal(quantity),
      unit_cost: unit === null ? null : decimal(unit),
      taxable_base:
        acquisition !== null
          ? (acquisition.summary.consideration_excluding_iva ?? null)
          : base === null
            ? null
            : decimal(base),
      iva_rate: decimal("0.21"),
      iva_amount: null,
      deductible_iva_ratio: decimal("1"),
      ...(acquisition !== null
        ? {
            ledger_row: "unstated",
            claimed_transaction_id: null,
            acquisition_cost: acquisition.summary,
            acquisition_detail: acquisition.detail,
          }
        : { acquisition_cost: null, acquisition_detail: null }),
    };
  };
  /** The units a book holds: what came in less what went out. */
  const unitsHeld = (book: Book): number =>
    book.movements.reduce((held, movement) => {
      const units = Number(decimalOf(movement.quantity));
      return movement.kind === "opening" || movement.kind === "purchase"
        ? held + units
        : held - units;
    }, 0);
  /** Refuses a change to the stock facts of a retired book, or of one whose
   * closing value is recorded. */
  const stockFactsOpen = (book: Book, shape: JsonObject) => {
    const refuse = (reason: string, extra: JsonObject = {}) =>
      inventoryRefusal(
        "REFUSED_INVENTORY_SERVICE_INPUT",
        reason,
        {
          actividad_id: book.actividad_id,
          year: book.year,
          ...extra,
        },
        shape,
      );
    if (book.retired) refuse("inventory_retired");
    if (book.closingRecorded) refuse("closing_authority_recorded");
  };
  const CORRECTION_REASONS = [
    "keying_error",
    "source_document_corrected",
    "duplicate_entry",
    "operation_did_not_occur",
  ];
  const RETIREMENT_REASONS = [
    "created_in_error",
    "activity_ceased",
    "no_stock_held",
  ];
  /** Each change already made, by its reference, with the request that made
   * it: the same request sent again changes nothing. */
  const made = new Map<string, string>();
  const changeShape = {
    profile_id: profileId,
    ledger: null,
    bucket_event_ids: [],
  };
  const historyEntry = (
    id: string,
    kind: string,
    facts: JsonObject = {},
  ): JsonObject => ({
    correction_id: id,
    kind,
    recorded_at: now(),
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
  /** One change to a book: refused as the contract refuses it, replayed when
   * the same request was made, else applied and kept in the history. */
  const change =
    (
      keys: readonly string[],
      applyTo: (
        book: Book,
        request: JsonObject,
        id: string,
        shape: JsonObject,
      ) => JsonObject,
    ): Handler =>
    (request) => {
      fromKeys(request, ["actividad_id", "year", "correction_id", ...keys]);
      const { actividad, year, book } = bookOf(request);
      const id = required(request.correction_id);
      if (id.length > 64) invalid();
      if (!book) return notFound(actividad, year, changeShape);
      const sent = JSON.stringify(request);
      const earlier = made.get(`${keyOfBook(book)}|${id}`);
      if (earlier === sent)
        return {
          outcome: "replayed",
          profile_id: profileId,
          ledger: bookProjection(book),
          bucket_event_ids: [],
          refusal: null,
        };
      if (earlier !== undefined)
        return inventoryRefusal(
          "REFUSED_INVENTORY_SERVICE_INPUT",
          "correction_id_conflict",
          { actividad_id: actividad, year },
          changeShape,
        );
      const entry = applyTo(book, request, id, changeShape);
      book.history.push(entry);
      made.set(`${keyOfBook(book)}|${id}`, sent);
      return {
        outcome: "applied",
        profile_id: profileId,
        ledger: bookProjection(book),
        bucket_event_ids: events(),
        refusal: null,
      };
    };
  const keyOfBook = (book: Book) => `${book.actividad_id}|${book.year}`;
  const reasonOf = (value: JsonValue | undefined, allowed: string[]) => {
    const reason = required(value);
    if (!allowed.includes(reason)) invalid();
    return reason;
  };
  /** The effective movement a change names, else the refusal for it. */
  const targetOf = (book: Book, request: JsonObject, shape: JsonObject) => {
    const target = required(request.target_movement_id);
    const found = book.movements.find((one) => one.movement_id === target);
    if (found) return found;
    const superseded = book.history.some(
      (one) =>
        (one.superseded_movement as JsonObject | null)?.movement_id === target,
    );
    return inventoryRefusal(
      "REFUSED_INVENTORY_SERVICE_INPUT",
      superseded ? "movement_already_superseded" : "movement_not_found",
      { actividad_id: book.actividad_id, year: book.year },
      shape,
    );
  };
  const inventoryWrites: Record<string, Handler> = {
    "ledger.inventory.describe": change(
      ["label", "description"],
      (book, request, id) => {
        const label = required(request.label);
        if (label.length > 120) invalid();
        const description =
          request.description === null || request.description === undefined
            ? null
            : required(request.description);
        const prior =
          book.label === undefined
            ? null
            : { label: book.label, description: book.description ?? null };
        book.label = label;
        book.description = description;
        return historyEntry(id, "described", { prior_descriptor: prior });
      },
    ),
    "ledger.inventory.correct": change(
      ["reason", "opening_stock", "valuation_method"],
      (book, request, id, shape) => {
        const reason = reasonOf(request.reason, CORRECTION_REASONS);
        const opening =
          request.opening_stock == null
            ? null
            : decimalOf(request.opening_stock);
        const method =
          request.valuation_method == null
            ? null
            : required(request.valuation_method);
        if (method !== null && !VALUATION.includes(method)) invalid();
        stockFactsOpen(book, shape);
        const newOpening =
          opening !== null && Number(opening) !== Number(book.opening_stock);
        const newMethod = method !== null && method !== book.valuation_method;
        if (!newOpening && !newMethod)
          return inventoryRefusal(
            "REFUSED_INVENTORY_SERVICE_INPUT",
            "correction_changes_nothing",
            { actividad_id: book.actividad_id, year: book.year },
            shape,
          );
        const facts = {
          correction_reason: reason,
          prior_opening_stock: newOpening ? decimal(book.opening_stock) : null,
          prior_valuation_method: newMethod ? book.valuation_method : null,
        };
        if (newOpening && opening !== null) book.opening_stock = opening;
        if (newMethod && method !== null) book.valuation_method = method;
        return historyEntry(id, "opening_corrected", facts);
      },
    ),
    "ledger.inventory.movement.correct": change(
      [
        "target_movement_id",
        "reason",
        "movement_id",
        "movement_date",
        "kind",
        "quantity",
        "unit_cost",
        "taxable_base",
        "acquisition_cost",
      ],
      (book, request, id, shape) => {
        const reason = reasonOf(request.reason, CORRECTION_REASONS);
        const replacement = movementOf(request);
        stockFactsOpen(book, shape);
        const target = targetOf(book, request, shape);
        book.movements = book.movements.map((one) =>
          one === target ? replacement : one,
        );
        return historyEntry(id, "movement_corrected", {
          correction_reason: reason,
          superseded_movement: target,
          replacement_movement_id: replacement.movement_id ?? null,
        });
      },
    ),
    "ledger.inventory.movement.reverse": change(
      ["target_movement_id", "reason"],
      (book, request, id, shape) => {
        const reason = reasonOf(request.reason, CORRECTION_REASONS);
        stockFactsOpen(book, shape);
        const target = targetOf(book, request, shape);
        book.movements = book.movements.filter((one) => one !== target);
        return historyEntry(id, "movement_reversed", {
          correction_reason: reason,
          superseded_movement: target,
        });
      },
    ),
    "ledger.inventory.movement.claim": change(
      ["movement_id", "ledger_row", "claimed_transaction_id"],
      (book, request, id, shape) => {
        const row = required(request.ledger_row);
        if (!["unstated", "claimed", "none"].includes(row)) invalid();
        const named =
          request.claimed_transaction_id == null
            ? null
            : required(request.claimed_transaction_id);
        // A transaction is named exactly when the purchase claims one.
        if ((row === "claimed") !== (named !== null)) invalid();
        const movementId = required(request.movement_id);
        const facts = {
          actividad_id: book.actividad_id,
          year: book.year,
          movement_id: movementId,
        };
        const target = book.movements.find(
          (one) => one.movement_id === movementId,
        );
        if (!target)
          return inventoryRefusal(
            "REFUSED_INVENTORY_SERVICE_INPUT",
            "movement_not_found",
            facts,
            shape,
          );
        if (target.kind !== "purchase")
          return inventoryRefusal(
            "REFUSED_INVENTORY_SERVICE_INPUT",
            "ledger_row_not_purchase",
            facts,
            shape,
          );
        if (
          (target.ledger_row ?? "unstated") === row &&
          (target.claimed_transaction_id ?? null) === named
        )
          return inventoryRefusal(
            "REFUSED_INVENTORY_SERVICE_INPUT",
            "correction_changes_nothing",
            facts,
            shape,
          );
        if (named !== null) {
          const found = transactions().find((one) => one.id === named);
          const claimedElsewhere = books.some((other) =>
            other.movements.some(
              (one) => one !== target && one.claimed_transaction_id === named,
            ),
          );
          const reason =
            found === undefined
              ? "claimed_transaction_missing"
              : claimedElsewhere
                ? "claimed_transaction_double_claim"
                : found.currency !== "EUR"
                  ? "claimed_transaction_not_eur"
                  : null;
          if (reason !== null)
            return inventoryRefusal(
              "REFUSED_INVENTORY_SERVICE_INPUT",
              reason,
              facts,
              shape,
            );
        }
        book.movements = book.movements.map((one) =>
          one === target
            ? { ...one, ledger_row: row, claimed_transaction_id: named }
            : one,
        );
        return historyEntry(id, "ledger_row_stated");
      },
    ),
    "ledger.inventory.retire": change(
      ["reason"],
      (book, request, id, shape) => {
        const reason = reasonOf(request.reason, RETIREMENT_REASONS);
        if (book.retired)
          return inventoryRefusal(
            "REFUSED_INVENTORY_SERVICE_INPUT",
            "inventory_already_retired",
            { actividad_id: book.actividad_id, year: book.year },
            shape,
          );
        book.retired = true;
        book.retirement = reason;
        return historyEntry(id, "retired", { retirement_reason: reason });
      },
    ),
    "ledger.inventory.restore": change([], (book, _request, id, shape) => {
      if (!book.retired)
        return inventoryRefusal(
          "REFUSED_INVENTORY_SERVICE_INPUT",
          "inventory_not_retired",
          { actividad_id: book.actividad_id, year: book.year },
          shape,
        );
      book.retired = false;
      book.retirement = null;
      return historyEntry(id, "restored");
    }),
    "ledger.inventory.create": (request) => {
      fromKeys(request, [
        "actividad_id",
        "year",
        "valuation_method",
        "opening_stock",
      ]);
      const { actividad, year, book } = bookOf(request);
      const method = required(request.valuation_method);
      const shape = {
        profile_id: profileId,
        ledger: null,
        bucket_event_ids: [],
      };
      if (!VALUATION.includes(method))
        return inventoryRefusal(
          "REFUSED_INVENTORY_SERVICE_INPUT",
          "invalid_valuation_method",
          { actividad_id: actividad, year, valuation_method: method },
          shape,
        );
      if (book)
        return inventoryRefusal(
          "REFUSED_INVENTORY_ACTIVIDAD_CONFLICT",
          "activity_conflict",
          { actividad_id: actividad, year },
          shape,
        );
      const created: Book = {
        actividad_id: actividad,
        year,
        valuation_method: method,
        opening_stock:
          request.opening_stock === undefined
            ? "0"
            : decimalOf(request.opening_stock),
        movements: [],
        closing: null,
        history: [],
      };
      books.push(created);
      return {
        outcome: "created",
        profile_id: profileId,
        ledger: bookProjection(created),
        bucket_event_ids: events(),
        refusal: null,
      };
    },
    "ledger.inventory.movement.add": (request) => {
      fromKeys(request, [
        "actividad_id",
        "year",
        "movement_id",
        "movement_date",
        "kind",
        "quantity",
        "unit_cost",
        "taxable_base",
        "acquisition_cost",
      ]);
      const { actividad, year, book } = bookOf(request);
      const id = required(request.movement_id);
      const date = required(request.movement_date);
      const kind = required(request.kind);
      if (!DATE.test(date) || !MOVEMENT_KINDS.includes(kind)) invalid();
      const quantity = decimalOf(request.quantity);
      movementOf(request);
      const shape = {
        profile_id: profileId,
        ledger: null,
        bucket_event_ids: [],
      };
      if (!book) return notFound(actividad, year, shape);
      stockFactsOpen(book, shape);
      if (book.movements.some((found) => found.movement_id === id))
        return inventoryRefusal(
          "REFUSED_PROFILE_INVENTORY_VALIDATION",
          "duplicate_movement_id",
          { actividad_id: actividad, year, movement_id: id },
          shape,
        );
      if (
        (kind === "cogs" || kind === "count") &&
        Number(quantity) > unitsHeld(book)
      )
        return inventoryRefusal(
          "REFUSED_INVENTORY_SERVICE_INPUT",
          "stock_would_go_negative",
          { actividad_id: actividad, year, sku: "papel-a3" },
          shape,
        );
      book.movements.push(movementOf(request));
      return {
        outcome: "added",
        profile_id: profileId,
        ledger: bookProjection(book),
        bucket_event_ids: events(),
        refusal: null,
      };
    },
    "ledger.inventory.evidence.add": (request) => {
      fromKeys(request, ["source_path"]);
      const file = tools.fileOf(request.source_path);
      // The worker keeps a PDF, an XML file or an image, and refuses any other
      // before anything is written.
      if (!/\.(pdf|xml|png|jpe?g|tiff?|webp|heic)$/i.test(file.name))
        return inventoryRefusal(
          "REFUSED_INVENTORY_SERVICE_INPUT",
          "evidence_file_not_admitted",
          {},
          {
            profile_id: profileId,
            reference: null,
            content_digest: null,
          },
        );
      const digest = hex64(`inventory-document:${file.name}`);
      keptNames.set(digest, file.name);
      return {
        outcome: "stored",
        profile_id: profileId,
        reference: `document-${digest}`,
        content_digest: digest,
        refusal: null,
      };
    },
    "ledger.inventory.closing-value.record": (request) => {
      fromKeys(request, ["actividad_id", "year", "facts"]);
      const { actividad, year, book } = bookOf(request);
      const facts = object(request.facts);
      fromKeys(facts, [
        "decision_id",
        "authority",
        "reason",
        "decision_evidence",
        "physical_count",
        "prior_evidence",
      ]);
      const decision = required(facts.decision_id);
      required(facts.reason);
      const authority = required(facts.authority);
      if (!CLOSING_AUTHORITIES.includes(authority)) invalid();
      const documentsOf = (
        value: JsonValue | undefined,
        roles: readonly string[],
        least: number,
      ) => {
        if (!Array.isArray(value) || value.length < least) return invalid();
        return value.map((document) => {
          const found = object(document);
          fromKeys(found, ["reference", "role", "content_digest"]);
          if (!/^[0-9a-f]{64}$/.test(required(found.content_digest))) invalid();
          if (!roles.includes(required(found.role))) invalid();
          return found;
        });
      };
      documentsOf(facts.decision_evidence, DECISION_ROLES, 1);
      const count = facts.physical_count;
      if ((authority === "physical_observation") !== (count != null)) invalid();
      if (count != null) {
        const observation = object(count);
        fromKeys(observation, [
          "observed_on",
          "closing_value",
          "valuation_basis",
          "evidence",
        ]);
        if (!DATE.test(required(observation.observed_on))) invalid();
        decimalOf(observation.closing_value);
        if (!CLOSING_BASES.includes(required(observation.valuation_basis)))
          invalid();
        documentsOf(observation.evidence, PHYSICAL_ROLES, 2);
      }
      const prior = facts.prior_evidence;
      if (!Array.isArray(prior)) return invalid();
      const shape = { record: null };
      if (!book) return notFound(actividad, year, shape);
      if (book.retired)
        return inventoryRefusal(
          "REFUSED_INVENTORY_SERVICE_INPUT",
          "inventory_retired",
          { actividad_id: actividad, year },
          shape,
        );
      const fingerprint = hex64(JSON.stringify(facts));
      if (book.closing !== null) {
        if (book.closingDecision !== decision)
          return inventoryRefusal(
            "REFUSED_INVENTORY_SERVICE_INPUT",
            "closing_authority_conflict",
            { actividad_id: actividad, year },
            shape,
          );
      } else {
        // An opening with no closed prior book needs a document that shows it.
        const earlier = books.find(
          (found) =>
            found.actividad_id === actividad && found.year === year - 1,
        );
        if ((earlier?.closing ?? null) === null && prior.length === 0)
          return inventoryRefusal(
            "REFUSED_INVENTORY_SERVICE_INPUT",
            "prior_closing_document_needed",
            { actividad_id: actividad, year },
            shape,
          );
      }
      const changed = book.closing === null;
      const closing = {
        record: fingerprint,
        decision: hex64(`decision:${decision}`),
        physical_observation: count != null ? hex64(`count:${decision}`) : null,
        prior_closing_link: hex64(`prior:${decision}`),
      };
      book.closing = closing;
      book.closingDecision = decision;
      book.closingRecorded = true;
      return {
        outcome: "recorded",
        record: {
          profile_id: profileId,
          actividad_id: actividad,
          year,
          authority_record_fingerprint: fingerprint,
          decision_fingerprint: closing.decision,
          physical_observation_fingerprint: closing.physical_observation,
          prior_closing_link_fingerprint: closing.prior_closing_link,
          changed,
        },
        refusal: null,
      };
    },
    "ledger.inventory.closing-authority.record": (request) => {
      fromKeys(request, ["actividad_id", "year", "authority_record"]);
      const { actividad, year, book } = bookOf(request);
      const record = request.authority_record;
      if (
        typeof record !== "object" ||
        record === null ||
        Array.isArray(record)
      )
        return invalid();
      const shape = { record: null };
      if (!book) return notFound(actividad, year, shape);
      const decision = record.decision as JsonObject | undefined;
      const link = record.prior_closing_link as JsonObject | undefined;
      if (
        !decision ||
        !link ||
        decision.actividad_id !== actividad ||
        decision.filing_year !== year
      )
        return inventoryRefusal(
          "REFUSED_PROFILE_INVENTORY_VALIDATION",
          "closing_authority_invalid",
          { actividad_id: actividad, year },
          shape,
        );
      const fingerprint = hex64(JSON.stringify(record));
      const changed = book.closing?.record !== fingerprint;
      book.closing = {
        record: fingerprint,
        decision: hex64(JSON.stringify(decision)),
        physical_observation: record.physical_observation
          ? hex64(JSON.stringify(record.physical_observation))
          : null,
        prior_closing_link: hex64(JSON.stringify(link)),
      };
      return {
        outcome: "recorded",
        record: {
          profile_id: profileId,
          actividad_id: actividad,
          year,
          authority_record_fingerprint: fingerprint,
          decision_fingerprint: book.closing.decision!,
          physical_observation_fingerprint: book.closing.physical_observation!,
          prior_closing_link_fingerprint: book.closing.prior_closing_link!,
          changed,
        },
        refusal: null,
      };
    },
  };

  const reads: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.inventory.list": (request) => {
      fromKeys(request, []);
      return {
        profile_id: profileId,
        rows: books.map((book) => ({
          actividad_id: book.actividad_id,
          year: book.year,
          valuation_method: book.valuation_method,
          opening_stock: decimal(book.opening_stock),
          movement_count: book.movements.length,
          label: book.label ?? null,
          retired: book.retired === true,
          retirement_reason: book.retired ? (book.retirement ?? null) : null,
          correction_count: book.history.length,
          advisories: advisoriesOf(book),
        })),
      };
    },
    "ledger.inventory.options": (request) => {
      fromKeys(request, []);
      return {
        profile_id: profileId,
        families: Object.entries(OPTION_FAMILIES).map(([family, values]) => ({
          family,
          options: values.map((value) => ({
            value,
            label_key: `application.inventory.labels.${family}.${value}`,
            role:
              family === "acquisition_evidence_kind" ||
              family === "closing_authority" ||
              family === "movement_kind"
                ? (OPTION_ROLES[value] ?? null)
                : null,
          })),
        })),
      };
    },
    "ledger.inventory.inspect": (request) => {
      fromKeys(request, ["actividad_id", "year"]);
      const { actividad, year, book } = bookOf(request);
      if (!book)
        return notFound(actividad, year, {
          profile_id: profileId,
          ledger: null,
        });
      return {
        outcome: "found",
        profile_id: profileId,
        ledger: bookProjection(book, true),
        refusal: null,
      };
    },
    "ledger.inventory.valuation.preview": (request) => {
      fromKeys(request, ["actividad_id", "year"]);
      const { actividad, year, book } = bookOf(request);
      if (!book) return notFound(actividad, year, { preview: null });
      const found = valuation(book);
      return {
        outcome: "previewed",
        preview: {
          profile_id: profileId,
          actividad_id: actividad,
          year,
          valuation_method: book.valuation_method,
          derived_closing_value: decimal(found.closing),
          cogs: decimal(found.cogs),
          bucket_event_ids: [],
        },
        refusal: null,
      };
    },
  };
  return { reads, writes: inventoryWrites };
}
