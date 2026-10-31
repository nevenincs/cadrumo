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
  ReasonFactKind,
  TimelineClaimUse,
  TimelineEvent,
} from "@/shell/ledgerSetup";
import type {
  JsonObject,
  JsonValue,
  LedgerDefinitionId,
} from "../shell/ledger";
import {
  ACQUIRED_CONDITIONS,
  ADMITTED_METHODS,
  BASIS_STAGES,
  BOX_NAMES,
  DISPOSAL_REASONS,
  FURTHER_ACQUISITION_SHAPES,
  M130_PERIODS,
  NO_TABLE_MINIMUM_KEY,
  NOT_APPLICABLE_ABSENCES,
  OPENING_STATUSES,
  REMEDY_FIELD_KEYS,
  SEED_ELEMENTS,
  TABLE_GROUPS,
  TIMELINE_FACT_PATHS,
  type SeedElement,
} from "./assetsSeed";

type Handler = (request: JsonObject) => JsonObject;

/** One fact an election of a method states, as the options serve it. */
type ServedFact = {
  path: string[];
  kind: string;
  required: boolean;
  required_with_group: boolean;
  token_family: string | null;
  tokens: string[];
};

/** The facts the options serve for each method, as the election model types
 * them. */
export const SERVED_METHOD_FACTS: { method: string; facts: ServedFact[] }[] = [
  {
    method: "linear",
    facts: [
      {
        path: ["authority_class_key"],
        kind: "class",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["linear_coefficient"],
        kind: "share",
        required: false,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["shift_hours_per_day"],
        kind: "decimal",
        required: false,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "evidence_reference"],
        kind: "text",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "made_available_on"],
        kind: "date",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "prior_period_net_turnover"],
        kind: "amount",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
      {
        path: ["used_original_price", "determination"],
        kind: "choice",
        required: false,
        required_with_group: true,
        token_family: "original_price_determination",
        tokens: ["known", "expert_valuation"],
      },
      {
        path: ["used_original_price", "original_price"],
        kind: "amount",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
      {
        path: ["used_original_price", "evidence_reference"],
        kind: "text",
        required: false,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "constant_percentage",
    facts: [
      {
        path: ["authority_class_key"],
        kind: "class",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["linear_coefficient"],
        kind: "share",
        required: false,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "sum_of_digits",
    facts: [
      {
        path: ["authority_class_key"],
        kind: "class",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["sum_of_digits_period_years"],
        kind: "whole",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["digit_order"],
        kind: "choice",
        required: true,
        required_with_group: false,
        token_family: "digit_order",
        tokens: ["descending", "ascending"],
      },
    ],
  },
  {
    method: "approved_plan",
    facts: [
      {
        path: ["approved_plan", "approval_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["approved_plan", "approval_kind"],
        kind: "choice",
        required: true,
        required_with_group: false,
        token_family: "plan_approval_kind",
        tokens: ["express", "amended_with_consent", "silence"],
      },
      {
        path: ["approved_plan", "submitted_on"],
        kind: "date",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["approved_plan", "resolved_on"],
        kind: "date",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["approved_plan", "annual_amounts"],
        kind: "rows",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "intangible_useful_life",
    facts: [
      {
        path: ["useful_life", "ends_on"],
        kind: "date",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["useful_life", "evidence_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "intangible_indefinite_life",
    facts: [
      {
        path: ["small_enterprise", "evidence_reference"],
        kind: "text",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "made_available_on"],
        kind: "date",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "prior_period_net_turnover"],
        kind: "amount",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "goodwill",
    facts: [
      {
        path: ["small_enterprise", "evidence_reference"],
        kind: "text",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "made_available_on"],
        kind: "date",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "prior_period_net_turnover"],
        kind: "amount",
        required: false,
        required_with_group: true,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "low_value_free",
    facts: [
      {
        path: ["low_value", "election_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["low_value", "new_material_evidence_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "research_development_free",
    facts: [
      {
        path: ["research_development_evidence_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "research_development_building",
    facts: [
      {
        path: ["authority_class_key"],
        kind: "class",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["research_development_evidence_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "charging_infrastructure_free",
    facts: [
      {
        path: ["charging_infrastructure", "technical_documentation_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["charging_infrastructure", "installation_certificate_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "electric_vehicle_free",
    facts: [
      {
        path: ["authority_class_key"],
        kind: "class",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "justified_amount",
    facts: [],
  },
  {
    method: "small_enterprise_employment_free",
    facts: [
      {
        path: ["authority_class_key"],
        kind: "class",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "evidence_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "made_available_on"],
        kind: "date",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["small_enterprise", "prior_period_net_turnover"],
        kind: "amount",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "renewable_self_consumption_free",
    facts: [
      {
        path: ["authority_class_key"],
        kind: "class",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["renewable_self_consumption", "purpose"],
        kind: "choice",
        required: true,
        required_with_group: false,
        token_family: "renewable_installation_purpose",
        tokens: ["electricity_self_consumption", "thermal_own_use"],
      },
      {
        path: ["renewable_self_consumption", "documentation_kind"],
        kind: "choice",
        required: true,
        required_with_group: false,
        token_family: "renewable_documentation_kind",
        tokens: [
          "operating_authorisation",
          "surplus_registration",
          "low_voltage_certificate",
          "renewable_gas_registration",
          "thermal_process_registration",
          "energy_efficiency_certificate",
        ],
      },
      {
        path: ["renewable_self_consumption", "documentation_reference"],
        kind: "text",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["renewable_self_consumption", "made_available_on"],
        kind: "date",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["renewable_self_consumption", "replaces_fossil_installation"],
        kind: "flag",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
      {
        path: ["renewable_self_consumption", "required_by_building_code"],
        kind: "flag",
        required: true,
        required_with_group: false,
        token_family: null,
        tokens: [],
      },
    ],
  },
  {
    method: "entity_regime_free",
    facts: [],
  },
];

/** The shapes an element can be registered under, and the activities an
 * element bought outside the ledger can belong to. */
export const SERVED_SHAPES = ["primary_purchase", "acquired_outside_ledger"];
export const SERVED_ACTIVITIES = [
  "A01",
  "A02",
  "A03",
  "A04",
  "A05",
  "B01",
  "B02",
  "B03",
  "B04",
  "B05",
];

/** Whether a form can state every fact the method requires as a single value. */
const statable = (method: string) =>
  (SERVED_METHOD_FACTS.find((found) => found.method === method)?.facts ?? [])
    .filter((fact) => fact.required)
    .every((fact) => fact.kind !== "rows");

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

/** A reason fact stated with the kind of the value it was raised with, as the
 * backend serves it; a bare string is a text. */
type Fact = string | { value: string; kind: ReasonFactKind };
const typed =
  (kind: ReasonFactKind) =>
  (value: string | number): Fact => ({ value: String(value), kind });
const asDate = typed("date");
const asCount = typed("count");
const asAmount = typed("amount");
const asPercent = typed("percent");

// ---- Amounts, in whole cents --------------------------------------------------

const toCents = (text: string): number => Math.round(Number(text) * 100);
const fromCents = (cents: number): string => (cents / 100).toFixed(2);

const leap = (year: number) =>
  (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
const daysBetween = (from: string, until: string) =>
  Math.round((Date.parse(until) - Date.parse(from)) / 86_400_000);
const later = (a: string, b: string) => (a > b ? a : b);
const dayBefore = (iso: string) =>
  new Date(Date.parse(iso) - 86_400_000).toISOString().slice(0, 10);
const dayAfter = (iso: string) =>
  new Date(Date.parse(iso) + 86_400_000).toISOString().slice(0, 10);
/** A span with the last day it covers beside its exclusive boundary. */
const withThrough = <T extends { covered_until: string }>(span: T) => ({
  ...span,
  covered_through: dayBefore(span.covered_until),
});
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
      for (const row of copy.rows) {
        row.claims = row.claims.map(withThrough);
        row.claimable_intervals = row.claimable_intervals.map(withThrough);
      }
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
    facts: Record<string, Fact> = {},
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
            .map(([name, fact]): ReasonFact =>
              typeof fact === "string"
                ? { key: name, value: fact, kind: "text" }
                : { key: name, ...fact },
            ),
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

  const SHARE_FIELDS = [
    "basis.business_use_share",
    "basis.ownership_share",
    "amortization.linear_coefficient",
  ];

  const history = (element: Element): JsonObject =>
    json({
      revisions: element.revisions.map((found) => found.revision),
      claims: element.rows.flatMap((row) => row.claims),
      descriptors: [],
      events: element.events,
    });

  /** The catalogue key of a fact the timeline words, as the backend names it:
   * null for a path no fact of the timeline has. */
  const fieldKeyOf = (field: string): string | null =>
    TIMELINE_FACT_PATHS.includes(field.replace(/\[\d+\]/g, "[]"))
      ? `${FAMILY}field.${field.replace(/\[\d*\]/g, "")}`
      : null;
  /** What the timeline says of a dotación: its year and last day, and that it
   * is in effect; a replaced one is judged against nothing. */
  const claimUse = (
    claim: PlanClaim,
    year: number,
    verdict: Pick<
      TimelineClaimUse,
      "matches_current_schedule" | "stale_reason"
    >,
  ): TimelineClaimUse => ({
    used_by: [],
    ...verdict,
    in_effect: claim.effective,
    tax_year: year,
    covered_from: claim.covered_from,
    covered_through: claim.covered_through,
  });
  /** A dotación a later one replaced stops being in effect, and no longer
   * disagrees with the schedule. */
  const retire = (element: Element, claimId: string) => {
    for (const event of element.events)
      if (event.kind === "claim" && event.record_id === claimId)
        event.claim =
          event.claim === null
            ? null
            : {
                ...event.claim,
                in_effect: false,
                matches_current_schedule: true,
                stale_reason: null,
              };
  };
  const record = (
    element: Element,
    kind: string,
    eventKind: string,
    origin: string,
    effect: string | null,
    changes: { field: string; before: string | null; after: string | null }[],
    extra: Partial<TimelineEvent> = {},
  ) => {
    const labelOf = (field: string, value: string | null): string | null => {
      if (value === null) return null;
      if (SHARE_FIELDS.includes(field))
        return `${Number((Number(value) * 100).toFixed(6))}%`;
      if (field === "amortization.authority_class_key")
        return (
          Object.values(TABLE_GROUPS)
            .flat()
            .find((group) => group.class_key === value)?.class_label ?? null
        );
      return null;
    };
    const keyOf = (field: string, value: string | null) =>
      value !== null && Object.hasOwn(TOKEN_FIELDS, field)
        ? `${FAMILY}${TOKEN_FIELDS[field]}.${value}`
        : null;
    element.events.push({
      sequence: element.events.length + 1,
      recorded_at: now(),
      kind,
      event_kind: eventKind,
      asset_id: element.id,
      record_id: hex64(`${kind}:${element.id}:${element.events.length + 1}`),
      effect_date: effect,
      origin,
      changes: changes.map((change) => ({
        ...change,
        kind:
          change.before === null
            ? ("added" as const)
            : change.after === null
              ? ("removed" as const)
              : ("changed" as const),
        field_key: fieldKeyOf(change.field),
        before_key: keyOf(change.field, change.before),
        after_key: keyOf(change.field, change.after),
        before_label: labelOf(change.field, change.before),
        after_label: labelOf(change.field, change.after),
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
    return gaps
      .filter((gap) => gap.covered_from < gap.covered_until)
      .map(withThrough);
  };

  const serviceWindow = (element: Element, row: PlanRow) => {
    const start = later(element.list.in_service_date, `${row.tax_year}-01-01`);
    const end =
      element.outOfService === null
        ? `${row.tax_year + 1}-01-01`
        : earlier(element.outOfService, `${row.tax_year + 1}-01-01`);
    return { start, end };
  };

  /** What the backend derives of a row once its absence, reasons and open
   * spans are settled: whether the year applies, and the entry to fill in
   * where that is the remedy. */
  const settle = (row: PlanRow) => {
    row.applies =
      row.absence === null ||
      !NOT_APPLICABLE_ABSENCES.includes(row.absence) ||
      row.claimable_intervals.length > 0;
    const remedy = (key: string | null) =>
      key !== null && Object.hasOwn(REMEDY_FIELD_KEYS, key)
        ? REMEDY_FIELD_KEYS[key]!
        : null;
    row.absence_remedy_field_key = remedy(row.absence_reason_key);
    row.claimable_refusal_remedy_field_key = remedy(row.claimable_refusal_key);
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
    settle(row);
  };

  /** The year a dotación form opens on: the latest year up to the scenario's
   * with something left to claim, else the earliest later one. */
  const claimYearOf = (rows: readonly PlanRow[]): number | null => {
    const open = rows
      .filter((row) => row.claimable_intervals.length > 0)
      .map((row) => row.tax_year);
    const elapsed = open.filter((year) => year <= Number(TODAY.slice(0, 4)));
    if (elapsed.length > 0) return Math.max(...elapsed);
    return open.length > 0 ? Math.min(...open) : null;
  };

  const recount = (element: Element) => {
    const stale = element.events.filter(
      (event) =>
        event.claim !== null &&
        event.claim.in_effect &&
        !event.claim.matches_current_schedule &&
        element.rows.some((row) =>
          row.claims.some(
            (claim) => claim.effective && claim.claim_id === event.record_id,
          ),
        ),
    ).length;
    // Each year is counted once, under the first thing that stops it: a year
    // whose figure cannot be worked out is never also counted as not claimed.
    const absent = (name: string) =>
      element.rows.filter((row) => row.absence === name).length;
    element.list.findings = {
      missing: element.rows.filter(
        (row) =>
          (row.absence === null || row.absence === "free_election") &&
          (row.claim_state === "missing" || row.claim_state === "partial"),
      ).length,
      incomplete: absent("incomplete"),
      conflict: absent("conflict"),
      unsupported: absent("unsupported"),
      without_tables: absent("edition_unavailable"),
      stale,
    };
    element.list.default_claim_year = claimYearOf(element.rows);
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
      const elapsed = years.filter((year) => year <= Number(TODAY.slice(0, 4)));
      return json({
        ...ok,
        rows,
        years,
        default_year:
          elapsed.length > 0 ? Math.max(...elapsed) : (years[0] ?? null),
      });
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
      // A claim states the verdict the timeline states of it: one judgement.
      const verdicts = new Map(
        element.events.flatMap((event) =>
          event.claim === null ? [] : [[event.record_id, event.claim] as const],
        ),
      );
      const rows = element.rows.map((row) => ({
        ...row,
        claims: row.claims.map((claim) => {
          const found = verdicts.get(claim.claim_id);
          return found === undefined
            ? claim
            : {
                ...claim,
                matches_current_schedule: found.matches_current_schedule,
                stale_reason: found.stale_reason as PlanClaim["stale_reason"],
              };
        }),
      }));
      return json({
        ...ok,
        asset_id: id,
        rows,
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
          { tax_year: asCount(year) },
          { options: null },
        );
      return json({
        ...ok,
        options: {
          tax_year: year,
          asset_kind: kind,
          regime: REGIME,
          edition,
          acquisition_shapes: SERVED_SHAPES,
          declared_activities: SERVED_ACTIVITIES,
          methods: ADMITTED_METHODS[kind]!.filter(statable),
          method_facts: ADMITTED_METHODS[kind]!.filter(statable).map((method) =>
            SERVED_METHOD_FACTS.find((found) => found.method === method)!,
          ),
          table_groups: TABLE_GROUPS[kind],
          disposal_reasons: DISPOSAL_REASONS,
          basis_stages: BASIS_STAGES,
          opening_statuses: OPENING_STATUSES,
          acquired_conditions: ACQUIRED_CONDITIONS,
          further_acquisition_shapes: FURTHER_ACQUISITION_SHAPES,
          m130_periods: M130_PERIODS[year] ?? [],
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
    if (Array.isArray(value))
      return value.length === 0
        ? { [prefix]: null }
        : Object.assign(
            {},
            ...value.map((item, position) =>
              flatten(item, `${prefix}[${position}]`),
            ),
          );
    if (typeof value !== "object") return { [prefix]: String(value) };
    return Object.assign(
      {},
      ...Object.entries(value).map(([name, item]) =>
        flatten(item, prefix === "" ? name : `${prefix}.${name}`),
      ),
    );
  };
  const changesBetween = (before: JsonObject | null, after: JsonObject) => {
    const old = before === null ? {} : flatten(before);
    const next = flatten(after);
    return Object.keys({ ...old, ...next })
      .filter(
        (path) =>
          fieldKeyOf(path) !== null &&
          (old[path] ?? null) !== (next[path] ?? null),
      )
      .map((path) => ({
        field: path,
        before: old[path] ?? null,
        after: next[path] ?? null,
      }));
  };

  /** The facts of a revision that no charge rests on: the register reads a
   * claim as matching the current revision whatever they say, so a baja, or
   * how the element was acquired, never marks a dotación stale. */
  const FIGURE_NEUTRAL = new Set([
    "revision_number",
    "supersedes_revision_id",
    "out_of_service_date",
    "disposal",
    "acquisition",
    "acquisition_shape",
    "further_acquisitions",
    "declared_acquisition_date",
    "declared_activity",
  ]);
  /** Whether a revision states a fact its predecessor's charges rest on
   * differently. */
  const movesCharge = (before: JsonObject, after: JsonObject) => {
    const old = flatten(before);
    const next = flatten(after);
    return Object.keys({ ...old, ...next }).some(
      (path) =>
        !FIGURE_NEUTRAL.has(path.split(".")[0]!) &&
        (old[path] ?? null) !== (next[path] ?? null),
    );
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
    const kind = textOf(revision.asset_kind);
    if (kind === null || !Object.hasOwn(TABLE_GROUPS, kind)) return invalid();
    const acquiredAs = textOf(revision.acquisition_shape);
    if (acquiredAs === null || !SERVED_SHAPES.includes(acquiredAs))
      return invalid();
    const inService = textOf(revision.in_service_date);
    if (inService === null || !DATE.test(inService)) return invalid();
    if (typeof acquisition.invoice_evidence_id !== "string") return invalid();
    if (acquiredAs === "acquired_outside_ledger") {
      if (
        acquisition.observed_transaction_id !== null ||
        acquisition.evidence_fingerprint !== null
      )
        return invalid();
      if (acquisition.invoice_evidence_id.trim() === "")
        return refuse(
          VALIDATION,
          "acquisition_evidence_reference_required",
          {},
          shape,
        );
      const bought = textOf(revision.declared_acquisition_date);
      if (bought === null)
        return refuse(
          VALIDATION,
          "declared_acquisition_date_required",
          {},
          shape,
        );
      if (bought > inService)
        return refuse(
          VALIDATION,
          "declared_acquisition_after_service",
          {
            declared_acquisition_date: asDate(bought),
            in_service_date: asDate(inService),
          },
          shape,
        );
      const activity = textOf(revision.declared_activity);
      if (activity === null || !SERVED_ACTIVITIES.includes(activity))
        return refuse(VALIDATION, "declared_activity_required", {}, shape);
      // Later ledger payments the element owns: each is a payment that
      // exists, named once.
      const further = revision.further_acquisitions;
      if (!Array.isArray(further)) return invalid();
      const named = new Set<string>();
      for (const row of further) {
        const given = obj(row);
        const lineage = obj(given?.lineage);
        if (
          !given ||
          !lineage ||
          !FURTHER_ACQUISITION_SHAPES.includes(String(given.shape)) ||
          typeof lineage.observed_transaction_id !== "string"
        )
          return invalid();
        const id = lineage.observed_transaction_id;
        if (!PURCHASES.some((found) => found.transaction_id === id))
          return refuse(
            VALIDATION,
            "acquisition_transaction_missing",
            { transaction_id: id },
            shape,
          );
        if (named.has(id))
          return refuse(VALIDATION, "acquisition_row_named_twice", {}, shape);
        named.add(id);
      }
    } else {
      for (const name of ["observed_transaction_id", "evidence_fingerprint"])
        if (typeof acquisition[name] !== "string") return invalid();
      if (
        revision.declared_acquisition_date != null ||
        revision.declared_activity != null
      )
        return invalid();
    }
    if (
      !ACQUIRED_CONDITIONS.some(
        (found) => found.condition === revision.acquired_condition,
      )
    )
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
    if (basis.stage === "whole_property") {
      if (basis.is_property !== true) return invalid();
      const parts = [
        "construction_cost",
        "land_cost",
        "office_area",
        "total_area",
        "ownership_share",
      ].filter((name) => decimalOf(basis[name]) === null);
      if (parts.length > 0 || textOf(basis.ownership_mode) === null)
        return refuse(INCOMPLETE, "allocation_components_missing", {}, shape, [
          ...parts.map((name) => `basis.${name}`),
          ...(textOf(basis.ownership_mode) === null
            ? ["basis.ownership_mode"]
            : []),
        ]);
      if (
        toCents(decimalOf(basis.construction_cost)!) +
          toCents(decimalOf(basis.land_cost)!) !==
          toCents(decimalOf(basis.basis_amount)!) ||
        Number(decimalOf(basis.office_area)) >
          Number(decimalOf(basis.total_area))
      )
        return invalid();
      if (basis.ownership_mode === "spousal_community")
        return refuse(
          UNSUPPORTED,
          "spousal_community_ownership_unsupported",
          {},
          shape,
        );
    } else if (basis.is_property === true) return invalid();
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
            {
              opening_tax_year: asCount(through),
              in_service_tax_year: asCount(inService.slice(0, 4)),
            },
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
            elected: asPercent(coefficient),
            minimum: asPercent(group.minimum_coefficient.decimal),
            maximum: asPercent(group.maximum_coefficient.decimal),
          },
          shape,
        );
    }
    const used = obj(election.used_original_price);
    if (used !== null) {
      const condition = ACQUIRED_CONDITIONS.find(
        (found) => found.condition === revision.acquired_condition,
      );
      if (
        method !== "linear" ||
        !condition?.facts.includes("used_original_price")
      )
        return refuse(
          VALIDATION,
          "used_original_price_requires_used_asset",
          {},
          shape,
        );
      if (
        !["known", "expert_valuation"].includes(String(used.determination)) ||
        decimalOf(used.original_price) === null
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
    // Every fact the method requires, and a group stated whole.
    const served = SERVED_METHOD_FACTS.find((found) => found.method === method);
    const stated = (path: string[]) =>
      path.reduce<unknown>((at, step) => obj(at)?.[step] ?? null, election) !==
      null;
    const absent = (served?.facts ?? [])
      .filter((fact) => fact.kind !== "rows")
      .filter((fact) => {
        if (stated(fact.path)) return false;
        if (fact.required) return true;
        return (
          fact.required_with_group &&
          (served?.facts ?? []).some(
            (other) => other.path[0] === fact.path[0] && stated(other.path),
          )
        );
      });
    if (absent.length > 0)
      return refuse(
        INCOMPLETE,
        null,
        {},
        shape,
        absent.map((fact) => `amortization.${fact.path.join(".")}`),
      );
    const hours = decimalOf(election.shift_hours_per_day);
    if (
      hours !== null &&
      (method !== "linear" || Number(hours) <= 0 || Number(hours) > 24)
    )
      return invalid();
    // A class the table charges only on a vehicle declaration needs one.
    const restricted = TABLE_GROUPS[kind]?.find(
      (found) => found.class_key === textOf(election.authority_class_key),
    )?.requires_vehicle_declaration;
    if (restricted === true && revision.vehicle_affectation == null)
      return refuse(
        INCOMPLETE,
        "vehicle_affectation_required_for_class",
        {},
        shape,
      );
    // A vehicle is an element of a material kind whose declaration admits it.
    const vehicle = obj(revision.vehicle_affectation);
    if (vehicle !== null) {
      if (kind !== "material") return invalid();
      for (const name of ["category", "private_use", "evidence_reference"])
        if (textOf(vehicle[name]) === null) return invalid();
      if (typeof vehicle.recorded_in_activity_books !== "boolean")
        return invalid();
      if (vehicle.recorded_in_activity_books === false)
        return refuse(UNSUPPORTED, "vehicle_missing_from_books", {}, shape);
      if (vehicle.private_use === "shared")
        return refuse(UNSUPPORTED, "vehicle_shared_use", {}, shape);
    }
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
        "described",
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
    // The reason the first year without a minimum has none, kept for every
    // year after it.
    let minimumReason: string | null = null;
    const rows: PlanRow[] = [];
    const base = (year: number, days: number | null): PlanRow => {
      const calendar = leap(year) ? 366 : 365;
      const edition = editionOf(year);
      const start = later(inService, `${year}-01-01`);
      const end = `${year + 1}-01-01`;
      const span = daysBetween(start, end);
      if (edition === null || !group) {
        minimumReason ??=
          edition === null
            ? `${FINDING}minimum_unresolved`
            : NO_TABLE_MINIMUM_KEY;
      } else if (minimumReason === null)
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
        absence_remedy_field_key: null,
        applies: true,
        claimed: dec("0.00"),
        claim_state: year > Number(TODAY.slice(0, 4)) ? "not_due" : "missing",
        claimable_intervals: [],
        claimable_refusal_key: null,
        claimable_refusal_facts: [],
        claimable_refusal_remedy_field_key: null,
        edition,
        service_days: days,
        calendar_days: days === null ? null : calendar,
        claims: [],
        // A minimum with an earlier year unresolved is unknown, with the
        // reason, and never a partial sum.
        minimum_through:
          minimumReason === null
            ? dec(fromCents(Math.min(toCents(basis), minimum)))
            : null,
        minimum_reason_key: minimumReason,
        minimum_complete: minimumReason === null,
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
      row.claimable_intervals = [
        withThrough({ covered_from: start, covered_until: end }),
      ];
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
    if (acquisition.observed_transaction_id !== null) {
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
    }
    for (const row of (revision.further_acquisitions as JsonObject[]) ?? []) {
      const id = obj(row.lineage)?.observed_transaction_id;
      if (typeof id === "string") taken.add(id);
    }

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
    rows.forEach(settle);
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
      pending_applies: true,
      opening_remedy_field_key:
        accumulated === null
          ? "ledger.actividad_asset.field.opening_history.accumulated_amount"
          : null,
      findings: {
        missing: 0,
        incomplete: 0,
        conflict: 0,
        unsupported: 0,
        without_tables: 0,
        stale: 0,
      },
      default_claim_year: null,
      disposal: null,
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
        maximum_period_last_day:
          group === undefined
            ? null
            : dayBefore(
                `${Number(inService.slice(0, 4)) + Number(group.maximum_period_years.decimal)}${inService.slice(4)}`,
              ),
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
        unavailable_reason_facts: [],
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
      "created",
      "ledger.actividad-asset.create",
      inService,
      changesBetween(null, revision),
    );
    record(
      element,
      "descriptor",
      "described",
      "ledger.actividad-asset.describe",
      null,
      [
        { field: "name", before: null, after: name },
        ...(list.serial_number
          ? [
              {
                field: "serial_number",
                before: null,
                after: list.serial_number,
              },
            ]
          : []),
      ],
    );
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
    // A correction states its baja, another one or null to remove it, and
    // leaves its number to the register: a number stated is checked and
    // refused only when it disagrees.
    if (!Object.hasOwn(revision, "disposal")) return invalid();
    if (
      (revision.revision_number !== undefined &&
        revision.revision_number !== element.list.revision_number + 1) ||
      revision.supersedes_revision_id !== current.revision_id
    )
      return refuse(VALIDATION, "correction_must_supersede_current", {}, shape);
    judgeRevision(revision, shape);
    // The baja a correction states replaces the one recorded, or removes it.
    const stated = obj(revision.disposal);
    const recorded = obj(current.revision.disposal);
    const bajaMoves = JSON.stringify(stated) !== JSON.stringify(recorded);
    const bajaFacts =
      stated !== null && bajaMoves
        ? statedDisposal({ disposal: stated })
        : null;
    if (bajaFacts !== null) judge(element, bajaFacts, shape);
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
    // Every effective claim not recorded again under this revision no longer
    // matches, when the revision states a fact a charge rests on differently.
    const chargeMoved = movesCharge(current.revision, revision);
    for (const event of element.events)
      if (
        chargeMoved &&
        event.claim !== null &&
        !replaced.includes(event.record_id)
      )
        event.claim = {
          ...event.claim,
          matches_current_schedule: false,
          stale_reason: event.claim.stale_reason ?? "revision_changed",
        };
    const number = element.list.revision_number + 1;
    const numbered: JsonObject = {
      ...structuredClone(revision),
      revision_number: number,
    };
    const revisionId = hex64(`revision:${JSON.stringify(numbered)}`);
    element.revisions.push({ revision: numbered, revision_id: revisionId });
    // What the record did: a baja recorded, changed or removed, which takes
    // effect on its own day, or else a correction from the day of service.
    const bajaKind =
      stated !== null && bajaMoves
        ? recorded === null
          ? "baja_recorded"
          : "baja_changed"
        : stated === null && recorded !== null
          ? "baja_removed"
          : null;
    record(
      element,
      "revision",
      bajaKind ?? "corrected",
      "ledger.actividad-asset.correct",
      bajaKind === null
        ? textOf(revision.in_service_date)
        : bajaKind === "baja_removed"
          ? textOf(recorded?.disposal_date)
          : textOf(stated?.disposal_date),
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
          matches_current_schedule: true,
          stale_reason: null,
        };
        old.effective = false;
        old.superseded_by = next.claim_id;
        row.claims.push(next);
        retire(element, old.claim_id);
        record(
          element,
          "claim",
          "claim_replaced",
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
            claim: claimUse(next, row.tax_year, {
              matches_current_schedule: true,
              stale_reason: null,
            }),
          },
        );
        restate(element, row);
      }
    if (bajaFacts !== null) putOutOfService(element, bajaFacts);
    else if (bajaMoves && stated === null) {
      element.baja = null;
      element.outOfService = null;
      element.list.disposal = null;
      element.list.pending_applies = true;
      element.list.state = "in_service";
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
    exact(request, ["tax_year", "m130_period", "output_language"]);
    const year = request.tax_year;
    // Without a quarter the Modelo 100 boxes alone are stated.
    const period =
      request.m130_period === undefined || request.m130_period === null
        ? null
        : required(request.m130_period);
    if (
      typeof year !== "number" ||
      (period !== null && !Object.hasOwn(PERIOD_END, period))
    )
      return invalid();
    const through = `${year}-${PERIOD_END[period ?? "4T"]}`;
    const until = dayAfter(through);
    const language = request.output_language;
    const names =
      BOX_NAMES[
        String(
          Math.max(FIRST_SUPPORTED_YEAR, Math.min(year, LAST_ADMITTED_YEAR)),
        )
      ]?.[String(language)];
    if (names === undefined) return invalid();
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
        box_name: names[`${kind}_m100`]!,
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
    /** The intervals of the year no effective claim covers, said by what can
     * be said of each: its accrual, that the method leaves it to the person,
     * or that the schedule cannot be worked out for it. */
    const m100Gaps = () =>
      sorted.flatMap((element) => {
        const row = element.rows.find((found) => found.tax_year === year);
        if (!row) return [];
        const free = row.absence === "free_election";
        const unworkable = [
          "incomplete",
          "edition_unavailable",
          "unsupported",
          "conflict",
        ].includes(row.absence ?? "");
        if (row.planned === null && !free && !unworkable) return [];
        const { start, end } = serviceWindow(element, row);
        if (end <= start) return [];
        return uncovered(row, start, end).map((gap) => {
          const kind = free
            ? "free_method"
            : unworkable
              ? "unavailable"
              : "accrued";
          return {
            asset_id: element.id,
            kind,
            ...withThrough({
              covered_from: gap.covered_from,
              covered_until: gap.covered_until,
            }),
            accrued:
              kind === "accrued"
                ? dec(
                    chargeFor(
                      element.annual,
                      later(element.list.in_service_date, `${year}-01-01`),
                      gap.covered_from,
                      gap.covered_until,
                      year,
                    ),
                  )
                : null,
          };
        });
      });
    const m130 = (kind: string) => {
      const contributions: {
        asset_id: string;
        amount: { decimal: string };
        claim_id: string | null;
        schedule_fingerprint: string | null;
      }[] = [];
      const unavailable: string[] = [];
      const freeGap: string[] = [];
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
          if (row.absence === "free_election") {
            if (!freeGap.includes(element.id)) freeGap.push(element.id);
            continue;
          }
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
        asset_kind: kind,
        target_casilla_id: "02",
        box_name: names[`${kind}_m130`]!,
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
        free_gap_asset_ids: freeGap,
        // No seeded element belongs to an agricultural activity.
        agrarian_excluded_asset_ids: [] as string[],
      };
    };
    return json({
      ...ok,
      tax_year: year,
      m130_period: period,
      filing_handoff: {
        material_m100: m100("material"),
        intangible_m100: m100("intangible"),
        m100_gaps: m100Gaps(),
        material_m130: period === null ? null : m130("material"),
        intangible_m130: period === null ? null : m130("intangible"),
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
          later_affectation_on: asDate(facts.later_affectation_on),
          in_service_date: asDate(element.list.in_service_date),
        },
        shape,
      );
    if (reason === "donation")
      refuse(UNSUPPORTED, "disposal_donation_refused", { reason }, shape);
    if (reason === "scrapping" && toCents(proceeds) !== 0)
      refuse(
        VALIDATION,
        "disposal_scrapping_with_proceeds",
        { proceeds: asAmount(proceeds) },
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

  /** The claims an overlap meets, comma-joined in history order. */
  const ids = (claims: readonly PlanClaim[]) =>
    claims.map((claim) => claim.claim_id).join(",");

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

  /** The element stands out of service after the baja's last day. The plan
   * ends the year of that day; the fixture does not work the figures of the
   * years it drops out again if the baja later moves back. */
  const putOutOfService = (element: Element, facts: DisposalFacts) => {
    element.baja = facts;
    element.outOfService = dayAfter(facts.disposal_date);
    element.list.disposal = {
      disposal_date: facts.disposal_date,
      reason: facts.reason,
      reason_key: `${FAMILY}disposal_reason.${facts.reason}`,
    };
    // Nothing is left to amortize once the element has left service: the
    // day after the baja's last day has come.
    element.list.pending_applies = dayAfter(facts.disposal_date) > TODAY;
    element.rows = element.rows.filter(
      (row) => row.tax_year <= Number(facts.disposal_date.slice(0, 4)),
    );
    if (facts.disposal_date < TODAY) element.list.state = "out_of_service";
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
        { disposal_date: asDate(element.baja.disposal_date) },
        { history: null },
      );
    judge(element, facts, { history: null });
    // A baja is neutral to every charge: the claims keep matching.
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
      "baja_recorded",
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
      out_of_service_date: dayAfter(facts.disposal_date),
    };
    element.revisions.push({
      revision: afterBaja,
      revision_id: hex64(`revision:${JSON.stringify(afterBaja)}`),
    });
    element.list.revision_number += 1;
    putOutOfService(element, facts);
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
      "covered_through",
      "requested_free_amount",
      "supersedes_claim_id",
    ]);
    const id = required(request.asset_id);
    const element = find(id);
    if (!element) return notFound({ forecast: null });
    const from = required(request.covered_from);
    // The end is stated as the exclusive boundary or as the last day covered;
    // stating both is accepted only when they name the same day.
    const stated = (value: unknown) =>
      value === undefined || value === null ? null : required(value);
    const statedUntil = stated(request.covered_until);
    const statedThrough = stated(request.covered_through);
    if (statedUntil === null && statedThrough === null) return invalid();
    if (
      !DATE.test(from) ||
      (statedUntil !== null && !DATE.test(statedUntil)) ||
      (statedThrough !== null && !DATE.test(statedThrough))
    )
      return invalid();
    const until = statedUntil ?? dayAfter(statedThrough!);
    if (statedThrough !== null && statedThrough !== dayBefore(until))
      return invalid();
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
            { tax_year: asCount(year) },
            { forecast: null },
          );
    if (row.absence === "period_elapsed")
      return refuse(
        UNSUPPORTED,
        "amortization_period_elapsed",
        { ended_on: asDate(element.limits.maximum_period_last_day ?? "") },
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
      return refuse(
        CLAIM_CONFLICT,
        "claims_overlap",
        { conflicting_claim_ids: ids(overlapping) },
        { forecast: null },
      );
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
        covered_through: dayBefore(until),
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
        { ended_on: asDate(element.limits.maximum_period_last_day ?? "") },
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
          tax_year: asCount(given.tax_year),
          last_admitted_year: asCount(LAST_ADMITTED_YEAR),
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
        { conflicting_claim_ids: ids(overlapping) },
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
      covered_through: dayBefore(given.covered_until),
      effective: true,
      superseded_by: null,
      revision_id: latest(element).revision_id,
      matches_current_schedule: true,
      stale_reason: null,
    };
    if (target) {
      target.effective = false;
      target.superseded_by = claimId;
      retire(element, target.claim_id);
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
      target ? "claim_replaced" : "claim_recorded",
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
        claim: claimUse(next, row.tax_year, {
          matches_current_schedule: true,
          stale_reason: null,
        }),
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
