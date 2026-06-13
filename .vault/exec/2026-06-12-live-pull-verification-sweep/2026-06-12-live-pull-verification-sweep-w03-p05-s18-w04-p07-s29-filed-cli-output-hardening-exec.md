---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S18,S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W03.P05.S18 / W04.P07.S29 - filed CLI output hardening

## Scope

Harden the filed CLI text output for `list`, `pull`, and `pull-sources` so operators can see the capture mode, target, failure count, justificante metadata count, and filing-evidence stamp/conflict counts without requiring JSON output.

## Description

- Centralize filed capture text metrics for single, bulk, and source-observation pull reports.
- Add `mode`, single target modelo/year, bulk year range/model count, source target modelo/year/period, and `failed_count` to text output.
- Preserve existing JSON payload fields for justificante metadata, filing evidence stamps, conflicts, observation paths, artefact refs, and calculation observations.
- Add focused tests built from the real report models rather than mocks or patched live calls.

## Outcome

The local CLI output path now exposes the evidence-enrollment state that matters for calendar/modelo reconciliation:

- single `filed pull` reports `mode=single`, target modelo/year, `failed_count=0`, justificante CSVs, filing evidence stamps, conflicts, observation paths, and artefact refs;
- bulk `filed pull` reports `mode=bulk`, model count, year range, failure count, and typed period failure rows while preserving the `pull` surface instead of introducing `pull-all`;
- `filed pull-sources` reports target modelo/year/period and the same justificante/filing evidence counters.

This is local CLI hardening only. `W03.P05.S18` remains open until authenticated live `filed list`, `filed pull`, and `filed pull-sources` are exercised through the backend path.

## Verification

- `python -m ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests/test_registry_cli.py`: passed.
- Focused filed CLI output and command-tree tests: 6 passed.
- Full `src/aeat/entrypoints/cli/tests/test_registry_cli.py`: 59 passed.

## Notes

The live-auth pytest lane in `W02.P03.S09` still fails on operator-mediated Clave completion, so this execution record deliberately does not claim live filed command acceptance.
