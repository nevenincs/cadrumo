---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
---

# audits-resolution group-e step-2

## scope

Plan row E2: final repo-wide verification sweep.

## results

### audit_cli_translations / audit_wizard_translations

```
cli missing: ()
wizard missing: ()
```

Both audits return the empty tuple — every CLI-referenced
translation key and every wizard descriptor key resolves cleanly in
every locale.

### locale-key discovery contains expected entries

```
año_help: True               # cli.filing.import.año_help present
cli.registry.metrics.*: True # namespace marker emitted by AST scanner
wizard.errors.* : True       # programmatic-emission namespace marker
```

### wizard command derivation

`inspect.signature(build_wizard_command(SETUP_FLOW))` reports
**42** parameters, matching ADR §D and the wizard-ux audit's
flag-count contract.

### aeat --version trim

```
$ aeat --version
aeat 0.1.0
```

One line. `aeat --version --detail` preserves the existing full
registry summary (25 modelos, 14952 casillas, 1039 formulas).

### aeat --help cardinality

```
Commands
  config   Gestionar configuración local y diagnósticos
  app      Espacio de trabajo fiscal para overview, ledger, modelo,
           registry y review
```

Exactly `config` and `app`. CLI root cardinality preserved.

### prek run --all-files

`ruff check`, `ruff format`, `ty check` all green on every file
audits-resolution touched. A pre-existing concurrent-agent ruff
finding in `entrypoints/cli/financial/txs.py` (an F401 import that
fired after another agent reordered the module) reproduces against
the clean checkout and is owned by that stream.

## concurrent-agent pre-existing failures flagged

The following failures are concurrent-stream territory (the CLI
workflow redesign, error registry hardening, and Renta WEB Open
ingest streams all landed commits during the audits-resolution
pipeline). They were not introduced by audits-resolution work and
reproduce against snapshots of HEAD without the audits-resolution
diff:

- `src/aeat/application/auth/test_authenticator.py` — circular
  import in `aeat.adapters.outbound.aeat.auth.__init__` blocks
  collection. Concurrent-stream auth package refactor.
- `src/aeat/entrypoints/cli/test_cli_surface.py` — 7 test failures
  asserting against renamed `aeat app <command>` surface tokens.
  Concurrent CLI rename owner.
- `src/aeat/entrypoints/cli/test_config_setter.py::test_config_help_lists_the_new_surfaces`
  — asserts the old `setup` CLI verb name; concurrent stream
  renamed to `init` and owns the test update.
- `src/aeat/entrypoints/cli/financial/test_cli.py` — 3 ingest
  test failures from concurrent-agent error-message shape changes.
- `src/aeat/entrypoints/cli/financial/test_profile.py::test_corrupt_file_surfaces_error_not_silent_empty`
  and `test_operator_success_moment_end_to_end` — tests asserting
  file-backed behaviour against the SQL-backed substrate the
  eliminate-shims audit explicitly flagged as the design.
- `src/aeat/application/filing/test_complementaria.py` and
  `test_modelo_303_390.py` — concurrent-stream registry
  calculation drifts ("computed registry casillas cannot be supplied
  as inputs"). Owned by the registry stream.
- `src/aeat/adapters/outbound/aeat/sede/test_declarations.py::test_modelo_100_relations_resolve_from_standardized_filed_observations`
  — concurrent ledger-renta-pipeline territory; Renta WEB Open
  filed-declaration shape drift.
- `src/aeat/entrypoints/cli/financial/txs.py` ruff F401 —
  concurrent-stream import-reorder fallout.

These pre-existing failures are flagged here for the orchestrator's
review per the plan's "concurrent-agent pre-existing failures flagged
but not fixed" gate.

## audits-resolution scope verification

Every HIGH and MEDIUM finding from the three source audits closed
end-to-end (Group A through Group D). The LOW findings folded into
the relevant groups where adjacent
(`__all__` private leak, the InventoryValuationJson double-
registration disproof, the four LOW UX wizard polish items absorbed
into Group C). No HIGH or MEDIUM finding from the three source
audits survives.

The CI tautology gate landed in commit `f98ae451` continues to
enforce that no new tautological calculation tests can re-introduce
the antipattern; D1 / D2 confirmed it passes against the chain-
behaviour and ledger-iva-aggregation surfaces.
