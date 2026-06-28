---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-google-oauth-calc-sheets-adr]]"
  - "[[2026-05-13-google-oauth-taxonomy-adr]]"
  - "[[2026-05-13-google-oauth-adr]]"
  - "[[2026-05-12-google-oauth-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-06-google-oauth-research]]"
---

# `google-oauth` adr: `Two-way Sheets sync feasibility verdict` | (**status:** `accepted — deferred`)

## Problem Statement

ADR-5 enumerated which domains have operator-editable fields per the four-source-kind taxonomy mandated by the cli-workflow-redesign invoice-domain-decoupling ADR: `ledger_transaction` (business_classification + category + notes), `purchase_invoice_evidence` (notes + attached_to_transaction_id), `payable_invoice` (payment_status + notes), `collectible_invoice` (payment_status + notes), `rental` income/expense (amounts + dias_alquilados). The forward question — when an operator edits these fields in a Sheets export, can the app reliably pull those changes back into substrate? — is the feasibility decision ADR-7 closes.

The verdict has direct material consequences for v1 scope: it determines whether the codebase contains a Sheets-pull command that reads operator edits from a workspace Sheets surface and applies them to the substrate, or whether no such command exists at all. The application-layer reverse-merge service (which validates editable-only field invariants and applies record subsets to the substrate) is fully active in v1 regardless of the verdict — the CLI edit commands and CSV-corrections import commands call it directly — so the question is only whether a Sheets-pull entry-point ships alongside those v1 callers.

## Considerations

- Research stream R5 surveyed: Sheets revision API, Drive change feed, CRDT/OT for spreadsheets, industry tools (Sheetgo, Sync2Sheets, Airtable, Coupler.io, TaxDome, n8n), and the structural row-diffing problem.
- The single most important risk identified: **financial data audit-trail corruption via silent sync collision**. An operator edits a transaction category in Sheets; meanwhile, the app writes a new transaction (from a bank-statement ingestion). Last-write-wins silently overwrites the operator's edit. The operator's edit vanishes with no notification; audit trail is incomplete; tax-filing consequences potentially severe.
- Industry tools converge on either (a) sequential unidirectional flows with operator-managed precedence (Sheetgo: "forbids simultaneous edits to same column") or (b) last-write-wins with no conflict guarantee (Airtable). Neither is acceptable for tax data.
- Project's stance throughout: refuse-on-uncertainty for legally-binding-data surfaces (charter `#116`).

## Constraints

- **Pydantic v2 strict** for any record introduced (verdict record + audit trail entries).
- **No partial implementations.** Either two-way sync ships complete in v1 with all four documented safety properties, or it does not ship. No half-built reverse-merge that "mostly works."
- **No backwards-compat.** No legacy operator-edit format readers.
- **Verdict applies uniformly.** Either all Tier-1 domains (per ADR-5) get reverse-flow or none.

## Implementation

### 1. Verdict — scope-split: calc-sheets is bidirectional in v1; ledger Sheets-pull remains deferred

**Amended 2026-05-14**: The original deferral verdict ("v1 ships one-way Sheets export only") applied uniformly across every Sheets surface. ADR-8 (`2026-05-14-google-oauth-adr.md`) supersedes it for the **calc-sheets surface specifically**: `aeat config google sync calc pull` is an active v1 command that reads operator edits to the `Entradas` (Inputs) sheet of a `calc-modelo-<NNN>-<period>.gsheet` and applies them to the local `ModeloWorkUnit` substrate. The partition-by-cell-ownership contract (operator owns `Entradas`, app owns `Cálculos / Resultado / Procedencia`) makes the calc-sheets bidirectional surface operationally simpler than ledger reverse-merge.

The **ledger reverse-merge surface (transactions, invoices, rental)** remains deferred per the original ADR-7 verdict. Operators correct ledger fields via the in-CLI edit commands (§3) or CSV upload (§4); no `aeat app ledger transaction sync pull --from-sheet` command exists in v1 because the four safety properties (§2) are not yet met for the Tier-1 ledger surface.

The application-layer reverse-merge service exists and is fully active in v1 because the v1 CLI edit commands (`aeat app ledger transaction edit`, etc.) and CSV-corrections import commands (`aeat app ledger transaction corrections import-csv`, etc.) call it directly. The service validates editable-only field invariants, applies record subsets to the substrate, and emits audit + bucket events on every applied row. It is real, tested, used, and does not carry a settings flag.

