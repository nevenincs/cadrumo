---
tags:
  - '#adr'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:eff7ccaecab64264454e3cdf9b934b459b8a510ddbde85d66d61655986fff227'
related:
  - "[[2026-09-09-facts-registry-discovery-blast-radius-research]]"
  - "[[2026-09-09-facts-registry-schema-persistence-research]]"
  - "[[2026-09-09-facts-registry-authority-plumbing-research]]"
  - "[[2026-09-09-facts-registry-dev-tooling-research]]"
---

# `facts-registry` adr: `Unify governed tax facts under a sibling registry catalogue` | (**status:** `accepted`)

## Problem Statement

Tax and legally governed values have multiple operative resolution paths. The
validated registry must become their sole authority without destabilising the
mature modelo/casilla registry. The discovery inventory remains intentionally
open, so the design must also support continued classification and enforceable
migration closure. Grounding:
`2026-09-09-facts-registry-discovery-blast-radius-research` and
`2026-09-09-facts-registry-schema-persistence-research`.

## Considerations

- The modelo/casilla schema, corpus, conformance denominator, export tooling,
  and revision lifecycle must remain unchanged. Grounding:
  `2026-09-09-facts-registry-dev-tooling-research`.
- Existing primitives suit scalar and bracket facts, but the domain also has
  mappings, sets, overrides, events, and multi-output bands. Grounding:
  `2026-09-09-facts-registry-schema-persistence-research`.
- Self-similarity belongs in identity, lifecycle, temporal, evidence, and
  ownership fields; unlike payload semantics must remain explicit. Grounding:
  `2026-09-09-facts-registry-schema-persistence-research`.
- Compilation, validation, fingerprints, memoisation, resets, and directory
  ownership must centralise with resolution. Grounding:
  `2026-09-09-facts-registry-authority-plumbing-research`.
- Resolution must be typed, exact, fail closed, and provenance-bearing.
  Grounding: `2026-09-09-facts-registry-authority-plumbing-research`.
- Static discovery cannot prove completeness or classify every candidate.
  Grounding: `2026-09-09-facts-registry-discovery-blast-radius-research`.

## Considered options

### Fold facts into `ModeloRevision`

This reuses mature revision machinery but invents modelo ownership and enrolls
unrelated values in casilla, filing, locale, export, and completeness duties.
Rejected because it violates the preservation boundary.

### Expand `LegalParameter` into the universal store

This reuses a global catalogue, but its string-oriented shape lacks the typed
payload, selectors, variants, citations, and executable resolution contract
required by the discovered families. Rejected as invasive and lossy.

### Flatten every fact into `ParameterDefinition`

This maximises surface uniformity but cannot preserve mappings, entity sets,
overrides, events, or multi-output bands without opaque dictionaries or
coercion. Rejected because it hides semantic divergence.

### Keep federated loaders behind an authority facade

This permits fast consumer convergence, but permanently preserves separate
compiler, validation, precedence, fingerprint, and cache semantics. Retained
only as an explicitly tracked migration technique.

### Add a sibling governed-fact catalogue

This preserves the modelo/casilla corpus, reuses registry-level rigor, and
centralises every authority responsibility through provider enrollment. This
is the proposed option.

## Constraints

- `ModeloRevision`, its TOML corpus, and modelo/casilla-specific tooling are
  outside the refactoring scope.
- Fact schemas may depend on stable registry-level primitives and
  `ValidatedRegistryAuthority`, but not outward domain modules.
- Resolution occurs at composition or request boundaries, never at import time.
- Every candidate is classified before enrollment as governed fact, product
  policy, implementation coverage, protocol constant, or extraction rule.
- One provider registration must own compilation, validation, directories,
  fingerprints, authority and memoisation identity, resets, and migration.
- Temporary adapters require explicit closure entries and retirement criteria.
- Overlap requires validated, deterministic, acyclic precedence; declaration
  order is never precedence.
- Evidence requirements are family-aware, not one universal cardinality rule.

## Implementation

Introduce a sibling `GovernedFactCatalogue` on `RegistryCatalogues`, compiled
and validated by `ValidatedRegistryAuthority` after legal and source catalogues.
The modelo/casilla loading path stays unchanged.

Persist normalised authored facts under
`src/cadrumo/_data/registry/aeat/facts/` as flat TOML fragments named
`NNNN-<stable-slug>.toml`. Each file owns one stable semantic fact and its
legally distinct variants. The prefix controls review order only. `fact_id`
excludes value, date, and modelo revision; immutable `variant_id` identifies a
legal redaction or interval. Filenames and declaration order never establish
runtime identity or precedence.

Use a fixed envelope for identity, closed family and payload kind, typed
selectors, one declared temporal axis and windows, variant-level evidence,
review state, authored/generated ownership, and explicit precedence edges.
Closed registry-owned payload families preserve scalar, bracket, mapping,
entity-set, override, event, and multi-output semantics. Adding a family
enrolls schema, compiler, query, validation, and tooling together.

A single provider registry declares directories, compilation, validation,
fingerprints, authority and memoisation identity, resets, and ownership.
Construction refuses unowned governed directories or partial enrollment.

Canonical resolution accepts a closed union of typed family queries and returns
a closed `ResolvedGovernedFact` union with payload, identities, matched
coordinates, temporal window, evidence, review state, ownership, and authority
digest. Absence, ambiguity, invalid coordinates, unsupported selectors, and
unresolved precedence are explicit; no canonical API returns a context-free
scalar.

Migration proceeds by bounded family slices. Existing data-backed families may
first register tracked adapters preserving their formats. Consumers then move
from constants, direct files, bespoke loaders, and raw scalars to authority
queries. Normalisation and adapter removal follow only when consumers,
duplicates, alternate paths, and local caches are closed.

Facts-specific tooling uses providers and resolved variants as its denominator.
Modelo/casilla tools remain unchanged. A report-only sentinel supports
continued discovery; enforceable gates prohibit retired imports, direct
governed-directory reads, unregistered loaders, and provenance-free results.

## Rationale

The sibling catalogue is the only option meeting both knockout criteria: the
modelo/casilla registry stays unchanged, while every other governed-value path
can converge on one authority and lifecycle.

The shared envelope supplies structural consistency without flattening distinct
legal semantics. Grounding:
`2026-09-09-facts-registry-schema-persistence-research`.

Attaching it to `RegistryCatalogues` uses the narrowest existing authority seam.
Provider-derived correctness prevents facade-only centralisation. Grounding:
`2026-09-09-facts-registry-authority-plumbing-research`.

A flat `facts/` family preserves one-concept review granularity without
equating facts to casillas or inventing premature taxonomy. Grounding:
`2026-09-09-facts-registry-schema-persistence-research`.

Separate fact gates preserve the trusted modelo denominator while applying its
resolved-surface and exhaustive-enrollment discipline to the new domain.
Grounding: `2026-09-09-facts-registry-dev-tooling-research`.

## Consequences

- Consumers gain one typed authority and evidence for every operative result.
- Modelo/casilla workflows do not absorb unrelated concepts.
- TOML facts share one lifecycle while payload differences remain visible.
- Provider enrollment, fingerprints, memoisation, resets, identity, and
  directory census become hard correctness requirements.
- Transitional adapters create enumerated debt that must close.
- Some Python values will remain outside the catalogue after classification.
- Continued discovery remains necessary; its sentinel cannot prove absence.
- New payload families require deliberate end-to-end enrollment, preventing ad
  hoc dictionaries and bespoke loaders from recreating divergent lanes.
