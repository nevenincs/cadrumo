---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e58c4f597e2e4e152d823fe579bd5032225338405e9b021ce88c49fcfa723426'
step_id: 'S08'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add the deudas read-landing guard modelled on the censal reader _assert_read_landing, shipped with an empty refusing _DEUDAS_READ_PATH_PREFIXES tuple so it fails closed by construction before any fetch function exists

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`

## Description

Added the deudas read-landing guard, shipped refusing every landing.

## Outcome

Modified files:

- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`
- `src/cadrumo/adapters/outbound/aeat/sede/__init__.py` (facade)

Exports `assert_deudas_landing`, `deudas_read_path_prefixes` and
`DEUDAS_READ_SURFACE`. The private `_DEUDAS_READ_PATH_PREFIXES` ships as the
empty tuple, and the accessor is exported so a conformance gate exercises the
real tuple rather than a mirrored copy that would keep passing if this one
changed shape.

The guard DELEGATES to the shared `assert_read_landing` allow-list wall in
`_adapter_utils.py` instead of restating it. The plan row said "modelled on the
censal reader `_assert_read_landing`", but semantic discovery found the censal
one is the marker-keyed DENYLIST that its own docstring calls the weaker second
wall, while `assert_read_landing` is the canonical fail-closed ALLOW-list --
its docstring already states that a surface declaring no read pages refuses
everything, and that an empty tuple refuses every landing. The research
document's own recommendation names `assert_read_landing` with a prefix tuple.
Restating it locally would have created a second authority able to drift from
the one every sibling reader is audited against, so delegating satisfies the
row's intent, fail-closed by construction, without duplicating the wall.

The policy declares no allowed browser-action patterns: no control on this
surface may be driven, and every payment and aplazamiento action is a control,
so any future browser action fails the guard until declared.

## Verification

See `S09`. Commit `9009926158`, shared with `S03` -- both plan rows name this
file, and a record shipped without its wall would be the worse intermediate.

## Notes

The empty tuple is not a placeholder standing in for missing work. It is the
only honest value while no specimen exists, and the comment says so: inventing
a plausible consulta prefix would assert an observation nobody made. A later
change to this tuple can only NARROW what is refused.
