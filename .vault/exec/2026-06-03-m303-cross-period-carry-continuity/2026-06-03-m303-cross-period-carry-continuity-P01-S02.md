---
tags:
  - '#exec'
  - '#m303-cross-period-carry-continuity'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-03-m303-cross-period-carry-continuity-plan]]'
  - '[[2026-06-03-m303-cross-period-carry-continuity-adr]]'
---

# `m303-cross-period-carry-continuity` `P01.S02` exec — Hypothesis identification

## Action

Name the broken step.

## Finding

Per the P01.S01 read-before-act discovery, the diagnostic resolves to **Hypothesis C variant**: cross-step semantic change that preserves per-period totals (`iva.cuota-devengada-total` / `iva.cuota-deducible-total`) but redirects the engine's read path. Commit `2677c82d6` repointed `iva.resultado-regimen-general` from the form-number casillas 27/45 to the computed semantic totals; the engine refuses inputs against computed casillas. The test's pre-`2677c82d6` injection path (casilla 27/45 manual inputs) silently dropped, devengada/deducible totals fell to zero, régimen-general result fell to zero, no credit was generated, the saldo collapsed to zero, and `carried_saldo > 0` fired.

The chain at HEAD with the corrected per-rate cuota binding injection produces a non-zero saldo end-to-end; no registry-level or engine-level edit is required.

## Phase-2 branch

**None.** The carry chain is intact at the registry/engine layer; only the test fixture needed to switch from `casilla_inputs={"27": ..., "45": ...}` to `cuota_binding_overrides={"modelo-303-iva-repercutido-general-cuota": ..., "modelo-303-iva-soportado-interiores-cuota": ...}`. Peer commit `c2e05f644` executed this rewire on 2026-06-04.
