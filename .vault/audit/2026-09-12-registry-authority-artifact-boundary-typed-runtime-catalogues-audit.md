---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:84279fb6b90d2424d70dfca0728b697eac82ebf497b4b03b18d94b410a6638fe'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
---
# `registry-authority-artifact-boundary` audit: `typed runtime catalogues`

## Scope

Reviewed the W04.P07.S13 implementation against the accepted immutable-runtime-publication ADR and its research grounding. The review covered the frozen runtime projection models, the `RegistryCatalogues.runtime` integration, compilation of IVA regulations and place-of-supply rules, country and Spanish-territory vocabulary, territory carve-outs, recargo bands and apoderamiento scopes, candidate-authority assembly, registry validation and validation-cache identity, v4 artifact reconstruction, and the focused compiler and artifact tests.

The typed projection is complete and immutable, compiler parsing is development-only, authored keys and identities are checked, recargo coverage and territory cycles fail closed, runtime legal references participate in registry validation, and the artifact writer/reader require a complete runtime catalogue. The supplied passing test and Ruff evidence is consistent with the reviewed implementation. The review identified the publication-grounding gap below, so S13 is not closable yet.

## Findings

### iva-verified-quotation-publication | high | Verified IVA quotations can be published without matching legal evidence

`PublishedIvaCitation` validates that a verified quotation is non-empty, and `RegistryValidator._validate_catalogues` validates that runtime legal-reference identifiers exist, but neither compilation nor full registry validation checks the quotation against the referenced legal evidence. The current regression in `dev/registry/compiler/tests/test_iva_runtime_catalogues.py` demonstrates the gap directly: it changes the quoted statutory rate from 21 percent to 25 percent, successfully calls `compile_validated_authority`, and only afterward observes that `legal_reference_quotes_corpus` returns false. This permits a candidate carrying a false `grounding = "verified"` claim to become the validated, publishable authority, contrary to the ADR requirement that development publication retain corpus conformance and that only a completely validated snapshot be published.

### iva-verified-quotation-publication-resolution | resolved | Full candidate validation refuses false verified quotations

Re-review confirmed `RegistryValidator._validate_catalogues` now checks every verified runtime IVA citation against the referenced anchored corpus whenever the development source root is present. It skips explicitly unresolved citations, avoids duplicating the existing unknown-reference diagnostic, and appends every ordinary quotation mismatch to the catalogue failure collection with both the regulation category and legal reference named. The check remains in the development compiler and adds no runtime source read. The inverted isolated mutation test now requires `compile_validated_authority` itself to refuse the false 25-percent quotation and proves an unaffected regulation is not spuriously named. The focused live regression passes. The `iva-verified-quotation-publication` finding is resolved, no further finding remains, and W04.P07.S13 is closable.

## Recommendations

- For `iva-verified-quotation-publication`, make full candidate validation check every verified runtime IVA citation quotation against its referenced legal evidence and source root, accumulating a named registry validation failure when it is absent. Invert the planted mutation test so `compile_validated_authority` itself refuses the candidate, while retaining positive coverage for the bundled catalogue and the explicit unresolved-citation disposition.
