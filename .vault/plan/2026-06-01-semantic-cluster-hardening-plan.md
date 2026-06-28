---
tags:
  - '#plan'
  - '#semantic-cluster-hardening'
date: '2026-06-01'
modified: '2026-06-01'
tier: L3
related:
  - '[[2026-06-01-semantic-cluster-hardening-adr]]'
  - '[[2026-06-01-semantic-cluster-hardening-research]]'
  - '[[2026-05-31-core-authority-adr]]'
---


# `semantic-cluster-hardening` `campaign` plan

A RAG-driven re-audit-and-remediate campaign that cross-references the
`src/aeat` tree against the accepted canonical-authority decisions and
removes duplication, dead code, and domain functionality redefinition. It
adds a standing 7th swarm-audit axis (semantic functionality-cluster
overlap), treats all prior research as unverified leads, and prioritises the
408-added / 1305-modified module delta since the 2026-05-19 baseline. Work
proceeds as a delta-audit gate (W01) feeding four sequenced remediation
Waves; every remediation Step is one cohesive change landing as one atomic
explicit-path commit with a real behaviour test.

## Wave `W01` - delta-audit gate and Axis-7 establishment

Establishes the standing 7th cadence axis and produces the verified functionality-cluster inventory over the 408-added/1305-modified delta since the 2026-05-19 baseline. Feeds every downstream Wave; prior research is treated as unverified leads, re-confirmed here with RAG plus rg.

### Phase `W01.P01` - Axis-7 cadence establishment

Add the standing 7th axis to the swarm-audit cadence and sync it into provider surfaces.

- [x] `W01.P01.S01` - Add the standing 7th axis (semantic functionality-cluster overlap and canonical-definition enrollment) to the cadence rule; `.vaultspec/rules/rules/aeat-swarm-audit-cadence.md`.
- [x] `W01.P01.S02` - Sync the amended cadence rule into provider surfaces via vaultspec-core; `.vaultspec`.

### Phase `W01.P02` - delta enumeration and RAG sweep

Enumerate the changed-module delta since baseline, run the Axis-7 RAG-plus-rg sweep, and persist a verified-cluster audit document.

- [x] `W01.P02.S03` - Enumerate Python modules added and modified since the 2026-05-19 baseline; `src/aeat`.
- [x] `W01.P02.S04` - Run the Axis-7 RAG functional-concept sweep over the delta and verify candidate clusters with rg; `src/aeat`.
- [x] `W01.P02.S05` - Persist the verified functionality-cluster delta-audit document; `.vault/audit`.

## Wave `W02` - duplication-cluster consolidation

Consolidates verified substitutable duplication clusters to canonical homes with behaviour and roundtrip tests. Seeded by the decimal-to-cents triplication; extended by clusters the delta sweep surfaces. Depends on W01.

### Phase `W02.P03` - numeric primitive consolidation

Create the canonical core money/Decimal primitive and migrate the three confirmed cents-rounding sites onto it.

- [x] `W02.P03.S06` - Create the canonical core money Decimal primitive with half-up cents rounding; `src/aeat/core/money/__init__.py`.
- [x] `W02.P03.S07` - Add a behaviour and roundtrip test for the core money primitive; `src/aeat/core/money/test_money.py`.
- [x] `W02.P03.S08` - Migrate the fincas rounding helper onto the core money primitive; `src/aeat/domain/fincas/_rounding.py`.
- [x] `W02.P03.S09` - Migrate the inventory quantize helper onto the core money primitive; `src/aeat/domain/profile/inventory/__init__.py`.
- [x] `W02.P03.S10` - Migrate the assets quantize helper onto the core money primitive; `src/aeat/domain/profile/assets/__init__.py`.

### Phase `W02.P04` - delta-surfaced cluster triage

Triage the verified clusters from the delta audit and insert one consolidation Step per confirmed cluster.

- [x] `W02.P04.S11` - Triage verified delta-audit clusters and insert one consolidation Step per confirmed cluster; `.vault/audit`.

## Wave `W03` - base-definition and pydantic enrollment re-verification

Re-proves, never trusts, the claimed canonical enrollment completeness (STRICT_FROZEN_CONFIG, typed aliases, enums) against the current tree, with the added modules as prime suspects. Depends on W01.

### Phase `W03.P05` - STRICT_FROZEN re-verification

Re-scan the current tree for local strict/frozen ConfigDict copies and close any stragglers against the canonical constant.

- [x] `W03.P05.S12` - Re-scan the current tree for local strict-frozen ConfigDict copies versus the canonical constant; `src/aeat`.
- [x] `W03.P05.S13` - Triage the local-config stragglers and insert one migration Step per confirmed site; `src/aeat`.

### Phase `W03.P06` - typed-alias and enum enrollment re-verification

Re-run the diagnostics enforcement suite, record gaps in the delta, and insert one migration Step per confirmed gap.

