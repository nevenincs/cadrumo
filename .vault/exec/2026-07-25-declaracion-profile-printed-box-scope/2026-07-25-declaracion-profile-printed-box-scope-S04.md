---
tags:
  - '#exec'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:76a2c7f328c0c4c9ec0623f74205f921ac207fb621b400207878a51f81443146'
step_id: 'S04'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-plan]]"
---

# Sweep the TOML-dominated id footprint, 38 registry files plus 2 extraction profiles carrying the six ids, since the registry TOMLs are where the edit actually lands and a module-count sizing understates the work by more than half

## Scope

- `src/cadrumo/_data/registry/`
- `40 TOML files`

## Description

- Re-derive the id footprint against HEAD by literal-string walk over `src/cadrumo` and `dev`.
- Confirm the non-profile registry TOMLs require no edit.

## Outcome

Re-measured at HEAD the footprint is 39 TOML, 22 Python and 4 Markdown files, against the recorded 40 TOML and 24 Python. The difference is not drift in the tree: the recorded census was taken before the extraction profiles had been edited, so the two profiles that no longer name the six ids account for the missing TOML, and the missing modules are those whose only reference was through the deleted generator helpers.

The 38 non-profile registry TOMLs are correctly untouched, and editing any of them would have been wrong. The decision preserves the engine's compute-from-primitives design, so the ids remain engine casillas, formula operands, bindings, locale labels and manifest entries. Of those files, 21 belong to Modelos 309, 322 and 353, which carry the same id strings in their own namespaces and are outside this feature.

No registry-build validator refuses a target removal, confirmed by the registry suite loading and validating the whole working tree green.

## Notes

The semantic code index was truncated throughout — roughly 1027 chunks against roughly 4546 files — while reporting itself healthy with an empty degraded-reasons list. A semantic miss was therefore worthless as evidence, so the footprint was established by literal-string walk and by loading revisions through the authority, never by search absence.
