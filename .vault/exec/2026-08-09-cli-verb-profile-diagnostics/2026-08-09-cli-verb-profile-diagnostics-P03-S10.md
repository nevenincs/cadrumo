---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:0b21fb5dd9879a98e35482ce14c90170cfd8fbb25c6d53b4849bfe2c2f0cc69d'
step_id: 'S10'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Promote the binding-selector profile-key extraction to the registry package public facade so consumers outside the domain module can resolve a profile binding to its consumed keys

## Scope

- `src/cadrumo/domain/calculations/registry/__init__.py`

## Description

- Renamed the private `_selector_profile_keys` to `binding_profile_keys` in the profile-grounding module, expanded its docstring to state which selector members contribute and why the gate member does not, and exported it from the module and the registry package facade.
- Left the whole-registry grounding index calling the same function, so the per-binding extraction and the registry-wide inversion cannot diverge.

## Outcome

A caller holding one binding can now obtain the profile keys it consumes without building the whole-registry grounding index, through the owning package's public facade rather than a private module path.

The function was promoted rather than reimplemented at the call site. Its subtlety is exactly the kind that gets lost in a reimplementation: `required_when_profile_key` names a key to TEST rather than to file, so counting it would over-claim that key's legal basis. A second extraction written from the selector shape would very plausibly have included it.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_import_hygiene_gate.py src/cadrumo/tests/test_marker_integrity.py -n 0 -q
    51 passed in 148.82s (0:02:28)

The import-hygiene gate is the relevant one here: it forbids cross-package imports from a private module, so it fails if a consumer added in the sibling Steps reached the old private name instead of the facade.

## Notes

Nothing about the grounding index's behaviour changed; the rename is internal to the module plus a new export.
