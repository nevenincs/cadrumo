---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:42fc7889a83cd9d8f6c3178fb3719f0da032d3556eca6587853b31abc5638f93'
step_id: 'S93'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# retain the M232 related-party-operation deferral until its carrier preserves direction and relationship type, a secure source owner exists, and S94 proves the full encrypted row route

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`
- `dev/source_connectivity/tests/test_m232_deferral.py`

## Description

- Record the M232 related-party row family as a terminal `ingress_blocked` census disposition.
- Bind the deferral to its campaign owner, expiry, and named follow-up action.
- Keep reopening conditional on durable direction, relationship type, stable identity, secure ingress, and S94 encrypted-route proof.

## Outcome

The M232 row remains disconnected. The census and no-mock gate make its owner, expiry, terminal disposition, and reopening predicate machine-checkable; no resolver, M232 calculation semantics, or connected claim was added.

## Notes

The original tracking record omitted the bounded follow-up owner. Independent review restored that required field and strengthened the gate without changing the deferral's scope or implementation boundary.
