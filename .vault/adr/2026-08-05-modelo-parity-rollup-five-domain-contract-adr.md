---
tags:
  - '#adr'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f8150fcc53e7e337e277d50d00a478d86e1ac50ced37fbe0feba69f6c103849a'
related:
  - '[[2026-08-05-modelo-parity-rollup-denominator-research]]'
  - '[[2026-08-04-modelo-100-casilla-implementation-audit]]'
  - '[[2026-06-03-executable-parity-evidence-tier-contract-adr]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-07-01-modelo-131-eo-modulos-engine-adr]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-candidate-contract-matrix-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-evidence-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-source-contract-research]]'
---
# `modelo-parity-rollup` adr: `Five-domain modelo revision parity ledger and bounded execution` | (**status:** `accepted`)

## Problem Statement

The registry lacks one measurable contract for distinguishing schema coverage, deterministic production, legal grounding, cross-model handoffs, and independent behavioral verification. Collapsing these domains into one scoreâ€”or treating the newest revision as canonicalâ€”would misclassify lawful annual differences, honest manual inputs, and unsupported behavior as implementation defects.

This ADR formalizes the bounded campaign grounded by `2026-08-05-modelo-parity-rollup-denominator-research`. It authorizes measurement and exact enrollment of already-proven oracle evidence. It does not authorize unresolved production semantics.

## Considerations

- `2026-04-21-casilla-schema-completeness-adr` governs year-specific official form inventory.
- `2026-06-03-executable-parity-evidence-tier-contract-adr` distinguishes evidence coverage from executable correctness.
- `2026-06-03-modelo-export-evidence-parity-adr` governs preservation of source and calculation provenance.
- `2026-06-10-calculation-aggregation-taxonomy-adr` governs canonical aggregation and relation mechanisms.
- `2026-07-01-modelo-131-eo-modulos-engine-adr` governs the existing M131 shared-engine boundary.
- `2026-08-04-modelo-100-casilla-implementation-audit` classifies M100 `0150`, `0613`, and `1481` as separate unresolved semantic cases, not copy targets.

## Considered options

- **Five-domain ledger with exact annual coordinates - accepted.** It preserves revision truth and routes semantic gaps to focused decisions.
- **Newest-revision baseline or count equalization - rejected.** It erases lawful historical differences and can fabricate producers, profiles, or relations.
- **One composite parity percentage - rejected.** It combines incompatible populations and conceals unmeasured domains.
- **Bulk or ungrounded enrollment - rejected.** It turns implementation output into its own evidence.
- **Unbounded implementation from ledger findings - rejected.** Measurement does not authorize semantic changes.

## Constraints

The portfolio denominator is the accepted baseline inventory of 73 modelos and 90 revision rows. It is reported separately from the behavioral denominator, which is a finite, explicitly enumerated matrix of exact `(modelo, ejercicio, period)` coordinates. Open-ended revisions do not prove unspecified future years. Missing, unsupported, deferred, and not-yet-measured coordinates remain visible and must not be omitted.

Every coordinate selects its registry revision through the law-determined authority. Schema parity uses that yearâ€™s official form or layout denominator, never the newest or largest revision.

`D2025` means provisionally and only: Modelo 100, ejercicio 2025, period `0A`, registry revision `2025`. It is not a repository-wide identifier, annex name, or global revision class.

Revision-level legal, source, layout, documentary, or executable evidence is a minimum evidence floor. It is not proof for each casilla, formula, parameter, binding, relation, or result. Numeric correctness requires an independent AEAT or BOE example, authoritative workbook result, or live AEAT oracle result.

Permitted now are read-only measurement, ledger construction, and enrollment of exact existing oracle evidence through unambiguous verification expectations and real tests. These actions must not change formulas, profiles, relations, aggregation behavior, or legal interpretation.

Deferred are bulk cloning, count equalization, inferred or ungrounded enrollment, and production changes for M100 `0150`, `0613`, or `1481`.

Any new producer, selector, operator, source, relation, aggregation semantic, annual-law interpretation, or manual-to-computed transition requires a focused addendum and return to SOL before implementation.

## Implementation

The ledger records five independent domains for every enrolled coordinate:

1. **Schema parity.** Compare the exact `(modelo, ejercicio, period)` casilla population and relevant attributes with the official form or layout for that year. Record missing, extra, divergent, unsupported, and unmeasured entries without equalizing revision counts.

2. **Formula and provenance parity.** Every legally deterministic casilla with authoritative inputs has exactly one registry-authorized typed producer. Formula-backed production requires the formula target and casilla reverse formula reference to identify each other exactly, with no duplicate target. The producer and resulting observation preserve applicable legal and source provenance. Manual or upstream production is valid only when its reason and provenance are explicit.

3. **Legal/source parity.** Reconcile each schema construct, formula, parameter, binding, relation, selector, and producer against its applicable authoritative corpus. Construct-level evidence is recorded independently of the revision evidence floor.

