import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import {
  forecastRequest,
  handoffRequest,
  staleClaims,
} from "../src/components/ledger/assets/assetWrites";
import {
  factKey,
  fieldsFor,
  formKeyOf,
  FURTHER_PURCHASE,
  FURTHER_SHAPE,
  initialOf,
} from "../src/components/ledger/assets/assetFields";
import {
  answer,
  parseField,
  specOf,
  type FormField,
} from "../src/components/ledger/assets/assetFormValues";
import { type AssetListRow, type FormOptions } from "../src/shell/ledgerSetup";
import {
  changeFieldWord,
  COUNT_ICON,
  COUNT_KINDS,
} from "../src/components/ledger/assets/assetsWords";
import {
  bajaRequest,
  correctRequest,
  createRequest,
} from "../src/components/ledger/assets/assetRevision";
import {
  leftOutNotes,
  type Handoff,
} from "../src/components/ledger/assets/handoffWords";
import {
  nothingOpen,
  recordedMark,
} from "../src/components/ledger/assets/planWords";
import { type JsonObject, type LedgerResult } from "../src/shell/ledger";
import type { Translate } from "../src/shell/strings";
import {
  SCENARIO_ELEMENTS,
  scenarioPaymentId,
} from "../src/dev/assetsRegister";
import {
  servedHandoffOf,
  servedM130PeriodsOf,
  servedSupport,
} from "../src/dev/servedYearAuthority";

import {
  beyondHorizon,
  scenarioYear,
  priorYear,
  OPTIONS,
  CANDIDATES,
  DISPOSE,
  FORECAST,
  CREATE,
  CORRECT,
  INSPECT,
  HANDOFF,
  portOf,
  settled,
  refused,
  listOf,
  planOf,
  eventsOf,
  cents,
  optionsOf,
  newRequest,
  NEW_ELEMENT,
  OUTSIDE_LEDGER_KEYED,
  OUTSIDE_WITH_LATER_PAYMENT,
  firstActivity,
  sale,
  servidorRow,
  words,
  claims,
} from "./support/assetContract";
import { fixtureDay } from "../src/dev/fixtureDates";

// What the backend serves the Assets tab in place of the screens' own rules:
// handoffs, counts, records, and the facts and shapes the options serve.

// ---- What the backend states and the screens no longer work out -------------

test("a forecast states the last day covered, which the backend turns into its boundary; stating neither or two different days is refused", async () => {
  const port = portOf();
  const ask = (extra: object) =>
    port.submit(FORECAST, {
      asset_id: "furgoneta",
      covered_from: fixtureDay(7, 1),
      requested_free_amount: null,
      supersedes_claim_id: null,
      ...extra,
    } as never) as unknown as Promise<{
      result?: { forecast: { amount: { decimal: string } } };
    }>;
  const request = forecastRequest(
    "furgoneta",
    { covered_from: fixtureDay(7, 1), covered_through: fixtureDay(12, 31) },
    null,
  )!;
  expect(request).not.toHaveProperty("covered_until");
  const through = (await ask({ covered_through: request.covered_through }))
    .result!.forecast;
  const until = (await ask({ covered_until: fixtureDay(1, 1, 1) })).result!
    .forecast;
  expect(through).toMatchObject({
    covered_from: fixtureDay(7, 1),
    covered_until: fixtureDay(1, 1, 1),
    covered_through: fixtureDay(12, 31),
  });
  expect(through.amount).toEqual(until.amount);
  // A shorter span is another forecast, and its last day is the one asked.
  const shorter = (await ask({ covered_through: fixtureDay(9, 30) })).result!
    .forecast;
  expect(shorter).toMatchObject({
    covered_until: fixtureDay(10, 1),
    covered_through: fixtureDay(9, 30),
  });
  expect(cents(shorter.amount.decimal)).toBeLessThan(
    cents(through.amount.decimal),
  );
  await expect(ask({})).rejects.toMatchObject({ reason: "invalid" });
  await expect(
    ask({
      covered_until: fixtureDay(1, 1, 1),
      covered_through: fixtureDay(12, 30),
    }),
  ).rejects.toMatchObject({ reason: "invalid" });
});

