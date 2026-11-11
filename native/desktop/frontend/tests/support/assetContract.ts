import { expect } from "@playwright/test";
import { fieldsFor } from "../../src/components/ledger/assets/assetFields";
import { answer } from "../../src/components/ledger/assets/assetFormValues";
import {
  type ActivityAssetListResult as AssetListResult,
  type AssetListRow,
  type PlanRow,
  type TimelineEvent,
  type FormOptions,
} from "../../src/shell/ledgerSetup";
import { createRequest } from "../../src/components/ledger/assets/assetRevision";
import { type LedgerPort, type LedgerResult } from "../../src/shell/ledger";
import type { Translate } from "../../src/shell/strings";
import {
  DECLARED_ACTIVITIES,
  SCENARIO_TODAY,
  SCENARIO_ELEMENTS,
  creationDraft,
} from "../../src/dev/assetsRegister";
import { fixtureDay } from "../../src/dev/fixtureDates";
import {
  servedEditionOf,
  servedSupport,
} from "../../src/dev/servedYearAuthority";

// What the Assets tab's contract specs share: the operations, the scenario
// ledger that answers them, and readers of its answers. No page is opened. The
// scenario ledger needs a window; a bare one stands in for it here. The
// register's figures are the backend's, recorded from the committed scenario;
// nothing here works one out again. The support envelope, editions and boxes
// are the backend's, read from its recording: the first year past the horizon,
// and the last year with an edition of its own, stand for the years the
// registry projects and the years it reads unprojected.

export const beyondHorizon = servedSupport.horizon + 1;
export const lastAuthored = servedEditionOf(
  servedSupport.horizon,
)!.authored_filing_year;

const stand = globalThis as unknown as { window?: unknown };
stand.window = {
  location: { search: "" },
  setTimeout: globalThis.setTimeout,
};
export const { ledgerFixture } = await import("../../src/dev/ledgerFixture");

// The seeded register reads as of the scenario's date, so its rows are named by
// that date's year and the one before it.
export const scenarioYear = Number(SCENARIO_TODAY.slice(0, 4));
export const priorYear = scenarioYear - 1;

export const LIST = "ledger.actividad-asset.list";
export const PLAN = "ledger.actividad-asset.plan";
export const TIMELINE = "ledger.actividad-asset.timeline";
export const OPTIONS = "ledger.actividad-asset.form-options";
export const CANDIDATES = "ledger.actividad-asset.acquisition-candidates";
export const DESCRIBE = "ledger.actividad-asset.describe";
export const DISPOSE = "ledger.actividad-asset.dispose";
export const FORECAST = "ledger.actividad-asset.forecast";
export const CLAIM = "ledger.actividad-asset.claim";
export const CREATE = "ledger.actividad-asset.create";
export const CORRECT = "ledger.actividad-asset.correct";
export const INSPECT = "ledger.actividad-asset.inspect";
export const HANDOFF = "ledger.actividad-asset.filing-handoff";
export const CALCULATE = "ledger.actividad-asset.disposal-calculate";

export const portOf = (shape: "fixture" | "unknown" = "fixture"): LedgerPort =>
  ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });

/** A field of the timeline given its first value, as the backend states it. */
export const change = (
  field: string,
  after: string | null,
  afterKey: string | null = null,
) => ({
  kind: "added" as const,
  field,
  field_key: `ledger.actividad_asset.field.${field}`,
  before: null,
  after,
  before_key: null,
  after_key: afterKey,
  before_label: null,
  after_label: null,
});

export async function settled<T>(
  outcome: Promise<{ kind: string }>,
): Promise<T> {
  const found = (await outcome) as { kind: string; result?: T };
  if (found.kind !== "settled") throw new Error(`not settled: ${found.kind}`);
  return found.result as T;
}

export type Refused = {
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
export async function refused(outcome: Promise<unknown>): Promise<Refused> {
  const found = (await outcome) as { kind: string };
  if (found.kind !== "refused") throw new Error(`not refused: ${found.kind}`);
  return found as Refused;
}

export const registerOf = (port: LedgerPort) =>
  settled<AssetListResult>(port.submit(LIST, {}));
export const listOf = async (port: LedgerPort) =>
  (await settled<AssetListResult>(port.submit(LIST, {})))
    .rows as AssetListRow[];
export const planOf = async (port: LedgerPort, id: string) =>
  (
    await settled<LedgerResult<typeof PLAN>>(
      port.submit(PLAN, { asset_id: id }),
    )
  ).rows as PlanRow[];
export const eventsOf = async (port: LedgerPort, id: string) =>
  (
    await settled<LedgerResult<typeof TIMELINE>>(
      port.submit(TIMELINE, { asset_id: id }),
    )
  ).events as TimelineEvent[];

// ---- Amounts compared to the cent -------------------------------------------

export const cents = (text: string) => BigInt(text.replace(".", ""));

export type Options = NonNullable<LedgerResult<typeof OPTIONS>["options"]>;

export async function optionsOf(
  port: LedgerPort,
  kind = "material",
): Promise<Options> {
  const read = await settled<LedgerResult<typeof OPTIONS>>(
    port.submit(OPTIONS, { asset_kind: kind, tax_year: scenarioYear }),
  );
  return read.options!;
}

/** The request the new-element form makes from what is typed in it. */
export async function newRequest(
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

/** An activity the registry declares for the scenario's taxpayer, and another
 * one, so a spec names a declared activity without stating its code. */
export const [firstActivity, secondActivity] = [
  DECLARED_ACTIVITIES[0]!,
  DECLARED_ACTIVITIES.at(-1)!,
];

/** The draft a person types to make each element the corpus commits, read from
 * the register's recording: the window's own creation requests are committed
 * scenario data, so a spec states no draft of its own and the register holds a
 * recorded answer for every creation a spec sends. */
export const NEW_ELEMENT = creationDraft("linear_new");
export const OPENING_MISSING = creationDraft("opening_missing");
export const USED_ELEMENT = creationDraft("used_expert_valuation");
export const OUTSIDE_LEDGER = creationDraft("outside_ledger");
export const OUTSIDE_LEDGER_KEYED = creationDraft("outside_ledger_keyed");
export const OUTSIDE_WITH_LATER_PAYMENT = creationDraft(
  "outside_ledger_with_later_payment",
);
export const WHOLE_PROPERTY = creationDraft("whole_property");
export const VEHICLE_ELEMENT = creationDraft("vehicle");
export const SHIFT_HOURS = creationDraft("shift_hours");

export const sale = {
  disposal_date: fixtureDay(6, 30, -1),
  reason: "sale",
  proceeds: { decimal: "9000.00" },
  transmission_costs: { decimal: "150.00" },
  market_value: null,
  prior_free_depreciation_regime: null,
  later_affectation_on: null,
};

export function servidorRow(): AssetListRow {
  return SCENARIO_ELEMENTS.find((seed) => seed.id === "servidor")!.list;
}

/** A translator that knows only the keys it is given, as the shell's does. */
export const words =
  (table: Record<string, string>): Translate =>
  (key, values) => {
    const template = table[key] ?? key;
    return values
      ? template.replace(/\{(\w+)\}/g, (whole, name: string) =>
          name in values ? String(values[name]) : whole,
        )
      : template;
  };

export const claims = (casilla: string) => ({
  target_casilla_id: casilla,
  box_name: `Box ${casilla}`,
  tax_year: priorYear,
  claim_ids: [],
  amount: { decimal: "0.00" },
});
