---
step_id: S167
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S167 — IVARegime enum surface

## Outcome

Replaced `frozenset({"SIMPLIFICADO"})` with `frozenset({IVARegime.SIMPLIFICADO})` in
`src/aeat/application/modelo/_actions.py:1326`. Added `IVARegime` to the
`from ...domain.deadlines import ...` line.

Added `_iva_regime_choice_values()` helper and `_IVA_REGIME_CHOICE_VALUES` module-level
constant to `src/aeat/application/wizard/_commands.py`, following the existing lazy-import
pattern used for `EntityType`, `IrpfEstimationRegime`, etc. Replaced:
`click.Choice(["GENERAL", "SIMPLIFICADO", "RECARGO_EQUIVALENCIA", "EXENTO"])` with
`click.Choice(_IVA_REGIME_CHOICE_VALUES)` — now covers all 5 `IVARegime` members
(including `REAGP` which was missing from the bare list).

Note: `_actions.py` changes (IVARegime import + frozenset) were absorbed into peer
commit `1aeb3aa41` (S161+S162 InputKind migration). The `_commands.py` change is in
commit `8381a5f9a`.

## Collision check

`git diff` run on all target files before editing. `_actions.py` and `_schema.py`
had uncommitted peer WIP (InputKind migration). My changes were additive and compatible;
the peer agent's commit `1aeb3aa41` landed the `_actions.py` edits concurrently.

## Files touched

- `src/aeat/application/modelo/_actions.py` — 1 site migrated (frozenset)
- `src/aeat/application/wizard/_commands.py` — 1 site migrated (click.Choice), +12 lines
