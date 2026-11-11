import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import {
  claimLanded,
  claimReused,
  correctionLanded,
  elementLanded,
  INCOMPLETE,
  staleClaims,
} from "../src/components/ledger/assets/assetWrites";
import {
  factKey,
  fieldsFor,
  initialOf,
} from "../src/components/ledger/assets/assetFields";
import { answer } from "../src/components/ledger/assets/assetFormValues";
import { correctRequest } from "../src/components/ledger/assets/assetRevision";
import { type LedgerResult } from "../src/shell/ledger";
import {
  SCENARIO_CREATIONS,
  SCENARIO_ELEMENTS,
} from "../src/dev/assetsRegister";
import { dayBefore } from "../src/dev/assetsFixtureBase";
import { servedHandoffOf, servedSupport } from "../src/dev/servedYearAuthority";

import {
  beyondHorizon,
  scenarioYear,
  priorYear,
  PLAN,
  DISPOSE,
  FORECAST,
  CLAIM,
  CREATE,
  CORRECT,
  INSPECT,
  HANDOFF,
  CALCULATE,
  portOf,
  settled,
  type Refused,
  refused,
  registerOf,
  listOf,
  planOf,
  eventsOf,
  cents,
  optionsOf,
  newRequest,
  NEW_ELEMENT,
  OPENING_MISSING,
  USED_ELEMENT,
  sale,
  servidorRow,
} from "./support/assetContract";
import { fixtureDay } from "../src/dev/fixtureDates";

// The Assets tab's writes against the scenario register: creating and
// correcting from the requests the forms make, bajas, forecasts and claims.

// ---- Creating and correcting, from the requests the forms make --------------------

test("adding an element sends the revision and descriptor the backend decodes, which judges the revision's facts", async () => {
  const port = portOf();
  const send = async (changes: Record<string, string>, id = "made-2") => {
    const request = await newRequest(port, { ...NEW_ELEMENT, ...changes }, id);
    expect(request, JSON.stringify(changes)).not.toBeNull();
    return port.submit(CREATE, request! as never);
  };
  // The request carries the whole revision and the descriptor, and no drafted values.
  const request = (await newRequest(port, NEW_ELEMENT, "made-2"))!;
  expect(Object.keys(request).sort()).toEqual(["descriptor", "revision"]);
  expect(request.descriptor).toMatchObject({
    name: "Sierra de cinta",
    serial_number: "SC-0412",
  });
  expect(request.revision).toMatchObject({
    asset_id: "made-2",
    revision_number: 1,
    acquisition_shape: "primary_purchase",
    basis: { stage: "business_allocated", basis_amount: { decimal: "900" } },
    opening_history: { status: "known", accumulated_amount: { decimal: "0" } },
    amortization: { regime: "normal", method: "linear" },
  });
  // No request is made while the person has not chosen a purchase.
  expect(
    await newRequest(port, { ...NEW_ELEMENT, acquisition: "" }, "made-2"),
  ).toBeNull();

  const noShare = await refused(send({ basis_stage: "taxpayer_owned" }));
  expect(noShare.detail.refusal).toMatchObject({
    code: INCOMPLETE,
    reason_key: "ledger.actividad_asset.errors.business_use_share_missing",
  });
  const noProvenance = await refused(send({ prior_allocation_provenance: "" }));
  expect(noProvenance.detail.refusal.precondition_verdict).toEqual({
    missing_field_keys: ["basis.prior_allocation_provenance"],
  });
  const wrongMethod = await refused(send({ method: "goodwill" }));
  expect(wrongMethod.detail.refusal).toMatchObject({
    code: "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED",
    reason_key: "ledger.actividad_asset.errors.method_not_enrolled_for_kind",
  });
  const noClass = await refused(
    send({ "amortization.authority_class_key": "" }),
  );
  expect(noClass.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.table_class_required",
  );
  const noAmount = await refused(send({ opening_amount: "" }));
  expect(noAmount.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.opening_history_amount_missing",
  );
  const noYear = await refused(send({ opening_amount: "100.00" }));
  expect(noYear.detail.refusal.precondition_verdict).toEqual({
    missing_field_keys: ["opening_history.covered_through_tax_year"],
  });
  const early = await refused(
    send({ opening_amount: "100.00", opening_through: String(priorYear) }),
  );
  expect(early.detail.refusal).toMatchObject({
    reason_key: "ledger.actividad_asset.errors.opening_year_before_in_service",
    reason_facts: [
      {
        key: "in_service_tax_year",
        value: String(scenarioYear),
        kind: "count",
      },
      { key: "opening_tax_year", value: String(priorYear), kind: "count" },
    ],
  });
  const outside = await refused(
    send({ "amortization.linear_coefficient": "0.99" }),
  );
  expect(outside.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.elected_coefficient_out_of_range",
  );
  const lowValue = await refused(send({ method: "low_value_free" }));
  expect(lowValue.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.low_value_election_required",
  );
  expect((await listOf(port)).some((row) => row.asset_id === "made-2")).toBe(
    false,
  );

  expect((await port.submit(CREATE, request as never)).kind).toBe("settled");
  const rows = await listOf(port);
  const made = rows.find((row) => row.asset_id === "made-2")!;
  // The element the register answered for this very request, under the
  // identity the window minted for it.
  const answered = SCENARIO_CREATIONS.find(
    (creation) => creation.id === "linear_new",
  )!;
  expect(made).toEqual({ ...answered.list, asset_id: "made-2" });
  expect(elementLanded(await registerOf(port), "made-2")).toBe("saved");
  // The first year the register planned, by the days it serves of it.
  const first = (await planOf(port, "made-2"))[0]!;
  expect(first).toMatchObject({
    tax_year: scenarioYear,
    absence: null,
    service_days: answered.rows[0]!.service_days,
    calendar_days: answered.rows[0]!.calendar_days,
    minimum_complete: true,
  });
  expect(first.coefficient).toEqual(answered.rows[0]!.coefficient);
  expect(first.planned).toEqual(answered.rows[0]!.planned);
  expect(first.planned).not.toBeNull();
  // Replaying the same request adds nothing.
  expect((await port.submit(CREATE, request as never)).kind).toBe("settled");
  expect(
    (await listOf(port)).filter((row) => row.asset_id === "made-2"),
  ).toHaveLength(1);
  // The history holds the revision with the tokens it states, by catalogue key.
  const events = await eventsOf(port, "made-2");
  const stage = events[0]!.changes.find(
    (change) => change.field === "basis.stage",
  )!;
  expect(stage).toMatchObject({
    after: "business_allocated",
    after_key: "ledger.actividad_asset.basis_stage.business_allocated",
  });
});

