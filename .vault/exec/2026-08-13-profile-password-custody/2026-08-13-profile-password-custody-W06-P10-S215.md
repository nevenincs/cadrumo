---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d627a1ddc46fd0637753fc86cf477afd99f31a1843f3758a33366e4adfc42cc0'
step_id: 'S215'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S215 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Migrate the terminal and TUI creation consumer to the required application recovery handoff while preserving masked exact re-entry and cancellation-before-publication and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py and src/cadrumo/adapters/inbound/tui/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the terminal and TUI creation consumer to the required application recovery handoff while preserving masked exact re-entry and cancellation-before-publication

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py and src/cadrumo/adapters/inbound/tui/`

## Description

- Carry the mandatory string-returning recovery handoff contract through the terminal manager seam and TUI registration injection boundary.
- Return masked exact mnemonic re-entry from the recovery screen to the application publication gate.
- Keep cancellation, mismatch, escape, shutdown, and timeout paths fail-closed while leaving successful secret zeroisation to the application scope.
- Exercise real TUI registration, recovery-word, and language-switch flows serially to avoid concurrent KDF timing interference.

## Outcome

The terminal manager and TUI creation paths now satisfy the mandatory application recovery handoff. The recovery screen clears the masked re-entry before dismissal, returns the exact verified phrase to the waiting registration worker, and lets the application compare and wipe it before publication. Refusal paths still wipe immediately and release the worker without creating a profile.

Verification completed with twenty-three focused TUI tests, scoped Ruff and type checks, a clean scoped diff check, and formal re-review with no remaining CRITICAL, HIGH, or MEDIUM recovery findings. The adjacent login screen module reached six passed and two unrelated failures in wrong-password worker exception presentation after its recovery-backed fixture profiles were created successfully.

## Notes

The parallel focused run exposed two timing/context failures that each passed alone; the same complete set passed serially. No test was skipped or weakened. Two pre-existing type diagnostics in the touched registration screen were resolved with boundary casts that preserve the existing structural injection design. Formal review found and corrected one TUI login fixture that returned `None` from the now-required handoff; it now returns the real enrollment mnemonic.
