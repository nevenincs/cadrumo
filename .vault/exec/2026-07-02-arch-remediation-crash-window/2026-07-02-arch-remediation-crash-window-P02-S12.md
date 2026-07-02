---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S12'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-crash-window with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Author the bundle-export crash-injection test proving the atomic rename yields no torn archive on a truncated tmp write and ## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bundle_crash_windows.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the bundle-export crash-injection test proving the atomic rename yields no torn archive on a truncated tmp write

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bundle_crash_windows.py`

## Description

Authored the bundle-export crash-injection test: prove a damaged sealed archive is rejected by the reader before decryption and that the writer refuses to overwrite an existing target; the anti-tautology partner proves an intact archive reads cleanly.

## Outcome

Three tests pass, pinning read-time damage detection plus refuse-overwrite.

## Notes

End-truncation detection is a reported production gap in the reader (raw EOFError / silent accept); the test pins mid-stream corruption detection, which holds, and documents the truncation gap.