No `settings.aeat_enable_two_way_sync` flag exists in v1. There is nothing to gate (no ledger Sheets-pull code is present) and no flag to flip later. The calc-sheets bidirectional pull lands as a new CLI command per ADR-8; it does not depend on, or remove, a pre-existing flag. A future amendment may add ledger Sheets-pull alongside ADR-7's safety-property closure work; that amendment ships the new command alongside its own ADR amendment.

### 2. Why ledger Sheets-pull is still deferred — the four unmet safety properties

The four properties below pertain to the **ledger reverse-merge surface** (Tier-1 ledger domains: transactions, invoices, rental). They were the original ADR-7 deferral argument and continue to govern that surface. The calc-sheets surface (per ADR-8) is operationally distinct — it has no row-position-keyed Sheets layout, no per-cell schema validation requirement beyond formula-input shape, no need for an operator-recoverable validation UX since the parity oracle (ADR-8 §3) catches translation defects pre-export, and a much simpler audit-trail story (single `CalculationRevision` rather than per-row reverse-merge events). The four properties below therefore apply only to the ledger surface:

| Property | What's needed | Why not v1 |
|---|---|---|
| **No silent overwrites** | Drift detection that surfaces conflicts to the operator before applying either side | Drive's row-position-based diff is fragile under operator inserts/deletes; row-keying (per-source-kind id: `transaction_id`, `evidence_id`, `payable_invoice_id`, `collectible_invoice_id`) helps but doesn't compose with operator-renamed sheets |
| **Schema lock with operator-visible feedback** | Sheets `protectedRanges` to forbid column changes; clear feedback when operator tries | Protected-range refusal is silent in Sheets UI (operator sees "this cell is protected" with no diagnostic context) |
| **Operator-recoverable validation failures** | When an operator-edited cell violates an invariant (negative income, malformed NIF), the app must show the operator *which cell, why, what to fix* — inside Drive UI, not buried in CLI logs | Sheets API has no per-cell in-UI error annotation; only cell comments (which the app would have to author and clean up) |
| **Audit trail of every operator edit** | Every reverse-merge writes an audit row recording (cell, before, after, timestamp, operator-identity) | Audit table doesn't exist; secure-persistence policy review needed before financial-class audit data is appended |

ADR-7's deferral records that the four properties are tractable engineering work — just not bundled into v1 scope. A future amendment closes them and flips the gate.

### 3. v1 alternative — in-CLI editing

Operators who want to correct a Tier-1 domain field (transaction category, payable-invoice payment_status, collectible-invoice payment_status, purchase-invoice-evidence link, rental income amount) use the existing CLI surface. Commands honor the cli-workflow-redesign invoice-domain-decoupling source-kind taxonomy: bare `invoice` is forbidden; each kind has its own verb:

```
aeat app ledger transaction edit <transaction_id> --category <cat> --notes <text>
aeat app ledger purchase-invoice-evidence edit <evidence_id> --notes <text> --attach-to <transaction_id>
aeat app ledger payable-invoice edit <payable_invoice_id> --payment-status <status> --notes <text>
aeat app ledger collectible-invoice edit <collectible_invoice_id> --payment-status <status> --notes <text>
aeat app ledger rental income edit <record_id> --amount <eur> --dias-alquilados <n>
aeat app ledger rental expense edit <record_id> --amount <eur> [--description] [--allocation-pct]
```

Edits flow through the substrate's typed validation immediately. The next `aeat config google sync push` propagates the change to Drive. Operator sees the change reflected in the Sheets visualisation (per ADR-6) after re-running the export.

This is honest about where the source of truth lives (substrate, not Drive) and matches the project's CLI-first philosophy.

### 4. v1 alternative — CSV upload + validation

For batch corrections (operator wants to recategorise 50 transactions at once), v1 provides:

```
aeat app ledger transaction corrections export-csv --period <p> --output <path>   # exports editable subset
aeat app ledger transaction corrections import-csv --input <path> --dry-run       # validates without writing
aeat app ledger transaction corrections import-csv --input <path>                 # commits after dry-run pass
```

