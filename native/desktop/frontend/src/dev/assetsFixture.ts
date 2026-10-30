// The scenario ledger's answers to the Assets tab's operations: a register of
// synthetic elements (see `assetsSeed.ts`) read as the backend reads it, and
// the writes the tab sends, answered with the reasons the backend gives. A
// write changes what the next read says, but the figures of a plan stay the
// seeded ones: only a claim, a description, a correction and a baja move
// anything, and a plan is never recalculated. An element made through create
// starts with a plan worked out for a linear election and the reason there is
// none for any other; the request it is made from is judged as the backend
// judges a revision.

import type {
  AcquisitionCandidate,
  AssetListRow,
  DescriptorFacts,
  DisposalCalculation,
  DisposalFacts,
  PlanClaim,
  PlanRow,
  ReasonFact,
  TimelineEvent,
} from "@/shell/ledgerSetup";
import type {
  JsonObject,
  JsonValue,
  LedgerDefinitionId,
} from "../shell/ledger";
import {
  ADMITTED_METHODS,
  SEED_ELEMENTS,
  TABLE_GROUPS,
  type SeedElement,
} from "./assetsSeed";

type Handler = (request: JsonObject) => JsonObject;

type Tools = {
  now: () => string;
  hex64: (text: string) => string;
  /** Throws the refusal of a request its contract would not decode. */
  invalid: () => never;
  /** Throws a refusal the ledger settles with its own result as detail. */
  stop: (reason: string, detail: JsonObject) => never;
};

/** The scenario's date: the register reads as of it. */
const TODAY = "2026-10-30";
const REGIME = "normal";
const VALIDATION = "REFUSED_ACTIVIDAD_ASSET_VALIDATION";
const INCOMPLETE = "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE";
const UNSUPPORTED = "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED";
const CLAIM_CONFLICT = "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT";
const ERRORS = "ledger.actividad_asset.errors.";
const STATE = "ledger.actividad_asset.non_deductible_iva_state.";
const FINDING = "ledger.actividad_asset.disposal_finding.";
const FAMILY = "ledger.actividad_asset.";
const FIRST_SUPPORTED_YEAR = 2022;
/** The last year the registry carries official tables for; later years are estimates. */
const LAST_ADMITTED_YEAR = 2026;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

const json = <T>(value: T): JsonObject => value as unknown as JsonObject;
const dec = (value: string) => ({ decimal: value });

// ---- Amounts, in whole cents --------------------------------------------------

const toCents = (text: string): number => Math.round(Number(text) * 100);
const fromCents = (cents: number): string => (cents / 100).toFixed(2);

