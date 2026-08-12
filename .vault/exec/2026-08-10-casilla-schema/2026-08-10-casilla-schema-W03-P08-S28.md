---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b04a99d841747d6bbb55159146f85ae45d19d79b050f8ea770aeac2b04d6d845'
step_id: 'S28'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace casilla-schema with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-08-10-casilla-schema-plan placeholders are machine-filled by
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
     The re-point pipeline health readiness at the persisted verification outcome and render INCOMPLETE distinctly from never-verified, with a parity regression and ## Scope

- `src/cadrumo/application/overview/_pipeline_health.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# re-point pipeline health readiness at the persisted verification outcome and render INCOMPLETE distinctly from never-verified, with a parity regression

## Scope

- `src/cadrumo/application/overview/_pipeline_health.py`

## Description

- Make the latest persisted `VerificationReport.completeness_status` and
  `granted_verificado_completo` authoritative for non-filed pipeline readiness.
- Render persisted `INCOMPLETE` separately from a calculated revision with no
  verification report, while retaining conclusive filed lifecycle precedence.
- Keep finding severities as display counts only and stop deriving verification
  readiness from `CalculationRevisionState`.
- Add an exact CLI regression that persists a genuine zero-finding incomplete
  report through the encrypted repository and contrasts it with the preceding
  never-verified output.
- Extend the existing four-locale pipeline help entry and the new incomplete
  summary through `dev.locales`, using the internal `incompleto` stem.

## Outcome

Pipeline health now reports `calculated` only when the current revision has no
persisted verification outcome, `incomplete` for the latest persisted incomplete
outcome, `blocked` for the persisted blocked outcome, and `verified` only for a
complete outcome that granted `verificado_completo`. Presented revisions remain
filed regardless of a preceding verification report.

Focused verification passed:

- exact persisted-report CLI parity regression: 1 passed;
- typed pipeline-row transport regression: 1 passed;
- Ruff over the changed Python implementation and test: passed;
- strict BasedPyright over the changed Python implementation and test: zero
  errors, warnings, or notes;
- `git diff --check`: passed.

## Notes

The full focused integration module reached six passes and one transient failure
while a concurrent registry writer changed the registry directory during cache
fingerprinting. The exact new regression was rerun after that race and passed.
The locale scaffold check remains blocked by concurrent unrelated catalogue
drift (missing profile-schema and IVA-wallet keys plus stale ledger keys); the
four edited pipeline-help leaves themselves were written by the locale CLI.

