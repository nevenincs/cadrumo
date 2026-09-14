---
tags:
  - '#adr'
  - '#canonical-exception-remediation'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:433a5d10e8dbb0121350efb3bc7d562be3eaa24f4364d0b90b269cfaf71d92be'
related:
  - "[[2026-09-14-canonical-exception-remediation-migration-taxonomy-research]]"
  - "[[2026-09-14-canonical-exception-remediation-production-inventory-reference]]"
---

# `canonical-exception-remediation` adr: `Canonical registered exception ownership` | (**status:** `accepted`)

## Problem Statement

Cadrumo-owned failures rooted directly in built-in exception classes bypass the
canonical registry and cannot promise stable downstream envelopes. The campaign needs
one rule for ownership, ancestry, binding, and external translation.

## Considerations

- Exact source and descendant closure are grounded by
  `2026-09-14-canonical-exception-remediation-production-inventory-reference`.
- Registry, envelope, retryability, and external-boundary tradeoffs are grounded by
  `2026-09-14-canonical-exception-remediation-migration-taxonomy-research`.
- Canonical defining modules must preserve dependency direction and avoid facades.

## Considered options

- Keep rationale-backed built-in roots: rejected because acknowledgements do not create
  registry identities or envelopes.
- Centralize all exception definitions: rejected because it displaces ownership and
  creates cross-layer import coupling.
- Register package-owned exceptions and translate only at proven external protocols:
  accepted because it preserves ownership and supplies one machine-readable contract.

## Constraints

`CadrumoError` import-time binding requires a registry row before a migrated class is
imported. Every descendant must bind exactly once. Third-party callbacks may receive a
built-in translation only at their narrow protocol boundary. The existing registry and
envelope system is stable and already enforced by focused gates.

## Implementation

Keep concrete definitions in their owning modules. Replace direct built-in ancestry
with `CadrumoError`, `CoreError`, `CoreValidationError`, or an existing specific
registered root. Enroll exact fully qualified identities in layer registry shards,
provide localized message keys, update concrete catches, and remove rationale metadata.

## Rationale

This is the only option that simultaneously satisfies canonical ownership, stable
envelopes, non-facade imports, and narrow interoperability, as established by the two
related grounding records.

## Consequences

Downstream consumers receive stable codes and redaction-safe envelopes for all owned
failures. The migration is broad: registry enrollment and ancestry changes must land in
coherent batches, and catches that formerly depended on built-in polymorphism require
focused review. Future bare roots become gate failures rather than rationale entries.