`import-csv` validates every row against the editable-field invariant (only `business_classification`, `category_id`, `notes` may differ from current state). Rows that violate the invariant or fail schema validation are reported with row numbers and explanations; the import is all-or-nothing.

CSV files can be uploaded to `/aeat-vault/_inbound/pending/` for the operator-supplies-edits-via-Drive workflow; the import-csv invocation pulls from there via the inbound bucket per ADR-4. The audit trail records every imported row.

Symmetric corrections surfaces exist for the three invoice-domain source kinds and the purchase-invoice-evidence kind, with the source-kind taxonomy split required by the cli-workflow-redesign invoice-domain-decoupling ADR:

```
aeat app ledger purchase-invoice-evidence corrections export-csv --period <p> --output <path>
aeat app ledger purchase-invoice-evidence corrections import-csv --input <path> [--dry-run]
aeat app ledger payable-invoice corrections export-csv --period <p> --output <path>
aeat app ledger payable-invoice corrections import-csv --input <path> [--dry-run]
aeat app ledger collectible-invoice corrections export-csv --period <p> --output <path>
aeat app ledger collectible-invoice corrections import-csv --input <path> [--dry-run]
```

Two namespace patterns require EPIC-team sign-off because they extend `aeat app ledger` with new sub-verbs not yet present in the cli-workflow-redesign ADR set: `aeat app ledger transaction corrections` and per-source-kind `aeat app ledger {purchase-invoice-evidence|payable-invoice|collectible-invoice} corrections`. If the EPIC team rejects the `corrections` sub-namespace, the v1 alternative decomposes into the existing `aeat app ledger classify` / `allocate` / `link` verbs invoked per-record by the operator (no bulk-CSV path) — at the cost of operator UX for batch corrections.

### 5. Future amendment surface

When the Sheets-pull entry-point becomes scope, the amendment ADR will specify:

- **The new CLI command.** `aeat config google sync pull --workspace-edits` (or a similarly explicit verb) reads `/aeat-vault/_workspace/` Sheets surfaces, builds record subsets per source kind, and routes each subset through the existing application-layer reverse-merge service that already ships in v1.
- **Row-keying strategy.** Every reverse-flow-eligible row must carry an immutable id column scoped to its source kind: `transaction_id` for ledger transactions, `evidence_id` for purchase-invoice-evidence, `payable_invoice_id` for payable invoices, `collectible_invoice_id` for collectible invoices, rental record `id` for rental rows. Operator-deleted rows = a "what should this mean?" question that needs an answer.
- **Schema-lock mechanism.** Sheets `protectedRanges` for header + column-name cells, with `warningOnly: false`.
- **Conflict-resolution UX.** Refuse-on-conflict matches ADR-2; per-row resolution via `--resolve <strategy>` flag.
- **Validation-failure UX in Drive.** Append a cell comment with the validation error; operator fixes the cell; re-runs pull.
- **Audit trail.** Reverse-merge service already emits a per-row audit row and a `ledger.<source-kind>.correction.applied` bucket event in v1; the Sheets-pull command inherits those emissions for free. The amendment may extend `source_revision` to carry the Drive `headRevisionId` for traceability.

The amendment ships the new command and its tests as one unit. There is no flag to flip, no inert code to activate, no settings field to mutate. It is a new feature, not a re-enablement.

### 6. Out of scope (deferred to the future amendment)

- All four safety properties from §2.
- Reverse-flow code activation (the gate stays False).
- Schema-evolution handling (operator adds a column / renames a sheet).
- Comments / suggestions reconciliation (operator leaves a Sheets comment vs an edit).

## Rationale

**Defer over ship-with-known-gaps.** Industry tools that ship two-way sync without the safety properties experience real data loss in production (R5 cited Sheetgo's forum threads and TaxDome's explicit one-way design). Tax data is unforgiving — a silent category overwrite that an operator doesn't notice until the next quarterly filing is a regression that's difficult to recover from. Deferring trades operator UX (no Sheets-edit-and-go) for operator safety (no audit-trail corruption); the trade is correct.

**In-CLI editing as the v1 alternative.** The CLI surface for editing Tier-1 domain fields already exists or is small to add. Edits flow through the substrate's typed validation immediately, with deterministic error UX. No spreadsheet-shape uncertainty. The operator who wants Sheets-side bulk-edit gets the CSV-upload path; the operator who wants single-record-edit gets the CLI.

