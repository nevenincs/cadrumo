---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S01'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# add a test-time conformance gate that pins next-action and failure-hint strings naming a command path to a live command, mirroring the documented-command gate mechanism

## Scope

- `src/aeat/entrypoints/cli/tests/test_self_referential_string_conformance.py`

## Description

Added the D5 hint-string conformance gate beside the documented-command gate,
reusing its `_parse_command_line` / `_resolve_path` / `_validate_command`
machinery (imported from `test_documented_command_conformance`). The gate pins
three authoritative hint-string sources against the live Typer/click tree:

- `ERROR_REGISTRY` `default_suggestion` rows (the copy-paste recovery commands
  the CLI error boundary prints);
- `cli.*` locale leaf strings that embed an `aeat app` / `aeat config`
  invocation;
- Python-literal next-action hints in the workflow engine and verify renderer.

A `_command_span` prose-trimmer extracts the maximal CLI-command prefix from a
sentence-embedded hint (so `aeat config unlock NAME or pass --profile.` is
validated as `aeat config unlock NAME`, not the trailing prose), strips sentence
terminators from tokens, and treats `--help` / `--version` as terminal globals.
A presence test guards against a vacuous pass.

## Outcome

Gate authored. Running it surfaced genuine F5 drift in eight error-registry
recovery suggestions (`casillas --year`, `work list --modelo`, `compare
--years`, `ledger update --set/--reason`, `repair list --namespace`) that name
non-existent options; those were corrected to resolvable forms (recorded under
this phase). With those corrections the hint-string classes pass; verified via
the atomic HEAD-consistent CLI-tree swap (peer WIP across the modelo CLI cluster
transiently breaks live-tree collection).

## Notes

The gate's live-tree walk depends on the CLI tree being importable. A concurrent
peer `OutputLanguageOpt` migration across `_modelo_cli_support.py`,
`_modelo_work_calculate_cli.py`, `_modelo_work_revision_cli.py`, and
`_modelo_work_runs_cli.py` left the working tree mid-refactor and un-importable;
the gate was validated by temporarily restoring that cluster to HEAD (safe
compare-aside per the worktree-safety rule), running green, and restoring peer
WIP byte-for-byte.
