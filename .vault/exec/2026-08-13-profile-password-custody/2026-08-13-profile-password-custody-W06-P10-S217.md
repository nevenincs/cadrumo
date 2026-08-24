---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:831e23104a2fc5baded017aedcd8da8c04dcc804a54ad69cc759e4ef84b6cc61'
step_id: 'S217'
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
     The S217 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Re-author application, CLI, TUI, storage, and harness tests around mandatory recovery handoff, exact possession verification, and rollback on missing, mismatched, cancelled, or failed handoff and ## Scope

- `src/cadrumo/application/user_profile/tests/ and src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/adapters/inbound/tui/tests/ and src/cadrumo/adapters/persistence/storage/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-author application, CLI, TUI, storage, and harness tests around mandatory recovery handoff, exact possession verification, and rollback on missing, mismatched, cancelled, or failed handoff

## Scope

- `src/cadrumo/application/user_profile/tests/ and src/cadrumo/entrypoints/cli/tests/ and src/cadrumo/adapters/inbound/tui/tests/ and src/cadrumo/adapters/persistence/storage/`

## Description

- Replace the last password-only fixture expectations with creation-enrollment and password-restore-independence assertions.
- Exercise real application registration, storage publication, archive/restore, scripted CLI, terminal/TUI, and harness paths.
- Prove exact possession success and atomic refusal for missing, failed, cancelled, and mismatched recovery handoffs.
- Run focused behavioral suites, scoped Ruff and ty, and an independent formal review.

## Outcome

- Current-format source profiles are tested as always enrolled at creation, even when a fixture discards the displayed words.
- Password restore is tested as remaining usable without retained recovery words, without making recovery part of the normal restore contract.
- The application/storage suite passed 22 tests, scripted CLI passed 36 tests, terminal/TUI passed 23 tests, and harness/console-guard passed 23 tests.
- Scoped Ruff passed. Scoped ty reported two pre-existing test typing diagnostics outside the changed assertions: Textual's historical `query_one(..., None)` call and a structural replay-key fixture used by recovery-artifact export.
- No mocks, patching, skips, or password-login coupling were introduced.

## Notes

- The first TUI matrix run exposed a transient composition race in the mismatch test; the unchanged lane passed all 23 tests on the focused rerun.
- Formal review rejected an initial draft that treated recovery as normal archive/restore cargo. The assertions were corrected to respect the ADR boundary that S218 owns: mandatory creation enrollment does not authorize recovery transport.
- Concurrent capability-output failures characterized in S216 remain unrelated and were not absorbed into this step.
