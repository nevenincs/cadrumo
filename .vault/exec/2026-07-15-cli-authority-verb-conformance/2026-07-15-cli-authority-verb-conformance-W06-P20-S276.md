---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S276'
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
     The S276 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Attribute the two P18 failures before any closure, 8 in the passphrase and recovery lifecycle suite and 22 in the MCP parity suite, separating the expected keychain remainder from real defects and ## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/`
- `src/cadrumo/entrypoints/mcp/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Attribute the two P18 failures before any closure, 8 in the passphrase and recovery lifecycle suite and 22 in the MCP parity suite, separating the expected keychain remainder from real defects

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/`
- `src/cadrumo/entrypoints/mcp/tests/`

## Description

- Re-run both failing suites at HEAD rather than attributing the recorded
  counts.
- Establish where the environmental keychain remainder actually lives, so the
  clean result cannot be read as covering it.

## Outcome

SATISFIED. Both failure clusters have cleared, and neither needed attribution
in the end because neither reproduces.

The MCP parity suite was recorded at 22 failed of 279, still 13 failed when
re-run sequentially, so explicitly not a parallelism artefact. Re-measured:
`uv run --no-sync pytest src/cadrumo/entrypoints/mcp/tests/ -n0 -m ""`,
collected 306, exit line `305 passed, 1 skipped in 559.19s`. The failures are
gone. The MCP identity defect that explained most of them - whoami resolving
through a process-global registry nothing on the MCP path seeded - was closed,
and the untracked wizard results module that explained the rest was committed
by its owner.

The passphrase and recovery lifecycle suite was recorded at 8 failed of 131 on
an order dependence. Re-measured: `uv run --no-sync pytest
src/cadrumo/entrypoints/cli/_config/tests/ -n0 -m ""`, collected 206, exit line
`206 passed in 313.02s`. No failures, and no deselection.

THE KEYCHAIN BOUNDARY, checked rather than assumed. The row asks me to separate
the expected keychain remainder from real defects, and a clean run over a suite
that never contained those cases would be a false clean if reported without
saying so. Both runs used `-m ""`, which selects everything - so if the six
os_keychain cases lived in either suite they would have been selected and would
have failed under this logon. They do not live there. Collected tree-wide:
6 of 18450 tests carry the marker, in the user-profile login-session and
strong-logout tests and in the CLI profile-session resume test. All six are
outside both re-measured suites.

So the correct statement is narrow and true: both named clusters are clear, and
the keychain remainder is untouched by that result and remains unverified under
an agent logon, where it fails `WinError 1312` on the network logon rather than
on any code defect.

Gates at HEAD `ce9df7380ca9e1000d3b977b2c7674869d96438d`:

- MCP: collected 306, `305 passed, 1 skipped in 559.19s`.
- Config custody: collected 206, `206 passed in 313.02s`.
- Keychain marker collection: `6/18450 tests collected (18444 deselected)`.

## Notes

The single skip in the MCP run is peer-owned and already attributed elsewhere
in this phase: two skip shortcuts in the MCP stdio-lifetime tests, landed by the
MCP campaign. Skips are barred by this project's own gates, so it is a real
finding - just not this campaign's.

Recorded because the shape recurs: a suite passing 206 of 206 says nothing
about cases that were never in it. The deselection banner is the usual tell,
and here there was none precisely because the cases live in other files. Only
collecting by marker across the whole tree settles where they are.
