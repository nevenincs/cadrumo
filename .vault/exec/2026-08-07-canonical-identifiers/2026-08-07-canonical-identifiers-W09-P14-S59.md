---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0ed217d8601b27bad4acefbb8c29cbb9927800ffec845f66d63e82e65cb7caaa'
step_id: 'S59'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# prove the gate's bite: add a throwaway bare-`str` field named to match the namespace vocabulary on a scratch model outside `src`, confirm the gate reds, then remove it and confirm the gate is green again

## Scope

- `src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py`

## Outcome

The bite used a temporary source file outside `src`, containing a real Pydantic `ScratchProbe` model with `expediente_id: str`. The gate's own `identifier_fields` and `unenrolled` scanner functions reported:

```text
scratch/probe.py:5 ScratchProbe.expediente_id: str [BARE] token=expediente_id
```

The proof deliberately exited nonzero after detecting that field, establishing the required red condition. The scratch probe file was then removed and the scanner was re-run clean before the focused gate returned green.

No fake, mock, patch, monkeypatch, or mirrored validation was used. The committed detector test separately exercises an explicit source snapshot containing a bare identifier field, an enrolled identifier, a structural `short_` companion, and a non-vocabulary field.

## Verification

- Scratch bite â€” red: actual scanner detected `ScratchProbe.expediente_id` as bare.
- Scratch restoration â€” pass: the external probe file was absent and an empty explicit scanner input was clean.
- `uv run --no-sync pytest src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py -q` â€” 10 passed after restoration.
- `uv run --no-sync ruff check src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py` â€” pass.
- `uv run --no-sync ruff format --check src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py` â€” pass.
- `uv run --no-sync ty check src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py` â€” pass.

## Notes

The platform rejected recursive deletion of the exact temporary directory. Its sole scratch probe file was removed; the remaining empty directory is outside the repository and contains no source or test residue.
