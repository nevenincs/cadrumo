import { expect, test } from "@playwright/test";
import {
  answer,
  bajaLanded,
  claimLanded,
  claimReused,
  CONFLICT,
  correctionLanded,
  createReused,
  describeRequest,
  descriptorLanded,
  disposeRequest,
  draftedCall,
  draftOf,
  elementLanded,
  forecastRequest,
  INCOMPLETE,
  neverReused,
  refusalWord,
  staleClaims,
  viewOf,
} from "../src/components/ledger/assets/assetWrites";
import {
  isProvisionalOperation,
  PROVISIONAL_OPERATIONS,
  submitProvisional,
  type AssetListResult,
  type FormKind,
  type FormOptions,
  type FormValues,
  type PlanRow,
  type TimelineEvent,
} from "../src/components/ledger/assets/assetsContract";
import type { SetupCall } from "../src/components/ledger/setup/setupModel";
import { LEDGER_DEFINITIONS, type LedgerPort } from "../src/shell/ledger";
import { ledgerClassOf } from "../src/dev/ledgerClassesFixture";

// The Assets tab's provisional operations and the scenario ledger that
// answers them. No page is opened. The scenario ledger needs a window; a
// bare one stands in for it here.

const stand = globalThis as unknown as { window?: unknown };
stand.window = {
  location: { search: "" },
  setTimeout: globalThis.setTimeout,
};
const { ledgerFixture } = await import("../src/dev/ledgerFixture");
const { assetFixtureYears } = await import("../src/dev/assetsFixture");

const LIST = "ledger.actividad-asset.list";
const PLAN = "ledger.actividad-asset.plan";
const TIMELINE = "ledger.actividad-asset.timeline";
const OPTIONS = "ledger.actividad-asset.form-options";
const DESCRIBE = "ledger.actividad-asset.describe";
const DISPOSE = "ledger.actividad-asset.dispose";

const portOf = (shape: "fixture" | "unknown" = "fixture"): LedgerPort =>
  ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });

async function settled<T>(outcome: Promise<{ kind: string }>): Promise<T> {
  const found = (await outcome) as { kind: string; result?: T };
  if (found.kind !== "settled") throw new Error(`not settled: ${found.kind}`);
  return found.result as T;
}

const planOf = async (port: LedgerPort, id: string) =>
  (
    await settled<{ rows: PlanRow[] }>(
      submitProvisional(port, PLAN, { asset_id: id }),
    )
  ).rows;
const eventsOf = async (port: LedgerPort, id: string) =>
  (
    await settled<{ events: TimelineEvent[] }>(
      submitProvisional(port, TIMELINE, { asset_id: id }),
    )
  ).events;
const listOf = (port: LedgerPort) =>
  settled<{
    rows: {
      asset_id: string;
      name: string | null;
      baja?: { date: string; reason_key: string } | null;
      in_service_date: string;
      counts: { missing: number };
    }[];
    years: number[];
  }>(submitProvisional(port, LIST, {}));

test("no provisional operation is admitted yet; once the host admits one, this module goes", () => {
  const admitted = LEDGER_DEFINITIONS as readonly string[];
  for (const id of Object.keys(PROVISIONAL_OPERATIONS)) {
    expect(isProvisionalOperation(id), id).toBe(true);
    expect(
      admitted,
      `${id} is admitted: conform and delete the draft`,
    ).not.toContain(id);
  }
  for (const id of LEDGER_DEFINITIONS)
    expect(isProvisionalOperation(id), id).toBe(false);
});

test("the scenario classes a provisional operation by its draft effect", () => {
  for (const [id, draft] of Object.entries(PROVISIONAL_OPERATIONS))
    expect(ledgerClassOf(id as keyof typeof PROVISIONAL_OPERATIONS), id).toBe(
      draft.effect,
    );
});

test("the register spans decades and offers each year it holds", async () => {
  const listed = await listOf(portOf());
  expect(listed.years).toEqual(assetFixtureYears());
  expect([...listed.years].sort((a, b) => a - b)).toEqual(listed.years);
  expect(new Set(listed.years).size).toBe(listed.years.length);
  expect(listed.years.at(-1)! - listed.years[0]!).toBeGreaterThanOrEqual(25);
  // Every element enters service in a year the stepper offers.
  for (const row of listed.rows)
    expect(listed.years).toContain(Number(row.in_service_date.slice(0, 4)));
});

