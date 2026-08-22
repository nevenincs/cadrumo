---
tags:
  - '#audit'
  - '#issue-625-m369-exterior-e2e'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:0ed7fc9f9b15d607e28e3fe2be29a7257dfe9dcc3eca1c04ae3c8d14ca084e76'
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

### exterior-vat-kind-wire-token | high | General-rate invoice rows emit a token outside AEAT's closed vocabulary

Corrective commit `f16a4b280c92c5f91ec6470b6546e5fec7f5773b` adds the
invoice-owned enum handoff for T36901, but maps `IvaRateKind.GENERAL` to `"G"`
and `IvaRateKind.SUPER_REDUCED` to `"S"`. The bundled AEAT Modelo 369
presentation authority defines this field's complete vocabulary as `R` (reducido) and
`S` (estándar); it defines no `G`. The strengthened E2E then asserts the implementation's
`G`, so its independent parser only proves writer/registry agreement and enshrines an
officially invalid byte. A real Exterior general-rate invoice therefore exports `G` at
T36901 instead of the official standard-rate marker `S`. The same mapping also labels a
super-reduced tier as standard without an authority-backed collapse policy.

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
- For `exterior-vat-kind-wire-token`, derive the two-value M369 wire classification from
  the official `R`/`S` vocabulary: emit `S` for estándar/general and document and test the
  authority-backed treatment of every internal reduced tier. Add a negative parser or
  field-policy gate proving `G` is refused rather than merely round-tripped.
- Do not integrate the commit or close issue 625 until all HIGH and MEDIUM findings are resolved and the
  focused producer, M369 calculate/review/export, and parser gates pass together.

## Corrective resolution verification

Corrective commit `f16a4b280c92c5f91ec6470b6546e5fec7f5773b` resolves
`producer-vocabulary-exhaustiveness` structurally and resolves
`exterior-e2e-caller-shadow`. The filing producer now exposes an exhaustive ownership map
over every typed `FilingProducerKey`; the shared snapshot resolver separately asserts an
exact set equality over the keys it owns, without manufacturing `None` entries for
modelo-specific owners. Its value projection is otherwise unchanged, so non-M369 shared
producer behavior and required-field refusal remain intact. The formerly failing dedicated
vocabulary gate passes. Source enum values are merged into the trusted backend handoff and
an explicit caller value retains final precedence.

All four Exterior-quarter E2E cases now omit caller bindings entirely. Each invoice's
operation date is in the selected quarter while its issue date is in a later quarter, so
the devengo path must genuinely attribute the source for the asserted cuota to exist. The
test parses the real exported payload through the registry parser and proves T36901's year,
period type, ordinal, country, rate, base and cuota; proves mandatory T36903 is present;
proves absent corrections omit optional T36902; and proves a malformed/truncated T36902
prefix is refused. This closes the original MEDIUM finding.

Focused producer-vocabulary, M369, filing-renderer and fixed-width parser coverage produced
199 passes. One pre-existing M303 lexical-vocabulary assertion remains red because it
forbids the already-present `m303.annual_volume_nonzero` typed key; the corrective diff did
not introduce or alter that key. Ruff and structural checks remained clean. The new
`exterior-vat-kind-wire-token` HIGH keeps issue 625 unsafe to integrate or close.

## Final resolution verification

Final corrective commit `6b06bf981aa200a290bd11270b69087c7a2997d8` resolves
`exterior-vat-kind-wire-token`. The Exterior detail projector now maps the internal
general/estándar tier to official wire token `S` and the reduced tier to official wire
token `R`. A source sweep found no remaining `G` branch in the M369 projector or its E2E
authority. The map contains only those two admitted typed keys.

Before grouping, binding handoff, calculation persistence, review or export, every Exterior
services observation whose typed `IvaRateKind` is not `GENERAL` or `REDUCED` now raises
`AggregationValidationError`. The refusal context carries both the stable ledger id and
the unsupported typed rate-kind value. This covers `SUPER_REDUCED`, `ZERO`, `EXEMPT`, and
any future closed-enum member by the fail-closed complement rather than guessing an `R` or
`S` collapse. Targeted negative cases independently construct super-reduced and zero
observations and prove the typed refusal. The production resolver invokes the same helper
before returning any decimal or enum binding values, so no unsupported row can reach the
export boundary.

The four-quarter real-invoice E2E remains free of caller-supplied economic or enum values,
continues to force operation-date devengo against a later invoice date, and now independently
parses the emitted general-rate token as official `S`. Its mandatory T36901/T36903,
optional-absent T36902, and malformed-optional refusal assertions remain intact. Focused
M369 source, vocabulary, filing-renderer, and fixed-width parser coverage passed: 158 tests.
Ruff, `git diff --check`, and the scoped Vaultspec document gates passed. No new findings
were identified. All findings in this audit are resolved; issue 625 is safe to integrate
and close.
