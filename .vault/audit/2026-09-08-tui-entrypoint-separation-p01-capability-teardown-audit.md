---
tags:
  - '#audit'
  - '#tui-entrypoint-separation'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:af2e60a3935f87c924496e56c253f4bde35850f30daa130dda251c0a53a94a3e'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-entrypoint-separation with a kebab-case feature tag, e.g. #foo-bar.
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

# `tui-entrypoint-separation` audit: `p01 capability teardown`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### p01 capability teardown | {level} | {summary}

     followed by a paragraph carrying the detail. p01 capability teardown is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### retired-tui-refusal-contract | medium | The removed CLI refusal still has a live registry declaration and locale entries

`CliTuiNotImplementedError` was removed from `src/cadrumo/entrypoints/cli/errors.py`, but
`src/cadrumo/core/errors/registry/_entrypoints.py` still declares its
`TUI_NOT_IMPLEMENTED` code. Resolving every entrypoint declaration directly reports that
qualname as missing. The corresponding `errors.refused.refused_tui_not_implemented` locale
key remains in each shipped locale, as do the now-unreferenced root help keys
`cli.root.tui_help` and `cli.operator_surface.help.root.section_frontend_options`. This leaves
P01.S04 incomplete and retains the retired global-request vocabulary in the product locale and
error authorities.

### stale-root-self-test | medium | The root retains a full-screen self-test option whose value is now ignored

`src/cadrumo/entrypoints/cli/_root_command_specs.py` still registers `--self-test` with
`cli.root.self_test_help`, whose copy promises to start the full-screen interface. The matching
`self_test` parameter in `src/cadrumo/entrypoints/cli/_root_cli.py` is no longer read after the
global TUI launch path was removed. The option therefore succeeds without performing its documented
full-screen action. It must be removed with the global request or rehomed, with its behavior and
help, on the forthcoming opaque `aeat app tui` launcher.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
