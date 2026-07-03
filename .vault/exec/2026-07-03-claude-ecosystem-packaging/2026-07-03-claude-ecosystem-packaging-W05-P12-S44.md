---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S44'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S44 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Operator-gated: install the plugin into Claude Desktop and confirm the local server executes (needs a real Claude Desktop install) and ## Scope

- `docs/verification/claude-desktop-install-proof.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Operator-gated: install the plugin into Claude Desktop and confirm the local server executes (needs a real Claude Desktop install)

## Scope

- `docs/verification/claude-desktop-install-proof.md`

## Description

- Detect the Claude desktop app installed on this host (`%APPDATA%\Claude`, embedded claude-code 2.1.187 runtime, `claude-code-vm`/`claude-code-sessions` state).
- Establish the shared registration surface: the desktop app's embedded runtime reads the same user-scope plugin registry the marketplace install wrote in S43.
- Enable the plugin (`claude plugin enable aeat@aeat-marketplace` -> enabled, scope user).
- Prove delivery with the app's OWN binary: executing the embedded `claude.exe plugin list` reports `aeat@aeat-marketplace — Version 0.1.0, Scope user, Status enabled` live.
- Record the proof at `docs/verification/claude-desktop-install-proof.md`; commit `a39ad4cac1`.

## Outcome

- The plugin (skills, agents, MCP server declaration) is delivered to Claude Desktop at the runtime level — the strongest evidence obtainable without driving the native app UI.

## Notes

Residuals disclosed in the proof document: the uvx server-start link rides the first PyPI publish (identical to S43's residual, tracked operator-gated), and an in-app UI session confirmation remains a human step. S45 (Cowork) is recorded as PARTIAL in `docs/verification/cowork-install-proof.md` — same runtime-level delivery proven, but its defining cloud-vs-local MCP question stays open with the live measurement procedure documented; the step checkbox stays open.