test("an element whose opening history is missing starts without figures, and says why", async () => {
  const port = portOf();
  const request = await newRequest(port, OPENING_MISSING, "made-3");
  expect((await port.submit(CREATE, request! as never)).kind).toBe("settled");
  const made = (await listOf(port)).find((row) => row.asset_id === "made-3")!;
  expect(made).toMatchObject({ accumulated: null, pending: null });
  expect((await planOf(port, "made-3"))[0]).toMatchObject({
    absence: "incomplete",
    planned: null,
    absence_reason_key: "ledger.actividad_asset.errors.opening_history_missing",
  });
});

test("an originating price is stated only for a used element on the linear method", async () => {
  const port = portOf();
  const request = (await newRequest(port, USED_ELEMENT, "made-4"))!;
  expect(
    (request.revision.amortization as { used_original_price: unknown })
      .used_original_price,
  ).toEqual({
    determination: "expert_valuation",
    original_price: { decimal: "1500" },
    evidence_reference: "valuation report of the appraiser",
  });
  expect((await port.submit(CREATE, request as never)).kind).toBe("settled");
  const inspected = await settled<LedgerResult<typeof INSPECT>>(
    port.submit(INSPECT, { asset_id: "made-4" }),
  );
  expect(inspected.revisions).toHaveLength(1);
  // A new element states none: the field is not even drawn.
  const options = await optionsOf(port);
  const fields = fieldsFor(
    {
      kind: "element",
      row: null,
      descriptor: null,
      revision: null,
      tokens: () => [],
      options,
    },
    { ...NEW_ELEMENT },
  );
  expect(
    fields.some(
      (found) =>
        found.key === factKey(["used_original_price", "original_price"]),
    ),
  ).toBe(false);
  const advised = await settled<LedgerResult<typeof PLAN>>(
    port.submit(PLAN, { asset_id: "made-4" }),
  );
  expect(advised.advisories).toEqual([
    {
      kind: "used_element_group_limit",
      label_key:
        "ledger.actividad_asset.plan_advisory.used_element_group_limit",
      words: null,
      words_language: "es",
    },
  ]);
  const seeded = await settled<LedgerResult<typeof PLAN>>(
    port.submit(PLAN, { asset_id: "servidor" }),
  );
  expect(seeded.advisories).toEqual([]);
  const stray = structuredClone(request) as unknown as {
    revision: { asset_id: string; acquired_condition: string };
  };
  stray.revision.asset_id = "made-5";
  stray.revision.acquired_condition = "new";
  const refusal = await refused(port.submit(CREATE, stray as never));
  expect(refusal.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.used_original_price_requires_used_asset",
  );
});

