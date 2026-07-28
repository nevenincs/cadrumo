---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S152'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S152 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Replace sandbox-use identity gating with canonical config switch handling and ## Scope

- `src/cadrumo/entrypoints/mcp/_identity_gate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace sandbox-use identity gating with canonical config switch handling

## Scope

- `src/cadrumo/entrypoints/mcp/_identity_gate.py`

## Description

- Read the MCP identity gate and confirm the identity-changing verb set uses the canonical switch grammar.
- Confirm no sandbox-use gating survives.

## Outcome

The gate is keyed on the canonical switch grammar. The closed set of active-identity-changing verbs is login, profile create, and logout, and the site records that login is what enters a sandbox, by its canonical label, so no separate sandbox-use door is gated or needed.

The reasoning at the site is precise about scope: editing or renaming the current profile does not change who is active and so deliberately does not re-arm the gate, while a profile switch does. The identity-read set that clears the gate is equally explicit, and the console harness read is admitted with a recorded rationale that it already surfaces the active identity.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
