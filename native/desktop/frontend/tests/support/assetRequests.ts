// The requests the Assets tab's forms make, for a test that checks them against
// the backend's own request contracts. The file is bundled and run by Node on
// the scenarios given on standard input; it opens no page and holds no state.
// The options the forms are drawn from, the facts each method takes among
// them, come in with the scenarios from the backend, so a fact the backend
// serves and a form cannot state fails the test and not the window.

import {
  fieldsFor,
  FURTHER_PURCHASE,
  initialOf,
  type FieldContext,
} from "../../src/components/ledger/assets/assetFields";
import {
  answer,
  type FormDraft,
} from "../../src/components/ledger/assets/assetFormValues";
import {
  forecastRequest,
  handoffRequest,
} from "../../src/components/ledger/assets/assetWrites";
import {
  bajaRequest,
  correctRequest,
  createRequest,
  type RevisionBase,
} from "../../src/components/ledger/assets/assetRevision";
import { SERVED_METHOD_FACTS } from "../../src/dev/assetsFixtureBase";
import {
  ACQUISITION_SHAPES,
  DECLARED_ACTIVITIES,
  SCENARIO_TODAY,
  TABLE_GROUPS,
} from "../../src/dev/assetsRegister";
import { servedEditionOf } from "../../src/dev/servedYearAuthority";
import type {
  AcquisitionCandidate,
  DisposalFacts,
  FormOptions,
  LedgerEntryLimits,
} from "../../src/shell/ledgerSetup";
import { holdLedgerLimits } from "../../src/shell/ledgerLimits";

/** What the backend serves with the options of a form. */
type Served = {
  methods: string[];
  method_facts: FormOptions["method_facts"];
  acquisition_shapes: string[];
  declared_activities: string[];
  disposal_reasons: FormOptions["disposal_reasons"];
  basis_stages: FormOptions["basis_stages"];
  opening_statuses: FormOptions["opening_statuses"];
  acquired_conditions: FormOptions["acquired_conditions"];
  further_acquisition_shapes: string[];
  m130_periods: string[];
};

type Scenario =
  | { id: string; kind: "create"; draft: FormDraft }
  | {
      id: string;
      kind: "correct";
      base: RevisionBase;
      changes: FormDraft;
      supersede: string[];
    }
  | {
      id: string;
      kind: "baja";
      base: RevisionBase;
      disposal: DisposalFacts | null;
    }
  | { id: string; kind: "fixture" }
  | {
      id: string;
      kind: "forecast";
      draft: FormDraft;
      supersedes: string | null;
    }
  | { id: string; kind: "handoff"; year: number; period: string }
  | { id: string; kind: "baja_fields"; asset_kind: string }
  | { id: string; kind: "vehicle_fields"; asset_kind: string };

type Input = {
  served: Served;
  limits: LedgerEntryLimits;
  /** The payments the ledger offers, as it accounts for them. A draft picks one
   * by its identifier, the way the window picks from what the register serves;
   * a draft that names none takes the first. */
  candidates: AcquisitionCandidate[];
  scenarios: Scenario[];
};

/** What one run was given beyond its scenarios. */
type Given = { served: Served; candidates: AcquisitionCandidate[] };

const hex = (seed: string) => seed.repeat(64).slice(0, 64);

/** The scenario's own year, read from its date. */
const scenarioYear = Number(SCENARIO_TODAY.slice(0, 4));

const optionsFor = (kind: string, served: Served): FormOptions => ({
  tax_year: scenarioYear,
  asset_kind: kind,
  regime: "normal",
  edition: servedEditionOf(scenarioYear)!,
  ...served,
  table_groups: [...(TABLE_GROUPS[kind] ?? [])],
});

const contextFor = (
  kind: "element" | "correction",
  options: FormOptions,
  base: RevisionBase | null,
): FieldContext => ({
  kind,
  row: null,
  descriptor: null,
  revision: base?.revision ?? null,
  tokens: () => [],
  options,
});