4. **Cross-model handoff parity.** Every legally required dependency uses one canonical relation or aggregation path under `2026-06-10-calculation-aggregation-taxonomy-adr`. The ledger records source and target coordinates, applicable periods, aggregation behavior, clean-state behavior, and provenance. Parallel production paths are failures, not fallback mechanisms.

5. **Behavioral verification parity.** Every claimed producer or handoff is exercised through the real validated registry and production runtime. Numeric assertions use independently sourced expected values. Structural tests may prove identity, graph wiring, period selection, validation, clean-state behavior, and provenance, but must not be reported as numeric proof.

Each annual-matrix row records at least the exact coordinate, selected registry revision, official layout source, casilla population, deterministic-producer population, handoff population, verification population, and classification of every gap.

Existing oracle evidence may be enrolled only where the coordinate, revision, casilla, inputs, expected output, verification expectation, and oracle evidence map one-to-one. Each tranche must retain exact producer, legal-reference, source-reference, expectation, corpus, payload, scenario, and raw-evidence-locator identifiers. Ambiguous period or revision attribution is deferred rather than inferred.

The bounded Luna Max execution contract is:

- Begin each tranche with vault and code RAG discovery, targeted exact-symbol confirmation, and whole-file reads of every owned expectation, oracle, registry, and test file.
- Declare disjoint coordinate and whole-file ownership. Files shared by several candidate enrollments have one owner.
- Capture the pre-change worktree and conformance baseline. Validated conformance, coverage, and audit results are the proof surface; degraded reads are labeled discovery only.
- If a baseline gate is red, retain its exact signature, distinguish owner-surface failures from peer churn, and do not claim the gate as green.
- Restrict writes to exact existing-oracle enrollment and the minimum unambiguous verification expectation and test changes required to prove it.
- Require the symmetric external-grounding honesty gate, a real runtime reproduction of the independent expected value, validated verification-policy projection, and focused registry/conformance checks.
- Use no fakes, mocks, stubs, patches, skips, copied business logic, or hand-derived numeric expectations.
- Preserve all peer WIP. Do not stash, reset, restore, clean, overwrite, roll back, or opportunistically repair unrelated files.

Luna Max may continue without another architecture decision only while every action remains inside this contract. Encountering any SOL-return trigger stops that tranche before production semantics change.

## Rationale

The five-domain ledger is the only considered option that preserves year-specific legal truth while making gaps operational. It separates inventory from behavior, revision evidence from construct proof, structural verification from numeric correctness, and portfolio coverage from the finite annual matrix.

This permits useful progress through measurement and exact evidence enrollment without turning neighboring revisions, engine output, or revision-level citations into false authority.

## Consequences

The campaign gains explicit denominators, visible unsupported populations, enforceable producer closure, canonical handoff measurement, and an evidence-bounded Luna Max execution path.

Initial results may remain low, deferred, or unmeasured. Building the annual matrix, matching official layouts, tracing construct-level provenance, and obtaining independent numeric examples remain substantive work.

M100 `0150`, `0613`, and `1481` remain open. Their production closure requires focused legal, profile, or aggregation addenda, independent evidence, and SOL approval.

## Amendment (2026-08-05): S16 rental source-contract boundary

### Decision

The 2025 Modelo 100 `0150` producer remains `manual`, and fincas source readiness remains false. This amendment authorizes only the source-contract definition and its independent-oracle gate; it authorizes no registry, formula, binding, relation, profile, persistence, application, or `0150` producer change.

Before `0150` can become computed, the future implementation must expose one typed rental-source contract through the application aggregation boundary. The contract must:

- represent movable-property and furniture amortization as a separate typed asset and ledger identity, with basis, in-service and disposal dates, rate provenance, cumulative cap, and the contract-use interval; it must not overload the building-specific amortization ledger;
- persist the asset, contract-use interval, source identity, and source fingerprints in the canonical secure repository for the active profile bucket;
- allocate income, expenses, building amortization, and furniture amortization through explicit contract/date intersections exactly once, retaining source identity and reconciling allocated amounts to their persisted totals;
- expose one resolver with the canonical `BindingSourceKind`, typed provenance and fingerprints, stable repeated-row identity for `0150`, and parity between pull and calculate paths;
- apply explicit rounding stages and enforce the reduction boundary: only a positive qualifying per-contract yield is reducible; non-qualifying and negative yields produce zero.

### Promotion gate

No source-backed `0150` producer may be promoted until a real secure-storage-to-calculate oracle independently verifies the official worked example, a zero-reduction case, multiple contracts, partial-year contract boundaries, and repeated `0150` row identity. The oracle must prove source resolution, calculation, provenance, and reconciliation; a fixture that precomputes the result or bypasses the source path is insufficient. The accepted grounding for this contract is `2026-08-05-modelo-parity-rollup-s16-source-contract-research`.

### Scope boundary

This amendment does not decide the concurrent registry/application-wide IRP invocation-shape remediation and must not alter its files or public contract. The eventual rental resolver may integrate with the resulting calculation boundary only after that remediation has stabilized and the source-contract gate above is satisfied. Any new legal producer or manual-to-computed transition still returns to SOL under the five-domain execution contract.
