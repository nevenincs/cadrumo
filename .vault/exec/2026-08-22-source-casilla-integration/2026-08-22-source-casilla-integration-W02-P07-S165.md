---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ad160f65551e4ee2db6c85525b3d5aebd33636f30e020c2269341cc9cc103428'
step_id: 'S165'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S165 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The prove complete acquisition-cost fields survive the encrypted inventory repository round trip and ## Scope

- `src/cadrumo/adapters/persistence/profile/tests/test_inventory_roundtrip.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# prove complete acquisition-cost fields survive the encrypted inventory repository round trip

## Scope

- `src/cadrumo/adapters/persistence/profile/tests/test_inventory_roundtrip.py`

## Description

- Replace the legacy purchase fixture with the complete acquisition envelope and role-specific evidence established by S163 and S164.
- Prove nested equality, acquisition fingerprint, capitalized value, unit basis, inventory document version, and governed secure-object metadata after encrypted save and load.
- Mutate nine required or cross-checked acquisition axes through real decryption and re-encryption and prove strict load refusal.
- Substitute one valid evidence digest and prove strict load succeeds while the acquisition fingerprint changes.
- Scan the database and WAL for every evidence reference, digest, component identity, and distinctive financial amount.

## Outcome

The inventory repository now has a non-tautological encrypted persistence proof for the complete acquisition-cost contract. Twelve focused tests passed; Ruff, ty, and diff hygiene passed. The final independent review was clear with no findings at any severity.

## Notes

The first review requested a valid digest-substitution proof, a missing-digest refusal, direct hashed object-key identity, and complete ciphertext-canary coverage. All were added and the same reviewer returned a clear verdict. No repository implementation defect was found and no production code changed.
