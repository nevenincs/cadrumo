---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:8e1e27c38af6ad4c198a5bea632ea5466909ec2872e92fd14beeb9b9a6a2f04d'
step_id: 'S329'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give the unvalidated-typed-defaults gate a witness that can still fail, because enabling validated defaults on the shared strict-frozen configuration made that gate permanently vacuous: its witness fixture declares the SHARED constant as its own model config, and that constant now carries `validate_default=True`, so the deliberately-invalid default the witness exists to smuggle is rejected at the witness's own construction -- the gate has nothing left to catch and its assertion that the schema check REFUSES an unvalidated typed default now passes because nothing reaches the check at all. A gate whose witness cannot express the violation it hunts is worse than no gate: it reports green forever and reads as coverage. Give the witness its own config literal carrying the strict and frozen settings WITHOUT validated defaults, so it can once again hold a default its field would reject, and prove the gate bites by asserting it refuses that witness and admits a well-formed one. Do NOT resolve it by relaxing the shared constant, which is the fix that would undo a real defence to keep a test meaningful

## Scope

- `the operations registry test witness fixture and the schema-identity gate that consumes it`

## Changes

- `M` `src/cadrumo/application/operations/tests/test_registry.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_registry.py` -> `pass`

## Notes

The Step described the gate as permanently vacuous and reporting green forever. It
was in fact red: the witness declared the shared strict-frozen constant, which now
carries `validate_default=True`, so the deliberately-invalid default could not be
expressed and `pytest.raises` reported DID NOT RAISE. The underlying defect is the
one the Step names, a witness that cannot state the violation it hunts, but the
symptom was a failing gate rather than a silent one. Recorded because the Step's
diagnosis will otherwise mislead the next reader.

The witness now declares its own strict and frozen config literal WITHOUT validated
defaults, so it can again hold a default its field rejects. An admitting case was
added alongside it, proving the refusal is about the missing validation and not
about carrying a default at all. A vacuity guard asserts the witness config still
omits `validate_default`, so a future re-pointing at the shared constant names its
own failure instead of surfacing as a bare DID NOT RAISE.

Both halves proven by mutation from outside the repository: blinding the
validated-default arm of `_require_model_config` reds the refusal while the
admitting case stays green, and re-pointing the witness at the shared constant trips
the vacuity guard with its stated message.
