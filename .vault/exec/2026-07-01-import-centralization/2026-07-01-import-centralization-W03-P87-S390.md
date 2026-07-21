---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S390'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Drop the dead OutputLanguage re-export from entrypoints.cli._config.__all__, confirming no live consumer imports it from that facade before removing it (the canonical source is aeat.core.i18n)

## Scope

- `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

- Confirmed via grep that no production or test consumer imports `OutputLanguage` from `entrypoints.cli._config` — the only re-export path was the `__all__` entry itself; every Typer option annotation inside the module uses the type internally, not through the facade re-export.
- Removed the `"OutputLanguage"` entry from `__all__`, keeping the internal `from ....core.external_constants import OutputLanguage` import (still used for the module's own Typer option type annotations).
- `aeat.core.i18n` remains the sole canonical facade for `OutputLanguage`, unaffected by this change.

## Outcome

Committed alongside S364, S368, S369, and S388 in one commit (`b6aafa707`). `pytest --collect-only -q src/aeat` clean; no consumer breakage since nothing imported it from this facade.

## Notes

None.
