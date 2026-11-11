import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import {
  claimLanded,
  correctionLanded,
  describeRequest,
  descriptorLanded,
  elementLanded,
  forecastRequest,
  INCOMPLETE,
  missingLabels,
  refusalOf,
  refusalWord,
  claimInTheWay,
  CLAIMS_OVERLAP,
  viewOf,
} from "../src/components/ledger/assets/assetWrites";
import {
  claimFields,
  claimSpans,
  factKey,
  factsOf,
  fieldsFor,
  initialOf,
  undrawableFacts,
  unlabelledFacts,
} from "../src/components/ledger/assets/assetFields";
import {
  answer,
  parseField,
  type FormField,
} from "../src/components/ledger/assets/assetFormValues";
import { type AssetListRow, type FormOptions } from "../src/shell/ledgerSetup";
import {
  ASSET_FAMILY,
  keyedText,
  refusalText,
  tokenWord,
} from "../src/components/ledger/assets/assetsWords";
import {
  bajaRequest,
  correctRequest,
} from "../src/components/ledger/assets/assetRevision";
import { changeValueText } from "../src/components/ledger/assets/planWords";
import type { SetupCall } from "../src/components/ledger/setup/setupModel";
import { type LedgerResult } from "../src/shell/ledger";
import type { Translate } from "../src/shell/strings";
import {
  ACQUIRED_CONDITIONS,
  ACQUISITION_SHAPES,
  BASIS_STAGES,
  DECLARED_ACTIVITIES,
  DISPOSAL_REASONS,
  FURTHER_ACQUISITION_SHAPES,
  METHOD_FACTS,
  OPENING_STATUSES,
  REGISTER_DEFAULT_YEAR,
  REGISTER_YEARS,
  SCENARIO_ELEMENTS,
  TABLE_GROUPS,
} from "../src/dev/assetsRegister";
import {
  servedEditionOf,
  servedM130PeriodsOf,
  servedSupport,
} from "../src/dev/servedYearAuthority";

import {
  scenarioYear,
  priorYear,
  PLAN,
  OPTIONS,
  CANDIDATES,
  DISPOSE,
  FORECAST,
  CREATE,
  CORRECT,
  INSPECT,
  portOf,
  change,
  settled,
  type Refused,
  refused,
  registerOf,
  listOf,
  planOf,
  optionsOf,
  newRequest,
  servidorRow,
  words,
  NEW_ELEMENT,
  OUTSIDE_LEDGER,
  SHIFT_HOURS,
  VEHICLE_ELEMENT,
  WHOLE_PROPERTY,
} from "./support/assetContract";
import { fixtureDay } from "../src/dev/fixtureDates";

// The Assets tab's forms: typed text, the requests they make, how a write
// ended, the words they draw and the facts they state.

// ---- Typed text, requests and how a write ended ------------------------------

const idle: SetupCall<unknown> = {
  kind: "failed",
  code: "unavailable",
  reason: null,
};

test("typed text becomes the values of its control, and nothing typed is not zero", () => {
  const field = (control: FormField["control"]): FormField => ({
    key: "k",
    label_key: "l",
    control,
    required: false,
    choices: [],
  });
  expect(parseField(field("amount"), "12.5")).toEqual({
    kind: "value",
    value: { decimal: "12.5" },
  });
  expect(parseField(field("amount"), "")).toEqual({ kind: "empty" });
  expect(parseField(field("amount"), "1,2,3").kind).toBe("refused");
  expect(parseField(field("date"), fixtureDay(2, 30)).kind).toBe("refused");
  expect(parseField(field("date"), fixtureDay(2, 28))).toEqual({
    kind: "value",
    value: fixtureDay(2, 28),
  });
  expect(parseField(field("whole"), "12")).toEqual({
    kind: "value",
    value: 12,
  });
  expect(parseField(field("whole"), "1e3").kind).toBe("refused");
  expect(parseField(field("choice"), "")).toEqual({ kind: "empty" });
});

