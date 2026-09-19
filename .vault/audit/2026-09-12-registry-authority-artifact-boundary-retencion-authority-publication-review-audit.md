---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:98ef6e8bb615fe42950ea468b4a4ff7cb9be5ca940f6708888714cda9d7a9bc3'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` audit: `retencion authority publication review`

## Scope

Reviewed the open `RetencionScheme` value migration across its core definition, application aggregation and advisory consumers, authority-backed withholding catalogue, all changed constructor call sites, authored treatment declaration, and facts-only authority publisher. The review checked exact wire-token preservation, syntax-only construction and Pydantic behavior, canonical imports, dated fail-closed resolution, absence of a closed Python fallback, and atomic/refusal behavior at publication. It was grounded in the accepted ADR, research, and current plan; current source and focused test evidence were treated as authoritative.

## Findings

### filing-scope-selection | high | Retenciones aggregation cannot resolve a revision for ordinary filing periods

`src/cadrumo/application/aggregation/retenciones.py:243` calls `RegistryQueryService.describe_modelo` with only `as_of=effective_date`. The query boundary correctly refuses point-in-time revision selection without filing-year scope, so the migrated aggregation path fails before it can apply the authority-backed scheme catalogue; the focused aggregation run reports 17 failures with `as_of point-in-time selection requires a filing-year-scoped query`. The caller already owns a complete `Period`, but `_aggregate_for_modelo` reduces it to `period.end_date` before `_registry_retenciones_catalogue`, losing `filing_year` and `code`. This is a production regression, not an expected unpublished-artifact failure.

### administrator-grounding | medium | Advisory grounding contract and selected rate facts disagree

`src/cadrumo/application/aggregation/_retencion_rate_advisory.py:252` obtains diagnostic references solely from `administrador_retencion_legal_refs`, whose selected scalar rate facts currently publish only `ley-35-2006:art-101`. The application test at `src/cadrumo/application/aggregation/tests/test_retencion_rate_advisory.py:172` and its explanatory contract require both that reference and `rd-439-2007:art-80`; the newly authored scheme/treatment mapping does carry Article 80, but `_administrador_refs` never resolves or combines that mapping provenance. The focused grounding test therefore fails after publication. Either the diagnostic is missing an authority-backed treatment reference or the test/documented legal claim is stale; it must not be repaired with a Python literal.

### filing-scope-selection-resolution | low | Filing-scope regression is resolved

Re-review confirms `_registry_retenciones_catalogue` now accepts the complete `Period` and calls `describe_modelo_for_scope` with its filing year, period code, and end date before resolving the dated mapping. The focused core, treatment, advisory, and aggregation run advances every caller past the former refusal: 46 tests pass, while the only two remaining failures are Modelo 123 source-applicability-window defects raised later during snapshot validation. No filing-scope finding remains.

### administrator-grounding-resolution | low | Scalar-rate provenance is now represented exactly

Re-review confirms the three administrator rate and threshold fact families publish `ley-35-2006:art-101` as their selected legal reference across their dated variants. `_administrador_refs` continues to derive its result from those scalar facts, and the corrected test now expects exactly that reference. The separate treatment mapping retains its broader references for fixed-versus-progressive scheme selection; unioning Article 80 into a rate diagnostic would conflate two authority claims. No administrator-grounding finding remains.

## Recommendations

For `filing-scope-selection`, retain the complete `Period` through `_registry_retenciones_catalogue` and validate the modelo with `describe_modelo_for_scope`, supplying `filing_year=period.filing_year`, `period=period.code`, and `as_of=period.end_date`. Keep the query service’s refusal guard intact and add focused coverage proving quarterly and annual aggregation select their scoped revisions.

For `administrator-grounding`, decide the legal provenance at the registry boundary: if Article 80 grounds the treatment asserted by the diagnostic, resolve and combine the selected treatment mapping’s legal references (or add properly sourced Article 80 grounding to the owning scalar facts); otherwise remove the unsupported expectation and prose. In either case, keep diagnostic references wholly authority-derived and add a focused test covering the selected dated variant.

Both recommendations are satisfied by the reviewed changes. The two Modelo 123 source-window failures are outside these findings and should remain fail-closed until their source applicability is corrected.