test("the plans hold every state the tab shows, none of them as a zero by default", async () => {
  const port = portOf();
  const listed = await listOf(port);
  const plans = await Promise.all(
    listed.rows.map((row) => planOf(port, row.asset_id)),
  );
  const rows = plans.flat();
  const states = new Set(rows.map((row) => row.state_key));
  for (const state of [
    "claimed",
    "missing",
    "partial",
    "incomplete",
    "forecast",
  ])
    expect(states, state).toContain(state);
  // A recorded zero is a claim; a missing year states no claimed figure.
  expect(
    rows.some(
      (row) => row.claimed?.decimal === "0.00" && row.claims.length > 0,
    ),
  ).toBe(true);
  for (const row of rows.filter((found) => found.state_key === "missing"))
    expect(row.claimed).toBeNull();
  for (const row of rows.filter((found) => found.state_key === "incomplete")) {
    expect(row.planned).toBeNull();
    expect(row.claimed).toBeNull();
    expect(row.planned_absent_key).not.toBeNull();
  }
  const absent = new Set(rows.map((row) => row.planned_absent_key));
  expect(absent).toContain("free_method");
  expect(absent).toContain("opening_history_unknown");
  // A superseded claim points to its replacement and is not counted claimed.
  const claims = rows.flatMap((row) => row.claims);
  const replaced = claims.find((claim) => claim.superseded_by !== null);
  expect(replaced?.effective).toBe(false);
  expect(
    claims.some((claim) => claim.claim_id === replaced?.superseded_by),
  ).toBe(true);
  expect(claims.some((claim) => !claim.matches_current_schedule)).toBe(true);
  expect(rows.some((row) => row.authority.projected)).toBe(true);
  expect(rows.some((row) => row.claimable !== null)).toBe(true);
  expect(rows.some((row) => row.finding_keys.includes("claim_conflict"))).toBe(
    true,
  );
  // A method change shows as a new election within one plan.
  expect(
    plans.some(
      (plan) => new Set(plan.map((row) => row.election.fingerprint)).size > 1,
    ),
  ).toBe(true);
  // The list counts what its plan holds.
  for (const [at, row] of listed.rows.entries()) {
    const plan = plans[at]!;
    expect(row.counts.missing).toBe(
      plan.filter((year) => year.state_key === "missing").length,
    );
  }
});

test("a baja keeps the element and its history and ends its plan", async () => {
  const port = portOf();
  const listed = await listOf(port);
  const disposed = listed.rows.find((row) => row.baja);
  expect(disposed).toBeDefined();
  const plan = await planOf(port, disposed!.asset_id);
  const last = Number(disposed!.baja!.date.slice(0, 4));
  expect(Math.max(...plan.map((row) => row.tax_year))).toBe(last);
  const types = (await eventsOf(port, disposed!.asset_id)).map(
    (event) => event.type_key,
  );
  expect(types).toContain("baja_recorded");
  expect(types.filter((type) => type === "claim_recorded").length).toBe(
    plan.flatMap((row) => row.claims).length,
  );
});

test("a timeline is ordered, never rewritten, and says what it replaced", async () => {
  const port = portOf();
  const listed = await listOf(port);
  const all = await Promise.all(
    listed.rows.map((row) => eventsOf(port, row.asset_id)),
  );
  for (const events of all)
    expect(events.map((event) => event.sequence)).toEqual(
      events.map((_, at) => at + 1),
    );
  const events = all.flat();
  expect(events.some((event) => event.recorded_at === null)).toBe(true);
  expect(events.some((event) => event.replaces_sequence !== null)).toBe(true);
  expect(
    events.some(
      (event) =>
        event.type_key === "description_added" && !event.affects_calculation,
    ),
  ).toBe(true);
  for (const events of all)
    for (const event of events)
      if (event.replaces_sequence !== null)
        expect(event.replaces_sequence).toBeLessThan(event.sequence);
});

test("describing appends a descriptor event and leaves every earlier event as it was", async () => {
  const port = portOf();
  const before = await eventsOf(port, "licencia");
  const done = await settled<{
    descriptor: { sequence: number; name: string; serial: string | null };
  }>(
    submitProvisional(port, DESCRIBE, {
      asset_id: "licencia",
      name: "Licencia de diseño",
      serial: "LIC-0042",
      fields: [],
    }),
  );
  expect(done.descriptor.name).toBe("Licencia de diseño");
  const after = await eventsOf(port, "licencia");
  expect(after.slice(0, before.length)).toEqual(before);
  expect(after).toHaveLength(before.length + 1);
  const added = after.at(-1)!;
  expect(added.type_key).toBe("description_added");
  expect(added.affects_calculation).toBe(false);
  expect(added.recorded_at).not.toBeNull();
  const listed = await listOf(port);
  expect(listed.rows.find((row) => row.asset_id === "licencia")?.name).toBe(
    "Licencia de diseño",
  );
});

