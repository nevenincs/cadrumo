---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S12'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# Prove expedientes pull fetches authenticated expediente rows with typed empty, timeout, and portal-drift outcomes

## Scope

- `src/cadrumo/application/live/_expedientes.py src/cadrumo/adapters/outbound/aeat/sede`

## Description

- Using the same authenticated Cl@ve Móvil session as S11, ran `app live expedientes pull` against a modelo/year combination known to hold real declarations (`--modelo 303 --year 2024`).
- Ran the same command against a modelo/year combination known to be empty (`--modelo 303 --year 2026`, and `--modelo 347 --year 2024`) to observe the typed empty outcome.
- Read back the persisted snapshot via `app live expedientes latest` and `app live expedientes view <snapshot_id>` to confirm the six declarations round-trip with their real `expediente_id`s.
- Separately, `app live filed pull-sources` (S11) surfaced a real `ERROR_SEDE_NAVIGATION` timeout on the shared sede navigation chain that `expedientes pull` also depends on.

## Outcome

- Non-empty outcome proven: `expedientes pull --modelo 303 --year 2024` returned `declaration_count=6`, `failed_count=0`, a persisted `snapshot_id`, and `source_url="declarations:modelo=303:ejercicio=2024"`. `expedientes view` on that snapshot round-tripped all six declarations with real `expediente_id`, `estado=ALTA`, and `presented_at` fields.
- Empty outcome proven: `expedientes pull --modelo 303 --year 2026` and `--modelo 347 --year 2024` both returned `declaration_count=0`, `failed_count=0` — a typed, non-error success shape distinguishing "authenticated and reached AEAT, zero rows" from a failure.
- Timeout/portal-drift outcome: NOT independently reproduced on `expedientes pull` itself in this sweep. The only live timeout observed on the shared sede navigation chain was on the separate `filed pull-sources` verb (`ERROR_SEDE_NAVIGATION`, "Timeout 15000ms exceeded while waiting for event \"page\""), which shares the underlying navigation/click machinery but is a distinct CLI command. This step's acceptance therefore has two of its three named outcome classes proven directly (non-empty, empty); the timeout/portal-drift class is evidenced only by the adjacent verb, not by `expedientes pull` in isolation.

## Notes

- Given the two-of-three direct coverage, this record documents an honest partial result rather than closing the step on inferred coverage. See the plan-row closure note for the disposition decision.
- Redacted per the sweep convention: only aggregate counts, typed status/error codes, and opaque identifiers (`expediente_id`, `snapshot_id`) are cited.
