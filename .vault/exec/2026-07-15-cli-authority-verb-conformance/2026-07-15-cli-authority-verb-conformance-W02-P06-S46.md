---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S46'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S46 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Prove acquisition-lock cleanup is target scoped and repeatable with real lock files and ## Scope

- `src/cadrumo/application/auth/tests/test_acquisition_lock.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove acquisition-lock cleanup is target scoped and repeatable with real lock files

## Scope

- `src/cadrumo/application/auth/tests/test_acquisition_lock.py`

## Description

- Add real-lock-file tests proving acquisition-lock cleanup is target-scoped and repeatable.
- Prove clearing one provider's lock leaves an unrelated provider's live lock file intact, and clearing one bucket's lock leaves the same provider's lock for another bucket intact.
- Prove clearing a target repeatedly removes the real lock once, then reports absence truthfully on the second and third calls without error.

## Outcome

Focused suite green: `uv run --no-sync pytest src/cadrumo/application/auth/tests/test_acquisition_lock.py -q` reports 7 passed (4 prior plus 3 new target-scoped and repeatable proofs). Ruff clean. The tests write and inspect real crash-recoverable lock files on disk with no mocks.

## Notes

Acquisition-lock paths are keyed by both bucket id and provider kind, so scoped cleanup is naturally target-specific; `clear_auth_acquisition_lock` returns the pre-clear status and treats an absent lock as a truthful no-op, which is what the repeatability proof asserts. No source-code change was required; only the missing proof was added.
