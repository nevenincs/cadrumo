---
tags:
  - '#audit'
  - '#live-submit-permanently-forbidden-code-review'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-live-submit-permanently-forbidden-plan]]"
  - "[[2026-04-27-live-submit-permanently-forbidden-adr]]"
  - "[[2026-04-27-live-submit-permanently-forbidden-research]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---



# `live-submit-permanently-forbidden-code-review` audit: `code review`

## Scope

Final code review for issue `#432` across the changed submission, auth-gate,
workflow, CLI, config, error-registry, documentation, and ADR surfaces that
implement the permanent prohibition on live AEAT submission.

Decision: **PASS** — the direct transport, workflow, settings,
error-taxonomy, regression-test, and Kent-facing documentation invariants for
issue `#432` now hold. No findings remain in the current branch state.

## Findings

VERIFIED-001 | INFO | No executable live-transport path remains in product code.
Reviewed `src/aeat/adapters/outbound/aeat/export/_engine.py`, `src/aeat/adapters/outbound/aeat/export/_submitters/__init__.py`, `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py`, `src/aeat/entrypoints/cli/submission/__init__.py`, `src/aeat/entrypoints/cli/filing/__init__.py`, `src/aeat/entrypoints/cli/workflow/run.py`, `src/aeat/entrypoints/cli/workflow/next.py`, `src/aeat/application/workflow/_engine.py`, and `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py`. The shipped runtime exposes no live-submit CLI surface, no workflow live flags, no concrete submitter `submit()` method, and no reachable AEAT write transport in the production composition path.

VERIFIED-002 | INFO | `SubmissionEngine` now refuses live execution before preflight.
A direct runtime probe against the current branch returns `LiveSubmitForbiddenError` for `submit_draft(..., dry_run=False)` before any preflight rejection. `src/aeat/adapters/outbound/aeat/export/_engine.py:176-180` enforces the order, and `src/aeat/adapters/outbound/aeat/export/test_engine.py:245-256` pins both the ordinary and invalid-draft cases.

VERIFIED-003 | INFO | Legacy live-submit env vars and public legacy error codes are removed.
`src/aeat/config.py` no longer exposes `AEAT_LIVE_SUBMIT_ENABLED` / `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN`; `env/.env.example` now documents permanent prohibition instead; `src/aeat/adapters/outbound/aeat/export/__init__.py` exports only `LiveSubmitForbiddenError` and the current submission errors; `src/aeat/core/errors/_registry.py` and `docs/error-codes.md` no longer publish the older live-submit enablement/refusal codes.

VERIFIED-004 | INFO | Historical runtime helpers are removed and ADR traceability is aligned.
`src/aeat/adapters/outbound/aeat/export/_confirm.py`, `src/aeat/adapters/outbound/aeat/export/_audit.py`, and `src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py` are deleted from the branch; `src/aeat/adapters/outbound/aeat/export/_engine.py` no longer carries the dead audit-log compatibility kwarg; and `.vault/adr/2026-04-27-live-submit-permanently-forbidden-adr.md` now includes the canonical `#live-submit-permanently-forbidden` tag, fixing the earlier vault-traceability mismatch.

TEST-001 | INFO | Focused prohibition regressions are broad and passing.
The targeted branch-state suite passes at `76 passed, 1 skipped, 1 deselected`: `src/aeat/adapters/outbound/aeat/export/test_live_submit_permanently_forbidden.py`, `src/aeat/adapters/outbound/aeat/export/test_engine.py`, `src/aeat/adapters/outbound/aeat/export/test_errors.py`, `src/aeat/adapters/outbound/aeat/export/_submitters/test_modelo130.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_gate.py`, `src/aeat/entrypoints/cli/submission/test_no_submit_command.py`, `src/aeat/entrypoints/cli/filing/test_filing_cli.py`, `src/aeat/entrypoints/cli/_test_doctor.py`, `src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py`, and `src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`. This is adequate for the direct prohibition contract at the submission/auth/CLI boundary.

VERIFIED-005 | INFO | The prior workflow dry-run/live modeling finding is resolved.
`src/aeat/application/workflow/_engine.py` now treats `dry_run=False` as a permanent-refusal preflight failure before calling the submission engine, `src/aeat/application/workflow/_protocols.py` and `src/aeat/application/workflow/__init__.py` document dry-run-only workflow semantics, `src/aeat/entrypoints/cli/workflow/run.py` and `src/aeat/entrypoints/cli/workflow/next.py` continue to hard-code `dry_run=True`, and the workflow-focused regression slice passes at `42 passed`: `src/aeat/application/workflow/test_engine.py`, `src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py`, `src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`, `src/aeat/adapters/outbound/aeat/export/test_engine.py`, and `src/aeat/adapters/outbound/aeat/export/test_live_submit_permanently_forbidden.py`. The stale workflow live-success assertions are gone; the replacement tests now prove refusal before dispatch and surface the permanent-forbid message.

## Recommendations

No remaining findings. Continue treating issue `#432` as a standing charter
check for any future submission, workflow, auth-gate, settings, CLI, or ADR
change.
