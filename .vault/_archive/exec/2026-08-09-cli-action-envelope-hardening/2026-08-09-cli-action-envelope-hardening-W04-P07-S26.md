---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:986fe1cb2e1c5dc7dd0fce45f04711b1baf913a176990eebf714ad51cfe55566'
step_id: 'S26'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace unknown-revision and verification continuations with bound or explicitly conditional actions

**Scope:** `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py`

## Description

- Grounded the closure with semantic code search and an ADR search. The accepted `cli-action-envelope-hardening` decision is the governing authority; the code search resolved one shared persisted-report projection and one shared discarded-parent admission guard.
- Confirmed the textual census with `rg` across the application, CLI, and focused tests. Verify and file address failures resolve from application preconditions; history no longer fabricates action text from report facts.
- Ran the focused AST authority proof. Lifecycle list, status, and history delegate continuation selection to the application and contain no legacy action construction or translation-default fallback.
- Closed the direct lifecycle cases with encrypted repositories and real verification readiness. A draft parent refusal, a verified parent refusal before the idempotent return, and a file refusal all preserve their catalogues.
- Added the persisted-report structural proof through the production renderer and output schemas. Historical `view` and `list` findings keep `action` as JSON null; live verification retains only the paired application verdict.

## Outcome

- Unknown natural targets and exact missing work-unit targets return declared schema verdicts. Where the catalog has no legitimate continuation, the action is absent and the no-recovery result is an explicit operator decision rather than a guessed command.
- A discarded parent is a persisted-state terminal condition for verify and file. It is evaluated before verification idempotence and filing mutation, with condition identity, evidence provenance, and localized message supplied from the canonical precondition source.
- The focused direct application suite passed 3 tests in 17.84 seconds. The CLI selector/envelope matrix passed 2 tests in 58.44 seconds across en, es, ca, and hu. The report renderer module passed 6 tests in 14.51 seconds. The live common-action resolver suite passed 14 tests in 38.08 seconds.
- The focused AST authority test passed 1 test in 0.80 seconds. The S26 locale verifier passed all four supported locales with ten keys each and identical placeholder shapes. Targeted `basedpyright` for the report-view test returned zero diagnostics; scoped Ruff format and Ruff checks passed, and the scoped diff check was clean.
- An earlier installed-console proof exercised natural verify and file absence against isolated storage. Both emitted a persisted-state `ERROR_MODELO_WORK_ADDRESS_NOT_FOUND` envelope with no action, `not_applicable` conditionality, and `operator_decision`; that proof used the installed console transport rather than an in-process runner.

## Notes

- No recovery prose, raw command string, or CLI-layer fallback was added. The action chain remains schema-resolved from the application verdict, while persisted report facts never reconstruct historical recovery instructions.
- The full repository `basedpyright` and global locale audit are not S26 acceptance evidence. Both remain affected by unrelated in-flight import and locale churn, so this record reports only the collected focused gates above rather than implying a workspace-wide green result.
- A first AST invocation used an integration marker on an unmarked test and collected zero tests. It was immediately rerun without that selector; only the collected 1-pass result is counted above.