test("a correction states only what changed from the record, and an emptied field is stated cleared or named", () => {
  const row = servidorRow() as AssetListRow;
  const context = {
    kind: "correction" as const,
    row,
    descriptor: null,
    revision: SCENARIO_ELEMENTS.find(
      (seed) => seed.id === "servidor",
    )!.revisions.at(-1)!.revision as never,
    tokens: () => [],
    options: null,
  };
  const initial = initialOf(context, fieldsFor(context, {}));
  const fields = fieldsFor(context, initial);
  expect(initial).toMatchObject({
    method: row.method,
    basis_amount: "3800",
    in_service_date: row.in_service_date,
  });
  expect(answer(fields, initial, initial).values).toEqual({});
  const changed = answer(fields, { ...initial, basis_amount: "3600" }, initial);
  expect(changed.values).toEqual({ basis_amount: { decimal: "3600" } });
  // A fact the record cannot do without is named, not stated and not dropped.
  const emptied = answer(fields, { ...initial, basis_amount: "" }, initial);
  expect(emptied.values).toEqual({});
  expect(emptied.cleared).toEqual(["basis_amount"]);
  // A fact it can do without is stated as cleared.
  const held = { ...initial, residual_value: "10" };
  expect(answer(fields, { ...held, residual_value: "" }, held).values).toEqual({
    residual_value: null,
  });
  // A full form states every field, null where nothing was typed.
  const adding = fieldsFor({
    kind: "element",
    row: null,
    descriptor: null,
    revision: null,
    tokens: () => [],
    options: null,
  });
  expect(Object.keys(answer(adding, {}, null).values)).toEqual(
    adding.map((found) => found.key),
  );
});

test("a cleared fact is taken out of the corrected revision, and the baja the revision records travels with it", async () => {
  const port = portOf();
  const options = (await optionsOf(port)) as FormOptions;
  const inspect = async (id: string) =>
    (
      await settled<LedgerResult<typeof INSPECT>>(
        port.submit(INSPECT, { asset_id: id }),
      )
    ).revisions!.at(-1)!;
  const base = await inspect("servidor");
  const context = {
    kind: "correction" as const,
    row: servidorRow(),
    descriptor: null,
    revision: base.revision,
    tokens: () => [],
    options,
  };
  const initial = initialOf(context, fieldsFor(context, {}));
  // Set a residual value, then clear it.
  const withResidual = { ...initial, residual_value: "10" };
  const first = correctRequest(
    answer(fieldsFor(context, withResidual), withResidual, initial).values,
    { assetId: "servidor", regime: null, candidate: null, base, options },
    [],
  )!;
  expect(first.revision).toMatchObject({ residual_value: { decimal: "10" } });
  expect(
    (await settled<{ outcome: string }>(port.submit(CORRECT, first as never)))
      .outcome,
  ).toBe("succeeded");
  const second = await inspect("servidor");
  const again = {
    ...context,
    revision: second.revision,
  };
  const start = initialOf(again, fieldsFor(again, {}));
  expect(start.residual_value).toBe("10");
  const cleared = correctRequest(
    answer(
      fieldsFor(again, { ...start, residual_value: "" }),
      {
        ...start,
        residual_value: "",
      },
      start,
    ).values,
    {
      assetId: "servidor",
      regime: null,
      candidate: null,
      base: second,
      options,
    },
    [],
  )!;
  expect(cleared.revision).not.toHaveProperty("residual_value");

  // An element with a baja keeps it through a correction of anything else.
  const dispose = await port.submit(DISPOSE, {
    asset_id: "taladro",
    disposal: {
      disposal_date: fixtureDay(9, 30),
      reason: "sale",
      proceeds: { decimal: "100.00" },
      transmission_costs: { decimal: "0.00" },
      market_value: null,
      prior_free_depreciation_regime: null,
      later_affectation_on: null,
    },
  });
  expect(dispose.kind).toBe("settled");
  const disposed = await inspect("taladro");
  const recorded = disposed.revision.disposal;
  expect(recorded).toMatchObject({ disposal_date: fixtureDay(9, 30) });
  const row = (await listOf(port)).find(
    (found) => found.asset_id === "taladro",
  )!;
  expect(row.disposal).toMatchObject({
    disposal_date: fixtureDay(9, 30),
    reason: "sale",
    reason_key: "ledger.actividad_asset.disposal_reason.sale",
  });
  const taladro = {
    kind: "correction" as const,
    row,
    descriptor: null,
    revision: disposed.revision,
    tokens: () => [],
    options: (await optionsOf(port)) as FormOptions,
  };
  const before = initialOf(taladro, fieldsFor(taladro, {}));
  const edit = { ...before, residual_value: "5" };
  const kept = correctRequest(
    answer(fieldsFor(taladro, edit), edit, before).values,
    {
      assetId: "taladro",
      regime: null,
      candidate: null,
      base: disposed,
      options: taladro.options,
    },
    [],
  )!;
  expect(kept.revision.disposal).toEqual(recorded);
  expect(
    (await settled<{ outcome: string }>(port.submit(CORRECT, kept as never)))
      .outcome,
  ).toBe("succeeded");
  expect(
    (await listOf(port)).find((found) => found.asset_id === "taladro")!
      .disposal,
  ).toMatchObject({ disposal_date: fixtureDay(9, 30) });
  const latest = await inspect("taladro");
  expect(latest.revision.disposal).toEqual(recorded);

  // A baja is changed by stating another, and removed by stating none.
  const moved = bajaRequest(latest, {
    disposal_date: fixtureDay(6, 30),
    reason: "sale",
    proceeds: { decimal: "100.00" },
    transmission_costs: { decimal: "0.00" },
    market_value: null,
    prior_free_depreciation_regime: null,
    later_affectation_on: null,
  })!;
  expect(moved.revision).toMatchObject({
    supersedes_revision_id: latest.revision_id,
    disposal: { disposal_date: fixtureDay(6, 30) },
  });
  expect(moved.revision).not.toHaveProperty("revision_number");
  expect(moved.superseding_claims).toEqual([]);
  expect(
    (await settled<{ outcome: string }>(port.submit(CORRECT, moved as never)))
      .outcome,
  ).toBe("succeeded");
  expect(
    (await listOf(port)).find((found) => found.asset_id === "taladro")!
      .disposal,
  ).toMatchObject({ disposal_date: fixtureDay(6, 30) });
  const removal = bajaRequest(await inspect("taladro"), null)!;
  expect(removal.revision.disposal).toBeNull();
  expect(removal.revision).not.toHaveProperty("revision_number");
  // A correction that leaves its baja out is not decoded, whatever else it
  // states: null is what removes it.
  const withoutBaja: Record<string, unknown> = { ...removal.revision };
  delete withoutBaja.disposal;
  await expect(
    port.submit(CORRECT, { ...removal, revision: withoutBaja } as never),
  ).rejects.toMatchObject({ code: "refused", reason: "invalid" });
  // Out of service, nothing is left to amortize: the list says so.
  expect(
    (await listOf(port)).find((found) => found.asset_id === "taladro"),
  ).toMatchObject({ pending_applies: false });
  expect(
    (await settled<{ outcome: string }>(port.submit(CORRECT, removal as never)))
      .outcome,
  ).toBe("succeeded");
  const freed = (await listOf(port)).find(
    (found) => found.asset_id === "taladro",
  )!;
  expect(freed.disposal).toBeNull();
  expect(freed.pending_applies).toBe(true);
  expect(freed.state).toBe("in_service");
  // A second baja is refused until the first is changed or removed.
  expect(bajaRequest(null, null)).toBeNull();
});

