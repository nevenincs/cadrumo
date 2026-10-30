import { expect, test } from "@playwright/test";
import {
  isProvisionalOperation,
  PROVISIONAL_OPERATIONS,
  submitProvisional,
  type PlanRow,
  type TimelineEvent,
} from "../src/components/ledger/assets/assetsContract";
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
