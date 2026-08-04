---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:736c2c772b6cba0f9c6ee9948bac33385e8912984fc091d6230f15a016e81bf6'
step_id: 'S18'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-localization-cascade with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Resolve placeholder debt and year-parameterized label decisions before emission and ## Scope

- `dev/registry/migration and the authorizing ADR/research records` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Resolve placeholder debt and year-parameterized label decisions before emission

## Scope

- `dev/registry/migration and the authorizing ADR/research records`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Re-ground the pre-emission boundary with `vaultspec-rag`, the accepted cascade ADR, and both localization research records.
- Build a deterministic `PreEmissionReviewRegister` from the sealed `SourceManifest` without reading a second source of truth or writing registry data.
- Record every real mirrored or key-echo placeholder as `delete_not_migrate` for canonicalization while preserving its old resolved value for parity.
- Expose the measured placeholder debt as 9,453 mirrored-help leaves plus 24 help key echoes (9,477 mirrored-help debt), alongside 24 label key echoes and 48 total key echoes.
- Admit year-parameterized label families only for exact annual revision ids whose embedded year matches the revision and whose template renders every captured official value verbatim.
- Keep official-Spanish year declarations on `es`, exclude fallback-only non-Spanish rows, bind the register to a canonical SHA-256 digest, and reject counter, ordering, or tamper drift.
- Add real bundled-corpus coverage for the placeholder dispositions, year rendering, source binding, and tamper refusal.

## Outcome

Implemented the read-only pre-emission review contract in `dev/registry/migration`.

- Modified `dev/registry/migration/review.py`, `dev/registry/migration/__init__.py`, and `dev/registry/migration/tests/test_pre_emission_review.py`.
- The real bundled corpus verifies 9,501 explicit placeholder decisions: 9,453 mirrored help, 24 help key echoes, 24 label key echoes, and 48 key echoes in total. All preserve the old value in parity mode; all are marked `delete_not_migrate` for later canonicalization.
- The real corpus verifies year-token rendering for the `100` `vivienda habitual` family across 2020 and 2021, with exact rendered-value equality and no non-Spanish fallback declaration.
- Strict immutable records and a source-manifest-bound review digest reject reordered entries, counter drift, invalid revision-year derivation, mixed fallback/authored families, and tampered review seals.
- No production revision schemas, locale data, production readers, live registry, or migration output were written.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Focused validation passed:

- `uv run --no-sync ruff check dev/registry/migration/review.py dev/registry/migration/__init__.py dev/registry/migration/tests/test_pre_emission_review.py`
- `uv run --no-sync basedpyright dev/registry/migration/review.py dev/registry/migration/__init__.py dev/registry/migration/tests/test_pre_emission_review.py`
- `uv run --no-sync pytest dev/registry/migration/tests/test_pre_emission_review.py -q -n 0 -m integration` (`1 passed in 121.54s`)

The broader migration integration folder produced `13 passed, 1 failed in 706.06s`; the unrelated candidate-classification fixture expected 144 grounded rows but observed 3,576 while concurrent registry fragment edits were active. The source reader separately refused one moving snapshot, then the focused S18 run passed after the tree stabilized. This boundary remains unclaimed rather than being hidden or repaired by changing peer-owned expectations.

The read-only `vaultspec-code-review` audit found no critical, high, or medium implementation finding. The current plan still lacks the dedicated user-profile phase required by the accepted ADR amendment; that architecture-owned plan change remains a Sol decision and is not folded into this step.
