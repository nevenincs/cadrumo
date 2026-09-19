---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:3f36863ea97af60874a4e9ad8358777a25175ca2a23206db8f1e4e5c15f23264'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# `registry-authority-artifact-boundary` audit: `identifier enumeration tax domain review`

## Scope

Reviewed the W04.P06.S11 identifier-enumeration continuation against the accepted
immutable-runtime-publication ADR and its research grounding. The review covered the
assigned Modelo enumeration migrations, TaxDomain named-member migrations, authority-backed
conformance and documentation enrolment paths, MCP completion guidance, registry embed
detection and new-modelo contributor guidance. It also inspected the syntax-only
`Modelo` and `TaxDomain` definitions to verify that construction remains lexical and
performs no registry I/O.

Static searches found no remaining named `Modelo` or `TaxDomain` members, direct iteration
of either former enum, enum-member-map access, or `is TaxDomain(...)` expression in the
reviewed files. The migrated production enumeration paths derive their populations from
`ValidatedRegistryAuthority.modelos` or `bundled_authority().modelos`, and the embed census
requires an explicitly supplied authority-derived code set. The syntax-only constructors
remain pure string subclasses with lexical validation, stable `.value`, equality, hashing,
serialization and distinct runtime types.

Verification included scoped diff inspection, focused pattern searches, Ruff over the
seventeen reviewed files, and focused execution of the two registry test modules carrying
TaxDomain expectations. Ruff reported the undefined export recorded below. The focused
test run produced five failures caused directly by the residual identity comparisons
recorded below, plus twelve failures from independently visible revision-selection and
governed-fact validation state; three tests passed.

## Findings

### tax-domain-identity | medium | Two registry tests still require enum singleton identity

`dev/registry/tests/test_modelo_576_122_registry.py:72` and
`dev/registry/tests/test_modelo_490_604_763_registry.py:105` compare a hydrated
`ModeloDefinition.tax_domain` with a separately constructed `TaxDomain` by `is`. A
syntax-only string value type preserves value equality, not closed-enum singleton identity.
The focused test run confirms all five parameter cases fail (`'iedmt' is 'iedmt'`,
`'irpf' is 'irpf'`, `'idsd' is 'idsd'`, `'itf' is 'itf'`, and `'juego' is 'juego'`).
This is an enum-dependent caller left inside the stated migration scope and prevents S11
from claiming that the scoped caller migration is complete.

### regulatory-embeds-export | low | The embed validator exports an undefined public name

`dev/registry/validation/regulatory_embeds.py:55` includes `"modelo_codes"` in `__all__`,
but the module defines no symbol by that name. Ruff reports F822 for the reviewed file.
The authority-input change correctly makes `census` consume `known_modelo_codes`; the stale
export nevertheless leaves the module's declared public surface inconsistent and keeps the
scoped quality check red.

### tax-domain-identity-resolution | resolved | Value equality removes the residual enum assumption

Re-review confirmed `dev/registry/tests/test_modelo_576_122_registry.py:72` and
`dev/registry/tests/test_modelo_490_604_763_registry.py:105` now use `==`. A focused
search finds no remaining `modelo.tax_domain is domain` assertion. The combined registry
run proceeds beyond all five former identity failures; its remaining failures concern the
independently visible invalid shared registry sources and Modelo 576 temporal state. The
`tax-domain-identity` finding is resolved.

### regulatory-embeds-export-resolution | resolved | The public export list is internally consistent

Re-review confirmed `dev/registry/validation/regulatory_embeds.py` no longer exports the
undefined `modelo_codes` name. Scoped Ruff, formatting and diff checks pass. The
`regulatory-embeds-export` finding is resolved.

### detector-authority-input | resolved | Every synthetic census call declares its code authority

`dev/registry/tests/test_modelo_specific_embed_scan.py` defines the bounded synthetic
`_KNOWN_MODELO_CODES` fixture and passes it to every `census()` call. This preserves test
isolation while exercising the production contract that Modelo recognition requires an
explicit authority-derived code set. The focused file passes all fifteen collected tests;
the wider focused detector evidence supplied with the change passes twenty-one tests.
No new finding was identified.

## Recommendations

- For `tax-domain-identity`, replace both identity assertions with value equality and rerun
  the five affected parameter cases. Keep identity checks absent from syntax-only identifier
  callers; membership and enumeration must continue to come from authority.
- For `regulatory-embeds-export`, remove the stale `modelo_codes` entry from `__all__` (or
  define a deliberately supported API if one is genuinely required), then rerun scoped Ruff
  and the embed-scan tests.
