---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S394'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# reconcile Convenio Espana-Marruecos follow-up: current registry has `MA/interest` at 0.10 grounded in `convenio-es-ma-1978:art-11` / BOE-A-1985-9280, not the old Art 14 anchor

## Scope

- `remaining scope is any MA/general row decision and the 183-day advisory location if still required`
- `leave unchecked until a matching exec/close record reconciles this historical step`
- `src/aeat/_data/registry/aeat/modelos/210/`

## Description

- Ground the follow-up with `uvx vaultspec-rag search "MA interest convenio-es-ma-1978 art-11 m210 convenio rate missing Marruecos" --type code --limit 10 --port 8766 --timeout 30`.
- Inspect the plan row, `src/aeat/_data/registry/aeat/treaties/es-ma.toml`, the focused M210 convenio-rate tests, and the M210 2025 registry rate/binding/formula/verification files.
- Confirm the current treaty authority has only `MA` / `interest`, kind `ceiling`, rate `0.10`, and legal refs anchored to `convenio-es-ma-1978:art-11` / `BOE-A-1985-9280`.
- Confirm the old `BOE-A-1985-13340` / Art 14 drift is no longer present in the scoped M210 and treaty surfaces.
- Confirm no model-local `m210-convenio-rates` table or stale `MA/general` row remains under Modelo 210; current missing-row behavior is the explicit blocking path for a treaty country without a matching income-type override.
- Confirm the only current Modelo 210 days field is `dias_imputacion` for imputed real estate, not an unresolved 183-day treaty-residence advisory.

## Outcome

No code or registry data edits were required. The historical follow-up is reconciled by the current implementation: `MA/interest` resolves to the 10 percent treaty ceiling through the cross-cutting `ConvenioAuthority`, the legal catalogue cites the bundled Morocco treaty Article 11 source, and the focused regression suite pins the corrected Article 11 anchor plus the Khadija `MA` / `interest` rate path.

Validation passed:

- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py -q` passed, 17 tests.

## Notes

- External BOE context supplied by orchestration agrees with the local source authority: `BOE-A-1985-9280` Article 11 caps Spain-Morocco source-state tax on gross interest at 10 percent.
- Residual scope remains outside this row: full Modelo 210 treaty roster and broader income-type expansion stay tracked by the Phase 2 M210 engine row, not by this historical Morocco correction.
