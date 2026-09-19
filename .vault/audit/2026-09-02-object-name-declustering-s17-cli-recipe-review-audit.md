---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:ec043858dfa2301bc284cbf90a3728568fe07ed0800885ddcc49047782f295c4'
related:
  - "[[2026-09-02-object-name-declustering-adr]]"
  - "[[2026-09-02-object-name-declustering-plan]]"
---
# `object-name-declustering` audit: `S17 CLI recipe review`

## Scope

Read-only review of `W03.P08.S17`: the new `fix-object-names` Just recipe, its
operator discovery metadata, and its argument forwarding into the approved
object-name declustering CLI.

## Findings

### argument-forwarding | medium | Variadic interpolation loses shell argument boundaries

The original recipe interpolated `{{ARGS}}` directly into a shell command. A
`just --dry-run` probe with the single argument `receipt with spaces.json` rendered
it as three unquoted tokens, so receipt and manifest paths containing spaces did not
reach the CLI exactly on Windows.

Resolved on re-review. The recipe now uses Just positional arguments with a
PowerShell script recipe and forwards `@args` directly to `uv`. Live refusal probes
proved that `mode with & spaces` arrived at argparse as one exact argument and that
`receipt with spaces.json` plus `sha256:a&b` arrived without splitting or shell
execution. The script explicitly propagates `$LASTEXITCODE`; no-argument invocation
leaves `@args` empty and therefore retains the CLI's default rehearsal.

## Recommendations

Completed: preserve each variadic value as a process argument and retain detector
teeth for no-argument rehearsal, explicit apply, paths with spaces, shell-significant
values, and exact exit propagation.