test("a handoff for a year alone states the Modelo 100 boxes and no Modelo 130 side; a chosen quarter adds it", async () => {
  const port = portOf();
  const alone = handoffRequest(priorYear, "", "es");
  expect(alone).toEqual({ tax_year: priorYear, output_language: "es" });
  const year = await settled<LedgerResult<typeof HANDOFF>>(
    port.submit(HANDOFF, alone),
  );
  expect(year).toMatchObject({ outcome: "succeeded", m130_period: null });
  expect(year.filing_handoff).toMatchObject({
    material_m130: null,
    intangible_m130: null,
  });
  const boxes = servedHandoffOf(priorYear)!.m100;
  expect(year.filing_handoff!.material_m100!.target_casilla_id).toBe(
    boxes.material!.casilla,
  );
  expect(year.filing_handoff!.intangible_m100!.target_casilla_id).toBe(
    boxes.intangible!.casilla,
  );
  const quarter = handoffRequest(priorYear, "2T", "es");
  expect(quarter).toEqual({
    tax_year: priorYear,
    output_language: "es",
    m130_period: "2T",
  });
  const chosen = await settled<LedgerResult<typeof HANDOFF>>(
    port.submit(HANDOFF, quarter),
  );
  expect(chosen.m130_period).toBe("2T");
  expect(chosen.filing_handoff!.material_m130).not.toBeNull();
  // The Modelo 100 boxes are the same with or without the quarter.
  expect(chosen.filing_handoff!.material_m100).toEqual(
    year.filing_handoff!.material_m100,
  );
});

test("the vehicle declaration is stated, with no question, for a table class the options say requires one, and nothing is drawn for any other", async () => {
  const port = portOf();
  const options = (await optionsOf(port, "material")) as FormOptions;
  const classKey = factKey(["authority_class_key"]);
  const drawn = (chosen: string, assetKind = "material") =>
    fieldsFor(
      {
        kind: "element",
        row: null,
        descriptor: null,
        revision: null,
        tokens: () => [],
        options,
      },
      { asset_kind: assetKind, method: "linear", [classKey]: chosen },
    ).filter((found) => found.key.startsWith("vehicle_"));
  const requires = options.table_groups.filter(
    (group) => group.requires_vehicle_declaration,
  );
  const not = options.table_groups.filter(
    (group) => !group.requires_vehicle_declaration,
  );
  expect(requires.length).toBeGreaterThan(0);
  expect(not.length).toBeGreaterThan(0);
  for (const group of requires) {
    const fields = drawn(group.class_key);
    expect(fields.map((found) => found.key)).not.toContain("vehicle_declared");
    // The declaration opens as required: its category and use are not optional.
    for (const key of ["vehicle_category", "vehicle_private_use"])
      expect(
        fields.find((found) => found.key === key)?.required,
        `${group.class_key} ${key}`,
      ).toBe(true);
  }
  for (const group of not)
    expect(drawn(group.class_key), group.class_key).toEqual([]);
  // No class chosen, or one the options do not list, draws nothing.
  expect(drawn("")).toEqual([]);
  expect(drawn("not-a-class")).toEqual([]);
  // The class the options serve decides alone; the kind does not gate it.
  expect(drawn(requires[0]!.class_key, "intangible")).not.toEqual([]);
});

test("a baja form offers exactly the reasons the options serve, each worded by the key served with it", async () => {
  const port = portOf();
  const reasonsOf = (options: FormOptions | null) =>
    fieldsFor(
      {
        kind: "baja",
        row: null,
        descriptor: null,
        revision: null,
        tokens: () => [],
        options,
      },
      {},
    ).find((found) => found.key === "reason")!.choices;
  for (const kind of ["material", "intangible"]) {
    const options = (await optionsOf(port, kind)) as FormOptions;
    const reasons = reasonsOf(options);
    expect(options.disposal_reasons.length).toBeGreaterThan(0);
    expect(reasons.map((choice) => [choice.token, choice.word])).toEqual(
      options.disposal_reasons.map((item) => [item.reason, item.label_key]),
    );
    expect(reasons.map((choice) => choice.token)).not.toContain("donation");
  }
  // Until the options are read, no reason is offered.
  expect(reasonsOf(null)).toEqual([]);
});

test("each plan claim states the verdict the timeline states of the same claim", async () => {
  const port = portOf();
  for (const row of await listOf(port)) {
    const verdicts = new Map(
      (await eventsOf(port, row.asset_id))
        .filter((event) => event.claim !== null)
        .map((event) => [event.record_id, event.claim!] as const),
    );
    for (const year of await planOf(port, row.asset_id))
      for (const claim of year.claims) {
        const found = verdicts.get(claim.claim_id);
        expect(claim.matches_current_schedule, claim.claim_id).toBe(
          found?.matches_current_schedule ?? true,
        );
        expect(claim.stale_reason, claim.claim_id).toBe(
          found?.stale_reason ?? null,
        );
        // A verdict names its reason exactly when the claim no longer matches.
        expect(claim.stale_reason === null).toBe(
          claim.matches_current_schedule,
        );
      }
  }
  const stale = staleClaims(await planOf(port, "servidor"));
  expect(stale.length).toBeGreaterThan(0);
  for (const { claim } of stale) {
    expect(claim.effective).toBe(true);
    expect(claim.stale_reason).toBe("revision_changed");
  }
});