- [x] `W03.P06.S14` - Re-run the diagnostics enrollment enforcement suite and record gaps; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W03.P06.S15` - Triage typed-alias and enum enrollment gaps in the delta and insert one migration Step per confirmed gap; `src/aeat`.

## Wave `W04` - exception consolidation

Authors the blank exception-restructure ADR, deletes the unused DomainError under a safeguarded commit, normalises error-module naming, and re-verifies every domain error base roots at AeatError. Depends on W01.

### Phase `W04.P07` - exception ADR and DomainError deletion

Author the exception-restructure ADR and delete the unused DomainError under a safeguarded commit sequence.

- [x] `W04.P07.S16` - Author the exception-restructure ADR content; `.vault/adr/2026-05-09-exception-restructure-adr.md`.
- [x] `W04.P07.S17` - Commit surrounding exception work as the safeguard checkpoint before deletion; `src/aeat/domain`.
- [x] `W04.P07.S18` - Delete the unused DomainError in its own clearly-messaged commit; `src/aeat/domain/_errors.py`.

### Phase `W04.P08` - error-module naming normalisation

Rename the four errors.py modules to the dominant _errors.py convention, each with consumer updates.

- [x] `W04.P08.S19` - Rename the renta error module to the _errors convention with consumer updates; `src/aeat/domain/renta/errors.py`.
- [x] `W04.P08.S20` - Rename the iva error module to the _errors convention with consumer updates; `src/aeat/domain/iva/errors.py`.
- [x] `W04.P08.S21` - Rename the normatives error module to the _errors convention with consumer updates; `src/aeat/domain/normatives/errors.py`.
- [x] `W04.P08.S22` - Rename the manuals error module to the _errors convention with consumer updates; `src/aeat/domain/manuals/errors.py`.

### Phase `W04.P09` - error-root re-verification

Re-verify every domain package error base still roots at AeatError.

- [x] `W04.P09.S23` - Re-verify every domain package error base roots at AeatError; `src/aeat/domain`.

## Wave `W05` - domain redefinition and taxonomy

Re-confirms prior duplication-sweep conceptual leads against current state, promotes tax_domain to a closed core StrEnum with loader hydration, and renames the mis-named portals Subdomain. Depends on W01; runs on the cleaned field after W02-W04.

### Phase `W05.P10` - tax_domain typed-constant promotion

Add a closed core tax_domain StrEnum, hydrate it at the loader boundary, and re-type the schema field with a roundtrip test.

- [x] `W05.P10.S24` - Add the closed tax_domain StrEnum typed-constant to core; `src/aeat/core/_tax_domain.py`.
- [x] `W05.P10.S25` - Hydrate tax_domain to the typed enum at the registry loader boundary; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `W05.P10.S26` - Re-type the ModeloDefinition tax_domain field to the enum; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W05.P10.S27` - Add a roundtrip test for tax_domain loader hydration; `src/aeat/domain/calculations/registry/test_tax_domain.py`.

### Phase `W05.P11` - Subdomain rename

Rename the mis-named portals Subdomain StrEnum to a portal-host concept with consumer updates.

- [x] `W05.P11.S28` - Rename the portals Subdomain StrEnum to a portal-host concept with consumer updates; `src/aeat/domain/portals/_categories.py`.

### Phase `W05.P12` - prior-lead re-confirmation

Re-confirm prior duplication-sweep conceptual leads against current state and insert one Step per confirmed redefinition.

- [x] `W05.P12.S29` - Re-confirm prior duplication-sweep conceptual leads and insert one Step per confirmed redefinition; `.vault/audit`.

## Wave `W06` - registry calculation-gate red remediation

Restore the registry meta-gates and calculation-completeness coverage to green. Read-only triage classified the 7 standing registry-gate failures as 2 real coverage/provenance gaps (M210/2025 completeness manifest; M390 fixture provenance) plus 5 stale-baseline / allowlist / born-stale-test drifts; none are filing-math defects, all self-introduced by rapid registry building. Each Step is gated by re-running its named test to green.

### Phase `W06.P13` - completeness-manifest restoration

Close calculation-completeness coverage: re-derive the drifted M100/2024 manifest from the calculation surface (stale), and author the missing M210/2025 manifest so the load-time gate is live for IRNR 2025 (real coverage gap).

