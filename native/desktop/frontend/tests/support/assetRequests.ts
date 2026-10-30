// The requests the Assets tab's forms make, for a test that checks them against
// the backend's own request contracts. The file is bundled and run by Node on
// the scenarios given on standard input; it opens no page and holds no state.

import {
  answer,
  fieldsFor,
  initialOf,
  type FieldContext,
  type FormDraft,
} from "../../src/components/ledger/assets/assetFields";
import {
  correctRequest,
  createRequest,
  type RevisionBase,
} from "../../src/components/ledger/assets/assetRevision";
import { TABLE_GROUPS } from "../../src/dev/assetsSeed";
import type {
  AcquisitionCandidate,
  FormOptions,
} from "../../src/shell/ledgerSetup";

type Scenario =
  | { id: string; kind: "create"; draft: FormDraft }
  | {
      id: string;
      kind: "correct";
      base: RevisionBase;
      changes: FormDraft;
      supersede: string[];
    };

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

const optionsFor = (kind: string): FormOptions => ({
  tax_year: 2026,
  asset_kind: kind,
  regime: "normal",
  edition: { revision_id: "2025", authored_filing_year: 2025, projected: true },
  methods: [],
  table_groups: [...(TABLE_GROUPS[kind] ?? [])],
});

const contextFor = (
  kind: "element" | "correction",
  assetKind: string,
  base: RevisionBase | null,
): FieldContext => ({
  kind,
  row: null,
  descriptor: null,
  revision: base?.revision ?? null,
  tokens: () => [],
  options: optionsFor(assetKind),
});

function run(scenario: Scenario) {
  if (scenario.kind === "create") {
    const context = contextFor(
      "element",
      scenario.draft.asset_kind ?? "material",
      null,
    );
    const fields = fieldsFor(context, scenario.draft);
    const stated = answer(fields, scenario.draft, null);
    const request = createRequest(stated.values, {
      assetId: hex("d"),
      regime: "normal",
      candidate: CANDIDATE,
      base: null,
    });
    return { id: scenario.id, problems: stated.problems, request };
  }
  const assetKind = String(scenario.base.revision.asset_kind);
  const context = contextFor("correction", assetKind, scenario.base);
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
    },
    scenario.supersede,
  );
  return { id: scenario.id, problems: stated.problems, request };
}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => (input += chunk));
process.stdin.on("end", () => {
  const scenarios = JSON.parse(input) as Scenario[];
  process.stdout.write(JSON.stringify(scenarios.map(run)));
});
