---
tags:
  - '#exec'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S03'
related:
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-plan]]"
---




# Re-type owned_sources and both source_kind carriers to BindingSourceKind

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description


This record covers the whole of P02 (S03 narrowed plus the S04-S12 resolver and
mesh-set re-typing) — commits `b4bde7d46` (S03), `1200e0532` (S06-S12), and
`3f78cccf5` (S05); S04 was absorbed by a concurrent codex commit.

- S03 (`b4bde7d46`): re-type `CalculationSourceResolution.owned_sources`, the
  `ModeloSourceResolver.owned_sources` Protocol property, `DEFERRED_SOURCE_KINDS`,
  and the `merge_source_resolutions` / `storage_degradation_resolution`
  owned-source carriers to `BindingSourceKind`. A `mode="before"` coercer hydrates
  known bare-string tokens to members so not-yet-migrated resolvers keep working
  under the strict model config.
- S06-S12 (`1200e0532`): re-type each clean resolver's `owned_sources` class
  attribute to its `BindingSourceKind` member (OSS, profile, relation-prefill,
  previous-filing, iva-wallet-decision, borrador, invoice-catalogue).
- S05 (`3f78cccf5`): re-type the five `_modelo_bindings.py` ledger/retenciones
  resolver `owned_sources`, landed via the apply-cached gated drive over r2's
  live RET-1/#28 WIP.

## Outcome

P02 complete. Both parity halves green, the mesh/boundary suites green, clean
collection across `src/aeat`. The two diagnostic/provenance `source_kind`
carriers were deliberately LEFT as `str` (narrowed §3) — they are a mixed
diagnostic channel carrying non-source-kind tokens.

## Notes


STRICT_FROZEN_CONFIG (strict=True) blocks pydantic string-to-enum coercion, so
re-typing the field alone would break every resolver still passing bare strings
(including the peer-WIP `_modelo_bindings.py` I could not edit). The
`mode="before"` coercer (the core `BindingAggregation._coerce_op` precedent)
resolves this: known tokens hydrate to members, blanks raise, unknown tokens fall
through to the strict field's standard enum rejection — no new locale key.

A `aeat.locales set` run during S03 triggered a broad scaffold-align that absorbed
locale keys referenced by peer code WIP (retenciones, iva-wallet overrides). The
locale files were restored to HEAD and the coercer reworked to reference only the
pre-existing `owned_sources_blank` key, so S03 introduced zero locale drift.

S05 used the apply-cached gated drive (`git apply --cached` of HEAD-anchored
own-only hunks, foreign-marker verified, no-pathspec commit) to land over r2's
uncommitted RET-1/#28 WIP without overwriting it.