- [x] `W06.P13.S30` - Re-derive the modelo-100/2024 calculation-completeness manifest from the registry calculation surface (STALE: ~41 closure-only casillas drifted in since last refresh); `use derive_calculation_completeness_casillas, not hand-typed numbers; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/completeness-manifest.toml`.
- [x] `W06.P13.S31` - Author the missing modelo-210/2025 completeness manifest (REAL coverage gap: 7-casilla closure, gate currently dark for IRNR 2025) so the load-time completeness gate is live; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/completeness-manifest.toml`.

### Phase `W06.P14` - validator reviewability baseline

Refresh the per-module reviewability baselines after benign docstring growth (4 stale baselines) and address the one real module-size regression in _validate_cross_revision.py (387 lines).

- [x] `W06.P14.S32` - Bump the 4 stale per-module line baselines drifted past by docstring/xlink growth (_validate.py 204->206, _validate_record_sections.py 238->240, _validate_relation_periods.py 198->203, _validate_revision_sections.py 252->254); `src/aeat/domain/calculations/registry/test_registry_reviewability.py`.
- [x] `W06.P14.S33` - Resolve _validate_cross_revision.py exceeding the 300-line reviewability cap (REAL: 387 lines from the continuity feature): split the continuity-drift helpers into a sibling module, or add a reviewed explicit baseline; `src/aeat/domain/calculations/registry/_validate_cross_revision.py`.

### Phase `W06.P15` - meta-gate allowlist and waiver refresh

Re-curate the two frozen-list meta-gates that drifted red against legitimate downstream changes: the schema-hygiene validator-test allowlist and the hand-summed-aggregation waiver list.

- [x] `W06.P15.S34` - Add the 3 legitimate validator-mechanics test files (test_schema.py, test_registry_schema.py, test_catalogue_verification.py) to the schema-authority-construction allowlist (they exercise broken-shape inputs the loader cannot reach); `src/aeat/domain/calculations/registry/test_schema_hygiene.py`.
- [x] `W06.P15.S35` - Refresh the hand-summed-aggregation waivers: rename the stale prior_filing_history->prior_year_history key, add waivers for the new legitimate tests, and confirm the 2 cross-dependency cumulative-sum asserts against an oracle or convert to delta-proof; `src/aeat/domain/calculations/registry/test_tautology_gate.py`.

### Phase `W06.P16` - born-stale test and fixture provenance

Repair the born-stale legal-entity rate-schedule test against the restructured Modelo 200 formula, and reconcile the M390 verification-source provenance tag with its mixed real/synthetic fixture pool.

- [x] `W06.P16.S36` - Fix the born-stale legal-entity rate-schedule test to navigate the restructured nested dispatch (args[2].args[2].args[2].dispatch_table) and assert the full 8-key entity-form set including sal/sll; `src/aeat/domain/calculations/registry/test_taxpayer_rate_schedules.py`.
- [x] `W06.P16.S37` - Reconcile the M390 verification_source provenance (REAL mislabel): regenerate 2021-0A as a synthetic fixture matching the synthetic_from_aeat_published_text tag, or split the mixed real/synthetic pool by tagged profile; `do not revert the tag; `src/aeat/tests/fixtures/justificantes/_generate.py`.

## Parallelization

W01 (the delta-audit gate) must land first; it produces the verified-cluster
inventory that W02 and the W03/W06 triage Steps consume. W02 through W05 are
sequenced by default, but W03 (enrollment re-verification) carries no hard
dependency on W02 and may run in parallel with it once W01 closes. W05 runs
last so the taxonomy work lands on a field already cleaned by W02 to W04.
Within a Wave, the triage Steps (`W02.P04.S11`, `W03.P05.S13`,
`W03.P06.S15`, `W05.P12.S29`) are expansion points: they insert one new Step
per confirmed item via `vault plan step insert`, and those inserted Steps are
independent and parallelisable. The four error-module renames
(`W04.P08.S19` to `S22`) are mutually independent and may run in parallel,
each its own atomic commit.

## Verification

Mission success criteria, each a verifiable check:

- The cadence rule carries the standing 7th axis and `vaultspec-core` sync
  regenerates provider surfaces with no drift (`spec doctor` clean).
- The delta-audit document exists with verified clusters, each tagged real or
  constraint-shape-divergent under the substitutability pre-filter.
- A single canonical core money primitive exists; `fincas`, inventory, and
  assets import it; its behaviour test passes and no `quantize` cents-rounding
  literal remains in the three former sites (`rg` confirms).
- The diagnostics enrollment enforcement suite passes with zero new
  violations introduced by the delta.
- The exception-restructure ADR is authored and accepted; `DomainError` is
  deleted in its own commit; the four error modules are named `_errors.py`;
  all 23 domain error bases root at `AeatError`.
- `tax_domain` is a closed core `StrEnum` hydrated at the loader boundary
  with a passing roundtrip test; `Subdomain` is renamed with no stale
  references (`rg` confirms).
- Every remediation commit was preceded by a clean
  `uv run --no-sync pytest --collect-only -q`; canonical-site moves are tagged
  `relocation:<symbol>`.
- Each Wave passes a fresh-context campaign-close honesty review before it is
  declared structurally complete.

The plan is complete when every Step in every Wave is closed (`- [x]`) and
every triage Step has either inserted its follow-on Steps or recorded that
none were warranted.
