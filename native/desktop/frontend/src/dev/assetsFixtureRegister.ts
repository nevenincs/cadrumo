// The scenario register the Assets simulation holds: its elements, the
// history it writes, a year restated after a claim, the reads and the judging
// of a revision as the backend judges it.

import type {
  DescriptorFacts,
  PlanClaim,
  PlanRow,
  ReasonFact,
  TimelineClaimUse,
  TimelineEvent,
} from "@/shell/ledgerSetup";
import type {
  JsonObject,
  LedgerDefinitionId,
  OutputLanguage,
} from "../shell/ledger";
import {
  ACQUIRED_CONDITIONS,
  ACQUISITION_SHAPES,
  ADMITTED_METHODS,
  BASIS_STAGES,
  DECLARED_ACTIVITIES,
  FURTHER_ACQUISITION_SHAPES,
  NOT_APPLICABLE_ABSENCES,
  REMEDY_FIELD_KEYS,
  SCENARIO_CREATIONS,
  SCENARIO_ELEMENTS,
  SCENARIO_PAYMENTS,
  SCENARIO_REGIME,
  SCENARIO_TODAY,
  TABLE_BOUND_METHODS,
  TABLE_GROUPS,
  TIMELINE_FACT_PATHS,
  type ScenarioCreation,
  formOptionsFor,
} from "./assetsRegister";
import {
  recordsEditionFor,
  servedEditionOf,
  type ServedEdition,
} from "./servedYearAuthority";
import {
  DATE,
  ERRORS,
  type Element,
  FAMILY,
  type Fact,
  type Handler,
  INCOMPLETE,
  SERVED_METHOD_FACTS,
  TOKEN_FIELDS,
  type Tools,
  UNSUPPORTED,
  VALIDATION,
  asCount,
  asDate,
  asPercent,
  dayAfter,
  dec,
  decimalOf,
  earlier,
  fromCents,
  json,
  later,
  textOf,
  toCents,
  withThrough,
} from "./assetsFixtureBase";

export type Session = { language: OutputLanguage };

