---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S12'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the curation verbs (set, relate, retire), the audit health report (draft counts, empty short_descriptions, unresolved relations, seed provenance coverage), and scaffold --check as the fast drift gate wired into CI and pre-commit (ADR D3/D8)

## Scope

- `aeat.terminology CLI + CI wiring`

## Description

- Flip the `cli_verbs` enrolment default to False per the coordinator ruling (CLI verbs are a W03 projection, not a scaffolded concept); keep the per-axis toggle for a future revisit.
- Implement the curation operations in `_curation.py` (`set_language_field`, `set_term`, `relate_concepts`, `retire_concept`), each mutating one fragment through the strict schema + serialiser, re-validating the whole tree via the S10 gates, and refusing-on-violation rather than writing an invalid tree.
- Implement the read-only `audit_handbook` returning a structured `AuditReport` (lifecycle counts, empty short_descriptions per language, dangling relations, retired-without-replaced_by, seed-provenance coverage).
- Wire the five CLI verbs (`scaffold` + `--check`, `set`, `relate`, `retire`, `audit`) on `python -m aeat.terminology`, mirroring the `aeat.locales` / `apidocs` dev-CLI style.
- Implement `scaffold --check` as a dry-run over the S11 `scaffold_handbook(apply=False)` plan seam, exit non-zero on drift.
- Write real-behaviour tests for every verb (mutate + idempotent + loader-valid + refuse-invalid), the audit counts, the `--check` drift/clean behaviour, and the ratified 82-concept granularity.
- Run the real-tree `--check` to confirm it is red-until-S13 and document the gate-activation handoff.

## Outcome

Phase W02.P05 is complete: the curation verbs, audit report, and `--check` drift gate are implemented and green. Deliverables:

- **`cli_verbs=False` default (ruling 2).** `collect_enrolment_candidates()` now yields the bounded 82-concept set (31 modelo + 17 IVA + 21 period + 13 topic), zero CLI-verb and zero legal candidates. The `cli_verbs=True` toggle is retained for a future revisit. Pinned by `test_default_enrolment_excludes_cli_verbs_and_is_bounded` (asserts exactly 82) and `test_cli_verbs_toggle_still_available`.
- **Curation operations (`_curation.py`).** `set_language_field` (short_description / definition / scope_note / source), `set_term` (label + term_status, replace-by-label idempotent), `relate_concepts` (add/remove broader/related), `retire_concept` (lifecycle=retired + required replaced_by, never deletes). Every operation loads the tree, mutates one record via `model_copy`, RE-VALIDATES through the full schema and the S10 handbook gates, and writes only on success - an invalid mutation raises `CurationError` and writes nothing.
- **Audit report (`AuditReport`, structured).** `audit_handbook()` returns lifecycle counts (`draft_count`/`approved_count`/`deprecated_count`/`retired_count`), `empty_short_description` (concept_id -> uncurated language codes), `dangling_relations`, `retired_without_replaced_by`, and seed-provenance coverage (`seeded_count`/`hand_authored_count`), plus an `is_clean` property gating only on structural defects (dangling/retired-without-replacement), not backlog signals (drafts/empty descriptions). This is the structured surface the W05.P13 ratchet consumes - counts, not printed text.
- **CLI verbs.** `scaffold` (+ `--check`), `set`, `relate`, `retire`, `audit` registered on `python -m aeat.terminology`; curation verbs surface `CurationError` as a Typer `BadParameter`; `audit` exits non-zero when `not is_clean`.
- **`scaffold --check`.** A dry-run over `scaffold_handbook(apply=False)`: reports the three-outcome counts and exits non-zero unless `plan.is_empty`.
- **Tests (`tests/test_curation.py`, 21 tests).** All green; package suite 65 passed.

Gates: `pytest src/aeat/terminology -q` 65 passed; `pytest --collect-only -q src/aeat/terminology` 65 clean; ruff / format / ty / pyright clean; apidocs `scaffold --check` conformant.

## The three curation verbs + how each stays loader-valid

Every operation funnels through `_commit_concept`, which (1) RE-VALIDATES the mutated record via `ConceptRecord.model_validate(record.model_dump())` so the per-record and per-section schema validators fire (these are bypassed by `model_copy`, which surfaced a real gap during testing - see Notes), wrapping any `ValidationError`/`TerminologyValidationError` as a `CurationError`; (2) assembles a candidate `TerminologyHandbook` with the mutated record swapped in and runs the full S10 `default_handbook_validators()` (id-uniqueness, legal-refs-resolve, relation-integrity, lifecycle/replaced_by, approved-completeness) over it; (3) writes the single fragment via the canonical serialiser ONLY if both pass. A refusal raises `CurationError` with the underlying validator message and writes nothing. Concretely: `set_term` refuses a second `preferred` term (per-section validator); `relate_concepts` refuses a dangling target (relation-integrity gate); `retire_concept` refuses a self-reference (per-record validator) and a retired-successor or cycle (lifecycle gate). Idempotence: re-running any verb with the same arguments produces a byte-identical fragment (proven for set / set_term / relate).

## Audit structured-result shape (for the W05 ratchet)

