import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import {
  currentDescriptor,
  descriptorLanded,
  INCOMPLETE,
  purchaseValues,
} from "../src/components/ledger/assets/assetWrites";
import { type FormOptions } from "../src/shell/ledgerSetup";
import { LEDGER_DEFINITIONS, type LedgerResult } from "../src/shell/ledger";
import { ledgerClassOf } from "../src/dev/ledgerClassesFixture";
import {
  REGISTER_YEARS,
  SCENARIO_ELEMENTS,
  TABLE_GROUPS,
  formOptionsFor,
  scenarioPaymentId,
} from "../src/dev/assetsRegister";
import { servedEditionOf, servedSupport } from "../src/dev/servedYearAuthority";

import {
  beyondHorizon,
  lastAuthored,
  LIST,
  PLAN,
  TIMELINE,
  OPTIONS,
  CANDIDATES,
  DESCRIBE,
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
  refused,
  registerOf,
  listOf,
  planOf,
  eventsOf,
  newRequest,
  NEW_ELEMENT,
} from "./support/assetContract";

// The Assets tab's operations against the scenario register: what the host
// admits, what the register lists and plans, the timeline, the options and
// purchases, and the simple writes.

// ---- The operations ---------------------------------------------------------

test("the host admits every operation the tab uses, and the scenario classes each as the host does", () => {
  const used = [
    LIST,
    PLAN,
    TIMELINE,
    OPTIONS,
    CANDIDATES,
    DESCRIBE,
    DISPOSE,
    FORECAST,
    CLAIM,
    CREATE,
    CORRECT,
    INSPECT,
    HANDOFF,
    CALCULATE,
  ];
  for (const id of used)
    expect(LEDGER_DEFINITIONS as readonly string[], id).toContain(id);
  for (const id of [DESCRIBE, DISPOSE, CREATE, CORRECT, CLAIM])
    expect(ledgerClassOf(id as never), id).toBe("write");
  for (const id of [
    LIST,
    PLAN,
    TIMELINE,
    OPTIONS,
    CANDIDATES,
    FORECAST,
    INSPECT,
    HANDOFF,
    CALCULATE,
  ])
    expect(ledgerClassOf(id as never), id).toBe("read");
});

test("an operation that is not admitted is refused", async () => {
  await expect(
    portOf().submit("ledger.actividad-asset.unlisted" as never, {} as never),
  ).rejects.toMatchObject({ code: "not_admitted" });
});

test("a write whose settlement was not seen is held by the host as for any write, and a read is not", async () => {
  const port = portOf("unknown");
  const failure = await port
    .submit(DESCRIBE, {
      asset_id: "taladro",
      descriptor: {
        name: "Taladro",
        serial_number: null,
        description: null,
        document_kind: null,
        document_number: null,
        supplier_name: null,
        supplier_tax_id: null,
      },
    })
    .then(
      () => null,
      (error: { code: string; operation_id: string | null }) => error,
    );
  expect(failure?.code).toBe("unknown");
  expect((await port.observe(failure!.operation_id!)).kind).toBe("settled");
  expect((await port.submit(LIST, {})).kind).toBe("settled");
});

// ---- The seeded register and the law -------------------------------------------

test("the list states the backend's fields, and the years on offer span the register", async () => {
  const rows = await listOf(portOf());
  expect(rows.map((row) => row.asset_id)).toEqual(
    SCENARIO_ELEMENTS.map((seed) => seed.id).sort(),
  );
  for (const row of rows) {
    // The remedy sentence and its language are served together, and only for a row with a remedy to word.
    const served = Object.keys(row).filter(
      (key) => key === "opening_remedy_words" || key === "words_language",
    );
    expect(served.length === 0 || served.length === 2, row.asset_id).toBe(true);
    expect(
      Object.keys(row)
        .filter(
          (key) => key !== "opening_remedy_words" && key !== "words_language",
        )
        .sort(),
      row.asset_id,
    ).toEqual(
      [
        "accumulated",
        "asset_id",
        "asset_kind",
        "basis",
        "default_claim_year",
        "disposal",
        "findings",
        "in_service_date",
        "method",
        "name",
        "opening_remedy_field_key",
        "pending",
        "pending_applies",
        "projected_years",
        "revision_number",
        "serial_number",
        "state",
        "years",
      ].sort(),
    );
    expect(["material", "intangible"]).toContain(row.asset_kind);
    expect(["in_service", "fully_amortized", "out_of_service"]).toContain(
      row.state,
    );
  }
  // The years on offer are the ones the register recorded.
  expect((await registerOf(portOf())).years).toEqual(REGISTER_YEARS);
  // An element with no recorded description is listed without a name.
  expect(rows.find((row) => row.asset_id === "herramienta")?.name).toBeNull();
  // An opening history never stated leaves the amounts unknown, never zero.
  const unknown = rows.find((row) => row.asset_id === "estanteria")!;
  expect(unknown.accumulated).toBeNull();
  expect(unknown.pending).toBeNull();
});

