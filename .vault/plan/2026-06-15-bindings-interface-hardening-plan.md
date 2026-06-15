---
tags:
  - '#plan'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
tier: L3
related:
  - '[[2026-06-14-bindings-interface-hardening-adr]]'
  - '[[2026-06-14-bindings-interface-hardening-reference]]'
  - '[[2026-06-14-bindings-interface-hardening-research]]'
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

# `bindings-interface-hardening` plan

Harden the binding definition / validation / boundary / naming altitude: one typed validation contract, fail-closed parity, operator provenance, and semantic disambiguation.

## Wave `W01` - Typed foundations

Establish the typed aggregation/op model and the single canonical binding source-kind taxonomy in core, the two surfaces every later Wave depends on. Backed by the bindings-interface-hardening ADR clusters A and B (decisions on typed aggregation and one source-kind taxonomy). No downstream Wave can begin until these typed primitives exist.

### Phase `W01.P01` - Typed aggregation and op enum

Replace the free-form aggregation mapping and the ~10 ad-hoc op re-parses with a typed BindingAggregation model and a closed BindingAggregationOp enum in core, wired onto DataBindingDefinition with one accessor and one per-family default.

- [x] `W01.P01.S01` - add a BindingAggregationOp StrEnum and a typed BindingAggregation pydantic model in core, then wire the typed aggregation field onto DataBindingDefinition replacing the free-form mapping; `src/aeat/core/aggregation.py, src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S02` - replace the ~10 ad-hoc op re-parses with one typed accessor and one declared per-family default, removing the divergent sum-vs-rows silent defaults; `src/aeat/domain/calculations/registry/_bindings.py, src/aeat/domain/calculations/registry/_detail_record_bindings.py, src/aeat/domain/calculations/registry/_bindings_previous_filing.py`.
- [x] `W01.P01.S03` - add typed-aggregation roundtrip and per-family default tests that fail if the typed op is dropped or a wrong family default is applied; `src/aeat/domain/calculations/registry/tests/test_binding_aggregation.py`.

### Phase `W01.P02` - Unified source-kind taxonomy

Consolidate the binding source kinds onto a single canonical core enum, derive the per-family frozensets from it, realign the enum-vs-string mismatches, complete the incomplete ledger source set, and wire-or-delete the dead typed_enum field.