test("each act's fields and requests come from the backend's choices", () => {
  const methods = ["linear", "low_value_free"];
  const options: FormOptions = {
    tax_year: servedSupport.horizon,
    asset_kind: "material",
    regime: "normal",
    edition: servedEditionOf(servedSupport.horizon)!,
    acquisition_shapes: [...ACQUISITION_SHAPES],
    declared_activities: [...DECLARED_ACTIVITIES],
    methods,
    method_facts: METHOD_FACTS.material!.filter((found) =>
      methods.includes(found.method),
    ) as unknown as FormOptions["method_facts"],
    table_groups: TABLE_GROUPS.material!.slice(0, 2),
    disposal_reasons: [...DISPOSAL_REASONS],
    basis_stages: [...BASIS_STAGES],
    opening_statuses: [...OPENING_STATUSES],
    acquired_conditions: [...ACQUIRED_CONDITIONS],
    further_acquisition_shapes: [...FURTHER_ACQUISITION_SHAPES],
    m130_periods: servedM130PeriodsOf(servedSupport.horizon),
  };
  const fields = fieldsFor(
    {
      kind: "element",
      row: null,
      descriptor: null,
      revision: null,
      tokens: (family) =>
        family === "asset_kind" ? ["material", "intangible"] : [],
      options,
    },
    { method: "linear" },
  );
  const choices = (key: string) =>
    fields.find((found) => found.key === key)!.choices;
  const classKey = factKey(["authority_class_key"]);
  expect(choices("asset_kind").map((choice) => choice.token)).toEqual([
    "material",
    "intangible",
  ]);
  expect(choices("method").map((choice) => choice.token)).toEqual([
    "linear",
    "low_value_free",
  ]);
  expect(choices("acquisition_shape").map((choice) => choice.token)).toEqual(
    ACQUISITION_SHAPES,
  );
  expect(choices(classKey).map((choice) => choice.token)).toEqual(
    options.table_groups.map((group) => group.class_key),
  );
  // A table class is drawn by the official name the backend serves with it.
  expect(
    choices(classKey).map((choice) => [choice.family, choice.label]),
  ).toEqual(options.table_groups.map((group) => [null, group.class_label]));
  const plan = SCENARIO_ELEMENTS.find(
    (seed) => seed.id === "furgoneta",
  )!.rows.find((row) => row.tax_year === scenarioYear)!;
  const claim = claimFields(plan, null);
  expect(claim.map((found) => [found.key, found.current])).toEqual([
    ["covered_from", fixtureDay(7, 1)],
    ["covered_through", fixtureDay(12, 31)],
  ]);
  // The span starts from the backend's own, and is shown by its last day.
  expect(claimSpans(plan, null)).toEqual([
    { from: fixtureDay(7, 1), through: fixtureDay(12, 31) },
  ]);
  const free = SCENARIO_ELEMENTS.find((seed) => seed.id === "impresora")!
    .rows[0]!;
  expect(claimFields(free, null).map((found) => found.key)).toEqual([
    "covered_from",
    "covered_through",
    "free_amount",
  ]);
  expect(
    forecastRequest(
      "a",
      {
        covered_from: fixtureDay(1, 1),
        covered_through: fixtureDay(6, 30),
        free_amount: { decimal: "5.00" },
      },
      "c",
    ),
  ).toEqual({
    asset_id: "a",
    covered_from: fixtureDay(1, 1),
    covered_through: fixtureDay(6, 30),
    requested_free_amount: { decimal: "5.00" },
    supersedes_claim_id: "c",
  });
  expect(
    forecastRequest("a", { covered_from: fixtureDay(1, 1) }, null),
  ).toBeNull();
  expect(
    forecastRequest("a", { covered_through: fixtureDay(6, 30) }, null),
  ).toBeNull();
  expect(
    describeRequest("a", { name: "Sierra", serial_number: "S1" }).descriptor,
  ).toEqual({
    name: "Sierra",
    serial_number: "S1",
    description: null,
    document_kind: null,
    document_number: null,
    supplier_name: null,
    supplier_tax_id: null,
  });
});

