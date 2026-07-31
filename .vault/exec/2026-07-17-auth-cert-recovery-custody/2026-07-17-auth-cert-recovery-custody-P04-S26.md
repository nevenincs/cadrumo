---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:fe8acfc25c8b58a27dc14de64be42ea92de816c04315baace9877b00f712c7f9'
step_id: 'S26'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Replace obsolete bootstrap exemptions with the exact accepted passphrase and recovery paths

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`

## Description

Verified against HEAD `8af409cd3f`, no re-implementation needed:

- Confirmed `_bootstrap_exempt.py`'s `BOOTSTRAP_EXEMPT_VERB_PATHS` carries exactly the current accepted custody paths (`config switch`, `config profile logout`, `config reset`, `config passphrase change`, `config recover`, `config recovery`) and none of the obsolete spellings (`rekey`, `show-recovery`, `verify-recovery`) that `test_root_grammar_invariants.py` pins as retired.
- Ran `test_root_grammar_invariants.py` and `test_repair_policy_coverage.py`, which assert the retired verb names are absent and the repair-policy/bootstrap inventories agree with the recovery family and flat `recover` exception.

## Outcome

Verified complete, zero production-code changes needed. `uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py -q -m integration` → `15 passed`.

## Notes

Bookkeeping-only closure: this record documents verification, not new implementation.
