---
tags:
  - '#plan'
  - '#suite-redgreen-2026-06-02'
date: '2026-06-02'
tier: L2
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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace suite-redgreen-2026-06-02 with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `suite-redgreen-2026-06-02` `Suite red-green burndown 2026-06-02` plan

### Phase `P01` - CLI work-calculate envelope cluster

Resolve the 14-test work-calculate empty-envelope cluster (peer signature drift around casilla_inputs)


<!-- One-line headline summary plan. -->

- [x] `P01.S01` - Diagnose work-calculate empty-envelope; `Reproduce on test_modelo_discovery_defects[1P]; identify where _emit_envelope is silenced; document the precise call path in a comment`.
- [x] `P01.S02` - Restore envelope emission for work-calculate; `Production fix in CLI handler + service so success/refusal always emits the SchemaEnvelope; cite the 14 failing test ids`.
- [x] `P01.S03` - Verify 14-test cluster passes; `Run all 14 listed CLI tests isolated; commit when green`.

### Phase `P02` - IVA wallet decision routing

Fix the prior-filing-history and prior-year-history wallet decision injection so casilla 87 (compensacion aplicada) gets the persisted 1200/450 from the wallet decision (currently returns 0)

- [x] `P02.S04` - Trace iva_compensation_decision binding into engine inputs; `From calculate_modelo_revision through _apply_iva_compensation_decision_binding into resolved_bindings; instrument with _log.debug at each hand-off`.
- [x] `P02.S05` - Fix prior-filing-history routing; `Wire the wallet decision's applied_periodo through modelo-303-compensacion-aplicada-periodo binding so casilla 87 receives 1000 not 0`.
- [x] `P02.S06` - Verify both IVA wallet integration tests pass; `test_wallet_capture_decision_feeds_real_modelo_303_engine_from_{prior_filing_history,prior_year_history}`.

### Phase `P03` - Storage encrypted persistence policy

Restore encryption-at-rest for filing history + attachments manifest so plaintext does not appear in SQLite bytes

- [x] `P03.S07` - Audit attachment manifest field encryption; `Restore EncryptedString or equivalent on Justificante.source_pdf_sha256 et al so the hex digest does not appear in raw SQLite bytes`.
- [x] `P03.S08` - Restore filing_history TestClassificationGate encryption; `test_database_payload_is_encrypted_audit_data — re-enable column-level encryption for AUDIT classification rows`.
- [x] `P03.S09` - Verify storage encryption suite; `test_blob_and_manifest_round_trip_without_plaintext_files + test_database_payload_is_encrypted_audit_data`.

### Phase `P04` - Registry parity + coverage

Catalogue-verification, formula-modelo parity, modelo-parity coverage, ledger-iva 390 binding chain

- [x] `P04.S10` - Catalogue verification; `test_committed_registry_tree_has_required_model_law_coverage — identify missing model/law pair; either supply or relax with rationale`.
- [x] `P04.S11` - Formula-modelo parity; `test_formula_revisions_are_owned_by_constructs_with_snapshot_workflow_surfaces — wire missing formula→construct ownership`.
- [x] `P04.S12` - Modelo parity coverage; `test_formula_bearing_modelos_have_constructs_and_model_specific_tests — list bare formula-bearing modelos`.
- [x] `P04.S13` - M390 IVA binding chain; `Supply missing modelo-303-autoconsumo-promotor-base binding for the 390 annual pipeline test`.
- [x] `P04.S28` - Fix M714 empty formula fragment load blocker; `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/formulas/0001-formulas.toml`.

### Phase `P05` - Structural ratchets

Identity-primitive sibling-domain enum cycle, exception base hygiene, monkeypatch + cross-module imports + relative-imports drift

- [x] `P05.S14` - IvaRate sibling-domain cycle; `Relocate IvaRate out of invoices._enums into a leaf module (core or domain/iva) so iva._invoice_classification can import from public surface without cycle`.
- [x] `P05.S15` - Exception base hygiene; `test_production_exception_classes_do_not_introduce_unregistered_builtin_roots — register or remove unregistered root`.
- [x] `P05.S16` - Monkeypatch + cross-module + relative-imports inventories; `Bring the three inventory ratchets back to zero (likely peer additions need rationale comments or removal)`.

### Phase `P06` - CLI surface contract

cli_workflow_verification retired-surface suggestions, operator_surface help_documents, backend_boundary, lazy_command_tree state-free general

- [x] `P06.S17` - Retired-surface canonical suggestions; `test_root_contract_service_rejects_retired_surfaces_with_canonical_suggestions — supply the suggestion map peer drift removed`.
- [x] `P06.S18` - Help documents backend-owned; `test_help_documents_are_backend_owned_and_current_surface_only — re-source help text from backend, remove stale entries`.
- [x] `P06.S19` - Backend boundary test xfail language; `test_cli_unit_tests_do_not_contain_process_state_or_xfail_language — find and remove the forbidden language`.
- [x] `P06.S20` - Lazy-command-tree state-free general; `test_state_free_surface_does_not_import_registry (non-help parametrize) — chase the registry leak path that --help-fix did not cover`.

### Phase `P07` - Setup + custody + Google

config_custody profile lifecycle, profile-create taxpayer-type paths, google sheets pull/export, fichero BOE golden sha

- [x] `P07.S21` - Config custody profile lifecycle; `test_profile_create_provisions_file_custody_and_switch_reopens_it — investigate why switch does not reopen`.
- [x] `P07.S22` - Legal-entity profile create; `test_legal_entity_profile_creates_non_interactively_without_spouse_flags`.
- [x] `P07.S23` - Google worksheet export-pull roundtrip; `test_workbook_input_values_survive_export_pull_compute_loop`.
- [x] `P07.S24` - Pull adapter classify_metadata empty pairs; `test_classify_metadata_returns_missing_for_empty_pairs (post sentinel + M347 fix; verify suite-level cleared)`.
- [ ] `P07.S25` - Fichero BOE golden sha; `test_modelo_303_golden_sha_fichero_boe — recompute golden sha if peer registry change altered output`.

### Phase `P08` - Filing + date routing

test_date_relation_routing non-iso rejection, test_binding_prefill modelo 390 prefill

- [x] `P08.S26` - Date relation routing non-iso reject; `test_date_inputs_for_ids_rejects_non_iso_value — re-derive non-iso rejection path post _parse_iso8601_date routing`.
- [x] `P08.S27` - Modelo 390 prefill binding-prefill; `test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations`.

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. -->

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorising documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter. -->
