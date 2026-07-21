---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S22'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace all-profile-reset with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S22 and 2026-07-17-all-profile-reset-plan placeholders are machine-filled by
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
     The Prove exact sandbox labels work through switch while sandbox use and bare names are absent and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_profile_sandbox.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove exact sandbox labels work through switch while sandbox use and bare names are absent

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_profile_sandbox.py`

## Description

- Rewrite the active-indicator-after-switch test to enter the sandbox by its canonical `sandbox:<name>` label through `config switch` instead of the removed `sandbox use`.
- Add `test_sandbox_use_command_is_absent` (invocation fails, `use` absent from the sandbox help), `test_switch_rejects_a_bare_sandbox_short_name`, and `test_switch_accepts_a_sandbox_bucket_uuid`.

## Outcome

The suite proves exact sandbox labels resolve through `switch`, a bucket UUID resolves through `switch`, a bare sandbox short name refuses, and `sandbox use` is absent with no alias. 44 passed against real per-bucket encrypted storage (no mocks).

## Notes

Co-committed with S19 (the removal these tests prove absent).
