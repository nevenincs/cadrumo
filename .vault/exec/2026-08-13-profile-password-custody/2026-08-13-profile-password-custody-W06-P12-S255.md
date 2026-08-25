---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6389f7e98a19e0f3d2b4c4e5f5df492acb50836c872aba6e809f93a0a9395dc2'
step_id: 'S255'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Reconcile the censo-update sequence with the current censal projection and reviewed-apply authority

## Scope

- `docs/_sequences/contracts/how-to/censo-update/`
- `docs/_sequences/how-to/censo-update/`
- `docs/how-to/censo-update.md`
- `src/cadrumo/application/user_profile/`
- `src/cadrumo/entrypoints/cli/_config/_censo_file.py`

## Description

- Trace censal observation, projection, exact reviewed operand, baseline, and sole-writer apply authority with Vaultspec RAG and exact source symbols.
- Reconcile the live-only pull contract and user guide with the current CLI's fresh-read apply behavior without presenting its preview as captured approval.
- Address validation through captured profile names and assert stable validation, readiness, period, and registry-revision semantics.
- Regenerate only the censo-update page outputs through the sequence owner CLI and verify focused application, CLI, parser, conformance, lint, and type gates.

## Outcome

The censo-update guide now states that the current CLI `--apply` invocation performs a new authenticated read and that its preceding preview is not the operand applied. It directs the operator to review the apply result itself and names the captured exact-baseline reviewed lifecycle as pending work rather than ratifying the direct frontend path.

Executable sequences now carry the profile identity they observed into addressed validation and independently assert the Modelo 303 filing year, period, registry revision, and readiness state. No application projection or censal mutation logic was duplicated or changed.

## Notes

- RAG confirmed `CensalOperationExecutor` and `CensalReviewedOperand` own one acquisition, encrypted reviewed state, exact baseline, and resume-without-reread; `_project_censal_review` owns its safe projection and `apply_cotejo` remains the sole mutation authority.
- The current CLI pull and legacy manager action bypass that reviewed operation. This Step documents the conflict honestly; concurrent plan commit `cfe5d51459` records the canonical migration as `W06.P12.S257`.
- Verification passed: censo-update golden and cumulative coherence; 48 focused censal application/CLI tests; 444 parser, comparator, documented-command, and JSON-schema conformance tests; scoped Ruff, formatting, and ty.
