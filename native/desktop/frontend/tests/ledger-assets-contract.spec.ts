import { expect, test } from "@playwright/test";
import {
  claimLanded,
  claimReused,
  correctionLanded,
  currentDescriptor,
  describeRequest,
  descriptorLanded,
  elementLanded,
  forecastRequest,
  handoffRequest,
  INCOMPLETE,
  missingLabels,
  purchaseValues,
  refusalOf,
  refusalWord,
  claimInTheWay,
  CLAIMS_OVERLAP,
  staleClaims,
  viewOf,
} from "../src/components/ledger/assets/assetWrites";
import {
  answer,
  claimFields,
  claimSpans,
  factKey,
  factsOf,
  fieldsFor,
  formKeyOf,
  FURTHER_PURCHASE,
  FURTHER_SHAPE,
  initialOf,
  parseField,
  undrawableFacts,
  unlabelledFacts,
  type FormField,
} from "../src/components/ledger/assets/assetFields";
import {
  type ActivityAssetListResult as AssetListResult,
  type AssetListRow,
  type PlanRow,
  type TimelineEvent,
  type FormOptions,
} from "../src/shell/ledgerSetup";
import {
  ASSET_FAMILY,
  ASSET_REASON_FAMILY,
  changeFieldWord,
  COUNT_ICON,
  COUNT_KINDS,
  keyedText,
  reasonText,
  refusalText,
  tokenWord,
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
  changeValueText,
  nothingOpen,
  recordedMark,
} from "../src/components/ledger/assets/planWords";
import type { SetupCall } from "../src/components/ledger/setup/setupModel";
import {
  LEDGER_DEFINITIONS,
  type JsonObject,
  type LedgerPort,
  type LedgerResult,
} from "../src/shell/ledger";
import type { Translate } from "../src/shell/strings";
import { ledgerClassOf } from "../src/dev/ledgerClassesFixture";
import {
  ADMITTED_METHODS,
  ACQUIRED_CONDITIONS,
  BASIS_STAGES,
  FURTHER_ACQUISITION_SHAPES,
  DISPOSAL_REASONS,
  M130_PERIODS,
  OPENING_STATUSES,
  SEED_ELEMENTS,
  TABLE_GROUPS,
} from "../src/dev/assetsSeed";

// The Assets tab's operations and the scenario ledger that answers them. No
// page is opened. The scenario ledger needs a window; a bare one stands in
// for it here. The seeded register is checked against the registry's own
// amortization table and the linear schedule, worked out again here from
// whole cents.

const stand = globalThis as unknown as { window?: unknown };
stand.window = {
  location: { search: "" },
  setTimeout: globalThis.setTimeout,
};
const { ledgerFixture } = await import("../src/dev/ledgerFixture");
const {
  assetFixtureYears,
  SERVED_ACTIVITIES,
  SERVED_METHOD_FACTS,
  SERVED_SHAPES,
} = await import("../src/dev/assetsFixture");

const LIST = "ledger.actividad-asset.list";
const PLAN = "ledger.actividad-asset.plan";
const TIMELINE = "ledger.actividad-asset.timeline";
const OPTIONS = "ledger.actividad-asset.form-options";
const CANDIDATES = "ledger.actividad-asset.acquisition-candidates";
const DESCRIBE = "ledger.actividad-asset.describe";
const DISPOSE = "ledger.actividad-asset.dispose";
const FORECAST = "ledger.actividad-asset.forecast";
const CLAIM = "ledger.actividad-asset.claim";
const CREATE = "ledger.actividad-asset.create";
const CORRECT = "ledger.actividad-asset.correct";
const INSPECT = "ledger.actividad-asset.inspect";
const HANDOFF = "ledger.actividad-asset.filing-handoff";
const CALCULATE = "ledger.actividad-asset.disposal-calculate";

const portOf = (shape: "fixture" | "unknown" = "fixture"): LedgerPort =>
  ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });

/** A changed field of the timeline, as the backend states it. */
const change = (
  field: string,
  after: string | null,
  afterKey: string | null = null,
) => ({
  field,
  field_key: `ledger.actividad_asset.field.${field}`,
  before: null,
  after,
  before_key: null,
  after_key: afterKey,
  before_label: null,
  after_label: null,
});

async function settled<T>(outcome: Promise<{ kind: string }>): Promise<T> {
  const found = (await outcome) as { kind: string; result?: T };
  if (found.kind !== "settled") throw new Error(`not settled: ${found.kind}`);
  return found.result as T;
}

type Refused = {
  kind: "refused";
  reason: string;
  detail: {
    refusal: {
      code: string;
      reason_key: string | null;
      reason_facts: { key: string; value: string }[];
      precondition_verdict: { missing_field_keys: string[] } | null;
    };
  };
};
async function refused(outcome: Promise<unknown>): Promise<Refused> {
  const found = (await outcome) as { kind: string };
  if (found.kind !== "refused") throw new Error(`not refused: ${found.kind}`);
  return found as Refused;
}

const registerOf = (port: LedgerPort) =>
  settled<AssetListResult>(port.submit(LIST, {}));
const listOf = async (port: LedgerPort) =>
  (await settled<AssetListResult>(port.submit(LIST, {})))
    .rows as AssetListRow[];
const planOf = async (port: LedgerPort, id: string) =>
  (
    await settled<LedgerResult<typeof PLAN>>(
      port.submit(PLAN, { asset_id: id }),
    )
  ).rows as PlanRow[];
const eventsOf = async (port: LedgerPort, id: string) =>
  (
    await settled<LedgerResult<typeof TIMELINE>>(
      port.submit(TIMELINE, { asset_id: id }),
    )
  ).events as TimelineEvent[];

// ---- Whole-cent arithmetic, independent of the fixture ----------------------

const cents = (text: string) => BigInt(text.replace(".", ""));
/** round(basis * rate * numerator / denominator) in cents, half up, from the
 * decimal text of the rate. */
function roundedCharge(
  basis: string,
  rate: string,
  numerator: number,
  denominator: number,
): bigint {
  const [whole = "0", fraction = ""] = rate.split(".");
  const scale = 10n ** BigInt(fraction.length);
  const rateScaled = BigInt(whole + fraction);
  const top = cents(basis) * rateScaled * BigInt(numerator);
  const bottom = scale * BigInt(denominator);
  return (top * 2n + bottom) / (bottom * 2n);
}

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
    SEED_ELEMENTS.map((seed) => seed.id).sort(),
  );
  for (const row of rows) {
    expect(Object.keys(row).sort(), row.asset_id).toEqual(
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
  const years = assetFixtureYears();
  expect([...years].sort((a, b) => a - b)).toEqual(years);
  // The first served year is the first the registry supports, even for an
  // element in service before it.
  expect(years[0]).toBe(2022);
  // An element with no recorded description is listed without a name.
  expect(rows.find((row) => row.asset_id === "herramienta")?.name).toBeNull();
  // An opening history never stated leaves the amounts unknown, never zero.
  const unknown = rows.find((row) => row.asset_id === "estanteria")!;
  expect(unknown.accumulated).toBeNull();
  expect(unknown.pending).toBeNull();
});