export function makeRegister(
  tools: Tools,
  session: Session,
  wordedDetail: (detail: JsonObject) => JsonObject,
) {
  const { now, hex64, invalid, unrecorded } = tools;
  const stop = (reason: string, detail: JsonObject): never =>
    tools.stop(reason, wordedDetail(detail));

  const elements = new Map<string, Element>(
    SCENARIO_ELEMENTS.map((seed) => {
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
          // An element the register already records a baja for stands out of
          // service the day after its last day, so its service window ends
          // where the register says it ends rather than at the year.
          outOfService:
            copy.list.disposal === null
              ? null
              : dayAfter(copy.list.disposal.disposal_date),
          baja: null,
        },
      ];
    }),
  );
  /** The purchases an element has taken as its acquisition. */
  const taken = new Set<string>();
  // The backend's history numbers every event of the register in one sequence,
  // so a new event continues the recorded numbering rather than restarting per
  // element.
  const sequence = {
    last: Math.max(
      0,
      ...[...elements.values()].flatMap((element) =>
        element.events.map((event) => event.sequence),
      ),
    ),
  };

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

  // The recording spans every year a plan can reach; one before it has no edition.
  const editionOf = (year: number): ServedEdition | null =>
    recordsEditionFor(year) ? servedEditionOf(year) : null;

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
    sequence.last += 1;
    element.events.push({
      sequence: sequence.last,
      recorded_at: now(),
      kind,
      event_kind: eventKind,
      asset_id: element.id,
      record_id: hex64(`${kind}:${element.id}:${sequence.last}`),
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
    const elapsed = open.filter(
      (year) => year <= Number(SCENARIO_TODAY.slice(0, 4)),
    );
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
      const elapsed = years.filter(
        (year) => year <= Number(SCENARIO_TODAY.slice(0, 4)),
      );
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
      const options = formOptionsFor(kind, year);
      if (options === undefined)
        return refuse(
          UNSUPPORTED,
          "tax_year_without_edition",
          { tax_year: asCount(year) },
          { options: null },
        );
      return json({ ...ok, options });
    },
    "ledger.actividad-asset.acquisition-candidates": (request) => {
      exact(request, []);
      return json({
        ...ok,
        candidates: SCENARIO_PAYMENTS.filter(
          (purchase) => !taken.has(purchase.transaction_id),
        ),
      });
    },
  };

  // ---- Revisions -------------------------------------------------------------

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
    if (acquiredAs === null || !ACQUISITION_SHAPES.includes(acquiredAs))
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
      if (activity === null || !DECLARED_ACTIVITIES.includes(activity))
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
        if (!SCENARIO_PAYMENTS.some((found) => found.transaction_id === id))
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
      !BASIS_STAGES.some((found) => found.stage === basis.stage)
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
    if (election.regime !== SCENARIO_REGIME) return invalid();
    const method = textOf(election.method);
    if (method === null) return invalid();
    if (!ADMITTED_METHODS[kind]!.includes(method))
      return refuse(
        UNSUPPORTED,
        "method_not_enrolled_for_kind",
        { asset_kind: kind, method, regime: SCENARIO_REGIME },
        shape,
      );
    const classKey = textOf(election.authority_class_key);
    const group = TABLE_GROUPS[kind]!.find(
      (found) => found.class_key === classKey,
    );
    if (TABLE_BOUND_METHODS.includes(method) && classKey === null)
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
    const like = SCENARIO_ELEMENTS.find(
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

  /** A revision as the recording holds it: the facts it states, with the
   * identity the window mints left out and the fields in one order. The
   * register answers the same plan whatever the element is called, and a
   * description moves no figure of it. */
  const asRecorded = (revision: JsonObject) =>
    JSON.stringify(
      Object.entries(revision)
        .filter(([name]) => name !== "asset_id")
        .sort(([a], [b]) => a.localeCompare(b)),
    );

  const recordedCreations = new Map(
    SCENARIO_CREATIONS.map((made) => [
      asRecorded(made.revisions[0]!.revision),
      made,
    ]),
  );

  /** What the register answered for this very create request, or null where it
   * was never asked it. */
  const recordedCreation = (revision: JsonObject): ScenarioCreation | null =>
    recordedCreations.get(asRecorded(revision)) ?? null;

  /** The recorded answer held as an element of the register, under the identity
   * the window minted for it. */
  const installed = (
    answer: ScenarioCreation,
    id: string,
    descriptor: DescriptorFacts,
  ): Element => {
    const copy = structuredClone(answer) as unknown as ScenarioCreation;
    for (const row of copy.rows) {
      row.claims = row.claims.map(withThrough);
      row.claimable_intervals = row.claimable_intervals.map(withThrough);
    }
    return {
      ...copy,
      id,
      list: { ...copy.list, asset_id: id, name: descriptor.name },
      events: [],
      descriptor,
      outOfService:
        copy.list.disposal === null
          ? null
          : dayAfter(copy.list.disposal.disposal_date),
      baja: null,
    };
  };

  /** The charge the register answered for a span, or for another span of an
   * element whose election it answered: the provisions a charge cites are the
   * election's, not the span's, the way `citationsFor` reads them. Null where
   * the register answered no charge of any like election, which a forecast is
   * refused for rather than named from anything stated here. */
  const recordedChargeFor = (
    element: Element,
    from: string,
    until: string,
  ): JsonObject | null => {
    const own = SCENARIO_ELEMENTS.find((seed) => seed.id === element.id);
    const exact = own?.charges[`${from}/${until}`];
    if (exact !== undefined) return exact;
    const like =
      own ??
      SCENARIO_ELEMENTS.find(
        (seed) =>
          seed.list.asset_kind === element.list.asset_kind &&
          seed.list.method === element.list.method &&
          seed.limits.class_key === element.limits.class_key &&
          Object.keys(seed.charges).length > 0,
      ) ??
      SCENARIO_ELEMENTS.find(
        (seed) =>
          seed.list.asset_kind === element.list.asset_kind &&
          seed.list.method === element.list.method &&
          Object.keys(seed.charges).length > 0,
      );
    return Object.values(like?.charges ?? {})[0] ?? null;
  };

  return {
    recordedChargeFor,
    recordedCreation,
    installed,
    now,
    hex64,
    invalid,
    unrecorded,
    session,
    stop,
    elements,
    taken,
    authority,
    ok,
    refuse,
    required,
    exact,
    find,
    editionOf,
    SHARE_FIELDS,
    history,
    fieldKeyOf,
    claimUse,
    retire,
    record,
    uncovered,
    serviceWindow,
    settle,
    restate,
    claimYearOf,
    recount,
    notFound,
    reads,
    obj,
    flatten,
    changesBetween,
    FIGURE_NEUTRAL,
    movesCharge,
    latest,
    judgeRevision,
    describe,
    citationsFor,
  };
}

export type Register = ReturnType<typeof makeRegister>;
