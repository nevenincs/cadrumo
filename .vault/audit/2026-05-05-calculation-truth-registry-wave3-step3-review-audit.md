---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave3-step3-exec]]'
---



# `calculation-truth-registry-wave3-step3` Code Review

No blocking findings.

Reviewed scope:

- `src/aeat/application/filing/test_export.py`, limited to the new Modelo 115
  export-verification assertion.
- `src/aeat/application/verification/test_verify.py`, limited to the new Modelo
  115 declaration-verification assertion and source path normalization.
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`, limited
  to the Modelo 115 verification tracking rows.
- `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-05-calculation-truth-registry-wave3-step3.md`.

Checks performed:

- The export-verification test writes an approved Modelo 115 draft through the
  committed registry layout and re-reads the generated payload through the
  public verification API.
- The declaration-verification test uses parsed declaration observations and
  the committed registry calculation expectation instead of a local schema,
  copied formula, or isolated fixture.
- The source path helper now follows the declared modelo so added tests do not
  carry an unrelated Modelo 130 file label.
- The plan keeps live artefact capture rows open and does not imply completed
  live filed-data coverage for Modelo 115.
- The reviewed scope does not introduce local-schema fixtures, fallback
  authorities, soft validation modes, or past-state comparison tests.

Verification reviewed:

- `uv run ruff check src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py`
- `uv run ty check src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py`
- `uv run pytest src\aeat\application\verification\test_verify.py src\aeat\application\filing\test_export.py -q`
- `uv run pytest src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_export.py src\aeat\application\verification\test_verify.py src\aeat\domain\calculations\registry\test_committed_registry.py -q`
- `git diff --check` over the reviewed scope.
- Static sanitization search over the reviewed code, tests, and step record.