test("a refused or incomplete write changes nothing and names what to fill in", async () => {
  const port = portOf();
  const before = await eventsOf(port, "prensa");
  const incomplete = await submitProvisional(port, DESCRIBE, {
    asset_id: "prensa",
    name: null,
    serial: null,
    fields: [],
  });
  expect(incomplete.kind).toBe("refused");
  expect((incomplete as { detail: unknown }).detail).toMatchObject({
    refusal: {
      code: "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE",
      precondition_verdict: { missing_field_keys: ["name"] },
    },
  });
  const unknownElement = await submitProvisional(port, DISPOSE, {
    asset_id: "nobody",
    date: "2026-01-31",
    reason_key: "sale",
  });
  expect(unknownElement.kind).toBe("refused");
  expect(await eventsOf(port, "prensa")).toEqual(before);
  // A malformed request is refused before anything runs.
  await expect(
    submitProvisional(port, DISPOSE, {
      asset_id: "prensa",
      date: "2026-01-31",
      reason_key: "sale",
      // @ts-expect-error a field the contract does not have
      proceeds: "1",
    }),
  ).rejects.toMatchObject({ code: "refused", reason: "invalid" });
});

test("a baja ends the plan at its date, replaces the claims it crosses and cannot be given twice", async () => {
  const port = portOf();
  const done = await settled<{
    baja: { date: string; reason_key: string };
    superseded_claim_ids: string[];
  }>(
    submitProvisional(port, DISPOSE, {
      asset_id: "furgoneta",
      date: "2026-03-31",
      reason_key: "theft",
    }),
  );
  expect(done.baja).toEqual({ date: "2026-03-31", reason_key: "theft" });
  // The half-year claim crosses the last day of service.
  expect(done.superseded_claim_ids).toHaveLength(1);
  const plan = await planOf(port, "furgoneta");
  expect(Math.max(...plan.map((row) => row.tax_year))).toBe(2026);
  expect(plan.find((row) => row.tax_year === 2026)?.claimed).toBeNull();
  const listed = await listOf(port);
  expect(listed.rows.find((row) => row.asset_id === "furgoneta")?.baja).toEqual(
    { date: "2026-03-31", reason_key: "theft" },
  );
  for (const refused of [
    { date: "2026-04-30", reason_key: "sale" },
    { date: "2026-04-30", reason_key: "not_offered" },
  ])
    expect(
      (
        await submitProvisional(port, DISPOSE, {
          asset_id: "furgoneta",
          ...refused,
        })
      ).kind,
    ).toBe("refused");
  const early = await submitProvisional(port, DISPOSE, {
    asset_id: "escaner",
    date: "2018-12-31",
    reason_key: "sale",
  });
  expect(early.kind).toBe("refused");
});

test("the forms are served as options, and a baja form bounds its date by the service date", async () => {
  const port = portOf();
  const baja = await settled<{
    options: {
      kind: string;
      fields: {
        key: string;
        choices: unknown[];
        bounds: { min: string | null } | null;
      }[];
    };
  }>(submitProvisional(port, OPTIONS, { kind: "baja", asset_id: "plotter" }));
  const date = baja.options.fields.find((found) => found.key === "date");
  expect(date?.bounds?.min).toBe("1999-03-15");
  expect(
    baja.options.fields.find((found) => found.key === "reason_key")?.choices
      .length,
  ).toBeGreaterThan(0);
  const correction = await settled<{
    options: { fields: { key: string }[] };
  }>(
    submitProvisional(port, OPTIONS, {
      kind: "correction",
      asset_id: "plotter",
    }),
  );
  expect(correction.options.fields.map((found) => found.key)).not.toContain(
    "out_of_service_date",
  );
});

test("a write whose settlement was not seen is held by the host as for any write, and a read is not", async () => {
  const port = portOf("unknown");
  const failure = await submitProvisional(port, DESCRIBE, {
    asset_id: "prensa",
    name: "Prensa",
    serial: null,
    fields: [],
  }).then(
    () => null,
    (error: { code: string; operation_id: string | null }) => error,
  );
  expect(failure?.code).toBe("unknown");
  expect((await port.observe(failure!.operation_id!)).kind).toBe("settled");
  expect((await submitProvisional(port, LIST, {})).kind).toBe("settled");
});

