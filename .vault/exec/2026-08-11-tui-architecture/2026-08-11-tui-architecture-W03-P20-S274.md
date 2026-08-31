---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:95d69a309f1d4374e6af475e79cf50b009d9504b069433ab1c732914b8cb12b1'
step_id: 'S274'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Correct the Workspace producer projection fingerprint so it identifies the contract a consumer actually receives instead of demanding that a model's input and output shapes coincide: derive the fingerprint from the serialization schema alone, replace the validation-equals-serialization equality with a real round-trip property proving a dumped projection re-validates, and prove the fingerprint admits a Decimal-bearing domain model while still refusing a genuine schema drift; amend the governing decision record in the same change

## Scope

- `src/cadrumo/application/modelo/workspace_producers.py`
- `the amended tui-architecture ADR`
- `and focused fingerprint round-trip and drift-refusal tests`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_producers.py -m 'unit or integration' -q` -> `pass` (18 passed; 1 unrelated pre-existing failure, a stale `docs/api` stub reference for a different module)

## Notes

The Step row's Scope names "the amended tui-architecture ADR", but the actual
governing decision record for the producer-contract/fingerprint mechanism is
`2026-08-24-tui-registry-api-gate-adr.md` -- `2026-08-11-tui-architecture-adr.md`
has zero mentions of "producer contract", "contributor_kind", or "epoch-v2".
Amended the ADR that actually defines the mechanism rather than the one the
Step row names, matching the same "the plan prose is the thing that is
imprecise" resolution used earlier in this campaign for the file-suffix and
workspace_manifest path questions.

The fingerprint now hashes `model_json_schema(mode="serialization")` only.
Added a real round-trip test (dump a Decimal-bearing instance, re-validate,
assert equality and type), a real acceptance test against the actual
motivating production model (`CalculationRevision`), and a real
drift-refusal test proving two structurally different projections -- and the
same projection unchanged -- still fingerprint differently and identically
respectively. The equality check is deleted, not weakened: nothing tolerates
a "known asymmetry"; the check is simply testing the correct property now.
