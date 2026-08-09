---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:99d908d9c4152451657f6912b018d66ee6b76070339e6d0600d9aa37360a5364'
step_id: 'S37'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Name the Cl@ve identity field by its schema-derived label in the missing-identity credential refusal

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Added `_profile_field_label`, returning one field's operator label from the canonical requirement builder.
- Passed the Cl@ve identity field's label on the refusal's context and removed the storage path from the sentence.

## Outcome

The refusal names the credential the way the profile editor names it.

The bare label is used here rather than the grounded rendering the other refusals use, because this name is embedded mid-sentence: a trailing legal citation would read as part of the instruction to record the value. The other refusals present their fields as a terminal list, where a citation reads correctly.

These three Cl@ve fields declare no `model_selectors`, so their labels resolve from the path alone. That is why the tests assert the rendering neither equals nor contains the path: the requirement builder's documented fallback is to return its argument unchanged, so an unresolved field and a resolved one are distinguished exactly by that.

The refusal CONDITION is unchanged.

## Verification

    uv run --no-sync pytest src/cadrumo/application/auth -m "unit or integration" -n 0 -q
    319 passed in 75.35s (0:01:15)

## Notes

An existing test pinned this refusal's context dict exactly and failed on the added key. Its own name says it asserts the refusal NAMES the absent credential, so it was updated to assert the schema-derived label rather than reverted or loosened.
