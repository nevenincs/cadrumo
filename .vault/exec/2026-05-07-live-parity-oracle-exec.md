---
tags:
  - '#exec'
  - '#live-parity-oracle'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-07-live-parity-oracle-plan]]"
  - "[[2026-05-07-live-parity-oracle-adr]]"
  - "[[2026-05-07-live-parity-oracle-reference]]"
  - "[[2026-05-08-live-parity-oracle-adr]]"
---

# `live-parity-oracle` execution summary (phases 2 — 5)

Records the autonomous execution of phases 2 — 5 of the
live-parity-oracle plan. Phase 1 was already committed before this
execution window opened. Phase 6 is gated on user-side
certificate-auth provisioning and remains pending.

## Phase 1 (prior commit `2d7e8b9e`)

`authenticated_simulator` cross-reference surface category added to
`LiveCrossReferenceDecision` schema with validator rules requiring
`executable_parity_evidence`, `requires_authentication=True`, allowed
methods restricted to `{GET, HEAD, OPTIONS, POST}`, and synthetic
data permitted by default. Pair `(authenticated_simulator,
vat_id_check)` added to `_COMPATIBLE_SURFACE_PAIRS`. Nine contract
tests in `test_authenticated_simulator_surface.py` verify positive
shape, each negative validator rule, compatibility-table membership,
and backwards-compat for the existing surface categories.

## Phase 2 (rolled into commit `ecd02bb9`)

GROI Spanish-ROI oracle bound to modelo 349 via a registry-data
cross-reference (not test-side wiring):

- Captured AEAT VIES gestiones page to
  `corpus/aeat_official/instructions/groi/aeat-vies-gestiones.html`
  (sha256 `5b439bae...`) and registered it as
  `aeat-groi-spanish-roi-procedure` source under
  `registry/aeat/legal/iva.toml` with
  `evidence_tier="executable_parity_evidence"`.
- Added cross-reference `modelo-349-groi-spanish-counterparty-check`
  to `registry/aeat/modelos/349.toml` declaring
  `surface=authenticated_simulator`,
  `oracle_id=aeat-groi-spanish-roi-checker`,
  `allowed_methods=("GET", "POST")`,
  `forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS`,
  `requires_authentication=True`, `synthetic_data_allowed=True`.
- Added the new cross-reference id and source ref to construct
  `modelo-349-informative` so the construct republishes everything
  its members consume.
- Re-exported `_groi_oracle`, `_live_parity`, and
  `AEAT_WRITE_FORBIDDEN_ACTIONS` from
  `aeat.domain.calculations.registry` so live tests outside the
  registry package satisfy the absolute-private-import boundary.
- Adapter live tests
  `test_groi_dependency_chain_live.py` and
  `test_groi_oracle_live.py` updated to use the public path.

This phase landed mixed with parallel-agent's MM-7-cuota work in
commit `ecd02bb9` (the parallel agent committed during the
pre-commit window); the GROI files are intact in the bundled commit.

## Phase 3 (commit `e6d8773f`)

Wired `aeat app registry verify` and `aeat app registry
audit-oracles` into `.github/workflows/ci.yml` as build gates that
run before the unit-test stage on every push and PR (ubuntu+windows
matrix). The audit-oracles step's docstring inline directs future
agents at the local remediation command.

## Phase 4 (commit `c9a16aaf`)

Authored `.github/workflows/aeat-drift-detector.yml` to run the GROI
live suite weekly (Sundays 07:00 UTC) under stored cl@ve-movil
secrets, auto-opening a labelled issue on failure. Activation gated
on the user provisioning the secrets named in the workflow header.

## Phase 5 (commit `4abfbf12`)

Authored the binding how-to under
`.vault/reference/2026-05-07-live-parity-oracle-reference.md`. Walks
a future agent through picking the oracle id, confirming surface
compatibility, declaring the cross-reference, capturing corpus
evidence, writing the regression test, and running the gate
sequence. Step 7 explicitly bakes the no-tautology mandate into the
test-authoring guidance.

## Gates achieved

- `ruff` / `ty` clean across all touched source files.
- `aeat app registry verify --json` reports `verified: true`.
- `aeat app registry audit-oracles --json` reports
  `failure_count: 0` with both `aeat-groi-spanish-roi-checker` and
  `aeat-nif-iva-checker` registered.
- `test_public_api_boundaries.py` passes (no source file outside
  the registry imports a registry private module by absolute path).
- `test_authenticated_simulator_surface.py` 9/9 passes.