test("the add form offers the methods the options serve, each with the facts they serve, and a correction keeps the element's own", async () => {
  const port = portOf();
  for (const kind of ["material", "intangible"]) {
    const options = (await optionsOf(port, kind)) as FormOptions;
    // Every served fact has a word, and no method is offered without its facts.
    expect(unlabelledFacts(options)).toEqual([]);
    // Every fact a basis stage or an opening status serves has a control.
    expect(undrawableFacts(options)).toEqual([]);
    const offered = (draft: Record<string, string>) =>
      fieldsFor(
        {
          kind: "element",
          row: null,
          descriptor: null,
          revision: null,
          tokens: () => [],
          options,
        },
        draft,
      );
    expect(
      offered({})
        .find((found) => found.key === "method")!
        .choices.map((choice) => choice.token),
    ).toEqual(options.methods);
    for (const method of options.methods) {
      // The fields drawn for a method are its served facts, nothing more.
      const drawn = offered({
        method,
        acquired_condition: "used",
      })
        .map((found) => found.key)
        .filter((key) => key.startsWith("amortization."));
      expect(drawn).toEqual(
        factsOf(options, method).map((fact) => factKey(fact.path)),
      );
    }
  }
  const options = (await optionsOf(port)) as FormOptions;
  const keptContext = {
    kind: "correction" as const,
    row: null,
    descriptor: null,
    revision: {
      amortization: { regime: "normal", method: "approved_plan" },
    } as never,
    tokens: () => [],
    options,
  };
  expect(
    fieldsFor(keptContext, {})
      .find((found) => found.key === "method")!
      .choices.map((choice) => choice.token),
  ).toContain("approved_plan");
});

