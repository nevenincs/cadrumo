---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:416ca714c76cf2c0da96321d2e487e2f739347f877219f4f46d7fc1e03998df1'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S30 IVA and recargo normalization review`

## Scope

Independent review of W04.P15.S30 against the accepted facts-registry plan, the adapted-family normalization reference, the raw IVA and recargo schedule compiler, authored fragments 0062 and 0063, direct provider registration, decimal selector materialization, and focused tests. The full IVA row comparison matched all 68 raw rows including applicability, values, legal and source references; source-citation parity also passed. The recargo comparison matched all seven raw rows, including Decimal applied-rate selectors, windows, values, notes, and legal references. Fact grounding, precedence validation, direct authored provider ownership, directory ownership, and Ruff passed.

## Findings

### stale-external-constants-ledger-read | high | The focused S30 handoff suite errors against the retired ledger schema

`test_handoff_targets_live_wave3_steps_files_and_wave1_ledgers` reads `external["classifications"]`, but the committed S31 retirement ledger now intentionally has schema version 2 and only the negative census `retired_statutory_symbols`. The focused command therefore reports one failure and 20 passes with `KeyError: 'classifications'`. The new S30 authored-fact assertions are sound, but the remaining positive mapping assertion retains a superseded ledger contract and blocks the checkpoint's required validation.

### stale-external-constants-ledger-read | low | Resolved by testing the v2 negative census and authored destinations

The repair removes the obsolete read and explicitly requires the version-2 zero declaration and consumer counts, the nonempty retired statutory-symbol census, the retired IVA general-rate symbol, and the absence of `classifications`. It independently derives the two destination identities from the IVA retirement ledger and proves that each is present as an authored mapping fact with only authored variants. No positive legacy mapping or adapter was recreated. The repaired focused suite passes all 21 tests and Ruff passes.

## Recommendations

Remove the stale positive external-constants classification join from the Wave-2 handoff manifest and test instead of restoring any legacy mapping or adapter. Keep S30 open until its focused suite is green; the S31 negative census should remain the sole proof that the retired Python declarations stay absent. That condition is now met.

## Final verdict

Clear to close W04.P15.S30. The normalized IVA and recargo facts remain the sole registered provider path; raw compiler and source-path deletion stays explicitly deferred to W04.P17.S56-S57.