## Pending

Phase 6 (IXVI certificate-auth probe) remains gated on user-side
configuration via `aeat setup auth configure --provider certificate`;
no code changes are blocking it. The plan's contingency branches
(cert unlocks IXVI vs. cert insufficient) are documented in the
plan's Phase 6 section.

A pre-existing parallel-agent state mismatch on the GROI corpus
file's byte count (registered `bytes=11499` vs. workspace `11492`
trailing-whitespace drift) is captured in commit `ecd02bb9`'s
message; resolution requires re-fetching the corpus or amending the
registered hash, neither of which is in scope for this execution
window.

## Cross-reference applicability gate (slices 1 — 12, 2026-05-08)

Second execution window adds the cross-reference applicability gate
authored under ADR `2026-05-08-live-parity-oracle-adr.md`. The gate
makes optional bindings (GROI for ROI / intracom subjects, OSS-369
for OSS-enrolled subjects) skip cleanly when the profile says off.

### Schema (commit `73302e4c`)

`LiveCrossReferenceDecision` gains
`applicability_predicates: tuple[ProfilePredicateDefinition, ...]`
and `applicability_condition_mode: Literal["all", "any"] = "all"`.
The validator mirrors `FilingScheduleDefinition`'s any-mode + empty
rejection. Both fields default to empty / `"all"` so every binding
declared before the gate landed remains unconditionally applicable.

### Evaluator + typed result (commit `73302e4c`)

`evaluate_cross_reference_applicability(decision, profile_facts)`
returns a strict frozen `CrossReferenceApplicability` with
`applicable`, `matched_explanations`, and `unmet_predicate_fields`.
Reuses `profile_condition_matches` from `_schedules.py` rather than
duplicating the predicate resolver.

### Profile fields (commits `73302e4c` + Slice 10)

Two new boolean fields under `iva`:
- `iva.roi_enrolled` — Modelo 036/037 ROI census state
- `iva.oss_enrolled` — OSS / IOSS one-stop-shop enrollment

Both are required=false (defaults to enrolled=false) and
effective_dated=true so historical state stays accurate as the
taxpayer enrolls or de-enrolls over time.

### Bindings

- `modelo-349-groi-spanish-counterparty-check` (commit `73302e4c`):
  `does_intracomunitario == true` predicate.
- `modelo-369-exterior-filed-declarations-read` (Slice 10):
  `iva.oss_enrolled == true` predicate. Subjects outside the OSS
  regime never invoke the read surface.

### Audit (Slice 8)

`aeat app registry audit-oracles --json` gains a new
`applicability_declarations` array surfacing each gated binding's
`modelo_id`, `revision_id`, `cross_reference_id`,
`applicability_condition_mode`, and `predicate_fields`. Backed by
`CrossReferenceApplicabilityDeclaration` (pydantic v2 strict
frozen). The audit reads declared state only — never re-evaluates
predicates.

Today's count: 2 declarations (GROI + OSS-369). Future bindings
that warrant the gate self-register here.

### Corpus (Slice 7)

`corpus/aeat_official/instructions/modelo_036/aeat-modelo-036-procedure.html`
captured from the AEAT G322 procedure page (36079 bytes,
sha256 `fd5264e1...`). Registered as
`aeat-modelo-036-roi-enrollment-procedure` source under
`registry/aeat/legal/iva.toml` for use as the legal grounding of
ROI enrollment claims.

### Tests (Slices 5 + 6)

`test_cross_reference_applicability.py` — 6 tests cover
backwards-compat, all-mode, any-mode, schema rejection of any-mode
+ empty, the registry-loaded GROI binding's predicate presence, and
the typed not-applicable evaluation against a non-intracom profile.

`test_groi_dependency_chain_live.py` gains a profile-gated test
that loads the binding and asserts the typed
`CrossReferenceApplicability` returns applicable=False for a
non-intracom profile, verifying the dependency-chain entry-point
short-circuits before any oracle resolution.

### How-to (Slice 9)

`.vault/reference/2026-05-07-live-parity-oracle-reference.md` gains
"Step 3.5 — declare applicability predicates for optional bindings"
documenting the universal vs. optional decision, predicate
declaration syntax, and the typed return shape future agents
should consume.

### Gates achieved

- `ruff` / `ty` clean across every touched source file.
- `aeat app registry verify --json` reports `verified: true`.
- `aeat app registry audit-oracles --json` reports
  `failure_count: 0` with 2 applicability declarations surfaced.
