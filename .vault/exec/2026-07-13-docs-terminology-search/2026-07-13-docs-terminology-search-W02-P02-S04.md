---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:5255c2ef0ed49c5e0090793cbf26044c24a4da55c498492cc6332941a64cf4e2'
step_id: 'S04'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Implement the upstream-schema adapter: serialize the repo PreprocessOutput to the upstream PreprocOutput JSON contract behind a python -m entry point, with unit tests against the pinned schema major

## Scope

- `dev/docs/preprocess/`

## Description

- Implement `dev/docs/preprocess/hook.py`: suffix-dispatched command-form
  adapter over the existing extractor families.
- Collapse multi-part workbook outputs into one upstream document with
  per-unit part provenance; aggregate status worst-wins.
- Emit the pinned upstream PreprocOutput contract (schema major 1) as UTF-8
  bytes on stdout; exit non-zero on unmatched suffix or empty extraction.

## Outcome

Adapter landed in `485ac85614`, no cadrumo imports, lazy extractor
imports. Live `preprocess run-one` initially failed on Windows because
text-mode stdout defaulted to cp1252 while the upstream runner decodes
UTF-8; fixed by writing UTF-8 bytes via `sys.stdout.buffer` and locked with
`test_hook_cli_emits_utf8_json_bytes`.

## Notes