test("the pending amount is the formula, and a schedule that ended over unclaimed years has not amortized the element", async () => {
  const rows = await listOf(portOf());
  for (const row of rows) {
    if (row.accumulated === null) {
      expect(row.pending, row.asset_id).toBeNull();
      continue;
    }
    const left = cents(row.basis.decimal) - cents(row.accumulated.decimal);
    expect(cents(row.pending!.decimal), row.asset_id).toBe(
      left > 0n ? left : 0n,
    );
  }
  // The glassware's period has elapsed, but two years were never claimed.
  const glass = rows.find((row) => row.asset_id === "cristaleria")!;
  expect(glass.pending!.decimal).toBe("400.00");
  expect(glass.state).toBe("in_service");
  expect(rows.find((row) => row.asset_id === "plotter")!.state).toBe(
    "fully_amortized",
  );
  // A year no edition covers is neither claimed nor missing.
  const compressor = await planOf(portOf(), "compresor");
  const early = compressor.filter((row) => row.tax_year < 2022);
  expect(early.length).toBeGreaterThan(0);
  for (const row of early) expect(row.claim_state).toBe("edition_unavailable");
  const counted = rows.find((row) => row.asset_id === "compresor")!;
  expect(counted.findings.missing).toBe(0);
});

test("every seeded element lies inside its table class's corridor and period", () => {
  for (const seed of SEED_ELEMENTS) {
    const limits = seed.limits;
    if (limits.not_table_bound !== null) continue;
    const groups = TABLE_GROUPS[seed.list.asset_kind]!;
    const group = groups.find((found) => found.class_key === limits.class_key);
    expect(
      group,
      `${seed.id} names a class the table lists for its kind`,
    ).toBeDefined();
    expect(limits.maximum_coefficient).toEqual(group!.maximum_coefficient);
    expect(limits.minimum_coefficient).toEqual(group!.minimum_coefficient);
    expect(limits.maximum_period_years).toEqual(group!.maximum_period_years);
    expect(ADMITTED_METHODS[seed.list.asset_kind]).toContain(seed.list.method);
    const rate = seed.rows.find((row) => row.coefficient !== null)?.coefficient;
    if (rate) {
      // Compared as scaled integers so no rounding enters.
      const scaled = (text: string) => Number(text) * 1_000_000;
      expect(scaled(rate.decimal)).toBeLessThanOrEqual(
        scaled(group!.maximum_coefficient.decimal) + 1,
      );
      expect(scaled(rate.decimal)).toBeGreaterThanOrEqual(
        scaled(group!.minimum_coefficient.decimal) - 1,
      );
    }
    const ends = new Date(`${seed.list.in_service_date}T00:00:00Z`);
    ends.setUTCFullYear(
      ends.getUTCFullYear() + Number(group!.maximum_period_years.decimal),
    );
    expect(limits.maximum_period_ends_on).toBe(ends.toISOString().slice(0, 10));
  }
});

test("a planned figure is the linear charge worked out again from whole cents", () => {
  for (const seed of SEED_ELEMENTS) {
    if (seed.list.method !== "linear") continue;
    // What the opening amount covers is consumed before the first year.
    const effective = seed.rows
      .flatMap((row) => row.claims)
      .filter((claim) => claim.effective)
      .reduce((sum, claim) => sum + cents(claim.amount.decimal), 0n);
    let consumed =
      seed.list.accumulated === null
        ? 0n
        : cents(seed.list.accumulated.decimal) - effective;
    for (const row of seed.rows) {
      const claimed = cents(row.claimed.decimal);
      if (row.planned === null || row.coefficient === null) {
        consumed += claimed;
        continue;
      }
      expect(row.service_days, `${seed.id} ${row.tax_year}`).not.toBeNull();
      const worked = roundedCharge(
        seed.list.basis.decimal,
        row.coefficient.decimal,
        row.service_days!,
        row.calendar_days!,
      );
      const left = cents(seed.list.basis.decimal) - consumed;
      const expected = worked < left ? worked : left;
      expect(cents(row.planned.decimal), `${seed.id} ${row.tax_year}`).toBe(
        expected,
      );
      // A year with an uncovered span consumes the larger of its claims and its charge.
      const planned = cents(row.planned.decimal);
      consumed +=
        row.claimable_intervals.length > 0 && planned > claimed
          ? planned
          : claimed;
    }
  }
});

test("years before the first supported edition state their absence, never an amount", () => {
  for (const seed of SEED_ELEMENTS)
    for (const row of seed.rows) {
      if (row.tax_year >= 2022) continue;
      // The opening amount covers its years; every other year has no edition.
      expect(
        ["edition_unavailable", "covered_by_opening"],
        `${seed.id} ${row.tax_year}`,
      ).toContain(row.absence);
      expect(row.planned).toBeNull();
      expect(row.coefficient).toBeNull();
      expect(row.edition).toBeNull();
      expect(row.claimable_intervals).toEqual([]);
    }
  const plan = (id: string) =>
    SEED_ELEMENTS.find((seed) => seed.id === id)!.rows.filter(
      (row) => row.tax_year < 2022,
    );
  expect(plan("compresor").map((row) => row.absence)).toEqual([
    "edition_unavailable",
    "edition_unavailable",
    "edition_unavailable",
  ]);
  expect(plan("plotter").map((row) => row.absence)).toEqual([
    "covered_by_opening",
    "covered_by_opening",
    "covered_by_opening",
  ]);
});

test("a plan states every absence with its figure null, and the years the tables are carried forward as projected", async () => {
  const port = portOf();
  for (const seed of SEED_ELEMENTS) {
    const rows = await planOf(port, seed.id);
    expect(rows.map((row) => row.tax_year)).toEqual(
      [...rows.map((row) => row.tax_year)].sort((a, b) => a - b),
    );
    for (const row of rows) {
      if (row.absence !== null)
        expect(row.planned, `${seed.id} ${row.tax_year}`).toBeNull();
      if (row.edition) expect(row.edition.projected).toBe(row.tax_year > 2025);
      // What is claimed is the effective claims, to the cent.
      const total = row.claims
        .filter((claim) => claim.effective)
        .reduce((sum, claim) => sum + cents(claim.amount.decimal), 0n);
      expect(cents(row.claimed.decimal), `${seed.id} ${row.tax_year}`).toBe(
        total,
      );
    }
  }
  const projected = (await planOf(port, "licencia")).find(
    (row) => row.tax_year === 2027,
  )!;
  expect(projected.edition).toMatchObject({
    projected: true,
    authored_filing_year: 2025,
  });
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
  const limits = SEED_ELEMENTS.find(
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
  for (const seed of SEED_ELEMENTS) {
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
        tax_year: 2025,
      }),
    )
  ).options!;
  // Only the methods whose facts a form can state in full are offered, each
  // with the facts it takes.
  expect(options.methods).toEqual(
    ADMITTED_METHODS.material!.filter((method) => method !== "approved_plan"),
  );
  expect(
    (options as FormOptions).method_facts!.map((found) => found.method),
  ).toEqual(options.methods);
  expect(options.table_groups).toEqual(TABLE_GROUPS.material);
  expect(options.edition).toEqual({
    revision_id: "2025",
    authored_filing_year: 2025,
    projected: false,
  });
  const later = (
    await settled<LedgerResult<typeof OPTIONS>>(
      port.submit(OPTIONS, {
        asset_kind: "intangible",
        tax_year: 2027,
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
      tax_year: 2021,
    }),
  );
  expect(before.detail.refusal).toMatchObject({
    reason_key: "ledger.actividad_asset.errors.tax_year_without_edition",
    reason_facts: [{ key: "tax_year", value: "2021" }],
  });
});