test("an operation that is neither admitted nor provisional is not admitted", async () => {
  const port = portOf();
  await expect(
    port.submit("ledger.actividad-asset.unlisted" as never, {} as never),
  ).rejects.toMatchObject({ code: "not_admitted" });
});

test("an element made through the admitted create appears in the register with its history", async () => {
  const port = portOf();
  const created = await port.submit("ledger.actividad-asset.create", {
    revision: {
      asset_id: "synthetic-created-1",
      revision_number: 1,
      acquisition: {
        observed_transaction_id: "a".repeat(64),
        invoice_evidence_id: "b".repeat(64),
        evidence_fingerprint: "c".repeat(64),
      },
      acquisition_shape: "purchase",
      asset_kind: "tangible",
      basis: {
        stage: "acquisition",
        basis_amount: { decimal: "1000" },
        non_deductible_iva: { decimal: "0" },
      },
      in_service_date: "2025-03-01",
      opening_history: { status: "complete" },
      acquired_condition: "new",
      amortization: { regime: "linear", method: "linear_table" },
    },
  });
  expect(created.kind).toBe("settled");
  const listed = await listOf(port);
  const found = listed.rows.find(
    (row) => row.asset_id === "synthetic-created-1",
  );
  expect(found?.name).toBeNull();
  const events = await eventsOf(port, "synthetic-created-1");
  expect(events.map((event) => event.type_key)).toEqual(["element_added"]);
  // It can be described like any other.
  const described = await submitProvisional(port, DESCRIBE, {
    asset_id: "synthetic-created-1",
    name: "Nuevo",
    serial: null,
    fields: [],
  });
  expect(described.kind).toBe("settled");
  expect(await eventsOf(port, "synthetic-created-1")).toHaveLength(2);
});

// ---- The forms: what typed text says, and how a write held in doubt landed --

const CANDIDATES = "ledger.actividad-asset.acquisition-candidates";
const CREATE = "ledger.actividad-asset.create";
const CORRECT = "ledger.actividad-asset.correct";
const FORECAST = "ledger.actividad-asset.forecast";
const CLAIM = "ledger.actividad-asset.claim";

const optionsOf = async (
  port: LedgerPort,
  kind: FormKind,
  extra: { asset_id?: string; tax_year?: number } = {},
) =>
  (
    await settled<{ options: FormOptions }>(
      submitProvisional(port, OPTIONS, { kind, ...extra }),
    )
  ).options;

/** The first choice of a field the options served. */
const firstChoice = (options: FormOptions, key: string) =>
  options.fields.find((field) => field.key === key)!.choices[0]!.token;

async function newElement(port: LedgerPort, assetId: string) {
  const options = await optionsOf(port, "element");
  const { candidates } = await settled<{
    candidates: { candidate_id: string }[];
  }>(submitProvisional(port, CANDIDATES, {}));
  const values: FormValues = {
    name: "Sierra de cinta",
    serial: null,
    kind_key: firstChoice(options, "kind_key"),
    method_key: firstChoice(options, "method_key"),
    in_service_date: "2026-06-15",
    acquisition: candidates[0]!.candidate_id,
    basis_amount: { decimal: "1500.00" },
    non_deductible_iva: { decimal: "0.00" },
  };
  return {
    values,
    send: () => draftedCall(port, CREATE, { asset_id: assetId, values }, true),
  };
}

const refusalIn = (call: SetupCall<unknown>) => {
  const view = viewOf(call, neverReused);
  if (view.kind !== "refused") throw new Error(`not refused: ${view.kind}`);
  return view;
};

test("typed text becomes the values of its control, and nothing typed is not zero", async () => {
  const options = await optionsOf(portOf(), "element");
  const full = answer(
    options,
    {
      name: "  Sierra  ",
      serial: "",
      kind_key: "tangible",
      method_key: "",
      in_service_date: "2026-06-15",
      acquisition: "",
      basis_amount: "1500.5",
      non_deductible_iva: "0",
    },
    null,
  );
  expect(full.problems).toEqual({});
  expect(full.values.name).toBe("Sierra");
  expect(full.values.serial).toBeNull();
  expect(full.values.method_key).toBeNull();
  expect(full.values.basis_amount).toEqual({ decimal: "1500.5" });
  // A stated zero is a value; an empty field is not one.
  expect(full.values.non_deductible_iva).toEqual({ decimal: "0" });
  const unstated = answer(options, { non_deductible_iva: "" }, null);
  expect(unstated.values.non_deductible_iva).toBeNull();
  const refused = answer(
    options,
    { basis_amount: "1,5", in_service_date: "15/06/2026" },
    null,
  );
  expect(refused.problems.basis_amount?.key).toBe("comma_decimal");
  expect(refused.problems.in_service_date?.key).toBe("date_not_iso");
  expect(refused.values.basis_amount).toBeUndefined();
});

