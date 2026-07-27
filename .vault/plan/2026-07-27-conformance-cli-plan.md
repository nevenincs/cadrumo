---
tags:
  - '#plan'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
tier: L2
related:
  - '[[2026-07-27-conformance-cli-adr]]'
  - '[[2026-07-27-conformance-cli-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `conformance-cli` plan

Ship the modelo schema conformance governance surface: declared per-revision provenance stamps, importable conformance fact libraries under `src/cadrumo`, a `python -m dev.registry.conformance` governance CLI, and a hardened one-way src/dev boundary.

## Description

This plan executes the accepted decision in the ADR listed in `related:`: fact-builders and the declared governance stamp land in the shipped application (`src/cadrumo`), the rendering and governance CLI lands in dev scaffolding (`dev/registry/conformance`), and the boundary between them is strictly one-way (dev imports src public facades; src never imports or reads anything under `dev/`). Status stays derived; only provenance (engineered_by, review_status, reviewed_by, reviewed_at) is declared, per-revision, fail-closed to pending_review on absence. Phase P01 lands the declared stamp end to end; P02 lifts the test-trapped conformance facts into typed libraries and adds the new fact-builders; P03 ships the dev CLI verbs (report, coverage, audit --check, stamp); P04 hardens the boundary and wires the CI gate and docs stubs; P05 verifies against real gates, persists the first real conformance report, and closes with the mandatory fresh-context honesty review. Every implementation step is preceded by the mandatory semantic discovery probe, and registry-surface steps must check for peer WIP before first edit in this shared worktree.

## Steps

### Phase `P01` - declared provenance schema

Land the per-revision governance stamp end to end: core enum, strict revision schema scalars, loader hydration, and refusal tests.

- [ ] `P01.S01` - add the RevisionReviewStatus StrEnum (pending_review, agent_reviewed, operator_reviewed) to the core closed-value-set surface and export it through the core facade; `src/cadrumo/core`.
- [ ] `P01.S02` - add optional governance scalars engineered_by, review_status, reviewed_by, reviewed_at to ModeloRevision with a model validator refusing reviewed_by or reviewed_at unless review_status is beyond pending_review, absence defaulting to pending_review; `src/cadrumo/domain/calculations/registry/_schema.py`.
- [ ] `P01.S03` - hydrate the governance scalars from revision.toml in the TOML compiler, rejecting unknown or misplaced governance keys loudly; `src/cadrumo/domain/calculations/registry/_loader.py`.
- [ ] `P01.S04` - add governance-stamp loader tests covering roundtrip, fail-closed default on absence, refusal of incoherent stamp combinations, and an anti-tautology mutation proof; `src/cadrumo/domain/calculations/registry/tests/test_governance_stamp.py`.

### Phase `P02` - fact lifts into src libraries

Lift the test-trapped conformance facts into importable typed libraries under src/cadrumo and re-point their gates without weakening them.

- [ ] `P02.S05` - lift the registry-wide external-oracle grounding fold (per-modelo oracle inventory, revision selection, both-direction honesty facts) into a new importable module exported through the registry facade; `src/cadrumo/domain/calculations/registry/_external_grounding.py`.
- [ ] `P02.S06` - re-point the external-oracle grounding gate at the lifted library in the same commit, keeping both honesty directions asserted; `src/cadrumo/domain/calculations/registry/tests/test_external_oracle_grounding_enrolled.py`.
- [x] `P02.S07` - extract the fichero-BOE required-applicable casilla derivation into one shared public function consumed by the export gate; `src/cadrumo/application/filing/_export.py`.
- [x] `P02.S08` - re-point the export completeness and fichero-BOE parity tests at the shared required-set derivation, removing the mirrored duplicate; `src/cadrumo/application/filing/tests`.
- [ ] `P02.S09` - add the classification-coherence checker (calculation_class vs tax_domain vs core modelo constants, plus the declared-but-dead axis census) as an importable typed fact-builder; `src/cadrumo/domain/calculations/registry/_classification_coherence.py`.
- [ ] `P02.S10` - add the per-revision conformance profile composer with strict typed row models, composing model-law coverage, support matrix, registry-scope diagnostics, authorization state, external grounding, and governance stamps; `src/cadrumo/application/registry/_conformance.py`.
- [ ] `P02.S11` - add structure-and-wiring tests for the classification-coherence checker grounded in the live registry tree; `src/cadrumo/domain/calculations/registry/tests/test_classification_coherence.py`.
- [ ] `P02.S12` - add structure-and-wiring tests for the conformance profile composer, asserting provenance fields and degraded-mode labelling, never author-invented numeric expectations; `src/cadrumo/application/registry/tests/test_conformance_profile.py`.

