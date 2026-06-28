---
tags:
  - '#audit'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - '[[2026-04-30-aeat-restructure-adr]]'
  - '[[2026-04-30-aeat-restructure-plan]]'
---



# `aeat-restructure` Code Review


RESTRUCTURE-001 | RESOLVED | Root compatibility modules are intentionally deleted

The review originally classified missing root modules as a critical compatibility break because the earlier rollout text described retained public re-export modules. The accepted delivery model is now explicitly a major hard cut: `src/aeat/auth.py`, `src/aeat/errors.py`, `src/aeat/formulas.py`, and `src/aeat/submission.py` remain deleted, and callers must use canonical hexagonal package paths. The ADR outcome and execution records have been aligned to that model, so this is no longer an open code defect.

RESTRUCTURE-002 | RESOLVED | Public submission error identity is canonical

The review found that `aeat.adapters.outbound.aeat.export`, `aeat.domain.submission`, and `aeat.core.access_gate` exposed separate submission error class identities. The fix makes the domain and export surfaces re-export the canonical core access-gate hierarchy, and prunes duplicate domain-submission rows from the error registry.

RESTRUCTURE-003 | RESOLVED | Migration records aligned to hard-cutover model

The review found that some execution records still described a minor compatibility rollout with retained compatibility modules while later records described a hard cut. The ADR outcome, summary, final review record, and milestone-close record now use the same hard-cutover model: root modules are absent, canonical package paths are required, and import-contract tests are the active guardrail.

RESTRUCTURE-002-FOLLOW-UP | LOW | Canonical error identity fixed; regression coverage should pin it directly

Targeted probes now confirm `aeat.core.access_gate`, `aeat.domain.submission`, and `aeat.adapters.outbound.aeat.export` expose the same `LiveSubmitForbiddenError`, `SubmissionError`, and `SubmissionPreflightError` class objects. The core registry now declares only the `aeat.core.access_gate._errors` rows for those submission errors. The focused export/core registry test run passes, and `aeat.adapters.outbound.aeat.export.test_errors` now directly asserts cross-module class identity. Treat all three review findings as resolved under the accepted hard-cutover model.
