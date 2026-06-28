---
step_id: S35
tags:
  - '#exec'
  - '#calculation-engine-foundations'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-10-calculation-engine-foundations-plan]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
---

# `calculation-engine-foundations` `W04.P11.S35` exec

## Step

`W04.P11.S35` — Port M100/2025 casillas 0596/0597 retención-credit folds to 2025 revision; add live E2E proof.

Scope: `registry modelos/100/revisions/2025/casillas + constructs; application/modelo/tests`.

## What was done

Wired M100/2025 casillas 0596 and 0597 to their `relation_prefill` bindings,
mirroring the M100/2024 shape exactly. Added a live E2E proof test for the
2025 revision.

### Registry changes

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0179-0596.toml`
  — added `input_kind = "bound"` and `binding = "renta-2025-modelo-111-retenciones-periodicas"`.
  Legal grounding: LIRPF arts. 17–20, 101 + RIRPF arts. 80, 86 + LIRPF art. 99 +
  Orden HAC/277/2026 art. 3 (BOE-A-2026-7041). Carries the 2025 casilla's
  existing `legal_refs`/`source_refs` unchanged.

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0180-0597.toml`
  — added `input_kind = "bound"` and `binding = "renta-2025-modelo-123-retenciones-periodicas"`.
  Legal grounding: LIRPF arts. 25–26, 101 + RIRPF art. 90 + LIRPF art. 99 +
  Orden HAC/277/2026 art. 3 (BOE-A-2026-7041).

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/constructs/0007-renta-payments-retentions.toml`
  — added `"0596"` and `"0597"` to `casillas` list; extended `legal_refs` with
  the provisions required by those casillas (LIRPF arts. 17–20, 25–26; RIRPF
  arts. 80, 86, 90) — all verified present in `src/aeat/_data/registry/aeat/legal/irpf.toml`.

Casilla 0598 / rel-115 excluded per coordinator deferral (double-count with
manual 0153 path).

### Orphaned bindings resolved

Both `renta-2025-modelo-111-retenciones-periodicas` and
`renta-2025-modelo-123-retenciones-periodicas` were pre-existing `relation_prefill`
bindings without a consuming casilla. They are now consumed by 0596 and 0597
respectively. The two variant relations (`renta-2025-rel-111-retenciones-trimestrales`
and `renta-2025-rel-111-retenciones-mensuales`) both target the same single binding
— the resolver picks whichever set of filings the taxpayer submitted.

### Test

- `src/aeat/application/modelo/tests/test_modelo_100_2025_retenciones_credit_fold_in_live.py`
  — new live E2E proof: four distinct M111/2025 c28 quarters fold into 0596 and
  four distinct M123/2025 c09 quarters fold into 0597 on the real
  `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` path.
  Anti-tautological (seeds: M111 totals 155+320.75+88.50+445.25=1009.50;
  M123 totals 15.60+72.30+8.40+51.70=148.00; mutually distinct).
  Real-adapter (real encrypted-SQLite, real registry authority, real
  `RelationPrefillSourceResolver`, no mocks/stubs/skips/xfail).
  Profile `display_name` matches `isolated_runtime_profile` manifest label so
  `ProfileAggregate` validates cleanly when the 2025 `ledger_renta_expense_aggregation`
  preflight path loads it. Ledger-locked binding sources excluded from
  `binding_values` to pass the engine's source-lock guard.

## Legal grounding carried

All `legal_refs` on 0596/0597 and the construct reference provisions in the
irpf.toml legal catalogue with `corpus_ref` entries (verified by
`python -c "import tomllib; ..."` prior to commit). `orden-hac-277-2026:art-3`
binds to BOE-A-2026-7041 and is the 2025 annual IRPF form approval order.

## Verification

- Registry validation: `python -c "from aeat.core.resources import resources; resources()"` — clean.
- `pytest --collect-only -q` — 14 418 collected, no errors.
- New proof test: `pytest src/aeat/application/modelo/tests/test_modelo_100_2025_retenciones_credit_fold_in_live.py -v` — 1 passed.
- Full modelo suite: `pytest src/aeat/application/modelo/tests/ -q` — 443 passed.
- Linter: `ruff check` clean; `ty check` clean on new test file.
- `python -m dev.docs.apidocs scaffold --check` — pre-existing drift for peer
  agent's `_justificante.py` (not authored here); no new drift from this step.

## Commit

`39dac2e2a feat(registry): port M100 0596/0597 retencion credit folds to 2025 + live proof (W04.P11.S35)`

4 files changed, 378 insertions, 1 deletion.
