---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:afca82b781b864c506853aceb9e99d1123d37be1d989106952f048e921da791d'
step_id: 'S11'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Enrich the app modelo requires unresolved-coefficient notice with schema-derived requirement rows instead of raw registry binding ids

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`

## Description

- Added `unresolved_profile_keys` to the data-inventory checklist, populated in the application layer from the unresolved bindings via the promoted extraction, de-duplicated and in binding order.
- Added the same field to the CLI output schema so the machine-readable payload carries the facts, not only the binding ids.
- Rewrote the warning message to render those keys through the shared enrichment helper, falling back to the binding ids when no key resolves.
- Kept the binding ids on the notice `context`.

## Outcome

The warning now names the profile facts the operator must supply. The binding ids remain on the notice context, because they are the registry-side identifiers a support channel needs while being the wrong thing to put in front of an operator.

Two deliberate choices:

The keys are computed in the application layer, not the CLI. Binding definitions are not in scope at the entrypoint, so computing there would have meant re-resolving the snapshot at a layer that should stay a thin projection.

The message falls back to binding ids when nothing resolves. A warning that fires but names nothing would be worse than one naming an internal identifier, and the fallback keeps the surface strictly better than before rather than conditionally worse.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_modelo_requires_data_inventory.py -m integration -n 0 -q
    3 passed in 24.42s

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_data_inventory_profile_keys.py src/cadrumo/entrypoints/cli/tests/test_modelo_requires_profile_grounding.py -n 0 -q
    5 passed in 10.98s

## Notes

This site already emitted through the typed notice channel, so only the schema-derivation half needed closing.
