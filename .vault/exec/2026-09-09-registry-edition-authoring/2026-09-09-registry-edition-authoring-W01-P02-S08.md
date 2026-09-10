---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:8100b8ec82d9053e166347fcdc5b0c082ddf90d9d25c4d97b9bdd85107d199aa'
step_id: 'S08'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Add the lineage totality gate, failing closed: a successor-edition row must carry lineage or declare itself new. A row carries lineage when its chain id is also carried by the edition immediately before it, or when it declares an origin (which S40's gate then enforces); an absence origin declares its kind of none; anything else is unresolved — including a row whose id only starts its chain in its own edition. Totality is a completeness property of the authoring corpus, NOT a load-time validity condition: the product must keep loading a registry whose lineage is partial, and one modelo will stay partial for a long campaign. So the RULE is a pure function in the registry package taking the exception set as a parameter, and the GATE that enforces it runs in the dev lane, fed from the seeding ledger, and fails the lane on any unlisted unresolved row. Unresolved rows pass only as per-row, classified ledger entries — never a modelo, prefix or count exemption. Modelos not yet examined are enumerated row by row as not-examined with their reason: the list is closed, so a new row added later is caught and an entry whose row gains lineage fails as stale, which a modelo-wide carve-out would never do. Proof: a planted row with neither is refused; a stale exception is refused; a row with a resolved id or an absence origin passes; the corpus passes with every unresolved row accounted for.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/casilla_lineage_totality.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_totality.py`
- `A` `dev/registry/analysis/casilla_lineage_ledger.py`
- `A` `dev/registry/tests/test_casilla_lineage_totality_gate.py`
- `M` `dev/registry/analysis/casilla_lineage_seed.py`
- `M` `dev/registry/analysis/casilla_lineage_ledger.toml`
- `M` `dev/registry/tests/test_casilla_lineage_seed.py`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_casilla_lineage_totality_gate.py dev/registry/tests/test_casilla_lineage_seed.py src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_totality.py src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_continuity.py src/cadrumo/domain/calculations/registry/tests/test_casilla_lineage_origin.py` -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`

## Notes

- The rule reads `NoPredecessor` and modelo 369's `predecessor.none` declarations, which landed with S48 in `ab60f19d4c`.
- The reviewer persona could not be launched; the orchestrating session reviewed the rule, the ledger reader and the gate against the ADR. Exceptions are keyed per row and the gate never reads the per-modelo `[[excluded]]` seeder metadata. No private imports. The orchestrating session re-ran the four lineage test files (52 passed), `registry verify` (exit 0), and ruff and ty (clean).
- The rule consults the adjacent edition and does not yet read a named `DeclaredPredecessor`; once an edition names its predecessor, the rule must follow the declared edge.
- One `aeat app registry verify` run exited 1 with no stderr while other sessions edited the tree; two following unpiped runs exited 0.