test("a changed fact on the timeline is worded by the key the backend served for it, and an unkeyed one reads as the generic word", async () => {
  const port = portOf();
  const t = words({
    "ledger.actividad_asset.field.serial_number": "Serial number",
    "desktop.ledger.assets.field.other": "Other detail",
  });
  const changes = (await eventsOf(port, "furgoneta")).flatMap(
    (event) => event.changes,
  );
  expect(changes.length).toBeGreaterThan(0);
  for (const found of changes)
    expect(found.field_key, found.field).toBe(
      `ledger.actividad_asset.field.${found.field}`,
    );
  expect(changeFieldWord(t, "ledger.actividad_asset.field.serial_number")).toBe(
    "Serial number",
  );
  // No key, or a key the catalogue lacks, is never drawn raw.
  expect(changeFieldWord(t, null)).toBe("Other detail");
  expect(changeFieldWord(t, "ledger.actividad_asset.field.invented")).toBe(
    "Other detail",
  );
  expect(changeFieldWord(t, "tui.ledger.activity_asset.plan")).toBe(
    "Other detail",
  );
  // The reference of a purchase outside the ledger is shown; the system's own identities are not.
  const keyed = portOf();
  const made = await newRequest(keyed, OUTSIDE_LEDGER_KEYED, "made-keys");
  await keyed.submit(CREATE, made! as never);
  const fields = (await eventsOf(keyed, "made-keys")).flatMap((event) =>
    event.changes.map((found) => found.field),
  );
  expect(fields).toContain("acquisition.invoice_evidence_id");
  expect(fields).not.toContain("acquisition.observed_transaction_id");
  expect(fields).not.toContain("acquisition.evidence_fingerprint");
  expect(fields).not.toContain("asset_id");
  expect(fields).not.toContain("revision_number");
});

test("a handoff says what it leaves out as the backend served it, by the elements' names and never by an id", async () => {
  const port = portOf();
  const handoff = (
    await settled<LedgerResult<typeof HANDOFF>>(
      port.submit(HANDOFF, {
        tax_year: priorYear,
        output_language: "en",
        m130_period: "4T",
      }),
    )
  ).filing_handoff!;
  const said = leftOutNotes(handoff);
  // The intervals Modelo 100 leaves out come first, then each reason a
  // Modelo 130 amount leaves elements out, as the backend states them.
  expect(said).toEqual([
    ...handoff.m100_gaps.flatMap((gap) => gap.words ?? []),
    ...handoff.left_out.map((entry) => entry.words),
  ]);
  expect(said.length).toBeGreaterThan(0);
  for (const sentence of said)
    for (const id of SCENARIO_ELEMENTS.map((seed) => seed.id))
      expect(sentence).not.toContain(id);
  // A handoff that leaves nothing out says nothing.
  expect(
    leftOutNotes({
      material_m100: claims("0208"),
      intangible_m100: claims("0227"),
      m100_gaps: [],
      material_m130: null,
      intangible_m130: null,
      left_out: [],
    }),
  ).toEqual([]);
  // An interval the backend could not say whole is not drawn.
  expect(
    leftOutNotes({
      ...handoff,
      m100_gaps: handoff.m100_gaps.map((gap) => ({ ...gap, words: null })),
      left_out: [],
    }),
  ).toEqual([]);
});

// ---- What the backend serves now ----------------------------------------------

test("the list serves the year a dotación form opens on, from what each element still has to record", async () => {
  const port = portOf();
  for (const row of await listOf(port)) {
    const open = (await planOf(port, row.asset_id))
      .filter((year) => year.claimable_intervals.length > 0)
      .map((year) => year.tax_year);
    // The latest year up to the scenario's with something left to record,
    // else the earliest later one, else none.
    const elapsed = open.filter((year) => year <= scenarioYear);
    const expected =
      elapsed.length > 0
        ? Math.max(...elapsed)
        : open.length > 0
          ? Math.min(...open)
          : null;
    expect(row.default_claim_year, row.asset_id).toBe(expected);
  }
});

