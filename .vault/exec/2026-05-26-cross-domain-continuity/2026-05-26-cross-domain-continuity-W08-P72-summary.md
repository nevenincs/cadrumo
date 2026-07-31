---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:d9b1678c0f52275e85bba780d51a39a78e679eacb5c184884c62d333b9508daa'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` `W08.P72` summary

S423 closes the selected-language locale parity gap found by the fresh Catalan and Hungarian persona rerun. Human-facing parser, calculation, verification, formula, and lifecycle text is localized at the CLI boundary while durable verification records retain one language-neutral canonical representation.

- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_modelo_cli_support.py`
- Modified: `src/aeat/entrypoints/cli/_modelo_rendering.py`
- Modified: `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`
- Modified: selected-language locale catalogues
- Created: `src/aeat/entrypoints/cli/tests/test_s423_selected_language_cli.py`

## Description

The phase isolates presentation localization from calculation and verification persistence. Exact canonical semantic contracts are translated only when rendering text notices, text reports, and JSON projections; all finding identity inputs, legal and source references, and encrypted stored payloads remain canonical. The CLI selector adapter also localizes only the exact already-verified refusal, preserving the application error.

Evidence covers real encrypted-store CLI workflows: two successful selected-language M130 personas, Catalan and Hungarian retry refusals, a successful pre-activity report viewed in a second language, and a non-granted M390 Catalan-to-Hungarian re-verification. The M390 flow proves a stable report id and single persisted report, canonical stored English findings, and localized blocking messages and next actions in both languages. The full selected-language integration file passed 4 tests; focused unit tests, Ruff, locale scaffold/audit, and scoped diff checks also passed. Independent review approved the final boundary.
