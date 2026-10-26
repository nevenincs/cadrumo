---
tags:
  - '#adr'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:997b8626203c45c773b01dfbcc1c304c290e41770256870a603c877bd3e4607a'
related:
  - "[[2026-09-10-data-provenance-consolidation-lane-inventory-research]]"
  - "[[2026-09-10-data-provenance-consolidation-live-lane-map-reference]]"
  - "[[2026-09-09-registry-generator-adr]]"
---

# `data-provenance-consolidation` adr: `compile artifact identity and role; preserve specialized authority` | (**status:** `accepted`)

## Problem Statement

`_data` has overlapping identity, acquisition, derivation, semantic-evidence, and documentation lanes. Filing already has a strong typed authority path, but acquisition and discovery reconstruct the same facts from manifests, prose, exceptions, and filename rules. The broad coverage sweep consequently treats unlike evidence as equivalent success. This ADR decides how to centralize shared facts without expanding filing-runtime authority or flattening distinct quality properties. Grounding: `2026-09-10-data-provenance-consolidation-lane-inventory-research` and `2026-09-10-data-provenance-consolidation-live-lane-map-reference`.

## Considerations

- `SourceReference` and `ValidatedRegistryAuthority` are canonical for filing and calculation consumers.
- Record-design manifests are acquisition/package projections, not runtime authority.
- The seven off-host BOE rows already align with manifests and registry sources; the extra file duplicates classification rather than closing a coverage gap.
- Prose remains valuable documentation but cannot prove immutable source identity.
- Derivation freshness, export reproduction, normative-text authenticity, and calculation/oracle correctness are independent properties.
- Each artifact inside an owning evidence boundary needs an explicit, reviewable role; registry configuration remains specialized authority rather than a catalog artifact.

## Considered options

**Retain independent lanes and refine local exceptions.** Rejected. It preserves duplicate classification and independent path interpretation.

**Make `SourceReference` the universal raw-file inventory.** Rejected. It would expand the filing authority boundary to unrelated bundled data.

**Adopt prose or manifests as universal authority.** Rejected. Prose is not immutable identity and manifests are not runtime regulatory authority.

**Compile a typed, read-only artifact catalog while retaining specialized authorities and gates.** Accepted.

## Constraints

- Registry consumers continue to use `ValidatedRegistryAuthority`, never raw catalog files.
- `SourceReference` retains source kind, evidence tier, applicability, review, and design-authority semantics.
- Derived artifacts name their input identity/digest and producer; they do not impersonate official acquisition.
- Diagnostics remain typed: missing or malformed identity, conflicting declaration, orphaned target, unknown file, stale derivative, and broken registry binding.
- No lane is removed until its catalog-backed successor has isolated temporary-tree detector teeth.
- Existing advisory analyses remain advisory unless explicitly promoted.

## Implementation

Introduce a typed, read-only `ArtifactIdentity` catalog/compiler keyed by canonical bundled relative path. The compiler remains caller-bounded: authority publication supplies the registry-cited evidence boundary and record-design sync supplies its acquisition boundary. A record carries immutable acquisition identity and exactly one role: official artifact, derived artifact, semantic annotation, disposition, or explicitly non-authoritative fixture.

Existing manifests, off-host rows, manual manifests, and e-invoice records become validated adapters or generated projections. Registry sources bind catalog identity while retaining their regulatory semantics. The compiler becomes the shared resolver for payload role, normalized location, identity alignment, and coverage diagnostics.

The broad three-way coverage gate, duplicated metadata/derivative classifiers, the basename-only off-host assertion, and sync-only extracted-sidecar authority route are replaced only after catalog-backed equivalents prove the same failures. `PROVENANCE.md` remains a documentation-quality surface, not filing-grade identity.

## Rationale

Artifact identity and role are shared facts currently reconstructed by multiple consumers. Compiling them once removes drift while preserving the boundaries that carry distinct meaning. The off-host correction confirms the right remedy is exact catalog alignment, not another provenance lane. Grounding: `2026-09-10-data-provenance-consolidation-lane-inventory-research` and `2026-09-10-data-provenance-consolidation-live-lane-map-reference`.

## Consequences

The project gains one canonical resolver for bundled identity and role within each owning evidence boundary, plus explicit diagnostics for unclassified, conflicting, stale, or orphaned data. Registry authority remains filing-specific and byte-verified; the catalog does not become a universal configuration inventory. Specialized derivation and correctness gates remain intact. Migration must be staged, because every deletion requires replacement evidence.
