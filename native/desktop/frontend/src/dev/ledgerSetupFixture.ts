// The scenario ledger's setup: its rules, business-use ratios,
// counterparties and model diagnostics; its own-account, prorrata, capital
// goods, inventory and activity asset registers; and its declaration-link
// rebuild and reset. Each answer follows its registered
// contract: a request the contract would not decode is refused before
// anything runs, and a refusal the ledger reports after reading settles as
// a refusal whose detail is the operation's own result, as the host passes
// it on. Everything it answers is synthetic.

import { isClassification } from "../shell/ledgerContract";
import type {
  JsonObject,
  JsonValue,
  LedgerDefinitionId,
} from "../shell/ledger";
import servedEntryOptions from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };

const entryWord = (family: string, value: string, word = value) => ({
  value,
  label_key: `application.ledger.entry_options.${family}.${word}`,
});
const SPENDING_CATEGORIES = new Set(
  servedOptions("spending_category").map((option) => option.value),
);
const isSpendingCategory = (id: string) => SPENDING_CATEGORIES.has(id);
/** What `ledger.entry-options` serves: the registry's families as recorded,
 * and a trimmed copy of the country, currency and Modelo 210 ones. */
const ENTRY_OPTION_FAMILIES = {
  ...Object.fromEntries(
    servedEntryOptions.families.map(({ family, options }) => [family, options]),
  ),
  country: ["DE", "ES", "FR", "PT"].map((value) => ({
    value,
    label_key: null,
  })),
  currency: ["EUR", "GBP", "USD"].map((value) => ({ value, label_key: null })),
  deduction_fact_kind: ["domestic_current", "rectification"].map((value) =>
    entryWord("deduction_fact_kind", value),
  ),
  m210_payer_mode: ["single_payer", "multiple_payers_code_35"].map((value) =>
    entryWord("m210_payer_mode", value),
  ),
  m210_tipo_renta: [
    entryWord("m210_income_concept", "02", "inmobiliaria"),
    entryWord("m210_income_concept", "24", "general"),
  ],
};
import { assetOperations } from "./assetsFixture";
import { inventoryOperations } from "./ledgerInventoryFixture";
import { prorrataOperations } from "./ledgerProrrataFixture";
import {
  SetupKeptInPart,
  SetupRequestUnrecorded,
  SetupStopped,
  fromKeys,
  invalid,
  required,
  servedOptions,
  text,
  whole,
  DATE,
  decimal,
  decimalOf,
  type Handler,
  type Tools,
} from "./ledgerSetupSupport";
import { RECORDED_DEFAULT_LANGUAGE, answerPeriods } from "./periodRecording";
import { withholdingOperations } from "./ledgerWithholdingFixture";
import { servedYearBounds } from "./servedYearAuthority";
import { RATIO_ELIGIBLE_FIXTURE, ratioWording } from "./fixtures/ledgerRatios";
import type {
  FixtureLedger,
  FixtureMovement,
  FixtureRule,
} from "./fixtures/ledger";

/** The scenario ledger's setup answers, held beside the movements. */
export function setupOperations(ledger: FixtureLedger, tools: Tools) {
  const { profileId, today, hex64, events, now } = tools;
  const prorrataWork = prorrataOperations(tools);
  const inventoryWork = inventoryOperations(tools);
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
    if (!isClassification(classification)) invalid();
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
    if (year < servedYearBounds.first || year > servedYearBounds.last)
      invalid();
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
    if (action !== "confirm" && text(request.note)) invalid();
    if (
      action === "confirm" &&
      (!text(request.asserted_by) ||
        (!text(request.territorial_scope) &&
          !text(request.identification_state)))
    )
      invalid();
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
        asserted_by: text(request.asserted_by),
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
    const evidenced = text(request.evidenced_scope);
    return {
      profile_id: profileId,
      action,
      tax_identifier: tax,
      country_code: country,
      evidenced_scope: text(request.evidenced_scope),
      facts: action === "confirm" ? (facts as JsonValue) : null,
      resolution:
        action === "view"
          ? {
              territorial_scope:
                (facts?.territorial_scope as string | null | undefined) ??
                evidenced,
              territorial_source: facts?.territorial_scope
                ? "operator_assertion"
                : evidenced
                  ? "document_evidence"
                  : null,
              identification_state:
                (facts?.identification_state as string | null | undefined) ??
                null,
              identification_source: facts?.identification_state
                ? "operator_assertion"
                : null,
              confirmed_scope: null,
              evidenced_scope: null,
              contradiction_detail: null,
            }
          : null,
      recorded: action === "confirm" ? true : null,
      withdrawn: action === "withdraw" ? changed : null,
      changed,
      conflict_context: null,
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

  // ---- Health and reset ----------------------------------------------------

  // A sealed movement belongs to a declaration filed in the scenario's year.
  const sealedYear = Number(today.slice(0, 4));
  const sealedBlockers = () =>
    ledger.movements.some((movement) => movement.sealed)
      ? [
          {
            work_unit_id: hex64(`work-unit:303:${sealedYear}:1T`),
            calculation_revision_id: hex64(`revision:303:${sealedYear}:1T`),
            revision_state: "PRESENTADO",
            modelo: "303",
            filing_year: sealedYear,
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
    const staleYear = Number(today.slice(0, 4));
    if (year !== null && year !== staleYear) return [];
    return [
      {
        modelo: "303",
        filing_year: staleYear,
        period: "3T",
        calculation_revision_id: hex64(`revision:303:${staleYear}:3T`),
        work_unit_id: hex64(`work-unit:303:${staleYear}:3T`),
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
    unrecorded: (): never => {
      throw new SetupRequestUnrecorded();
    },
    stop: (reason, detail) => {
      throw new SetupStopped(reason, detail);
    },
  });
  const withholding = withholdingOperations({
    profileId,
    today,
    now,
    hex64,
    invalid,
    stop: (reason, detail) => {
      throw new SetupStopped(reason, detail);
    },
    keptInPart: (reason, detail) => {
      throw new SetupKeptInPart(reason, detail);
    },
    fileOf: tools.fileOf,
    language: tools.language,
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
      const language = String(request.output_language);
      const rows = Object.entries(RATIO_ELIGIBLE_FIXTURE).map(
        ([category, found]) => ({
          category,
          ...ratioWording(found, language),
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
    "ledger.entry-options": (request) => {
      fromKeys(request, ["output_language", "periods"]);
      const language = request.output_language ?? RECORDED_DEFAULT_LANGUAGE;
      const periods = answerPeriods(
        language as Parameters<typeof answerPeriods>[0],
        (request.periods ?? {}) as Parameters<typeof answerPeriods>[1],
      );
      // A year or day the recording of the read holds no answer for is
      // refused: nothing here works a period out.
      if (periods === null) throw new SetupStopped("ERROR_PERIOD_NOT_RECORDED");
      return {
        profile_id: profileId,
        families: Object.entries(ENTRY_OPTION_FAMILIES).map(
          ([family, options]) => ({ family, options }),
        ),
        classifications: servedEntryOptions.classifications,
        limits: servedEntryOptions.limits,
        periods,
      };
    },
    ...prorrataWork.reads,
    ...inventoryWork.reads,
    ...provisional.reads,
    ...withholding.reads,
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
    ...prorrataWork.writes,
    ...inventoryWork.writes,
    ...provisional.writes,
    ...withholding.writes,
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