test("every kind of count the list serves has a pill with a glyph of its own, and each year is counted once", async () => {
  const rows = await listOf(portOf());
  expect([...COUNT_KINDS].sort()).toEqual(
    Object.keys(rows[0]!.findings).sort(),
  );
  expect(new Set(COUNT_KINDS.map((kind) => COUNT_ICON[kind])).size).toBe(
    COUNT_KINDS.length,
  );
  // Years with no official tables are counted under their own kind, and not
  // again as missing.
  const compressor = rows.find((row) => row.asset_id === "compresor")!;
  expect(compressor.findings.without_tables).toBeGreaterThan(0);
  expect(compressor.findings.missing).toBe(0);
  for (const row of rows) {
    const plan = await planOf(portOf(), row.asset_id);
    const stopped = (absence: string) =>
      plan.filter((year) => year.absence === absence).length;
    expect(row.findings.incomplete, row.asset_id).toBe(stopped("incomplete"));
    expect(row.findings.conflict, row.asset_id).toBe(stopped("conflict"));
    expect(row.findings.unsupported, row.asset_id).toBe(stopped("unsupported"));
    expect(row.findings.without_tables, row.asset_id).toBe(
      stopped("edition_unavailable"),
    );
  }
});

test("a record says what it did and the day it takes effect, and a replaced dotación is no longer in effect", async () => {
  const port = portOf();
  const inspect = async (id: string) =>
    (
      await settled<LedgerResult<typeof INSPECT>>(
        port.submit(INSPECT, { asset_id: id }),
      )
    ).revisions!.at(-1)!;
  const last = async (id: string) => (await eventsOf(port, id)).at(-1)!;
  // An element is created from the day it entered service.
  const first = (await eventsOf(port, "taladro"))[0]!;
  expect(first).toMatchObject({
    event_kind: "created",
    effect_date: servidorLike("taladro").in_service_date,
  });
  // A baja takes effect on its own day, changed on its new one, and removing
  // it on the day it had.
  const baja = { ...sale, disposal_date: fixtureDay(9, 30) };
  await settled(
    port.submit(DISPOSE, { asset_id: "taladro", disposal: baja } as never),
  );
  expect(await last("taladro")).toMatchObject({
    kind: "baja",
    event_kind: "baja_recorded",
    effect_date: fixtureDay(9, 30),
  });
  const moved = bajaRequest(await inspect("taladro"), {
    ...baja,
    disposal_date: fixtureDay(6, 30),
  })!;
  await settled(port.submit(CORRECT, moved as never));
  expect(await last("taladro")).toMatchObject({
    event_kind: "baja_changed",
    effect_date: fixtureDay(6, 30),
  });
  expect(
    (await listOf(port)).find((row) => row.asset_id === "taladro"),
  ).toMatchObject({ pending_applies: false });
  await settled(
    port.submit(CORRECT, bajaRequest(await inspect("taladro"), null)! as never),
  );
  expect(await last("taladro")).toMatchObject({
    event_kind: "baja_removed",
    effect_date: fixtureDay(6, 30),
  });
  expect(
    (await listOf(port)).find((row) => row.asset_id === "taladro"),
  ).toMatchObject({ pending_applies: true });

  // A correction takes effect from the day of service; one that records a
  // dotación again replaces it, which is then no longer in effect.
  const base = await inspect("servidor");
  const options = (await optionsOf(port)) as FormOptions;
  const context = {
    kind: "correction" as const,
    row: servidorRow(),
    descriptor: null,
    revision: base.revision,
    tokens: () => [],
    options,
  };
  const initial = initialOf(context, fieldsFor(context, {}));
  const draft = { ...initial, basis_amount: "3600" };
  const claim = (await planOf(port, "servidor"))[0]!.claims[0]!;
  const request = correctRequest(
    answer(fieldsFor(context, draft), draft, initial).values,
    { assetId: "servidor", regime: null, candidate: null, base, options },
    [claim.claim_id],
  )!;
  await settled(port.submit(CORRECT, request as never));
  const events = await eventsOf(port, "servidor");
  const corrected = events.find((event) => event.event_kind === "corrected")!;
  expect(corrected.effect_date).toBe(servidorRow().in_service_date);
  const replaced = events.filter(
    (event) => event.event_kind === "claim_replaced",
  );
  expect(replaced).toHaveLength(1);
  const year = (await planOf(port, "servidor"))[0]!.tax_year;
  expect(replaced[0]!.claim).toMatchObject({
    in_effect: true,
    tax_year: year,
    matches_current_schedule: true,
  });
  expect(replaced[0]!.claim!.covered_through).toBe(claim.covered_through);
  expect(
    events.find((event) => event.record_id === claim.claim_id)!.claim,
  ).toMatchObject({
    in_effect: false,
    tax_year: year,
    covered_from: claim.covered_from,
    covered_through: claim.covered_through,
    matches_current_schedule: true,
    stale_reason: null,
  });
  // Every record of every element says what it did.
  for (const id of ["furgoneta", "servidor", "camara"])
    for (const event of await eventsOf(port, id))
      expect(event.event_kind, `${id} ${event.sequence}`).not.toBeNull();
});

