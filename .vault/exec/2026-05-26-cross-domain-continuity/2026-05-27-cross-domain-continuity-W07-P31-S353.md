---
step_id: S353
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# S353: M100 casilla 0505 formula derivation

## Outcome

Casilla 0505 (base liquidable general sometida a gravamen) is now computed
via formula `renta-2024/2025-base-liquidable-general-sometida-a-gravamen`:
`max(0, [0500] - [0527])`. Before the fix the casilla was manual; when not
supplied the engine used 0 and cuota integra silently became 0.

## Commits

`94b424c6b` — S353: add renta-2024/2025-base-liquidable-general-sometida-a-gravamen formula  
`eb8793d07` — S353: regression tests for casilla 0505 computed formula + migrate leaf inputs

## Changes

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0168-renta-2024-base-liquidable-general-sometida-a-gravamen.toml` (NEW): Formula `max(0, [0500]-[0527])`, legal_refs ley-35-2006:art-56/art-50, source_refs lirpf-cuota-chain-authority.
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0177-renta-2025-base-liquidable-general-sometida-a-gravamen.toml` (NEW): Same expression with 2025 prefix, adds art-49/rd-439-2007:art-109/orden-hac-277-2026:art-3.
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0487-0505.toml`: Added `input_kind = "computed"`, `formula = "renta-2024-base-liquidable-general-sometida-a-gravamen"`, `ley-35-2006:art-56` in legal_refs.
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0571-0505.toml`: Same casilla change for 2025 revision.
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0001-renta-cuota-chain.toml`: Registered new formula after `renta-2024-base-liquidable-general`.
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/constructs/0001-renta-cuota-chain.toml`: Registered new formula; added `lirpf-cuota-chain-authority` to construct source_refs.
- `src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`: 3 new tests (S353 oracle, anualidades reduction, anti-tautology). 7 existing tests migrated from `inputs={"0505": ...}` (rejected — computed casilla) to `inputs={"0003": 35400}` (leaf manual casilla trabajo ingresos integros that produces 0500=35400 through chain).

## Legal authority

LIRPF Art. 56 para. 1: base liquidable general sometida a gravamen = base
liquidable general menos las reducciones (anualidades por alimentos, Art. 50).
Operand 0527 = sum of casillas 1741/1744/1749/1754/1759 (already computed).

## Gates

- 10/10 tests pass in test_modelo_100_tarifa_real.py
- ruff: 0 errors on modified file
- Registry snapshot builds cleanly for 2024 and 2025 (source citation validation passes)