`AuditReport` (frozen dataclass): `total_concepts: int`, `draft_count`/`approved_count`/`deprecated_count`/`retired_count: int`, `empty_short_description: Mapping[str, tuple[str, ...]]` (concept_id -> sorted uncurated language codes; a section is uncurated when its short_description is blank or carries the `(sin curar)` scaffold placeholder), `dangling_relations: Mapping[str, tuple[str, ...]]`, `retired_without_replaced_by: tuple[str, ...]`, `seeded_count`/`hand_authored_count: int`, and `is_clean: bool` (True iff no dangling relations and no retired-without-replaced_by). The W05.P13 ratchet reads `draft_count` and `len(empty_short_description)` as the non-increasing curation-backlog metrics directly off this object - no text parsing.

## --check design + the S13 gate-activation handoff (green-state coordination)

`scaffold --check` computes `scaffold_handbook(apply=False)` and exits non-zero unless `plan.is_empty`. CONFIRMED via a temp-copy run: against the real committed tree (3 hand-authored exemplars, 0 of the 82 expected scaffold concepts) `--check` reports 82 SCAFFOLD_EMPTY and is therefore RED until S13 materialises the drafts. Per the brief's green-state coordination, NO CI gate is wired in this step. Instead:
- The `--check` VERB ships and is unit-tested on fixtures: `test_check_detects_drift_on_missing_concept` (drift -> non-empty plan) and `test_check_reports_clean_on_synced_fixture` (a materialised fixture -> empty plan).
- A green-TODAY-and-post-bootstrap real-tree gate ships instead: `test_bundled_handbook_audit_is_structurally_clean` asserts the committed tree's `AuditReport.is_clean` (no dangling relations, no retired-without-replaced_by). This is green now (3 clean exemplars) and stays green after S13 (the bootstrap adds drafts, which are backlog signals, not structural defects, so `is_clean` is unaffected).

S13 HANDOFF (recorded explicitly): wire `terminology scaffold --check` into the docs/quality CI + pre-commit gate ONLY AFTER the S13 bootstrap materialises the 82 drafts and makes `--check` green. Until then the gate would be red-until-bootstrap and must not be activated. The verb and its fixture tests are ready; only the CI wiring is deferred.

## cli_verbs=False -> 82 confirmation + regression test

CONFIRMED: `collect_enrolment_candidates()` returns exactly 82 (31 modelo + 17 IVA + 21 period + 13 topic), no CLI-verb domain. Pinned by `test_default_enrolment_excludes_cli_verbs_and_is_bounded` (`len == 82`, no CLI-verb, no legal) and the S11 `test_real_enrolment_candidates_are_concept_grade_and_bounded` still passes under the new default.

## Test names + pass (21 in test_curation.py; 65 package total)

set: `test_set_definition_writes_and_stays_loader_valid`, `test_set_short_description_is_idempotent`, `test_set_source_attaches_citation`, `test_set_unknown_field_is_refused`, `test_set_on_unknown_concept_is_refused`, `test_set_term_replaces_same_label_idempotently`, `test_set_two_preferred_terms_is_refused`. relate: `test_relate_adds_and_removes_edge`, `test_relate_is_idempotent`, `test_relate_dangling_target_is_refused`, `test_relate_unknown_relation_is_refused`. retire: `test_retire_tombstones_with_successor_and_never_deletes`, `test_retire_self_reference_is_refused`, `test_retire_pointing_at_retired_successor_is_refused`. audit: `test_audit_counts_drafts_empty_descriptions_and_seed_coverage`, `test_audit_flags_retired_without_replaced_by_via_loaded_state`, `test_bundled_handbook_audit_is_structurally_clean`. check: `test_check_reports_clean_on_synced_fixture`, `test_check_detects_drift_on_missing_concept`. granularity: `test_default_enrolment_excludes_cli_verbs_and_is_bounded`, `test_cli_verbs_toggle_still_available`. All pass.

## Notes

- One real gap surfaced and fixed during testing: pydantic `model_copy(update=...)` does NOT re-run validators, so a mutation building a two-preferred-term section or a self-`replaced_by` slipped past the handbook-level S10 gates (which do not check per-section/per-record invariants). Fixed by `_revalidate_record` re-running `ConceptRecord.model_validate(record.model_dump())` in `_commit_concept` so every schema validator fires and is reported as a `CurationError`. Two tests pin this (`test_set_two_preferred_terms_is_refused`, `test_retire_self_reference_is_refused`).
- The `set` curation verbs run the S10 `legal_refs_resolve_validator` (default), which loads the registry legal catalogue. This is intentional - a curation write must not break legal-ref resolution - and is acceptable for a dev/maintenance verb.
- NO CI wiring landed (green-state coordination): the `scaffold --check` gate activation is an explicit S13 handoff (above). This is a deliberate scope-narrowing of the plan-step text "wired into CI and pre-commit", justified by the red-until-bootstrap state; the verb and tests are complete.
- Pre-existing peer drift, out of scope, none under terminology: `test_codebase_size_budgets` and `test_docstring_core_struct_links` (`aeat.application.live._justificante`, `aeat.application.modelo._calculation_actions`). apidocs `scaffold` again generated peer `aeat.application.ledger._evidence_input` and `._evidence_textlayer` stubs, left UNCOMMITTED; committed only my `_curation` stub + the toctree line.
- No mocks, skips, xfail, or tautological assertions. Curation tests mutate real fixture trees and assert against the real loader; refusal tests trip the real validators.
