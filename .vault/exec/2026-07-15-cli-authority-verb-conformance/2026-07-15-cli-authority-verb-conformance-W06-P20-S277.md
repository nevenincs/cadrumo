---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S277'
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
     The S277 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Seed the profile-key registry on the MCP path itself rather than relying on a wizard import side effect, and prove whoami through a real stdio subprocess client and ## Scope

- `src/cadrumo/entrypoints/mcp/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Seed the profile-key registry on the MCP path itself rather than relying on a wizard import side effect, and prove whoami through a real stdio subprocess client

## Scope

- `src/cadrumo/entrypoints/mcp/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Seed the profile-key registry from an initialisation point the MCP entrypoints
actually execute, rather than relying on a wizard import side effect.

Prove the fix against a real server process, not a passing in-process test.

## Outcome

SATISFIED. Landed at `0918c3f7a7`, four files.

The registry had exactly two seeding points, both test conftests, neither
reachable from the MCP or CLI-config trees, and every production wizard import
is function-local under the lazy-import policy. So nothing seeded it in a
shipped process. The fix promotes the CLI's existing private helper to a
documented idempotent public symbol and calls it at the server's initialisation
point and inside the identity reader itself - one authority, two call sites,
not a second mechanism.

Acceptance evidence, to the standard set before the work began: a real
`cadrumo-mcp` stdio subprocess spawned outside pytest returned
`isError=False` for both `cadrumo_whoami` and `cadrumo_harness_load`, with a
rendered identity payload. The clean-interpreter probe that originally proved
the defect inverted: the wizard stays absent and the read returns keys instead
of raising. Twelve of the twelve identity failures pass.

A third conftest import would have turned all twelve green and left the shipped
server broken. That trap was named in advance and avoided.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
