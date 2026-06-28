---
tags:
  - '#audit'
  - '#rename-corpus-review'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-rename-corpus-review-schema-adr]]'
  - '[[2026-04-18-rename-corpus-review-implementation-plan]]'
---

# `rename-corpus-review` Code Review

No findings.

Plan audit result: the plan covers every corpus-loading surface that currently
hard-codes `reviewed_by` / `reviewed_at`, including `src/aeat/domain/casillas/_test_catalogue.py`,
`src/aeat/domain/casillas/_test_cli.py`, `src/aeat/domain/manuals/test_loader.py`,
`src/aeat/domain/manuals/test_schema.py`, and `src/aeat/domain/manuals/test_verify.py`. The
verification scope also matches the revised ADR: assert the repository emits and
tests only `definition_reviewed_*`, with no lingering old-key fixtures in the
committed corpus.
