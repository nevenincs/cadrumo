---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:5820b32044ecb7f0e7e9e15b10c8e564f5b824123278c4a87dece3fceb8f4209'
step_id: 'S02'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove the stale live censo adapter ignore entry

## Scope

- `.importlinter`

## Description

- Ground the Step with `vaultspec-rag search "stale live censo import-linter ignore no source module" --type code`.
- Confirm the waiver occurs once and that no live or tracked `_censo` source module or import edge exists.
- Remove only `cadrumo.application.live._censo -> cadrumo.adapters.**` from the layered-contract ignore ledger.
- Run the uncached graph to distinguish the separately planned S03 and S04 findings.

## Outcome

The dead live-censo waiver is gone. No source, import, contract, wildcard, or other ignore was changed. A fresh complete uncached invocation no longer reports the S02 edge and stops only on the unmatched `cadrumo.application.user_profile._censo_sync -> cadrumo.adapters.**` entry owned by S03.

A focused uncached four-contract run analyzed 3,421 files and 16,152 dependencies. The registry and both domain contracts remained kept; the core contract reported only the accepted helper-mediated path from `cadrumo.core.tests.test_isolation_fixture_state_root_coverage` through `cadrumo.tests.secure_sql`, owned by S04.

## Notes

The semantic query returned the architecture reporter and import-linter project configuration rather than the stale ledger line. Targeted `rg`, `fd`, and `git ls-files` supplied the decisive evidence: the waiver occurred once in `.importlinter`, no `_censo.py` exists under `src`, and no tracked live-censo module or caller exists. The entry was therefore a stale measurement exemption, not a dormant implementation or duplicate authority.

S03 and S04 remain intentionally open. No compatibility path, production waiver, test double, skip, or destructive worktree operation was introduced.
