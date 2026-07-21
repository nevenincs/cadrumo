---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S63'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update English product locale messages through the locales CLI

## Scope

- `English locale catalogue`

## Description

- Snapshot all four locale catalogue hashes before mutation.
- Run the reviewed English-only production command `python -m cadrumo.locales canonicalize-product-identity --locale en` under isolated local storage.
- Compare every parsed changed leaf with the production identity normaliser and classify each change by referent.
- Verify catalogue audits, focused tests, sibling hash equality, and live English help output.

## Outcome

- The command changed exactly 38 semantic leaves: 28 command-leading references became `aeat`, and 10 product-display references became `CADRUMO`.
- Parsed key sets are identical before and after the mutation, and every changed value equals the production normaliser result.
- The English catalogue hash changed from `2108A1AC2E2C60B8713FE8C7A850CD55525451C7D17B5263F51DE9FF6D7ED630` to `FD1949009563A0D3211164BC7C715848B6717D26DB951AC75559C7A9698A0037`.
- Spanish, Catalan, and Hungarian hashes remained unchanged.
- Catalogue scaffold and audit checks passed for all four locales; 38 focused tests passed; live English help presents `CADRUMO`, `AEAT`, and the `aeat` command without stale title-case or command-leading forms.

## Notes

- The production YAML serializer produced a 147-insertion and 152-deletion textual diff; semantic comparison isolated the 38 intended leaf changes.
- No questionable replacements were found. `AEAT` remained at 224 occurrences and `CADRUMO_` remained at 21 occurrences.
- English targeted residue is zero. Remaining display/command residues are Spanish 7/22, Catalan 13/26, and Hungarian 6/24 for S64 through S66.
- No locale YAML was hand-edited.
