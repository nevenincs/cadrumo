---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S08'
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
     The S08 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Author the mixed-key rotation crash-injection test first, interrupting rotation across envelope files, blob manifests, and the keystore and proving the probe-skip re-run recovers every partial state, using real adapters and simulating the interruption point rather than patching the primitives and ## Scope

- `src/aeat/adapters/persistence/storage/tests/test_rotation_crash_windows.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the mixed-key rotation crash-injection test first, interrupting rotation across envelope files, blob manifests, and the keystore and proving the probe-skip re-run recovers every partial state, using real adapters and simulating the interruption point rather than patching the primitives

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_rotation_crash_windows.py`

## Description

Authored the mixed-key rotation crash-injection test: seed real envelope files, a real EncryptedBlobStore blob, and a real keystore wrapped DEK under the old key; rotate only the envelopes to simulate the crash; prove the mixed state fails new-key-only reads for the un-rotated stores; re-run the full rotation across all three stores and prove probe-skip recovery; assert a converged re-run is a clean no-op.

## Outcome

Three tests pass with real crypto and no patched primitives; DEK value is preserved across the re-wrap and the blob payload survives byte-for-byte.

## Notes

The keystore leg's probe-skip re-wrap uses the sanctioned `wrap_dek`/`unwrap_dek` primitives; no storage primitive is mocked.
