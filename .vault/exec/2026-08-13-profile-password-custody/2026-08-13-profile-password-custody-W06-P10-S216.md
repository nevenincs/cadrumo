---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0c615cecc6764fa524706ba31b2bc3f044b09b77b543b37e0cb17cc1e654bcde'
step_id: 'S216'
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
     The S216 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Migrate all remaining direct registration callers and their shared test provisioning doors to supply and verify recovery instead of constructing password-only profiles and ## Scope

- `src/cadrumo/tests/ and src/cadrumo-harness/src/cadrumo_harness/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate all remaining direct registration callers and their shared test provisioning doors to supply and verify recovery instead of constructing password-only profiles

## Scope

- `src/cadrumo/tests/ and src/cadrumo-harness/src/cadrumo_harness/`

## Description

- Inventory every direct registration call across the application tree, CLI/TUI tests, storage tests, shared test support, and the harness.
- Supply each ordinary caller with a real handoff that returns the minted enrollment mnemonic, retaining words only where the test needs them.
- Preserve the deliberate missing, mismatched, and raising handoff controls at the application recovery boundary.
- Recursively scan executable modules and embedded child-interpreter source for missing or `None` recovery handoffs.
- Collect all migrated test modules and exercise representative application, storage, CLI, and harness lanes.

## Outcome

Every ordinary `register_profile_with_credentials` caller visible in the live tree now supplies exact recovery proof. The recursive inventory found 136 direct executable-tree calls plus an embedded child-interpreter call; the sole missing handoff is the intentional TypeError control proving that the application parameter is mandatory. No explicit `None`, conditional-`None`, or mnemonic-free lambda handoff remains.

The migrated test corpus collected successfully. A representative eighty-eight-test application/storage/CLI/harness run produced eighty-four passes: two failures are stale optional-recovery assertions assigned to S217, and two are unrelated concurrent capability-output expectations. The embedded-source regression test passes independently. Scoped Ruff is clean across every direct-caller module, and formal re-review reports no remaining CRITICAL, HIGH, or MEDIUM findings.

## Notes

The broad scoped type check reports existing diagnostics in test-only lazy facade annotations and unrelated concurrent test work; its only recovery diagnostics are the deliberate missing-argument and raising-callback negative controls. Comprehensive behavioral reauthoring of tests that assert recovery absence remains S217 rather than being hidden inside this mechanical caller migration. Formal review found one call hidden inside an embedded child-interpreter program that the first AST sweep could not see; the recursive scan and exact integration gate now cover that lane.
