---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c3af2d0a97776cb03c3b0da8183507487d77d2ac31fc639be2f6abb7f8d45bd1'
step_id: 'S04'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Add the delta-minimality screen in reporting mode only: no stated row is identical to the row it would inherit. SCOPE IT TO CASILLA ROWS ONLY. The completeness manifest does not inherit, so every migrated edition still restates its whole manifest — a screen spanning both families would report every migrated modelo as non-minimal forever, which is a permanently wrong answer rather than a noisy one. Proof: it names a modelo known to restate its casillas, and does not name a migrated modelo on manifest grounds.

## Scope

- `dev/registry/analysis`

## Changes

- `A` `dev/registry/analysis/delta_minimality.py`
- `A` `dev/registry/tests/test_delta_minimality.py`
- `M` `dev/registry/analysis/screens.py`
- `M` `dev/registry/README.md`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_delta_minimality.py dev/registry/tests/test_declaration_invariant_gates.py` -> `fail`

## Notes

- The one failing test is `test_no_registry_source_or_declaration_cites_a_vault_record`, triggered by committed `facts_*` files this Step did not touch; the other 51 pass.
- The `screens.py` import block carried a pre-existing ruff I001 at HEAD; it was re-sorted as part of enrolling the new screen.
- The reviewer persona could not be launched; the orchestrating session reviewed the diff against the ADR (casilla rows only, reporting mode, public imports, unjudged rows counted apart from minimal ones). `test_delta_minimality.py` 10 passed; ruff and ty clean.
- The screen imports `NoPredecessor` from `schema.py`, which S48 introduces, so this Step commits with or after S48.