**CSV-upload as the bridge for bulk edits.** Some operator workflows (annual recategorisation, post-bank-statement bulk cleanup) genuinely benefit from spreadsheet ergonomics. CSV export + validated re-import preserves the spreadsheet workflow without the two-way-sync complexity: operator gets a file, edits it, uploads, app validates, audit-logs every row. Failure UX is clear (validation report per row). Two-way sync without these guarantees is strictly worse than this bridge.

**Future-amendment surface documented now.** The next round of two-way sync research has a concrete starting point. Whoever picks this up later doesn't re-do R5; they implement the four safety properties against a defined surface.

## EPIC conformance

ADR-7's CLI surfaces use `aeat app ledger ...` namespaces consistent with the cli-workflow-redesign EPIC's two-root constraint (`aeat config` + `aeat app`). The `aeat data` root the discarded gcloud-era stack used is retired with no alias per the EPIC's apex fold-under map.

Two CLI sub-namespaces this ADR introduces are not yet in the EPIC ADR set and require sign-off before implementation lands:

- `aeat app ledger transaction edit` — single-record correction verb (category + notes). The EPIC's `aeat app ledger classify` / `allocate` may be the preferred decomposition; this ADR proposes `transaction edit` as a one-shot alternative for operator UX. EPIC-team must accept the new verb or reject in favour of decomposition before P08 implements.
- `aeat app ledger transaction corrections export-csv / import-csv` and `aeat app ledger payable-invoice corrections export-csv / import-csv` and `aeat app ledger collectible-invoice corrections export-csv / import-csv` — the `corrections` sub-namespace is new. It is structurally distinct from the EPIC's `aeat app ledger export` (which serves modelo-preparation) because corrections targets the editable-field subset only. EPIC-team must accept `corrections` as a sub-namespace under `aeat app ledger` or reject in favour of per-record CLI editing without bulk-CSV.

These two items are the only EPIC-conformance gates between this ADR and implementation; every other CLI surface ADR-7 mentions is fully conformant.

## Consequences

**Positive.**

- No financial audit-trail corruption from silent collisions in v1.
- Operator has explicit, deterministic paths for both single-record edits (CLI) and bulk edits (CSV).
- ADR-5's reverse-merge code is written + tested in v1, just gated; future flip is a settings change + amendment.
- Future amendment has a structured surface to fill in rather than starting fresh.

**Negative.**

- Operator workflows that assume "edit anywhere, sync everywhere" are not available. The autónomo who wants to fix a category in Sheets and have it appear in their filing must instead re-run `aeat app ledger transaction edit`. CSV path covers bulk cases but adds an export-edit-import loop.
- The "Drive is the truth" mental model that two-way would establish is replaced with "substrate is the truth" — Drive is a read-only window plus an inbound chute. Slightly more cognitive load for operators who interact heavily with Drive.
- Wired-but-gated reverse-merge code is dead weight in v1 (~200 LOC across the four Tier-1 domains). Cost accepted for the future-amendment ease.

**Neutral.**

- The deferral is not permanent; the amendment surface is open. Operators / accountants can request the gate flip when they're willing to accept the safety-property constraints.
- ADR-6's calc-to-Sheets read-only stance is unaffected — those Sheets are always read-only regardless of ADR-7's verdict.

## References

External:
- Sheetgo two-way sync documentation — `https://support.sheetgo.com/en/articles/8529696-how-do-i-create-a-two-way-sync`
- TaxDome → QuickBooks one-way design — `https://help.taxdome.com/article/488-quickbooks-integration-manually-handling-sync-issues`
- Operational Transformation overview — `https://en.wikipedia.org/wiki/Operational_transformation`

Internal:
- `[[2026-05-13-google-oauth-calc-sheets-adr]]` — Calc → Sheets visualisation (read-only, independent of ADR-7).
- `[[2026-05-13-google-oauth-taxonomy-adr]]` — per-domain editability matrix gated by ADR-7.
- `[[2026-05-13-google-oauth-adr]]` — bucket layout + sync state.
- `[[2026-05-12-google-oauth-adr]]` — provider abstraction.
- `[[2026-05-06-google-oauth-research]]` — R5 two-way feasibility research.