function servidorLike(id: string): AssetListRow {
  return SCENARIO_ELEMENTS.find((seed) => seed.id === id)!.list;
}

test("the facts of a basis stage and of an opening status are the ones the options serve, and a correction drops what its stage no longer states", async () => {
  const port = portOf();
  const options = (await optionsOf(port)) as FormOptions;
  const context = {
    kind: "element" as const,
    row: null,
    descriptor: null,
    revision: null,
    tokens: (family: string) => (family === "ownership_mode" ? ["sole"] : []),
    options,
  };
  const drawn = (draft: Record<string, string>) =>
    fieldsFor(context, draft).map((found) => found.key);
  const everyStageFact = new Set(options.basis_stages.flatMap((s) => s.facts));
  for (const stage of options.basis_stages) {
    const keys = drawn({ basis_stage: stage.stage });
    for (const name of everyStageFact)
      expect(keys.includes(name), `${stage.stage} ${name}`).toBe(
        stage.facts.includes(name),
      );
  }
  const everyOpeningFact = new Set(
    options.opening_statuses.flatMap((s) => s.facts),
  );
  for (const status of options.opening_statuses) {
    const keys = drawn({ opening_status: status.status });
    for (const name of everyOpeningFact)
      expect(
        keys.includes(formKeyOf(`opening_history.${name}`)),
        `${status.status} ${name}`,
      ).toBe(status.facts.includes(name));
  }
  // The date a building was built is a fact of an element bought used, in
  // whatever stage its basis is.
  for (const stage of options.basis_stages) {
    expect(
      drawn({ basis_stage: stage.stage, acquired_condition: "used" }),
    ).toContain("building_construction_date");
    expect(
      drawn({ basis_stage: stage.stage, acquired_condition: "new" }),
    ).not.toContain("building_construction_date");
  }
  expect(drawn({})).not.toContain("building_construction_date");

  // A correction that moves the basis to another stage states the facts of
  // that stage and none of the others', and the property flag the options
  // serve for it.
  const base = (
    await settled<LedgerResult<typeof INSPECT>>(
      port.submit(INSPECT, { asset_id: "servidor" }),
    )
  ).revisions!.at(-1)!;
  const correction = {
    ...context,
    kind: "correction" as const,
    row: servidorRow(),
    revision: base.revision,
  };
  const initial = initialOf(correction, fieldsFor(correction, {}));
  const draft = {
    ...initial,
    basis_stage: "taxpayer_owned",
    business_use_share: "0.6",
  };
  const request = correctRequest(
    answer(fieldsFor(correction, draft), draft, initial).values,
    { assetId: "servidor", regime: null, candidate: null, base, options },
    [],
  )!;
  const basis = request.revision.basis as Record<string, unknown>;
  expect(basis).toMatchObject({
    stage: "taxpayer_owned",
    is_property: false,
    business_use_share: { decimal: "0.6" },
  });
  for (const name of everyStageFact)
    if (name !== "business_use_share") expect(basis).not.toHaveProperty(name);
  // A missing opening history states none of the facts a known one does.
  const startMissing = { ...initial, opening_status: "missing" };
  const missing = correctRequest(
    answer(fieldsFor(correction, startMissing), startMissing, initial).values,
    { assetId: "servidor", regime: null, candidate: null, base, options },
    [],
  )!;
  const opening = missing.revision.opening_history as Record<string, unknown>;
  expect(opening.status).toBe("missing");
  for (const name of everyOpeningFact) expect(opening).not.toHaveProperty(name);
});

