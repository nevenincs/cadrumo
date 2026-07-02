---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S04'
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
     The S04 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Confirm the bundle-export ordering at HEAD and resolve the archive-checkpoints-or-includes-wal-sidecar cell, updating the reference body with the finding and ## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm the bundle-export ordering at HEAD and resolve the archive-checkpoints-or-includes-wal-sidecar cell, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the bundle-export ordering at HEAD; recorded that the sealed-archive writer writes directly to the output path (no tmp plus rename) and refuses to overwrite. Resolved the archive-checkpoints-or-includes-wal-sidecar cell in the reference body.

## Outcome

Confirmed guarantee: read-time positional/layout detection plus refuse-overwrite; tmp+rename resolved as a non-goal.

## Notes

Surfaced a production gap: the reader caught only `tarfile.TarError`/`OSError`, so a torn-write truncation leaked a raw EOFError. After coordinator authorization the bounded contract fix landed (widen the caught set to `gzip.BadGzipFile`/`EOFError`, re-raise as the documented `SealedArchivePayloadError`, honest docstring). The cell is now CONFIRMED-with-residual: 30-80% truncation caught at read; near-complete truncation caught by the AEAD backstop before provisioning; a trailing-marker format change is a tracked follow-up.


Surfaced a production gap: the reader does not reliably reject a truncated archive (raw EOFError for mid-file truncation, silent accept near-complete). Reported to the coordinator; not patched under this test-only campaign.