test("a refusal is read by its reason key and facts, and what is still to fill in is named", () => {
  const body = {
    outcome: "refused",
    refusal: {
      code: INCOMPLETE,
      precondition_verdict: { missing_field_keys: ["name", "basis_amount"] },
      reason_key: "ledger.actividad_asset.errors.table_class_required",
      reason_facts: [
        { key: "method", value: "linear", kind: "text" },
        { key: "bad", value: 3, kind: "count" },
        { key: "untyped", value: "x" },
      ],
    },
  };
  expect(refusalOf(body)).toEqual({
    code: INCOMPLETE,
    reasonKey: "ledger.actividad_asset.errors.table_class_required",
    reasonFacts: [{ key: "method", value: "linear", kind: "text" }],
    words: null,
    missing: ["name", "basis_amount"],
  });
  expect(refusalOf(null)).toEqual({
    code: null,
    reasonKey: null,
    reasonFacts: [],
    words: null,
    missing: [],
  });
  const view = viewOf({ kind: "done", result: body }, () => false);
  expect(view).toMatchObject({ kind: "refused", code: INCOMPLETE });
  expect(
    viewOf({ kind: "refused", reason: "invalid", detail: null }, () => false),
  ).toMatchObject({ kind: "refused", reason: "invalid", missing: [] });
  expect(viewOf(idle, () => false).kind).toBe("failed");
  expect(viewOf({ kind: "unknown" }, () => false).kind).toBe("unknown");
  expect(viewOf(null, () => false).kind).toBe("none");
  const labels = missingLabels(
    ((key: string) => `<${key}>`) as Translate,
    fieldsFor({
      kind: "element",
      row: null,
      descriptor: null,
      revision: null,
      tokens: () => [],
      options: null,
    }),
    ["name", "amortization.method"],
  );
  expect(labels).toContain("<desktop.ledger.assets.field.name>");
  expect(labels).toContain("<desktop.ledger.assets.field.method>");
  expect(refusalWord({ words: null })).toBeNull();
  expect(refusalWord({ words: "A served sentence." })).toBe(
    "A served sentence.",
  );
});

test("a held write is read against the register: found, not found, or not told", async () => {
  const port = portOf();
  const listed = await registerOf(port);
  expect(elementLanded(listed, "plotter")).toBe("saved");
  expect(elementLanded(listed, "minted-but-never-saved")).toBe("not_saved");
  const plotter = listed.rows!.find((row) => row.asset_id === "plotter")!;
  // A correction landed once the element stands past the revision it
  // superseded; one that has not moved past it did not.
  expect(correctionLanded(listed, "plotter", plotter.revision_number - 1)).toBe(
    "saved",
  );
  expect(correctionLanded(listed, "plotter", plotter.revision_number)).toBe(
    "not_saved",
  );
  expect(correctionLanded(listed, "nobody", 1)).toBe("untold");
  const rows = await planOf(port, "furgoneta");
  const sent = {
    tax_year: priorYear - 1,
    from: `${priorYear - 1}-01-01`,
    until: `${priorYear}-01-01`,
    amount: "2880",
  };
  // The same number however it is spelled; a different one is not found.
  expect(claimLanded(rows, sent)).toBe("saved");
  expect(claimLanded(rows, { ...sent, amount: "2880.01" })).toBe("not_saved");
  expect(claimLanded(rows, { ...sent, until: `${priorYear - 1}-06-30` })).toBe(
    "not_saved",
  );
  // A year the register does not list is not told.
  const unlisted = Math.min(...REGISTER_YEARS) - 1;
  expect(claimLanded(rows, { ...sent, tax_year: unlisted })).toBe("untold");
  expect(descriptorLanded([], 1)).toBe("not_saved");
});

// ---- Words ------------------------------------------------------------------

test("a refusal reads as the sentence the backend served, and anything else as the generic word", () => {
  const t = words({
    "desktop.ledger.assets.refused": "Not accepted.",
    "desktop.ledger.assets.unrecognised": "Not recognised",
    [`${ASSET_FAMILY.method}linear`]: "Linear",
  });
  // The sentence arrives said; the window adds nothing to it.
  expect(refusalText(t, { refusal_words: "A served sentence." })).toBe(
    "A served sentence.",
  );
  // None served, or no refusal at all: the generic refused word.
  expect(refusalText(t, { refusal_words: null })).toBe("Not accepted.");
  expect(refusalText(t, {})).toBe("Not accepted.");
  expect(refusalText(t, null)).toBe("Not accepted.");
  expect(tokenWord(t, "method", "linear")).toBe("Linear");
  expect(tokenWord(t, "method", "invented")).toBe("Not recognised");
  expect(tokenWord(t, "method", null)).toBe("Not recognised");
  expect(
    changeValueText(
      t,
      "en",
      change("amortization.method", "invented"),
      "after",
    ),
  ).toBe("Not recognised");
  expect(
    changeValueText(t, "en", change("serial_number", "SC-1"), "after"),
  ).toBe("SC-1");
});

