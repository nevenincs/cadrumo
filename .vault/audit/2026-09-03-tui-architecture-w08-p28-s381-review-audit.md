---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:29d15f0d9af604329152d70d0895408e8e20b4db688c4cf251de0eeb6cb370b7'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `W08.P28.S381 Review`

## Scope

Reviewed the S381 Home implementation in commits `9f10eec356`, `3e8bc1b2da`, and `56ae5030b9`, together with the checked S381 plan row and execution record. The review covered projection-only authority, the application-enforced three-action limit and agenda ordering, readiness and evidence-state rendering, responsive single-scroll and keyboard behavior, implicit-network absence, devtools dependency direction, clone removal, and focused quality gates.

## Findings

`HomeScreen` receives one immutable `HomeProjectionV1`, publishes only semantic selection and back messages, and contains no reader, adapter, CLI, filesystem, network, or action invocation. The projection validates the maximum three ranked actions, chronological three-row agenda, and unavailable-count honesty before rendering. The selected layout retains one page scroll owner, no table horizontal overflow, three keyboard tab stops, semantic focus targets, and non-colour textual status. Devtools consumes the production identity/address helpers in the permitted presentation direction, eliminating the duplicate helper bodies without adding an application or runtime authority edge.

### agenda-identity-collision | medium | Duplicate agenda addresses collide in selectable row keys

`HomeProjectionV1` accepts two agenda entries with the same Modelo, year, and period so long as their dates are chronological. `HomeScreen` creates each agenda row key from precisely that natural address through `home_agenda_identity`. A valid injected projection can therefore create duplicate keys, causing ambiguous selection and failed semantic focus restoration. The application projection must reject duplicate agenda natural addresses before the TUI receives them.

Focused evidence passed: `test_home.py` (7 tests), Ruff, ty, and basedpyright. The candidate suite is separately in progress elsewhere in the shared worktree, so this audit does not claim a second concurrent result for it.

## Recommendations

1. Reject duplicate agenda natural addresses at the `HomeProjectionV1` application boundary and add a negative projection test. This restores unique agenda selection and semantic focus restoration.

The planned W08.P29 verification remains the owner of the broader locale, terminal-size, and installed-workbench proof.