test("a purchase states what the ledger knows and leaves the rest null, and one used by an element is no longer offered", async () => {
  const port = portOf();
  const offered = (
    await settled<LedgerResult<typeof CANDIDATES>>(port.submit(CANDIDATES, {}))
  ).candidates!;
  const known = offered.find((found) => found.transaction_id === "t-portatil")!;
  const silent = offered.find((found) => found.transaction_id === "t-silla")!;
  expect(purchaseValues(known)).toEqual({
    basis_amount: "900.00",
    non_deductible_iva: "0.00",
  });
  expect(purchaseValues(silent)).toEqual({
    basis_amount: "200.00",
    non_deductible_iva: null,
  });
  expect(purchaseValues(undefined)).toEqual({
    basis_amount: null,
    non_deductible_iva: null,
  });
  const noConversion = offered.find(
    (found) => found.transaction_id === "t-monitor",
  )!;
  expect(noConversion.paid_in_euro).toBeNull();
  await port.submit(
    CREATE,
    (await newRequest(port, NEW_ELEMENT, "made-1"))! as never,
  );
  const after = (
    await settled<LedgerResult<typeof CANDIDATES>>(port.submit(CANDIDATES, {}))
  ).candidates!;
  expect(after.some((found) => found.transaction_id === "t-portatil")).toBe(
    false,
  );
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

// ---- Creating and correcting, from the requests the forms make --------------------

type Options = NonNullable<LedgerResult<typeof OPTIONS>["options"]>;

async function optionsOf(
  port: LedgerPort,
  kind = "material",
): Promise<Options> {
  const read = await settled<LedgerResult<typeof OPTIONS>>(
    port.submit(OPTIONS, { asset_kind: kind, tax_year: 2026 }),
  );
  return read.options!;
}

/** The request the new-element form makes from what is typed in it. */
async function newRequest(
  port: LedgerPort,
  draft: Record<string, string>,
  assetId: string,
) {
  const options = await optionsOf(port, draft.asset_kind ?? "material");
  const candidates = (
    await settled<LedgerResult<typeof CANDIDATES>>(port.submit(CANDIDATES, {}))
  ).candidates!;
  const candidate = candidates.find(
    (found) => found.transaction_id === draft.acquisition,
  );
  const fields = fieldsFor(
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
  const stated = answer(fields, draft, null);
  expect(stated.problems).toEqual({});
  return createRequest(stated.values, {
    assetId,
    regime: options.regime,
    candidate: candidate ?? null,
    base: null,
    options: options as FormOptions,
  });
}

const NEW_ELEMENT = {
  asset_kind: "material",
  name: "Sierra de cinta",
  serial_number: "SC-0412",
  acquisition: "t-portatil",
  acquisition_shape: "primary_purchase",
  in_service_date: "2026-06-15",
  acquired_condition: "new",
  basis_stage: "business_allocated",
  basis_amount: "900.00",
  non_deductible_iva: "0.00",
  prior_allocation_provenance: "allocation booked in the ledger",
  opening_status: "known",
  opening_amount: "0.00",
  method: "linear",
  "amortization.authority_class_key": "maquinaria",
};

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
    send({ opening_amount: "100.00", opening_through: "2025" }),
  );
  expect(early.detail.refusal).toMatchObject({
    reason_key: "ledger.actividad_asset.errors.opening_year_before_in_service",
    reason_facts: [
      { key: "in_service_tax_year", value: "2026", kind: "count" },
      { key: "opening_tax_year", value: "2025", kind: "count" },
    ],
  });
  const outside = await refused(
    send({ "amortization.linear_coefficient": "99" }),
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
  expect(made).toMatchObject({
    name: "Sierra de cinta",
    accumulated: { decimal: "0.00" },
    pending: { decimal: "900.00" },
    revision_number: 1,
  });
  expect(elementLanded(await registerOf(port), "made-2")).toBe("saved");
  // The first year is worked out on the table's maximum coefficient, by days.
  const group = TABLE_GROUPS.material!.find(
    (found) => found.class_key === "maquinaria",
  )!;
  const first = (await planOf(port, "made-2"))[0]!;
  expect(first).toMatchObject({
    tax_year: 2026,
    absence: null,
    service_days: 200,
    calendar_days: 365,
    minimum_complete: true,
  });
  const expected = roundedCharge(
    "900.00",
    group.maximum_coefficient.decimal,
    200,
    365,
  );
  expect(first.planned!.decimal).toBe(
    `${expected / 100n}.${String(expected % 100n).padStart(2, "0")}`,
  );
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
  const request = await newRequest(
    port,
    { ...NEW_ELEMENT, opening_status: "missing", opening_amount: "" },
    "made-3",
  );
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
  const used = {
    acquired_condition: "used",
    "amortization.used_original_price.determination": "expert_valuation",
    "amortization.used_original_price.original_price": "1500.00",
    "amortization.used_original_price.evidence_reference":
      "valuation report of the appraiser",
  };
  const request = (await newRequest(
    port,
    { ...NEW_ELEMENT, ...used },
    "made-4",
  ))!;
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
      tax_year: 2025,
      output_language: "en",
      m130_period: "4T",
    }),
  );
  const projection = handoff.filing_handoff!;
  const effective = (kind: string) =>
    SEED_ELEMENTS.filter((seed) => seed.list.asset_kind === kind).flatMap(
      (seed) =>
        seed.rows
          .filter((row) => row.tax_year === 2025)
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
    expect(projection[key].claim_ids.sort()).toEqual(
      claims.map((claim) => claim.claim_id).sort(),
    );
    expect(cents(projection[key].amount.decimal)).toBe(total);
    expect(projection[key].amount.decimal).not.toBe("0.00");
  }
  expect(projection.material_m100.target_casilla_id).toBe("0208");
  expect(projection.intangible_m100.target_casilla_id).toBe("0227");
  // Every element of the year is behind casilla 02, and the one it cannot work out is named.
  const material130 = projection.material_m130!;
  expect(material130.target_casilla_id).toBe("02");
  expect(material130.unavailable_asset_ids).toEqual(["estanteria"]);
  expect(
    material130.contributions.some(
      (item) => item.asset_id === "furgoneta" && item.claim_id !== null,
    ),
  ).toBe(true);
  const quarter = await settled<LedgerResult<typeof HANDOFF>>(
    port.submit(HANDOFF, {
      tax_year: 2025,
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
  const long = await limitsOf("furgoneta");
  expect(long.legal_citations.length).toBeGreaterThanOrEqual(10);
  expect(long.legal_citations_complete).toBe(true);
  expect(long.legal_citations[0]).toEqual({
    text: "Ley 35/2006, art. 28",
    permalink: "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28",
  });
  for (const citation of long.legal_citations)
    expect(citation.permalink).toMatch(/^https:\/\/www\.boe\.es\//);
  const partial = await limitsOf("herramienta");
  expect(partial.legal_citations_complete).toBe(false);
  expect(partial.legal_citations.length).toBeGreaterThan(0);
  expect((await limitsOf("estanteria")).legal_citations).toEqual([]);
  expect("legal_references" in long).toBe(false);
});

test("a date among the facts of a reason is worded for the language of the interface", () => {
  const strings: Record<string, string> = {
    [`${ASSET_REASON_FAMILY}amortization_period_elapsed`]:
      "Ended on {ended_on}.",
  };
  const translate = (locale: string) =>
    Object.assign(
      (key: string, values?: Record<string, string | number>) =>
        (strings[key] ?? key).replace(/\{(\w+)\}/g, (_, name: string) =>
          String(values?.[name] ?? `{${name}}`),
        ),
      { locale },
    ) as unknown as Translate;
  const facts = [
    { key: "ended_on", value: "2025-12-31", kind: "date" as const },
  ];
  const english = reasonText(
    translate("en"),
    `${ASSET_REASON_FAMILY}amortization_period_elapsed`,
    facts,
  );
  const spanish = reasonText(
    translate("es"),
    `${ASSET_REASON_FAMILY}amortization_period_elapsed`,
    facts,
  );
  expect(english).not.toContain("2025-12-31");
  expect(spanish).not.toContain("2025-12-31");
  expect(english).toContain("2025");
  expect(english).not.toBe(spanish);
});

test("a fact of a reason is drawn by its kind: a year as a count is never grouped, an amount to the cent, a percent as a percentage", () => {
  const key = `${ASSET_REASON_FAMILY}claim_year_beyond_registry`;
  const strings: Record<string, string> = {
    [key]: "{tax_year} {amount} {rate} {method}",
  };
  const translate = (locale: string) =>
    Object.assign(
      (name: string, values?: Record<string, string | number>) =>
        (strings[name] ?? name).replace(/\{(\w+)\}/g, (_, found: string) =>
          String(values?.[found] ?? `{${found}}`),
        ),
      { locale },
    ) as unknown as Translate;
  const facts = [
    { key: "tax_year", value: "2026", kind: "count" as const },
    { key: "amount", value: "12345.5", kind: "amount" as const },
    { key: "rate", value: "0.125", kind: "percent" as const },
    { key: "method", value: "linear", kind: "text" as const },
  ];
  for (const locale of ["en", "es", "ca", "hu"]) {
    const said = reasonText(translate(locale), key, facts)!;
    // Digits of a count are never grouped in any language.
    expect(said.startsWith("2026 "), locale).toBe(true);
    expect(said.endsWith(" linear"), locale).toBe(true);
    // The amount is drawn for the language, not as it was stated.
    expect(said, locale).not.toContain("12345.5");
    expect(said, locale).toContain(locale === "en" ? "12.5%" : "12,5%");
  }
  // A text stands as it is, even one that looks like a date or a number.
  expect(
    reasonText(translate("en"), key, [
      { key: "tax_year", value: "2026-01-01", kind: "text" },
      { key: "amount", value: "1", kind: "text" },
      { key: "rate", value: "2", kind: "text" },
      { key: "method", value: "m", kind: "text" },
    ]),
  ).toBe("2026-01-01 1 2 m");
});

const sale = {
  disposal_date: "2025-06-30",
  reason: "sale",
  proceeds: { decimal: "9000.00" },
  transmission_costs: { decimal: "150.00" },
  market_value: null,
  prior_free_depreciation_regime: null,
  later_affectation_on: null,
};
test("a baja is judged by the backend, which refuses by key and facts", async () => {
  const port = portOf();
  const dispose = (disposal: object, id = "furgoneta") =>
    port.submit(DISPOSE, { asset_id: id, disposal } as never);
  const reasonOf = async (disposal: object) => {
    const found = await refused(dispose(disposal));
    return [found.detail.refusal.code, found.detail.refusal.reason_key];
  };
  expect(await reasonOf({ ...sale, disposal_date: "2020-01-01" })).toEqual([
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
  expect((await planOf(port, "furgoneta")).at(-1)!.tax_year).toBe(2025);
  const event = (await eventsOf(port, "furgoneta")).at(-1)!;
  expect(event).toMatchObject({ kind: "baja", affects_calculation: true });
  expect(event.changes).toEqual([
    ...[
      ["disposal.disposal_date", "2025-06-30"],
      ["disposal.reason", "sale"],
      ["disposal.proceeds", "9000.00"],
      ["disposal.transmission_costs", "150.00"],
    ].map(([field, after]) => ({
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
    reason_facts: [{ key: "disposal_date", value: "2025-06-30" }],
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
  expect(preview.years.at(-1)).toMatchObject({ tax_year: 2026 });
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
    disposal_date: "2025-06-30",
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
  const ask = (extra: object) =>
    port.submit(FORECAST, {
      asset_id: "furgoneta",
      covered_from: "2026-07-01",
      covered_until: "2027-01-01",
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
  // The rest of the year, worked out again from whole cents.
  const annual = roundedCharge("24000.00", "0.12", 1, 1);
  const upTo = (n: number) => roundedCharge("24000.00", "0.12", n, 365);
  expect(annual).toBe(288000n);
  expect(cents(forecast.amount.decimal)).toBe(upTo(365) - upTo(181));
  expect(forecast.service_days).toBe(184);
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
    (row) => row.tax_year === 2026,
  )!;
  expect(year).toMatchObject({
    claim_state: "claimed",
    claimable_intervals: [],
  });
  expect(year.claims.filter((found) => found.effective)).toHaveLength(2);
  expect(cents(year.claimed.decimal)).toBe(cents("2880.00"));
  const overlap = (await refused(
    ask({ covered_from: "2026-01-01", covered_until: "2027-01-01" }),
  )) as Refused;
  expect(overlap.detail.refusal).toMatchObject({
    code: "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT",
    reason_key: "ledger.actividad_asset.errors.claims_overlap",
  });
  const crossing = await refused(
    ask({ covered_from: "2026-07-01", covered_until: "2027-02-01" }),
  );
  expect(crossing.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.covered_interval_outside_tax_year",
  );
  expect(
    claimLanded(await planOf(port, "furgoneta"), {
      tax_year: 2026,
      from: "2026-07-01",
      until: "2027-01-01",
      amount: forecast.amount.decimal,
    }),
  ).toBe("saved");
});

test("a free method asks for its amount, and a claim replaces the one it corrects", async () => {
  const port = portOf();
  const ask = (extra: object) =>
    port.submit(FORECAST, {
      asset_id: "impresora",
      covered_from: "2026-09-01",
      covered_until: "2027-01-01",
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
  const forecast = (await port.submit(FORECAST, {
    asset_id: "made-1",
    covered_from: "2026-06-15",
    covered_through: "2026-12-31",
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
      disposal: { ...sale, disposal_date: "2026-06-30" },
    } as never),
  );
  expect(read.calculation!.minimum).toBeNull();
  expect(
    read.calculation!.findings.filter(
      (finding) => finding.kind === "minimum_unresolved",
    ).length,
  ).toBe(3);
  const seed = SEED_ELEMENTS.find((found) => found.id === "plotter")!;
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
  ).toEqual([2019, 2020, 2021]);
  // The reduction and the net value stay numbers.
  expect(seed.disposal!.reduction).not.toBeNull();
  expect(seed.disposal!.net_value).not.toBeNull();
});

test("a claim past the registry's last year is refused with the years it can take, and a replayed replaced claim is a conflict", async () => {
  const port = portOf();
  const forecast = (await port.submit(FORECAST, {
    asset_id: "furgoneta",
    covered_from: "2027-01-01",
    covered_through: "2027-12-31",
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
      { key: "last_admitted_year", value: "2026" },
      { key: "tax_year", value: "2027" },
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
      disposal: { ...sale, later_affectation_on: "2024-01-01" },
    } as never),
  );
  expect(late.detail.refusal.reason_key).toBe(
    "ledger.actividad_asset.errors.later_affectation_out_of_order",
  );
});

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
  expect(parseField(field("date"), "2026-02-30").kind).toBe("refused");
  expect(parseField(field("date"), "2026-02-28")).toEqual({
    kind: "value",
    value: "2026-02-28",
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
    revision: SEED_ELEMENTS.find(
      (seed) => seed.id === "servidor",
    )!.revisions.at(-1)!.revision as never,
    tokens: () => [],
    options: null,
  };
  const initial = initialOf(context, fieldsFor(context, {}));
  const fields = fieldsFor(context, initial);
  expect(initial).toMatchObject({
    method: row.method,
    basis_amount: row.basis.decimal,
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
      disposal_date: "2026-09-30",
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
  expect(recorded).toMatchObject({ disposal_date: "2026-09-30" });
  const row = (await listOf(port)).find(
    (found) => found.asset_id === "taladro",
  )!;
  expect(row.disposal).toMatchObject({
    disposal_date: "2026-09-30",
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
  ).toMatchObject({ disposal_date: "2026-09-30" });
  const latest = await inspect("taladro");
  expect(latest.revision.disposal).toEqual(recorded);

  // A baja is changed by stating another, and removed by stating none.
  const moved = bajaRequest(latest, {
    disposal_date: "2026-06-30",
    reason: "sale",
    proceeds: { decimal: "100.00" },
    transmission_costs: { decimal: "0.00" },
    market_value: null,
    prior_free_depreciation_regime: null,
    later_affectation_on: null,
  })!;
  expect(moved.revision).toMatchObject({
    supersedes_revision_id: latest.revision_id,
    disposal: { disposal_date: "2026-06-30" },
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
  ).toMatchObject({ disposal_date: "2026-06-30" });
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

function servidorRow(): AssetListRow {
  return SEED_ELEMENTS.find((seed) => seed.id === "servidor")!.list;
}

test("each act's fields and requests come from the backend's choices", () => {
  const methods = ["linear", "low_value_free"];
  const options: FormOptions = {
    tax_year: 2026,
    asset_kind: "material",
    regime: "normal",
    edition: {
      revision_id: "2025",
      authored_filing_year: 2025,
      projected: true,
    },
    acquisition_shapes: [...SERVED_SHAPES],
    declared_activities: [...SERVED_ACTIVITIES],
    methods,
    method_facts: SERVED_METHOD_FACTS.filter((found) =>
      methods.includes(found.method),
    ),
    table_groups: TABLE_GROUPS.material!.slice(0, 2),
    disposal_reasons: [...DISPOSAL_REASONS],
    basis_stages: [...BASIS_STAGES],
    opening_statuses: [...OPENING_STATUSES],
    acquired_conditions: [...ACQUIRED_CONDITIONS],
    further_acquisition_shapes: [...FURTHER_ACQUISITION_SHAPES],
    m130_periods: [...M130_PERIODS[2026]!],
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
    SERVED_SHAPES,
  );
  expect(choices(classKey).map((choice) => choice.token)).toEqual(
    options.table_groups.map((group) => group.class_key),
  );
  // A table class is drawn by the official name the backend serves with it.
  expect(
    choices(classKey).map((choice) => [choice.family, choice.label]),
  ).toEqual(options.table_groups.map((group) => [null, group.class_label]));
  const plan = SEED_ELEMENTS.find((seed) => seed.id === "furgoneta")!.rows.find(
    (row) => row.tax_year === 2026,
  )!;
  const claim = claimFields(plan, null);
  expect(claim.map((found) => [found.key, found.current])).toEqual([
    ["covered_from", "2026-07-01"],
    ["covered_through", "2026-12-31"],
  ]);
  // The span starts from the backend's own, and is shown by its last day.
  expect(claimSpans(plan, null)).toEqual([
    { from: "2026-07-01", through: "2026-12-31" },
  ]);
  const free = SEED_ELEMENTS.find((seed) => seed.id === "impresora")!.rows[0]!;
  expect(claimFields(free, null).map((found) => found.key)).toEqual([
    "covered_from",
    "covered_through",
    "free_amount",
  ]);
  expect(
    forecastRequest(
      "a",
      {
        covered_from: "2026-01-01",
        covered_through: "2026-06-30",
        free_amount: { decimal: "5.00" },
      },
      "c",
    ),
  ).toEqual({
    asset_id: "a",
    covered_from: "2026-01-01",
    covered_through: "2026-06-30",
    requested_free_amount: { decimal: "5.00" },
    supersedes_claim_id: "c",
  });
  expect(forecastRequest("a", { covered_from: "2026-01-01" }, null)).toBeNull();
  expect(
    forecastRequest("a", { covered_through: "2026-06-30" }, null),
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
    missing: ["name", "basis_amount"],
  });
  expect(refusalOf(null)).toEqual({
    code: null,
    reasonKey: null,
    reasonFacts: [],
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
  expect(
    refusalWord(((key: string) => key) as Translate, {
      reasonKey: null,
      reasonFacts: [],
    }),
  ).toBeNull();
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
    tax_year: 2024,
    from: "2024-01-01",
    until: "2025-01-01",
    amount: "2880",
  };
  // The same number however it is spelled; a different one is not found.
  expect(claimLanded(rows, sent)).toBe("saved");
  expect(claimLanded(rows, { ...sent, amount: "2880.01" })).toBe("not_saved");
  expect(claimLanded(rows, { ...sent, until: "2024-06-30" })).toBe("not_saved");
  expect(claimLanded(rows, { ...sent, tax_year: 1901 })).toBe("untold");
  expect(descriptorLanded([], 1)).toBe("not_saved");
});

// ---- Words ------------------------------------------------------------------

/** A translator that knows only the keys it is given, as the shell's does. */
const words =
  (table: Record<string, string>): Translate =>
  (key, values) => {
    const template = table[key] ?? key;
    return values
      ? template.replace(/\{(\w+)\}/g, (whole, name: string) =>
          name in values ? String(values[name]) : whole,
        )
      : template;
  };

test("a reason is said by its catalogue key with its facts, and anything else reads as the generic word", () => {
  const t = words({
    [`${ASSET_REASON_FAMILY}amortization_period_elapsed`]:
      "Ended on {ended_on}.",
    [`${ASSET_REASON_FAMILY}elected_coefficient_out_of_range`]:
      "{elected} is outside [{minimum}, {maximum}].",
    "desktop.ledger.assets.refused": "Not accepted.",
    "desktop.ledger.assets.unrecognised": "Not recognised",
    [`${ASSET_FAMILY.method}linear`]: "Linear",
  });
  const elapsed = `${ASSET_REASON_FAMILY}amortization_period_elapsed`;
  expect(
    reasonText(t, elapsed, [
      { key: "ended_on", value: "2025-12-31", kind: "date" },
    ]),
  ).toBe("Ended on Dec 31, 2025.");
  // A fact the sentence needs and was not given: never a raw placeholder.
  expect(reasonText(t, elapsed, [])).toBeNull();
  expect(
    reasonText(t, `${ASSET_REASON_FAMILY}elected_coefficient_out_of_range`, [
      { key: "elected", value: "0.5", kind: "percent" },
      { key: "minimum", value: "0.1", kind: "percent" },
      { key: "maximum", value: "0.2", kind: "percent" },
    ]),
  ).toBe("50% is outside [10%, 20%].");
  // A key the generated strings lack, one outside the family, and none.
  expect(reasonText(t, `${ASSET_REASON_FAMILY}not_generated`)).toBeNull();
  expect(reasonText(t, "tui.ledger.activity_asset.plan")).toBeNull();
  expect(reasonText(t, null)).toBeNull();
  expect(
    refusalText(t, {
      reason_key: `${ASSET_REASON_FAMILY}not_generated`,
      reason_facts: [],
    }),
  ).toBe("Not accepted.");
  expect(refusalText(t, null)).toBe("Not accepted.");
  expect(
    refusalText(t, {
      reason_key: elapsed,
      reason_facts: [{ key: "ended_on", value: "x", kind: "text" }],
    }),
  ).toBe("Ended on x.");
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

test("the list serves the years, and the pane opens on one that has begun", async () => {
  const port = portOf();
  const register = await registerOf(port);
  const served = [
    ...new Set((register.rows ?? []).flatMap((row) => row.years)),
  ].sort((a, b) => a - b);
  expect(register.years).toEqual(served);
  expect(register.years).toEqual(assetFixtureYears());
  // No year before the first supported edition is served.
  expect(Math.min(...register.years)).toBe(2022);
  // Every year of an element is a year of its plan.
  for (const row of register.rows ?? []) {
    const plan = (await planOf(port, row.asset_id)).map(
      (found) => found.tax_year,
    );
    // The years the registry carries tables for, then the estimated ones.
    expect(row.years, row.asset_id).toEqual(
      plan.filter((year) => year >= 2022 && year <= 2026),
    );
    expect(row.projected_years, row.asset_id).toEqual(
      plan.filter((year) => year > 2026),
    );
  }
  expect(
    (register.rows ?? []).some((row) => row.projected_years.length > 0),
  ).toBe(true);
  expect(Math.max(...register.years)).toBe(2026);
  // The year the register opens on is the backend's to serve, never one the
  // computer's clock picks: the latest served year that has begun on the
  // scenario's date.
  expect(register.default_year).toBe(2026);
});

test("a table class is named as the backend serves it, in the options and in the plan", async () => {
  const port = portOf();
  const options = (
    await settled<LedgerResult<typeof OPTIONS>>(
      port.submit(OPTIONS, {
        asset_kind: "material",
        tax_year: 2025,
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
  expect(keyedText(t, null, "2026-01-01")).toBe("2026-01-01");
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
  ).toBe(t("desktop.ledger.assets.timeline.value_changed"));
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
  const outside = {
    ...NEW_ELEMENT,
    acquisition: "",
    acquisition_shape: "acquired_outside_ledger",
    declared_acquisition_date: "2024-11-05",
    declared_activity: "A05",
    acquisition_reference: "Factura 2024-118",
  };
  const request = (await newRequest(port, outside, "made-6"))!;
  expect(request).not.toBeNull();
  expect(request.revision).toMatchObject({
    acquisition_shape: "acquired_outside_ledger",
    acquisition: {
      observed_transaction_id: null,
      observed_lineage_event_id: null,
      invoice_evidence_id: "Factura 2024-118",
      evidence_fingerprint: null,
    },
    further_acquisitions: [],
    declared_acquisition_date: "2024-11-05",
    declared_activity: "A05",
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
    { ...outside, declared_acquisition_date: "2026-07-01" },
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
  const send = async (changes: Record<string, string>, id: string) => {
    const port = portOf();
    const request = await newRequest(port, { ...NEW_ELEMENT, ...changes }, id);
    expect(request, JSON.stringify(changes)).not.toBeNull();
    return {
      request: request!,
      outcome: port.submit(CREATE, request as never),
    };
  };
  const property = {
    basis_stage: "whole_property",
    basis_amount: "1000.00",
    construction_cost: "800.00",
    land_cost: "200.00",
    ownership_mode: "sole",
    ownership_share: "100",
    office_area: "30",
    total_area: "100",
  };
  const made = await send(property, "made-8");
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

  const vehicle = {
    "amortization.authority_class_key": "transporte-externo",
    vehicle_declared: "yes",
    vehicle_category: "passenger_car",
    vehicle_private_use: "none",
    vehicle_in_books: "yes",
    vehicle_evidence: "Libro registro de bienes de inversión",
    vehicle_propulsion: "bev",
  };
  const driven = await send(vehicle, "made-11");
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

  const hours = await send(
    { "amortization.shift_hours_per_day": "16" },
    "made-13",
  );
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
    tax_year: 2026,
    asset_kind: "material",
    regime: "normal",
    edition: {
      revision_id: "2025",
      authored_filing_year: 2025,
      projected: true,
    },
    disposal_reasons: [],
    methods: ["plain", "rows", "unworded"],
    acquisition_shapes: [...SERVED_SHAPES],
    declared_activities: [...SERVED_ACTIVITIES],
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
    (row) => row.tax_year === 2026,
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
  // The names are for acting on, never for saying.
  const t = wordsOf({ [CLAIMS_OVERLAP]: "That period is already recorded." });
  expect(reasonText(t, CLAIMS_OVERLAP, named)).toBe(
    "That period is already recorded.",
  );
  for (const interval of furgoneta.claimable_intervals)
    expect(interval.covered_through < interval.covered_until).toBe(true);
});

// ---- What the backend states and the screens no longer work out -------------

test("a forecast states the last day covered, which the backend turns into its boundary; stating neither or two different days is refused", async () => {
  const port = portOf();
  const ask = (extra: object) =>
    port.submit(FORECAST, {
      asset_id: "furgoneta",
      covered_from: "2026-07-01",
      requested_free_amount: null,
      supersedes_claim_id: null,
      ...extra,
    } as never) as unknown as Promise<{
      result?: { forecast: { amount: { decimal: string } } };
    }>;
  const request = forecastRequest(
    "furgoneta",
    { covered_from: "2026-07-01", covered_through: "2026-12-31" },
    null,
  )!;
  expect(request).not.toHaveProperty("covered_until");
  const through = (await ask({ covered_through: request.covered_through }))
    .result!.forecast;
  const until = (await ask({ covered_until: "2027-01-01" })).result!.forecast;
  expect(through).toMatchObject({
    covered_from: "2026-07-01",
    covered_until: "2027-01-01",
    covered_through: "2026-12-31",
  });
  expect(through.amount).toEqual(until.amount);
  // A shorter span is another forecast, and its last day is the one asked.
  const shorter = (await ask({ covered_through: "2026-09-30" })).result!
    .forecast;
  expect(shorter).toMatchObject({
    covered_until: "2026-10-01",
    covered_through: "2026-09-30",
  });
  expect(cents(shorter.amount.decimal)).toBeLessThan(
    cents(through.amount.decimal),
  );
  await expect(ask({})).rejects.toMatchObject({ reason: "invalid" });
  await expect(
    ask({ covered_until: "2027-01-01", covered_through: "2026-12-30" }),
  ).rejects.toMatchObject({ reason: "invalid" });
});

test("a handoff for a year alone states the Modelo 100 boxes and no Modelo 130 side; a chosen quarter adds it", async () => {
  const port = portOf();
  const alone = handoffRequest(2025, "", "es");
  expect(alone).toEqual({ tax_year: 2025, output_language: "es" });
  const year = await settled<LedgerResult<typeof HANDOFF>>(
    port.submit(HANDOFF, alone),
  );
  expect(year).toMatchObject({ outcome: "succeeded", m130_period: null });
  expect(year.filing_handoff).toMatchObject({
    material_m130: null,
    intangible_m130: null,
  });
  expect(year.filing_handoff!.material_m100.target_casilla_id).toBe("0208");
  expect(year.filing_handoff!.intangible_m100.target_casilla_id).toBe("0227");
  const quarter = handoffRequest(2025, "2T", "es");
  expect(quarter).toEqual({
    tax_year: 2025,
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
  const made = await newRequest(
    keyed,
    {
      ...NEW_ELEMENT,
      acquisition: "",
      acquisition_shape: "acquired_outside_ledger",
      declared_acquisition_date: "2026-01-10",
      declared_activity: SERVED_ACTIVITIES[0]!,
      acquisition_reference: "Factura 2026-118",
    },
    "made-keys",
  );
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

const HANDOFF_WORDS = words({
  "desktop.ledger.assets.handoff_gap_accrued":
    "{name}: nothing from {start} to {end}, {amount} EUR accrued.",
  "desktop.ledger.assets.handoff_gap_free":
    "{name}: nothing from {start} to {end}, left to you.",
  "desktop.ledger.assets.handoff_gap_unavailable":
    "{name}: nothing from {start} to {end}, not worked out.",
  "desktop.ledger.assets.handoff_gap_unnamed": "{count} more periods.",
  "desktop.ledger.assets.handoff_gap_unnamed_one": "1 more period.",
  "desktop.ledger.assets.handoff_free_named": "Free: {names}.",
  "desktop.ledger.assets.handoff_free_count": "Free: {count} elements.",
  "desktop.ledger.assets.handoff_agrarian_named": "Agricultural: {names}.",
  "desktop.ledger.assets.handoff_agrarian_count":
    "Agricultural: {count} elements.",
  "desktop.ledger.assets.handoff_agrarian_count_one":
    "Agricultural: 1 element.",
});

const projection = (
  casilla: string,
  assetKind: string,
  facts: {
    free?: string[];
    agrarian?: string[];
  } = {},
) => ({
  asset_kind: assetKind,
  target_casilla_id: casilla,
  box_name: `Expenses - ${assetKind}`,
  tax_year: 2025,
  amount: { decimal: "0.00" },
  contributions: [],
  unavailable_asset_ids: [],
  free_gap_asset_ids: facts.free ?? [],
  agrarian_excluded_asset_ids: facts.agrarian ?? [],
});

const claims = (casilla: string) => ({
  target_casilla_id: casilla,
  box_name: `Box ${casilla}`,
  tax_year: 2025,
  claim_ids: [],
  amount: { decimal: "0.00" },
});

test("a handoff says what it leaves out by the elements' names, and by their number where a name is missing, never by an id", () => {
  const names = new Map([
    ["asset-aaa", "Laptop"],
    ["asset-bbb", "Printer"],
  ]);
  const handoff: Handoff = {
    material_m100: claims("0208"),
    intangible_m100: claims("0227"),
    m100_gaps: [
      {
        asset_id: "asset-aaa",
        kind: "accrued",
        covered_from: "2025-01-01",
        covered_until: "2025-04-01",
        covered_through: "2025-03-31",
        accrued: { decimal: "412.50" },
      },
      {
        asset_id: "asset-bbb",
        kind: "free_method",
        covered_from: "2025-02-01",
        covered_until: "2025-04-01",
        covered_through: "2025-03-31",
        accrued: null,
      },
      {
        // An accrual that is not stated is never drawn as an amount.
        asset_id: "asset-aaa",
        kind: "accrued",
        covered_from: "2025-04-01",
        covered_until: "2025-05-01",
        covered_through: "2025-04-30",
        accrued: null,
      },
      {
        asset_id: "asset-zzz",
        kind: "unavailable",
        covered_from: "2025-01-01",
        covered_until: "2026-01-01",
        covered_through: "2025-12-31",
        accrued: null,
      },
    ],
    material_m130: projection("02", "material", {
      free: ["asset-aaa", "asset-bbb"],
      agrarian: ["asset-zzz"],
    }),
    intangible_m130: projection("02", "intangible", { free: ["asset-bbb"] }),
  };
  const said = leftOutNotes(HANDOFF_WORDS, "en", handoff, names);
  expect(said).toEqual([
    "Laptop: nothing from Jan 1, 2025 to Mar 31, 2025, 412.50 EUR accrued.",
    "Printer: nothing from Feb 1, 2025 to Mar 31, 2025, left to you.",
    "Laptop: nothing from Apr 1, 2025 to Apr 30, 2025, not worked out.",
    "1 more period.",
    // Both kinds name the element once; one element has no name here.
    "Free: Laptop and Printer.",
    "Agricultural: 1 element.",
  ]);
  expect(said.join(" ")).not.toMatch(/asset-/);
  // A handoff that leaves nothing out says nothing.
  expect(
    leftOutNotes(
      HANDOFF_WORDS,
      "en",
      {
        material_m100: claims("0208"),
        intangible_m100: claims("0227"),
        m100_gaps: [],
        material_m130: null,
        intangible_m130: null,
      },
      names,
    ),
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
    const elapsed = open.filter((year) => year <= 2026);
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
  const baja = { ...sale, disposal_date: "2026-09-30" };
  await settled(
    port.submit(DISPOSE, { asset_id: "taladro", disposal: baja } as never),
  );
  expect(await last("taladro")).toMatchObject({
    kind: "baja",
    event_kind: "baja_recorded",
    effect_date: "2026-09-30",
  });
  const moved = bajaRequest(await inspect("taladro"), {
    ...baja,
    disposal_date: "2026-06-30",
  })!;
  await settled(port.submit(CORRECT, moved as never));
  expect(await last("taladro")).toMatchObject({
    event_kind: "baja_changed",
    effect_date: "2026-06-30",
  });
  expect(
    (await listOf(port)).find((row) => row.asset_id === "taladro"),
  ).toMatchObject({ pending_applies: false });
  await settled(
    port.submit(CORRECT, bajaRequest(await inspect("taladro"), null)! as never),
  );
  expect(await last("taladro")).toMatchObject({
    event_kind: "baja_removed",
    effect_date: "2026-06-30",
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
  return SEED_ELEMENTS.find((seed) => seed.id === id)!.list;
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
    business_use_share: "60",
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
    declared_acquisition_date: "2026-01-10",
    declared_activity: "A01",
    acquisition_reference: "invoice held at the office",
  };
  const keys = (draft: Record<string, string>) =>
    fieldsFor(context, draft).map((found) => found.key);
  // Offered for an element bought outside the ledger and for none other; what
  // the payment is asked once one is picked.
  expect(keys(NEW_ELEMENT)).not.toContain(FURTHER_PURCHASE);
  expect(keys(outside)).toContain(FURTHER_PURCHASE);
  expect(keys(outside)).not.toContain(FURTHER_SHAPE);
  expect(keys({ ...outside, [FURTHER_PURCHASE]: "t-silla" })).toContain(
    FURTHER_SHAPE,
  );
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
  const withPayment = {
    ...outside,
    [FURTHER_PURCHASE]: "t-silla",
    [FURTHER_SHAPE]: "split_payment",
  };
  const request = build(withPayment, "made-6");
  expect(request.revision.further_acquisitions).toEqual([
    {
      shape: "split_payment",
      lineage: {
        observed_transaction_id: "t-silla",
        invoice_evidence_id: "",
        evidence_fingerprint: null,
      },
    },
  ]);
  expect((await port.submit(CREATE, request as never)).kind).toBe("settled");
  // The payment is the element's now, and no longer on offer.
  const left = (
    await settled<LedgerResult<typeof CANDIDATES>>(port.submit(CANDIDATES, {}))
  ).candidates!;
  expect(left.some((found) => found.transaction_id === "t-silla")).toBe(false);
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
  for (const year of [2022, 2026, 2027]) {
    const read = await settled<LedgerResult<typeof OPTIONS>>(
      port.submit(OPTIONS, { asset_kind: "material", tax_year: year }),
    );
    expect(read.options!.m130_periods, String(year)).toEqual(
      M130_PERIODS[year],
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
  for (const seed of SEED_ELEMENTS)
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

test("a year with nothing open says the plan's own reason, the absence's when the refusal gives none, and never blank, each with the entry to fill in where one is served", () => {
  const refusalKey = `${ASSET_REASON_FAMILY}amortization_period_elapsed`;
  const absenceKey = `${ASSET_REASON_FAMILY}opening_history_missing`;
  const t = wordsOf({
    [refusalKey]: "Ended on {ended_on}.",
    [absenceKey]: "The opening amount is not entered.",
    "desktop.ledger.assets.plan.claimable_none": "Nothing left to record",
  });
  const none = {
    claimable_intervals: [],
    claimable_refusal_key: null,
    claimable_refusal_facts: [],
    claimable_refusal_remedy_field_key: null,
    absence_reason_key: null,
    absence_reason_facts: [],
    absence_remedy_field_key: null,
  };
  const field =
    "ledger.actividad_asset.field.opening_history.accumulated_amount";
  const refusal = nothingOpen(t, {
    ...none,
    claimable_refusal_key: refusalKey,
    claimable_refusal_facts: [
      { key: "ended_on", value: "2025-12-31", kind: "date" },
    ],
    claimable_refusal_remedy_field_key: field,
    absence_reason_key: absenceKey,
  })!;
  expect(refusal.why).toContain("2025");
  // The remedy is the one served with the sentence that is said.
  expect(refusal.remedyFieldKey).toBe(field);
  expect(
    nothingOpen(t, {
      ...none,
      absence_reason_key: absenceKey,
      absence_remedy_field_key: field,
    }),
  ).toEqual({
    why: "The opening amount is not entered.",
    remedyFieldKey: field,
  });
  expect(nothingOpen(t, none)).toEqual({
    why: "Nothing left to record",
    remedyFieldKey: null,
  });
  expect(
    nothingOpen(t, {
      ...none,
      claimable_intervals: [
        {
          covered_from: "2026-01-01",
          covered_until: "2027-01-01",
          covered_through: "2026-12-31",
        },
      ],
    }),
  ).toBeNull();
});

test("the handoff says what could not be worked out, by name or by count, in the singular for one", async () => {
  const port = portOf();
  const handoff = (
    await settled<LedgerResult<typeof HANDOFF>>(
      port.submit(HANDOFF, {
        tax_year: 2025,
        output_language: "en",
        m130_period: "4T",
      }),
    )
  ).filing_handoff!;
  const strings = {
    "desktop.ledger.assets.handoff_unavailable_named":
      "Couldn't be worked out, so left out: {names}.",
    "desktop.ledger.assets.handoff_unavailable_count":
      "{count} elements couldn't be worked out, so they are left out.",
    "desktop.ledger.assets.handoff_unavailable_count_one":
      "1 element couldn't be worked out, so it is left out.",
  };
  const t = wordsOf(strings);
  const only = (ids: string[]): Handoff => ({
    ...handoff,
    m100_gaps: [],
    material_m130: {
      ...handoff.material_m130!,
      unavailable_asset_ids: ids,
      free_gap_asset_ids: [],
      agrarian_excluded_asset_ids: [],
    },
    intangible_m130: null,
  });
  const names = new Map([
    ["a", "Van"],
    ["b", "Printer"],
  ]);
  expect(leftOutNotes(t, "en", only(["a", "b"]), names)).toEqual([
    "Couldn't be worked out, so left out: Van and Printer.",
  ]);
  expect(leftOutNotes(t, "en", only(["a", "x", "y"]), names)).toEqual([
    "3 elements couldn't be worked out, so they are left out.",
  ]);
  expect(leftOutNotes(t, "en", only(["x"]), names)).toEqual([
    "1 element couldn't be worked out, so it is left out.",
  ]);
  expect(leftOutNotes(t, "en", only([]), names)).toEqual([]);
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
  const request = (await newRequest(
    port,
    {
      ...NEW_ELEMENT,
      acquired_condition: "new",
      building_construction_date: "2001-01-01",
    },
    "made-cond",
  ))!;
  expect(request.revision).not.toHaveProperty("building_construction_date");
  const built = (await newRequest(
    port,
    {
      ...NEW_ELEMENT,
      acquired_condition: "used",
      building_construction_date: "2001-01-01",
    },
    "made-cond-2",
  ))!;
  expect(built.revision.building_construction_date).toBe("2001-01-01");
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
        [FURTHER_PURCHASE]: "t-silla",
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
      disposal: { ...sale, disposal_date: "2027-03-31" },
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
          tax_year: 2025,
          output_language: language,
          m130_period: "4T",
        } as never),
      )
    ).filing_handoff!;
  const english = await read("en");
  const spanish = await read("es");
  expect(english.material_m100.box_name).not.toBeNull();
  expect(english.material_m100.box_name).not.toBe(
    spanish.material_m100.box_name,
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
