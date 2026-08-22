---
tags:
  - '#audit'
  - '#issue-625-m369-exterior-e2e'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:440bc63a1c1bf41bf3c895291b1b44d937a17d002508fb8ee1777314b4f6806e'
related: []
---



# `issue-625-m369-exterior-e2e` audit: `M369 Exterior end-to-end implementation review`

## Scope

Fresh-context review of implementation commit
`39755a9a7a245404dc96ffc8ba789988e54ab17b` against its parent and current
branch HEAD. The audit covered Exterior-period invoice attribution, preservation of the
canonical `EXT-1T` through `EXT-4T` typed tokens and text observations, the official
header/detail wire spellings, T3690/T36901/T36902 record occurrence semantics,
producer-key projection, optional fixed-width parsing, and the independence of the new
calculate-review-export proof. The bundled AEAT Modelo 369 presentation guide and record
design were used as the authority: T36901 is mandatory, T36902 is optional, T36903 is
mandatory, the header period is `1T` through `4T`, and detail rows carry type `T` plus
ordinal `1` through `4`. Production code was not modified.

## Findings

### producer-vocabulary-exhaustiveness | high | M369 unblocking deletes a global fail-closed producer invariant

`filing_producer_values` previously required its projected key set to equal the complete
typed `FilingProducerKey` vocabulary. The commit removes that check globally because the
enum contains modelo-specific keys outside this shared projection, but supplies neither
modelo-scoped producer dispatch nor an equivalent exhaustive ownership table. The existing
dedicated semantic-vocabulary gate now fails: the resolver mentions only its partial key
set while hundreds of typed producer identities remain unowned. Required fields can still
refuse when their value is absent, but optional producer-backed fields may now silently
render blank, and future enum additions no longer fail at this authority boundary. This is
not scoped to M369 and weakens every modelo using the shared filing producer.

### exterior-e2e-caller-shadow | medium | The new E2E does not prove invoice devengo or economic projection

The four-quarter E2E seeds one Exterior invoice, but also passes the exact three Decimal
binding values and two enum binding values that the invoice resolver is supposed to
produce. Caller bindings are the highest-precedence tier, so the calculation and exported
T36901 economic fields can remain green even if `project_oss_ioss_invoices_from_repositories`
filters the invoice out or produces different values. The test independently proves the
typed period token survives persistence/review and that the T3690 header spells `01`
through `04`, but its only economic assertion checks a caller-injected value. It also does
not parse the rendered payload or assert the mandatory T36901 occurrence and its detail
type/ordinal fields, leaving the claimed period-to-devengo and record-level end-to-end
authority tautological.

No additional defects were identified in the reviewed implementation. Exterior periods
are converted only for invoice date-span selection, leaving the canonical typed token
unchanged; text observation integrity now checks the string input channel; the header
mapping is scoped to Modelo 369 Exterior tokens; and T3690's forced occurrence is confined
to the three M369 schemas. T36902 is correctly declared optional. The optional-record
matcher now treats malformed literal decoding as a non-match, while the unchanged cursor
causes the following required-record read or trailing-byte gate to reject the malformed
bytes rather than accept them. Focused M369, renderer, registry, and fixed-width parser
tests passed: 144 tests. The dedicated producer-vocabulary suite produced 11 passes and
the one blocking failure described above. A broader focused run produced 166 passes plus
one pre-existing M303 lexical-vocabulary assertion unrelated to this diff.

## Recommendations

- For `producer-vocabulary-exhaustiveness`, preserve fail-closed exhaustive ownership while
  allowing modelo-specific producers: introduce an explicit exhaustive dispatch/ownership
  map (shared versus modelo-specific) and keep the existing vocabulary gate green. Do not
  make a global optional-blank fallback the M369 remedy.
- For `exterior-e2e-caller-shadow`, remove the caller values for fields owned by the
  OSS/IOSS invoice resolver. Assert the resolver-produced observation/binding provenance,
  parse the real exported bytes through the independent registry parser, and assert one
  mandatory T36901 with year, type `T`, ordinal `1` through `4`, and the invoice-derived
  economic values; separately prove absent corrections omit optional T36902 and malformed
  T36902 bytes are refused.
- Do not integrate the commit or close issue 625 until both findings are resolved and the
  focused producer, M369 calculate/review/export, and parser gates pass together.
