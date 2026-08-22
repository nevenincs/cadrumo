---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:6f9bd186aa5e2633987a12db544bbb04837c239003b5862075dfd8496ca470fa'
related:
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-w01-p01-s138-review-audit]]"
---

# `source-casilla-integration` audit: `W01.P01.S139 persisted source reference parity review`

## Scope

Reviewed commit `21934675ce` against the accepted source-casilla integration
ADR, `W01.P01.S139`, and the HIGH persisted-reference-domain finding in the
S138 review at commit `3c6d8b643d`. The review compared both connectivity
source-reference fields directly with authoritative
`CalculationSourceRef.source_ref`, inspected the production invoice,
withholding, and foreign-asset emitters, and checked constraint width,
whitespace, case, punctuation, Unicode, exact equality, API exposure, and the
absence of normalization or compatibility paths.

The focused core suite passes 45 tests and Ruff passes both changed Python
files. Direct parity probes show both models accept whitespace-only strings,
leading and trailing whitespace, punctuation, composed and decomposed Unicode,
emoji, and 256 Unicode code points unchanged; both reject empty strings and 257
code points. Their generated schemas both declare only `minLength: 1`,
`maxLength: 256`, and `type: string` for this field. The private purpose type is
not exported through the core facade, and the existing cross-component and
persisted-identity drift tests retain literal string equality. No production or
test source was modified by this review.

## Findings

### representative-foreign-asset-shape | medium | The claimed foreign-asset positive is not emitted by the live resolver

The new positive table includes `foreign_asset:Opaque Asset Ref #1`, but
`ForeignAssetsAggregationSourceResolver` does not prefix persisted provenance
with its owned binding source `foreign_asset`. It emits
`{observation.source_kind.value}:{observation.source_object_id}`; the admitted
source kinds are `ledger_transaction`, `purchase_invoice_evidence`,
`payable_invoice`, and `collectible_invoice`. A production fixture already
demonstrates an external source object id of `INV-2025-0007`, so a faithful
example is such as `payable_invoice:INV-2025-0007`. The current string still
proves that spaces and uppercase characters survive the new opaque constraint,
and the invoice and withholding entries are real emitter grammars, so this does
not reopen the corrected contract defect. It does mean the test's named set of
representative shapes is only partly production-grounded.

### persisted-reference-parity | low | The HIGH domain mismatch is closed without a shim or public type leak

Both `SourceConnectivityConnectionIdentity.source_ref` and
`SourceConnectivityEncryptedRevisionProof.persisted_source_identity` now use a
private purpose-named annotation whose Pydantic constraint shape exactly
matches `CalculationSourceRef.source_ref`. It does not strip, case-fold, parse,
prefix, alias, or normalize. The encrypted proof still compares the strings
literally, so case, punctuation, surrounding whitespace, and Unicode
normalization-form drift remain observable and are refused. The old
`source_object_id` compatibility surface remains absent, while `resolver_id`
continues to model resolver ownership independently. There are no HIGH or
CRITICAL findings in S139; the S138 blocking source-reference defect is closed.

## Recommendations

- Replace the synthetic `foreign_asset:` positive with a value constructed from
  the live foreign-asset resolver grammar, including an uppercase, punctuated,
  or spaced external `source_object_id`. Keep the current invoice, withholding,
  surrounding-whitespace, and 256-character boundary cases.
- S137 is not blocked by S139: proceed under the corrected persisted-reference
  contract. Retain literal equality and the private purpose type; do not add a
  normalization, parser, raw-object alias, or compatibility shim.
