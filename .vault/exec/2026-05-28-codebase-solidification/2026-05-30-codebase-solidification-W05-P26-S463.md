---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-07-17'
body_hash: 'sha256:c35c9fdb20f919096c83a44e9c59d0c20e8ae318e78fbc0eb0a331c9e129d064'
step_id: S463
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# `codebase-solidification` `W05.P26.S463`

Aligned `inputs_snapshot` in `CalculationRevisionPayload`, `WorkCalculateResult`, and `WorkRevisionResult` from `dict[str, object]` to `dict[str, str]`, matching the domain source (`Mapping[str, str]`) and the application constructor that builds canonical Decimal strings.

- Modified: `src/aeat/entrypoints/cli/_modelo_payloads.py` (lines 84, 275, 317)

## Description

Three payload classes in the CLI wire module all declared `inputs_snapshot: dict[str, object]`. The domain `CalculationRevision` model declares `inputs_snapshot: Mapping[str, str]`, and the application action at `_actions.py:1066` builds a `dict[str, str]`. The CLI boundary was accepting any object type, silently bypassing pydantic's strict validation. All three occurrences were narrowed to `dict[str, str]`.

## Tests

Covered by S464 (`test_modelo_payloads.py`). Commit `781f9c0fd`.
