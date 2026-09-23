---
tags:
  - '#adr'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:e4670fd33085a292a7691aab03a467dad360f5f6fc7984f270e65a399bdaa200'
related:
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - "[[2026-09-21-assets-core-lifecycle-and-integration-research]]"
---

# `assets-core` adr: `IRPF asset cost-basis stages` | (**status:** `accepted`)

## Problem Statement

The accepted lifecycle ADR accidentally narrows every stored cost to a
whole-property basis. That wording conflicts with the authorized amendment,
which requires each cost to state whether it is whole-property,
taxpayer-owned, or already business-allocated. The implementation needs this
distinction before its persisted contract is frozen.

## Considerations

- Allocation must be applied exactly once; existing ledger `business_pct` is
  evidence, not an implicit second multiplier.
- Construction/land and office/total-area evidence applies to mixed-use real
  property, not to every material or intangible asset.
- Unsupported ownership treatment must remain an explicit refusal.

## Considered options

### Require whole-property facts for every asset

Rejected. It preserves home-allocation evidence but makes equipment and
intangibles depend on inapplicable land and area facts.

### Accept one untyped cost and infer its allocation stage

Rejected. The same amount could be multiplied twice or accepted without a
required legal share.

### Store an explicit cost-basis stage with stage-specific evidence

Accepted. A discriminated contract makes the multiplier history visible and
permits each stage to validate only its relevant evidence.

## Constraints

- The acquisition remains one canonical transaction and invoice relationship.
- Spousal-community real-property allocation remains unsupported until its
  authority is enrolled.
- Mixed-use real property must use the `whole_property` stage. The other stages
  cannot be used to bypass construction, land, ownership, or area evidence.
- This amendment changes only the cost-basis stage; all other lifecycle ADR
  commitments remain accepted.

## Implementation

Every asset revision carries exactly one typed cost allocation:

- `whole_property` records total cost, construction, land, ownership treatment,
  and business-use area. The schedule excludes land and applies the supported
  ownership share and area ratio once.
- `taxpayer_owned` records the taxpayer-owned cost and an explicit business-use
  share, applied once. It does not accept whole-property ownership evidence and
  is limited to assets that are not mixed-use real property.
- `business_allocated` records a cost already reduced to the deductible
  business basis and applies no further percentage. It is limited to assets
  that are not mixed-use real property and records the provenance of the prior
  allocation.

The acquisition transaction's allocation fields are checked for consistency
and provenance but are never silently multiplied into any of these bases.
Equipment and intangibles can use the latter two stages without synthetic land
or area facts. Whole-property spousal-community treatment refuses until a
dedicated authority resolver exists.

## Rationale

The discriminated stage is the only option that both exposes whether a
percentage has already been consumed and supports non-property assets without
fabricated evidence. It closes the conflict identified during P02 review while
preserving the accepted home-allocation refusal boundaries.

## Consequences

- Ordinary material and intangible assets can establish a lawful basis without
  home-specific fields.
- Persisted revisions disclose exactly where ownership and business allocation
  occurred, so resolvers can detect a second application.
- Import and UI operations must ask for the basis stage rather than guessing it.
- Changing the stage or its evidence creates a superseding asset revision and
  invalidates dependent unfiled forecasts or claims.
