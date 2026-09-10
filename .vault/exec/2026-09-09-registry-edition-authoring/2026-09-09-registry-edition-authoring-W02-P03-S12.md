---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:2ea38015382a717c3f856e9bf3594959938e0ab043eded748cee60a5d59eb667'
step_id: 'S12'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Add the round-trip gate: a materialised edition equals its pre-migration materialisation by typed equality, and its export bytes are unchanged. This gate is what makes each migration step acceptable and is retired after the last modelo. Proof: it passes on the unmigrated corpus before any modelo moves.

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/tests/test_revision_edition_round_trip.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_revision_edition_round_trip.py` -> `pass`
- `verify:` `uv run --no-sync ruff check` / `ruff format` / `ty check` on the added file -> `pass`

## Notes

- Mandatory code review not yet run; the executor had no reviewer dispatch available.
- CI checkouts are depth 1; the first baseline entry fails closed there until the unit lane fetches the base commit.
- `build_draft` calculates from the bundled authority regardless of the schema provider, so byte comparison judges the export surface only.

- The reviewer persona could not be launched. The orchestrating session reviewed the gate against the ADR's proof obligations: the equality is explicit and not pydantic `==`, a separate order assertion, bytes only where an export scenario exists, the reference read from the base commit, and a fail-closed on a delta-authored reference. Re-run: 66 passed, ruff and ty clean. Follow-on: CI checkouts are shallow, so the job running this gate needs full history before the first migration entry lands.
