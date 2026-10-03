---
tags:
  - '#plan'
  - '#registry-health-repair'
date: '2026-10-02'
tier: L1
related:
  - '[[2026-08-10-aeat-export-fragment-generator-authority-adr]]'
  - '[[2026-09-09-registry-edition-authoring-adr]]'
  - '[[2026-09-09-registry-generator-adr]]'
  - '[[2026-09-11-binding-schema-adr]]'
  - '[[2026-09-17-modelo-locale-delta-keying-adr]]'
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
modified: '2026-10-02'
body_schema: body-v2
body_hash: 'sha256:353fef9339724381e1fe8a1d41f15c7b55b8f0cf0f84d804a4cfd8f8c3061f28'
---

# `registry-health-repair` plan

## Description

Approved 2026-10-02

The operator requested all remaining registry repairs and explicitly invoked aeat-authority-registry-authoring. They authorized GPT-6 Luna with maximum reasoning for the batch fleet, assigned this session Modelo 360 exports and form layouts, and approved the publisher supersession and indexed form parity tool fixes. The existing binding-consumer-closure session retains the 179 unused bindings and final authority publication; its source and consumer edits are outside this fleet. The 33 check-bindings findings assigned to tui-bb remain excluded.

The initial target inventory has 119 excluded entries. It is a worklist for evidence and authorship, not authority to invent export layouts or fixed-width sources for native XML or applicability-only revisions. Preserve the 2022 supported filing floor, typed capability grades, historical storage baselines still inherited by supported editions, source provenance, and reviewed form authority. Newly discovered unsupported behavior must be scoped before implementation. Git operations must preserve unrelated worktree and index changes.

Decision coverage: the accepted registry-edition-authoring ADR governs S01 and installed baseline/delta semantics; the accepted export-fragment-generator-authority ADR governs S02, S03 and S06-S09, including hard cutover, official wire facts and source-pinned generation; registry-generator governs canonical candidate, component and publication boundaries in S05 and S10; the accepted localization cascade and delta-keying ADRs govern S04; binding-schema governs the S10 ownership interface. Existing decisions cover the repairs currently executing. The audit and row-level receipts record findings and proof without replacing these decisions.

## Steps

