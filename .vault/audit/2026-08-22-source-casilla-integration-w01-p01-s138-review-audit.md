---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:84a776a331c4d60f4082feace8b17b3b688ffaf11f491e3a4be9776847b0718d'
related:
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-w01-p01-s136-review-audit]]"
---


# `source-casilla-integration` audit: `W01.P01.S138 persisted source reference review`

## Scope

Reviewed commit `55d952eb0b` against the accepted source-casilla integration
ADR, `W01.P01.S138`, and the blocking persisted-identity finding recorded by the
S136 review. The review compared the new core connection identity directly with
the production `CalculationSourceRef` persistence model and with resolver-authored
invoice, foreign-asset, withholding, transaction, and prorrata source references.
It also checked removal of the old raw-object field, exact equality behavior,
resolver-ownership separation, facade exposure, and the realism and bite of the
focused tests.

The focused core suite passes 38 tests and Ruff passes both changed Python files.
Repository search finds no `source_object_id` occurrence in the core connectivity
module or its tests, and the public facade exposes only the renamed canonical
model. A direct production-shape reproduction proves that
`CalculationSourceRef` accepts `percepcion:12345678Z:A:-`, emitted by the live
withholding resolver, while `SourceConnectivityConnectionIdentity` rejects that
same byte sequence. No production or test source was modified by this review.

## Findings

### persisted-reference-domain | high | The replacement field rejects valid persisted source references

`SourceConnectivityConnectionIdentity.source_ref` and
`SourceConnectivityEncryptedRevisionProof.persisted_source_identity` use
`_StableToken`: at most 160 characters and restricted to lowercase ASCII token
characters. The authoritative persisted field they claim to equal,
`CalculationSourceRef.source_ref`, accepts any non-empty string up to 256
characters. This is not merely a theoretical width mismatch. The live
withholding resolver emits a reference containing the operator's uppercase NIF,
clave, and subclave, for example `percepcion:12345678Z:A:-`; the persisted model
accepts it unchanged, but the new connectivity identity refuses it before the
authority can perform the exact join. Foreign-asset `source_object_id` is also
only non-empty rather than lower-token constrained, so the same disconnect can
occur there.

The equality validator itself is byte-exact and performs no normalization,
prefix stripping, or aliasing. However, equality cannot establish a production
contract when one side cannot represent the persisted side's legal value
domain. S134 would therefore be forced either to reject real connected rows or
to add the very normalization or reconstruction shim that S138 exists to
forbid. This remains a blocking identity-contract defect for S137 and S134.

### representative-shape-coverage | medium | The new examples do not exercise live invoice or foreign-asset acceptance

The positive fixture uses `collectible_invoice:inv-0001`, copied from an
encrypted repository test fixture, while live invoice resolvers emit
`invoice:{invoice_id}`. The foreign-asset string appears only as an intentionally
different connection or wrong namespace; no positive test constructs a
connection from a live foreign-asset resolver shape, including an unconstrained
source object id. The drift parameterization is mutation-sensitive to removal
of the equality check, and correctly proves raw, altered, and differently
namespaced strings are unequal. It does not prove that every value the real
persistence model can hold is admitted unchanged. That gap allowed the HIGH
domain mismatch above to pass all 38 tests.

### raw-object-removal-and-boundaries | low | The old field is removed and resolver ownership remains independent

The target core module and tests contain no `source_object_id`, alias,
deprecated property, fallback, or model-validation tolerance for the old shape.
The core facade exposes the canonical connection model without a parallel API.
The encrypted proof compares its asserted persisted identity directly with
`connection.source_ref`; resolver identity remains separately represented by
`resolver_id` and checked through source enrollment rather than inferred from
`CalculationSourceRef`, which correctly persists no resolver id. Core retains
its dependency-inverted authority protocol and imports no application or
persistence implementation.

## Recommendations

- Align both connectivity source-reference fields with the complete
  `CalculationSourceRef.source_ref` constraint shape: non-empty, at most 256
  characters, with no case or character normalization. Keep the equality check
  literal and do not introduce a raw-object alias, parser, namespace inference,
  or compatibility path.
- Add positive cases sourced from the live grammars, including
  `invoice:{invoice_id}`, a foreign-asset reference whose source object id is not
  a lowercase stable token, and the uppercase withholding reference demonstrated
  above. Retain the existing raw, altered, and cross-namespace negative cases so
  the equality gate continues to bite.
- Treat `persisted-reference-domain` as HIGH and block S137 and S134 until it is
  corrected and re-reviewed. The old S136 raw-object defect is removed in name,
  but production parity is not yet achieved.