const leap = (year: number) =>
  (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
const daysBetween = (from: string, until: string) =>
  Math.round((Date.parse(until) - Date.parse(from)) / 86_400_000);
const later = (a: string, b: string) => (a > b ? a : b);
const earlier = (a: string, b: string) => (a < b ? a : b);

/** The charge of a span on the tax year's cumulative curve: each end is
 * rounded, so contiguous spans add up to the year's figure. */
function chargeFor(
  annual: string,
  window: string,
  from: string,
  until: string,
  year: number,
): string {
  const days = leap(year) ? 366 : 365;
  const upTo = (point: string) =>
    Math.round((toCents(annual) * daysBetween(window, point)) / days);
  return fromCents(upTo(until) - upTo(from));
}

// ---- The register ----------------------------------------------------------------

/** What the register holds of one element. */
type Element = Omit<SeedElement, "id"> & {
  id: string;
  /** The facts of the latest description. */
  descriptor: DescriptorFacts | null;
  /** The day after the last day of service, if it has a baja. */
  outOfService: string | null;
  /** The baja the element carries, if any. */
  baja: DisposalFacts | null;
};

const PURCHASES: AcquisitionCandidate[] = [
  {
    transaction_id: "t-portatil",
    booked_date: "2026-05-06",
    description: "Portátil de trabajo",
    amount: dec("1089.00"),
    currency: "EUR",
    paid_in_euro: dec("1089.00"),
    taxable_base: dec("900.00"),
    iva_amount: dec("189.00"),
    non_deductible_iva_state: "known",
    non_deductible_iva_state_key: `${STATE}known`,
    non_deductible_iva: dec("0.00"),
    invoice_evidence_id:
      "9f2c0a1e4b7d3a58c61e0f93d7b2a4c8e5f1073a6d9b28c4e0a7f35b16d82c94",
    evidence_fingerprint:
      "9f2c0a1e4b7d3a58c61e0f93d7b2a4c8e5f1073a6d9b28c4e0a7f35b16d82c94",
  },
  {
    transaction_id: "t-silla",
    booked_date: "2026-02-11",
    description: "Silla ergonómica",
    amount: dec("242.00"),
    currency: "EUR",
    paid_in_euro: dec("242.00"),
    taxable_base: dec("200.00"),
    iva_amount: dec("42.00"),
    non_deductible_iva_state: "unknown",
    non_deductible_iva_state_key: `${STATE}unknown`,
    non_deductible_iva: null,
    invoice_evidence_id: null,
    evidence_fingerprint: null,
  },
  {
    transaction_id: "t-efectivo",
    booked_date: "2025-11-30",
    description: "Compra pagada en efectivo",
    amount: dec("150.00"),
    currency: "EUR",
    paid_in_euro: dec("150.00"),
    taxable_base: null,
    iva_amount: null,
    non_deductible_iva_state: "unknown",
    non_deductible_iva_state_key: `${STATE}unknown`,
    non_deductible_iva: null,
    invoice_evidence_id: null,
    evidence_fingerprint: null,
  },
  {
    transaction_id: "t-monitor",
    booked_date: "2025-09-03",
    description: "Monitor de diseño",
    amount: dec("400.00"),
    currency: "USD",
    paid_in_euro: null,
    taxable_base: null,
    iva_amount: null,
    non_deductible_iva_state: "unknown",
    non_deductible_iva_state_key: `${STATE}unknown`,
    non_deductible_iva: null,
    invoice_evidence_id: null,
    evidence_fingerprint: null,
  },
];

const textOf = (found: unknown): string | null =>
  typeof found === "string" && found !== "" ? found : null;
const decimalOf = (found: unknown): string | null =>
  found !== null &&
  typeof found === "object" &&
  typeof (found as { decimal?: unknown }).decimal === "string"
    ? (found as { decimal: string }).decimal
    : null;

export function assetOperations(tools: Tools) {
  const { now, hex64, invalid, stop } = tools;

  const elements = new Map<string, Element>(
    SEED_ELEMENTS.map((seed) => {
      const copy = structuredClone(seed);
      return [
        seed.id,
        {
          ...copy,
          descriptor:
            copy.list.name === null
              ? null
              : {
                  name: copy.list.name,
                  serial_number: copy.list.serial_number,
                  description: null,
                  document_kind: null,
                  document_number: null,
                  supplier_name: null,
                  supplier_tax_id: null,
                },
          outOfService: null,
          baja: null,
        },
      ];
    }),
  );
  /** The purchases an element has taken as its acquisition. */
  const taken = new Set<string>();

  const authority = {
    logical_generation: hex64("authority:generation"),
    reader_incarnation: hex64("authority:reader"),
  };
  const ok = {
    profile_id: "story-profile",
    authority,
    outcome: "succeeded",
    refusal: null,
  };

  /** A refusal as the backend states it: a code, a reason key and its facts. */
  const refuse = (
    code: string,
    key: string | null,
    facts: Record<string, string> = {},
    shape: JsonObject = {},
    missing: string[] = [],
  ): never =>
    stop(
      code,
      json({
        ...ok,
        outcome: "refused",
        refusal: {
          code,
          precondition_verdict:
            missing.length > 0 ? { missing_field_keys: missing } : null,
          accelerated_da18: null,
          reason_key: key === null ? null : `${ERRORS}${key}`,
          reason_facts: Object.entries(facts)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([name, value]): ReasonFact => ({ key: name, value })),
        },
        ...shape,
      }),
    );

  const required = (value: unknown): string => {
    if (typeof value !== "string" || value === "") return invalid();
    return value;
  };
  const exact = (request: JsonObject, keys: string[]) => {
    if (Object.keys(request).some((key) => !keys.includes(key))) invalid();
  };
  const find = (id: string): Element | undefined => elements.get(id);

  const editionOf = (year: number) =>
    year < FIRST_SUPPORTED_YEAR
      ? null
      : {
          revision_id: String(Math.min(year, 2025)),
          authored_filing_year: Math.min(year, 2025),
          projected: year > 2025,
        };

  const history = (element: Element): JsonObject =>
    json({
      revisions: element.revisions.map((found) => found.revision),
      claims: element.rows.flatMap((row) => row.claims),
      descriptors: [],
      events: element.events,
    });

  const record = (
    element: Element,
    kind: string,
    origin: string,
    effect: string | null,
    changes: { field: string; before: string | null; after: string | null }[],
    extra: Partial<TimelineEvent> = {},
  ) => {
    const keyOf = (field: string, value: string | null) =>
      value !== null && Object.hasOwn(TOKEN_FIELDS, field)
        ? `${FAMILY}${TOKEN_FIELDS[field]}.${value}`
        : null;
    element.events.push({
      sequence: element.events.length + 1,
      recorded_at: now(),
      kind,
      asset_id: element.id,
      record_id: hex64(`${kind}:${element.id}:${element.events.length + 1}`),
      effect_date: effect,
      origin,
      changes: changes.map((change) => ({
        ...change,
        before_key: keyOf(change.field, change.before),
        after_key: keyOf(change.field, change.after),
      })),
      affects_calculation: kind !== "descriptor",
      claim: null,
      ...extra,
    });
  };

  // ---- Restating a year after a claim -------------------------------------------

  /** The parts of [from, until) the effective claims leave uncovered. */
  const uncovered = (row: PlanRow, from: string, until: string) => {
    const covered = row.claims
      .filter((claim) => claim.effective)
      .map((claim) => [claim.covered_from, claim.covered_until] as const)
      .sort(([a], [b]) => a.localeCompare(b));
    const gaps: { covered_from: string; covered_until: string }[] = [];
    let cursor = from;
    for (const [start, end] of covered) {
      if (start > cursor)
        gaps.push({
          covered_from: cursor,
          covered_until: earlier(start, until),
        });
      cursor = later(cursor, end);
    }
    if (cursor < until)
      gaps.push({ covered_from: cursor, covered_until: until });
    return gaps.filter((gap) => gap.covered_from < gap.covered_until);
  };

  const serviceWindow = (element: Element, row: PlanRow) => {
    const start = later(element.list.in_service_date, `${row.tax_year}-01-01`);
    const end =
      element.outOfService === null
        ? `${row.tax_year + 1}-01-01`
        : earlier(element.outOfService, `${row.tax_year + 1}-01-01`);
    return { start, end };
  };

  const restate = (element: Element, row: PlanRow) => {
    const { start, end } = serviceWindow(element, row);
    const effective = row.claims.filter((claim) => claim.effective);
    row.claimed = dec(
      fromCents(
        effective.reduce(
          (sum, claim) => sum + toCents(claim.amount.decimal),
          0,
        ),
      ),
    );
    const gaps = uncovered(row, start, end);
    row.claimable_intervals = gaps;
    row.claim_state =
      effective.length === 0
        ? row.claim_state
        : gaps.length > 0
          ? "partial"
          : row.claims.some((claim) => claim.superseded_by !== null)
            ? "superseded"
            : "claimed";
  };

  const recount = (element: Element) => {
    const stale = element.events.filter(
      (event) =>
        event.claim !== null &&
        !event.claim.matches_current_schedule &&
        element.rows.some((row) =>
          row.claims.some(
            (claim) => claim.effective && claim.claim_id === event.record_id,
          ),
        ),
    ).length;
    element.list.findings = {
      missing: element.rows.filter(
        (row) => row.claim_state === "missing" || row.claim_state === "partial",
      ).length,
      incomplete: element.rows.filter((row) => row.absence === "incomplete")
        .length,
      conflict: 0,
      stale,
    };
  };

  // ---- Reads ---------------------------------------------------------------------

  const notFound = (shape: JsonObject): never =>
    refuse(VALIDATION, "asset_not_found", {}, shape);

  const reads: Partial<Record<LedgerDefinitionId, Handler>> = {
    "ledger.actividad-asset.list": (request) => {
      exact(request, []);
      const rows = [...elements.values()]
        .map((element) => element.list)
        .sort((a, b) => a.asset_id.localeCompare(b.asset_id));
      const years = [...new Set(rows.flatMap((row) => row.years))].sort(
        (a, b) => a - b,
      );
      return json({ ...ok, rows, years });
    },
    "ledger.actividad-asset.plan": (request) => {
      exact(request, ["asset_id"]);
      const id = required(request.asset_id);
      const element = find(id);
      if (!element)
        return notFound({
          asset_id: null,
          rows: null,
          limits: null,
          advisories: [],
        });
      // The warning on a used element's election, which changes no figure.
      const current = obj(latest(element).revision.amortization);
      const used =
        latest(element).revision.acquired_condition === "used" &&
        current?.method === "linear" &&
        element.rows.some((row) => row.edition !== null);
      return json({
        ...ok,
        asset_id: id,
        rows: element.rows,
        limits: element.limits,
        advisories: used
          ? [
              {
                kind: "used_element_group_limit",
                label_key: `${FAMILY}plan_advisory.used_element_group_limit`,
              },
            ]
          : [],
      });
    },
    "ledger.actividad-asset.timeline": (request) => {
      exact(request, ["asset_id"]);
      const id = required(request.asset_id);
      const element = find(id);
      if (!element) return notFound({ asset_id: null, events: null });
      return json({ ...ok, asset_id: id, events: element.events });
    },
    "ledger.actividad-asset.form-options": (request) => {
      exact(request, ["asset_kind", "tax_year"]);
      const kind = required(request.asset_kind);
      const year = request.tax_year;
      if (typeof year !== "number" || !Object.hasOwn(TABLE_GROUPS, kind))
        return invalid();
      const edition = editionOf(year);
      if (edition === null)
        return refuse(
          VALIDATION,
          "tax_year_without_edition",
          { tax_year: String(year) },
          { options: null },
        );
      return json({
        ...ok,
        options: {
          tax_year: year,
          asset_kind: kind,
          regime: REGIME,
          edition,
          methods: ADMITTED_METHODS[kind],
          table_groups: TABLE_GROUPS[kind],
        },
      });
    },
    "ledger.actividad-asset.acquisition-candidates": (request) => {
      exact(request, []);
      return json({
        ...ok,
        candidates: PURCHASES.filter(
          (purchase) => !taken.has(purchase.transaction_id),
        ),
      });
    },
  };

  // ---- Writes --------------------------------------------------------------------

  // ---- Revisions -------------------------------------------------------------

  /** The fields of a revision that state a token, which the history words by
   * the catalogue key of the token. */
  const TOKEN_FIELDS: Record<string, string> = {
    acquired_condition: "acquired_condition",
    acquisition_shape: "acquisition_shape",
    "basis.stage": "basis_stage",
    "opening_history.status": "opening_history_status",
  };
  const obj = (found: unknown): JsonObject | null =>
    typeof found === "object" && found !== null && !Array.isArray(found)
      ? (found as JsonObject)
      : null;

  /** A revision as the history compares it: each stated fact by its path. */
  const flatten = (
    value: unknown,
    prefix = "",
  ): Record<string, string | null> => {
    if (value === null || value === undefined)
      return prefix === "" ? {} : { [prefix]: null };
    const stated = decimalOf(value);
    if (stated !== null) return { [prefix]: stated };
    if (typeof value !== "object" || Array.isArray(value))
      return { [prefix]: String(value) };
    return Object.assign(
      {},
      ...Object.entries(value).map(([name, item]) =>
        flatten(item, prefix === "" ? name : `${prefix}.${name}`),
      ),
    );
  };
  const LINKS = ["revision_number", "supersedes_revision_id"];
  const changesBetween = (before: JsonObject | null, after: JsonObject) => {
    const old = before === null ? {} : flatten(before);
    const next = flatten(after);
    return Object.keys({ ...old, ...next })
      .filter(
        (path) =>
          !LINKS.includes(path) &&
          !path.startsWith("acquisition.") &&
          (old[path] ?? null) !== (next[path] ?? null),
      )
      .map((path) => ({
        field: path,
        before: old[path] ?? null,
        after: next[path] ?? null,
      }));
  };

  const latest = (element: Element) => element.revisions.at(-1)!;
  const STAGES = ["taxpayer_owned", "business_allocated", "whole_property"];
  const TABLE_METHODS = ["linear", "constant_percentage", "sum_of_digits"];

  /** The backend's judgement of a revision: the refusal it gives, if any. */
  const judgeRevision = (revision: JsonObject, shape: JsonObject): void => {
    const acquisition = obj(revision.acquisition);
    const basis = obj(revision.basis);
    const opening = obj(revision.opening_history);
    const election = obj(revision.amortization);
    if (!acquisition || !basis || !opening || !election) return invalid();
    for (const key of [
      "observed_transaction_id",
      "invoice_evidence_id",
      "evidence_fingerprint",
    ])
      if (typeof acquisition[key] !== "string") return invalid();
    const kind = textOf(revision.asset_kind);
    if (kind === null || !Object.hasOwn(TABLE_GROUPS, kind)) return invalid();
    if (revision.acquisition_shape !== "primary_purchase") return invalid();
    const inService = textOf(revision.in_service_date);
    if (inService === null || !DATE.test(inService)) return invalid();
    if (!["new", "used"].includes(String(revision.acquired_condition)))
      return invalid();
    if (
      decimalOf(basis.basis_amount) === null ||
      decimalOf(basis.non_deductible_iva) === null ||
      !STAGES.includes(String(basis.stage))
    )
      return invalid();
    if (
      basis.stage === "taxpayer_owned" &&
      decimalOf(basis.business_use_share) === null
    )
      return refuse(INCOMPLETE, "business_use_share_missing", {}, shape, [
        "basis.business_use_share",
      ]);
    if (
      basis.stage === "business_allocated" &&
      textOf(basis.prior_allocation_provenance) === null
    )
      return refuse(INCOMPLETE, null, {}, shape, [
        "basis.prior_allocation_provenance",
      ]);
    if (basis.stage === "whole_property")
      return refuse(INCOMPLETE, "allocation_components_missing", {}, shape, [
        "basis.construction_cost",
      ]);
    // The opening history.
    const accumulated = decimalOf(opening.accumulated_amount);
    const through = opening.covered_through_tax_year;
    if (opening.status === "known") {
      if (accumulated === null)
        return refuse(INCOMPLETE, "opening_history_amount_missing", {}, shape, [
          "opening_history.accumulated_amount",
        ]);
      if (toCents(accumulated) > 0) {
        if (typeof through !== "number")
          return refuse(INCOMPLETE, null, {}, shape, [
            "opening_history.covered_through_tax_year",
          ]);
        if (through < Number(inService.slice(0, 4)))
          return refuse(
            VALIDATION,
            "opening_year_before_in_service",
            { opening_tax_year: String(through) },
            shape,
          );
      } else if (through !== undefined && through !== null) return invalid();
    } else if (opening.status === "missing") {
      if (
        (opening.accumulated_amount ?? null) !== null ||
        (opening.amortization_method ?? null) !== null ||
        (through ?? null) !== null
      )
        return invalid();
    } else return invalid();
    // The election.
    if (election.regime !== REGIME) return invalid();
    const method = textOf(election.method);
    if (method === null) return invalid();
    if (!ADMITTED_METHODS[kind]!.includes(method))
      return refuse(
        UNSUPPORTED,
        "method_not_enrolled_for_kind",
        { asset_kind: kind, method, regime: REGIME },
        shape,
      );
    const classKey = textOf(election.authority_class_key);
    const group = TABLE_GROUPS[kind]!.find(
      (found) => found.class_key === classKey,
    );
    if (TABLE_METHODS.includes(method) && classKey === null)
      return refuse(INCOMPLETE, "table_class_required", { method }, shape, [
        "amortization.authority_class_key",
      ]);
    if (classKey !== null && !group)
      return refuse(
        VALIDATION,
        "table_class_wrong_kind",
        { asset_kind: kind, class_key: classKey },
        shape,
      );
    const coefficient = decimalOf(election.linear_coefficient);
    if (coefficient !== null) {
      if (method !== "linear") return invalid();
      if (
        group &&
        (Number(coefficient) > Number(group.maximum_coefficient.decimal) ||
          Number(coefficient) < Number(group.minimum_coefficient.decimal))
      )
        return refuse(
          VALIDATION,
          "elected_coefficient_out_of_range",
          {
            elected: coefficient,
            minimum: group.minimum_coefficient.decimal,
            maximum: group.maximum_coefficient.decimal,
          },
          shape,
        );
    }
    const used = obj(election.used_original_price);
    if (used !== null) {
      if (method !== "linear" || revision.acquired_condition !== "used")
        return refuse(
          VALIDATION,
          "used_original_price_requires_used_asset",
          {},
          shape,
        );
      if (
        !["known", "expert_valuation"].includes(String(used.determination)) ||
        decimalOf(used.original_price) === null ||
        textOf(used.evidence_reference) === null
      )
        return invalid();
    }
    if (method === "sum_of_digits") {
      if (typeof election.sum_of_digits_period_years !== "number")
        return refuse(INCOMPLETE, "sum_of_digits_period_required", {}, shape, [
          "amortization.sum_of_digits_period_years",
        ]);
      if (!["descending", "ascending"].includes(String(election.digit_order)))
        return refuse(INCOMPLETE, null, {}, shape, [
          "amortization.digit_order",
        ]);
    }
    if (method === "low_value_free") {
      const low = obj(election.low_value);
      if (
        !low ||
        textOf(low.election_reference) === null ||
        textOf(low.new_material_evidence_reference) === null
      )
        return refuse(INCOMPLETE, "low_value_election_required", {}, shape, [
          "amortization.low_value",
        ]);
    }
    if (
      method === "research_development_free" &&
      textOf(election.research_development_evidence_reference) === null
    )
      return refuse(INCOMPLETE, null, {}, shape, [
        "amortization.research_development_evidence_reference",
      ]);
  };

  const describe: Handler = (request) => {
    exact(request, ["asset_id", "descriptor"]);
    const id = required(request.asset_id);
    const element = find(id);
    if (!element) return notFound({ history: null });
    const given = request.descriptor as unknown as DescriptorFacts;
    if (typeof given !== "object" || given === null) return invalid();
    if (given.name.trim() === "")
      return refuse(INCOMPLETE, null, {}, { history: null }, ["name"]);
    const before = element.descriptor;
    const facts: (keyof DescriptorFacts)[] = [
      "name",
      "serial_number",
      "description",
      "document_kind",
      "document_number",
      "supplier_name",
      "supplier_tax_id",
    ];
    const changes = facts
      .filter((fact) => (before?.[fact] ?? null) !== (given[fact] ?? null))
      .map((fact) => ({
        field: fact,
        before: before?.[fact] ?? null,
        after: given[fact] ?? null,
      }));
    if (changes.length > 0) {
      element.descriptor = { ...given, name: given.name.trim() };
      element.list.name = element.descriptor.name;
      element.list.serial_number = given.serial_number ?? null;
      record(
        element,
        "descriptor",
        "ledger.actividad-asset.describe",
        null,
        changes,
      );
    }
    return json({ ...ok, history: history(element) });
  };

  /** The citations a new element's election carries: the provisions the
   * register already cites for an election of its kind and method, else none
   * and a list that says it is partial. */
  const citationsFor = (kind: string, method: string) => {
    const like = SEED_ELEMENTS.find(
      (seed) =>
        seed.list.asset_kind === kind &&
        seed.list.method === method &&
        seed.limits.legal_citations.length > 0,
    );
    return like
      ? {
          legal_citations: structuredClone(like.limits.legal_citations),
          legal_citations_complete: like.limits.legal_citations_complete,
        }
      : { legal_citations: [], legal_citations_complete: false };
  };

  /** The plan a new element starts with. Only a linear election whose opening
   * history is known is worked out; any other starts with the reason it is
   * not. */
  const startingRows = (revision: JsonObject, annual: string | null) => {
    const kind = textOf(revision.asset_kind)!;
    const inService = textOf(revision.in_service_date)!;
    const election = obj(revision.amortization)!;
    const method = textOf(election.method)!;
    const basis = decimalOf(obj(revision.basis)!.basis_amount)!;
    const opening = obj(revision.opening_history)!;
    const group = TABLE_GROUPS[kind]!.find(
      (found) => found.class_key === textOf(election.authority_class_key),
    );
    const first = Number(inService.slice(0, 4));
    const through =
      typeof opening.covered_through_tax_year === "number"
        ? opening.covered_through_tax_year
        : null;
    let left =
      opening.status === "known"
        ? toCents(basis) - toCents(decimalOf(opening.accumulated_amount)!)
        : null;
    let minimum = 0;
    let minimumComplete = true;
    const rows: PlanRow[] = [];
    const base = (year: number, days: number | null): PlanRow => {
      const calendar = leap(year) ? 366 : 365;
      const edition = editionOf(year);
      const start = later(inService, `${year}-01-01`);
      const end = `${year + 1}-01-01`;
      const span = daysBetween(start, end);
      if (edition === null || !group) minimumComplete = false;
      else
        minimum += Math.round(
          (toCents(basis) * Number(group.minimum_coefficient.decimal) * span) /
            calendar,
        );
      return {
        tax_year: year,
        method,
        coefficient: null,
        planned: null,
        absence: null,
        absence_reason_key: null,
        absence_reason_facts: [],
        claimed: dec("0.00"),
        claim_state: year > Number(TODAY.slice(0, 4)) ? "not_due" : "missing",
        claimable_intervals: [],
        claimable_refusal_key: null,
        edition,
        service_days: days,
        calendar_days: days === null ? null : calendar,
        claims: [],
        minimum_through: dec(fromCents(Math.min(toCents(basis), minimum))),
        minimum_complete: minimumComplete,
      };
    };
    if (left === null) {
      for (
        let year = first;
        year <= Math.max(first, 2026) && rows.length < 6;
        year++
      ) {
        const row = base(year, null);
        row.absence = "incomplete";
        row.absence_reason_key = `${ERRORS}opening_history_missing`;
        row.claimable_refusal_key = `${ERRORS}opening_history_missing`;
        row.claim_state = "missing";
        rows.push(row);
      }
      return rows;
    }
    if (method !== "linear" || annual === null) {
      const row = base(first, null);
      row.absence = [
        "low_value_free",
        "research_development_free",
        "small_enterprise_employment_free",
      ].includes(method)
        ? "free_election"
        : "unsupported";
      rows.push(row);
      return rows;
    }
    for (let year = first; rows.length < 15 && year <= 2032; year++) {
      const start = later(inService, `${year}-01-01`);
      const end = `${year + 1}-01-01`;
      const days = daysBetween(start, end);
      const row = base(year, days);
      rows.push(row);
      if (row.edition === null) {
        row.absence = "edition_unavailable";
        row.claim_state = "edition_unavailable";
        row.service_days = null;
        row.calendar_days = null;
        continue;
      }
      if (through !== null && year <= through) {
        row.absence = "covered_by_opening";
        row.service_days = null;
        row.calendar_days = null;
        row.claim_state = "not_due";
        continue;
      }
      if (left <= 0) {
        row.absence = "basis_exhausted";
        row.claim_state = "not_due";
        break;
      }
      const charge = Math.min(
        left,
        toCents(chargeFor(annual, start, start, end, year)),
      );
      left -= charge;
      row.planned = dec(fromCents(charge));
      row.coefficient = dec(
        decimalOf(election.linear_coefficient) ??
          group!.maximum_coefficient.decimal,
      );
      row.claimable_intervals = [{ covered_from: start, covered_until: end }];
    }
    return rows;
  };

  const create: Handler = (request) => {
    exact(request, ["revision", "descriptor"]);
    const revision = obj(request.revision);
    const descriptor = request.descriptor as unknown as DescriptorFacts;
    if (!revision || typeof descriptor !== "object" || descriptor === null)
      return invalid();
    const shape = { history: null };
    const id = required(revision.asset_id);
    judgeRevision(revision, shape);
    if (revision.revision_number !== 1)
      return refuse(VALIDATION, "creation_requires_first_revision", {}, shape);
    const name =
      typeof descriptor.name === "string" ? descriptor.name.trim() : "";
    if (name === "") return refuse(INCOMPLETE, null, {}, shape, ["name"]);
    const existing = find(id);
    if (existing) return json({ ...ok, history: history(existing) });
    const acquisition = obj(revision.acquisition)!;
    const purchase = PURCHASES.find(
      (found) => found.transaction_id === acquisition.observed_transaction_id,
    );
    if (!purchase)
      return refuse(
        VALIDATION,
        "acquisition_transaction_missing",
        { transaction_id: String(acquisition.observed_transaction_id) },
        shape,
      );
    if (
      purchase.invoice_evidence_id !== acquisition.invoice_evidence_id ||
      purchase.evidence_fingerprint !== acquisition.evidence_fingerprint
    )
      return invalid();
    taken.add(purchase.transaction_id);

    const basis = obj(revision.basis)!;
    const election = obj(revision.amortization)!;
    const opening = obj(revision.opening_history)!;
    const kind = textOf(revision.asset_kind)!;
    const method = textOf(election.method)!;
    const inService = textOf(revision.in_service_date)!;
    const group = TABLE_GROUPS[kind]!.find(
      (found) => found.class_key === textOf(election.authority_class_key),
    );
    const amount = decimalOf(basis.basis_amount)!;
    const coefficient =
      decimalOf(election.linear_coefficient) ??
      group?.maximum_coefficient.decimal ??
      null;
    const annual =
      method === "linear" && coefficient !== null
        ? fromCents(Math.round(toCents(amount) * Number(coefficient)))
        : null;
    const rows = startingRows(revision, annual);
    const accumulated =
      opening.status === "known" ? decimalOf(opening.accumulated_amount) : null;
    const list: AssetListRow = {
      asset_id: id,
      name,
      serial_number: descriptor.serial_number ?? null,
      asset_kind: kind,
      state: "in_service",
      in_service_date: inService,
      method,
      revision_number: 1,
      basis: dec(fromCents(toCents(amount))),
      accumulated:
        accumulated === null ? null : dec(fromCents(toCents(accumulated))),
      pending:
        accumulated === null
          ? null
          : dec(fromCents(Math.max(toCents(amount) - toCents(accumulated), 0))),
      findings: { missing: 0, incomplete: 0, conflict: 0, stale: 0 },
      years: rows
        .map((row) => row.tax_year)
        .filter(
          (year) => year >= FIRST_SUPPORTED_YEAR && year <= LAST_ADMITTED_YEAR,
        ),
      projected_years: rows
        .map((row) => row.tax_year)
        .filter((year) => year > LAST_ADMITTED_YEAR),
    };
    const element: Element = {
      id,
      list,
      annual: annual ?? "0.00",
      forecasts: {},
      descriptor: { ...descriptor, name },
      outOfService: null,
      baja: null,
      disposal: null,
      rows,
      limits: {
        class_key: group?.class_key ?? null,
        class_label: group?.class_label ?? null,
        maximum_coefficient: group?.maximum_coefficient ?? null,
        minimum_coefficient: group?.minimum_coefficient ?? null,
        maximum_period_years: group?.maximum_period_years ?? null,
        maximum_period_ends_on:
          group === undefined
            ? null
            : `${Number(inService.slice(0, 4)) + Number(group.maximum_period_years.decimal)}${inService.slice(4)}`,
        ...citationsFor(kind, method),
        not_table_bound: group
          ? null
          : accumulated === null
            ? "authority_unavailable"
            : "free_election",
        unavailable_reason_key:
          group || accumulated !== null
            ? null
            : `${ERRORS}opening_history_missing`,
      },
      events: [],
      revisions: [
        {
          revision: structuredClone(revision),
          revision_id: hex64(`revision:${JSON.stringify(revision)}`),
        },
      ],
    };
    elements.set(id, element);
    recount(element);
    record(
      element,
      "revision",
      "ledger.actividad-asset.create",
      inService,
      changesBetween(null, revision),
    );
    record(element, "descriptor", "ledger.actividad-asset.describe", null, [
      { field: "name", before: null, after: name },
      ...(list.serial_number
        ? [{ field: "serial_number", before: null, after: list.serial_number }]
        : []),
    ]);
    return json({ ...ok, history: history(element) });
  };

  const correct: Handler = (request) => {
    exact(request, ["revision", "superseding_claims"]);
    const revision = obj(request.revision);
    const superseding = request.superseding_claims;
    if (!revision || !Array.isArray(superseding)) return invalid();
    const shape = { history: null };
    const id = required(revision.asset_id);
    const element = find(id);
    if (!element) return notFound(shape);
    const current = latest(element);
    if (
      revision.revision_number !== element.list.revision_number + 1 ||
      revision.supersedes_revision_id !== current.revision_id
    )
      return refuse(VALIDATION, "correction_must_supersede_current", {}, shape);
    judgeRevision(revision, shape);
    const changes = changesBetween(current.revision, revision);
    if (changes.length === 0) return invalid();
    const replaced = superseding.map((entry) => {
      const stated = obj(entry);
      if (!stated) return invalid();
      return required(stated.supersedes_claim_id);
    });
    const effective = element.rows.flatMap((row) =>
      row.claims.filter((claim) => claim.effective),
    );
    for (const claimId of replaced)
      if (!effective.some((claim) => claim.claim_id === claimId))
        return refuse(VALIDATION, "superseded_claim_not_effective", {}, shape);
    const stays = effective
      .filter((claim) => !replaced.includes(claim.claim_id))
      .reduce((sum, claim) => sum + toCents(claim.amount.decimal), 0);
    const newBasis = decimalOf(obj(revision.basis)!.basis_amount)!;
    if (stays > toCents(newBasis))
      return refuse(VALIDATION, "correction_below_effective_claims", {}, shape);
    // Every effective claim not recorded again under this revision no longer matches.
    for (const event of element.events)
      if (event.claim !== null && !replaced.includes(event.record_id))
        event.claim = {
          ...event.claim,
          matches_current_schedule: false,
          stale_reason: event.claim.stale_reason ?? "revision_changed",
        };
    const number = element.list.revision_number + 1;
    const revisionId = hex64(`revision:${JSON.stringify(revision)}`);
    element.revisions.push({
      revision: structuredClone(revision),
      revision_id: revisionId,
    });
    record(
      element,
      "revision",
      "ledger.actividad-asset.correct",
      textOf(revision.in_service_date),
      changes,
    );
    for (const row of element.rows)
      for (const old of [...row.claims]) {
        if (!old.effective || !replaced.includes(old.claim_id)) continue;
        const next: PlanClaim = {
          ...old,
          claim_id: hex64(`claim:${id}:${old.claim_id}:${number}`),
          effective: true,
          superseded_by: null,
          revision_id: revisionId,
        };
        old.effective = false;
        old.superseded_by = next.claim_id;
        row.claims.push(next);
        record(
          element,
          "claim",
          "ledger.actividad-asset.correct",
          next.covered_from,
          [
            {
              field: "amount",
              before: old.amount.decimal,
              after: next.amount.decimal,
            },
          ],
          {
            record_id: next.claim_id,
            claim: {
              used_by: [],
              matches_current_schedule: true,
              stale_reason: null,
            },
          },
        );
        restate(element, row);
      }
    element.list.revision_number = number;
    element.list.in_service_date = textOf(revision.in_service_date)!;
    element.list.method = textOf(obj(revision.amortization)!.method)!;
    element.list.basis = dec(fromCents(toCents(newBasis)));
    recount(element);
    return json({ ...ok, history: history(element) });
  };

  const inspect: Handler = (request) => {
    exact(request, ["asset_id"]);
    const id = required(request.asset_id);
    const element = find(id);
    if (!element) return notFound({ asset_id: id, revisions: null });
    return json({ ...ok, asset_id: id, revisions: element.revisions });
  };

  const PERIOD_END: Record<string, string> = {
    "1T": "03-31",
    "2T": "06-30",
    "3T": "09-30",
    "4T": "12-31",
  };
  const M100_CASILLA: Record<string, string> = {
    material: "0208",
    intangible: "0227",
  };

  /** Where the claims of a year go: Modelo 100 from the effective claims, and
   * Modelo 130 from the year's accrual through the quarter, each element by
   * its recorded claims or else its schedule. An element with a span neither
   * covers is named, never counted as zero. */
  const filingHandoff: Handler = (request) => {
    exact(request, ["tax_year", "m130_period"]);
    const year = request.tax_year;
    const period = required(request.m130_period);
    if (typeof year !== "number" || !Object.hasOwn(PERIOD_END, period))
      return invalid();
    const through = `${year}-${PERIOD_END[period]}`;
    const until = new Date(Date.parse(through) + 86_400_000)
      .toISOString()
      .slice(0, 10);
    const sorted = [...elements.values()].sort((a, b) =>
      a.id.localeCompare(b.id),
    );
    const m100 = (kind: string) => {
      const claims = sorted
        .filter((element) => element.list.asset_kind === kind)
        .flatMap((element) =>
          element.rows
            .filter((row) => row.tax_year === year)
            .flatMap((row) => row.claims.filter((claim) => claim.effective)),
        );
      return {
        target_casilla_id: M100_CASILLA[kind]!,
        tax_year: year,
        claim_ids: claims.map((claim) => claim.claim_id),
        amount: dec(
          fromCents(
            claims.reduce(
              (sum, claim) => sum + toCents(claim.amount.decimal),
              0,
            ),
          ),
        ),
      };
    };
    const m130 = (kind: string) => {
      const contributions: {
        asset_id: string;
        amount: { decimal: string };
        claim_id: string | null;
        schedule_fingerprint: string | null;
      }[] = [];
      const unavailable: string[] = [];
      for (const element of sorted) {
        if (element.list.asset_kind !== kind) continue;
        const row = element.rows.find((found) => found.tax_year === year);
        if (!row) continue;
        const { start, end } = serviceWindow(element, row);
        const stop = earlier(end, until);
        if (stop <= start) continue;
        const covered = row.claims.filter(
          (claim) => claim.effective && claim.covered_until <= stop,
        );
        for (const claim of covered)
          contributions.push({
            asset_id: element.id,
            amount: claim.amount,
            claim_id: claim.claim_id,
            schedule_fingerprint: null,
          });
        for (const gap of uncovered({ ...row, claims: covered }, start, stop)) {
          if (row.planned === null) {
            // Only a span the schedule cannot be worked out for is named.
            if (
              [
                "incomplete",
                "edition_unavailable",
                "unsupported",
                "conflict",
              ].includes(row.absence ?? "") &&
              !unavailable.includes(element.id)
            )
              unavailable.push(element.id);
            continue;
          }
          const window = later(element.list.in_service_date, `${year}-01-01`);
          contributions.push({
            asset_id: element.id,
            amount: dec(
              chargeFor(
                element.annual,
                window,
                gap.covered_from,
                gap.covered_until,
                year,
              ),
            ),
            claim_id: null,
            schedule_fingerprint: hex64(
              `schedule:${element.id}:${gap.covered_from}:${gap.covered_until}`,
            ),
          });
        }
      }
      return {
        target_casilla_id: "02",
        tax_year: year,
        amount: dec(
          fromCents(
            contributions.reduce(
              (sum, item) => sum + toCents(item.amount.decimal),
              0,
            ),
          ),
        ),
        contributions,
        unavailable_asset_ids: unavailable,
      };
    };
    return json({
      ...ok,
      tax_year: year,
      m130_period: period,
      filing_handoff: {
        material_m100: m100("material"),
        intangible_m100: m100("intangible"),
        material_m130: m130("material"),
        intangible_m130: m130("intangible"),
      },
    });
  };

  /** The backend's judgement of a stated baja: the refusal it gives, if any. */
  const judge = (
    element: Element,
    facts: DisposalFacts,
    shape: JsonObject,
  ): void => {
    const { reason, disposal_date: date } = facts;
    const proceeds = facts.proceeds.decimal;
    const costs = facts.transmission_costs.decimal;
    if (toCents(proceeds) < 0 || toCents(costs) < 0)
      refuse(VALIDATION, "disposal_amount_invalid", {}, shape);
    if (date < element.list.in_service_date)
      refuse(VALIDATION, "disposal_before_service", {}, shape);
    if (
      facts.later_affectation_on !== null &&
      facts.later_affectation_on > element.list.in_service_date
    )
      refuse(
        VALIDATION,
        "later_affectation_out_of_order",
        {
          later_affectation_on: facts.later_affectation_on,
          in_service_date: element.list.in_service_date,
        },
        shape,
      );
    if (reason === "donation")
      refuse(UNSUPPORTED, "disposal_donation_refused", { reason }, shape);
    if (reason === "scrapping" && toCents(proceeds) !== 0)
      refuse(
        VALIDATION,
        "disposal_scrapping_with_proceeds",
        { proceeds },
        shape,
      );
    if (
      reason === "withdrawal" &&
      (toCents(proceeds) !== 0 ||
        toCents(costs) !== 0 ||
        facts.market_value !== null)
    )
      refuse(VALIDATION, "disposal_withdrawal_with_amounts", {}, shape);
  };

  const statedDisposal = (request: JsonObject): DisposalFacts => {
    const given = request.disposal;
    if (typeof given !== "object" || given === null || Array.isArray(given))
      return invalid();
    const facts = given as unknown as DisposalFacts;
    if (
      typeof facts.disposal_date !== "string" ||
      !DATE.test(facts.disposal_date) ||
      typeof facts.reason !== "string" ||
      decimalOf(facts.proceeds) === null ||
      decimalOf(facts.transmission_costs) === null
    )
      return invalid();
    return facts;
  };

  const dispose: Handler = (request) => {
    exact(request, ["asset_id", "disposal"]);
    const element = find(required(request.asset_id));
    if (!element) return notFound({ history: null });
    const facts = statedDisposal(request);
    // The same baja stated again is the record already there.
    if (
      element.baja !== null &&
      JSON.stringify(element.baja) === JSON.stringify(facts)
    )
      return json({ ...ok, history: history(element) });
    if (element.baja !== null)
      return refuse(
        VALIDATION,
        "disposal_already_recorded",
        { disposal_date: element.baja.disposal_date },
        { history: null },
      );
    judge(element, facts, { history: null });
    // Every claim stays as recorded, under a revision that is no longer current.
    for (const event of element.events)
      if (event.claim !== null)
        event.claim = {
          ...event.claim,
          matches_current_schedule: false,
          stale_reason: event.claim.stale_reason ?? "revision_changed",
        };
    const changes = [
      { field: "disposal.disposal_date", after: facts.disposal_date },
      { field: "disposal.reason", after: facts.reason },
      { field: "disposal.proceeds", after: facts.proceeds.decimal },
      {
        field: "disposal.transmission_costs",
        after: facts.transmission_costs.decimal,
      },
      { field: "disposal.market_value", after: decimalOf(facts.market_value) },
      {
        field: "disposal.prior_free_depreciation_regime",
        after: facts.prior_free_depreciation_regime,
      },
      {
        field: "disposal.later_affectation_on",
        after: facts.later_affectation_on,
      },
    ]
      .filter((change) => change.after !== null)
      .map((change) => ({ ...change, before: null }));
    record(
      element,
      "baja",
      "ledger.actividad-asset.dispose",
      facts.disposal_date,
      changes,
    );
    // The baja is a revision of its own, which the history chains to the last.
    const before = latest(element).revision;
    const afterBaja: JsonObject = {
      ...before,
      revision_number: element.list.revision_number + 1,
      supersedes_revision_id: latest(element).revision_id,
      disposal: json({
        disposal_date: facts.disposal_date,
        reason: facts.reason,
        proceeds: facts.proceeds,
        transmission_costs: facts.transmission_costs,
        market_value: facts.market_value,
        prior_free_depreciation_regime: facts.prior_free_depreciation_regime,
        later_affectation_on: facts.later_affectation_on,
      }),
      out_of_service_date: new Date(
        Date.parse(facts.disposal_date) + 86_400_000,
      )
        .toISOString()
        .slice(0, 10),
    };
    element.revisions.push({
      revision: afterBaja,
      revision_id: hex64(`revision:${JSON.stringify(afterBaja)}`),
    });
    element.list.revision_number += 1;
    element.baja = facts;
    element.outOfService = new Date(
      Date.parse(facts.disposal_date) + 86_400_000,
    )
      .toISOString()
      .slice(0, 10);
    // The plan ends the year of the last day of service.
    element.rows = element.rows.filter(
      (row) => row.tax_year <= Number(facts.disposal_date.slice(0, 4)),
    );
    if (facts.disposal_date < TODAY) element.list.state = "out_of_service";
    recount(element);
    return json({ ...ok, history: history(element) });
  };

  /** The figures of a stated baja, or of the recorded one. The registry's own
   * calculation worked out the seeded figures for a sale with nothing stated;
   * what the person states moves only the transmission figures and the result. */
  const calculate: Handler = (request) => {
    exact(request, ["asset_id", "disposal"]);
    const id = required(request.asset_id);
    const element = find(id);
    const none = { asset_id: null, calculation: null };
    if (!element) return notFound(none);
    const facts =
      request.disposal === null ? element.baja : statedDisposal(request);
    if (facts === null)
      return refuse(VALIDATION, "disposal_not_recorded", {}, none);
    if (request.disposal !== null) judge(element, facts, none);
    const base = element.disposal;
    if (!base) return refuse(INCOMPLETE, "opening_history_missing", {}, none);
    const withdrawal = facts.reason === "withdrawal";
    const net = toCents(base.net_value.decimal);
    const stated = Math.max(
      toCents(facts.proceeds.decimal),
      toCents(decimalOf(facts.market_value) ?? "0"),
    );
    const costs = toCents(facts.transmission_costs.decimal);
    const result = stated - costs - net;
    const calculation: DisposalCalculation = {
      ...base,
      disposal_date: facts.disposal_date,
      reason: facts.reason,
      transmission_value: withdrawal ? null : dec(fromCents(stated)),
      transmission_costs: withdrawal ? null : dec(fromCents(costs)),
      result: withdrawal ? null : dec(fromCents(result)),
      route_changed_by_later_affectation: false,
      findings: [
        ...base.findings.map((finding) => ({
          ...finding,
          label_key: `${FINDING}${finding.kind}`,
        })),
        ...(!withdrawal && result > 0
          ? [
              {
                kind: "exemption_not_computed",
                label_key: `${FINDING}exemption_not_computed`,
                tax_year: null,
                effect_on_cost: null,
              },
            ]
          : []),
      ],
    };
    return json({ ...ok, asset_id: id, calculation });
  };

  const forecast: Handler = (request) => {
    exact(request, [
      "asset_id",
      "covered_from",
      "covered_until",
      "requested_free_amount",
      "supersedes_claim_id",
    ]);
    const id = required(request.asset_id);
    const element = find(id);
    if (!element) return notFound({ forecast: null });
    const from = required(request.covered_from);
    const until = required(request.covered_until);
    if (!DATE.test(from) || !DATE.test(until)) return invalid();
    if (until <= from)
      return refuse(
        VALIDATION,
        "covered_interval_empty",
        {},
        { forecast: null },
      );
    if (
      from.slice(0, 4) !==
      String(
        Number(until.slice(0, 4)) -
          (until.endsWith("-01-01") && until.slice(0, 4) !== from.slice(0, 4)
            ? 1
            : 0),
      )
    )
      return refuse(
        VALIDATION,
        "covered_interval_outside_tax_year",
        {},
        { forecast: null },
      );
    const year = Number(from.slice(0, 4));
    const row = element.rows.find((found) => found.tax_year === year);
    if (!row)
      return refuse(
        VALIDATION,
        "covered_interval_without_service_days",
        {},
        { forecast: null },
      );
    if (row.absence === "incomplete" || row.absence === "edition_unavailable")
      return row.absence === "incomplete"
        ? refuse(INCOMPLETE, "opening_history_missing", {}, { forecast: null })
        : refuse(
            VALIDATION,
            "tax_year_without_edition",
            { tax_year: String(year) },
            { forecast: null },
          );
    if (row.absence === "period_elapsed")
      return refuse(
        UNSUPPORTED,
        "amortization_period_elapsed",
        { ended_on: element.limits.maximum_period_ends_on ?? "" },
        { forecast: null },
      );
    if (
      row.absence === "basis_exhausted" ||
      row.absence === "covered_by_opening"
    )
      return refuse(
        VALIDATION,
        "claims_exceed_amortizable_basis",
        {},
        { forecast: null },
      );
    const { start, end } = serviceWindow(element, row);
    const spanStart = later(from, start);
    const spanEnd = earlier(until, end);
    if (spanEnd <= spanStart)
      return refuse(
        VALIDATION,
        "covered_interval_without_service_days",
        {},
        { forecast: null },
      );
    const supersedes = textOf(request.supersedes_claim_id);
    const overlapping = row.claims.filter(
      (claim) =>
        claim.effective &&
        claim.claim_id !== supersedes &&
        claim.covered_from < until &&
        from < claim.covered_until,
    );
    if (overlapping.length > 0)
      return refuse(CLAIM_CONFLICT, "claims_overlap", {}, { forecast: null });
    const target = row.claims.find((claim) => claim.claim_id === supersedes);
    if (supersedes !== null && (!target || !target.effective))
      return refuse(
        VALIDATION,
        "superseded_claim_not_effective",
        {},
        { forecast: null },
      );
    if (
      target &&
      (target.covered_from !== from || target.covered_until !== until)
    )
      return refuse(
        VALIDATION,
        "superseding_claim_changes_interval",
        {},
        { forecast: null },
      );
    let amount: string;
    if (row.absence === "free_election") {
      const asked = decimalOf(request.requested_free_amount);
      if (asked === null)
        return refuse(
          VALIDATION,
          "free_amount_required",
          {},
          { forecast: null },
        );
      if (toCents(asked) <= 0)
        return refuse(
          VALIDATION,
          "free_amount_not_positive_cents",
          {},
          { forecast: null },
        );
      const left =
        element.list.pending === null ? null : element.list.pending.decimal;
      if (
        left !== null &&
        toCents(asked) >
          toCents(left) + (target ? toCents(target.amount.decimal) : 0)
      )
        return refuse(
          VALIDATION,
          "free_amount_exceeds_remaining_basis",
          {},
          { forecast: null },
        );
      amount = asked;
    } else {
      const window = later(element.list.in_service_date, `${year}-01-01`);
      amount = chargeFor(element.annual, window, spanStart, spanEnd, year);
    }
    return json({
      ...ok,
      forecast: {
        asset_id: id,
        asset_revision_id: latest(element).revision_id,
        tax_year: year,
        covered_from: from,
        covered_until: until,
        service_days: daysBetween(spanStart, spanEnd),
        calendar_days: leap(year) ? 366 : 365,
        amount: dec(amount),
        schedule_fingerprint: hex64(
          `schedule:${id}:${from}:${until}:${amount}`,
        ),
        authority_generation: authority.logical_generation,
        source_reference: "ley-35-2006:art-28",
        method: row.method,
        annual_rate: row.coefficient,
      },
    });
  };

  const claim: Handler = (request) => {
    exact(request, ["forecast", "supersedes_claim_id"]);
    const given = request.forecast as unknown as {
      asset_id: string;
      tax_year: number;
      covered_from: string;
      covered_until: string;
      amount: { decimal: string };
    };
    if (typeof given !== "object" || given === null) return invalid();
    const element = find(given.asset_id);
    if (!element) return notFound({ claim_result: null, claim_id: null });
    const row = element.rows.find((found) => found.tax_year === given.tax_year);
    if (!row)
      return refuse(
        VALIDATION,
        "covered_interval_without_service_days",
        {},
        { claim_result: null, claim_id: null },
      );
    if (row.absence === "period_elapsed")
      return refuse(
        UNSUPPORTED,
        "amortization_period_elapsed",
        { ended_on: element.limits.maximum_period_ends_on ?? "" },
        { claim_result: null, claim_id: null },
      );
    const supersedes = textOf(request.supersedes_claim_id);
    const claimId = hex64(
      `claim:${given.asset_id}:${given.covered_from}:${given.covered_until}:${given.amount.decimal}:${supersedes ?? ""}`,
    );
    const again = row.claims.find((found) => found.claim_id === claimId);
    if (again && again.superseded_by !== null)
      return refuse(
        CLAIM_CONFLICT,
        "claim_superseded_replay",
        {},
        { claim_result: null, claim_id: null },
      );
    if (!again && given.tax_year > LAST_ADMITTED_YEAR)
      return refuse(
        UNSUPPORTED,
        "claim_year_beyond_registry",
        {
          tax_year: String(given.tax_year),
          last_admitted_year: String(LAST_ADMITTED_YEAR),
        },
        { claim_result: null, claim_id: null },
      );
    const reply = (reused: boolean) =>
      json({
        ...ok,
        claim_result: {
          history: history(element),
          reused_existing_claim: reused,
        },
        claim_id: claimId,
      });
    if (again) return reply(true);
    const overlapping = row.claims.filter(
      (found) =>
        found.effective &&
        found.claim_id !== supersedes &&
        found.covered_from < given.covered_until &&
        given.covered_from < found.covered_until,
    );
    if (overlapping.length > 0)
      return refuse(
        CLAIM_CONFLICT,
        "claims_overlap",
        {},
        { claim_result: null, claim_id: null },
      );
    const target = row.claims.find((found) => found.claim_id === supersedes);
    if (supersedes !== null && (!target || !target.effective))
      return refuse(
        VALIDATION,
        "superseded_claim_not_effective",
        {},
        { claim_result: null, claim_id: null },
      );
    const next: PlanClaim = {
      claim_id: claimId,
      amount: dec(given.amount.decimal),
      covered_from: given.covered_from,
      covered_until: given.covered_until,
      effective: true,
      superseded_by: null,
      revision_id: latest(element).revision_id,
    };
    if (target) {
      target.effective = false;
      target.superseded_by = claimId;
    }
    row.claims.push(next);
    const delta =
      toCents(next.amount.decimal) -
      (target ? toCents(target.amount.decimal) : 0);
    const { accumulated, pending } = element.list;
    if (accumulated !== null)
      element.list.accumulated = dec(
        fromCents(toCents(accumulated.decimal) + delta),
      );
    if (pending !== null)
      element.list.pending = dec(
        fromCents(Math.max(toCents(pending.decimal) - delta, 0)),
      );
    record(
      element,
      "claim",
      "ledger.actividad-asset.claim",
      next.covered_from,
      [
        {
          field: "amount",
          before: target?.amount.decimal ?? null,
          after: next.amount.decimal,
        },
      ],
      {
        record_id: claimId,
        claim: {
          used_by: [],
          matches_current_schedule: true,
          stale_reason: null,
        },
      },
    );
    restate(element, row);
    if (
      element.list.pending !== null &&
      toCents(element.list.pending.decimal) <= 0
    )
      element.list.state = "fully_amortized";
    recount(element);
    return reply(false);
  };

  return {
    reads: {
      ...reads,
      "ledger.actividad-asset.forecast": forecast,
      "ledger.actividad-asset.inspect": inspect,
      "ledger.actividad-asset.filing-handoff": filingHandoff,
      "ledger.actividad-asset.disposal-calculate": calculate,
    } as Record<string, Handler>,
    writes: {
      "ledger.actividad-asset.describe": describe,
      "ledger.actividad-asset.dispose": dispose,
      "ledger.actividad-asset.create": create,
      "ledger.actividad-asset.correct": correct,
      "ledger.actividad-asset.claim": claim,
    } as Record<string, Handler>,
  };
}

/** The tax years the seeded register offers: from the oldest element's first
 * year to the year after the scenario's date, for stories that show the
 * stepper on a register that spans decades. */
export function assetFixtureYears(): number[] {
  return [...new Set(SEED_ELEMENTS.flatMap((seed) => seed.list.years))].sort(
    (a, b) => a - b,
  );
}

export type { JsonValue };
