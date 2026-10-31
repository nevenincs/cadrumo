// The scenario ledger's setup: its rules, business-use ratios,
// counterparties and model diagnostics; its own-account, prorrata, capital
// goods, inventory and activity asset registers; and its declaration-link
// rebuild and reset. Each answer follows its registered
// contract: a request the contract would not decode is refused before
// anything runs, and a refusal the ledger reports after reading settles as
// a refusal whose detail is the operation's own result, as the host passes
// it on. Everything it answers is synthetic.

import type {
  JsonObject,
  JsonValue,
  LedgerDefinitionId,
} from "../shell/ledger";
import { isSpendingCategory } from "../shell/ledgerVocabulary";
import { assetOperations } from "./assetsFixture";
import { RATIO_ELIGIBLE_FIXTURE } from "./fixtures/ledgerRatios";
import type {
  FixtureLedger,
  FixtureMovement,
  FixtureRule,
} from "./fixtures/ledger";

/** A request its registered contract would not decode. */
export class SetupRequestInvalid extends Error {}
/** Settled without writing, with the refusal's code and its detail. */
export class SetupStopped extends Error {
  constructor(
    readonly reason: string,
    readonly detail: JsonObject | null = null,
  ) {
    super(reason);
  }
}

type Tools = {
  profileId: string;
  today: string;
  now: () => string;
  events: () => string[];
  hex64: (text: string) => string;
  /** The file a token the window was given stands for. */
  fileOf: (token: JsonValue | undefined) => { name: string };
};

type Handler = (request: JsonObject) => JsonObject;

const invalid = (): never => {
  throw new SetupRequestInvalid();
};
const text = (value: JsonValue | undefined): string | null =>
  typeof value === "string" && value !== "" ? value : null;
const required = (value: JsonValue | undefined): string =>
  text(value) ?? invalid();
const whole = (value: JsonValue | undefined): number =>
  typeof value === "number" && Number.isInteger(value) ? value : invalid();
const decimalOf = (value: JsonValue | undefined): string => {
  if (
    typeof value !== "object" ||
    value === null ||
    Array.isArray(value) ||
    typeof value.decimal !== "string" ||
    !/^(0|[1-9]\d*)(\.\d+)?$/.test(value.decimal)
  )
    return invalid();
  return value.decimal;
};
const decimal = (value: string) => ({ decimal: value });
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const DECIDED = ["BUSINESS", "PERSONAL", "MIXED"];
const CLASSIFICATIONS = [
  ...DECIDED,
  "NOT_YET_PROCESSED",
  "PROCESSED_UNCLASSIFIED",
  "SKIPPED_BY_RULE",
  "FAILED_VALIDATION",
  "REVIEWED_EXCLUDED",
];
const fromKeys = (request: JsonObject, allowed: readonly string[]) => {
  if (Object.keys(request).some((key) => !allowed.includes(key))) invalid();
};

const PROVENANCES = ["aeat_autorizada", "inicio_actividad"];
const CARRIED = "carried_prior_definitiva";
const SECTOR_LETTERS = ["a", "b", "c", "d"];
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
    "retired",
    "restored",
  ],
  movement_kind: MOVEMENT_KINDS,
  physical_evidence_role: PHYSICAL_ROLES,
  retirement_reason: ["created_in_error", "activity_ceased", "no_stock_held"],
  valuation_method: VALUATION,
};
const CAPITAL_KINDS = ["mueble", "inmueble"];
const DISPOSAL_REGIMES = ["sujeta_no_exenta", "exenta_o_no_sujeta"];