test("the options number the next descriptor and revision, so a landing never counts for itself", async () => {
  const port = portOf();
  const next = async (kind: FormKind, asset: string) =>
    (await optionsOf(port, kind, { asset_id: asset })).next_sequence;
  // The plotter has one description and one revision; the server two revisions.
  expect(await next("descriptor", "plotter")).toBe(2);
  expect(await next("correction", "plotter")).toBe(2);
  expect(await next("correction", "servidor")).toBe(3);
  expect(await next("baja", "plotter")).toBeNull();
});

test("a correction states only what changed from the record, and never an emptied field", async () => {
  const options = await optionsOf(portOf(), "correction", {
    asset_id: "servidor",
  });
  const initial = draftOf(options);
  expect(initial.method_key).toBe("constant_percentage");
  const changed = answer(
    options,
    { ...initial, basis_amount: "19800.00", method_key: "" },
    initial,
  );
  // Text is sent in the product's canonical spelling.
  expect(changed.values).toEqual({ basis_amount: { decimal: "19800" } });
  expect(answer(options, initial, initial).values).toEqual({});
});

test("each act's request is built from the values, and a span waits for both dates", () => {
  expect(
    describeRequest("a", {
      name: "Plotter",
      serial: null,
      libro_registro: "R-7",
    }),
  ).toEqual({
    asset_id: "a",
    name: "Plotter",
    serial: null,
    fields: [{ key: "libro_registro", value: "R-7" }],
  });
  expect(
    disposeRequest("a", { date: "2026-01-31", reason_key: "sale" }),
  ).toEqual({ asset_id: "a", date: "2026-01-31", reason_key: "sale" });
  expect(disposeRequest("a", {})).toEqual({
    asset_id: "a",
    date: null,
    reason_key: null,
  });
  expect(forecastRequest("a", { from: "2026-01-01" }, null)).toBeNull();
  expect(
    forecastRequest(
      "a",
      {
        from: "2026-01-01",
        until: "2026-06-30",
        free_amount: { decimal: "5" },
      },
      "c",
    ),
  ).toEqual({
    asset_id: "a",
    covered_from: "2026-01-01",
    covered_until: "2026-06-30",
    requested_free_amount: { decimal: "5" },
    supersedes_claim_id: "c",
  });
});

test("a write held in doubt is read against the register: found, not found, or not told", async () => {
  const port = portOf();
  const listed = await settled<AssetListResult>(
    submitProvisional(port, LIST, {}),
  );
  const plotter = listed.rows.find((row) => row.asset_id === "plotter")!;
  expect(elementLanded(listed, "plotter")).toBe("saved");
  expect(elementLanded(listed, "minted-but-never-saved")).toBe("not_saved");
  expect(correctionLanded(listed, "plotter", plotter.revision_number)).toBe(
    "saved",
  );
  expect(correctionLanded(listed, "plotter", plotter.revision_number + 1)).toBe(
    "not_saved",
  );
  expect(correctionLanded(listed, "nobody", 1)).toBe("untold");
  expect(bajaLanded(listed, "plotter")).toBe("not_saved");
  expect(bajaLanded(listed, "camara")).toBe("saved");
  expect(bajaLanded(listed, "nobody")).toBe("untold");
  const events = await eventsOf(port, "plotter");
  expect(descriptorLanded(events, 1)).toBe("saved");
  expect(descriptorLanded(events, 2)).toBe("not_saved");
  const rows = await planOf(port, "furgoneta");
  const sent = {
    tax_year: 2024,
    from: "2024-01-01",
    until: "2024-12-31",
    amount: "2100",
  };
  // The same number however it is spelled; a different one is not found.
  expect(claimLanded(rows, sent)).toBe("saved");
  expect(claimLanded(rows, { ...sent, amount: "2100.01" })).toBe("not_saved");
  expect(claimLanded(rows, { ...sent, until: "2024-06-30" })).toBe("not_saved");
  expect(claimLanded(rows, { ...sent, tax_year: 1901 })).toBe("untold");
});

