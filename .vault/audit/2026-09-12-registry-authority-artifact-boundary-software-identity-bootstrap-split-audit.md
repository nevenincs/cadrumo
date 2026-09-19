---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:4daf0b4baa4983120fe06a734cf613d739be3f2bdc9c55d115672a32926c174a'
related:
  - '[[2026-09-12-registry-authority-artifact-boundary-tax-id-bootstrap-boundary-reference]]'
  - '[[2026-09-10-registry-authority-artifact-boundary-plan]]'
---
# `registry-authority-artifact-boundary` audit: `Software identity bootstrap split`

## Scope

Reviewed the atomic relocation of `AeatProgramIdentifier`, `AeatProductSoftwareEvidence`, and `AeatProductSoftwareIdentity` from `src/cadrumo/core/product_identity.py` to the canonical filing-domain module `src/cadrumo/domain/filing/software_identity.py`. The review covered dependency direction, sole-definition ownership, direct consumer migration across production, development tooling, and tests, removal of the displaced core surface, formatting and lint checks, focused contract tests, and clean-process import behavior. The accepted architecture decision, implementation plan, and tax-ID bootstrap reference were used as the governing intent.

The relocation matches the recommended first bootstrap cut. `core.product_identity` is standard-library-only, `core.resources.bundled_data` can resolve the authority artifact without importing Pydantic, tax-ID validation, registry authority/schema modules, or the filing software-identity module, and exact searches found neither a legacy core import nor a second definition. The filing-domain owner imports inward from core and all discovered consumers import directly from it. No compatibility re-export or package initializer forwarding surface exists.

## Findings

### tax-id-declaration-incompleteness | high | Independent tax-ID migration failure blocks the moved model's behavioral acceptance

The focused contract run completed nine tests and failed the positive `AeatProductSoftwareIdentity` construction because `SubjectTaxId` reached `validate_spanish_tax_id`, whose current `_tax_id_format_declarations()` mapping lacked `tax_id.country_prefix`. This was not a regression caused by the software-identity split: the pre-split model used the same `SubjectTaxId` field, and the moved validator/model structure was otherwise preserved. The failure belonged to the concurrent tax-ID authority/bootstrap migration described by the reference.

Resolution: resolved. Re-review confirmed that the incomplete four-key Python mapping has been removed, `_tax_id_format_declarations()` now resolves the complete governed fact, and the width lookup is deferred so importing the product/resource bootstrap does not eagerly validate a tax identifier. The exact two-module contract run now passes all ten tests; focused Ruff and diff checks also pass. This closes only the observed missing-declaration failure. It does not establish the reference's durable explicit-format injection boundary for candidate compilation and artifact decoding.

No critical, high, medium, or low finding remains in the relocation itself.

## Recommendations

Retain the current canonical filing-domain module, direct imports, deleted core definitions, and import-light product/resource boundary.

Continue the separate tax-ID bootstrap work described by the reference: replace the remaining outward core lookup with explicit typed format injection for candidate compilation and artifact decoding, without restoring a Python operative-value fallback. Treat the successful resource probe and focused split tests as proof of this first graph cut only. A clean import of `dev.registry.pipeline.cli` may still load tax-ID and registry authority/schema modules through other paths, so the later staged-decoder and explicit-format verification remains open.