test("an element bought outside the ledger can own a later ledger payment, which the request carries as the backend takes it", async () => {
  const port = portOf();
  const options = (await optionsOf(port)) as FormOptions;
  const candidates = (
    await settled<LedgerResult<typeof CANDIDATES>>(port.submit(CANDIDATES, {}))
  ).candidates!;
  const context = {
    kind: "element" as const,
    row: null,
    descriptor: null,
    revision: null,
    tokens: () => [],
    options,
  };
  const outside = {
    ...NEW_ELEMENT,
    acquisition_shape: "acquired_outside_ledger",
    acquisition: "",
    declared_acquisition_date: fixtureDay(1, 10),
    declared_activity: firstActivity,
    acquisition_reference: "invoice held at the office",
  };
  const keys = (draft: Record<string, string>) =>
    fieldsFor(context, draft).map((found) => found.key);
  // Offered for an element bought outside the ledger and for none other; what
  // the payment is asked once one is picked.
  expect(keys(NEW_ELEMENT)).not.toContain(FURTHER_PURCHASE);
  expect(keys(outside)).toContain(FURTHER_PURCHASE);
  expect(keys(outside)).not.toContain(FURTHER_SHAPE);
  expect(
    keys({ ...outside, [FURTHER_PURCHASE]: scenarioPaymentId("t-silla") }),
  ).toContain(FURTHER_SHAPE);
  const build = (draft: Record<string, string>, id: string) => {
    const stated = answer(fieldsFor(context, draft), draft, null);
    return createRequest(stated.values, {
      assetId: id,
      regime: options.regime,
      candidate: null,
      further:
        candidates.find(
          (found) => found.transaction_id === draft[FURTHER_PURCHASE],
        ) ?? null,
      base: null,
      options,
    })!;
  };
  // Without a payment the element states none.
  expect(build(outside, "made-5").revision.further_acquisitions).toEqual([]);
  const withPayment = OUTSIDE_WITH_LATER_PAYMENT;
  const request = build(withPayment, "made-6");
  // The lineage names the payment the draft picked, the shape it chose, and
  // the invoice the ledger holds of that payment, as the register serves it.
  const later = candidates.find(
    (found) => found.transaction_id === withPayment[FURTHER_PURCHASE],
  )!;
  expect(request.revision.further_acquisitions).toEqual([
    {
      shape: withPayment[FURTHER_SHAPE],
      lineage: {
        observed_transaction_id: later.transaction_id,
        invoice_evidence_id: later.invoice_evidence_id ?? "",
        evidence_fingerprint: later.evidence_fingerprint,
      },
    },
  ]);
  expect((await port.submit(CREATE, request as never)).kind).toBe("settled");
  // The payment is the element's now, and no longer on offer.
  const left = (
    await settled<LedgerResult<typeof CANDIDATES>>(port.submit(CANDIDATES, {}))
  ).candidates!;
  expect(
    left.some(
      (found) => found.transaction_id === withPayment[FURTHER_PURCHASE],
    ),
  ).toBe(false);
  // A payment the ledger does not hold, and one named twice, are refused.
  const unknown = build(withPayment, "made-7");
  (unknown.revision.further_acquisitions as { lineage: object }[])[0]!.lineage =
    {
      observed_transaction_id: "t-nowhere",
      invoice_evidence_id: "",
      evidence_fingerprint: null,
    };
  expect(
    (await refused(port.submit(CREATE, unknown as never))).detail.refusal,
  ).toMatchObject({
    reason_key: "ledger.actividad_asset.errors.acquisition_transaction_missing",
  });
  const twice = build(withPayment, "made-8");
  const row = (twice.revision.further_acquisitions as JsonObject[])[0]!;
  twice.revision.further_acquisitions = [row, row];
  expect(
    (await refused(port.submit(CREATE, twice as never))).detail.refusal
      .reason_key,
  ).toBe("ledger.actividad_asset.errors.acquisition_row_named_twice");
});

test("the Modelo 130 periods are the ones the options serve for the year", async () => {
  const port = portOf();
  for (const year of [
    servedSupport.floor,
    servedSupport.horizon,
    beyondHorizon,
  ]) {
    const read = await settled<LedgerResult<typeof OPTIONS>>(
      port.submit(OPTIONS, { asset_kind: "material", tax_year: year }),
    );
    expect(read.options!.m130_periods, String(year)).toEqual(
      servedM130PeriodsOf(year),
    );
  }
});

/** A translator over a table of strings, filling `{name}` as the catalogue does. */
const wordsOf = (strings: Record<string, string>, locale = "en"): Translate =>
  Object.assign(
    (key: string, values?: Record<string, string | number>) =>
      (strings[key] ?? key).replace(/\{(\w+)\}/g, (_, name: string) =>
        String(values?.[name] ?? `{${name}}`),
      ),
    { locale },
  ) as unknown as Translate;

test("a year draws nothing recorded where it applies and does not apply where the plan says so, never by its absence", async () => {
  const port = portOf();
  let applying = 0;
  let notApplying = 0;
  for (const seed of SCENARIO_ELEMENTS)
    for (const row of await planOf(port, seed.id)) {
      expect(recordedMark(row), `${seed.id} ${row.tax_year}`).toBe(
        row.applies ? "nothing_recorded" : "not_applicable",
      );
      if (row.applies) applying += 1;
      else notApplying += 1;
      // A year with a span open applies, whatever its absence is.
      if (row.claimable_intervals.length > 0) expect(row.applies).toBe(true);
    }
  expect(applying).toBeGreaterThan(0);
  expect(notApplying).toBeGreaterThan(0);
  expect(recordedMark({ applies: false })).toBe("not_applicable");
  expect(recordedMark({ applies: true })).toBe("nothing_recorded");
});

