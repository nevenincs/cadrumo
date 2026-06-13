---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# audits-resolution group-c step-6

## scope

Plan row C6: trim `aeat --version` to a single line; move the
existing comprehensive registry summary behind a new `--detail`
flag.

## changes

`src/aeat/entrypoints/cli/__init__.py`: the root callback gains an
eager `--detail` boolean option. When `--version` runs without
`--detail`, the callback echoes `f"{package_name} {package_version}"`
(one line). With `--detail`, it echoes the existing
`render_cli_version_text` output.

Locale catalogues `es / en / ca / hu` gain
`cli.root.detail_help` and reflow `version_help` to point at the
new flag.

## verification

`aeat --version` emits `aeat 0.1.0` on one line.
`aeat --version --detail` emits the full report with registry
revisions, modelo count, casilla count, and formula count.

Pre-existing test_cli_surface failures touching unrelated `app
<command>` surfaces are concurrent-agent territory (the cli-redesign
stream renamed several commands and owns the test updates); they
reproduce without the C6 changes.
