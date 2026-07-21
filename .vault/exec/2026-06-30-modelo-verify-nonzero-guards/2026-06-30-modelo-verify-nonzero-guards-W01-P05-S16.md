---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S16'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M210 rendimientos-integros-to-base-imponible advisory alongside the existing representante-fiscal predicate on the loaded 2025 revision snapshot

## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_210_registry.py`

## Description

- Added `test_modelo_210_2025_verification_predicates_guard_representante_fiscal_and_base_imponible` to `test_modelo_210_registry.py`, loading the committed M210 modelo via the existing `_load_modelo_210` / `_committed_modelo` helper (no fixture duplication).
- Asserted both predicates by `predicate_id` on the loaded 2025 revision: the representante-fiscal predicate keeps its exact `expression`, `finding_kind == "BLOCKING_RULE"`, and `trlirnr-rdleg-5-2004:art-10` legal ref; the new guard asserts `expression == 'implies_nonzero(["rendimientos_integros", "base_imponible"])'`, `finding_kind == "ADVISORY"`, and `trlirnr-rdleg-5-2004:art-24` in its legal refs.
- Asserted both casilla ids referenced by the new predicate (`rendimientos_integros`, `base_imponible`) exist on the revision's casilla set.
- Cross-checked the `trlirnr-rdleg-5-2004:art-24` legal reference against the bundled BOE corpus by calling the real registry-build validator `verify_legal_catalogue` (the same function `_validate_surfaces.py` runs at registry-build time), then independently confirmed every `required_text` phrase is present in the bundled `trlirnr-rdleg-5-2004.html` corpus file. Avoided the file's `_trlirnr_corpus_paragraph` per-`<p id=...>` helper for this anchor because art. 24's anchor sits on the `<h1>` heading (`<h1 id="a24">`), not a per-paragraph tag like the 25.1.* sub-letter anchors the helper was built for.
- Ran `ruff format` on the file; the formatter additionally reflowed one unrelated pre-existing line in `test_modelo_210_interest_rate_is_grounded_in_unconditional_art_25_1_f`. Manually reverted that unrelated reflow by hand so the diff stays scoped to the new test, per the swarm-orchestration discipline against touching unrelated peer-owned code.
- Ran `ruff check` (clean) and the full file's targeted pytest run (18 passed) plus the M210-wide `-k "modelo_210 or m210"` sweep (48 passed) and the full `domain/calculations/registry/tests` suite (3627 passed, 2 pre-existing failures in unrelated M100 tests confirmed clean against this Step's `git status --short` -- not introduced by this change).

## Outcome

The registry-shape test asserts both M210 verification predicates' shape (id, expression, finding_kind, legal_refs) directly off the loaded authority snapshot, and cross-checks the new guard's legal grounding against the real bundled BOE corpus via the production validator rather than a hand-authored excerpt.

## Notes

Two pre-existing, unrelated failures surfaced in the full registry suite run (`test_catalogue_verification_normatives.py::test_modelo_100_withholding_imports_use_formal_withholding_article` and `test_modelo_100_registry_constructs.py::test_modelo_100_renta_section_constructs_classify_registered_relation_sources`). Confirmed via `git status --short` that neither the failing test files nor the M100 registry tree carry any uncommitted change from this Step; these are peer-campaign-owned failures on HEAD, out of scope per full-tree-gate-must-distinguish-owner, and not actioned here.
