---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e8fa6036b1b2474d6e68fead116a9844bc51f61f8ec13ca685b39cc74b745ce0'
step_id: 'S214'
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
     The S214 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Migrate the scripted CLI creation consumer to the required application recovery handoff while preserving bounded descriptor transfer, collision preflight, verification, and failure atomicity and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py and src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the scripted CLI creation consumer to the required application recovery handoff while preserving bounded descriptor transfer, collision preflight, verification, and failure atomicity

## Scope

- `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py and src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py`

## Description

- Return the CLI-verified recovery phrase from the scripted handoff to the mandatory application publication gate.
- Preserve terminal and paired-descriptor delivery, strict verification JSON parsing, descriptor collision preflight, and CLI-specific mismatch refusal.
- Exercise the complete real scripted profile-creation matrix across interactive and non-interactive lanes.

## Outcome

Scripted profile creation now satisfies the required application handoff contract without weakening the CLI leaf protocol. The CLI still refuses malformed, missing, colliding, or mismatched recovery channels before a profile can survive; after its surface-specific verification succeeds, the exact phrase reaches the application for the final pre-publication comparison.

Verification completed with the thirty-six-test scripted creation integration matrix, scoped Ruff and type checks, a clean diff check, and a formal review with zero CRITICAL, HIGH, MEDIUM, or LOW findings.

## Notes

The profile command specification already owned the paired leaf-channel declarations and required no code change. Terminal manager and TUI consumers remain intentionally untouched for S215.
