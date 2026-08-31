---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b2c37ddf231a3c0f0bad1d232b3c4970913f966d6620f99f273c7a2ac57c2b9c'
step_id: 'S157'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Make the two Orden coefficient annotations state the rule that was already reachable, after proving zero was never constructible through either field's only source

## Scope

- `src/cadrumo/domain/iva/regimen_simplificado_rows.py`

## Changes

- `M` `src/cadrumo/domain/iva/regimen_simplificado_rows.py`
- `verify:` module coefficient probed -- 0 refused, 0.5 accepted, -1 refused
- `verify:` seasonal coefficient probed -- 0 refused on the coefficient field
- `verify:` `pytest domain/iva -k "orden or simplificado or regimen" -n 0 -m ""` -> pass (5)
- `verify:` `pytest registry -k "m303_orden or orden_projection or simplificado" -n 0 -m ""` -> pass (79)
- `verify:` `validate_registry()` -> passes over the whole tree

## Notes

A new shape, and the inverse of the one recorded in the invisible-bounds audit.
There the annotation UNDERSTATED, and a field that looked unbounded was governed
by a closed set, a codec or a shared validator. Here the annotation OVERSTATED:
both Orden coefficients declared `ge=0`, permitting a zero that neither field can
actually receive.

The evidence differs per field and both were checked rather than generalised
from one:

- A module coefficient is refused by `validate_orden_module_identities`, and the
  only construction site builds each `ModuloOrdenAnual` straight into the
  `ActividadOrdenAnual` that runs it, so a zero was never constructible.
- A seasonal index coefficient is compiled from
  `M303AnnualOrdenRawSeasonalIndex`, whose own field is already `gt=0`, so a zero
  could never arrive from the only source there is.

The downstream module check stays rather than being replaced. It takes a
Protocol, so it governs any future implementer and not only this class -- the
annotation now agrees with it instead of contradicting it.

Deliberately NOT done the other way. The tempting move was to leave the
annotation and treat the downstream validator as the whole rule, which is what
the Modelo 720 correction earlier in this campaign taught: do not preempt a
shared validator with an annotation. That reasoning does not apply here, because
the annotation and the validator disagree rather than overlap, and it was the
annotation making the unstated claim.

### Verification was blocked, then completed

At the time this landed the tests could not run. A peer was relocating inside
`core/`: `authority_grade` did not resolve, which broke collection for
twenty-nine registry test modules and eight IVA ones, and `storage_taxonomy`
appeared BETWEEN two runs minutes apart. The step was recorded as resting on
direct construction probes rather than a green suite, which is weaker evidence.

The relocation has since settled and the suites were re-run: 79 registry tests,
5 IVA tests, and `validate_registry()` over the whole tree, all green. The
verify lines above are that run, not the probes.
