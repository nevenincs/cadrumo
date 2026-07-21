---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S19'
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
     The S19 and 2026-07-17-all-profile-reset-plan placeholders are machine-filled by
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
     The Remove the config profile sandbox use registration and execution path without an alias and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_sandbox.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove the config profile sandbox use registration and execution path without an alias

## Scope

- `src/cadrumo/entrypoints/cli/_config/_sandbox.py`

## Description

- Delete `_register_sandbox_use_command` and its registration from `_sandbox.py` with no alias (no-legacy hard cut).
- Delete the `ConfigProfileSandboxUseResult` schema and its `config.profile.sandbox.use` registration from `_config_sandbox_payloads.py`.
- Remove `config.profile.sandbox.use` from the operator-surface `_risk_table.py` and from the MCP `_identity_gate.py` active-identity-changing set; correct the two docstrings naming the removed door (`_common.py`, `_identity_gate.py`).

## Outcome

The second sandbox-selection door is gone across code, JSON schema, risk metadata, and the MCP identity gate; `switch` (S18) is the sole selector. Sandbox-CLI suite green (44 passed); schema-conformance, custody-lifecycle, and MCP suites green (420 passed); operator-surface risk suite green (56 passed). Locale keys for the removed verb are dropped in S28 through the locales CLI.

## Notes

Sandbox entry is now `config switch sandbox:<name>` (canonical label) — the removed `use` had no independent authority, delegating to the same select-lifecycle-span primitive `switch` uses.
