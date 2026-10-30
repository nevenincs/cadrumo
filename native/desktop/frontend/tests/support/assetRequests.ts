// The requests the Assets tab's forms make, for a test that checks them against
// the backend's own request contracts. The file is bundled and run by Node on
// the scenarios given on standard input; it opens no page and holds no state.
// The options the forms are drawn from, the facts each method takes among
// them, come in with the scenarios from the backend, so a fact the backend
// serves and a form cannot state fails the test and not the window.

import {
  answer,
  fieldsFor,
  initialOf,
  type FieldContext,
  type FormDraft,
} from "../../src/components/ledger/assets/assetFields";
import {
  bajaRequest,
  correctRequest,
  createRequest,
  type RevisionBase,
} from "../../src/components/ledger/assets/assetRevision";
import {
  SERVED_ACTIVITIES,
  SERVED_METHOD_FACTS,
  SERVED_SHAPES,
} from "../../src/dev/assetsFixture";
import { TABLE_GROUPS } from "../../src/dev/assetsSeed";
import type {
  AcquisitionCandidate,
  DisposalFacts,
  FormOptions,
} from "../../src/shell/ledgerSetup";

/** What the backend serves with the options of a form. */
type Served = {
  methods: string[];
  method_facts: FormOptions["method_facts"];
  acquisition_shapes: string[];
  declared_activities: string[];
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
  | { id: string; kind: "fixture" };

type Input = { served: Served; scenarios: Scenario[] };

const hex = (seed: string) => seed.repeat(64).slice(0, 64);

/** The purchase the person picks: the ledger's own account of it. */
const CANDIDATE: AcquisitionCandidate = {
  transaction_id: hex("a"),
  booked_date: "2026-05-06",
  description: "Compra",
  amount: { decimal: "1089.00" },
  currency: "EUR",
  paid_in_euro: { decimal: "1089.00" },
  taxable_base: { decimal: "900.00" },
  iva_amount: { decimal: "189.00" },
  non_deductible_iva_state: "known",
  non_deductible_iva_state_key:
    "ledger.actividad_asset.non_deductible_iva_state.known",
  non_deductible_iva: { decimal: "0.00" },
  invoice_evidence_id: hex("b"),
  evidence_fingerprint: hex("c"),
};

const optionsFor = (kind: string, served: Served): FormOptions => ({
  tax_year: 2026,
  asset_kind: kind,
  regime: "normal",
  edition: { revision_id: "2025", authored_filing_year: 2025, projected: true },
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

function run(scenario: Scenario, served: Served) {
  if (scenario.kind === "fixture")
    return {
      id: scenario.id,
      facts: SERVED_METHOD_FACTS,
      shapes: SERVED_SHAPES,
      activities: SERVED_ACTIVITIES,
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
      candidate: CANDIDATE,
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
  const { served, scenarios } = JSON.parse(input) as Input;
  process.stdout.write(
    JSON.stringify(scenarios.map((scenario) => run(scenario, served))),
  );
});