test("a year with nothing open says the plan's own reason, the absence's when the refusal gives none, and never blank, each with the sentence for the entry to fill in where one is served", () => {
  const t = wordsOf({
    "desktop.ledger.assets.plan.claimable_none": "Nothing left to record",
  });
  const none = {
    claimable_intervals: [],
    claimable_refusal_words: null,
    claimable_refusal_remedy_words: null,
    absence_reason_words: null,
    absence_remedy_words: null,
  };
  // The sentences arrive said; the window picks between them and adds none.
  const refusal = nothingOpen(t, {
    ...none,
    claimable_refusal_words: "The refusal, said.",
    claimable_refusal_remedy_words: "Where to fill the refusal in.",
    absence_reason_words: "The absence, said.",
  })!;
  expect(refusal.why).toBe("The refusal, said.");
  // The remedy is the one served with the sentence that is said.
  expect(refusal.remedyWords).toBe("Where to fill the refusal in.");
  expect(
    nothingOpen(t, {
      ...none,
      absence_reason_words: "The absence, said.",
      absence_remedy_words: "Where to fill the absence in.",
    }),
  ).toEqual({
    why: "The absence, said.",
    remedyWords: "Where to fill the absence in.",
  });
  expect(nothingOpen(t, none)).toEqual({
    why: "Nothing left to record",
    remedyWords: null,
  });
  expect(
    nothingOpen(t, {
      ...none,
      claimable_intervals: [
        {
          covered_from: fixtureDay(1, 1),
          covered_until: fixtureDay(1, 1, 1),
          covered_through: fixtureDay(12, 31),
        },
      ],
    }),
  ).toBeNull();
});

test("the handoff marks an amount that leaves elements out with the sentence the backend served for it", async () => {
  const port = portOf();
  const handoff = (
    await settled<LedgerResult<typeof HANDOFF>>(
      port.submit(HANDOFF, {
        tax_year: priorYear,
        output_language: "en",
        m130_period: "4T",
      }),
    )
  ).filing_handoff!;
  for (const projection of [handoff.material_m130, handoff.intangible_m130]) {
    if (projection === null) continue;
    // A sentence is served exactly where some element could not be worked out.
    expect(typeof projection.partial_words === "string").toBe(
      projection.unavailable_asset_ids.length > 0,
    );
  }
  // Each reason an amount leaves elements out is one entry, naming the
  // elements it concerns by id for acting on and saying them in words.
  const reasons = handoff.left_out.map((entry) => entry.reason);
  expect(new Set(reasons).size).toBe(reasons.length);
  for (const entry of handoff.left_out) {
    expect(entry.asset_ids.length).toBeGreaterThan(0);
    expect(entry.words.length).toBeGreaterThan(0);
  }
});

// ---- What the backend serves in place of the screens' own rules ----------------

test("the facts of a condition are drawn from the conditions the options serve, so a fact no condition lists is never asked", async () => {
  const port = portOf();
  const options = (await optionsOf(port, "material")) as FormOptions;
  const keys = (served: FormOptions, draft: Record<string, string>) =>
    fieldsFor(
      {
        kind: "element",
        row: null,
        descriptor: null,
        revision: null,
        tokens: () => [],
        options: served,
      },
      { method: "linear", ...draft },
    ).map((found) => found.key);
  const price = factKey(["used_original_price", "original_price"]);
  const used = options.acquired_conditions.find(
    (found) => found.condition === "used",
  )!;
  expect(used.facts).toEqual([
    "building_construction_date",
    "used_original_price",
  ]);
  expect(keys(options, { acquired_condition: "used" })).toEqual(
    expect.arrayContaining(["building_construction_date", price]),
  );
  expect(keys(options, { acquired_condition: "new" })).not.toContain(price);
  expect(keys(options, { acquired_condition: "new" })).not.toContain(
    "building_construction_date",
  );
  // The options alone decide: a used condition that lists no fact asks none.
  const bare: FormOptions = {
    ...options,
    acquired_conditions: options.acquired_conditions.map((found) => ({
      ...found,
      facts: [],
    })),
  };
  expect(keys(bare, { acquired_condition: "used" })).toContain(price);
  expect(keys(bare, { acquired_condition: "used" })).not.toContain(
    "building_construction_date",
  );
  // A fact only the used condition states is left out of a new element's
  // request, even where it was typed before the condition changed.
  const constructed = fixtureDay(1, 1, -25);
  const request = (await newRequest(
    port,
    {
      ...NEW_ELEMENT,
      acquired_condition: "new",
      building_construction_date: constructed,
    },
    "made-cond",
  ))!;
  expect(request.revision).not.toHaveProperty("building_construction_date");
  const built = (await newRequest(
    port,
    {
      ...NEW_ELEMENT,
      acquired_condition: "used",
      building_construction_date: constructed,
    },
    "made-cond-2",
  ))!;
  expect(built.revision.building_construction_date).toBe(constructed);
});