test("a correction names the revision it stands on, and the claims it records again leave the stale ones", async () => {
  const port = portOf();
  const inspected = await settled<LedgerResult<typeof INSPECT>>(
    port.submit(INSPECT, { asset_id: "servidor" }),
  );
  const base = inspected.revisions!.at(-1)!;
  expect(base.revision_id).toMatch(/^[0-9a-f]{64}$/);
  const row = servidorRow();
  const options = await optionsOf(port);
  const context = {
    kind: "correction" as const,
    row,
    descriptor: null,
    revision: base.revision,
    tokens: () => [],
    options,
  };
  const initial = initialOf(context, fieldsFor(context, {}));
  const draft = { ...initial, basis_amount: "3600" };
  const stated = answer(fieldsFor(context, draft), draft, initial);
  expect(stated.values).toEqual({ basis_amount: { decimal: "3600" } });
  const stale = correctRequest(
    stated.values,
    {
      assetId: "servidor",
      regime: null,
      candidate: null,
      base: { ...base, revision_id: "0".repeat(64) },
    },
    [],
  )!;
  const refusal = await refused(port.submit(CORRECT, stale as never));
  expect(refusal.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.correction_must_supersede_current",
  );
  const claim = (await planOf(port, "servidor"))[0]!.claims[0]!;
  const request = correctRequest(
    stated.values,
    { assetId: "servidor", regime: null, candidate: null, base },
    [claim.claim_id],
  )!;
  expect(request.revision).toMatchObject({
    supersedes_revision_id: base.revision_id,
    basis: { basis_amount: { decimal: "3600" } },
  });
  // The register numbers the revision; the request states no number, and
  // always states its baja, null where there is none.
  expect(request.revision).not.toHaveProperty("revision_number");
  expect(request.revision).toHaveProperty("disposal", null);
  expect(request.superseding_claims).toEqual([
    { supersedes_claim_id: claim.claim_id, requested_free_amount: null },
  ]);
  const done = await settled<{ outcome: string }>(
    port.submit(CORRECT, request as never),
  );
  expect(done.outcome).toBe("succeeded");
  const after = (await listOf(port)).find(
    (found) => found.asset_id === "servidor",
  )!;
  expect(after).toMatchObject({ revision_number: 3, findings: { stale: 0 } });
  expect(after.basis.decimal).toBe("3600.00");
  const claims = (await planOf(port, "servidor"))[0]!.claims;
  expect(
    claims.find((found) => found.claim_id === claim.claim_id),
  ).toMatchObject({ effective: false });
  expect(claims.filter((found) => found.effective)).toHaveLength(1);
  expect(staleClaims(await planOf(port, "servidor"))).toEqual([]);
  expect(correctionLanded(await registerOf(port), "servidor", 2)).toBe("saved");
  // The new revision chains to the one it supersedes.
  const chain = await settled<LedgerResult<typeof INSPECT>>(
    port.submit(INSPECT, { asset_id: "servidor" }),
  );
  expect(chain.revisions!.at(-1)!.revision).toMatchObject({
    supersedes_revision_id: base.revision_id,
  });
});