test("a refusal is read by its backend keys, and what is still to fill in is named", () => {
  const incomplete = refusalIn({
    kind: "refused",
    reason: "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE",
    detail: {
      refusal: {
        code: INCOMPLETE,
        precondition_verdict: { missing_field_keys: ["name", "basis_amount"] },
      },
    } as never,
  });
  expect(incomplete.code).toBe(INCOMPLETE);
  expect(incomplete.missing).toEqual(["name", "basis_amount"]);
  const conflict = refusalIn({
    kind: "refused",
    reason: null,
    detail: {
      refusal: { code: CONFLICT, reason_key: "overlapping_claim" },
      conflicting_claim: {
        claim_id: "c1",
        from: "2026-01-01",
        until: "2026-06-30",
        amount: { decimal: "1050.00" },
      },
    } as never,
  });
  expect(conflict.conflict).toEqual({
    claim_id: "c1",
    from: "2026-01-01",
    until: "2026-06-30",
    amount: { decimal: "1050.00" },
  });
  // A refusal settled as a result reads the same as a refused outcome.
  expect(
    refusalIn({
      kind: "done",
      result: { outcome: "refused", refusal: { code: "X", reason_key: "y" } },
    }),
  ).toMatchObject({ code: "X", reasonKey: "y" });
  expect(viewOf(null, neverReused).kind).toBe("none");
  expect(viewOf({ kind: "unknown" }, neverReused).kind).toBe("unknown");
  expect(viewOf({ kind: "saved_unread" }, neverReused).kind).toBe(
    "saved_unread",
  );
  expect(
    viewOf({ kind: "failed", code: "too_large", reason: null }, neverReused)
      .kind,
  ).toBe("failed");
  expect(viewOf({ kind: "done", result: {} }, () => true)).toEqual({
    kind: "saved",
    reused: true,
  });
  // The words are the backend key's; a key the tab has no line for is null.
  const say = (key: string) => key;
  expect(refusalWord(say, { code: null, reasonKey: "already_disposed" })).toBe(
    "desktop.ledger.assets.reason.already_disposed",
  );
  expect(refusalWord(say, { code: INCOMPLETE, reasonKey: "unheard_of" })).toBe(
    "desktop.ledger.assets.refusal.refused_actividad_asset_incomplete",
  );
  expect(
    refusalWord(say, { code: "SOMETHING_NEW", reasonKey: null }),
  ).toBeNull();
});

test("adding an element: incomplete names what to fill in, a purchase is used once, the same id is already there", async () => {
  const port = portOf();
  const made = await newElement(port, "added-1");
  const empty = await draftedCall(
    port,
    CREATE,
    {
      asset_id: "added-1",
      values: { ...made.values, name: null, non_deductible_iva: null },
    },
    true,
  );
  expect(refusalIn(empty).code).toBe(INCOMPLETE);
  expect(refusalIn(empty).missing).toEqual(["name", "non_deductible_iva"]);
  expect((await listOf(port)).rows.map((row) => row.asset_id)).not.toContain(
    "added-1",
  );

  const first = await made.send();
  expect(viewOf(first, createReused)).toEqual({
    kind: "saved",
    reused: false,
  });
  const again = await made.send();
  expect(viewOf(again, createReused)).toEqual({ kind: "saved", reused: true });
  expect(
    (await eventsOf(port, "added-1")).map((event) => event.type_key),
  ).toEqual(["element_added", "description_added"]);
  // The id says the same act; other facts under it are another element's.
  const clash = await draftedCall(
    port,
    CREATE,
    { asset_id: "added-1", values: { ...made.values, name: "Otra" } },
    true,
  );
  expect(refusalIn(clash).reasonKey).toBe("asset_exists");
  // The purchase it was made from is no longer offered.
  const left = await settled<{ candidates: { candidate_id: string }[] }>(
    submitProvisional(port, CANDIDATES, {}),
  );
  expect(left.candidates.map((found) => found.candidate_id)).not.toContain(
    made.values.acquisition,
  );
  const second = await draftedCall(
    port,
    CREATE,
    { asset_id: "added-2", values: made.values },
    true,
  );
  expect(refusalIn(second).reasonKey).toBe("acquisition_not_found");
  // It is listed, so a lost answer to the add reads as saved.
  const listed = await settled<AssetListResult>(
    submitProvisional(port, LIST, {}),
  );
  expect(elementLanded(listed, "added-1")).toBe("saved");
});

