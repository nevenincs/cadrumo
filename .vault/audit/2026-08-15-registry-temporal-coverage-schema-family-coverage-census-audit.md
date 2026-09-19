---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-15'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8f2ae0c2c72281fdf7ecbb52b3a8dd82be1b5de81824f7dbc383335020f6b47d'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
---

# `registry-temporal-coverage` audit: `schema family coverage census and the three grounded discriminators`

## Scope

Historical census of schema-family coverage across the registry corpus, the
grade-refusal handover assumption, and the export-layout discriminator. The
remaining detail is deliberately retained in the chronological Context section
below; this document is not a current-head release review.

## Findings

### historical-census-context | low | The detailed 2026-08-15 findings were preserved under Context

The census, corrected grade interpretation, discriminator analysis, and
measured counts below are historical discovery evidence. They must not be read
as a current completion claim or used in place of the later predicate review.

## Recommendations

Use the current predecessor-closure audit and live derived authority for release
decisions. Treat the historical census as grounding for its enrolled rows, not
as proof that any unchecked row has since been implemented.

## Context

Campaign resumed 2026-08-15 from the stood-down state at 161 refusals. This audit records the census that reframed the remaining work, two corrections to the handover, and the adjudication rubric governing schema-family coverage.

## The real size of the work

The refusal count is not the measure of completeness. Loading the compiled tree and running `build_revision_coverage_manifest` over every revision gives 73 modelos, 102 revisions, 19 schema families, and **955 blocked (family, revision) cells with zero revisions fully resolved**. Worst families: `projection_endpoints` 97/102, `casilla_continuidad_evolutions` 94, `export_layouts` 83, `relations` and `verification_predicates` 73 each.

A cell resolves either by being populated or by a `family_dispositions` declaration carrying a reason plus real `legal_refs` and `source_refs` (`_schema_family_coverage.py:141-185`). Only 12 of 102 revisions used that mechanism at all; `modelos/189/revisions/2025/revision.toml:29-43` and `modelos/145/revisions/2012-01-31-y-siguientes/revision.toml:24-56` are the worked examples.

## Correction 1: the grade block was never an attestation gap

The handover recorded 62 grade refusals as blocked on operator attestation. `_validate_authority_grade.py:58-62` rules otherwise in its own comment: the refusal is by design for a revision that intended to reach filing whose families do not yet back it, and reading the grade off present content would make the claim agree by construction and the check inert. A signature clears nothing. Only populating the families does, or a demotion that is substantively true.

Adjudicating all 34 modelos carrying the refusal produced exactly **one defensible demotion** (M185's `2003-2025` predecessor revision, matching the ruling already applied to `2025-y-siguientes`). The other 19 previously-unadjudicated modelos verified as genuine self-filed obligations: the payer-side withholding returns 111/115/123/216 and their annual summaries 180/190/193/296, M151 as the article 93 impatriate substitute for M100, M184 as the atribucion-de-rentas entity's own compliance obligation, M347/M349 as the business's own counterparty and intra-EU reporting. 62 to 61.

The conclusion that matters: the residual grade lines are a coverage-authoring problem, not over-claiming.

## Correction 2: the export-layout gate is grade-blind, and no disposition reaches it

`validate_export_exemption_declarations` (`_validate_export_exemption.py:242-285`) produces all 83 lines, reads `revision.export_layouts` directly and never consults `family_dispositions`. Its docstring is binding: there is no allowance, no allowlist and no per-modelo exemption, and the enumeration is the capability worklist which shrinks only when a layout is authored. M185 proves it empirically, already at `applicability` grade and still refusing.

`export_layouts` must therefore never be declared `not_applicable`. Doing so would satisfy the coverage row while leaving the real gate red.

## The three grounded discriminators

Of the 955 cells, 183 (19 percent) are honestly resolvable now; 772 are genuine authoring work. Only three families carry a discriminator strong enough to ground a declaration without per-revision legal research.

`casilla_continuidad_evolutions`, 75 cells. The revision has no strictly-earlier sibling, so there is nothing for a chain to be continuous with; `CasillaContinuidadEvolutionDefinition` structurally requires `from_revision != to_revision`. Proven with zero exceptions in either direction against the 8 populated rows. The remaining 19 blocked rows do have a predecessor and are real gaps.

`relations`, 12 cells. `validate_informative_class_invariant` (`_validate_revision_rules.py:41-67`) hard-refuses non-empty relations for `calculation_class == informative`, so the declaration states a registry-enforced truth. Same clause already grounds the `formulas` declarations on those same revisions.

`projection_endpoints`, 96 cells. `FilingProjectionRef` is a closed union of seven `m303_*` members. The worry that repeating-detail modelos such as 190/347/349 would be falsely declared was tested and refuted: `ExportRecordDefinition.repeat` supports `binding_rows` as a wholly independent repeating mechanism, live and populated for M131, M349 and M720. Repeating rows elsewhere are that family's job.

## The near-miss worth preserving

`verification_expectations` looked like a fourth discriminator: 100 percent of its 40 blocked rows have zero formulas. But six populated rows also have zero formulas and zero relations (036, 182, 184, 232 twice, 720), reconciling bound or manual casilla values against an external oracle with nothing calculated. Declaring on that clean-looking correlation would have produced exactly the false declaration that hides real work. Discriminator tested and falsified.

`extraction_profiles` was likewise refuted against M145. Eleven further families have no principled discriminator and need per-revision adjudication; `live_cross_references` has a real one but it lives outside the registry in AEAT's portal catalogue.

## Closed veins

`historical_exclusions.json` audited in full: all 100 remaining exclusions verified correct, no acquisition warranted. The handover's two-wrong-out-of-three sample was the two already fixed. `DR714_2022.xls` adjudicated as window wrong, bundling correct.

## Export-layout shape census

The 83 are far more concentrated than the count suggests. 58 revisions are tiny (1-15 casillas, 271 casillas total) and 34 of those carry no completeness manifest, so the per-casilla exemption scan does not fire and one grounded layout clears each. 12 are small, 6 medium, 6 large. M200 alone carries 3,250 of the roughly 5,500 casilla population. M303's five design epochs were already mapped in `dev/registry/mappings/modelo_303/` but had never been published against the real tree.