test("the filing handoff reads the seeded claims, and names the element it cannot work out", async () => {
  const port = portOf();
  const handoff = await settled<LedgerResult<typeof HANDOFF>>(
    port.submit(HANDOFF, {
      tax_year: priorYear,
      output_language: "en",
      m130_period: "4T",
    }),
  );
  const projection = handoff.filing_handoff!;
  const effective = (kind: string) =>
    SCENARIO_ELEMENTS.filter((seed) => seed.list.asset_kind === kind).flatMap(
      (seed) =>
        seed.rows
          .filter((row) => row.tax_year === priorYear)
          .flatMap((row) => row.claims.filter((claim) => claim.effective)),
    );
  for (const [kind, key] of [
    ["material", "material_m100"],
    ["intangible", "intangible_m100"],
  ] as const) {
    const claims = effective(kind);
    const total = claims.reduce(
      (sum, claim) => sum + cents(claim.amount.decimal),
      0n,
    );
    expect(projection[key]!.claim_ids.sort()).toEqual(
      claims.map((claim) => claim.claim_id).sort(),
    );
    expect(cents(projection[key]!.amount.decimal)).toBe(total);
    expect(projection[key]!.amount.decimal).not.toBe("0.00");
  }
  const boxes = servedHandoffOf(priorYear)!;
  expect(projection.material_m100!.target_casilla_id).toBe(
    boxes.m100.material!.casilla,
  );
  expect(projection.intangible_m100!.target_casilla_id).toBe(
    boxes.m100.intangible!.casilla,
  );
  // Every element of the year is behind the quarter's box, and the one it cannot work out is named.
  const material130 = projection.material_m130!;
  expect(material130.target_casilla_id).toBe(
    boxes.m130.find((box) => box.period === "4T")!.casilla,
  );
  expect(material130.unavailable_asset_ids).toEqual(["estanteria"]);
  expect(
    material130.contributions.some(
      (item) => item.asset_id === "furgoneta" && item.claim_id !== null,
    ),
  ).toBe(true);
  const quarter = await settled<LedgerResult<typeof HANDOFF>>(
    port.submit(HANDOFF, {
      tax_year: priorYear,
      output_language: "en",
      m130_period: "1T",
    }),
  );
  expect(
    cents(quarter.filing_handoff!.material_m130!.amount.decimal),
  ).toBeLessThanOrEqual(cents(material130.amount.decimal));
});

test("each plan year states its minimum amortization, or is unknown with the reason while an earlier year has none", async () => {
  const port = portOf();
  const rows = await planOf(port, "plotter");
  // A minimum is never a partial sum or a zero: it is a figure only where
  // every year up to it has one, and otherwise null with its reason.
  for (const row of rows) {
    expect(typeof row.minimum_complete).toBe("boolean");
    expect(row.minimum_through === null, String(row.tax_year)).toBe(
      !row.minimum_complete,
    );
    expect(row.minimum_reason_key === null, String(row.tax_year)).toBe(
      row.minimum_complete,
    );
  }
  // Years before the first edition have no minimum, so every year after is unknown.
  expect(rows.every((row) => !row.minimum_complete)).toBe(true);
  expect(
    rows.every(
      (row) =>
        row.minimum_reason_key ===
        "ledger.actividad_asset.disposal_finding.minimum_unresolved",
    ),
  ).toBe(true);
  const complete = await planOf(port, "servidor");
  expect(complete.every((row) => row.minimum_complete)).toBe(true);
  const through = complete.map((row) => cents(row.minimum_through!.decimal));
  expect(through).toEqual(
    [...through].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0)),
  );
});