- [x] `S01` - Compress the redundant Modelo 303 predicate payload with the canonical converter and prove installed equivalence, minimality and idempotence; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [x] `S02` - Repair governed literal fact JSON round trips and provenance projection, retaining mismatch refusal and canonical absence; `src/cadrumo/domain/calculations/registry/schema_exports.py, dev/registry/pipeline/export_fragment_provenance.py, dev/registry/compiler/tests/test_export_literal_fact.py, dev/registry/tests/test_provenance_manifest.py`.
- [x] `S03` - Preserve all seven Modelo 360 official signed numeric slots through reviewed profiles and the real fixed-width codec; `dev/registry/pipeline/render_profile.py, dev/registry/pipeline/_export_tree.py, dev/registry/render_profiles/modelo_360/2010/, dev/registry/pipeline/tests/test_signed_singleton_render_profile.py`.
- [x] `S04` - Review all 300 initial modelo label signals, apply supported scalar corrections through the locale owner and retain row-level evidence; `src/cadrumo/locales/{es,en,ca}/modelo/schema/{145,216,360,369}.yml, .logs/audit-runs/2026-10-02/registry-health-repair/label-review.json`.
- [x] `S05` - Compare complete indexed revisions and snapshots including separately stored form layouts and detect missing or changed components; `dev/registry/registry_collapse_verification.py, dev/registry/tests/test_registry_collapse_verification.py`.
- [x] `S06` - Make source-pinned manual layout supersession atomic with construct and generated form companions, guarded whole-revision receipts and recoverable rollback or committed cleanup; `dev/registry/pipeline/candidate_staging.py, dev/registry/pipeline/cli.py, dev/registry/pipeline/_tree_publication.py, dev/registry/pipeline/tests/`.
- [ ] `S07` - Author and publish the grounded initial export batch for modelos 111, 115, 117, 122, 123 and 360 with generated form companions and retired bootstrap declarations; `dev/registry/mappings/modelo_{111,115,117,122,123}/, dev/registry/render_profiles/modelo_{111,115,117,122,123}/, dev/registry/pipeline/generated_export_bootstrap_targets.toml, src/cadrumo/_data/registry/aeat/modelos/{111,115,117,122,123,360}/revisions/*/{export,export_layouts,constructs,form_layouts}/`.
- [ ] `S08` - Ground the remaining missing semantic maps and render profiles for the target inventory, preserving capability and supported filing bounds, and publish each supported named target; `dev/registry/mappings/modelo_{130,131,145,156,165,180,181,189,190,193,216,270,280,309,322,341,345,349,369,490,576,604,714,720}/, corresponding render_profiles directories, corresponding generated export and form companions`.
- [ ] `S09` - Adjudicate native XML coverage, absent export layouts and ambiguous 126 or 128 source frames against typed capability and official evidence, recording actual missing or superfluous fields without invented layouts or sources; `dev/registry/analysis/generated_tree_state.py read boundary, src/cadrumo/_data/registry/aeat/modelos/{036,038,100,126,128,136,165,182,184,185,187,188,194,200,216,220,280,296,308,345,390,576,721,763,840}/, .vault/audit/2026-10-02-registry-health-repair-registry-health-audit.md`.
- [ ] `S10` - Coordinate the retained binding owner, complete stable full-inventory verification and deliver the scoped review with final authority publication and currency verified from that owner's generation; `.vault/plan/2026-10-02-binding-consumer-closure-plan.md ownership boundary, dev/registry/registry_collapse_verification.py, dev/registry/pipeline/authority_publication.py read boundary, .authority/ owner boundary, .vault/audit/2026-10-02-registry-health-repair-registry-health-audit.md`.
- [x] `S11` - Resolve the exact Modelo 122 referenced declaration-type constant through a source-pinned note reading while refusing alternatives, conditions, stale sources and geometry conflicts; `dev/registry/pipeline/note_literals.py, dev/registry/pipeline/_export_tree.py, dev/registry/pipeline/export_fragment_provenance.py, dev/registry/pipeline/tests/test_note_literal_derivation.py`.
- [x] `S12` - Normalize case spelling of declared variable workbook markers and prove real Modelo 216 composition plus malformed marker refusals.; `dev/registry/compiler/record_design_workbook.py and dev/registry/tests/test_record_design.py`.
- [x] `S13` - Enforce Modelo 216's source-pinned lower year bound in generated exports; `src/cadrumo/domain/calculations/registry/schema_exports.py and fixed_width_codec.py with separately owned fixed_width_parser.py handoff and dev/registry/pipeline/year_constraints.py and render_profile_eligibility.py and _export_tree.py and export_fragment_provenance.py and tests/test_source_bounded_year.py and modelo_216 source inputs`.
- [x] `S14` - Preserve complete validated semantic-role context when checking an isolated generated revision; `Publisher validation repair in dev/registry/pipeline/_tree_validation.py and cli.py and tests/test_generated_tree_scope_context.py with source witness target replacement and typo and metadata refusal proofs`.

## Parallelization

S01-S05 and S06 have separate primary file ownership and may proceed independently; dependent acceptance waits for the changed serializer and schema contracts to settle. Within S07 and S08, semantic map and render-profile authors own disjoint modelo directories. Root owns the bootstrap ledger and serializes named target publications after S06; the publisher worker temporarily owns its tightly coupled generated form installation. Source modelos shared with the binding session require the operator's assigned boundary and a fresh source receipt. The binding session alone performs its final authority publication. Whole-inventory verification runs only after the local batch stops mutating interpreting code and source.

## Verification

Prove canonical source installation and hydrated equivalence separately from field-level minimality and converter idempotence. Enumerate all live modelos through canonical discovery, with no hardcoded corpus count. Run the real parser, semantic joiner, reviewed numeric policy validator and codec for changed wire semantics; show malformed and ambiguous inputs refuse.

Named export acceptance requires a source-pinned canonical candidate check, transactional publication, a fresh target-current proof, and the generated form companion's currentness. Publisher tests cover zero construct references, exact retirement, unrelated authority refusal or retention, source changes outside the export directory, rollback refusal on changed live candidates, interrupted recovery and committed cleanup failure. Indexed parity tests compare separately stored form layouts and detect genuine changed or absent forms.

Review every initial suspicious locale row, apply corrections through dev.locales, preserve legal references and placeholders, and retain correction or retention reasons. The remaining spelling signal count is reported honestly.

Run focused tests, Ruff/format/type checks on owned changed surfaces, the data-format owner on actual changed TOML files, vault plan/check gates, and one integrated review of the final batch. Re-run whole check-registry and the collapse verifier with stable receipts after the batch. Report source, named targets, authority and runtime boundaries independently; final authority currency is accepted only against the generation published by the retained binding owner. No binding disposition, capability downgrade, support-floor change or fake design source may silence an unresolved finding.