- [x] `W01.P02.S04` - introduce one canonical binding source-kind enum in core reconciling AggregationSourceKind and RowSetGroupingKind, realigning the related_party, atribucion and refund tokens to match enum values; `src/aeat/core/aggregation.py`.
- [x] `W01.P02.S05` - derive every per-family source-kind frozenset from the canonical enum, fix the incomplete LEDGER_BINDING_SOURCE_KINDS, and reconcile every consumer into one accept-or-reject state per the retired-enum rule; `src/aeat/domain/calculations/registry/_ledger_bindings.py, src/aeat/domain/calculations/registry/_invoice_bindings.py, src/aeat/core/aggregation.py`.
- [x] `W01.P02.S06` - wire the dead typed_enum schema field to a real consumer or delete it outright per no-legacy-compatibility, with the deletion test asserting no module reads it; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P02.S07` - add a taxonomy parity gate asserting the canonical source-kind enum equals the registry binding source set; `src/aeat/domain/calculations/registry/tests/test_binding_source_taxonomy.py`.

## Wave `W02` - One validation contract

Collapse the three incompatible validator conventions onto a single per-family validate(binding)->list[str] signature registered in one dispatch table and run at registry-build for every family. Backed by ADR cluster A. Depends on W01 (the typed op enum underpins the unified validator); W03 fail-closed parity depends on this Wave's build gate.

### Phase `W02.P03` - Single validator signature

Define one validate(binding)->list[str] per source family in a single dispatch table, lift the detail-record and previous_filing op/fact invariants to build time via selector_as_dict, and collapse the near-verbatim invoice/counterpart duplication.

- [x] `W02.P03.S08` - define one validate(binding)->list[str] validator per source family registered in the single binding dispatch table alongside the selector model; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `W02.P03.S09` - lift the four detail-record family and previous_filing op/fact invariants to registry-build, routing each through selector_as_dict and preserving the underlying pydantic field error in the diagnostic; `src/aeat/domain/calculations/registry/_detail_record_bindings.py, src/aeat/domain/calculations/registry/_bindings_previous_filing.py, src/aeat/domain/calculations/registry/_binding_selector_utils.py`.
- [x] `W02.P03.S10` - collapse the near-verbatim invoice and counterpart resolver and validator duplication to one shared implementation parameterised by source kind; `src/aeat/domain/calculations/registry/_counterpart_bindings.py, src/aeat/domain/calculations/registry/_invoice_bindings.py`.

### Phase `W02.P04` - Build gate

Run every family validator in the registry-build section validator so a malformed binding is rejected at snapshot build for all families, and fix any latent malformed registry TOML the new gate surfaces.

- [x] `W02.P04.S11` - run every family validator from the single dispatch table inside the registry-build section validator so all families are checked at snapshot build; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `W02.P04.S12` - add build-time rejection tests per family plus an anti-tautology proof asserting a malformed binding fails at build for each family, not only at resolve; `src/aeat/domain/calculations/registry/tests/test_binding_build_validation.py`.
- [x] `W02.P04.S13` - fix any latent malformed registry TOML the new build gate surfaces so the full registry suite collects and builds clean; `src/aeat/_data/registry/aeat/modelos/`.

## Wave `W03` - Fail-closed parity

Generalise the IVA-only unsupported-observation screen into a per-family unrouted-observation diagnostic and unify the triplicated revision-carry gate, so no resolver silently returns Decimal(0). Backed by ADR cluster C and the no-silent-under-declaration rule. Depends on W01 source-kind taxonomy and W02 validation contract.

### Phase `W03.P05` - No-silent-zero

Generalise the IVA unsupported-observation screen into a per-family unrouted-observation screen wired on the calculate path, so every aggregation resolver surfaces an advisory instead of a silent Decimal(0).

- [x] `W03.P05.S14` - generalise the IVA unsupported-observation screen into a per-family unrouted-observation screen that flags an unrouted declarable observation for every aggregation family; `src/aeat/domain/calculations/registry/_ledger_bindings.py, src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W03.P05.S15` - wire the per-family unrouted-observation advisory diagnostics on the live calculate path so a resolver surfaces an advisory instead of a silent Decimal(0); `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `W03.P05.S16` - add silent-zero refusal tests per family asserting a positive unrouted observation raises an advisory rather than resolving to zero; `src/aeat/application/modelo/tests/test_unrouted_observation_screen.py`.

### Phase `W03.P06` - Carry-gate unification

Unify the three ADR-R2 revision-carry gate copies onto one path and emit a diagnostic for an unresolved non-formula relation that today produces neither value nor warning.

- [x] `W03.P06.S17` - unify the three ADR-R2 revision-carry gate copies onto one shared path consumed by the binding-prefill, cross-period clean-state, and relation-prefill callers; `src/aeat/application/calculations/_binding_prefill.py, src/aeat/application/calculations/_cross_period_clean_state.py, src/aeat/application/calculations/_relation_prefill.py`.
- [x] `W03.P06.S18` - emit a diagnostic for an unresolved non-formula relation that today produces neither value nor warning at calculate time; `src/aeat/application/calculations/_relation_prefill.py`.
- [x] `W03.P06.S19` - add carry-gate parity and relation-diagnostic tests asserting one gate path and a surfaced diagnostic for an unresolved non-formula relation; `src/aeat/application/calculations/tests/test_carry_gate_parity.py`.

## Wave `W04` - Operator-boundary provenance and CLI

Carry legal_refs/source_refs and a typed source kind onto the encrypted ModeloBindingValue carrier and the CLI payloads, at provenance parity with casillas. Backed by ADR cluster D and the aeat-calculation-grounding rule. Coordinates with the in-flight storage-backend-security-review campaign on the encrypted boundary; depends on W01 typed source kind.

