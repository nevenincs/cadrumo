---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
step_id: 'S336'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# durable maintenance gate two  -  ledger and storage roundtrip test suite remains in CI

## Scope

- `the S108-S109 S254 S273 work built it`
- `never deprecate without explicit replacement`
- `.github/workflows/`

## Description

- Assess-first: `ci.yml` already runs the full `uv run pytest` unit suite on push/PR to `main`, so the ledger + storage roundtrip tests do execute in CI today - but only as anonymous members of the whole suite, with no named durable gate and no anti-deprecation guard.
- Locate the roundtrip suite the S108-S109 / S254 / S273 work built: the ledger command + catalogue roundtrips under `src/aeat/application/ledger/tests` and `src/aeat/adapters/persistence/profile/tests`, the encrypted secure-storage roundtrips under `src/aeat/adapters/persistence/storage`, and the `src/aeat/tests/test_roundtrip_coverage.py` inventory meta-gate that asserts every declared persistence boundary still has its roundtrip test file on disk.
- Add `roundtrip-suite-gate` job to `.github/workflows/durable-maintenance-gates.yml` running that selector (`-k roundtrip` over the coverage gate plus the ledger + storage test directories) with a JUnit artifact, after `uv sync --frozen`.
- Add a prominent header guard: this gate MUST NOT be deprecated, removed, or selector-narrowed without an explicit replacement gate landing in the same commit.
- Verify the selector collects: 124 roundtrip tests collect from the named paths; all are `unit`-marked so the default `-m 'unit'` filter runs them.

## Outcome

Named, durable, blocking `roundtrip-suite-gate` job landed with an explicit never-deprecate-without-replacement guard in the workflow header. The selector collects the 124-test ledger + storage roundtrip suite plus the boundary-inventory meta-gate. This makes the roundtrip suite a first-class, greppable CI gate rather than an anonymous slice of the full unit run, satisfying the "remains in CI; never deprecate without explicit replacement" contract.

## Notes

Same plan-commit deferral as the sibling S335 record: the plan checkbox was flipped in the working tree via the plan CLI, but the plan file carries peer WIP and the shared index holds 51 peer-staged files, so committing the plan would sweep foreign work. Only the workflow file and the two exec records were committed, by explicit pathspec.