### Phase `P03` - conformance governance CLI in dev

Ship the python -m dev.registry.conformance Typer trio: report, coverage, audit --check, and stamp verbs over the src fact libraries.

- [ ] `P03.S13` - build the pure manager composing the src fact facades plus ModeloLocaleManager coverage rows, with typed payload models and a self-labelling no-validate degraded mode; `dev/registry/conformance/manager.py`.
- [ ] `P03.S14` - build the Typer cli and __main__ with report and coverage verbs, greppable key=value text rows and strict --json payloads; `dev/registry/conformance`.
- [ ] `P03.S15` - add the audit verb with --check gating exit, shrink-only JSON baseline, anti-vacuity floor, and empty-input SystemExit refusal; `dev/registry/conformance/cli.py`.
- [ ] `P03.S16` - add the stamp verb writing the per-revision governance scalars with vocabulary and coherence validation; `dev/registry/conformance/_stamp.py`.
- [ ] `P03.S17` - add dev-side CLI behaviour tests covering every verb, the ratchet, the vacuity refusal, and the degraded-mode labelling; `dev/tests/test_registry_conformance_cli.py`.

### Phase `P04` - boundary hardening and gates

Make the one-way src/dev boundary enforceable, wire the CI gate, and regenerate the API docs stubs.

- [x] `P04.S18` - add the dev-path isolation gate asserting no shipped module imports dev.* or embeds a dev/ path literal, with an injectable-root anti-tautology proof; `src/cadrumo/tests/test_dev_path_isolation.py`.
- [ ] `P04.S19` - add the dev-side pytest wrapper gate running the conformance audit --check against the committed baseline; `dev/tests/test_registry_conformance_gate.py`.
- [ ] `P04.S20` - regenerate the API reference stubs for the new src modules via the apidocs scaffold CLI and land the deltas with the source change; `docs/api`.
- [ ] `P04.S21` - wire a conformance recipe invoking python -m dev.registry.conformance report and audit into the task runner; `justfile`.

### Phase `P05` - verification and closeout

Run the real gates, persist the first conformance report as an audit, and close with a fresh-context honesty review.

- [ ] `P05.S22` - run the full-tree collect-only gate and the scoped registry, filing, and dev suites, recording failure signatures and triaging owner vs peer churn; `src/cadrumo`.
- [ ] `P05.S23` - run the first real conformance report over the bundled registry and persist the findings as a vault audit document; `.vault/audit`.
- [ ] `P05.S24` - run the fresh-context campaign-close honesty review and track every surfaced item as a new step or a formally deferred follow-up; `.vault/audit`.

## Parallelization

P01 and P02 are independent of each other and may run in parallel (the composer step P02.S10 consumes the P01 schema surface for its governance column, so P02.S10 lands after P01.S02 and P01.S03). Within P02, the three lift tracks are independent: S05+S06 (external grounding), S07+S08 (fichero-BOE derivation), S09+S11 (classification coherence); each re-point step follows its lift in the same commit. P03 depends on P02 (and P02.S10 in particular) and is internally sequential except P03.S16, which depends only on P01. P04.S18 is independent and may start immediately; P04.S19 depends on P03.S15; P04.S20 and P04.S21 follow the src modules and CLI they document. P05 is strictly last and sequential. All registry-schema steps (P01.S02, P01.S03) touch peer-contended files and must serialize with any live peer WIP rather than assuming exclusive ownership.

## Verification

- Registry loader and schema suites pass with the governance scalars present, absent, and incoherent (refusal), including the anti-tautology mutation proof in `src/cadrumo/domain/calculations/registry/tests/test_governance_stamp.py`.
- The re-pointed gates (external grounding, export completeness, fichero-BOE parity) stay green and non-vacuous after the lifts, with no weakened assertion.
- `python -m dev.registry.conformance report` renders a row for every registry modelo and revision (anti-vacuity floor enforced), `coverage` reconciles with the research counts axis by axis, and `audit --check` exits 1 on a seeded baseline regression and 0 at the committed baseline.
- The dev-path isolation gate fails when a `dev.*` import or `dev/` path literal is injected into a shipped module under an injectable root, and passes on the real tree.
- `python -m dev.docs.apidocs scaffold --check` and the full-tree `uv run --no-sync pytest --collect-only -q` gate are clean, with owner-vs-peer triage recorded for any residual red.
- The first conformance report is persisted as a vault audit document and the campaign-close honesty review has run, with every surfaced item tracked as a step or a formally deferred follow-up.
- The plan is complete when every Step row is closed and each closed Step has a matching exec record.
