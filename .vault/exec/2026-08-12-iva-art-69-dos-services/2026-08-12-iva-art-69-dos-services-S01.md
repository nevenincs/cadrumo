---
tags:
  - '#exec'
  - '#iva-art-69-dos-services'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2908dbc0f760343b091dc4a43f0c4126ccd9664c9c24bdd2a6d6a934f835b5a2'
step_id: 'S01'
related:
  - "[[2026-08-12-iva-art-69-dos-services-plan]]"
---

# Declare the twelve lettered items of LIVA art 69.Dos as a closed StrEnum, mirroring the art 20 sub-article discriminator the tree already carries. Document each member from the bundled consolidated text it is read out of, never from memory, and carry the two exclusions the statute writes into its own letters - the art 70.Uno.1 carve-out inside letter d, and the transport-and-container carve-out inside letter j

## Scope

- `src/cadrumo/domain/iva/_schema.py`

## Description

- Declared the twelve lettered items of LIVA art. 69.Dos as a closed `StrEnum`,
  beside the art. 20 sub-article discriminator it mirrors.
- Documented each member from the bundled consolidated text, read out of the
  anchored unit rather than from memory.
- Carried the two exclusions the statute writes INSIDE its own letters: the
  art. 70.Uno.1.º carve-out in letter d), and the means-of-transport and
  containers carve-out in letter j).
- Promoted the enum to the package facade in the same change, since the
  consuming row is in a sibling module.

## Outcome

Done. Twelve members, exported and importable.

## Notes

The two in-letter exclusions are the reason the docstrings quote rather than
summarise. A reader who sees letter j) as "arrendamientos de bienes muebles"
will place a car rental on the list, which the letter itself excludes; and
letter d)'s "otros similares" invites the same over-reach until the art. 70.Uno.1
carve-out beside it is read. Summarising either would produce a member that
looks complete and is not.
