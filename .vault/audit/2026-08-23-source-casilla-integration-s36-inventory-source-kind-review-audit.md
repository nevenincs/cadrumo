---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:5206c171fc7790630b7ba54a33774ea0042965e0f4a15e6c58aea071554a7b92'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `s36 inventory source kind review`

## Scope

Formal review of `W02.P07.S36`, limited to the canonical
`BindingSourceKind.INVENTORY` addition, its derived-family classification,
explicit pre-resolver disposition, exhaustive readiness projections, and the
taxonomy/parity tests changed with it. The review checked the accepted inventory
mapping and aggregation-taxonomy decisions, semantic uniqueness against the
ledger, invoice, counterpart, and bienes-de-inversion families, absence of any
premature selector, validator, registry binding, or resolver, and the no-legacy
requirement. It also ran the focused taxonomy, source-mesh, selector-validation,
and operator-readiness parity suites.

## Findings

### selector-parity | high | The new source is unclassified by both selector and validator coverage gates

`BindingSourceKind.INVENTORY` is correctly deferred and has no premature selector
or validator, but the exhaustive gates still require every non-mesh-only enum
member to appear in `_BINDING_SELECTOR_REGISTRY` and
`_BINDING_VALIDATOR_REGISTRY`. Consequently
`test_binding_selector_registry_covers_typed_sources` and
`test_every_binding_source_kind_is_validator_dispatched_or_documented_mesh_only`
fail. S36 cannot close with those standing gates red. The parity contract needs a
derived, stale-safe classification for a deferred source whose registry binding
has not yet been declared; it must stop exempting inventory automatically when
S37/S38 or the binding step makes the source declarable.

### readiness-locales | high | The exhaustive readiness projection points to an untranslated locale key

`CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS` adds
`cli.app.modelo.bindings.readiness.inventario`, but that key is absent from the
locale catalogues. The exhaustive catalogue gate fails first for Catalan and
would leave an operator-facing sentinel/fallback if accepted. Either add the
semantic key to every supported catalogue or select an already-authoritative key
whose wording truly describes the inventory schedule; the total locale and
action projections must remain exact over `BindingSourceKind`.

### readiness-taxonomy | medium | Inventory readiness still denies and duplicates the canonical taxonomy member

`application.inventory._source_readiness` still states that the raw `inventory`
token is not a `BindingSourceKind` member and owns a separate
`INVENTORY_SOURCE_KIND = "inventory"` constant. S36 makes both statements false:
there is now one canonical typed member, and the application declaration should
project its byte-stable value rather than preserve a parallel raw-token
authority. Leaving the contradiction in place weakens the single-taxonomy and
no-legacy guarantees even though the discovery surface currently records only
the expression text.

### selector-parity-resolution | high | Still open: green exemptions are not fail-closed against registry declaration

Re-review confirms the focused suite is green, but the original finding is not
fully resolved. Both new exemptions compute `DEFERRED_SOURCE_KINDS` minus the
selector or validator registry itself. That makes an implemented selector or
validator remove its own exemption, but it does not detect a compiled registry
binding that arrives first. A deferred inventory binding with neither contract
could therefore remain exempt from these two exhaustive gates. The exemption
must be limited to deferred **and registry-undeclared** members, derived from the
compiled registry rather than from the implementation collection the gate is
measuring. No selector, validator, binding, or resolver was added prematurely in
the reviewed S36 diff.

### readiness-locales-resolution | low | Resolved: every supported catalogue now carries the inventory label

Re-review finds the inventory readiness key in Catalan, English, Spanish, and
Hungarian catalogues. The exhaustive readiness projection test passes, so the
operator surface no longer falls through to a missing-translation sentinel.

### readiness-taxonomy-resolution | low | Resolved: readiness now consumes the canonical typed member

`InventorySourceReadiness.source_kind` is now typed as `BindingSourceKind`, the
constructor uses `BindingSourceKind.INVENTORY`, and the parallel raw-string
constant plus its public export were deleted. The stale documentation denial was
replaced with the canonical identity. This resolves the taxonomy and no-legacy
finding without adding resolution behavior.

### selector-parity-final-resolution | low | Resolved: exemptions now require deferred, undeclared, and unimplemented state

Final re-review confirms the selector and validator exemptions subtract the
compiled registry's declared sources as well as their respective implementation
registries from production `DEFERRED_SOURCE_KINDS`. Explicit ratchet tests prove
that a binding declaration, selector or validator implementation, or removal
from deferral independently ends the exemption. This closes the remaining high
finding with a fail-closed transition into S37/S38 and the later registry step.
The reviewed diff still contains no premature selector, validator, binding, or
resolver. The expanded focused suite passes all 86 tests.

### final-verdict | low | Clear to close S36

All recorded high and medium findings are resolved. The canonical inventory
member is semantically distinct, remains outside the derived ledger, invoice,
and counterpart families, is explicitly deferred without being silenced as
manual input, projects readiness exhaustively, uses the canonical typed identity
without a compatibility alias, and carries fail-closed selector/validator
ratchets. No further findings block S36 closure.

## Recommendations

- Resolve `selector-parity` in S36 with a production-derived deferred-and-
  undeclared classification in the exhaustive tests; do not add the S37 selector
  or S38 validator early, and retain a gate that bites once inventory becomes
  registry-declared.
- Resolve `readiness-locales` by completing the locale projection in every
  catalogue and rerun the operator-readiness action-projection suite.
- Resolve `readiness-taxonomy` by making the readiness declaration consume the
  canonical enum member/value and deleting the stale denial and parallel raw
  token authority.
- Re-run the focused six-module suite used by this review before attesting the
  audit: taxonomy, enrollment status, mesh parity, build validation, selector
  shape, and modelo-readiness action projection.