test("a plan states every absence with its figure null, and the years the tables are carried forward as projected", async () => {
  const port = portOf();
  for (const seed of SCENARIO_ELEMENTS) {
    const rows = await planOf(port, seed.id);
    expect(rows.map((row) => row.tax_year)).toEqual(
      [...rows.map((row) => row.tax_year)].sort((a, b) => a - b),
    );
    for (const row of rows) {
      if (row.absence !== null)
        expect(row.planned, `${seed.id} ${row.tax_year}`).toBeNull();
      if (row.edition)
        expect(row.edition, `${seed.id} ${row.tax_year}`).toEqual(
          servedEditionOf(row.tax_year),
        );
    }
  }
  const projected = (await planOf(port, "licencia")).find(
    (row) => row.tax_year === beyondHorizon,
  )!;
  expect(projected.edition).toEqual(servedEditionOf(beyondHorizon));
  expect(projected.edition!.projected).toBe(true);
});

test("a plan past the maximum period states it, with the date it ended", async () => {
  const port = portOf();
  const rows = await planOf(port, "cristaleria");
  const elapsed = rows.find((row) => row.absence === "period_elapsed")!;
  expect(elapsed.planned).toBeNull();
  expect(elapsed.claim_state).toBe("not_due");
  expect(elapsed.absence_reason_key).toBe(
    "ledger.actividad_asset.errors.amortization_period_elapsed",
  );
  const limits = SCENARIO_ELEMENTS.find(
    (seed) => seed.id === "cristaleria",
  )!.limits;
  // The day it ended is the last day it covers, one before the boundary the
  // schedule works to, and it arrives as a date.
  expect(limits.maximum_period_last_day).toBe("2025-12-31");
  expect(limits.maximum_period_ends_on).toBe("2026-01-01");
  expect(elapsed.absence_reason_facts).toEqual([
    { key: "ended_on", value: limits.maximum_period_last_day, kind: "date" },
  ]);
  const forecast = await refused(
    port.submit(
      FORECAST as never,
      {
        asset_id: "cristaleria",
        covered_from: "2026-01-01",
        covered_until: "2027-01-01",
        requested_free_amount: null,
        supersedes_claim_id: null,
      } as never,
    ),
  );
  expect(forecast.detail.refusal).toMatchObject({
    code: "REFUSED_ACTIVIDAD_ASSET_UNSUPPORTED",
    reason_key: "ledger.actividad_asset.errors.amortization_period_elapsed",
    reason_facts: [
      { key: "ended_on", value: limits.maximum_period_last_day, kind: "date" },
    ],
  });
});

test("the plan states the limits of the election, or why it has none", async () => {
  const port = portOf();
  const table = await settled<LedgerResult<typeof PLAN>>(
    port.submit(PLAN, { asset_id: "furgoneta" }),
  );
  expect(table.limits).toMatchObject({
    class_key: "transporte-externo",
    not_table_bound: null,
    maximum_period_ends_on: "2037-04-01",
  });
  const free = await settled<LedgerResult<typeof PLAN>>(
    port.submit(PLAN, { asset_id: "taladro" }),
  );
  expect(free.limits).toMatchObject({
    class_key: null,
    not_table_bound: "free_election",
  });
  const missing = await settled<LedgerResult<typeof PLAN>>(
    port.submit(PLAN, { asset_id: "estanteria" }),
  );
  expect(missing.limits).toMatchObject({
    not_table_bound: "authority_unavailable",
    unavailable_reason_key:
      "ledger.actividad_asset.errors.opening_history_missing",
  });
  const unknown = await refused(port.submit(PLAN, { asset_id: "nobody" }));
  expect(unknown.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.asset_not_found",
  );
});

