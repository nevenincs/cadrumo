---
tags:
  - '#adr'
  - '#executable-parity-evidence-tier-contract'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-bare-invocation-bucket-session-gate-adr]]"
  - "[[2026-06-02-m303-parser-engine-totals-impedance-adr]]"
  - '[[2026-06-04-executable-parity-evidence-tier-contract-research]]'
---


# `executable-parity-evidence-tier-contract` adr: documentary_parity_evidence tier for layout-only modelos | (**status:** `accepted`)

## Authoring note

Authored via Write tool — same bash constraint as the prior nine ADRs this campaign. Commit-bot validates via `vault check all`.

## Problem statement

`test_committed_registry_tree_has_required_model_law_coverage` flags 38 modelo-revision pairs for missing executable_parity_evidence. The gate at `_coverage.py:174-179` accepts ONLY `formula_coverage = "formula_form"` entries, which require `runner_required = true` + populated `output_cells`. That contract describes XLSX-formula-runner-verifiable parity.

The 38 flagged include informativas (M309, M322, M360, M308, M720, M714, M721, others) that ship NO formula workbook. Their parity is layout-only: BOE-published form + AEAT record-design. There is no runnable formula to verify against an XLSX oracle because there is no formula — informativas project ledger-side data into positional fields, not computed values.

Forcing formula_form authoring on layout-only modelos is contract-bending: it would require authoring runner stubs that don't exercise real engine behaviour, just to satisfy a gate that was designed for a different modelo class. The 38 reds persist as a permanent burndown unless the gate's contract is widened correctly.

## Forces in tension

- **`aeat-calculation-grounding`** mandates regulatory grounding for every casilla observation. Layout-only modelos still need legal/source refs; they just don't have a formula engine to verify.
- **`registry-calculation-legal-grounding`** mandates citing the binding provision that establishes each regulatory value. Layout-only modelos cite the BOE form-spec / record-design Orden as their parity reference, not an XLSX workbook.
- **Existing `formula_coverage` taxonomy** at `workbook_parity_refs/*.toml`: `formula_form` (XLSX-runner-verifiable), `static_layout` (form layout only), `record_design_layout` (AEAT diseño-de-registro only). The taxonomy ALREADY distinguishes the three parity shapes; only the gate restricts to one.
- **No-ratchet-bypass discipline**: widening the gate without naming the qualifying criterion turns it into a soft pass-through. Future modelos could declare `static_layout` to dodge formula-runner authoring even when a formula workbook exists.

## Candidate shapes evaluated

### Option A — widen the gate to accept static_layout + record_design_layout

Direct fix: change `_coverage.py:174-179` to accept all three `formula_coverage` values. Document the criterion (modelos that ship no XLSX workbook qualify) inline at the gate.

Pros: smallest diff. Honours the existing taxonomy.

Cons: the criterion ("no XLSX workbook") is descriptive, not enforceable. A future modelo could declare `static_layout` even when a workbook exists, ratchet-bypassing the formula-form requirement. The gate becomes weaker.

### Option B — new tier `documentary_parity_evidence` between legal_authority and executable_parity_evidence

Schema extension: introduce a new tier name in the parity-evidence enumeration. Authors of layout-only modelos declare `documentary_parity_evidence`; the gate accepts that tier for modelos in a curated allowlist (informativas with no XLSX workbook).

Pros: explicit tier separation. The allowlist is the enforceable criterion (additions are reviewable). Future modelos must justify joining the allowlist.

Cons: schema change + migration. The allowlist becomes load-bearing — adds a new authoring-discipline surface.

### Option C — author runner stubs for the 38 modelos

For each of the 38 modelos, author a workbook_parity_refs entry with `formula_coverage = "formula_form"`, `runner_required = true`, `output_cells = []`, and an inline documentary comment "layout-only modelo; no formula to runner". Update the validator to accept empty output_cells when accompanied by the documentary marker.

Pros: zero gate-contract change.

