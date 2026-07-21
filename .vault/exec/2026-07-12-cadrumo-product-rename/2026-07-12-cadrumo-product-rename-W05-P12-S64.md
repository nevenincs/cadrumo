---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S64'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update Spanish product locale messages through the locales CLI

## Scope

- `Spanish locale catalogue`

## Description

- Snapshot all four locale catalogue hashes before mutation.
- Run the reviewed Spanish-only production command `python -m cadrumo.locales canonicalize-product-identity --locale es` under isolated local storage.
- Compare every parsed changed leaf with the production identity normaliser and classify each change by referent.
- Verify catalogue audits, focused tests, sibling hash equality, raw residue classification, and live Spanish help output.

## Outcome

- The command changed exactly 29 semantic leaves: 22 command-leading references became `aeat`, and 7 product-display references became `CADRUMO`.
- Parsed key sets are identical before and after the mutation, and every changed value equals the production normaliser result.
- The Spanish catalogue hash changed from `9C06BEA436A970C041C1B5B6E0697552328E30CEA51E7468AB32AF0E0E26DD52` to `58CC27A9731B392490F0E8523A15DA26B88B17B08EA222AD4656B5962E7679D1`.
- English, Catalan, and Hungarian hashes remained unchanged.
- Catalogue scaffold and audit checks passed for all four locales; 38 focused tests passed; live Spanish help presents `CADRUMO`, `AEAT`, and the `aeat` command without stale title-case or command-leading forms.

## Notes

- The production YAML serializer produced a 154-insertion and 161-deletion textual diff; semantic comparison isolated the 29 intended leaf changes.
- No questionable replacements were found. `AEAT` remained at 238 occurrences and `CADRUMO_` remained at 20 occurrences.
- Raw Spanish residue is classified as 7 `CADRUMO` product displays, 20 `CADRUMO_*` environment references, 224 `aeat` command prefixes, one `registry/aeat` authority path, 234 standalone `AEAT` authority references, and one retained `cadrumo-vault/` machine or historical folder name.
- English and Spanish targeted residue is zero. Remaining display/command residues are Catalan 13/26 and Hungarian 6/24 for S65 and S66.
- No locale YAML was hand-edited.
