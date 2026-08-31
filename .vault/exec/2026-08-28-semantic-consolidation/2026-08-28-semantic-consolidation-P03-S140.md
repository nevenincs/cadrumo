---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3e266f099574c0de7f9fefa33bef1bd059fdbf75841325064052fc9ad196ca51'
step_id: 'S140'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# State the minimo-descendientes relacion ambiguity once, and correct the reasoning both copies had let go stale when the relacion axis gained a member

## Scope

- `src/cadrumo/domain/contribuyente/descendant_maternity.py`
- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

## Changes

- `M` `src/cadrumo/domain/contribuyente/descendant_maternity.py`
- `M` `src/cadrumo/application/modelo/_calculate_input.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_descendiente.py`
- `verify:` probed every DescendantRelacion member: only descendiente is ambiguous
- `verify:` `pytest src/cadrumo/domain/contribuyente -n 0 -m ""` -> pass (523)

## Notes

The declaration surface and the calculate path both asked whether a descendant
relación is ambiguous for Art. 58.1 versus Art. 81.1, and both restated the AEAT
manual reasoning beside their own copy of
`relacion is DescendantRelacion.DESCENDIENTE`. Only the relación half was
extracted. The months gate stays at each site because it genuinely differs --
declared months at declaration time, contributing months at calculate time.

Consolidating surfaced something the two copies were hiding. Both asserted the
axis has "no member for either population today", naming two: a grandchild or
other descendant by consanguinidad, and a minor under judicial guarda y custodia.
The second half is stale. DescendantRelacion.GUARDA_Y_CUSTODIA_JUDICIAL exists,
its own docstring says Art. 81.1 excludes it BY NAME, and it is correctly absent
from ART_81_1_MATERNIDAD_RELACIONES -- so that carer can state their relationship
truthfully and the deducción already does not reach them.

Behaviour was right; the reasoning beside it was written twice and neither copy
followed the axis when it gained the member. The centralised version now names
the one population that remains without a truthful value.
