---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:1fd958c2ed20090ef66fbdf790245c1b684a7c090a3d391cb0a6f468045243d2'
step_id: 'S454'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Read a translation key supplied through a conditional, since `empty_key="..." if not rows else None` is how a surface states a state-dependent label and the collector read only a bare literal, so both arms vanished and the catalogue looked complete on whichever branch a developer happened to exercise; two genuinely missing error messages surfaced once the arms were read, closing the missing side of codebase-to-locale parity to zero

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`
- `src/cadrumo/locales/{ca,en,es,hu}`

## Changes

Codebase-to-locale parity: missing 2 -> 0, extras 316 -> 308.

`_TRANSLATION_KEY_KWARGS` gained `label_key` and `empty_key`, and the kwarg
collector changed from reading one bare literal to recursing:

    empty_key="flows.progress.rows_absent" if not rows else None

is how a surface states a state-dependent label, and reading only a bare
literal dropped BOTH arms. The failure is asymmetric in the worst direction:
the key that ships is the one behind the condition, so the catalogue reads
complete on whichever branch a developer happens to exercise and is missing on
the other. The parameter is DECLARED to take a key, so any dotted literal that
can reach it is one.

Reading the arms surfaced two keys that were genuinely absent rather than
over-collected, at `application/modelo/work_addressing.py:940`: a calculation
revision id names either a work unit or a discarded one, and neither message
existed in any catalogue. Authored in es/en/ca/hu with
`%{calculation_revision_id}` and `%{work_unit_id}`; `set-batch` updated 4
catalogues. That closes the missing side of the gate to zero -- it was 228 when
this target opened.

Teeth: restoring the single-literal read fails the new gate on the conditional
arm. Restored by copy; the suite passes.

## Notes

`test_codebase_to_locale_parity` still FAILS on 308 extras, so target 2 is not
closed. The partition is now roughly 262 keys with no string literal anywhere
plus ~46 reachable but uncollected.

This is the FIFTH scanner blind spot found in this residue -- mapping lookup
tokens, a guard table's prose column, positional cross-module parameters,
boundary wrappers, and now conditional kwargs. Each turned keys that looked
dead into keys plainly alive, which is why "no literal found" is still not
permission to delete the 262.