test("a purchase that does not state its IVA leaves it unknown, and a stated zero is a value", async () => {
  const { candidates } = await settled<{
    candidates: { values: Record<string, string | null> }[];
  }>(submitProvisional(portOf(), CANDIDATES, {}));
  expect(
    candidates.some((found) => found.values.non_deductible_iva === null),
  ).toBe(true);
  expect(
    candidates.some((found) => found.values.non_deductible_iva === "0.00"),
  ).toBe(true);
});

test("a correction is refused on a stale revision or no change, asks a year for a method, and records claims again atomically", async () => {
  const port = portOf();
  const send = (values: FormValues, claims: string[] = [], revision = 2) =>
    draftedCall(
      port,
      CORRECT,
      {
        asset_id: "servidor",
        revision_number: revision,
        values,
        supersede_claim_ids: claims,
      },
      true,
    );
  const revisionOf = async () =>
    (
      await settled<AssetListResult>(submitProvisional(port, LIST, {}))
    ).rows.find((row) => row.asset_id === "servidor")?.revision_number;
  expect(
    refusalIn(await send({ basis_amount: { decimal: "1" } }, [], 1)).reasonKey,
  ).toBe("revision_stale");
  expect(refusalIn(await send({})).reasonKey).toBe("nothing_changed");
  const options = await optionsOf(port, "correction", { asset_id: "servidor" });
  const other = options.fields
    .find((field) => field.key === "method_key")!
    .choices.map((choice) => choice.token)
    .find((token) => token !== "constant_percentage")!;
  const noYear = refusalIn(await send({ method_key: other }));
  expect(noYear.code).toBe(INCOMPLETE);
  expect(noYear.missing).toEqual(["method_year"]);
  // Nothing was written by any of those.
  expect(await revisionOf()).toBe(2);

  const stale = staleClaims(await planOf(port, "servidor"));
  expect(stale.map((entry) => entry.year)).toEqual([2015]);
  const done = await send(
    { basis_amount: { decimal: "19800.00" } },
    stale.map((entry) => entry.claim.claim_id),
  );
  expect(viewOf(done, neverReused).kind).toBe("saved");
  const listed = await settled<AssetListResult>(
    submitProvisional(port, LIST, {}),
  );
  expect(await revisionOf()).toBe(3);
  expect(correctionLanded(listed, "servidor", 3)).toBe("saved");
  const after = await planOf(port, "servidor");
  const year = after.find((row) => row.tax_year === 2015)!;
  // The old claim is replaced, not edited, and the new one matches.
  const effective = year.claims.filter((claim) => claim.effective);
  expect(effective).toHaveLength(1);
  expect(effective[0]?.matches_current_schedule).toBe(true);
  expect(year.claims.find((claim) => !claim.effective)?.superseded_by).toBe(
    effective[0]?.claim_id,
  );
  // The claims left alone no longer match what was corrected.
  expect(
    after.find((row) => row.tax_year === 2016)?.claims[0]
      ?.matches_current_schedule,
  ).toBe(false);
  const types = (await eventsOf(port, "servidor")).map(
    (event) => event.type_key,
  );
  expect(types.slice(-2)).toEqual(["correction_added", "claim_recorded"]);
});

