---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0bb99e7db1490ea0b47de5b4487d4fc50014ffd362115b6aaa2cad95c51fd4cd'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `s168 inventory projection review`

## Scope

Independent review of S168 inventory projection arithmetic, complete acquisition-cost authority, closing-authority composition, continuity and conflict provenance, deterministic ordering, and fail-closed result construction.

## Findings

### s168-inventory-projection-review | high | resolved projection provenance could be forged

Cross-field validation now binds the selected authority to its authoritative value and requires physical identity, value, fingerprint, and retained conflict state to agree with the projection and its canonical resolution. Divergent physical values require a conflict under either authority selection.

### s168-inventory-projection-review | high | resolved nonzero acquisition totals lacked proof identity

A nonzero complete acquisition total now requires at least one acquisition fingerprint, and fingerprints must be unique because movement identity is part of the canonical acquisition fingerprint. Empty and duplicate mutations refuse.

### s168-inventory-projection-review | medium | resolved incidental movement order changed provenance

Purchase totals and fingerprints now use the same canonical movement ordering as valuation. Reordered semantically identical ledgers produce identical acquisition provenance.

### s168-inventory-projection-review | high | resolved closing decision acquired a rival mutable value field

The accidental physical-value field was removed from `InventoryClosingAuthorityDecision`; physical values remain exclusively in the canonical observation, resolution, and projection provenance contracts.

### s168-inventory-projection-review | high | resolved correlated substitutions could remint a public checksum

The result now retains its strict canonical source as runtime-only state and re-derives every flattened value and provenance identity from that source. Correlated authority, observation, continuity, acquisition, and output substitutions refuse even after the public envelope fingerprint is reminted; a distinct internally consistent source still projects successfully with a distinct identity.

### s168-inventory-projection-review | high | resolved retained source serialization exposed protected facts

The retained ledger is excluded from serialization and representation. Safe projection JSON carries only canonical source and projection fingerprints and omits all acquisition, authority-decision, physical-observation, and continuity evidence references, content digests, actor, and command canaries. Serialized projections are explicitly non-rehydratable without the runtime source.

### s168-inventory-projection-review | medium | resolved derivation bypassed typed strict validation

The derivation is a frozen typed contract rather than an untyped mapping, and the public producer returns a normally validated projection. A private temporary construction exists only to compute the circular envelope fingerprint and is never returned.

### s168-inventory-projection-review | medium | resolved canonical source identity drift

Canonical source identity sorts movements and nested evidence, refuses duplicate movement identifiers, and canonicalizes every Decimal-bearing opening-layer and movement field. Reordering and scale-equivalent mutations preserve the source and projection fingerprints.

### s168-inventory-projection-review | pass | final complete inventory projection is coherent

Both final reviews reported zero critical, high, medium, or low findings. Fifty-three inventory-domain tests, Ruff, the type checker, and diff hygiene were clean.

## Recommendations

Proceed to the inventory resolver using this projection as the sole source of 0177, 0181, and 0182. Do not reconstruct acquisition, authority, continuity, or sign-split semantics in the registry layer.
