---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:ab9ca58cd826a73a8724db5b17c979576b5ada31f9a4a5f04d873721273597df'
step_id: 'S45'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add a path-based requirement renderer beside the selector-based one and export it

## Scope

- `src/cadrumo/application/user_profile/_preflight.py`

## Description

- Added `format_profile_path_requirements`, rendering profile PATHS through the canonical requirement builder, and exported it from the module and the package facade.
- Documented on both renderers why they are not interchangeable.

## Outcome

**This Phase corrects a defect in earlier work in this same campaign, not in pre-existing code.**

Registry bindings name the profile fact they consume by its `section.field` PATH. The deadline engine's completeness gate names its fields by their declared `model_selectors` TOKEN. These are different namespaces, and a key from one does not resolve in the other.

Two surfaces landed earlier - the modelo requires warning and the date-binding calculate guidance - hold BINDING keys and were wired to the selector renderer. Every key therefore resolved to nothing and was passed through unchanged, so both enrichments were silently no-ops. The surfaces were no worse than before, but they were not better either, and both Steps were recorded as delivered.

A second renderer was added rather than the existing one widened to try both lookups. Trying both would make the resolution depend on which namespace happened to match first, and a key that exists in both would resolve non-deterministically. Two named functions make the caller state which kind of key it holds.

## Verification

    uv run --no-sync pytest src/cadrumo/application/user_profile/tests/test_requirement_rendering_paths.py -n 0 -q
    4 passed in 8.98s

## Notes

The defect was invisible to the tests in place because they asserted the output was not the BINDING ID. Under the no-op, the output was the profile KEY, which satisfies that assertion while still being a raw identifier.