- 96 / 96 tests pass on the touched-surface sweep
  (test_cross_reference_applicability +
  test_authenticated_simulator_surface +
  test_resolve_cross_reference_oracle +
  test_audit_oracle_surface_compatibility +
  test_public_api_boundaries + test_registry_schema +
  test_schema_hygiene + user_profile/).

## Hardening pass (slices 13 — 15, 2026-05-08)

Third execution window hardens the applicability gate against the
two main regression vectors: typo'd predicate fields and missing
runtime enforcement.

### Slice 13 — Predicate field validation against profile schema

`UserProfileRegistryContractIssue` gains the
`cross_reference_applicability` surface literal. New
`_cross_reference_applicability_issues` walker checks every
declared `applicability_predicates[*].field` against the
schedule-predicate index built from the user-profile schema. A
typo'd field surfaces a typed error at registry load time,
mirroring the existing schedule / deadline-window predicate
validation. New contract test
`test_user_profile_contract_rejects_typoed_predicate_field` proves
the gate catches a substituted bad selector on the GROI binding.

### Slice 14 — Resolver-side runtime gate

`resolve_cross_reference_oracle` accepts optional `decision` and
`profile_facts` arguments. When both are supplied the resolver
calls `evaluate_cross_reference_applicability` first and raises a
typed `RegistryValidationError` naming the unmet predicate fields
if the binding is not applicable to the profile. Three new
contract tests cover the applicable-pass, not-applicable-raise,
and legacy-omitted (gate skipped, opt-in) branches. The
catalogue-only path stays intact for adapters that haven't yet
threaded profile facts.

### Slice 15 — OSS-369 mirror tests

Two new tests on the OSS-369 binding mirror the GROI test pattern:
applicability=False under `iva.oss_enrolled=false`, applicability=
True under `iva.oss_enrolled=true`, with the expected typed
unmet-fields shape; plus a structural pinning test that catches
predicate drop on a future TOML edit. Both share a
`_load_binding(modelo_id, revision_id, cross_reference_id)` helper
to avoid re-walking the registry per test.

### Gates achieved (2026-05-08 hardening)

- `ruff` / `ty` clean across every touched source file.
- `aeat app registry verify --json` reports `verified: true`.
- `aeat app registry audit-oracles --json` reports `failure_count:
  0` with 2 applicability declarations surfaced.
- Touched-surface test sweep: 102 / 102 pass (added 6 new tests
  across the three slices, plus the existing 96 from the prior
  windows).

## Consistency pass (slices 17 — 18, 2026-05-08)

Fourth execution window aligns the filing-schedule layer with the
cross-reference applicability gate and adds an orphan-oracle audit
surface.

### Slice 17 — Modelo 369 filing schedules gate on iva.oss_enrolled

All three Modelo 369 filing schedules (esquema-exterior trimestral,
esquema-union trimestral, esquema-importacion mensual) declared no
profile_conditions, so the schedule fired for every taxpayer
regardless of OSS enrollment. Each now declares the
`iva.oss_enrolled == true` predicate, mirroring Modelo 349's
existing `does_intracomunitario` gate. Subjects who haven't
enrolled in the OSS / IOSS regime no longer see the schedule fire
at all; the cross-reference applicability gate at the binding
layer is now defense-in-depth rather than the sole filter.

New contract test
`test_oss_369_filing_schedules_select_only_when_oss_enrolled`
asserts the schedule fires only when the profile carries
`iva.oss_enrolled=true`, across all three esquemas.

### Slice 18 — Audit-oracles surfaces orphan oracles

`collect_orphan_oracle_ids(modelos, catalogue)` returns catalogue
oracle ids that no cross-reference binds. Surfaces drift in either
direction (registered-but-unused, or rename without catalogue
update). audit-oracles JSON gains an `orphan_oracle_ids` array.

Today: `aeat-nif-iva-checker` is correctly flagged as orphan (the
catalogue carries it but no cross-reference binds it).

Two new contract tests cover both branches: the orphan flagged
when present in catalogue but absent from bindings, and the empty
result when every catalogue entry is bound.

### Gates achieved (2026-05-08 consistency)

- `ruff` / `ty` clean across every touched source file.
- `aeat app registry verify --json` reports `verified: true`.
- `aeat app registry audit-oracles --json` reports `failure_count:
  0`, 2 applicability declarations, 1 orphan oracle.
- 105 / 105 tests pass on the touched-surface sweep (added 3 new
  tests for the schedule and orphan-oracle gates).