### Phase `W04.P07` - Carrier provenance

Add legal_refs/source_refs and a typed source kind to the encrypted ModeloBindingValue carrier and populate them from the binding definition in the filing builder, dropping the hardcoded free-text source string, with strict roundtrip and anti-tautology proof. Coordinate with the storage-backend-security-review campaign: re-read HEAD and git diff before each edit.

- [x] `W04.P07.S20` - add legal_refs, source_refs and a typed source kind to ModeloBindingValue at parity with the casilla provenance model, re-reading HEAD and git diff before editing the encrypted boundary; `src/aeat/domain/filing/_schema.py`.
- [x] `W04.P07.S21` - populate the binding-value provenance from the binding definition in the filing builder and drop the hardcoded source=registry binding input free-text string; `src/aeat/application/filing/__init__.py`.
- [x] `W04.P07.S22` - add a strict save-load-equality roundtrip and an anti-tautology proof that corrupts the persisted provenance and asserts refusal on the encrypted filing-draft boundary; `src/aeat/domain/filing/tests/test_binding_value_provenance_roundtrip.py`.

### Phase `W04.P08` - CLI surface

Expose binding provenance on the typed CLI payloads, convert bindings list off the dict bag, make --modelo a registry-derived Choice with an accepted-codes refusal, and replace the --binding numeric-vs-enum try/except heuristic with registry-data-type-driven coercion.

