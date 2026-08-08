---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6de3912cf456530fed372f1c832881ca332984fe0a5aad0e3c2a169fd6876546'
step_id: 'S09'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add the aeat app live filed pull-all verb, verified by test_documented_command_conformance.py and a new JSON-schema conformance case

## Scope

- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

- Add the `filed pull-all` verb emitting the onboarding result plus its advisories.
- Add the conformance cases for the registered schema.

## Outcome

The verb assembles its notices from the authorities beside the run model rather
than re-deriving them, so the asymmetry rule and the INFO-not-WARNING judgement
are each decided once. It adds one notice of its own: a WARNING naming every pair
that REFUSED, stating explicitly that a refusal is not evidence nothing was filed.

The envelope command identifier and the schema key are `app.live.filed.pull_all`,
matching the canonicalisation the CLI leaf walk performs on a hyphenated verb —
the sibling `pull_sources` key confirms the convention.

## Verification

uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -q -n0 -m "unit or integration"
    (within the closeout run below; 1147 passed overall)

The leaf-schema gate caught the key mismatch on first run, naming both sides:
`app.live.filed.pull_all` missing a schema and `app.live.filed.pull-all` an orphan
registry key.

## Notes

The envelope round-trip and no-bespoke-notice-field cases are written out
explicitly rather than left to the shared parametrised gates, for the reason now
rowed as `P04.S30`: those gates parametrise over the schema registry as populated
at COLLECTION time, and the conformance module imports only the config payload
modules, so the entire `app.*` family never reaches them.