test("a forecast works out a span and records nothing; a claim is recorded once, refused where it overlaps, and replaces the claim it corrects", async () => {
  const port = portOf();
  const claimsOf = async (year: number) =>
    (await planOf(port, "furgoneta")).find((row) => row.tax_year === year)!
      .claims;
  const before = await claimsOf(2025);
  const forecast = (from: string, until: string, supersedes?: string) =>
    draftedCall(
      port,
      FORECAST,
      {
        asset_id: "furgoneta",
        covered_from: from,
        covered_until: until,
        requested_free_amount: null,
        supersedes_claim_id: supersedes ?? null,
      },
      false,
    );
  const forecasted = async (
    from: string,
    until: string,
    supersedes?: string,
  ) => {
    const call = await forecast(from, until, supersedes);
    if (call.kind !== "done" || !call.result.forecast)
      throw new Error("no forecast");
    return call.result.forecast;
  };
  const claim = (
    worked: Awaited<ReturnType<typeof forecasted>>,
    supersedes: string | null = null,
  ) =>
    draftedCall(
      port,
      CLAIM,
      { forecast: worked, supersedes_claim_id: supersedes },
      true,
    );

  const year = await forecasted("2025-01-01", "2025-12-31");
  expect(year.amount).toEqual({ decimal: "2100.00" });
  expect(year.service_days).toBe(365);
  expect(await claimsOf(2025)).toEqual(before);

  expect(viewOf(await claim(year), claimReused)).toEqual({
    kind: "saved",
    reused: false,
  });
  expect(viewOf(await claim(year), claimReused)).toEqual({
    kind: "saved",
    reused: true,
  });
  expect(await claimsOf(2025)).toHaveLength(1);
  const rows = await planOf(port, "furgoneta");
  expect(rows.find((row) => row.tax_year === 2025)?.state_key).toBe("claimed");
  expect(
    claimLanded(rows, {
      tax_year: 2025,
      from: "2025-01-01",
      until: "2025-12-31",
      amount: "2100.00",
    }),
  ).toBe("saved");

  // 2026 holds a half-year claim: a span over it names it and writes nothing.
  const over = await forecasted("2026-01-01", "2026-12-31");
  const conflict = refusalIn(await claim(over));
  expect(conflict.code).toBe(CONFLICT);
  expect(conflict.conflict).toMatchObject({
    from: "2026-01-01",
    until: "2026-06-30",
  });
  expect(await claimsOf(2026)).toHaveLength(1);
  // Correcting that claim replaces it in the same write.
  const replaced = conflict.conflict!.claim_id;
  const half = await forecasted("2026-01-01", "2026-06-30", replaced);
  expect(viewOf(await claim(half, replaced), claimReused).kind).toBe("saved");
  const after = await claimsOf(2026);
  expect(after.filter((found) => found.effective)).toHaveLength(1);
  expect(after.find((found) => found.claim_id === replaced)).toMatchObject({
    effective: false,
  });
  const events = await eventsOf(port, "furgoneta");
  expect(events.at(-1)?.type_key).toBe("claim_recorded");
  expect(events.at(-1)?.replaces_sequence).not.toBeNull();
});

test("a forecast is refused with a reason where the year cannot be worked out, and a free method asks for its amount", async () => {
  const port = portOf();
  const forecast = (id: string, from: string, until: string) =>
    draftedCall(
      port,
      FORECAST,
      {
        asset_id: id,
        covered_from: from,
        covered_until: until,
        requested_free_amount: null,
        supersedes_claim_id: null,
      },
      false,
    );
  const reason = async (id: string, from: string, until: string) =>
    refusalIn(await forecast(id, from, until)).reasonKey;
  expect(await reason("furgoneta", "2027-01-01", "2027-12-31")).toBe(
    "projected_authority",
  );
  expect(await reason("escaner", "2025-01-01", "2025-12-31")).toBe(
    "opening_history_unknown",
  );
  expect(await reason("furgoneta", "1990-01-01", "1990-12-31")).toBe(
    "year_not_in_plan",
  );
  expect(await reason("furgoneta", "2025-06-01", "2026-06-30")).toBe(
    "span_crosses_years",
  );
  const free = refusalIn(await forecast("prensa", "2024-01-01", "2024-12-31"));
  expect(free.code).toBe(INCOMPLETE);
  expect(free.missing).toEqual(["free_amount"]);
  const options = await optionsOf(port, "claim", {
    asset_id: "prensa",
    tax_year: 2024,
  });
  expect(options.fields.map((field) => field.key)).toContain("free_amount");
  const plain = await optionsOf(port, "claim", {
    asset_id: "furgoneta",
    tax_year: 2025,
  });
  expect(plain.fields.map((field) => field.key)).not.toContain("free_amount");
  // The span starts from what can still be claimed.
  expect(plain.fields.find((field) => field.key === "from")?.current).toBe(
    "2025-01-01",
  );
});

test("the admitted shapes are still answered for an element made through the admitted operations", async () => {
  const port = portOf();
  await port.submit(CREATE, {
    revision: {
      asset_id: "legacy-1",
      revision_number: 1,
      acquisition: {
        observed_transaction_id: "a".repeat(64),
        invoice_evidence_id: "b".repeat(64),
        evidence_fingerprint: "c".repeat(64),
      },
      acquisition_shape: "purchase",
      asset_kind: "tangible",
      basis: {
        stage: "acquisition",
        basis_amount: { decimal: "1000" },
        non_deductible_iva: { decimal: "0" },
      },
      in_service_date: "2025-03-01",
      opening_history: { status: "complete" },
      acquired_condition: "new",
      amortization: { regime: "linear", method: "linear_table" },
    },
  });
  const legacy = await port.submit(FORECAST, {
    asset_id: "legacy-1",
    covered_from: "2025-03-01",
    covered_until: "2025-12-31",
  });
  // The admitted answer carries the profile, which the drafted one does not.
  expect(legacy).toMatchObject({
    kind: "refused",
    detail: { profile_id: expect.any(String) },
  });
});
