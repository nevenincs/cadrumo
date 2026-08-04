---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:770eae67f38eca635a636df3ffe13e33ad936a312bb3fb97ff281c009a78d57c'
step_id: 'S04'
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
     The S04 and 2026-08-04-modelo-localization-cascade-plan placeholders are machine-filled by
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
     The Classify candidates as grounded, revision-exact, or continuity-candidate without promoting provisional identity and ## Scope

- `dev/registry/migration` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Classify candidates as grounded, revision-exact, or continuity-candidate without promoting provisional identity

## Scope

- `dev/registry/migration`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Re-ground the classification boundary with `vaultspec-rag`, the ADR, and feasibility research.
- Group only ungrounded declared `casilla.id` values by Modelo and repeated revision presence.
- Classify declared continuity as `grounded`, unique ungrounded occurrences as `revision_exact`, and repeated ungrounded occurrences as `continuity_candidate`.
- Attach an explicit migration-only provisional group token without changing the S03 canonical address.
- Add real bundled-corpus tests for the measured partition and refusal to serialize incomplete provisional state.

## Outcome

Implemented immutable structural classification in `dev/registry/migration`.
The complete current population partitions into:

- 144 grounded rows from 18 declared continuity occurrences.
- 32,008 revision-exact rows.
- 94,040 continuity-candidate rows across 2,354 provisional groups.

Classification uses only declared continuity presence and repeated
Modelo/casilla occurrence across revisions. It never promotes a provisional
group into `continuidad_id`, and it never uses values, labels, printed
numbers, or normalized text as semantic evidence.

Modified files:

- `dev/registry/migration/__init__.py`
- `dev/registry/migration/manager.py`
- `dev/registry/migration/tests/test_candidate_classification.py`
- `.vault/reference/2026-08-04-modelo-localization-cascade-reference.md`
- `.vault/exec/2026-08-04-modelo-localization-cascade-W01-P02-S04.md`
- `.vault/plan/2026-08-04-modelo-localization-cascade-plan.md`
- `.vault/audit/2026-08-04-modelo-localization-cascade-audit.md`

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Focused validation passed:

- `uv run --no-sync ruff format --check dev/registry/migration`
- `uv run --no-sync ruff check dev/registry/migration`
- `uv run --no-sync basedpyright dev/registry/migration`
- `uv run --no-sync pytest dev/registry/migration/tests/test_candidate_classification.py -q -n 0 -m integration` — 2 passed.

No production schemas, locale data, readers, migration output, or live
registry were modified. Later source-hash manifest and emission steps remain
out of scope.
