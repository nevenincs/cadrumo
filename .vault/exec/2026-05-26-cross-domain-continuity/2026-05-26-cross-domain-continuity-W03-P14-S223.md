---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S223'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S223 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The R7-B variant of S218 covers tax-residence-ccaa enum binding in M100 verify path and ## Scope

- `fix is the same _decimal_inputs_for_ids type-discrimination from S218`
- `this Step pins regression coverage explicitly for the M100 CCAA case so a future M200-only fix does not regress M100`
- `src/aeat/application/filing/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# R7-B variant of S218 covers tax-residence-ccaa enum binding in M100 verify path

## Scope

- `fix is the same _decimal_inputs_for_ids type-discrimination from S218`
- `this Step pins regression coverage explicitly for the M100 CCAA case so a future M200-only fix does not regress M100`
- `src/aeat/application/filing/__init__.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Run the required code RAG query for `_decimal_inputs_for_ids`, enum bindings, M100 tax-residence CCAA, and the `build_draft` / verify replay path.
- Inspect the plan row, `src/aeat/application/filing/__init__.py`, and `src/aeat/application/filing/tests/test_date_relation_routing.py`.
- Confirm production already routes enum-consumed bindings through `enum_binding_values` and excludes them from `decimal_binding_ids` before `_decimal_inputs_for_ids`.
- Add an M100-specific `build_draft` regression to `src/aeat/application/filing/tests/test_date_relation_routing.py` using a flat verify-replay-style input map with `renta-2024-profile-tax-residence-ccaa = "madrid"`.
- Keep helper-level assertions proving the CCAA binding is discovered as enum-routed, excluded from Decimal extraction, and extracted by `_string_inputs_for_ids`.
- Run focused pytest, ruff, and a read-only code review of the test-only patch.
- Address follow-up review findings by strengthening the test from helper-level coverage to the real `build_draft` path, correcting the closure wording, and removing unrelated feature-index drift.

## Outcome

- Closed with test-only coverage. No production change was needed in `src/aeat/application/filing/__init__.py`.
- The primary regression now calls production `build_draft` with the M100 CCAA enum string in the flat input map. If `build_draft` routes `renta-2024-profile-tax-residence-ccaa` through `_decimal_inputs_for_ids`, the test fails on the attempted Decimal conversion of `"madrid"`.
- The helper assertions remain as diagnostics for the id-set discriminator that feeds the production path.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- Validation: `uvx vaultspec-rag search "_decimal_inputs_for_ids enum binding tax residence ccaa M100 build_draft verify path" --type code --limit 8 --port 8766 --timeout 30` passed and returned the S218 enum-routing regression plus M100 CCAA enum-channel precedents.
- Validation: `uv run --no-sync pytest src/aeat/application/filing/tests/test_date_relation_routing.py -q` passed with 7 tests.
- Validation: `uv run --no-sync ruff check src/aeat/application/filing/tests/test_date_relation_routing.py` passed.
- Review findings resolved. Residual risk is limited to this being a production `build_draft` replay-path test rather than a full CLI `work verify` journey.
