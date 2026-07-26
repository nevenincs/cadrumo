---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S07'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Map the identity and address fields read from mis datos censales onto profile schema paths with a provenance token naming the consulta surface, the regime fields being out of scope while they have no route

## Scope

- `src/cadrumo/application/live`

## Description

- Discover the existing censal surface semantically before writing, finding the
  already-built sede reader and its typed result model rather than adding a
  second navigation or parse layer.
- Declare the adoptable path set as a named constant so the mapping is data, not
  scattered literals.
- Project the censal read onto four declared profile paths: the filing identity,
  the composed fiscal address, the postcode, and the cadastral reference.
- Compose the decomposed address parts into the single declared address string
  in the order AEAT prints them, skipping absent parts rather than rendering
  gaps.
- Stamp every projected fact with the declared provenance token naming the
  censal consulta surface.
- Emit no fact for a read field AEAT left empty.
- Pin the mapping with real-behaviour tests: every projected path is declared by
  the profile schema, the provenance token is a member of the schema's declared
  source enum, absent read fields emit nothing, and the address parts reach the
  composed field.

## Outcome

The identity and address half of the censal autofill is mapped and committed.
Four paths are populated from the consulta read; the regime fields are out of
scope for this Step and have no route today.

Modified files:

- `src/cadrumo/application/user_profile/_censo_sync.py` — the adoptable-path
  constant, the address composition, and the projection function.
- `src/cadrumo/application/user_profile/__init__.py` — facade exports, so
  consumers reach the projection through the package top level rather than a
  private module.
- `src/cadrumo/application/user_profile/tests/test_censal_sync.py` — the
  projection tests.

Key decision: the combined *Apellidos y Nombre* field is deliberately NOT
projected onto the given-name and surname paths. Recovering the split requires
assuming the Spanish two-surname convention, which reverses the identity of
anyone holding one surname and two given names. Nothing in the read says where
the boundary falls, so the projection declines to guess rather than write a
plausible-looking wrong name into a filing identity. A test pins that neither
name path is emitted and that the combined string is not smuggled into another
path. Filling those fields needs an operator confirmation step, not a heuristic.

## Notes

The Step row scopes this to the live application package, but the work landed in
the user-profile application package instead. Projection and reconciliation are
profile concerns; the live package holds only the acquisition call, which is a
separate Step and a separate owner. Splitting them that way keeps a preview from
writing anything.

Three routes to the regime fields were eliminated on live evidence during this
Step, which is why they are scoped out rather than deferred: the two
consultation form submits return to the same page unchanged, the obligations
route serves a 605-byte shell under a non-standard status with no rendered
content, and the activities register refuses identification before any
interaction because an IAE-exempt individual holds no entry in it. That last
error was present on arrival, not produced by the query, so it is a property of
the register rather than a failed attempt.

Four tests elsewhere in the user-profile package and one import-boundary
violation were red while this Step ran. Both belong to the concurrent work
making the fact model enforce the declared path and provenance sets; neither
involves the files changed here, and the new tests pass under that enforcement.