// ---- The timeline -----------------------------------------------------------

test("a timeline is ordered, names its origin and what each claim is used by", async () => {
  const port = portOf();
  for (const seed of SCENARIO_ELEMENTS) {
    const events = await eventsOf(port, seed.id);
    expect(events.map((event) => event.sequence)).toEqual(
      events.map((_, at) => at + 1),
    );
    const claims = seed.rows.flatMap((row) =>
      row.claims.map((claim) => claim.claim_id),
    );
    expect(
      events
        .filter((event) => event.kind === "claim")
        .map((event) => event.record_id)
        .sort(),
    ).toEqual([...claims].sort());
    for (const event of events) {
      expect(["revision", "claim", "descriptor", "baja"]).toContain(event.kind);
      expect(event.affects_calculation).toBe(event.kind !== "descriptor");
      expect(event.claim === null).toBe(event.kind !== "claim");
    }
  }
  const stale = (await eventsOf(port, "servidor")).filter(
    (event) => event.claim,
  )[0]!;
  expect(stale.claim).toMatchObject({
    matches_current_schedule: false,
    stale_reason: "revision_changed",
  });
  expect(
    (await listOf(port)).find((row) => row.asset_id === "servidor")?.findings
      .stale,
  ).toBe(1);
});

// ---- Options and purchases --------------------------------------------------

test("the options are the registry's methods and table classes for the kind and year", async () => {
  const port = portOf();
  const options = (
    await settled<LedgerResult<typeof OPTIONS>>(
      port.submit(OPTIONS, {
        asset_kind: "material",
        tax_year: lastAuthored,
      }),
    )
  ).options!;
  // Only the methods whose facts a form can state in full are offered, each
  // with the facts it takes.
  const recorded = formOptionsFor("material", lastAuthored)!;
  expect(options.methods).toEqual(recorded.methods);
  expect(options.methods.length).toBeGreaterThan(0);
  expect(
    (options as FormOptions).method_facts!.map((found) => found.method),
  ).toEqual(options.methods);
  expect(options.table_groups).toEqual(recorded.table_groups);
  expect(options.edition).toEqual(servedEditionOf(lastAuthored));
  expect(options.edition.projected).toBe(false);
  const later = (
    await settled<LedgerResult<typeof OPTIONS>>(
      port.submit(OPTIONS, {
        asset_kind: "intangible",
        tax_year: beyondHorizon,
      }),
    )
  ).options!;
  expect(later.edition.projected).toBe(true);
  expect(later.table_groups.map((group) => group.class_key)).toEqual(
    TABLE_GROUPS.intangible!.map((group) => group.class_key),
  );
  const before = await refused(
    port.submit(OPTIONS, {
      asset_kind: "material",
      tax_year: servedSupport.floor - 1,
    }),
  );
  expect(before.detail.refusal).toMatchObject({
    reason_key: "ledger.actividad_asset.errors.tax_year_without_edition",
    reason_facts: [{ key: "tax_year", value: String(servedSupport.floor - 1) }],
  });
});

