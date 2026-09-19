---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:be2f94b41536173cd108818d4bfd249c9e6c960daace33daa1bc38f2d899f1bb'
related:
  - "[[2026-08-24-deadline-window-revision-authority-adr]]"
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - "[[2026-07-09-m210-plazo-keying-adr]]"
---

# `deadline-window-revision-authority` audit: `architecture corpus and lifecycle reconciliation`

## Scope

Reconcile the accepted deadline-window revision-authority decision against its related temporal-coverage and M210 decisions, the current registry/deadline implementation, and the feature plan. The review used Vaultspec RAG semantic discovery first, then exact-symbol confirmation for revision selection, authority projection, filing-window matching, supported-year coverage, cadence derivation, and the civil-date clock seam.

## Findings

### decision-topology | low | One governing ADR composes cleanly with its parent decisions

The feature has one accepted governing ADR, `2026-08-24-deadline-window-revision-authority-adr`. It refines rather than contradicts the accepted temporal-coverage authority and M210 plazo-keying decisions: supported filing years remain registry-owned, `select_revision` remains the law selector, M210 reuses typed qualifier authorities, and deadline rows remain regulatory data. No supersession, duplicate ADR, off-taxonomy status, or stranded decision was found.

### decision-vs-code | low | Canonical authority architecture is implemented

Current code reflects the accepted decision. `ValidatedRegistryAuthority.deadline_windows` law-selects each candidate through `select_revision`, validation refuses non-owner rows and incomplete periodic cadence, `resolve_filing_window` is the shared qualifier-aware matcher, and the deadline engine consumes the authority projection without deduplication. RAG plus exact-symbol sweeps found no competing production revision selector, deadline catalogue, supported-year declaration, or downstream multiplicity erasure in the reviewed path.

### lifecycle-coupling | high | S35 conflates feature acceptance with unrelated repository health

Plan step `W04.P13.S35` combines attributable feature gates with full-repository pytest, formatting, locale, and generated-reference health. In a cooperative shared worktree, those repository-wide observations can remain red solely because concurrent unrelated campaigns are incomplete. That makes the deadline feature's completion state depend on mutable work outside its architecture and authorization boundary, although the feature-specific registry, resolver, engine, CLI, RAG, and formal-review evidence is already independently measurable.

Repository-wide gates still matter for release readiness and must be reported honestly. They should not be the sole completion predicate for this feature unless a failure is attributable to deadline-window changes. The current wording therefore forks two facts: feature acceptance and repository/release health.

### legal-date-tests | medium | Exact facts and generalized invariants need distinct homes

Exact filing dates are regulated facts. Their canonical home is the revision-owned registry row with specific official provenance, and source-fidelity tests must assert those literal dates so a legally incorrect value fails. Architecture and fleet behavior tests should instead derive the supported horizon from `catalogues.supported_filing_years` and compare semantic coordinates or legally shared relationships across modelos and periods.

The current generalized authority tests follow that split. The plan still freezes campaign census numbers and the 2022-2026 adjudication scope, which is valid historical execution evidence, but those counts and years must not become the enduring pass condition for future horizons.

### transient-reference-date | medium | Runtime today is a clock input, not a durable deadline fact

Production deadline status classification defaults through the canonical `today_madrid()` clock seam and accepts explicit reference dates. This correctly treats “today” as transient Europe/Madrid civil runtime context, distinct from revision-owned filing dates.

Two consistency debts remain visible in the reviewed path: deadline-engine docstrings still say `date.today()` despite using `today_madrid()`, and `test_modelo_calculate_recargo_notice.py` reads `date.today()` directly while claiming deterministic selection. That test can change posture at midnight or exhaust its fixed 2026 horizon; it should inject or freeze the canonical clock and derive candidate filing years from registry authority rather than encoding the execution date as an implicit test oracle.

### lifecycle-boundary | low | Research grounds, ADR decides, audits find

The research records the defect inventory and option evidence; the ADR owns the architectural decision; the plan sequences implementation; audits record verification. Some historical counts and implementation facts necessarily appear in execution records, but no substantive ADR decision was found displaced into the reviewed research or audits. No content-preserving relocation was required.

## Recommendations

1. Applied: S35 now separates mandatory attributable deadline gates from an honestly recorded, pinned, revision-scoped whole-repository checkpoint. Unrelated failures are routed to their owning campaigns and no longer define deadline feature acceptance.
2. Applied: the accepted ADR and reference now distinguish literal source-fidelity dates from catalogue-driven behavioral invariants, define “today” as an injectable `today_madrid()` reference input, and bind finite attributable feature acceptance to the quality-gate-zero-closure architecture.
3. Applied: plan step S45 now owns correction of stale `date.today()` documentation and direct wall-clock deadline tests, including supported-year derivation.
4. Recommended active goal wording: “Deliver and verify a cohesive, revision-owned deadline and filing-window authority for every supported modelo and filing year: canonical law-selected ownership, complete registry-declared cadence, one qualified resolver, thin engine/CLI consumers, no duplicate authority, source-grounded legal dates, and catalogue-driven behavioral invariants. Completion requires all attributable feature gates green and no unresolved deadline-window findings; repository-wide unrelated health is reported separately.”
5. Keep the existing ADR accepted. The curation refines completion and verification semantics without changing the chosen production architecture.
