---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:b5324778c5f717857fa557afd3da2d47e163a7954a902ad7a605ed118f9aefa6'
step_id: 'S23'
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
     The S23 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh run and codify real CLI, TUI, recovery-isolation, artifact, and live read-only DEHu routes without remote writes and ## Scope

- `src/cadrumo/entrypoints/cli/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh run and codify real CLI, TUI, recovery-isolation, artifact, and live read-only DEHu routes without remote writes

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Three route modules codified (commit `5b8bfdb87d`-era, 5 cases green + one clean live-gated deselection): `test_recovery_isolation_cli_matrix.py` — A's archive restores into a B-active root as A's own capsule without switching the active profile (the archive contract held at the operator surface), and B's passphrase refuses at A's login through the real verb; `test_live_notifications_pull_route.py` — the `aeat_live`-marked pull route driving the real CLI with the in-body live gate, proving the preflight/persistence/grounding wiring when the live lane runs and deselecting cleanly without credentials; `test_login_screen_restored_and_legacy_members.py` — the full-screen login presents and unlocks a restore-fed profile through the real Pilot-driven door, and a retired-manifest member refuses at the login surface. The routes already covered (local notifications reads, local subgroups, archive roundtrip, restore CLI, the eight Pilot login cases) were inventoried and not duplicated.

## Notes

The live pull route is codified, not executed here: it runs only in the live lane with `CADRUMO_LIVE_TESTS_ENABLED=1`; its deselection under the normal lanes is the property asserted today. The route's grounding fields assert envelope shape, never operator data.
