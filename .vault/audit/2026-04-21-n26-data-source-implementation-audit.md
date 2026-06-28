---
tags:
  - '#audit'
  - '#n26-data-source'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-n26-data-source-implementation-adr]]'
  - '[[2026-04-21-n26-data-source-phase-2-plan]]'
  - '[[2026-04-14-n26-data-source-research]]'
  - '[[2026-04-21-n26-data-source-audit]]'
---

# `n26-data-source` implementation code review

## Scope

- Branch: `feature/106-n26-research`
- Issue: `#308`
- Surface: `PdfN26Provider`, `SourceFormat.PDF`, provider auto-detection, `aeat financial ingest`, committed N26 PDF fixtures, and the implementation ADR / phase-2 plan
- Review basis: live code on `main`, hand-maintained fixture goldens, targeted pytest / Ruff / ty runs, and manual CLI inspection of the emitted rows

## Findings

### N26-IMPL-001 | MEDIUM | fixture breadth still covers the savings-statement family only

The implemented provider is grounded in a real N26 statement template family, but the public corpus recovered during this run came from sanitized N26 savings-account statements (`Sparkonto`) rather than the broader current-account / card / FX monthly statements discussed in the original research. The committed fixtures therefore prove a real N26 PDF read path and a real template change (`N26 Bank AG` -> `N26 Bank SE`), but they do **not** yet exhaust the wider current-account / FX statement family.

This is not a parser correctness bug on the exercised surface. It is a remaining evidence gap:

- the provider is implemented and green for the recovered real template family
- the broader N26 statement family is still under-sourced
- the feature should not be described as fully exhausted until a current-account / FX fixture family is sourced and added

## Verification

- `uv run python tests/fixtures/financial/n26/_generate.py` -> regenerated the committed deterministic PDF fixture corpus
- `uv run pytest src/aeat/domain/financial/providers/test_pdf_n26.py src/aeat/domain/financial/providers/test_base.py src/aeat/entrypoints/cli/financial/test_cli.py -q` -> passed (`15 passed`)
- `uv run pytest src/aeat/domain/financial/providers src/aeat/entrypoints/cli/financial/test_cli.py -q` -> passed (`26 passed`)
- `uv run ruff check src/aeat/domain/financial/providers/_pdf_n26.py src/aeat/domain/financial/providers/test_pdf_n26.py src/aeat/domain/financial/_raw_transaction.py src/aeat/domain/financial/providers/__init__.py src/aeat/domain/financial/providers/_detection.py src/aeat/entrypoints/cli/financial/ingest.py src/aeat/entrypoints/cli/financial/test_cli.py tests/fixtures/financial/n26/_generate.py` -> passed
- `uv run ty check src/aeat/financial src/aeat/entrypoints/cli/financial` -> passed
- `uv run aeat financial ingest tests/fixtures/financial/n26/n26-savings-2025-05.pdf --provider auto --output-json` -> emitted 6 rows matching the hand-written expected ledger for that fixture
- Manual fixture review -> the committed goldens for `2024-06`, `2025-01`, and `2025-05` match the visual statement rows, booking dates, value dates, and amounts in the synthetic PDF corpus

## Status

- Accepted for the implemented N26 savings-statement slice.
- Not yet accepted as the fully exhausted N26 monthly-statement family described in the research, because the current-account / FX fixture breadth remains open.