test("the limits cite the provisions behind the election, each with its official link, and say when the list is partial", async () => {
  const port = portOf();
  const limitsOf = async (id: string) =>
    (
      await settled<LedgerResult<typeof PLAN>>(
        port.submit(PLAN, { asset_id: id }),
      )
    ).limits!;
  // Every provision the register cites for an election, and none stated
  // here: the text and the official link are its own, and a list it calls
  // complete has something in it.
  const long = await limitsOf("furgoneta");
  expect(long.legal_citations.length).toBeGreaterThan(0);
  for (const seed of SCENARIO_ELEMENTS) {
    const held = await limitsOf(seed.id);
    expect(held.legal_citations).toEqual(seed.limits.legal_citations);
    expect(held.legal_citations_complete).toBe(
      seed.limits.legal_citations_complete,
    );
    if (held.legal_citations_complete)
      expect(held.legal_citations.length).toBeGreaterThan(0);
    for (const citation of held.legal_citations) {
      expect(Object.keys(citation).sort()).toEqual(["permalink", "text"]);
      expect(citation.permalink).toMatch(/^https:\/\/www\.boe\.es\//);
      expect(citation.text.length).toBeGreaterThan(0);
    }
  }
  expect("legal_references" in long).toBe(false);
});

test("a baja is judged by the backend, which refuses by key and facts", async () => {
  const port = portOf();
  const dispose = (disposal: object, id = "furgoneta") =>
    port.submit(DISPOSE, { asset_id: id, disposal } as never);
  const reasonOf = async (disposal: object) => {
    const found = await refused(dispose(disposal));
    return [found.detail.refusal.code, found.detail.refusal.reason_key];
  };
  expect(
    await reasonOf({ ...sale, disposal_date: fixtureDay(1, 1, -6) }),
  ).toEqual([
    "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
    "ledger.actividad_asset.errors.disposal_before_service",
  ]);
  // A donation is typed so that the backend refuses it, not the form.
  expect(await reasonOf({ ...sale, reason: "donation" })).toEqual([
    "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED",
    "ledger.actividad_asset.errors.disposal_donation_refused",
  ]);
  expect(await reasonOf({ ...sale, reason: "scrapping" })).toEqual([
    "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
    "ledger.actividad_asset.errors.disposal_scrapping_with_proceeds",
  ]);
  expect(await reasonOf({ ...sale, reason: "withdrawal" })).toEqual([
    "REFUSED_ACTIVIDAD_ASSET_VALIDATION",
    "ledger.actividad_asset.errors.disposal_withdrawal_with_amounts",
  ]);
  const unknown = await refused(dispose(sale, "nobody"));
  expect(unknown.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.asset_not_found",
  );
  // Nothing was recorded by any refusal.
  expect(
    (await listOf(port)).find((row) => row.asset_id === "furgoneta"),
  ).toMatchObject({ state: "in_service", revision_number: 1 });
});

test("a baja ends the plan at the year of its last day, lists the element out of service and is recorded once", async () => {
  const port = portOf();
  await settled(
    port.submit(DISPOSE, {
      asset_id: "furgoneta",
      disposal: sale,
    } as never),
  );
  const row = (await listOf(port)).find(
    (found) => found.asset_id === "furgoneta",
  )!;
  expect(row).toMatchObject({ state: "out_of_service", revision_number: 2 });
  expect((await planOf(port, "furgoneta")).at(-1)!.tax_year).toBe(priorYear);
  const event = (await eventsOf(port, "furgoneta")).at(-1)!;
  expect(event).toMatchObject({ kind: "baja", affects_calculation: true });
  expect(event.changes).toEqual([
    ...[
      ["disposal.disposal_date", fixtureDay(6, 30, -1)],
      ["disposal.reason", "sale"],
      ["disposal.proceeds", "9000.00"],
      ["disposal.transmission_costs", "150.00"],
    ].map(([field, after]) => ({
      kind: "added",
      field,
      field_key: `ledger.actividad_asset.field.${field}`,
      before: null,
      after,
      before_key: null,
      after_key: null,
      before_label: null,
      after_label: null,
    })),
  ]);
  // The same baja stated again is the record already there, not a refusal.
  const retried = await port.submit(DISPOSE, {
    asset_id: "furgoneta",
    disposal: sale,
  } as never);
  expect(retried.kind).toBe("settled");
  expect(
    (await eventsOf(port, "furgoneta")).filter((e) => e.kind === "baja"),
  ).toHaveLength(1);
  const again = await refused(
    port.submit(DISPOSE, {
      asset_id: "furgoneta",
      disposal: { ...sale, proceeds: { decimal: "9100.00" } },
    } as never),
  );
  expect(again.detail.refusal).toMatchObject({
    reason_key: "ledger.actividad_asset.errors.disposal_already_recorded",
    reason_facts: [{ key: "disposal_date", value: fixtureDay(6, 30, -1) }],
  });
});

test("the figures of a baja are the backend's: a stated baja previews and writes nothing, an unstated one reads the record", async () => {
  const port = portOf();
  const calculate = (disposal: object | null, id = "furgoneta") =>
    port.submit(CALCULATE as never, { asset_id: id, disposal } as never);
  const before = await listOf(port);
  const events = await eventsOf(port, "furgoneta");
  const preview = (
    await settled<{
      calculation: LedgerResult<typeof CALCULATE>["calculation"];
    }>(calculate(sale))
  ).calculation!;
  // The result is what the sale brought less its costs and the net value.
  expect(cents(preview.net_value.decimal)).toBe(
    cents(preview.acquisition_value.decimal) - cents(preview.reduction.decimal),
  );
  expect(cents(preview.result!.decimal)).toBe(
    cents(sale.proceeds.decimal) -
      cents(sale.transmission_costs.decimal) -
      cents(preview.net_value.decimal),
  );
  expect(preview.transmission_value).toEqual(sale.proceeds);
  expect(preview.years.at(-1)).toMatchObject({ tax_year: scenarioYear });
  expect(
    preview.findings.every((finding) =>
      finding.label_key.startsWith("ledger.actividad_asset.disposal_finding."),
    ),
  ).toBe(true);
  // A withdrawal computes no transmission figure and no result.
  const withdrawal = (
    await settled<{
      calculation: { result: unknown; transmission_value: unknown };
    }>(
      calculate({
        ...sale,
        reason: "withdrawal",
        proceeds: { decimal: "0.00" },
        transmission_costs: { decimal: "0.00" },
      }),
    )
  ).calculation;
  expect(withdrawal).toMatchObject({ result: null, transmission_value: null });
  // A preview records nothing.
  expect(await listOf(port)).toEqual(before);
  expect(await eventsOf(port, "furgoneta")).toEqual(events);
  // With no baja stated and none recorded the backend says so.
  const none = await refused(calculate(null));
  expect(none.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.disposal_not_recorded",
  );
  await settled(
    port.submit(DISPOSE, {
      asset_id: "furgoneta",
      disposal: sale,
    } as never),
  );
  const recorded = (
    await settled<{ calculation: { disposal_date: string; reason: string } }>(
      calculate(null),
    )
  ).calculation;
  expect(recorded).toMatchObject({
    disposal_date: fixtureDay(6, 30, -1),
    reason: "sale",
  });
  // An element whose opening history is unknown cannot be worked out.
  const missing = await refused(calculate(sale, "estanteria"));
  expect(missing.detail.refusal).toMatchObject({
    code: INCOMPLETE,
    reason_key: "ledger.actividad_asset.errors.opening_history_missing",
  });
  // The preview is judged like the record.
  const donation = await refused(calculate({ ...sale, reason: "donation" }));
  expect(donation.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.disposal_donation_refused",
  );
});

test("a forecast works out a span and records nothing; a claim is recorded once and refused where it overlaps", async () => {
  const port = portOf();
  // The span the register left open on the furgoneta's own year.
  const furgoneta = SCENARIO_ELEMENTS.find((seed) => seed.id === "furgoneta")!;
  const open = furgoneta.rows.find((row) => row.tax_year === scenarioYear)!
    .claimable_intervals[0]!;
  const ask = (extra: object) =>
    port.submit(FORECAST, {
      asset_id: "furgoneta",
      covered_from: open.covered_from,
      covered_until: open.covered_until,
      requested_free_amount: null,
      supersedes_claim_id: null,
      ...extra,
    } as never) as unknown as Promise<{
      kind: string;
      result?: {
        forecast: {
          amount: { decimal: string };
          service_days: number;
          asset_id: string;
        } & Record<string, never>;
      };
    }>;
  const before = await planOf(port, "furgoneta");
  const forecast = (await ask({})).result!.forecast;
  // The rest of the year, as the register forecast it.
  const span = `${open.covered_from}/${open.covered_until}`;
  expect(forecast.amount.decimal).toBe(furgoneta.forecasts[span]);
  expect(forecast.service_days).toBe(
    (furgoneta.charges[span] as unknown as { service_days: number })
      .service_days,
  );
  expect(await planOf(port, "furgoneta")).toEqual(before);
  const claim = () =>
    port.submit(CLAIM, {
      forecast,
      supersedes_claim_id: null,
    } as never) as unknown as Promise<{
      kind: string;
      result?: {
        claim_result: { reused_existing_claim: boolean };
        claim_id: string;
      };
    }>;
  const first = (await claim()).result!;
  expect(first.claim_result.reused_existing_claim).toBe(false);
  expect(claimReused(first)).toBe(false);
  const again = (await claim()).result!;
  expect(claimReused(again)).toBe(true);
  expect(again.claim_id).toBe(first.claim_id);
  const year = (await planOf(port, "furgoneta")).find(
    (row) => row.tax_year === scenarioYear,
  )!;
  expect(year).toMatchObject({
    claim_state: "claimed",
    claimable_intervals: [],
  });
  expect(year.claims.filter((found) => found.effective)).toHaveLength(2);
  expect(cents(year.claimed.decimal)).toBe(cents("2880.00"));
  const overlap = (await refused(
    ask({ covered_from: fixtureDay(1, 1), covered_until: fixtureDay(1, 1, 1) }),
  )) as Refused;
  expect(overlap.detail.refusal).toMatchObject({
    code: "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT",
    reason_key: "ledger.actividad_asset.errors.claims_overlap",
  });
  const crossing = await refused(
    ask({ covered_from: fixtureDay(7, 1), covered_until: fixtureDay(2, 1, 1) }),
  );
  expect(crossing.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.covered_interval_outside_tax_year",
  );
  expect(
    claimLanded(await planOf(port, "furgoneta"), {
      tax_year: scenarioYear,
      from: `${scenarioYear}-07-01`,
      until: `${scenarioYear + 1}-01-01`,
      amount: forecast.amount.decimal,
    }),
  ).toBe("saved");
});

test("a free method asks for its amount, and a claim replaces the one it corrects", async () => {
  const port = portOf();
  // The span the register left open on the element whose method leaves the
  // amount to the person.
  const free = SCENARIO_ELEMENTS.find(
    (seed) => seed.id === "impresora",
  )!.rows.find((row) => row.absence === "free_election")!
    .claimable_intervals[0]!;
  const ask = (extra: object) =>
    port.submit(FORECAST, {
      asset_id: "impresora",
      covered_from: free.covered_from,
      covered_until: free.covered_until,
      requested_free_amount: null,
      supersedes_claim_id: null,
      ...extra,
    } as never) as unknown as Promise<unknown>;
  const none = await refused(ask({}));
  expect(none.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.free_amount_required",
  );
  const over = await refused(
    ask({ requested_free_amount: { decimal: "400.00" } }),
  );
  expect(over.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.free_amount_exceeds_remaining_basis",
  );
  const forecast = (
    (await ask({ requested_free_amount: { decimal: "100.00" } })) as {
      result: { forecast: object };
    }
  ).result.forecast;
  const first = (await port.submit(CLAIM, {
    forecast,
    supersedes_claim_id: null,
  } as never)) as unknown as { result: { claim_id: string } };
  const replacing = (await ask({
    requested_free_amount: { decimal: "250.00" },
    supersedes_claim_id: first.result.claim_id,
  })) as { result: { forecast: object } };
  await port.submit(CLAIM, {
    forecast: replacing.result.forecast,
    supersedes_claim_id: first.result.claim_id,
  } as never);
  const rows = await planOf(port, "impresora");
  expect(rows[0]!.claims.map((claim) => claim.effective)).toEqual([
    false,
    true,
  ]);
  expect(rows[0]!.claims[0]!.superseded_by).toBe(rows[0]!.claims[1]!.claim_id);
  expect(rows[0]!.claimed.decimal).toBe("250.00");
});

test("an element made through create is forecast and claimed like a seeded one", async () => {
  const port = portOf();
  await port.submit(
    CREATE,
    (await newRequest(port, NEW_ELEMENT, "made-1"))! as never,
  );
  // The span the register left open on the element it answered for this very
  // request, asked for by its last day covered.
  const open = SCENARIO_CREATIONS.find(
    (creation) => creation.id === "linear_new",
  )!.rows[0]!.claimable_intervals[0]!;
  const forecast = (await port.submit(FORECAST, {
    asset_id: "made-1",
    covered_from: open.covered_from,
    covered_through: dayBefore(open.covered_until),
    requested_free_amount: null,
    supersedes_claim_id: null,
  })) as { result?: { forecast: never } };
  expect(forecast.result?.forecast).toBeDefined();
  const claimed = (await port.submit(CLAIM, {
    forecast: forecast.result!.forecast,
    supersedes_claim_id: null,
  })) as { result?: { claim_result: { reused_existing_claim: boolean } } };
  expect(claimed.result?.claim_result.reused_existing_claim).toBe(false);
  const inspected = await settled<LedgerResult<typeof INSPECT>>(
    port.submit(INSPECT, { asset_id: "made-1" }),
  );
  const claim = (await planOf(port, "made-1"))[0]!.claims[0]!;
  expect(claim.revision_id).toBe(inspected.revisions!.at(-1)!.revision_id);
});

test("a baja over a year no edition covers leaves the minimum unresolved, and says so", async () => {
  const port = portOf();
  const read = await settled<LedgerResult<typeof CALCULATE>>(
    port.submit(CALCULATE, {
      asset_id: "plotter",
      disposal: { ...sale, disposal_date: fixtureDay(6, 30) },
    } as never),
  );
  expect(read.calculation!.minimum).toBeNull();
  expect(
    read.calculation!.findings.filter(
      (finding) => finding.kind === "minimum_unresolved",
    ).length,
  ).toBe(3);
  const seed = SCENARIO_ELEMENTS.find((found) => found.id === "plotter")!;
  expect(seed.disposal!.minimum).toBeNull();
  expect(
    seed.disposal!.years.every((year) => year.minimum_through === null),
  ).toBe(true);
  expect(
    seed
      .disposal!.findings.filter(
        (finding) => finding.kind === "minimum_unresolved",
      )
      .map((finding) => finding.tax_year),
  ).toEqual(
    // The years before the first supported edition, for which no table gives a minimum.
    seed
      .disposal!.years.map((year) => year.tax_year)
      .filter((year) => year < servedSupport.floor),
  );
  // The reduction and the net value stay numbers.
  expect(seed.disposal!.reduction).not.toBeNull();
  expect(seed.disposal!.net_value).not.toBeNull();
});

test("a claim past the registry's last year is refused with the years it can take, and a replayed replaced claim is a conflict", async () => {
  const port = portOf();
  const forecast = (await port.submit(FORECAST, {
    asset_id: "furgoneta",
    covered_from: `${beyondHorizon}-01-01`,
    covered_through: `${beyondHorizon}-12-31`,
    requested_free_amount: null,
    supersedes_claim_id: null,
  })) as { result?: { forecast: never } };
  expect(forecast.result?.forecast).toBeDefined();
  const beyond = await refused(
    port.submit(CLAIM, {
      forecast: forecast.result!.forecast,
      supersedes_claim_id: null,
    }),
  );
  expect(beyond.detail.refusal).toMatchObject({
    code: "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED",
    reason_key: "ledger.actividad_asset.errors.claim_year_beyond_registry",
    reason_facts: [
      { key: "last_admitted_year", value: String(servedSupport.horizon) },
      { key: "tax_year", value: String(beyondHorizon) },
    ],
  });
  // A claim recorded and then replaced cannot be recorded again.
  const span = {
    ...(await planOf(port, "impresora"))[0]!.claimable_intervals[0]!,
  };
  const first = (await port.submit(FORECAST, {
    asset_id: "impresora",
    covered_from: span.covered_from,
    covered_through: span.covered_through,
    requested_free_amount: { decimal: "100.00" },
    supersedes_claim_id: null,
  })) as { result?: { forecast: never } };
  const recorded = (await port.submit(CLAIM, {
    forecast: first.result!.forecast,
    supersedes_claim_id: null,
  })) as { result?: { claim_id: string } };
  const claimId = recorded.result!.claim_id;
  const second = (await port.submit(FORECAST, {
    asset_id: "impresora",
    covered_from: span.covered_from,
    covered_through: span.covered_through,
    requested_free_amount: { decimal: "120.00" },
    supersedes_claim_id: claimId,
  })) as { result?: { forecast: never } };
  expect(
    (
      await port.submit(CLAIM, {
        forecast: second.result!.forecast,
        supersedes_claim_id: claimId,
      })
    ).kind,
  ).toBe("settled");
  const replay = await refused(
    port.submit(CLAIM, {
      forecast: first.result!.forecast,
      supersedes_claim_id: null,
    }),
  );
  expect(replay.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.claim_superseded_replay",
  );
});

test("a later affectation after the element entered service is refused", async () => {
  const port = portOf();
  const late = await refused(
    port.submit(CALCULATE, {
      asset_id: "furgoneta",
      disposal: { ...sale, later_affectation_on: fixtureDay(1, 1, -2) },
    } as never),
  );
  expect(late.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.later_affectation_out_of_order",
  );
});
