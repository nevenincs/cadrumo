---
tags:
  - '#audit'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# `binding-vocabulary-cli-cohesion` audit: `Wave 1 D9 close-blocker audit`

## Scope

Wave 1 D9 close-blocker pass over the open remainder reported by
`vaultspec-core vault plan status` on 2026-07-02 after reconciling landed F8 work.
The pass used semantic search first, then targeted `rg`, plan-status JSON, scoped
`git diff -- <path>` WIP checks, and focused tests. This audit is not a closure
honesty review because the campaign is not structurally complete.

## Findings

### f8-implementation-reconciled | low | S25 and S26 were implemented but unchecked

The selector-union and `typed_enum` implementation was already present at HEAD in
commit `071438bd6`. Exec records were added for S25 and S26 and the plan steps were
checked through the plan CLI. The focused F8 run is not green yet: `test_selector_shape.py`
already carries non-authored WIP and fails because the live selector registry includes
`DONATIVO_DONOR` while the expected-set test has not been currentized. S27 remains
open and deferred until that peer-owned test WIP clears or its owner lands the
coverage update. Log: `_scratch-wave1-d9/f8-tests.log`.

### observation-prefix-tail-blocked | medium | S15-S18 still require relocation work on a dirty target surface

The Observation-prefix phase remains open. Several listed names are already prefixed,
but live code still exposes unprefixed carriers such as `RetencionObservation`,
`CounterpartObservation`, `CounterpartAggregationObservation`,
`DeclaracionObservation`, `BorradorObservation`, and `GroiObservation`. The first
phase target includes `src/aeat/domain/calculations/registry/_ledger_bindings.py`,
which already has non-authored WIP, so this pass did not start the relocation series.
S15-S18 are formally deferred to the next owner after the dirty target files are
peer-clean.

### operator-verb-tail-blocked | medium | S21-S24 are blocked by active locale/operator-surface WIP

The CLI verb-reconciliation phase remains open: `bindings preview`, `calc pull --compute`,
and `work calculate` are still present in the live CLI. The step surface includes the
locale catalogues and operator help/write-policy/error-suggestion sweep; scoped WIP
checks found active non-authored edits in `src/aeat/locales/ca.yml`,
`src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`, and `src/aeat/locales/hu.yml`.
Because these are operator-visible locale-bound changes, S21-S24 are deferred until
the locale/operator-surface WIP is clear and the locale CLI can own the full sweep.

## Recommendations

Resume at `W03.P05.S15` once `_ledger_bindings.py` and the affected observation
carrier files are clean, then run `W03.P05.S18` before starting W04. Keep S27 open
until the selector coverage test is green. Do not lift the bindings freeze from this
campaign: `vault plan status` still reports open steps.
