---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
  - '[[2026-05-04-live-filing-data-capture-research]]'
  - '[[2026-05-04-calculation-truth-registry-phase-0c-review-audit]]'
---



# `calculation-truth-registry` `phase0c` `step2`

Completed live Modelo 130 submitted-file capture after Cl@ve reauthentication
and tightened observation storage path privacy.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_observation_store.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Modified: `.vault/audit/2026-05-04-calculation-truth-registry-phase-0c-review.md`

## Description

Reauthenticated with Cl@ve Movil and captured one read-only Modelo 130 filed
declaration for ejercicio 2024 and period 1T. The live observation persisted
three encrypted financial artefacts and decrypted through the store API as 19
casilla observations sourced from `submitted_file` with extraction coverage
`1.0`.

The first live recapture showed that observation manifest paths still included
filing metadata. The capture directory was deleted after path-containment
verification, the store was changed to use opaque hashed observation paths, and
the live capture was rerun. The final capture path no longer embeds modelo,
period, or expediente values.

The remaining Phase 0C live binding gate stays open because Modelo 130's
previous-filing binding depends on Modelo 100 casillas, and Modelo 100 is not
yet backed by a committed registry/parser snapshot.

## Tests

- `uv run aeat auth login --provider clave_movil`
- `uv run aeat app registry capture-filed-data --modelo 130 --ejercicio 2024 --period 1T --limit 1 --output-root var\aeat\filed-declarations --json`
- Store API verification confirmed 19 submitted-file casillas, three encrypted
  artefacts, and extraction coverage `1.0`.
- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_observation_store.py -q`
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_observation_store.py src/aeat/adapters/outbound/aeat/sede/test_observation_store.py`
- `uv run ty check src/aeat/adapters/outbound/aeat/sede/_observation_store.py src/aeat/adapters/outbound/aeat/sede/test_observation_store.py`