- [x] `W04.P08.S23` - expose the binding provenance on BindingRowPayload and BindingPreviewRowPayload and convert bindings list from the list[dict[str,object]] bag to the typed payload; `src/aeat/entrypoints/cli/_modelo_payloads.py, src/aeat/entrypoints/cli/_modelo_discovery_cli.py`.
- [x] `W04.P08.S24` - make bindings list --modelo a registry-derived click.Choice that refuses an unknown code with the accepted-codes set in the error message; `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`.
- [x] `W04.P08.S25` - replace the --binding numeric-vs-enum try-Decimal-except heuristic with a registry-data-type-driven coercion that rejects a malformed amount instead of reclassifying it as an enum; `src/aeat/application/modelo/_calculate_input.py, src/aeat/entrypoints/cli/_modelo_cli_support.py`.
- [x] `W04.P08.S26` - add documented-command and json-schema conformance tests covering the typed bindings list payload and the --modelo Choice refusal; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py, src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`.

## Wave `W05` - Semantic disambiguation

Reserve the word binding for the registry-data-input concept by renaming the homonym modules and giving the three source-resolver result types one role-named contract. Backed by ADR cluster E. Each rename is an atomic explicit-path relocation commit; independent of W01-W04 substance but sequenced after them to avoid churning files under active edit.

### Phase `W05.P09` - Renames

Rename the homonym surfaces that overload the word binding, each as an atomic explicit-path relocation commit with docs-scaffold regeneration to avoid orphan stubs.

- [x] `W05.P09.S27` - rename the Google OAuth _profile_binding.py to an active-profile resolver name in one atomic explicit-path relocation commit and run python -m dev.docs.apidocs scaffold; `src/aeat/adapters/outbound/google/_profile_binding.py`.
- [x] `W05.P09.S28` - reclassify decimal_from_string out of the _decimal_binding_value binding-value filename in one atomic explicit-path relocation commit and run python -m dev.docs.apidocs scaffold; `src/aeat/application/modelo/_decimal_binding_value.py`.
- [x] `W05.P09.S29` - rename the legal_basis_binding rate-to-BOE verification test concept off the binding word in one atomic explicit-path relocation commit and run python -m dev.docs.apidocs scaffold; `src/aeat/domain/iva/tests/test_legal_basis_binding.py`.

### Phase `W05.P10` - Result-type role

Give the three source-resolver result types one role-named contract or a documented shared role, so naming-by-role replaces naming-by-source.

- [x] `W05.P10.S30` - give the three source-resolver result types one role-named shared contract or a documented shared role, replacing naming-by-source with naming-by-role; `src/aeat/application/modelo/_profile_binding.py, src/aeat/application/modelo/_borrador_binding.py, src/aeat/application/modelo/_binding_resolution.py`.

## Wave `W06` - Codification

Promote the two never-promoted structural audit candidates, author the five new bindings-interface rules from the ADR codification candidates, and run the fresh-context close audit. Backed by ADR cluster F and the vaultspec-codify and campaign-close-honesty rules. Depends on every prior Wave landing so the rules describe shipped contracts.

### Phase `W06.P11` - Promote and author rules

Promote the two never-promoted structural audit candidates and author the five new bindings-interface rules from the ADR codification candidates, then propagate with vaultspec-core sync.

- [x] `W06.P11.S31` - promote the never-promoted registry-resolver-family-extraction and registry-formula-runtime-facade candidates to rules with vaultspec-core vault rule promote from their 2026-06-02 boundary audits; `.vaultspec/rules/rules/registry-resolver-family-extraction.md, .vaultspec/rules/rules/registry-formula-runtime-facade.md`.
- [x] `W06.P11.S32` - author the five new bindings-interface rules from the ADR codification candidates and propagate them with vaultspec-core sync; `.vaultspec/rules/rules/binding-validation-single-contract.md, .vaultspec/rules/rules/binding-aggregation-is-typed.md, .vaultspec/rules/rules/binding-source-kind-single-taxonomy.md, .vaultspec/rules/rules/binding-values-carry-provenance.md, .vaultspec/rules/rules/binding-names-reserved-for-registry-input.md`.

### Phase `W06.P12` - Close audit

Run a fresh-context honesty review and close audit per the campaign-close-honesty rule, with full-tree owner triage distinguishing feature-surface failures from peer churn.

- [x] `W06.P12.S33` - run a fresh-context honesty review and close audit per the campaign-close-honesty rule with full-tree owner triage, tracking every surfaced item as a new Step with a verification gate; `.vault/audit/2026-06-15-bindings-interface-hardening-close-audit.md`.

## Description

This plan hardens the binding definition / validation / boundary / naming altitude of the calculation-source interface. Per the `bindings-interface-hardening` ADR, the resolver-mesh altitude (the `ModeloSourceResolver` port, `CalculationSourceMesh`, enrollment and novel-source gates, pull-equals-calculate parity) is settled across the calculation-source-connectivity and aggregation-taxonomy ADRs and is explicitly out of scope; this plan touches only the uncodified drift the research anchored to clusters A through F.

The work is sequenced by risk into six Waves. W01 lays the typed foundations the ADR's decisions 2 require: a typed `BindingAggregation` model with a closed `BindingAggregationOp` enum in `core/aggregation.py`, replacing the free-form mapping and the ~10 ad-hoc `op` re-parses with their divergent sum-vs-rows defaults; and one canonical binding source-kind enum, with per-family frozensets derived from it, reconciling the `AggregationSourceKind` / `RowSetGroupingKind` half-adoption, completing the incomplete `LEDGER_BINDING_SOURCE_KINDS`, and resolving the dead `typed_enum` field. W02 collapses the three incompatible validator conventions onto one `validate(binding) -> list[str]` per family in a single dispatch table run at registry-build for every family, lifting the detail-record and `previous_filing` op/fact invariants to build time via `selector_as_dict`. W03 closes the off-IVA silent-zero hole by generalising the `unsupported_ledger_iva_observations` screen into a per-family unrouted-observation diagnostic on the calculate path, and unifies the three copies of the ADR-R2 revision-carry gate. W04 carries `legal_refs` / `source_refs` and a typed source kind onto the encrypted `ModeloBindingValue` carrier and the CLI payloads at parity with `ModeloCasillaProvenance`, dropping the hardcoded `source="registry binding input"` string, and hardens the CLI surface. W05 reserves the word binding for the registry-data-input concept through atomic explicit-path renames. W06 promotes the two never-promoted structural audit candidates, authors the five new ADR codification candidates as rules, and runs the close audit.

The concrete current-state code anchors each Step edits are recorded in the `bindings-interface-hardening` reference document. Line numbers there are HEAD-at-discovery and MUST be re-confirmed immediately before each edit, because the shared `chore/eliminate-shims` factory branch lands peer commits continuously.

## Parallelization

Waves are sequenced and each must land before the next begins, because the clusters are interdependent: the typed `op` enum (W01.P01) underpins the unified validator (W02.P03), and the source-kind taxonomy (W01.P02) underpins both the build gate (W02.P04) and fail-closed parity (W03.P05). Within a Wave, Phases that share no hard interdependency may be parallelised. In W01, P01 (typed aggregation) and P02 (source-kind taxonomy) touch the same `core/aggregation.py` and `_schema.py` surfaces and so are sequenced P01 then P02 to avoid a write race. In W02, P03 (validator signature) must complete before P04 (build gate runs those validators). In W03, P05 (no-silent-zero) and P06 (carry-gate unification) touch disjoint modules and may run in parallel. In W04, P07 (carrier) must precede P08 (CLI), because the CLI payloads surface the carrier's new provenance fields; the encrypted-carrier Steps S20 to S22 are serialised among themselves and demand a HEAD re-read and `git diff` before each edit to coordinate with the concurrent storage-backend-security-review campaign. In W05, the three renames in P09 are independent atomic commits and may be dispatched in parallel, but each is its own relocation commit; P10 is independent. In W06, P11 must complete before P12, because the close audit reviews the authored rules. Recommended executor assignment: `vaultspec-high-executor` for the core-logic Steps (S01, S04, S05, S08, S09, S14, S17, S20, S21, S25); `vaultspec-standard-executor` for the typical CLI and builder Steps (S02, S06, S10, S11, S15, S18, S23, S24, S30); `vaultspec-low-executor` for the well-defined test, rename, and rule-authoring Steps (S03, S07, S12, S13, S16, S19, S22, S26, S27, S28, S29, S31, S32); `vaultspec-code-reviewer` drives the close audit (S33).

## Verification

The plan is complete when every Step is closed (`- [x]`) with a matching execution record per the plan-closure-requires-exec-records rule, and the close audit (S33) reports a fresh-context honest pass with full-tree owner triage.

Per-Wave success criteria, each a real gate:

- W01: `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_binding_aggregation.py src/aeat/domain/calculations/registry/tests/test_binding_source_taxonomy.py` passes; the taxonomy parity gate asserts the canonical enum equals the registry binding source set; no module reads a `typed_enum` field.
- W02: `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_binding_build_validation.py` passes, including the per-family anti-tautology proof that a malformed binding fails at build, not only at resolve; `uv run --no-sync pytest --collect-only -q src/aeat` collects clean after the latent-TOML fixes.
- W03: `uv run --no-sync pytest src/aeat/application/modelo/tests/test_unrouted_observation_screen.py src/aeat/application/calculations/tests/test_carry_gate_parity.py` passes; `test_pull_path_calculate_path_casilla_parity.py` stays green.
- W04: `uv run --no-sync pytest src/aeat/domain/filing/tests/test_binding_value_provenance_roundtrip.py` passes with strict save-load-equality and the anti-tautology corruption proof; `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` passes for the typed `bindings list` payload and the `--modelo` Choice refusal.
- W05: each rename lands as one atomic explicit-path relocation commit tagged `relocation:<symbol>`; `python -m dev.docs.apidocs scaffold --check` exits clean (no orphan stubs); `uv run --no-sync pytest --collect-only -q src/aeat` collects clean.
- W06: `uv run --no-sync vaultspec-core spec rules list` shows the two promoted and five authored rules; `uv run --no-sync vaultspec-core sync` reports success; `uv run --no-sync vaultspec-core vault check all` and `uv run --no-sync vaultspec-core vault check features --feature bindings-interface-hardening` pass.

For the campaign-wide cadence (swarm audit triggers, full-tree owner triage on the shared branch), see the authorizing ADR linked in the `related:` frontmatter.
