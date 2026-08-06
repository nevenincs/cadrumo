---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:185d1b47af55969a451237aa017b1327265331f46091d830ee1e5eeabf5627fc'
step_id: 'S395'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# reconcile Art 25.1.b pension follow-up: current registry implements `m210-pension-tarifa-2025` as a three-tranche bracket table (8%, 30%, 40%) and AR/pension delegates through `DOMESTIC_TARIFF`

## Scope

- `leave unchecked until a matching exec/close record reconciles this historical step`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0004-m210-pension-tarifa-2025.toml`

## Description

- Ground the follow-up with `uvx vaultspec-rag search "m210-pension-tarifa-2025 Art 25.1.b AR pension DOMESTIC_TARIFF" --type code --limit 10 --port 8766 --timeout 30`.
- Inspect the plan row, `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0004-m210-pension-tarifa-2025.toml`, `src/aeat/_data/registry/aeat/treaties/es-ar.toml`, and `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`.
- Confirm `m210-pension-tarifa-2025` is a `bracket_table` grounded in `trlirnr-rdleg-5-2004:art-25.1.b` with brackets `0` to `12000` at `0.08`, `12000` to `18700` at `0.30` with `960` fixed addition, and excess over `18700` at `0.40` with `2970` fixed addition.
- Confirm the Spain-Argentina pension override uses `allocation_domestic_tariff`, has no fixed scalar rate, and carries both `convenio-es-ar-1992:art-19` and `trlirnr-rdleg-5-2004:art-25.1.b`.
- Confirm the focused M210 convenio-rate regression pins the AR/pension `ALLOCATION_DOMESTIC_TARIFF` row and the Felipe AR/pension no-blocking scalar-helper behavior.

## Outcome

- No code, registry, or test edits were required. The historical Art 25.1.b pension follow-up is already satisfied by the current local registry and treaty authority.
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py -q` passed with 17 tests.
- Closed W09.P41.S395 through the vault plan CLI after creating this matching exec record.

## Notes

- Audit note: local registry/source refs are the authority for this closure; the orchestrator-supplied consolidated TRLIRNR Art. 25.1.b context agrees with the same three-tranche pension scale.
- Shared worktree already contained extensive unrelated dirty state; this step did not revert, clean, stage, or commit unrelated files.
