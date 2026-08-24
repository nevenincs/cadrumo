---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:fb3255208a79633430dde3aa9ee63dd768fa77303e3f4daa8dcbf0a02935656b'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `Modelo 036 filing-route docstrings post-review`

## Scope

Independent post-review of `W02.P04.S81`, limited to the Modelo 036 lifecycle
and CLI callback docstrings plus their focused contract tests. Reviewed the
mixed implementation ancestor `b40fd5bf4c` only at those owned hunks and the
scoped follow-up `188eeb0d5b` in full. The review checked that a declaration is
recorded only after filing through AEAT Sede or in person at a competent AEAT
office, that an electronic `sede_justificante` is optional, and that the local
application never files. It also ran semantic discovery, whole-file reads, and
exact-symbol confirmation for the service and boundary to detect a parallel
recording or filing implementation.

Focused verification passed: `uv run --no-sync pytest
src/cadrumo/application/modelo/tests/test_m036_lifecycle_contracts.py
src/cadrumo/entrypoints/cli/tests/test_m036_command_shape.py -q` (20 passed),
and `uv run --no-sync ruff check` over the four scoped files.

## Findings

No in-scope finding. The semantic sweep and targeted symbol search locate one
canonical encrypted declaration-recording service and one thin CLI boundary;
the reviewed changes do not add a writer, submission path, authority model, or
duplicate contract. The Pydantic schema and the three callback docstrings now
say Sede-or-competent-office, distinguish optional electronic receipt evidence,
and retain the no-local-filing boundary.

Rendered `aeat app modelo m036 alta --help` remains governed by the separate
locale catalogue and continues to use its existing Sede-only wording. S81 did
not modify that catalogue or claim that the localized help text changed; its
callback-docstring test is intentionally separate from localized-help authority.

## Recommendations

Accept the scoped documentation correction. Keep any future rendered-help
localization change in the locale catalogue workflow with translations for all
supported locales; do not use callback docstrings as a second localization
authority. Keep `W02.P04.S81` unchecked until its required execution record is
present and canonical plan state is reconciled.
