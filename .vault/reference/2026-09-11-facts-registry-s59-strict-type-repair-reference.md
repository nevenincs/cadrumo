---
tags:
  - '#reference'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:ef5eb0fb89256b32179e9ac6585c811e5643354b074382c5e65906511fad5a70'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` reference: `s59 strict type repair`

Strict production type checking after legacy-provider deletion finds 67 facts-registry diagnostics. The failure is live and attributable to direct projections over the closed `FactAtom` payload union, rather than to an obsolete provider. The governing facts ADR requires explicit typed payload and provenance handling and rejects opaque dictionaries, federation, and compatibility adapters.

## Summary

`facts/schema.py` defines `FactAtom` as `str | int | Decimal | bool | date`; a fact identifier does not statically narrow a `GovernedFact` payload. The existing scalar-resolution path in `renta/maritime_exemption.py` supplies the project pattern: check the resolved family and exact atom type, then refuse an incompatible value.

Apply that same fail-closed boundary to categories, IVA rate, and recargo projections. Verify mapping payload family, string keys, exact selector and field types, and required temporal citation values before construction. Do not coerce with `str()` or decimal parsing; malformed compiled facts must raise the existing domain validation error. In `facts/schema.py`, preserve Pydantic rejection by validating each entity-set member as a string rather than filtering or coercing it.

Remove the redundant holiday projection cache because a `ValidatedRegistryAuthority` is unhashable and `bundled_authority()` already provides the authority/fingerprint cache. Retain publication-event refusal behavior. In facts quality analysis, establish typed TOML mapping and regex-group shapes before iteration. In the convenio compiler, validate the country selector is a string before normalisation. In fact validation, treat a source with no `applies_from` as non-covering so legal applicability remains fail-closed.

The involved campaign files are `src/cadrumo/domain/calculations/registry/facts/schema.py`, `src/cadrumo/domain/categories/registry.py`, `src/cadrumo/domain/deadlines/festivos.py`, `src/cadrumo/domain/iva/rates.py`, `src/cadrumo/domain/iva/recargo_equivalencia.py`, `dev/registry/analysis/facts_catalogue_quality.py`, `dev/registry/compiler/convenio.py`, and `dev/registry/compiler/fact_validation.py`. The quality analysis and convenio compiler are concurrently modified in the authority-artifact worktree migration; re-read them immediately before editing and isolate the factual type repair in a temporary index commit.
