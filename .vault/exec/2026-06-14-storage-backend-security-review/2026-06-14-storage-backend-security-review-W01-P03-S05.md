---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S05'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Apply the manifest KDF validation window to the file-fallback parameters on read and reject below-floor Argon2 cost and ## Scope

- `src/aeat/adapters/persistence/storage/master_key/_master_key_records.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Apply the manifest KDF validation window to the file-fallback parameters on read and reject below-floor Argon2 cost

## Scope

- `src/aeat/adapters/persistence/storage/master_key/_master_key_records.py`

## Description

- Add the OWASP-baseline Argon2 cost window (`ge`/`le` on `memory_cost`,
  `time_cost`, `parallelism`) to the file-fallback `_KdfParameters`, reusing the
  canonical bound constants from `_kdf_params` rather than re-declaring literals.

## Outcome

A tampered or buggy `master.kdf` declaring a below-floor cost is refused on read as
`MasterKeyUnavailableError` instead of deriving a weakened KEK. Proven by a new
real-behavior test that provisions a store, lowers `memory_cost` to 8, and asserts
the refusal on `get_master_key`. Storage tree collect-only clean (no import cycle
from the new intra-package import). Committed in `e6f280e68`.

## Notes

The baseline mint constants equal the floor exactly (19 MiB / 2 / 1), so minting
still validates.
