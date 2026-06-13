---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S70'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W06.P18.S70`

Scope: `.vault/audit`.

## Description

- Captured the W06 focused type baseline after S64 through S69.
- Verified the combined executed bucket set is `ty`-green.
- Recorded Pyright residuals explicitly instead of claiming a broader all-green
  state.
- Used the resident VaultSpec RAG server on port `8766` to ground the baseline
  format against the earlier W02 typecheck baseline audit.

## Outcome

The W06 type baseline is persisted. S70 closes the current type wave with a
green primary `ty` ratchet and an explicit Pyright follow-up list.

## Notes

Verification:

- `uv run --no-sync vaultspec-rag search "repo health type ratchet residual ty pyright audit plan S70" --type vault --max-results 8 --port 8766 --json`
- `uv run --no-sync ty check src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py src/aeat/adapters/outbound/aeat/auth src/aeat/application/aggregation src/aeat/domain/filing src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py --output-format concise`
- `uv run --no-sync pyright src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py src/aeat/adapters/outbound/aeat/auth src/aeat/application/aggregation src/aeat/domain/filing src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py --level warning --warnings`