test("a share in the timeline is drawn from its value in the window's language, the backend's label for it unused, and a class keeps its label", () => {
  const share = {
    ...change("amortization.linear_coefficient", "0.255"),
    after_label: "25.5%",
  };
  // The backend writes its label without a language: 25.5%.
  expect(changeValueText(words({}), "en", share, "after")).toBe("25.5%");
  expect(changeValueText(words({}), "es", share, "after")).toMatch(/^25,5\s%$/);
  const kind = {
    ...change("amortization.authority_class_key", "maquinaria"),
    after_label: "Maquinaria",
  };
  expect(changeValueText(words({}), "es", kind, "after")).toBe("Maquinaria");
});

test("the list serves the years, and the pane opens on one that has begun", async () => {
  const port = portOf();
  const register = await registerOf(port);
  const served = [
    ...new Set((register.rows ?? []).flatMap((row) => row.years)),
  ].sort((a, b) => a - b);
  expect(register.years).toEqual(served);
  expect(register.years).toEqual(REGISTER_YEARS);
  // Every year of an element, served or projected, is a year of its plan.
  for (const row of register.rows ?? []) {
    const plan = (await planOf(port, row.asset_id)).map(
      (found) => found.tax_year,
    );
    for (const year of [...row.years, ...row.projected_years])
      expect(plan, row.asset_id).toContain(year);
  }
  expect(
    (register.rows ?? []).some((row) => row.projected_years.length > 0),
  ).toBe(true);
  // The year the register opens on is the backend's to serve, never one the
  // computer's clock picks.
  expect(register.default_year).toBe(REGISTER_DEFAULT_YEAR);
});

test("a table class is named as the backend serves it, in the options and in the plan", async () => {
  const port = portOf();
  const options = (
    await settled<LedgerResult<typeof OPTIONS>>(
      port.submit(OPTIONS, {
        asset_kind: "material",
        tax_year: priorYear,
      }),
    )
  ).options!;
  const group = options.table_groups.find(
    (found) => found.class_key === "transporte-externo",
  )!;
  expect(group.class_label.length).toBeGreaterThan(0);
  const limits = (
    await settled<LedgerResult<typeof PLAN>>(
      port.submit(PLAN, { asset_id: "furgoneta" }),
    )
  ).limits!;
  expect(limits.class_label).toBe(group.class_label);
  // A free method has no class, so it has no name.
  const free = (
    await settled<LedgerResult<typeof PLAN>>(
      port.submit(PLAN, { asset_id: "taladro" }),
    )
  ).limits!;
  expect(free).toMatchObject({ class_key: null, class_label: null });
});

test("a value the backend worded by key is drawn by that key, and anything else as stated", () => {
  const t = words({
    "ledger.actividad_asset.basis_stage.business_allocated":
      "Allocated to the activity",
    "ledger.actividad_asset.disposal_finding.claim_gap":
      "Year with depreciation not recorded",
    "desktop.ledger.assets.unrecognised": "Not recognised",
  });
  expect(
    keyedText(
      t,
      "ledger.actividad_asset.basis_stage.business_allocated",
      "business_allocated",
    ),
  ).toBe("Allocated to the activity");
  expect(keyedText(t, null, fixtureDay(1, 1))).toBe(fixtureDay(1, 1));
  expect(keyedText(t, undefined, "x")).toBe("x");
  // A key outside the families, or one the table lacks, is never drawn.
  expect(keyedText(t, "tui.ledger.activity_asset.plan", "stated")).toBe(
    "stated",
  );
  expect(
    keyedText(t, "ledger.actividad_asset.basis_stage.invented", "stated"),
  ).toBe("stated");
  expect(
    keyedText(t, "ledger.actividad_asset.disposal_finding.claim_gap", ""),
  ).toBe("Year with depreciation not recorded");
  expect(
    changeValueText(t, "en", change("disposal.reason", "invented"), "after"),
  ).toBe("Not recognised");
  // A word the backend names and the catalogue lacks is never drawn raw.
  expect(
    changeValueText(
      t,
      "en",
      change(
        "disposal.prior_free_depreciation_regime",
        "invented",
        "ledger.actividad_asset.prior_free_depreciation_regime.invented",
      ),
      "after",
    ),
  ).toBe(t("desktop.ledger.assets.timeline.value_recorded"));
});

test("a purchase states the ledger's own account of its non-deductible IVA", async () => {
  const offered = (
    await settled<LedgerResult<typeof CANDIDATES>>(
      portOf().submit(CANDIDATES, {}),
    )
  ).candidates!;
  for (const purchase of offered)
    expect(purchase.non_deductible_iva_state_key).toBe(
      `ledger.actividad_asset.non_deductible_iva_state.${purchase.non_deductible_iva_state}`,
    );
});