/** The payment a draft picks, or the first on offer where it names none. */
const pickedBy = (
  candidates: AcquisitionCandidate[],
  named: string | undefined,
): AcquisitionCandidate | null =>
  candidates.find((found) => found.transaction_id === named) ??
  (named === undefined ? (candidates[0] ?? null) : null);

function run(scenario: Scenario, given: Given) {
  const { served, candidates } = given;
  if (scenario.kind === "forecast")
    return {
      id: scenario.id,
      request: forecastRequest(
        "furgoneta",
        scenario.draft,
        scenario.supersedes,
      ),
    };
  if (scenario.kind === "handoff")
    return {
      id: scenario.id,
      request: handoffRequest(scenario.year, scenario.period, "es"),
    };
  if (scenario.kind === "baja_fields") {
    const options = optionsFor(scenario.asset_kind, served);
    const reason = fieldsFor(
      {
        kind: "baja",
        row: null,
        descriptor: null,
        revision: null,
        tokens: () => [],
        options,
      },
      {},
    ).find((found) => found.key === "reason");
    return {
      id: scenario.id,
      reasons: (reason?.choices ?? []).map((choice) => ({
        reason: choice.token,
        label_key: choice.word ?? null,
      })),
    };
  }
  if (scenario.kind === "vehicle_fields") {
    const options = optionsFor(scenario.asset_kind, served);
    const classKey = "amortization.authority_class_key";
    return {
      id: scenario.id,
      drawn: Object.fromEntries(
        options.table_groups.map((group) => [
          group.class_key,
          fieldsFor(
            {
              kind: "element",
              row: null,
              descriptor: null,
              revision: null,
              tokens: () => [],
              options,
            },
            {
              asset_kind: scenario.asset_kind,
              method: "linear",
              [classKey]: group.class_key,
            },
          ).some((found) => found.key === "vehicle_category"),
        ]),
      ),
    };
  }
  if (scenario.kind === "fixture")
    return {
      id: scenario.id,
      facts: SERVED_METHOD_FACTS,
      shapes: ACQUISITION_SHAPES,
      activities: DECLARED_ACTIVITIES,
    };
  if (scenario.kind === "baja")
    return {
      id: scenario.id,
      problems: {},
      request: bajaRequest(scenario.base, scenario.disposal),
    };
  if (scenario.kind === "create") {
    const options = optionsFor(scenario.draft.asset_kind ?? "material", served);
    const fields = fieldsFor(
      contextFor("element", options, null),
      scenario.draft,
    );
    const stated = answer(fields, scenario.draft, null);
    const request = createRequest(stated.values, {
      assetId: hex("d"),
      regime: "normal",
      candidate: pickedBy(candidates, scenario.draft.acquisition),
      further: pickedBy(candidates, scenario.draft[FURTHER_PURCHASE]),
      base: null,
      options,
    });
    return { id: scenario.id, problems: stated.problems, request };
  }
  const options = optionsFor(String(scenario.base.revision.asset_kind), served);
  const context = contextFor("correction", options, scenario.base);
  const initial = initialOf(context, fieldsFor(context, {}));
  const draft = { ...initial, ...scenario.changes };
  const fields = fieldsFor(context, draft);
  const stated = answer(fields, draft, initial);
  const request = correctRequest(
    stated.values,
    {
      assetId: String(scenario.base.revision.asset_id),
      regime: null,
      candidate: null,
      base: scenario.base,
      options,
    },
    scenario.supersede,
  );
  return {
    id: scenario.id,
    problems: stated.problems,
    cleared: stated.cleared,
    request,
  };
}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => (input += chunk));
process.stdin.on("end", () => {
  const { served, limits, candidates, scenarios } = JSON.parse(input) as Input;
  holdLedgerLimits(limits);
  process.stdout.write(
    JSON.stringify(
      scenarios.map((scenario) => run(scenario, { served, candidates })),
    ),
  );
});
