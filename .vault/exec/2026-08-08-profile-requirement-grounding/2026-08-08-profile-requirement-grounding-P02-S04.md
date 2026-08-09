---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d021cad8afb914c2cde54b41d37fcdf3f29b0a0bf717138c28121cea03eccde3'
step_id: 'S04'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Add label, legal_refs, and modelos to ProfilePreflightMissingPayload and its construction site

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

Added `label: str`, `legal_refs: list[str]`, `modelos: list[str]` to `ProfilePreflightMissingPayload` in `_config_payloads.py`, and populated them at the construction site in `_profile_inspect.py`'s `preflight` command from the corresponding `ProfilePreflightRequirement` fields. Also threaded `authority=resources().modelos.authority` into both `modelo_work_profile_preflight_report(...)` calls in that command so the registry-binding grounding union actually fires on this explicitly-invoked surface. Later extended (post-review) to append a `modelos` column to the command's text-line output, which had been carrying `label`/`legal_refs` but not `modelos`.

## Outcome

JSON payload delivered as specified when first checked. The text-line `modelos` column was added afterward as part of the P04.S10 review's `modelos-absent-from-both-text-surfaces` fix - that gap was in this Step's surface but outside its originally-scoped file list (it named only `_config_payloads.py`).

## Verification

`pytest src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py -m integration -n 0` - all pass, including a JSON-mode assertion that `missing[].label != missing[].selector` and that `legal_refs`/`modelos` are lists on a real blocked-profile fixture.

## Notes

None.
