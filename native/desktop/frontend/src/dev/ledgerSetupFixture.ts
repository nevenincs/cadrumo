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

/** The categories whose business use a ratio states, and the kind of
 * proportion each is. */
const RATIO_ELIGIBLE: Record<
  string,
  { kind: string; standard: string | null }
> = {
  suministros_home_office_internet: {
    kind: "usage_ratio_home_area",
    standard: "0.3",
  },
  suministros_home_office_luz: {
    kind: "usage_ratio_home_area",
    standard: "0.3",
  },
  telefonia_movil: { kind: "usage_ratio_personal", standard: null },
  vehiculo_combustible: { kind: "usage_ratio_personal", standard: null },
  vehiculo_mantenimiento: { kind: "usage_ratio_personal", standard: null },
};

const PROVENANCES = ["aeat_autorizada", "inicio_actividad"];
const CARRIED = "carried_prior_definitiva";
const SECTOR_LETTERS = ["a", "b", "c", "d"];
const VALUATION = ["fifo", "pmp", "coste_medio"];
const MOVEMENT_KINDS = ["opening", "purchase", "cogs", "count"];
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
};
type Asset = {
  revisions: { revision: JsonObject; revision_id: string }[];
  claims: JsonObject[];
};

/** The scenario ledger's setup answers, held beside the movements. */
export function setupOperations(ledger: FixtureLedger, tools: Tools) {
  const { profileId, hex64, events, now } = tools;
  const ratios = new Map<string, string>([["telefonia_movil", "0.5"]]);
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
      actividad_id: "ACT-01",
      year: 2026,
      valuation_method: "fifo",
      opening_stock: "410",
      movements: [
        {
          movement_id: "INV-001",
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
    },
  ];
  const assets = new Map<string, Asset>();

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
    if (request.dry_run === true)
      return {
        ...base,
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
  const bookProjection = (book: Book): JsonObject => ({
    actividad_id: book.actividad_id,
    year: book.year,
    valuation_method: book.valuation_method,
    opening_stock: decimal(book.opening_stock),
    opening_layers: [],
    closing_authority_fingerprints: book.closing,
    period_movements: book.movements,
    schema_version: "1",
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
      if (movement.kind === "opening" || movement.kind === "purchase")
        lots.push({ quantity, cost: units(movement.unit_cost) });
      else if (movement.kind === "cogs") {
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
  const inventoryWrites: Record<string, Handler> = {
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
      const unit =
        request.unit_cost == null ? null : decimalOf(request.unit_cost);
      const base =
        request.taxable_base == null ? null : decimalOf(request.taxable_base);
      const shape = {
        profile_id: profileId,
        ledger: null,
        bucket_event_ids: [],
      };
      if (!book) return notFound(actividad, year, shape);
      if (book.movements.some((found) => found.movement_id === id))
        return inventoryRefusal(
          "REFUSED_PROFILE_INVENTORY_VALIDATION",
          "duplicate_movement_id",
          { actividad_id: actividad, year, movement_id: id },
          shape,
        );
      book.movements.push({
        movement_id: id,
        movement_date: date,
        kind,
        sku: "papel-a3",
        quantity: decimal(quantity),
        unit_cost: unit === null ? null : decimal(unit),
        taxable_base: base === null ? null : decimal(base),
        iva_rate: decimal("0.21"),
        iva_amount: null,
        deductible_iva_ratio: decimal("1"),
      });
      return {
        outcome: "added",
        profile_id: profileId,
        ledger: bookProjection(book),
        bucket_event_ids: events(),
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

  // ---- Activity assets -----------------------------------------------------

  const authority = {
    logical_generation: hex64("authority:generation"),
    reader_incarnation: hex64("authority:reader"),
  };
  const assetRefusal = (code: string, shape: JsonObject = {}): never => {
    throw new SetupStopped(code, {
      profile_id: profileId,
      authority,
      outcome: "refused",
      refusal: { code, precondition_verdict: null, accelerated_da18: null },
      ...shape,
    });
  };
  const REVISION_REQUIRED = [
    "asset_id",
    "revision_number",
    "acquisition",
    "acquisition_shape",
    "asset_kind",
    "basis",
    "in_service_date",
    "opening_history",
    "acquired_condition",
    "amortization",
  ];
  /** Whether a revision states every fact it needs, at any depth. */
  const complete = (value: JsonValue): boolean =>
    value !== null &&
    (typeof value !== "object" ||
      (Array.isArray(value)
        ? value.every(complete)
        : Object.values(value).every(
            (inner) => inner === undefined || complete(inner),
          )));
  const revisionOf = (request: JsonObject) => {
    fromKeys(request, ["revision"]);
    const revision = request.revision;
    if (
      typeof revision !== "object" ||
      revision === null ||
      Array.isArray(revision)
    )
      return invalid();
    if (REVISION_REQUIRED.some((key) => !(key in revision))) invalid();
    return revision;
  };
  const historyOf = (asset: Asset): JsonObject => ({
    revisions: asset.revisions.map((found) => found.revision),
    claims: asset.claims,
  });
  const writeRevision = (revision: JsonObject, correcting: boolean) => {
    const id = required(revision.asset_id);
    const required_ = { ...revision };
    delete required_.supersedes_revision_id;
    delete required_.out_of_service_date;
    delete required_.building_construction_date;
    delete required_.vehicle_affectation;
    if (!complete(required_))
      return assetRefusal("REFUSED_ACTIVIDAD_ASSET_INCOMPLETE", {
        history: null,
      });
    const asset = assets.get(id);
    const latest = asset?.revisions.at(-1);
    if (correcting) {
      if (
        !asset ||
        !latest ||
        revision.supersedes_revision_id !== latest.revision_id
      )
        return assetRefusal("REFUSED_ACTIVIDAD_ASSET_VALIDATION", {
          history: null,
        });
    } else if (asset)
      return assetRefusal("REFUSED_ACTIVIDAD_ASSET_VALIDATION", {
        history: null,
      });
    const held = asset ?? { revisions: [], claims: [] };
    held.revisions.push({
      revision,
      revision_id: hex64(`revision:${JSON.stringify(revision)}`),
    });
    assets.set(id, held);
    return {
      profile_id: profileId,
      authority,
      outcome: "succeeded",
      refusal: null,
      history: historyOf(held),
    };
  };
  const assetWrites: Record<string, Handler> = {
    "ledger.actividad-asset.create": (request) =>
      writeRevision(revisionOf(request), false),
    "ledger.actividad-asset.correct": (request) =>
      writeRevision(revisionOf(request), true),
    "ledger.actividad-asset.claim": (request) => {
      fromKeys(request, ["forecast", "creating_operation"]);
      const forecast = request.forecast;
      required(request.creating_operation);
      if (
        typeof forecast !== "object" ||
        forecast === null ||
        Array.isArray(forecast)
      )
        return invalid();
      const asset = assets.get(required(forecast.asset_id));
      if (!asset)
        return assetRefusal("REFUSED_ACTIVIDAD_ASSET_VALIDATION", {
          claim_result: null,
          claim_id: null,
        });
      const claimId = hex64(`claim:${JSON.stringify(forecast)}`);
      const existing = asset.claims.find((found) => found.claim_id === claimId);
      const claim: JsonObject = existing ?? {
        ...forecast,
        claim_id: claimId,
        creating_operation: required(request.creating_operation),
      };
      if (!existing) asset.claims.push(claim);
      return {
        profile_id: profileId,
        authority,
        outcome: "succeeded",
        refusal: null,
        claim_result: {
          history: historyOf(asset),
          claim,
          reused_existing_claim: existing !== undefined,
        },
        claim_id: claimId,
      };
    },
  };
  const assetReads: Record<string, Handler> = {
    "ledger.actividad-asset.inspect": (request) => {
      fromKeys(request, ["asset_id"]);
      const id = required(request.asset_id);
      const asset = assets.get(id);
      if (!asset)
        return assetRefusal("REFUSED_ACTIVIDAD_ASSET_VALIDATION", {
          asset_id: id,
          revisions: null,
        });
      return {
        profile_id: profileId,
        authority,
        outcome: "succeeded",
        refusal: null,
        asset_id: id,
        revisions: asset.revisions,
      };
    },
    "ledger.actividad-asset.forecast": (request) => {
      fromKeys(request, [
        "asset_id",
        "covered_from",
        "covered_until",
        "requested_free_amount",
        "supersedes_claim_id",
      ]);
      const id = required(request.asset_id);
      const from = required(request.covered_from);
      const until = required(request.covered_until);
      if (!DATE.test(from) || !DATE.test(until) || until < from) invalid();
      const asset = assets.get(id);
      const latest = asset?.revisions.at(-1);
      if (!asset || !latest)
        return assetRefusal("REFUSED_ACTIVIDAD_ASSET_VALIDATION", {
          forecast: null,
        });
      const revision = latest.revision;
      const basis = Number(
        (
          (revision.basis as JsonObject | null)?.basis_amount as {
            decimal?: string;
          } | null
        )?.decimal ?? 0,
      );
      const coefficient = Number(
        (
          (revision.amortization as JsonObject | null)?.linear_coefficient as {
            decimal?: string;
          } | null
        )?.decimal ?? 0,
      );
      if (!coefficient)
        return assetRefusal("REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED", {
          forecast: null,
        });
      const day = 86_400_000;
      const days = Math.round((Date.parse(until) - Date.parse(from)) / day) + 1;
      const year = Number(from.slice(0, 4));
      const leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
      const calendar = leap ? 366 : 365;
      const amount = ((basis * coefficient * days) / calendar).toFixed(2);
      return {
        profile_id: profileId,
        authority,
        outcome: "succeeded",
        refusal: null,
        forecast: {
          asset_id: id,
          asset_revision_id: latest.revision_id,
          tax_year: year,
          covered_from: from,
          covered_until: until,
          service_days: days,
          calendar_days: calendar,
          amount: decimal(amount),
          schedule_fingerprint: hex64(`schedule:${id}:${from}:${until}`),
          authority_generation: authority.logical_generation,
          source_reference: "ley-35-2006:art-30",
        },
      };
    },
    "ledger.actividad-asset.filing-handoff": (request) => {
      fromKeys(request, ["tax_year", "m130_period"]);
      const year = whole(request.tax_year);
      const period = required(request.m130_period);
      if (!["1T", "2T", "3T", "4T"].includes(period)) invalid();
      const claims = [...assets.values()].flatMap((asset) =>
        asset.claims.filter((claim) => claim.tax_year === year),
      );
      const total = claims
        .reduce(
          (sum, claim) =>
            sum + Number((claim.amount as { decimal: string }).decimal),
          0,
        )
        .toFixed(2);
      const ids = claims.map((claim) => claim.claim_id as string);
      const projection = (
        casilla: string,
        amount: string,
        named: string[],
      ) => ({
        target_casilla_id: casilla,
        tax_year: year,
        claim_ids: named,
        amount: decimal(amount),
      });
      return {
        profile_id: profileId,
        authority,
        outcome: "succeeded",
        refusal: null,
        tax_year: year,
        m130_period: period,
        filing_handoff: {
          material_m100: projection("0156", total, ids),
          intangible_m100: projection("0157", "0", []),
          material_m130: projection("02", total, ids),
          intangible_m130: projection("02", "0", []),
        },
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
      fromKeys(request, ["year"]);
      const year = yearOf(request);
      const rows = Object.entries(RATIO_ELIGIBLE).map(([category, found]) => ({
        category,
        proportionality_kind: found.kind,
        default_ratio: found.standard,
        override_present: ratios.has(category),
      }));
      return { profile_id: profileId, year, rows, count: rows.length };
    },
    "ledger.ratios.validate": (request) => {
      fromKeys(request, []);
      const missing = Object.keys(RATIO_ELIGIBLE).filter(
        (category) =>
          RATIO_ELIGIBLE[category]!.standard === null && !ratios.has(category),
      );
      return {
        profile_id: profileId,
        profile_present: true,
        eligible_count: Object.keys(RATIO_ELIGIBLE).length,
        overrides_count: ratios.size,
        missing_overrides: missing,
        findings: missing.map((category) => ({
          category,
          kind: "missing_override",
          detail: "",
        })),
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
        })),
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
    ...assetReads,
  };
  const writes: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.rule.add": addRule,
    "ledger.rule.apply": applyRules,
    "ledger.ratios.set": (request) => {
      fromKeys(request, ["category", "ratio", "year"]);
      const category = required(request.category);
      const ratio = unitRatio(request.ratio);
      yearOf(request);
      if (!(category in RATIO_ELIGIBLE))
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
    ...assetWrites,
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
