---
tags:
  - '#research'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d75a36135218f134e0e0c3f306f301416546652f1fd7a1e1992a91d1cc472ce7'
related: []
---

# `facts-registry` research: `Authority plumbing and migration gaps`

The safest integration seam is a sibling governed-fact catalogue owned and
compiled by `ValidatedRegistryAuthority`, attached to `RegistryCatalogues`
rather than `ModeloRevision`. Correctness depends on enrolling every provider
in compilation, validation, fingerprints, cache identity, reset behavior, and
directory ownership from a single declaration. Centralizing only the public
method while retaining independent loader semantics would not meet the goal.

## Findings

### RegistryCatalogues is the narrow integration seam

`ValidatedRegistryAuthority` owns modelos and catalogues at
`src/cadrumo/domain/calculations/registry/authority.py:433`. Authority
construction already compiles treaties and the annual Modelo 303 Orden after
the core tree load at `src/cadrumo/domain/calculations/registry/authority.py:1093`.
A first facts implementation can follow this seam: compile providers after
legal/source catalogues exist, attach a `GovernedFactCatalogue`, then validate
the full authority without changing modelo loading.

### Provider enrollment must own identity as well as compilation

Registry identity currently concatenates core, treaty, and annual-Orden
/blocking collectors explicitly at
`src/cadrumo/domain/calculations/registry/authority.py:67`. The base fingerprint
walk covers authorization, legal, modelos, and profile schema but omits current
IVA, category, and calendar directories at
`src/cadrumo/domain/calculations/registry/_loader_internals.py:977`. A single
provider registry should derive compiler enrollment, fingerprint collection,
validation, reset hooks, and directory ownership. A top-level census should
refuse an unowned governed directory.

### Validation memoization is a correctness trap

`RegistryValidator` retains legal, source, and supported-year inputs at
`src/cadrumo/domain/calculations/registry/_validate.py:78`; its cache keys do not
know about a future facts facet. Registry validation memoization likewise keys
existing catalogue identities at
`src/cadrumo/domain/calculations/registry/_validation_memoization.py:19`.
Adding facts to the data model without adding their identity to both memo
layers could reuse a green verdict for a different fact catalogue.

### One public authority needs typed queries and provenance results

A free-form selector mapping would turn spelling errors into false absence and
make precedence unverifiable. The candidate API is a closed union of
registry-owned query models dispatched by fact family. Resolution returns a
closed `ResolvedGovernedFact` union containing the typed payload, fact and
variant identities, matched selector and temporal window, references and
citations, review state, ownership, and authority digest. Raw scalar getters
are noncanonical because they discard the evidence chain.

### Cycles constrain provider schemas

Registry binding code imports IVA domain types at
`src/cadrumo/domain/calculations/registry/ledger_iva_bindings.py:19`, while IVA
loaders import registry grounding at `src/cadrumo/domain/iva/rates.py:194`.
Fact schemas must therefore own registry-level tokens and core primitives
without importing IVA, renta, or application modules. Domain adapters translate
resolved facts outward. Resolution must occur at composition or request
boundaries, never at module import.

### Migration can centralize authority before normalizing every file

Existing data-backed families can first register provider adapters under the
authority while retaining typed payloads and file locations. Consumers then
stop opening TOML or calling domain loaders. A later bounded step normalizes
authoring envelopes where appropriate and deletes the adapters. Temporary
adapter state needs an explicit closure inventory so it cannot become the new
permanent fragmentation.

Provider-local caches should be removed during migration. If any remain,
`src/cadrumo/domain/calculations/registry/authority.py:1038` must reset them
under the same barrier as authority generations.

## Sources

- `src/cadrumo/domain/calculations/registry/authority.py:67`
- `src/cadrumo/domain/calculations/registry/authority.py:433`
- `src/cadrumo/domain/calculations/registry/authority.py:1038`
- `src/cadrumo/domain/calculations/registry/authority.py:1093`
- `src/cadrumo/domain/calculations/registry/_loader_internals.py:977`
- `src/cadrumo/domain/calculations/registry/_validate.py:78`
- `src/cadrumo/domain/calculations/registry/_validation_memoization.py:19`
- `src/cadrumo/domain/calculations/registry/ledger_iva_bindings.py:19`
- `src/cadrumo/domain/iva/rates.py:194`