test("the shapes of a later payment are the ones the options serve", async () => {
  const port = portOf();
  const options = (await optionsOf(port, "material")) as FormOptions;
  expect(options.further_acquisition_shapes).toEqual([
    "split_payment",
    "ancillary_cost",
  ]);
  const choices = (served: readonly string[]) =>
    fieldsFor(
      {
        kind: "element",
        row: null,
        descriptor: null,
        revision: null,
        tokens: () => [],
        options: { ...options, further_acquisition_shapes: [...served] },
      },
      {
        ...NEW_ELEMENT,
        acquisition_shape: "acquired_outside_ledger",
        [FURTHER_PURCHASE]: scenarioPaymentId("t-silla"),
      },
    )
      .find((found) => found.key === FURTHER_SHAPE)!
      .choices.map((choice) => choice.token);
  expect(choices(options.further_acquisition_shapes)).toEqual([
    "split_payment",
    "ancillary_cost",
  ]);
  expect(choices(["ancillary_cost"])).toEqual(["ancillary_cost"]);
});

test("a baja that has not yet left service keeps its pending amount, and one that has leaves none", async () => {
  const port = portOf();
  await settled(
    port.submit(DISPOSE, {
      asset_id: "furgoneta",
      disposal: { ...sale, disposal_date: fixtureDay(3, 31, 1) },
    } as never),
  );
  const future = (await listOf(port)).find(
    (found) => found.asset_id === "furgoneta",
  )!;
  expect(future.disposal).not.toBeNull();
  expect(future.pending_applies).toBe(true);
  await settled(
    port.submit(DISPOSE, {
      asset_id: "camara",
      disposal: sale,
    } as never),
  );
  const gone = (await listOf(port)).find(
    (found) => found.asset_id === "camara",
  )!;
  expect(gone.pending_applies).toBe(false);
});

test("the handoff names each box in the language asked, tells the two Modelo 130 rows apart by name and kind, and ends each gap on its last day", async () => {
  const port = portOf();
  const read = async (language: string) =>
    (
      await settled<LedgerResult<typeof HANDOFF>>(
        port.submit(HANDOFF, {
          tax_year: priorYear,
          output_language: language,
          m130_period: "4T",
        } as never),
      )
    ).filing_handoff!;
  const english = await read("en");
  const spanish = await read("es");
  expect(english.material_m100!.box_name).not.toBeNull();
  expect(english.material_m100!.box_name).not.toBe(
    spanish.material_m100!.box_name,
  );
  const [material, intangible] = [
    english.material_m130!,
    english.intangible_m130!,
  ];
  expect([material.asset_kind, intangible.asset_kind]).toEqual([
    "material",
    "intangible",
  ]);
  expect(material.target_casilla_id).toBe(intangible.target_casilla_id);
  expect(material.box_name).not.toBe(intangible.box_name);
  expect(english.m100_gaps.length).toBeGreaterThan(0);
  for (const gap of english.m100_gaps)
    expect(gap.covered_through < gap.covered_until).toBe(true);
});

test("a typed text of any length is the backend's to refuse, not the form's", () => {
  const description: FormField = {
    key: "description",
    label_key: "desktop.ledger.assets.field.description",
    control: "text",
    required: false,
    choices: [],
  };
  const long = "x".repeat(5000);

  expect(specOf(description)).toEqual({ kind: "text" });
  expect(parseField(description, long)).toEqual({ kind: "value", value: long });
  expect(parseField(description, "a\nb").kind).toBe("refused");
});

test("a kind the edition has no box for draws no box, and says which element goes undeclared as the backend served it", () => {
  const served = "The interval, said by the backend.";
  const handoff: Handoff = {
    material_m100: null,
    intangible_m100: null,
    m100_gaps: [
      {
        asset_id: "asset-aaa",
        kind: "box_unbound",
        covered_from: fixtureDay(1, 1, -1),
        covered_through: fixtureDay(12, 31, -1),
        covered_until: fixtureDay(1, 1),
        accrued: null,
        words: served,
        words_language: "en",
      },
    ],
    material_m130: null,
    intangible_m130: null,
    left_out: [],
  };

  expect(leftOutNotes(handoff)).toEqual([served]);
});
