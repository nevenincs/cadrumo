---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:03d079207dd18116004f520cb9cb51e754708d62643d88e74bffcffd67f60e69'
step_id: 'S137'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Route Cl@ve Movil identity classification through the domain classifier, restoring the prefixed NIF its hand-rolled shape regexes silently excluded

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/clave_movil_support.py`
- `src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_movil.py`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/auth/clave_movil_support.py`
- `M` `src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_movil.py`
- `verify:` 12345678Z -> DNI, X1234567L -> NIE, K1234567L -> DNI, L1234567L -> DNI
- `verify:` B66012345 refused naming CIF; 12345678A and notanid refused on checksum
- `verify:` `pytest .../auth/tests/test_clave_movil.py -n 0 -m ""` -> pass (20)
- `verify:` `pytest .../aeat/auth -n 0 -m ""` -> 285 pass, 7 live-gated

## Notes

The adapter carried its own DNI and NIE regexes to pick the kind, then called the
canonical checksum. Half-merged, and the half it kept was incomplete: no branch
for a K/L/M NIF, the number a natural person holds when they have no DNI or NIE
-- a minor, or a foreign national whose number is not yet assigned.

Probed rather than reasoned: validate_identity on K1234567L returns NIF, and
classify_identity on the same value raised, telling the holder their identifier
was not a valid DNI or NIE. A checksum-valid Spanish identifier refused with a
false claim about it.

The exclusion was NOT policy. The function docstring states the CIF exclusion and
its reason -- Cl@ve Movil authenticates a natural person -- and says nothing
about a prefixed NIF, which is what distinguishes a stale copy from a decision.

Classification now comes from validate_identity and the local regexes are gone.
The accepted set is a mapping keyed by IdentityDocument, so the exclusion is
stated rather than emergent: if AEAT is found to bar a prefixed NIF from this
flow specifically, that is one entry with the evidence beside it, not a regex to
re-derive. The CIF refusal improved for free -- it now names what the operator
supplied instead of reporting only that the value was not a DNI or NIE, which was
equally true of a typo and of an empty string.