test("a purchase states what the ledger knows and leaves the rest null, and one used by an element is no longer offered", async () => {
  const port = portOf();
  const offered = (
    await settled<LedgerResult<typeof CANDIDATES>>(port.submit(CANDIDATES, {}))
  ).candidates!;
  // The form takes each figure from what the ledger knows of the payment and
  // leaves what it does not know null; the figures themselves are the
  // register's, read from its own account of the payment.
  const known = offered.find(
    (found) => found.transaction_id === scenarioPaymentId("t-portatil"),
  )!;
  const silent = offered.find(
    (found) => found.transaction_id === scenarioPaymentId("t-efectivo"),
  )!;
  expect(known.non_deductible_iva_state).toBe("known");
  expect(purchaseValues(known)).toEqual({
    basis_amount: known.taxable_base!.decimal,
    non_deductible_iva: known.non_deductible_iva!.decimal,
  });
  expect(silent.non_deductible_iva_state).toBe("unknown");
  expect(silent.taxable_base).toBeNull();
  expect(purchaseValues(silent)).toEqual({
    basis_amount: null,
    non_deductible_iva: null,
  });
  expect(purchaseValues(undefined)).toEqual({
    basis_amount: null,
    non_deductible_iva: null,
  });
  const noConversion = offered.find(
    (found) => found.transaction_id === scenarioPaymentId("t-monitor"),
  )!;
  expect(noConversion.currency).not.toBe("EUR");
  expect(noConversion.paid_in_euro).toBeNull();
  await port.submit(
    CREATE,
    (await newRequest(port, NEW_ELEMENT, "made-1"))! as never,
  );
  const after = (
    await settled<LedgerResult<typeof CANDIDATES>>(port.submit(CANDIDATES, {}))
  ).candidates!;
  expect(
    after.some(
      (found) => found.transaction_id === scenarioPaymentId("t-portatil"),
    ),
  ).toBe(false);
});

// ---- Writes -----------------------------------------------------------------

test("describing appends a description and leaves every earlier event as it was", async () => {
  const port = portOf();
  const before = await eventsOf(port, "furgoneta");
  const done = await settled<LedgerResult<typeof DESCRIBE>>(
    port.submit(DESCRIBE, {
      asset_id: "furgoneta",
      descriptor: {
        name: "Furgoneta de reparto",
        serial_number: "FR-2023-0114",
        description: "Furgoneta eléctrica",
        document_kind: "invoice",
        document_number: "F-8841",
        supplier_name: null,
        supplier_tax_id: null,
      },
    }),
  );
  expect(done.outcome).toBe("succeeded");
  const after = await eventsOf(port, "furgoneta");
  expect(after.slice(0, before.length)).toEqual(before);
  const added = after.at(-1)!;
  expect(added).toMatchObject({
    kind: "descriptor",
    affects_calculation: false,
    origin: "ledger.actividad-asset.describe",
  });
  expect(added.changes.map((change) => change.field)).toEqual([
    "description",
    "document_kind",
    "document_number",
  ]);
  expect(currentDescriptor(after)).toMatchObject({
    name: "Furgoneta de reparto",
    description: "Furgoneta eléctrica",
    document_kind: "invoice",
  });
  expect(descriptorLanded(after, 2)).toBe("saved");
  expect(descriptorLanded(after, 3)).toBe("not_saved");
});

test("a refused or incomplete write changes nothing and names what to fill in", async () => {
  const port = portOf();
  const before = await eventsOf(port, "taladro");
  const incomplete = await refused(
    port.submit(DESCRIBE, {
      asset_id: "taladro",
      descriptor: {
        name: "",
        serial_number: null,
        description: null,
        document_kind: null,
        document_number: null,
        supplier_name: null,
        supplier_tax_id: null,
      },
    }),
  );
  expect(incomplete.detail.refusal).toMatchObject({
    code: INCOMPLETE,
    precondition_verdict: { missing_field_keys: ["name"] },
  });
  const unknown = await refused(
    port.submit(DESCRIBE, {
      asset_id: "nobody",
      descriptor: {
        name: "x",
        serial_number: null,
        description: null,
        document_kind: null,
        document_number: null,
        supplier_name: null,
        supplier_tax_id: null,
      },
    }),
  );
  expect(unknown.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.asset_not_found",
  );
  expect(await eventsOf(port, "taladro")).toEqual(before);
  await expect(
    port.submit(DESCRIBE, {
      asset_id: "taladro",
      descriptor: {
        name: "x",
        serial_number: null,
        description: null,
        document_kind: null,
        document_number: null,
        supplier_name: null,
        supplier_tax_id: null,
      },
      // @ts-expect-error a field the contract does not have
      proceeds: "1",
    }),
  ).rejects.toMatchObject({ code: "refused", reason: "invalid" });
});
