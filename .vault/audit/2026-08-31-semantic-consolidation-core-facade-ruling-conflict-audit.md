---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0bd443696bc11df0040fd7f3b76fc65999d7820e66e7d3ce30943014f7f91120'
related: []
---

# `semantic-consolidation` audit: `core facade ruling conflict`

## The conflict

`P01.S08` directs retiring the `cadrumo.core` lazy export map "on the measured
finding that the facade saves a real consumer nothing", and
`aeat-architecture-boundaries` states plainly that package namespaces "are inert
and may not import, bind, alias, lazily resolve, or re-export project symbols".

Thirteen shipped gates assert the opposite, by name:

- `test_casilla_id::test_casilla_id_capabilities_are_public_only_from_core`
- `test_prorrata_register_core_authority::test_prorrata_register_enums_are_public_only_from_core`
- `test_estado_casilla_oficial::test_estado_casilla_oficial_is_the_single_public_core_identity`
- `test_operator_action_axis::test_operator_action_axis_is_the_single_public_core_identity`
- `test_filing_projection_ref::test_core_facade_exposes_the_canonical_flat_projection_union`
- `test_filing_projection_ref::test_core_facade_exposes_the_single_projection_union_owner`
- `test_notificacion_estado_servicio::test_the_axis_is_reachable_through_the_core_facade`
- `test_corpus_text::test_core_facade_normaliser_imports_without_configuration_or_domain_loading`
- `test_external_constants_centralisation_part1::test_m347_consumers_use_public_core_facade_in_source`
- `test_early_init_facade_imports` (four cases, on facade resolution during
  settings construction)

These do not merely READ the facade. They require it: that a symbol is public
*only* from core, that an axis is *reachable through* the facade, that the
facade resolves a late-bound name while settings are being constructed.

## What was done, and undone

The retirement was executed and verified first, so the conflict is measured
rather than predicted. The map validated completely -- 357 of 357 entries name a
module that really binds the symbol -- and retiring it repointed 33 consumers,
kept `--collect-only` at its 6 pre-existing peer errors, and left the core suite
at 2264 passing.

Only 33 consumers, against 357 exports. That is direct evidence FOR the step's
premise: almost every real consumer already imports from the specific core
module, so the facade is carrying far less than its size suggests.

It was then reverted, and `P01.S08` reopened.

## Why it was reverted rather than pushed through

The precedent set under `P01.S07` was to rewrite a contradicting gate against
the defining module, preserving what the gate PROTECTS while dropping the
retired premise. That was one gate, and its subject genuinely survived the move.

Thirteen is a different claim. A single gate asserting "import this from the
package root" reads as an artefact of the old regime. Thirteen, spread across
eight files, naming the facade in the test names themselves, reads as a
deliberate and defended position -- and at least one is not a naming artefact at
all: `test_early_init_facade_imports` exercises facade resolution DURING settings
construction, which is behaviour, not style.

Rewriting all thirteen would make the tree green while deciding, unilaterally
and at the end of a long session, that a documented architectural position is
obsolete. The measurement is the deliverable here; the ruling is not the
executor's to make.

## What is needed

An operator ruling on whether `cadrumo.core` is exempt from the inert-namespace
rule as a declared public API, or whether these thirteen gates are the old
regime and should be reauthored against defining modules.

If the ruling is to proceed, the work is ready: the map validates completely,
the tooling is proven on the larger storage case, and the thirteen gates are
enumerated above. The one requiring real thought is
`test_early_init_facade_imports`, because it tests import-time behaviour rather
than surface.
