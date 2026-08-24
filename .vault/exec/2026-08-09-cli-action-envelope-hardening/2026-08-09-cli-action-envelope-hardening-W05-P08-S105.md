---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0bb93331eb45324aa6f208441daf20408b3bbe9fed300ea59b62f9585e289dc9'
step_id: 'S105'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Finish portal taxonomy and typed refusal propagation

## Scope

- `src/cadrumo/domain/portals/_errors.py`
- `src/cadrumo/domain/portals/_registry.py`
- `src/cadrumo/domain/portals/tests`
- `src/cadrumo/entrypoints/cli/_app_live_portals_cli.py`
- `src/cadrumo/entrypoints/cli/tests`

## Description

- Define a closed domain-owned portal failure classification without importing application policy.
- Classify two unknown-portal branches, malformed modelo input, and eight registry integrity invariants with redacted facts.
- Project the full portal error family only at the CLI boundary through the canonical no-action helper.
- Remove BadParameter flattening and authored integrity sentences.
- Add exact carrier, fact-expression, import-boundary, and live JSON envelope proofs.

## Outcome

The portal population is exactly two unknown-portal carriers, one malformed-modelo carrier, and eight integrity carriers. Unknown portal/modelo observations resolve to `OPERATOR_DECISION`; registry integrity failures resolve to `SAFETY`. The domain transports only its closed classification on the standard mixin and has no application import or verdict construction.

Both portal CLI verbs catch the complete `PortalRegistryError` family and the CLI owns the sole canonical projection. The show path no longer flattens typed failures into `BadParameter`. Domain tests pass 19 cases and CLI integrations pass 11; Ruff and diff checks pass. Independent review found no residue.

## Notes

- The earlier broad invoice/IVA/portal execution record was stale. Invoice and IVA reachability was split into S130 so this portal slice could close independently without hiding that remaining census.
