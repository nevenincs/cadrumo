---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S67'
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
     The S67 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Regenerate locale scaffold output and pass locale parity checks and ## Scope

- `generated locale scaffold` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate locale scaffold output and pass locale parity checks

## Scope

- `generated locale scaffold`

## Description

- Run the authoritative locale scaffold under isolated Cadrumo local state after S65 and S66 landed.
- Translate all thirty generated keys in English, Spanish, Catalan, and Hungarian through `python -m cadrumo.locales set` only.
- Cover cross-period findings, verification/workflow recovery guidance, formula-operation labels, and Click help/error fragments.
- Preserve AEAT in agency/censo/evidence meanings and leave the intentional-identical authority unchanged.
- Verify scaffold parity, codebase audit, YAML, Unicode, placeholder removal, and translation honesty.

## Outcome

All four catalogues contain the complete codebase key set, and every generated
leaf has a language-specific value with preserved placeholders. No scaffold
placeholder or Unicode replacement character remains, and the honesty ratchet
passes without an allowlist change.

## Notes

- A stale S65 background locale writer overlapped the first scaffold attempt and malformed `ca.yml`. The writer was terminated, the catalogue was reconstructed byte-for-byte from the committed S65 blob through `apply_patch`, and work resumed only after the atomic locale-manager fix `4a3511c9d6` landed.
- An interrupted translation pass left forty-five explicit placeholders; inspection identified them precisely and they were filled through targeted locale CLI calls rather than another bulk transformation.
- `scaffold --check` and `audit` report every catalogue `ok`; twenty-two focused parity, honesty, coverage, positional, and locale-CLI tests pass.
- Three broader CLI tests still fail because current non-S67 command constants emit `aeat` or compare persisted `cadrumo` actions against `aeat` constants. The localized Catalan/Hungarian prose is selected correctly; S67 does not modify those command authorities.
- No child `cadrumo.locales` process remained at final verification, and `_intentional_identical.json` was unchanged.
