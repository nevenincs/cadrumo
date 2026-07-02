---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S231'
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
     The S231 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The R7-INES-5 disambiguate the CLI input-validation refusal message from the stored-data validation refusal message and ## Scope

- `a malformed --retencion-observation JSON currently emits the same Catalan-Spanish-text and recommends aeat config repair which is wrong`
- `need a distinct argument-validation message pointing to the expected pydantic field shape`
- `src/aeat/entrypoints/cli/_errors.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# R7-INES-5 disambiguate the CLI input-validation refusal message from the stored-data validation refusal message

## Scope

- `a malformed --retencion-observation JSON currently emits the same Catalan-Spanish-text and recommends aeat config repair which is wrong`
- `need a distinct argument-validation message pointing to the expected pydantic field shape`
- `src/aeat/entrypoints/cli/_errors.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Ground the testimonial with `vaultspec-rag` against the Modelo aggregate observation parser and CLI error-boundary surfaces.
- Verify that production already routes malformed `--retencion-observation` schema failures through `typer.BadParameter`, not the generic pydantic command boundary.
- Add an end-to-end CLI regression proving a missing `scheme` field reports the flag name and pydantic field detail.
- Keep the stored-data drift boundary distinct by correcting the boundary-test profile fixture to a valid bucket identifier.
- Review the test-only closure with `vaultspec-code-reviewer`.

## Outcome

- Closed. A malformed `--retencion-observation` object is refused as a CLI argument error with `Invalid value`, the `--retencion-observation` flag, and `scheme: Field required` detail.
- Closed. The same CLI path does not emit `aeat config repair` guidance and does not reuse the stored-record schema-drift text.
- Closed. Stored-data drift coverage still exercises the repair-oriented boundary with a valid profile bucket id.
- Closed. No production code or locale files changed; the current parser implementation was already correct.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The live fix surface was `src/aeat/entrypoints/cli/_modelo_aggregate_cli.py`, not the stale plan-row pointer to `src/aeat/entrypoints/cli/_errors.py`; that parser already catches JSON and pydantic validation before the command error boundary.
- Review found no code issues. Residual note: `src/aeat/entrypoints/cli/tests/test_errors_boundary.py` has mixed working-tree line endings, but `git diff --check` passed.
- Validation: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_modelo_typed_observations.py src/aeat/entrypoints/cli/tests/test_errors_boundary.py -m integration -q` passed with 8 tests.
- Validation: `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_modelo_typed_observations.py src/aeat/entrypoints/cli/tests/test_errors_boundary.py` passed.
- Validation: reviewer reran the same focused pytest slice with `-p no:cacheprovider`, reran ruff, and ran `git diff --check` on the scoped files.
