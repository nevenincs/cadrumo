// The writes the Assets tab sends to the scenario register, and the reads
// worked out from what a write left: a forecast, an inspection, the filing
// handoff and a baja's figures.

import type {
  AssetListRow,
  DescriptorFacts,
  DisposalCalculation,
  DisposalFacts,
  PlanClaim,
  PlanRow,
} from "@/shell/ledgerSetup";
import type { JsonObject } from "../shell/ledger";
import {
  NO_TABLE_MINIMUM_KEY,
  SCENARIO_PAYMENTS,
  SCENARIO_TODAY,
  TABLE_GROUPS,
} from "./assetsRegister";
import {
  recordsEditionFor,
  servedAdmits,
  servedBeyondLastAdmitted,
  servedEditionYears,
  servedHandoffOf,
  servedSupport,
} from "./servedYearAuthority";
import {
  CLAIM_CONFLICT,
  DATE,
  ERRORS,
  type Element,
  FAMILY,
  FINDING,
  type Handler,
  INCOMPLETE,
  UNSUPPORTED,
  VALIDATION,
  asAmount,
  asCount,
  asDate,
  chargeFor,
  dayAfter,
  dayBefore,
  daysBetween,
  dec,
  decimalOf,
  earlier,
  fromCents,
  json,
  later,
  leap,
  textOf,
  toCents,
  todayYear,
  withThrough,
} from "./assetsFixtureBase";
import type { Register } from "./assetsFixtureRegister";

export function makeWrites(register: Register) {
  const {
    ok,
    citationsFor,
    hex64,
    invalid,
    elements,
    taken,
    authority,
    refuse,
    required,
    exact,
    find,
    editionOf,
    history,
    claimUse,
    retire,
    record,
    uncovered,
    serviceWindow,
    settle,
    restate,
    recount,
    notFound,
    obj,
    changesBetween,
    movesCharge,
    latest,
    judgeRevision,
    recordedChargeFor,
  } = register;
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
        claim_state:
          year > Number(SCENARIO_TODAY.slice(0, 4)) ? "not_due" : "missing",
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
        minimum_has_no_table: minimumReason === NO_TABLE_MINIMUM_KEY,
        minimum_complete: minimumReason === null,
      };
    };
    if (left === null) {
      for (
        let year = first;
        year <= Math.max(first, todayYear) && rows.length < 6;
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
    for (
      let year = first;
      rows.length < 15 && year <= servedEditionYears.last;
      year++
    ) {
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
      const purchase = SCENARIO_PAYMENTS.find(
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
          (year) => servedAdmits(year) && !servedBeyondLastAdmitted(year),
        ),
      projected_years: rows
        .map((row) => row.tax_year)
        .filter((year) => servedAdmits(year) && servedBeyondLastAdmitted(year)),
    };
    const element: Element = {
      id,
      list,
      annual: annual ?? "0.00",
      forecasts: {},
      charges: {},
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
    const language = String(request.output_language);
    const boxes = recordsEditionFor(year) ? servedHandoffOf(year) : null;
    if (boxes === null) return invalid();
    const quarter =
      period === null
        ? null
        : boxes.m130.find((found) => found.period === period);
    if (quarter === undefined) return invalid();
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
        target_casilla_id: boxes.m100[kind]!.casilla,
        box_name: boxes.m100[kind]!.names[language]!,
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
        target_casilla_id: quarter!.casilla,
        box_name: quarter!.names[kind]![language]!,
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
    element.list.pending_applies =
      dayAfter(facts.disposal_date) > SCENARIO_TODAY;
    element.rows = element.rows.filter(
      (row) => row.tax_year <= Number(facts.disposal_date.slice(0, 4)),
    );
    if (facts.disposal_date < SCENARIO_TODAY)
      element.list.state = "out_of_service";
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
    // The provisions a charge rests on are the register's, never named here. A
    // span it answered is replayed whole while the revision it rests on still
    // stands; any other span carries the provisions the register cited for this
    // element, whose election cites the same ones whatever the span.
    const charge = recordedChargeFor(element, from, until);
    if (charge === null)
      return refuse(
        INCOMPLETE,
        "schedule_authority_unavailable",
        {},
        { forecast: null },
      );
    if (
      charge.covered_from === from &&
      charge.covered_until === until &&
      charge.asset_revision_id === latest(element).revision_id &&
      row.absence !== "free_election"
    )
      return json({ ...ok, forecast: charge });
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
        source_reference: charge.source_reference,
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
    if (!again && servedBeyondLastAdmitted(given.tax_year))
      return refuse(
        UNSUPPORTED,
        "claim_year_beyond_registry",
        {
          tax_year: asCount(given.tax_year),
          last_admitted_year: asCount(servedSupport.horizon),
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
    startingRows,
    create,
    correct,
    inspect,
    PERIOD_END,
    filingHandoff,
    judge,
    ids,
    statedDisposal,
    putOutOfService,
    dispose,
    calculate,
    forecast,
    claim,
  };
}
