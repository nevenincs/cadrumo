---
tags:
  - '#audit'
  - '#registry-fact-relocation-retirement'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:3e7b2a8a77e1dbea7bb951e5deef4c841d3301ecc3fc43d806fbcefe0b518029'
related: []
---



# `registry-fact-relocation-retirement` audit: remove the completed campaign surface

## Scope

Audited removal of the completed fact-relocation campaign command, implementation, import-load enrollment, workflow reference, and source labels. The current governed-fact compiler, provider declarations, authority validation, publication, registry health, and runtime artifact readers remain intact.

## Findings

No implementation findings. Static closure found no remaining live `check-facts`, `fact-relocation`, or `dev.registry.facts` reference outside historical Vault records. The regenerated import-load metadata excludes the deleted module. No compatibility alias or replacement facts-only publication path was introduced.

## Recommendations

Use the full authority publisher and `check-registry` for registry/fact publication validity. Keep historical campaign evidence in Vault records only; do not restore its executable command or temporary-manifest dependency.
