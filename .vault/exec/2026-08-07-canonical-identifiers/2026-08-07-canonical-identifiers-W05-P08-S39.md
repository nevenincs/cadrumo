---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:fb6ca52482cbe514e5fd75f662dbc1bbb79866e4960c7f1176b91a09f5d521f1'
step_id: 'S39'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# declare `RegistryRevisionId` as a new `IdentifierNamespace.APP_REGISTRY_REVISION_ID` member and alias for the human-authored registry version tag

## Scope

- `src/cadrumo/core/identity/_namespace.py`

## Description

- Before declaring anything, semantic-searched and grepped for the concept
  this row targets — "the human-authored registry version tag" — because
  `W05.P07.S36`'s own corrected text already named this exact concept:
  "the concept already has a canonical home as `type RevisionId` in the
  registry ids module, exported from the registry facade and carrying 16
  users at HEAD." A row asking to mint a NEW alias for a concept a sibling
  row's own text says already has a canonical home is worth checking before
  building anything.
- Grepped every `registry_revision_id` site in the tree (36 files) for a
  still-bare `str` declaration: zero matches, production or test. Read a
  representative site, `application/modelo/_work_addressing.py`, directly:
  every `registry_revision_id` field and parameter (nine sites in that file
  alone) is already typed `RevisionId | None` or `RevisionId`, and none of
  it is in this session's own working-tree diff — it was already this way
  at HEAD before `W05.P07.S36` started.
- Read `core/identity/_namespace.py`'s own docstring for
  `APP_CALCULATION_REVISION_ID`, which independently confirms the
  disposition: "Distinct from the registry's own human-authored revision
  version tag, which is a different namespace with its own home in the
  registry schema package." That sentence already exists at HEAD, in the
  very file this row would edit, and already states this concept's home is
  the registry package — i.e. `RevisionId` — not this taxonomy.
- Concluded: this row's premise is the SAME stale premise `W05.P07.S36`'s
  own text already named and corrected once. Declaring
  `APP_REGISTRY_REVISION_ID` / `RegistryRevisionId` now would mint a SECOND
  alias beside `RevisionId` for one concept — precisely the criticality
  `W05.P07.S36` closed, re-opened by this row if executed literally. Did
  not declare it.

## Outcome

**ADJUDICATED, NOT DECLARED — correctly, not by omission.** No file
changed. The row's premise (that the human-authored registry version tag
has "no existing alias") was true when the ADR's Wave `W05` amendment was
written (2026-08-07) but was superseded by `W05.P07.S36`'s correction
(instructed 2026-08-11): that concept's canonical home is `RevisionId` in
`domain/calculations/registry/_ids.py`, already carrying every
`registry_revision_id` site in the tree. Declaring a second alias here
would fragment a canonical type the sibling row just consolidated, and
would make `W05.P08.S40`'s instruction to "retype the ... `registry_revision_id`
sites onto the two new aliases" impossible to execute correctly, since
there is nothing bare left to retype — see `S40`'s own record. No ADR
amendment currently records this correction for the `W05.P08` rows
specifically (only `W05.P07.S36`'s row text was updated); flagged to the
team lead in case a short correcting amendment is warranted so a future
reader does not re-derive this from the same now-stale ADR sentence a
second time.

## Notes

No incidents. This is the same finding shape as `W05.P07.S37`
(`short_calculation_revision_id` onto `Hex16Str`): a row's literal
instruction, faithfully executed, would have reproduced a defect a sibling
row in the SAME plan already fixed. Caught by re-reading the sibling row's
own corrected text before writing any code, not by chance.
