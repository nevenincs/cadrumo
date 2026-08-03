---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:525e11bc20d7fdf5d0b03925a018b9d9819c7e2a3ebd9d5c4d0bdd6711cb39ed'
step_id: 'S103'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S103 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Run the commissioned runtime write census, instrumenting the actual write primitives for a full suite run and recording every real destination, cross-checking the static census against what code paths the suite actually exercises and ## Scope

- `src/cadrumo/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the commissioned runtime write census, instrumenting the actual write primitives for a full suite run and recording every real destination, cross-checking the static census against what code paths the suite actually exercises

## Scope

- `src/cadrumo/tests/`

## Description

- Instrument the actual write primitives (`open`, `Path.write_*`, `os.replace`, etc.) for the duration of a full suite run, recording every real destination touched.
- Cross-check the static write-call census against what code paths the suite actually exercises.

## Outcome

Landed as `storage-root-ledger/14-runtime-write-census.md` in the session scratchpad: a full-suite run under write instrumentation, 5,328 write records / 2,980 distinct paths / 1,186 tests. Headline: zero writes reach the repository checkout or the real platform user-data root. One genuine leak found: `cadrumo-settings-*`, 457 unbounded temp directories originating from `env_scope.py:92` — a test-hygiene defect under the separate cleanup standard (see W03.P23, S84/S85), not an enrollment violation.

## Notes

**Coverage limit stated in its own findings, and worth restating here**: this covers only paths the suite actually exercises, not universal enrollment — the closure-criterion document's own "what a passing runtime check would and would not prove" section states this precisely. A companion directory-creation pass (`dir_census.py`) is written but not yet run. **Not durably homed** — same scratchpad-only gap as S102; findings recorded here so the analysis survives independent of the scratchpad file.
