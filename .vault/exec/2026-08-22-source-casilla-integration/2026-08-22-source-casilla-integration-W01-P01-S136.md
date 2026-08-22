---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:51a3c80cd4951e5ff00a547cfd394cdea9fd5e76d62207324e99e973948d8ddb'
step_id: 'S136'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# extend connected authority validation with the full encrypted-revision proof and refuse persisted identity or fingerprint drift

## Scope

- `src/cadrumo/core`

## Description

- Join the persisted source identity to the connection's canonical source object identity.
- Pass the complete encrypted-revision proof through the live authority seam.
- Refuse live encrypted provenance that differs by source identity or fingerprint.
- Preserve core dependency independence and the existing resolver-ownership boundary.

## Outcome

Connected census admission now requires an application authority to verify the
complete encrypted-revision proof. A caller cannot substitute a different
persisted source identity at model construction, and an authoritative read can
reject fingerprint drift before a connected disposition is admitted.

## Notes

The persisted calculation provenance intentionally does not carry a resolver
identifier. Resolver ownership therefore remains a separate live-enrollment
decision and was not inferred from encrypted revision storage in this step.