type Prorrata = {
  ejercicio: number;
  regime: "general" | "especial";
  sector_id: string | null;
  provisional: string | null;
  provenance: string | null;
  reference: string | null;
  transition: { kind: string; evidence_reference: string } | null;
  definitive: string | null;
  con: string | null;
  sin: string | null;
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

/** The scenario ledger's setup answers, held beside the movements. */
export function setupOperations(ledger: FixtureLedger, tools: Tools) {
  const { profileId, hex64, events, now } = tools;
  const ratios = new Map<string, string>([["telefonia_fija", "0.5"]]);
  const counterparties = new Map<string, JsonObject>([
    [
      "LU20260001",
      {
        counterparty_key: hex64("counterparty:LU20260001"),
        canonical_tax_identifier: "LU20260001",
        territorial_scope: "eu_member",
        identification_state: "LU",
        asserted_by: "person",
        asserted_at: "2026-03-02T10:00:00Z",
        note: "",
      },
    ],
  ]);
  const designations: { role: string; modelo: string | null; id: string }[] = [
    { role: "charge", modelo: null, id: "acc-01" },
  ];
  const prorrata: Prorrata[] = [
    {
      ejercicio: 2025,
      regime: "general",
      sector_id: null,
      provisional: "90",
      provenance: "inicio_actividad",
      reference: "REF-2025-0042",
      transition: null,
      definitive: "92",
      con: "48200",
      sin: "4190",
    },
  ];
  const sectors: { sector_id: string; letra: string; codes: string[] }[] = [];
  const capital: JsonObject[] = [
    {
      identifier: "BI-2024-01",
      description: "Plotter de gran formato",
      acquisition_year: 2024,
      cuota_soportada: decimal("714"),
      prorrata_inicial_pct: decimal("92"),
      kind: "mueble",
      art108_elegible: true,
      acquisition_ledger_id: hex64("capital:plotter"),
      prorrata_sector_id: null,
      disposal: null,
      deduccion_efectuada: decimal("656.88"),
      schema_version: "1",
    },
  ];
  const books: Book[] = [
    {
      actividad_id: "Papelería y reprografía",
      year: 2026,
      valuation_method: "fifo",
      opening_stock: "410",
      movements: [
        {
          movement_id: "b1f7c6d2-5f0e-4a43-9d53-2c9a6c1e7a10",
          movement_date: "2026-01-02",
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
      year: 2026,
      valuation_method: "pmp",
      opening_stock: "0",
      movements: [
        {
          movement_id: "e3a9c5d1-4b72-4f08-9d16-5a2c7e0b8f43",
          movement_date: "2026-03-04",
          kind: "purchase",
          sku: "papel-a3",
          quantity: decimal("100"),
          unit_cost: null,
          taxable_base: decimal("1000"),
          iva_rate: decimal("0.21"),
          iva_amount: null,
          deductible_iva_ratio: decimal("1"),
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
      year: 2025,
      valuation_method: "fifo",
      opening_stock: "380",
      movements: [
        {
          movement_id: "0c4a6b8e-93d1-4e0b-8a3f-6f1d2b7c5e21",
          movement_date: "2025-01-03",
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
          movement_date: "2025-11-20",
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
          recorded_at: "2025-02-10T09:30:00Z",
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
          recorded_at: "2025-11-24T17:05:00Z",
          actor: "runtime",
          correction_reason: "source_document_corrected",
          retirement_reason: null,
          superseded_movement: {
            movement_id: "c8f1d3a5-7b29-4e60-a4d2-9f0b6e8c1a73",
            movement_date: "2025-11-20",
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
      year: 2025,
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
          recorded_at: "2025-03-02T11:00:00Z",
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
          recorded_at: "2025-12-31T18:20:00Z",
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

  // ---- Rules ---------------------------------------------------------------

  const ordered = () =>
    [...ledger.rules].sort(
      (a, b) =>
        a.priority - b.priority ||
        (a.created_at < b.created_at
          ? -1
          : a.created_at > b.created_at
            ? 1
            : 0),
    );
  const matcher = (pattern: string) => {
    try {
      return new RegExp(pattern, "iu");
    } catch {
      return null;
    }
  };
  const ruleRefusal = (code: string, message: string): never => {
    throw new SetupStopped("REFUSED_CLI_VALIDATION_BOUNDARY", {
      profile_id: profileId,
      outcome: "validation_error",
      rule: null,
      validation_code: code,
      validation_messages: [message],
      category_example: code === "category" ? "software_suscripcion" : null,
    });
  };
  function addRule(request: JsonObject): JsonObject {
    fromKeys(request, [
      "description_pattern",
      "classification",
      "category_id",
      "priority",
      "actor",
    ]);
    const pattern = request.description_pattern;
    if (typeof pattern !== "string") return invalid();
    const classification = required(request.classification);
    if (!CLASSIFICATIONS.includes(classification)) invalid();
    const priority = request.priority ?? 100;
    if (
      typeof priority !== "number" ||
      !Number.isInteger(priority) ||
      priority < 1
    )
      invalid();
    if (pattern.trim() === "")
      return ruleRefusal("empty_pattern", "The pattern is empty.");
    if (!matcher(pattern))
      return ruleRefusal("invalid_pattern", "The pattern does not compile.");
    const category = text(request.category_id);
    if (category !== null && !isSpendingCategory(category))
      return ruleRefusal("category", "Not a spending category.");
    const rule: FixtureRule = {
      rule_id: hex64(`${pattern}|${classification}|${category ?? ""}`),
      description_pattern: pattern,
      classification,
      category_id: category,
      priority: priority as number,
      actor: "person",
      created_at: now(),
    };
    const at = ledger.rules.findIndex(
      (found) => found.rule_id === rule.rule_id,
    );
    if (at >= 0) ledger.rules.splice(at, 1, rule);
    else ledger.rules.push(rule);
    return {
      profile_id: profileId,
      outcome: "added",
      rule: rule as unknown as JsonValue,
      validation_code: null,
      validation_messages: [],
      category_example: null,
    };
  }
  /** What the rules would classify, first match deciding. */
  function rulePlan(reaffirm: boolean) {
    const rules = ordered();
    const matched: { movement: FixtureMovement; rule: FixtureRule }[] = [];
    let skipped = 0;
    let noMatch = 0;
    for (const movement of ledger.movements) {
      const t = movement.transaction;
      if (t.lifecycle_state !== "ACTIVE" || movement.sealed) continue;
      const open =
        t.business_classification === "NOT_YET_PROCESSED" ||
        (reaffirm && t.classified_by.startsWith("rule:"));
      if (!open) {
        skipped += 1;
        continue;
      }
      const rule = rules.find((found) =>
        matcher(found.description_pattern)?.test(t.description),
      );
      if (rule) matched.push({ movement, rule });
      else noMatch += 1;
    }
    return { rules, matched, skipped, noMatch };
  }
  function applyRules(request: JsonObject): JsonObject {
    fromKeys(request, ["reaffirm", "dry_run", "actor"]);
    const reaffirm = request.reaffirm === true;
    const plan = rulePlan(reaffirm);
    const base = {
      profile_id: profileId,
      rules_evaluated: plan.rules.length,
      transactions_scanned: ledger.movements.length,
      matched: plan.matched.length,
      skipped_already_classified: plan.skipped,
      no_match: plan.noMatch,
      validation_code: null,
      validation_messages: [],
    };
    // A dry run counts only what it would match: the product sends none of
    // the live counts with it.
    if (request.dry_run === true)
      return {
        ...base,
        rules_evaluated: null,
        transactions_scanned: null,
        matched: null,
        skipped_already_classified: null,
        no_match: null,
        outcome: "dry_run",
        dry_run: true,
        count: plan.matched.length,
        would_match: plan.matched.map(({ movement, rule }) => ({
          transaction_id: movement.transaction.transaction_id,
          description: movement.transaction.description,
          matched_rule_id: rule.rule_id,
          classification: rule.classification,
        })),
        applied: null,
        bucket_event_count: 0,
      };
    const stamp = now();
    for (const { movement, rule } of plan.matched) {
      const t = movement.transaction;
      t.business_classification = rule.classification;
      t.category_id = rule.category_id;
      t.classified_by = `rule:${rule.rule_id}`;
      t.classified_at = stamp;
      t.modified_at = stamp;
    }
    return {
      ...base,
      outcome: "applied",
      dry_run: null,
      count: null,
      would_match: null,
      applied: plan.matched.map(({ movement, rule }) => ({
        transaction_id: movement.transaction.transaction_id,
        matched_rule_id: rule.rule_id,
        classification: rule.classification,
      })),
      bucket_event_count: plan.matched.length,
    };
  }

  // ---- Ratios --------------------------------------------------------------

  const yearOf = (request: JsonObject) => {
    const year = whole(request.year);
    if (year < 1900 || year > 9999) invalid();
    return year;
  };
  const ratioRows = () =>
    [...ratios.entries()]
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([category, ratio]) => ({ category, ratio }));
  const unitRatio = (value: JsonValue | undefined) => {
    const ratio = required(value);
    if (!/^(0(\.\d+)?|1(\.0+)?)$/.test(ratio)) invalid();
    return ratio;
  };

  // ---- Counterparties ------------------------------------------------------

  function counterparty(request: JsonObject): JsonObject {
    fromKeys(request, [
      "action",
      "tax_identifier",
      "country_code",
      "territorial_scope",
      "identification_state",
      "evidenced_scope",
      "note",
      "asserted_by",
    ]);
    const action = required(request.action);
    if (!["view", "confirm", "withdraw"].includes(action)) invalid();
    const tax = required(request.tax_identifier).toUpperCase();
    const country = text(request.country_code);
    const state = text(request.identification_state);
    if ((country && country.length !== 2) || (state && state.length !== 2))
      invalid();
    let facts = counterparties.get(tax) ?? null;
    let changed = false;
    if (action === "confirm") {
      facts = {
        counterparty_key: hex64(`counterparty:${tax}`),
        canonical_tax_identifier: tax,
        territorial_scope: text(request.territorial_scope),
        identification_state: state,
        asserted_by: "person",
        asserted_at: now(),
        note: text(request.note) ?? "",
      };
      counterparties.set(tax, facts);
      changed = true;
    } else if (action === "withdraw" && facts) {
      counterparties.delete(tax);
      facts = null;
      changed = true;
    }
    const prefix = tax.slice(0, 2);
    const evidenced = /^[A-Z]{2}$/.test(prefix) && prefix !== "ES";
    return {
      profile_id: profileId,
      action,
      tax_identifier: tax,
      country_code: country,
      evidenced_scope: text(request.evidenced_scope),
      facts: facts as JsonValue,
      resolution: {
        territorial_scope:
          (facts?.territorial_scope as string | null | undefined) ??
          (evidenced ? "eu_member" : null),
        territorial_source: facts
          ? "operator_assertion"
          : evidenced
            ? "document_evidence"
            : null,
        identification_state:
          (facts?.identification_state as string | null | undefined) ?? null,
        identification_source: facts?.identification_state
          ? "operator_assertion"
          : null,
        confirmed_scope:
          (facts?.territorial_scope as string | null | undefined) ?? null,
        evidenced_scope: evidenced ? "eu_member" : null,
        contradiction_detail: null,
      },
      recorded: action === "confirm" ? true : null,
      withdrawn: action === "withdraw" ? changed : null,
      changed,
    };
  }

  // ---- Own accounts --------------------------------------------------------

  const designationRows = () =>
    designations.map((found) => ({
      role: found.role,
      modelo: found.modelo,
      own_account_id: found.id,
    }));
  const accountResult = (
    action: string,
    id: string | null,
    changed: boolean,
  ): JsonObject => ({
    profile_id: profileId,
    action,
    own_account_id: id,
    accounts: ledger.accounts as unknown as JsonValue,
    designations: designationRows(),
    changed,
  });
  const registerRefusal = (): never => {
    throw new SetupStopped("REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION");
  };
  /** The own account actions that carry no account details. */
  function ownAccount(request: JsonObject): JsonObject {
    const action = required(request.action);
    const id = text(request.own_account_id);
    const account = ledger.accounts.find(
      (found) => found.own_account_id === id,
    );
    const role = text(request.role);
    const modelo = text(request.modelo);
    if (modelo !== null && !/^\d{3}$/.test(modelo)) invalid();
    switch (action) {
      case "list":
        return accountResult(action, null, false);
      case "close": {
        const closed = required(request.closed_on);
        if (!id || !DATE.test(closed)) return invalid();
        if (!account || account.closed_on) return registerRefusal();
        if (account.opened_on && closed < account.opened_on)
          return registerRefusal();
        account.closed_on = closed;
        return accountResult(action, id, true);
      }
      case "remove": {
        if (!id) return invalid();
        if (!account) return registerRefusal();
        // An account movements name is closed, never removed.
        if (ledger.movements.some((movement) => movement.own_account_id === id))
          return registerRefusal();
        if (designations.some((found) => found.id === id))
          return registerRefusal();
        ledger.accounts.splice(ledger.accounts.indexOf(account), 1);
        return accountResult(action, id, true);
      }
      case "designate": {
        if (!id || (role !== "charge" && role !== "refund")) return invalid();
        if (!account) return registerRefusal();
        const at = designations.findIndex(
          (found) => found.role === role && found.modelo === modelo,
        );
        const next = { role, modelo, id };
        if (at >= 0) designations.splice(at, 1, next);
        else designations.push(next);
        return accountResult(action, id, true);
      }
      case "undesignate": {
        if (id || (role !== "charge" && role !== "refund")) return invalid();
        const at = designations.findIndex(
          (found) => found.role === role && found.modelo === modelo,
        );
        if (at < 0) return registerRefusal();
        designations.splice(at, 1);
        return accountResult(action, null, true);
      }
      default:
        return invalid();
    }
  }

  // ---- Prorrata ------------------------------------------------------------

  const entryOf = (found: Prorrata): JsonObject => ({
    ejercicio: found.ejercicio,
    regime: found.regime,
    especial_transition: found.transition,
    sector_id: found.sector_id,
    interrupted: false,
    provisional_percentage: found.provisional
      ? decimal(found.provisional)
      : null,
    provisional_provenance: found.provenance,
    authorisation_reference: found.reference,
    definitive_percentage: found.definitive ? decimal(found.definitive) : null,
    definitive_volume_con_derecho: found.con ? decimal(found.con) : null,
    definitive_volume_sin_derecho: found.sin ? decimal(found.sin) : null,
    source_observation_ref: null,
    source_registry_snapshot_refs: [],
    schema_version: "1",
  });
  const sectorOf = (found: (typeof sectors)[number]): JsonObject => ({
    sector_id: found.sector_id,
    letra: found.letra,
    member_activity_codes: found.codes,
  });
  const prorrataResult = (
    operation: string,
    extra: JsonObject = {},
  ): JsonObject => ({
    operation_id: operation,
    profile_id: profileId,
    outcome: "success",
    entry: null,
    sector_definition: null,
    seed_source: null,
    findings: [],
    prior_ejercicio: null,
    count: prorrata.length,
    refusal: null,
    ...extra,
  });
  const prorrataRefusal = (
    operation: string,
    code: string,
    reason: string,
    detail: string,
    extra: JsonObject = {},
  ): never => {
    throw new SetupStopped(code, {
      ...prorrataResult(operation),
      outcome: "refused",
      count: null,
      refusal: {
        code,
        reason,
        detail,
        ejercicio: null,
        sector_id: null,
        findings: [],
        accepted_provenances: [],
        existing_provenance: null,
        ...extra,
      },
    });
  };
  const VALIDATION = "REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION";
  const findEntry = (ejercicio: number, sector: string | null) =>
    prorrata.find(
      (found) => found.ejercicio === ejercicio && found.sector_id === sector,
    );
  const sectorKnown = (sector: string | null) =>
    sector === null || sectors.some((found) => found.sector_id === sector);

  function elect(operation: string, request: JsonObject): JsonObject {
    const ejercicio = whole(request.ejercicio);
    const percentage = decimalOf(request.percentage);
    if (Number(percentage) > 100) invalid();
    const provenance = text(request.provenance);
    const reference = text(request.reference);
    const sector = text(request.sector_id);
    const evidence = text(request.evidence_reference);
    if (operation === "revoke_especial" && !evidence) invalid();
    if (!sectorKnown(sector))
      return prorrataRefusal(
        operation,
        VALIDATION,
        "validation",
        "Unknown sector.",
        {
          ejercicio,
          sector_id: sector,
        },
      );
    if (provenance === null || provenance === CARRIED)
      return prorrataRefusal(
        operation,
        "REFUSED_PRORRATA_ELECTION",
        "provenance_required",
        provenance === CARRIED
          ? "A carried prior definitive is seeded, not elected."
          : "An election names where its percentage comes from.",
        { ejercicio, accepted_provenances: PROVENANCES },
      );
    if (!PROVENANCES.includes(provenance))
      return prorrataRefusal(
        operation,
        "REFUSED_PRORRATA_ELECTION",
        "provenance_not_electable",
        "That provenance is computed, not declared.",
        { ejercicio, accepted_provenances: PROVENANCES },
      );
    if (!reference)
      return prorrataRefusal(
        operation,
        "REFUSED_PRORRATA_ELECTION",
        "reference_required",
        "This provenance stands on a document: name its reference.",
        { ejercicio },
      );
    const existing = findEntry(ejercicio, sector);
    if (operation === "revoke_especial" && existing?.regime !== "especial")
      return prorrataRefusal(
        operation,
        VALIDATION,
        "validation",
        "The ejercicio is not in prorrata especial.",
        { ejercicio, sector_id: sector },
      );
    const entry: Prorrata = {
      ejercicio,
      regime: operation === "elect_especial" ? "especial" : "general",
      sector_id: sector,
      provisional: percentage,
      provenance,
      reference,
      transition:
        operation === "elect_especial"
          ? evidence
            ? { kind: "opcion", evidence_reference: evidence }
            : null
          : operation === "revoke_especial"
            ? { kind: "revocacion", evidence_reference: evidence! }
            : null,
      definitive: existing?.definitive ?? null,
      con: existing?.con ?? null,
      sin: existing?.sin ?? null,
    };
    if (existing) prorrata.splice(prorrata.indexOf(existing), 1, entry);
    else prorrata.push(entry);
    return prorrataResult(operation, { entry: entryOf(entry) });
  }

  const prorrataWrites: Record<string, Handler> = {
    "ledger.prorrata.seed": (request) => {
      fromKeys(request, ["ejercicio"]);
      const ejercicio = whole(request.ejercicio);
      const prior = findEntry(ejercicio - 1, null);
      if (!prior?.definitive)
        return prorrataRefusal(
          "seed",
          "REFUSED_PROFILE_PRORRATA_WHOLE_SEED",
          "seed_source_absent",
          `No definitive percentage for ${ejercicio - 1} to seed from.`,
          { ejercicio },
        );
      if (findEntry(ejercicio, null))
        return prorrataRefusal(
          "seed",
          "REFUSED_PROFILE_PRORRATA_WHOLE_SEED",
          "seed_existing_blocked",
          `${ejercicio} already has an entry.`,
          { ejercicio },
        );
      const entry: Prorrata = {
        ejercicio,
        regime: prior.regime,
        sector_id: null,
        provisional: prior.definitive,
        provenance: CARRIED,
        reference: null,
        transition: null,
        definitive: null,
        con: null,
        sin: null,
      };
      prorrata.push(entry);
      return prorrataResult("seed", {
        entry: entryOf(entry),
        prior_ejercicio: ejercicio - 1,
        seed_source: {
          modelo: "390",
          filing_year: ejercicio - 1,
          period: "0A",
          casilla_id: "108",
          stamped_revision_id: hex64(`m390:${ejercicio - 1}`),
          authority: "local_prior_observation",
        },
      });
    },
    "ledger.prorrata.declare_sector": (request) => {
      fromKeys(request, ["sector_id", "letra", "member_activity_codes"]);
      const sector = required(request.sector_id);
      const letra = required(request.letra);
      const codes = request.member_activity_codes ?? [];
      if (
        !Array.isArray(codes) ||
        codes.some((code) => typeof code !== "string")
      )
        return invalid();
      if (!SECTOR_LETTERS.includes(letra))
        return prorrataRefusal(
          "declare_sector",
          VALIDATION,
          "validation",
          "Not a differentiated-sector letter.",
          { sector_id: sector },
        );
      const declared = { sector_id: sector, letra, codes: codes as string[] };
      const at = sectors.findIndex((found) => found.sector_id === sector);
      if (at >= 0) sectors.splice(at, 1, declared);
      else sectors.push(declared);
      return prorrataResult("declare_sector", {
        sector_definition: sectorOf(declared),
      });
    },
    "ledger.prorrata.elect_general": (request) => {
      fromKeys(request, [
        "ejercicio",
        "percentage",
        "provenance",
        "reference",
        "sector_id",
      ]);
      return elect("elect_general", request);
    },
    "ledger.prorrata.elect_especial": (request) => {
      fromKeys(request, [
        "ejercicio",
        "percentage",
        "provenance",
        "reference",
        "sector_id",
        "evidence_reference",
      ]);
      return elect("elect_especial", request);
    },
    "ledger.prorrata.revoke_especial": (request) => {
      fromKeys(request, [
        "ejercicio",
        "percentage",
        "provenance",
        "reference",
        "sector_id",
        "evidence_reference",
      ]);
      return elect("revoke_especial", request);
    },
    "ledger.prorrata.seed_sector": (request) => {
      fromKeys(request, ["ejercicio", "sector_id"]);
      const ejercicio = whole(request.ejercicio);
      const sector = required(request.sector_id);
      const prior = findEntry(ejercicio - 1, sector);
      if (!sectorKnown(sector) || !prior?.definitive)
        return prorrataRefusal(
          "seed_sector",
          "REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE",
          "sector_prior_definitive_absent",
          `Sector ${sector} has no ${ejercicio - 1} definitive.`,
          { ejercicio, sector_id: sector },
        );
      const entry: Prorrata = {
        ...prior,
        ejercicio,
        provisional: prior.definitive,
        provenance: CARRIED,
        reference: null,
        transition: null,
        definitive: null,
        con: null,
        sin: null,
      };
      prorrata.push(entry);
      return prorrataResult("seed_sector", { entry: entryOf(entry) });
    },
    "ledger.prorrata.settle_sector": (request) => {
      fromKeys(request, [
        "ejercicio",
        "sector_id",
        "con_derecho_volume",
        "sin_derecho_volume",
      ]);
      const ejercicio = whole(request.ejercicio);
      const sector = required(request.sector_id);
      const con = decimalOf(request.con_derecho_volume);
      const sin = decimalOf(request.sin_derecho_volume);
      const entry = findEntry(ejercicio, sector);
      if (!entry)
        return prorrataRefusal(
          "settle_sector",
          "REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE",
          "sector_settlement_entry_absent",
          `Sector ${sector} has no ${ejercicio} entry to settle.`,
          { ejercicio, sector_id: sector },
        );
      const total = Number(con) + Number(sin);
      entry.con = con;
      entry.sin = sin;
      // LIVA art. 104.Dos: rounded up to the next whole unit.
      entry.definitive = String(
        total === 0 ? 0 : Math.ceil((Number(con) / total) * 100),
      );
      return prorrataResult("settle_sector", { entry: entryOf(entry) });
    },
  };

  // ---- Capital goods -------------------------------------------------------

  function declareCapital(request: JsonObject): JsonObject {
    fromKeys(request, [
      "identifier",
      "description",
      "acquisition_year",
      "acquisition_ledger_id",
      "cuota_soportada",
      "prorrata_inicial_pct",
      "kind",
      "art108_elegible",
      "prorrata_sector_id",
      "disposal_year",
      "disposal_regime",
    ]);
    const identifier = required(request.identifier);
    const year = whole(request.acquisition_year);
    if (year < 1 || year > 2099) invalid();
    const cuota = decimalOf(request.cuota_soportada);
    const pct = decimalOf(request.prorrata_inicial_pct);
    const kind = required(request.kind);
    const refuse = (reason: string, extra: JsonObject = {}): never => {
      throw new SetupStopped("REFUSED_PROFILE_BIENES_INVERSION_VALIDATION", {
        outcome: "refused",
        profile_id: profileId,
        record: null,
        count: null,
        refusal: {
          code: "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION",
          reason,
          missing: null,
          identifier,
          ...extra,
        },
      });
    };
    if (!CAPITAL_KINDS.includes(kind) || Number(pct) > 100)
      return refuse("validation");
    const disposalYear = request.disposal_year ?? null;
    const disposalRegime = text(request.disposal_regime);
    if ((disposalYear === null) !== (disposalRegime === null))
      return refuse("disposal_incomplete", {
        missing: disposalYear === null ? "year" : "regime",
      });
    if (disposalRegime !== null && !DISPOSAL_REGIMES.includes(disposalRegime))
      return refuse("validation");
    if (capital.some((found) => found.identifier === identifier))
      return refuse("duplicate_identifier");
    const record: JsonObject = {
      identifier,
      description: required(request.description),
      acquisition_year: year,
      cuota_soportada: decimal(cuota),
      prorrata_inicial_pct: decimal(pct),
      kind,
      art108_elegible: request.art108_elegible !== false,
      acquisition_ledger_id: required(request.acquisition_ledger_id),
      prorrata_sector_id: text(request.prorrata_sector_id),
      disposal:
        disposalYear === null
          ? null
          : { year: whole(disposalYear), regime: disposalRegime },
      deduccion_efectuada: decimal(
        ((Number(cuota) * Number(pct)) / 100).toFixed(2).replace(/\.?0+$/, ""),
      ),
      schema_version: "1",
    };
    capital.push(record);
    return {
      outcome: "declared",
      profile_id: profileId,
      record,
      count: capital.length,
      refusal: null,
    };
  }

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

  // ---- Health and reset ----------------------------------------------------

  const sealedBlockers = () =>
    ledger.movements.some((movement) => movement.sealed)
      ? [
          {
            work_unit_id: hex64("work-unit:303:2026:1T"),
            calculation_revision_id: hex64("revision:303:2026:1T"),
            revision_state: "PRESENTADO",
            modelo: "303",
            filing_year: 2026,
            period: "1T",
          },
        ]
      : [];
  function reset(request: JsonObject): JsonObject {
    fromKeys(request, ["reason", "dry_run", "actor"]);
    const reason = request.reason ?? "";
    if (typeof reason !== "string" || reason.length > 4096) invalid();
    const dryRun = request.dry_run === true;
    const blockers = sealedBlockers();
    const report = (removed: string[], done: boolean): JsonObject => ({
      profile_id: profileId,
      report: {
        bucket_id: profileId,
        dry_run: dryRun,
        actor: "person",
        reason,
        cascaded_purchase_invoice_evidence_ids: ledger.evidence.map(
          (found) => found.evidence_id,
        ),
        cascaded_attachment_ids: ledger.evidence.map(
          (found) => found.attachment_id,
        ),
        blocking_modelo_references: blockers,
        stale_draft_revision_references: [],
        bucket_event_ids: done ? events() : [],
        removed_transaction_ids: removed,
        reset: done,
      },
    });
    const ids = ledger.movements.map(
      (movement) => movement.transaction.transaction_id,
    );
    if (dryRun) return report(ids, false);
    // A reset that finalized revisions cite is refused before it writes.
    if (blockers.length) throw new SetupStopped("ERROR_TRANSACTION_VALIDATION");
    ledger.movements.splice(0);
    ledger.evidence.splice(0);
    return report(ids, true);
  }

  /** Declarations calculated before their movements last changed. */
  function staleFilings(period: JsonValue | null): JsonObject[] {
    const year =
      period && typeof period === "object" && !Array.isArray(period)
        ? period.filing_year
        : null;
    if (year !== null && year !== 2026) return [];
    return [
      {
        modelo: "303",
        filing_year: 2026,
        period: "3T",
        calculation_revision_id: hex64("revision:303:2026:3T"),
        work_unit_id: hex64("work-unit:303:2026:3T"),
        changed_count: 6,
        removed_count: 0,
        covers_current_fact_set: false,
      },
    ];
  }

  const provisional = assetOperations({
    now,
    hex64,
    invalid,
    stop: (reason, detail) => {
      throw new SetupStopped(reason, detail);
    },
  });
  const reads: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.rule.list": (request) => {
      fromKeys(request, []);
      return {
        profile_id: profileId,
        rules: ordered() as unknown as JsonValue,
      };
    },
    "ledger.ratios.list": (request) => {
      fromKeys(request, ["year"]);
      const year = yearOf(request);
      const rows = ratioRows();
      return {
        profile_id: profileId,
        year,
        outcome: "available",
        rows,
        count: rows.length,
      };
    },
    "ledger.ratios.eligible": (request) => {
      fromKeys(request, ["year", "output_language"]);
      const year = yearOf(request);
      const rows = Object.entries(RATIO_ELIGIBLE_FIXTURE).map(
        ([category, found]) => ({
          category,
          label: found.label,
          notes: found.notes,
          proportionality_kind: found.kind,
          override_present: ratios.has(category),
        }),
      );
      return { profile_id: profileId, year, rows, count: rows.length };
    },
    "ledger.ratios.validate": (request) => {
      fromKeys(request, []);
      return {
        profile_id: profileId,
        profile_present: true,
        eligible_count: Object.keys(RATIO_ELIGIBLE_FIXTURE).length,
        overrides_count: ratios.size,
        missing_overrides: [],
        findings: [],
      };
    },
    "ledger.llm-diagnostics": (request) => {
      fromKeys(request, ["since", "until", "low_confidence_threshold"]);
      const threshold = decimalOf(request.low_confidence_threshold);
      return {
        profile_id: profileId,
        operation_id: "ledger.llm-diagnostics",
        outcome: "completed",
        effect: "none",
        since: text(request.since),
        until: text(request.until),
        low_confidence_threshold: decimal(threshold),
        report: {
          since: text(request.since),
          until: text(request.until),
          low_confidence_threshold: decimal(threshold),
          usage_providers: [
            {
              provider: "local-model",
              calls: 47,
              cache_hits: 6,
              input_tokens: 51_230,
              output_tokens: 8_904,
              total_tokens: 60_134,
              cost_estimate_usd: decimal("0"),
              unpriced_calls: 0,
            },
          ],
          total_calls: 47,
          total_cache_hits: 6,
          total_input_tokens: 51_230,
          total_output_tokens: 8_904,
          total_cost_estimate_usd: decimal("0"),
          total_unpriced_calls: 0,
          confidence_providers: [
            {
              provider: "local-model",
              classified_count: 41,
              low_confidence_count: Number(threshold) >= 0.7 ? 6 : 2,
              medium_confidence_count: 14,
              high_confidence_count: 21,
              min_confidence: decimal("0.41"),
              max_confidence: decimal("0.97"),
              mean_confidence: decimal("0.79"),
            },
          ],
          total_classified: 41,
          total_low_confidence: Number(threshold) >= 0.7 ? 6 : 2,
        },
      };
    },
    "ledger.prorrata.list": (request) => {
      fromKeys(request, []);
      return {
        profile_id: profileId,
        entries: [...prorrata]
          .sort((a, b) => b.ejercicio - a.ejercicio)
          .map(entryOf),
        sectors: sectors.map(sectorOf),
        count: prorrata.length,
      };
    },
    "ledger.bienes_inversion.list": (request) => {
      fromKeys(request, []);
      return { profile_id: profileId, rows: capital };
    },
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
    ...provisional.reads,
  };
  const writes: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.rule.add": addRule,
    "ledger.rule.apply": applyRules,
    "ledger.ratios.set": (request) => {
      fromKeys(request, ["category", "ratio", "year"]);
      const category = required(request.category);
      const ratio = unitRatio(request.ratio);
      yearOf(request);
      if (!(category in RATIO_ELIGIBLE_FIXTURE))
        throw new SetupStopped("REFUSED_CLI_VALIDATION_BOUNDARY");
      const prior = ratios.get(category) ?? null;
      ratios.set(category, ratio);
      return {
        profile_id: profileId,
        requested_category: category,
        category,
        ratio,
        prior_ratio: prior,
      };
    },
    "ledger.ratios.unset": (request) => {
      fromKeys(request, ["category"]);
      const category = required(request.category);
      const prior = ratios.get(category) ?? null;
      const result = {
        profile_id: profileId,
        requested_category: category,
        category,
        outcome: prior === null ? "no_override" : "cleared",
        prior_ratio: prior,
      };
      if (prior === null)
        throw new SetupStopped("REFUSED_CLI_VALIDATION_BOUNDARY", result);
      ratios.delete(category);
      return result;
    },
    "ledger.counterparty": counterparty,
    ...prorrataWrites,
    "ledger.bienes_inversion.declare": declareCapital,
    ...inventoryWrites,
    ...provisional.writes,
    "ledger.participation.rebuild": (request) => {
      fromKeys(request, []);
      return {
        profile_id: profileId,
        transaction_count: ledger.movements.length,
        participation_count: ledger.movements.filter((found) => found.sealed)
          .length,
        revision_count: 2,
        stale_removed_count: 0,
      };
    },
    "ledger.reset": reset,
  };

  return {
    reads,
    writes,
    ownAccount,
    designations: designationRows,
    staleFilings,
  };
}
