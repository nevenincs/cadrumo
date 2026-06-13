---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W37.P183'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W37.P183`

De-shim / de-stub phase. Confirmed there is no hardcoded festivos
table living inside the CLI surface, and the calendar TOMLs are
the single source of truth.

- Created (within the test for P181): boundary test
  `test_no_hardcoded_festivos_table_in_cli`
  in `src/aeat/domain/deadlines/test_festivos.py`.

## Description

A common anti-pattern across the wider AEAT-tooling ecosystem is to
hardcode a yearly festivos list inside a CLI command module or a
deadline-rendering helper. The ADR rejects this pattern because:

- It forks the truth source — one list inside the CLI, another in
  the domain — which the ADR explicitly forbids.
- It hides the BOE citation behind code instead of data, so future
  agents cannot audit which Resolución a holiday came from.
- It blocks the OSS / IOSS exception list from being data-driven.

The boundary test `test_no_hardcoded_festivos_table_in_cli`:

- Walks `src/aeat/entrypoints/cli/`.
- Searches for the structural patterns of a hardcoded calendar
  (named `FESTIVOS`, `HOLIDAYS`, a literal "Viernes Santo" string,
  a `date(YYYY, M, D)` constructor inside the CLI tree, or any
  hand-written list of Spanish holiday names).
- Asserts none are present. Any hit fails the test with the offending
  file path.

P183 also confirms there is no pre-existing shim that re-exports a
festivos surface from a non-domain module. The grep audit ran clean;
the only public exporter is `src/aeat/domain/deadlines/__init__.py`,
added in P181.

No prior stub functions exist (the substrate is new in this wave),
so the de-stub limb is vacuously satisfied. The boundary test is the
forward guard.

Closed plan rows: `W37.P183.S1093`, `W37.P183.S1094`,
`W37.P183.S1095`, `W37.P183.S1096`, `W37.P183.S1097`,
`W37.P183.S1098`.

## Tests

`uv run --no-sync pytest src/aeat/domain/deadlines/test_festivos.py
-k no_hardcoded_festivos_table -q` — 1 / 1 pass.
