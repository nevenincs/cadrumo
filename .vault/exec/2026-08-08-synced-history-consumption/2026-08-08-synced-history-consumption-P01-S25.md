---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:66f69b8d1bccbd424a905733a2b03240fe39f93fa187138b122b3a4a353d9335'
step_id: 'S25'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Group carry advisories by source requirement rather than by relation, because one missing filing currently produces up to ten lines. Measured on Modelo 190 for 2025 with an empty store and a long-running filer: ten advisories, one per annual-summary relation, every one of them naming the same absent Modelo 111 source. Ten distinct facts are genuinely missing - trabajo dinerario, trabajo especie, actividades, premios, ganancias, derechos de imagen, retenciones - but there is ONE root cause and one remedy, so ten lines is redundancy rather than information. The remedy is scoping the presentation, never removing the signal. Gate: a single absent source filing produces one advisory naming the source and enumerating the affected facts, the affected relation or binding ids remain machine-readable rather than being collapsed into prose, and the Modelo 190 case is measured again after the change to show the reduction

## Scope

- `src/cadrumo/application/calculations/_relation_prefill.py`

## Description

- Add a structured `relation_ids: tuple[RelationId, ...]` field to
  `CalculationSourceDiagnostic`, carrying the full grouped membership while
  the pre-existing `relation_id` stays the lowest-sorted member for
  backward compatibility.
- Rewrite `_unresolved_relation_diagnostics` to group unresolved,
  requirement-backed relations by `(source_modelo, filing_year, periods)`
  before emitting one diagnostic per group, instead of one per relation. An
  unresolved relation with no scoped requirement (an orphan) has no source
  coordinate to group by and keeps its own diagnostic.
- Order the grouped message's content so the source, the count and the
  affected facts (the source casilla ids) come first and the trailing
  relation-id listing comes last, so the field's length-capped elision (a
  pre-existing, deliberately visible cap on system-assembled prose) cuts
  the redundant tail rather than the facts — the complete, un-elided
  relation membership already lives in the structured `relation_ids` field.
- Add pure-function coverage pinning the grouping property directly against
  hand-built `RegistryFoldRequirement` rows (ten relations sharing one
  absent source collapse to one diagnostic; two different source
  coordinates stay two diagnostics; an orphan relation stays its own
  diagnostic; a singular group still populates both id fields).
- Add a real-registry measurement test resolving the actual Modelo 190
  2025 annual snapshot against an empty local store through
  `RelationPrefillSourceResolver`, reproducing the row's own measured case
  and asserting the ten Modelo 111-sourced relations now produce exactly
  one diagnostic.

## Outcome

`_unresolved_relation_diagnostics` groups by source coordinate; the real
Modelo 190/2025 measurement against an empty store now produces exactly one
diagnostic naming the absent Modelo 111 1T-4T filing (previously ten, one
per relation), with all ten relation ids present in the diagnostic's
`relation_ids` field regardless of message length. The grouped message
itself fits all ten affected casilla facts before any elision and only
elides into the redundant trailing relation-id restatement.

Verification: the new pure-function test file (4 passed) and the new real-
registry Modelo 190 measurement test (13 passed in the enclosing file) are
green; `ruff check`, `ruff format --check`, `ty check` and `basedpyright`
are clean on every touched file. The broader
`application/calculations/tests/` suite (38 pre-existing failures) and
`application/aggregation/tests/` suite (5 pre-existing failures) were run
before and after this change; the failure sets are unchanged (confirmed by
diffing the sorted `FAILED` lines, not by re-reading them) and none of the
failures' stack traces touch `_relation_prefill.py`,
`_unresolved_relation_diagnostics`, or `CalculationSourceDiagnostic` — they
trace to unrelated concurrent registry and IVA-deduction work in this
shared tree (an `AggregationCaptureKind` enum-strictness mismatch, a
profile-binding source-refs fingerprint divergence, an IVA deduction-
authority refusal, and two IVA relation-prefill tests already known to be
missing their runtime-profile context manager).

## Notes

`_absent_bound_carry_diagnostics` (the sibling diagnostic path for BOUND
carries the taxpayer files) is a different diagnostic class from the
formula-fed relations this row's own Modelo 190 example measures, and was
deliberately left untouched — out of this row's scope.

The grouped message's first draft enumerated every member's
`relation_id!r} needs {casilla}` pair in prose; for a ten-member group this
exceeded the diagnostic message's existing 512-character elision cap
(`ElidedProse`, a pre-existing, deliberately-visible truncation primitive
for system-assembled prose scaling with taxpayer data — not something this
row introduced or should route around). Caught by the pure-function test
asserting every relation id appeared verbatim in the message. Fixed by
reordering the message to name the source, the count and the affected
casilla facts first and the relation-id restatement last, and by
correcting the test to assert full membership against the structured
`relation_ids` field — which the length cap never touches — rather than
against the length-capped prose.
