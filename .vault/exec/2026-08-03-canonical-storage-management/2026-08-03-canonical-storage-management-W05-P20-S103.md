---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:7a31dab1ec8f845aeed9bfb46ed4fff0e8eb2aae2c8ce54bef69ff54145e100d'
step_id: 'S103'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

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