// ---- Facts the forms could not state before ----------------------------------------

test("an element bought outside the ledger names its document, its date and its activity, and no purchase", async () => {
  const port = portOf();
  const outside = OUTSIDE_LEDGER;
  const request = (await newRequest(port, outside, "made-6"))!;
  expect(request).not.toBeNull();
  expect(request.revision).toMatchObject({
    acquisition_shape: outside.acquisition_shape,
    acquisition: {
      observed_transaction_id: null,
      observed_lineage_event_id: null,
      invoice_evidence_id: outside.acquisition_reference,
      evidence_fingerprint: null,
    },
    further_acquisitions: [],
    declared_acquisition_date: outside.declared_acquisition_date,
    declared_activity: outside.declared_activity,
  });
  // The document it holds is stated; without it nothing is made.
  expect(
    await newRequest(port, { ...outside, acquisition_reference: "" }, "made-6"),
  ).toBeNull();
  expect((await port.submit(CREATE, request as never)).kind).toBe("settled");
  expect(
    (await listOf(port)).some((found) => found.asset_id === "made-6"),
  ).toBe(true);
  // The day it was bought cannot follow the day it entered service.
  const late = await newRequest(
    port,
    { ...outside, declared_acquisition_date: fixtureDay(7, 1) },
    "made-7",
  );
  const refusal = await refused(port.submit(CREATE, late as never));
  expect(refusal.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.declared_acquisition_after_service",
  );
  const options = (await optionsOf(port)) as FormOptions;
  const drawn = (shape: string) =>
    fieldsFor(
      {
        kind: "element",
        row: null,
        descriptor: null,
        revision: null,
        tokens: () => [],
        options,
      },
      { acquisition_shape: shape },
    ).map((found) => found.key);
  expect(drawn("primary_purchase")).toContain("acquisition");
  expect(drawn("primary_purchase")).not.toContain("declared_activity");
  expect(drawn("acquired_outside_ledger")).not.toContain("acquisition");
  expect(drawn("acquired_outside_ledger")).toEqual(
    expect.arrayContaining([
      "declared_acquisition_date",
      "declared_activity",
      "acquisition_reference",
    ]),
  );
});

test("a whole property states its parts, a vehicle its declaration, and a linear election its hours", async () => {
  // Each element names the one purchase the ledger offers, so each has a ledger.
  /** Send one whole draft the corpus commits, whose answer the register holds. */
  const sendDraft = async (draft: Record<string, string>, id: string) => {
    const port = portOf();
    const request = await newRequest(port, draft, id);
    expect(request, id).not.toBeNull();
    return {
      request: request!,
      outcome: port.submit(CREATE, request as never),
    };
  };
  /** Send a draft changed away from a committed one, which the register was
   * never asked and so holds no answer for. */
  const send = async (changes: Record<string, string>, id: string) => {
    const port = portOf();
    const request = await newRequest(port, { ...NEW_ELEMENT, ...changes }, id);
    expect(request, JSON.stringify(changes)).not.toBeNull();
    return {
      request: request!,
      outcome: port.submit(CREATE, request as never),
    };
  };
  const property = WHOLE_PROPERTY;
  const made = await sendDraft(property, "made-8");
  expect(made.request.revision.basis).toMatchObject({
    stage: "whole_property",
    is_property: true,
    construction_cost: { decimal: "800" },
    land_cost: { decimal: "200" },
    ownership_mode: "sole",
    ownership_share: { decimal: "1" },
    office_area: { decimal: "30" },
    total_area: { decimal: "100" },
  });
  expect((await made.outcome).kind).toBe("settled");
  // A stage that is not a property states none of its parts.
  const plain = await newRequest(
    portOf(),
    { ...NEW_ELEMENT, construction_cost: "800.00" },
    "made-9",
  );
  expect(plain!.revision.basis).toMatchObject({ is_property: false });
  expect(plain!.revision.basis).not.toHaveProperty("construction_cost");
  const parts = await send({ ...property, office_area: "" }, "made-10");
  const incomplete = await refused(parts.outcome);
  expect(incomplete.detail.refusal).toMatchObject({
    code: INCOMPLETE,
    precondition_verdict: { missing_field_keys: ["basis.office_area"] },
  });

  const vehicle = VEHICLE_ELEMENT;
  const driven = await sendDraft(vehicle, "made-11");
  expect(driven.request.revision.vehicle_affectation).toEqual({
    category: "passenger_car",
    private_use: "none",
    recorded_in_activity_books: true,
    evidence_reference: "Libro registro de bienes de inversión",
    electric_propulsion: "bev",
  });
  expect((await driven.outcome).kind).toBe("settled");
  const unbooked = await send(
    { ...vehicle, vehicle_in_books: "no" },
    "made-12",
  );
  expect((await refused(unbooked.outcome)).detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.vehicle_missing_from_books",
  );
  // A vehicle is declared for a material element only.
  const intangible = await optionsOf(portOf(), "intangible");
  expect(
    fieldsFor(
      {
        kind: "element",
        row: null,
        descriptor: null,
        revision: null,
        tokens: () => [],
        options: intangible as FormOptions,
      },
      { asset_kind: "intangible", vehicle_declared: "yes" },
    ).map((found) => found.key),
  ).not.toContain("vehicle_declared");

  const hours = await sendDraft(SHIFT_HOURS, "made-13");
  expect(hours.request.revision.amortization).toMatchObject({
    method: "linear",
    shift_hours_per_day: { decimal: "16" },
  });
  expect((await hours.outcome).kind).toBe("settled");
  const tooMany = await send(
    { "amortization.shift_hours_per_day": "25" },
    "made-14",
  );
  await expect(tooMany.outcome).rejects.toMatchObject({ reason: "invalid" });
});