Cons: 38 stub commits with no executable content. The `runner_required = true` + empty `output_cells` shape is structurally dishonest — it tells the runner there's nothing to run while claiming runnable parity. Same anti-pattern as the M131 S398 false-implication rollback: claim made without grounding. Reject.

## Decision: Option B — documentary_parity_evidence tier with curated allowlist

The taxonomy `formula_coverage` already distinguishes the three parity shapes; the gate restricting to one is a contract gap that pre-dates the informativa landings. Option B closes the gap by introducing the missing tier at the validator level WITHOUT a ratchet-bypass risk:

1. **New tier `documentary_parity_evidence`** at the parity-evidence enumeration. Sits between `legal_authority` (registry-side legal cite) and `executable_parity_evidence` (workbook-runner-verifiable). Captures: "parity is verified against the BOE form-spec or AEAT record-design rather than an executable XLSX workbook, because no workbook exists for this modelo".

2. **Curated allowlist** at `_coverage.py` enumerating which modelo-revision pairs qualify. The 38 currently-flagged pairs land in the initial allowlist. The allowlist is the enforceable criterion: each entry cites the BOE Orden that publishes the form-spec / record-design.

3. **Gate accepts documentary_parity_evidence** when the modelo-revision is in the allowlist AND the workbook_parity_refs entry's `formula_coverage` is `static_layout` or `record_design_layout` AND the entry cites a BOE form-spec source-ref.

4. **Ratchet preserved**: a future modelo cannot escape executable_parity_evidence by declaring documentary unless its modelo-revision pair joins the allowlist AND the audit trail (PR review) justifies the join. The allowlist makes the criterion enforceable, not descriptive.

### Why not A

Option A's "no XLSX workbook" criterion is descriptive; nothing prevents a future modelo with a workbook from declaring `static_layout` to dodge runner authoring. Option B's allowlist is enforceable. Reject A.

### Why not C

Stub authoring with `runner_required = true` + empty `output_cells` is structurally dishonest. Same anti-pattern the dual-keying ADR rejected (claim made without the matching engine edge). Reject C.

## Consequences

- New tier name added at the parity-evidence enumeration in `_coverage.py` (or wherever the tier taxonomy lives). ~10 LOC.
- Allowlist at `_coverage.py` enumerating the 38 modelo-revision pairs + their BOE form-spec citations. ~50 LOC TOML or Python dict.
- Gate logic extension: accept documentary_parity_evidence when allowlist + form_coverage condition matches. ~15 LOC.
- 38 modelos' existing workbook_parity_refs entries get tier annotation. Either inline `tier = "documentary_parity_evidence"` per entry, or implicit via the allowlist lookup. Recommend explicit per-entry — the entry self-declares its tier; the allowlist verifies the declaration. ~38 small TOML edits.
- Anti-tautology gate: a new modelo declaring `documentary_parity_evidence` without an allowlist entry fails the gate; an allowlist entry without a matching workbook_parity_refs declaration also fails.

The suite-redgreen P04.S10 burndown drops from 38 to 0.

## Migration path

Single atomic commit per the tier-extension + allowlist + 38-entry annotation must co-land. Split into two commits if the allowlist authoring is heavy:

1. Commit 1: tier extension + gate logic + allowlist scaffold (empty).
2. Commit 2: populate allowlist with 38 entries + per-modelo tier annotation in workbook_parity_refs.

Anti-tautology test lands with commit 2.

Dispatch to coder with M309/M322/M360/M308/M720/M714/M721 context. ~100 LOC + 38 small TOML edits + anti-tautology test. ~2 commits.

## Out of scope

- The actual BOE Orden authoring for each of the 38 modelos (those citations should already exist in legal/source refs; the allowlist just references them).
- M303 / M390 parser-engine impedance (separate ADR `2026-06-02-m303-parser-engine-totals-impedance`).
- M390 autoconsumo asymmetry (separate ADR `2026-06-02-m390-annual-autoconsumo-promotor-source`).
