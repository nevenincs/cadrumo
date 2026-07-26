---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S294'
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
     The S294 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Land the proven MCP identity seeding fix once the wizard results module is committed, so both transports report the same schema count and the parity assertion is no longer comparing two equally blind sets and ## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`
- `src/cadrumo/entrypoints/mcp/_harness_tools.py`
- `src/cadrumo/application/wizard/_compiler.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Land the proven MCP identity seeding fix once the wizard results module is committed, so both transports report the same schema count and the parity assertion is no longer comparing two equally blind sets

## Scope

- `src/cadrumo/entrypoints/mcp/_server.py`
- `src/cadrumo/entrypoints/mcp/_harness_tools.py`
- `src/cadrumo/application/wizard/_compiler.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Land the proven identity fix once its blockers cleared, and confirm it owes the
unsanctioned-import ratchet nothing.

## Outcome

SATISFIED. Landed at `0918c3f7a7`.

Both blockers dissolved rather than being negotiated away. The transport
divergence ended when a peer bridged the schema-name filter; the parity suite
passes 8 of 8 at the landing HEAD. The ratchet blocker ended by better
engineering: the held version reached the seeding authority through two
deferred function-local imports, which would have moved the ratchet and
required an allowlist entry plus a ceiling raise, and that was authorised. The
landed version imports at module level in both call sites instead.

Confirmed by inspecting the commit rather than trusting the instruction: it adds
zero function-local imports and removes none, so it contributed nothing to the
domain cycle-break count and correctly touched no ceiling.

The ratchet's residual red - 52 live sites against a ceiling of 50, and two
ceilings carrying slack - is therefore entirely peer drift with nothing
attributable to this campaign.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
