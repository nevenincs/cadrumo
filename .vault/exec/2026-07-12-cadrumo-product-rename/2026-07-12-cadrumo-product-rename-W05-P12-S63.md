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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S63 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Update English product locale messages through the locales CLI and ## Scope

- `English locale catalogue` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
