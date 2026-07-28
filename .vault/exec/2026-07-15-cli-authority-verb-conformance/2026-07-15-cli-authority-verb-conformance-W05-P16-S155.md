---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S155'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Assert MCP descriptors and dispatch mirror accepted keys and reject removed keys

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_tools_and_dispatch.py`

## Description

- Verify the row's two halves separately rather than reading a green gate as covering both.
- Establish by measurement which keys the live CLI registers and which are retired.
- Find the rejection half unasserted, with a positive control proving the search was capable of finding it.
- Assert the retired keys have no descriptor and no dispatch round-trip, with the accepted successors as the control.
- Record what actually keeps a retired key off the surface, since it is not the exposability filter.
- Mutation-prove each new assertion by feeding it a key of the opposite kind.

## Outcome

The row's mirroring half was already satisfied. Its rejection half was not, and is now.

Corrected claim: an earlier version of this record stated the gate "asserts the descriptor set and the dispatch table mirror the accepted keys and reject removed ones". The first clause was true, the second was not. Before this change the module contained no reference to any retired key. That was established with a positive control on the same tool and path, matching a token the module does assert on, so the empty result is a measurement rather than a failed search.

The CLI side is settled and was measured rather than taken on trust. The live registration surface carries 295 schema keys. All eight accepted keys are present, and every retired key named for this cluster is absent. The sandbox family survives as eight `config.profile.sandbox` verbs with no `use` among them, so the retirement is specific rather than a family removal.

Two cases were added. The first asserts each retired key has no descriptor and no tool-name round-trip, and runs its positive control FIRST: the accepted successors are present and do round-trip, so a descriptor set that failed to build, or a lookup that always answered nothing, cannot satisfy the retirement checks while measuring nothing.

The second records a finding that changes where a later reader looks. `is_exposable_command` answers True for a retired key, because it only removes the root landing keys. It is a filter, not a registration guard. What actually keeps a retired verb off the surface is that descriptors are built from the registered schema refs. Pinning both halves stops a reader adding a retirement to the filter and believing that is the guard, and stops the opposite error of reading the permissive answer as a leak.

Each new assertion was mutation-proved by feeding it an accepted key where a retired one is expected. Both flipped to failure, so neither is vacuous.

`uv run --no-sync pytest src/cadrumo/entrypoints/mcp -m "unit or integration"` reported `285 passed, 6 warnings in 83.02s`, up from `279 passed` before this cluster. `ruff check`, `ruff format --check` and `ty check` all reported clean.

## Notes

The default marker selection made this surface look verified when it was not. A bare path run of the MCP tests reports `16 passed`, because these modules are integration-marked and the default expression is unit-only. Every measurement here uses an explicit marker expression, and the one serial test the xdist run holds out was re-run separately with `-n0` and reported `1 passed in 224.34s`.

The retired key list is written literally rather than derived. Deriving what is absent from the same registration the descriptors are built from would restate the implementation and pass however the registration drifted, which is the shape this campaign exists to remove.
