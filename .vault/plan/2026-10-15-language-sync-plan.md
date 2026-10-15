---
tags:
  - '#plan'
  - '#language-sync'
date: '2026-10-15'
tier: L1
related:
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-06-01-output-language-typed-constant-migration-adr]]'
  - '[[2026-07-12-multilang-externalization-adr]]'
  - '[[2026-10-09-desktop-titlebar-adr]]'
modified: '2026-10-15'
body_schema: body-v2
body_hash: 'sha256:e977620d63cb0c13b4fc7274194cebb830ec669c3e72c4d4601ac2b6ba7ea4c8'
---

# `language-sync` plan

## Description

Approved 2026-10-15

Authorization: the user's explicit request to implement shared language selection in the Tauri Settings popup and Cmd+K palette, synchronize documentation, TUI, CLI and desktop, and review canonical state and live wiring. The user specifies Luna max for discovery, summary and verification and Sol 6.1 medium for coding.

Reuse the canonical encrypted profile preference `preferences.output_language`, its authenticated mutation and existing nonsecret bucket hint. Preserve explicit per-invocation CLI language overrides. The desktop-shell and desktop-design-system decisions are amended for this bounded shared-language behavior; their existing frontend-only language restrictions no longer apply to language controls. The typed language and multilang decisions retain the four-language axis and canonical catalog renderer. Do not add another persisted preference or state library. Signed-out choices remain transient and cannot mutate a profile without authentication.

## Steps

- [ ] `S01` - Route shared language reads and writes through the canonical profile fact, then publish typed updates to TUI and CLI consumers; `src/cadrumo/application/user_profile, application/modelo/work_form_localization.py, core/i18n/render.py, entrypoints/tui and owning tests, locales/*/common.yml, src/cadrumo_client language/event contracts and transport, src/cadrumo_runtime holder, profile event observation, installed TUI composition and owning tests, dev/quality/metadata/import_load_targets{,.cadrumo,.cadrumo_client}.json generated module enrollment`.
- [x] `S02` - Expose the shared language preference through narrow verified desktop host reads, writes, and live observation; `native/desktop/src-tauri language IPC and event adapter`.
- [ ] `S03` - Connect Settings, Cmd+K, and the documentation switcher to one subscribed language controller; `native/desktop/frontend/src, frontend tests and fixtures, docs/_static/cadrumo-desktop-bridge.js, and dev/docs/tests/test_docs_desktop_flavor.py`.

## Parallelization

S01, S02 and S03 may proceed concurrently with disjoint ownership after agreement on the typed holder and host contracts. S01 owns Python product, client and runtime files; S02 owns the Rust Tauri host; S03 owns frontend and the documentation bridge. The root serializes governance, checkpoints and commits. Luna agents own shared verification and review; coding agents reuse their evidence. Preserve unrelated worktree edits.
## Verification

Prove canonical authenticated persistence, malformed-language refusal, profile isolation and cross-process invalidation. Verify changing language in Settings, Cmd+K, documentation or TUI updates the subscribed desktop and mounted TUI views without destroying staged work. Verify all four options remain available without bundled documentation, account changes reject old results, and explicit CLI overrides stay invocation-local. Use existing UI primitives and generated catalog translations.

Run focused Python tests and configured lint, format, type and import checks; frontend `npm run check` and relevant Playwright tests followed by the configured suite; documentation bridge tests; and CMake-owned desktop host tests and clippy. Obtain final exit codes, distinguish existing failures and unavailable native acceptance from new regressions, and finish with an integrated review. No Step is closed without required passing verification.