test("a method with a fact that has no form is not offered, and its repeated rows are never drawn", () => {
  const options: FormOptions = {
    tax_year: servedSupport.horizon,
    asset_kind: "material",
    regime: "normal",
    edition: servedEditionOf(servedSupport.horizon)!,
    disposal_reasons: [],
    methods: ["plain", "rows", "unworded"],
    acquisition_shapes: [...ACQUISITION_SHAPES],
    declared_activities: [...DECLARED_ACTIVITIES],
    method_facts: [
      { method: "plain", facts: [] },
      {
        method: "rows",
        facts: [
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
        method: "unworded",
        facts: [
          {
            path: ["invented_fact"],
            kind: "text",
            required: true,
            required_with_group: false,
            token_family: null,
            tokens: [],
          },
        ],
      },
    ],
    table_groups: [],
    basis_stages: [],
    opening_statuses: [],
    acquired_conditions: [],
    further_acquisition_shapes: [],
    m130_periods: [],
  };
  const fields = fieldsFor({
    kind: "element",
    row: null,
    descriptor: null,
    revision: null,
    tokens: () => [],
    options,
  });
  expect(
    fields
      .find((found) => found.key === "method")!
      .choices.map((choice) => choice.token),
  ).toEqual(["plain"]);
  expect(unlabelledFacts(options)).toEqual(["invented_fact"]);
});

test("the one dotación a refusal names as in the way is offered for correction; several, none or a plain refusal offer none", async () => {
  const port = portOf();
  const furgoneta = (await planOf(port, "furgoneta")).find(
    (row) => row.tax_year === scenarioYear,
  )!;
  const recorded = furgoneta.claims.filter((found) => found.effective);
  expect(recorded.length).toBeGreaterThan(0);
  const first = recorded[0]!;
  // The last day a dotación covers is the day before its exclusive boundary.
  expect(first.covered_through < first.covered_until).toBe(true);
  // A forecast that meets it is refused with the claim it meets.
  const refusal = (await refused(
    port.submit(FORECAST, {
      asset_id: "furgoneta",
      covered_from: first.covered_from,
      covered_through: first.covered_through,
      requested_free_amount: null,
      supersedes_claim_id: null,
    }),
  )) as Refused;
  expect(refusal.detail.refusal.reason_key).toBe(CLAIMS_OVERLAP);
  const named = refusalOf(refusal.detail).reasonFacts;
  expect(named).toEqual([
    { key: "conflicting_claim_ids", value: first.claim_id, kind: "text" },
  ]);
  expect(claimInTheWay(named)).toBe(first.claim_id);
  // Several, none, or a refusal without the fact name no single one.
  expect(
    claimInTheWay([
      { key: "conflicting_claim_ids", value: "a,b", kind: "text" },
    ]),
  ).toBeNull();
  expect(
    claimInTheWay([{ key: "conflicting_claim_ids", value: "", kind: "text" }]),
  ).toBeNull();
  expect(claimInTheWay([])).toBeNull();
  // The names are for acting on, never for saying: the sentence arrives said
  // and does not carry the claim ids.
  expect(refusalOf(refusal.detail).words ?? "").not.toContain(first.claim_id);
  for (const interval of furgoneta.claimable_intervals)
    expect(interval.covered_through < interval.covered_until).toBe(true);
});
