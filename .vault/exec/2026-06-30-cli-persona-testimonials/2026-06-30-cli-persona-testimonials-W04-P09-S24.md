---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S24'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# W04.P09.S24 Modelo 303 Compensation And Devolucion Legal Wording

Scope: official-source grounding and wording-only legal hardening around Modelo
303 compensation carry-forward and REDEME devolucion disposition.

## Description

RAG grounding:

- `uvx vaultspec-rag search "Modelo 303 compensacion carryover legal text LIVA article 99 IVA wallet" --type code`
- `uvx vaultspec-rag search "Modelo 303 compensacion carryover IVA legal grounding" --type vault --doc-type adr`
- `uvx vaultspec-rag search "REDEME refund election resolve_modelo_result_disposition devolucion compensacion Modelo 303" --type code`
- `uvx vaultspec-rag search "redeme refund election operator choice standing election Modelo 303" --type vault --doc-type adr`

Official source packet:

- BOE Ley 37/1992 art. 99, 115, and 116.
- BOE RD 1624/1992 art. 30.
- AEAT Modelo 303 instructions 2025.
- AEAT Pre303 compensation-wallet FAQ.

The decision was wording-only. Current accepted ADR policy still treats REDEME
inscription as the application's standing monthly-devolucion disposition policy,
while non-REDEME last-period refund uses explicit `DEVOLVER`. The wording now
avoids implying AEAT payment, acceptance, or official legal certainty from local
calculation/export. Text now says "requested as devolucion" and "excluded from
compensacion carry" instead of "returned by AEAT".

## Outcome

Changed wording only in:

- `src/aeat/application/modelo/_result_disposition_resolution.py`
- `src/aeat/core/_refund_election.py`
- `src/aeat/core/_result_disposition.py`
- `src/aeat/domain/iva_compensation/_carry_forward.py`
- `src/aeat/application/modelo/_revision_persistence.py`
- `src/aeat/application/modelo/_filed_revision_observation.py`
- `src/aeat/application/modelo/tests/test_export_result_disposition.py`
- `src/aeat/application/modelo/tests/test_modelo_303_refund_auto_carry_e2e.py`
- `src/aeat/application/modelo/tests/test_modelo_303_refund_election_e2e.py`
- `src/aeat/application/calculations/tests/test_modelo_303_refunded_period_carry.py`

Code review found no behavior or assertion changes. Residual uncertainty remains:
if the project wants REDEME taxpayers to choose `C` per period, that requires a
new accepted ADR because it changes user-visible defaults, export behavior, and
cross-period carry.

## Verification

Passed:

- `.venv\Scripts\pytest.exe` on the four focused M303 refund/disposition test files -> 25 passed in the worker run.
- Reviewer rerun of the same focused files -> 25 passed.
- `.venv\Scripts\ruff.exe check` on scoped S24 files -> passed.
- `git diff --check -- <scoped files>` -> passed.
- W04 touched-file ruff gate in isolated latest-HEAD worktree passed.

Latest isolated retest note: current clean `HEAD` blocks these registry-loading
tests on baseline source byte-count mismatch `boe-modelo-210-base-order`, proven
in a no-W04 baseline worktree.

