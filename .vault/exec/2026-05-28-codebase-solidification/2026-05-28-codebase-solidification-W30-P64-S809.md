---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S809'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# Add `-n auto --dist=loadfile` to the pytest default addopts in pyproject.toml. Precondition: S804 has landed so module-scoped fixtures actually reduce work across workers. Verify each worker pays the registry compile once via lru_cache. Estimated savings: 4-6x sequential time on an 8-core box

## Scope

- `pyproject.toml`

## Description

Add `-n auto --dist=loadfile` to the pytest default `addopts` in `pyproject.toml`, ahead of the existing `--tb=short -m 'unit' --strict-markers --ignore=...workbook_parity` flags. The `--dist=loadfile` grouping keeps every test in one file on one worker, which is required so the module-scoped secure-storage runtime fixtures from S804 (and the per-file registry `lru_cache`) pay their setup once per file rather than being split across workers. Precondition S804 has landed (filing + ledger module-scoped teardown, storage dead-fixture removal).

## Outcome

S809 landed and verified. A representative `-n auto --dist=loadfile` slice over the registry authority suite plus the two S804 app dirs (filing, ledger) ran 3820 passed in 142s with the xdist workers active and no registry-compile blowup, confirming each worker pays the registry `lru_cache` compile once (criterion a). A default-config run with no explicit `-n` flag prints `bringing up nodes...`, confirming xdist now activates from the addopts config alone.

No new failures beyond the known peer reds (criterion b): the slice showed 10 failures; re-running all 10 sequentially (per the aeat-local-execution loader-cache-race guidance) left 8 failing and 2 passing. The 8 fail regardless of parallelism and are owner-distinguished pre-existing peer reds — the registry-validator complexity breach (`_validate_surfaces.py` 720 lines exceeds the 644 baseline) and the bundled-resource sha256 / corpus-grounding drift (`test_modelo_202` order-chain sha, `test_record_design_completeness` 14≠12, `test_modelo_210`/`test_modelo_349` corpus-backed, `test_catalogue_verification_normatives` orden BOE). The 2 that passed sequentially (`test_retencion_clave_hardening`) were NOT a parallel race: the traceback showed a stale `clave=RetencionClave(clave)` source line while HEAD carries the peer fix `d9402f8b02` (`clave=clave` + mode="before" validator) — pure version skew, the peer fix having landed between the slice run and the sequential re-run. Re-running `test_retencion_clave_hardening` under `-n auto` at HEAD passes (6 passed), so no genuine loader-cache race surfaces (criterion c).

Plan step `W30.P64.S809` marked complete via the CLI, closing the final phase of the codebase-solidification epic's W30.P64 performance cluster.

## Notes

SHARED BLAST RADIUS (load-bearing): this change flips the DEFAULT test execution for every concurrent agent in this shared worktree from single-process to `-n auto` xdist. Any agent running a bare `pytest` now gets parallel execution. Two consequences agents must know: (1) the aeat-local-execution loader-cache-race guidance now applies to the DEFAULT run — a registry-suite failure under the default should be re-run sequentially (`-p no:xdist` or `-n0`) before being triaged as a real regression; (2) background pytest capture must continue to write the full log to disk (per aeat-pytest-background-capture), as xdist interleaves worker output. The user explicitly approved this shared-config change (durable authorization) after the S809 blast-radius go/no-go was surfaced.

Version-skew hazard observed and resolved: a peer test-file fix (`d9402f8b02`) landing between the slice run and the sequential re-run produced 2 phantom parallel-only failures that were neither a race nor a regression. Re-reading HEAD and re-running at HEAD (per the swarm re-read-HEAD discipline) resolved them to green.
