---
tags:
  - '#exec'
  - '#modelo-111-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-111-calc-verify-research]]"
  - "[[2026-04-27-modelo-111-calc-verify-adr]]"
  - "[[2026-04-27-modelo-111-calc-verify-plan]]"
  - "[[2026-04-27-modelo-111-rule-delta-reference]]"
---

# `modelo-111-calc-verify` exec summary

Phase summary for issue `#318` — Tier-L per-modelo
calc-verify-roundtrip for Modelo 111 across 2024 / 2025 / 2026.
Mirrors the M130 reference implementation under issue `#321`.

## Outcome

All Tier-L acceptance criteria from issue `#318` are met. Branch
`feature/318-modelo-111-calc-verify` is ready to PR.

## Per-year casilla inventory

Modelo 111 ships **11 casillas modelled in the formula DAG** (4
computed + 7 user-supplied) out of **21 casillas printed on the BOE
template** (the additional 10 are perceptores + percepciones
extractor-only fields). Identical inventory across 2024 / 2025 / 2026:

| Casilla | Computed | Statute                                       | Formula                               |
| :------ | :------: | :-------------------------------------------- | :------------------------------------ |
| 03      | No       | LIRPF arts. 99-101 (table-driven)             | user input (rendimientos del trabajo)  |
| 06      | No       | LIRPF art. 101 + RIRPF art. 95 (table-driven) | user input (actividades económicas)    |
| 08      | No       | LIRPF art. 101.7                              | user input (premios percepciones)      |
| **09**  | **Yes**  | LIRPF art. 101.7 + RIRPF art. 99              | `0,19 × 08`                            |
| 11      | No       | LIRPF art. 101.2                              | user input (ganancias percepciones)    |
| **12**  | **Yes**  | LIRPF art. 101.2 + RIRPF art. 100             | `0,19 × 11`                            |
| 15      | No       | LIRPF arts. 99-101                            | user input (en especie)                |
| 18      | No       | LIRPF arts. 99-101                            | user input (cesión de imagen)          |
| **28**  | **Yes**  | Instrucciones M111                            | `03 + 06 + 09 + 12 + 15 + 18`          |
| 29      | No       | Instrucciones M111                            | user input (deducción complementaria)  |
| **30**  | **Yes**  | Instrucciones M111                            | `28 - 29`                              |

## BOE source list (citation provenance)

Every `computed=True` casilla cites the wave-67a-corrected mapping:

- **LIRPF (Ley 35/2006), arts. 99 + 101.2 + 101.7** —
  `BOE-A-2006-20764`. Last consolidated update 2026-03-21.
- **RIRPF (RD 439/2007), arts. 99 + 100** — `BOE-A-2007-6820`. Last
  consolidated update 2026-02-28.
- **Orden HAP/2194/2013** (M111 form layout) — `BOE-A-2013-12489`.

No 2025 / 2026 BOE amendment touches the rate-bearing articles. RD
253/2025 (the only 2025 modification to the RIRPF) touched art. 69
(information obligations), not arts. 99-100.

## Audit-citations CLI — before / after

**Before** (pre-`#318`, on `main`):
```
OK  modelo_111.2024                  modelo 111 2024-01-01…2024-12-31  computed=  4  with_citation=  4  coverage=100.00%
OK  modelo_111.2025                  modelo 111 2025-01-01…2025-12-31  computed=  4  with_citation=  4  coverage=100.00%
```

**After** (`feature/318-modelo-111-calc-verify`):
```
OK  modelo_111.2024                  modelo 111 2024-01-01…2024-12-31  computed=  4  with_citation=  4  coverage=100.00%
OK  modelo_111.2025                  modelo 111 2025-01-01…2025-12-31  computed=  4  with_citation=  4  coverage=100.00%
OK  modelo_111.2026                  modelo 111 2026-01-01…2026-12-31  computed=  4  with_citation=  4  coverage=100.00%
```

Aggregate: `computed=114, with_citation=114, coverage=100.00%` (was
110 / 110 pre-`#318`). All three M111 years are blocklist-clean per
`src/aeat/domain/modelos/_citation_registry.py`.

## Mutation harness fingerprint

| Ruleset            | `sub_op` | `percent_rate_param` | `mul_div_scalar` | `brackets_threshold` |
| :----------------- | :------: | :------------------: | :--------------: | :------------------: |
| `modelo_111.2024`  | 1        | 2                    | 0                | 0                    |
| `modelo_111.2025`  | 1        | 2                    | 0                | 0                    |
| `modelo_111.2026`  | 1        | 2                    | 0                | 0                    |

Aggregate kill-rate on the populated M111 surface: **100 %** (well
above the issue-`#338` 90 % floor). 17 M111 mutation tests pass (was
11 pre-`#318`; the 6 new tests are 4 percent-rate cases on
`modelo_111.2026` × 2 directions, 1 operand-swap on
`modelo_111.2026:30`, and 1 kill-rate fingerprint check).

## L1 anchor decision

**Waiver filed** in `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md` per ADR
§D9. Modelo 111 is the autónomo's quarterly *autoliquidación* of
retenciones — every real M111 filing is a private autoliquidación
tied to a specific NIF + quarter, and AEAT does not publish any
specimen Modelo 111 declaración as a normative exemplar. The Tier-L
bar is met via the L3 synthetic generator + extractor round-trip.

## Scope decision

The PR keeps the existing M111 ruleset surface (4 computed casillas:
09, 12, 28, 30). The variable-rate retentions on apartados I / II /
V / VI (rendimientos del trabajo, actividades económicas,
contraprestaciones en especie, cesión de imagen) are user-supplied
because their rates depend on tabla inputs + categoría-profesional
mapping (out of scope for the formula DSL — sub-EPIC
`#305-Modelo-111-full`).

## Files changed

### Source code

- `src/aeat/domain/formulas/_rulesets/modelo_111_2026.py` — **new**, 73
  lines. Structural clone of 2024 / 2025.
- `src/aeat/domain/formulas/_rulesets/__init__.py` — +3 lines
  (`MODELO_111_2026` import, `ALL_RULESETS` entry, `__all__` entry).
- `src/aeat/adapters/inbound/declaracion/_extractors/modelo_111_v2025.py` — extended
  from 60 lines to 113 lines. Adds `Modelo111V2024Extractor` +
  `Modelo111V2026Extractor` sibling classes (post-PR-440 fix).
- `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py` — extended with
  sibling-class imports + registrations.

### Tests

- `src/aeat/domain/formulas/_rulesets/test_modelo_111_2024.py` — **new**, 7
  parametrised cases (happy path + 2024-vs-2025 no-drift + external-
  anchored worked example + zero boundary + premios typo + arrendamiento
  typical + ruleset-id-and-effective-range).
- `src/aeat/domain/formulas/_rulesets/test_modelo_111_2026.py` — **new**, 8
  cases (happy path + 2026-vs-2025 no-drift + external-anchored worked
  example + premios typical + zero boundary + complementaria
  subtraction + arrendamiento typo + ruleset-id-and-effective-range).
- `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py` — +12 lines
  (`modelo_111.2026` row in `EXPECTED_COUNTS`).
- `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py` — +3
  lines (import + two `_ruleset_cases` entries).
- `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py` — +7
  lines (import + one `pytest.param` entry).

### Vault

- `.vault/research/2026-04-27-modelo-111-calc-verify-research.md` — **new**.
- `.vault/adr/2026-04-27-modelo-111-calc-verify-adr.md` — **new**.
- `.vault/plan/2026-04-27-modelo-111-calc-verify-plan.md` — **new**.
- `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md` — **new** (rule-delta
  manifest + L1 waiver).
- `.vault/exec/2026-04-27-modelo-111-calc-verify/2026-04-27-modelo-111-calc-verify-summary-exec.md` —
  **new** (this file).

### Docs

- `docs/coverage/modelos.md` — flipped M111 row to ✅ on calc-verify
  (2024 + 2025 + 2026), tests, and declaración import (2024 + 2025 +
  2026, 21-casilla MVP). Updated provenance line.

## Sibling-coordination note

Three concurrent per-modelo Tier-L branches in flight at PR-open time:

- `feature/326-modelo-303-calc-verify` (IVA Tier-L; ZERO source
  collision).
- `feature/322-modelo-131-calc-verify` (IRPF módulos; ZERO source
  collision).
- `feature/319-modelo-115-calc-verify` (IRPF rent retention; closest
  pattern twin; ZERO source collision).

Soft collisions on three shared files at PR-open time:

- `tests/integration/test_kent_workflows.py` — different test class
  (`TestKentImportsModelo111Declaracion`); no edit in this PR (the
  class was already at the Tier-L bar via `#340`).
- `docs/coverage/modelos.md` — different row (M111); textual union
  is mechanical.
- `src/aeat/domain/formulas/_rulesets/__init__.py` — different ruleset
  register (`MODELO_111_2026`); textual union is mechanical.

Coordination at PR-open time: the soft collisions resolve via
mechanical textual union — each sibling branch flips its own row,
adds its own ruleset, and the integration test class is untouched
in this PR.

## Verification gates

All gates green at HEAD:

- `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_111_*.py` —
  23/23 pass.
- `uv run pytest src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py
  src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py
  src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py -k 111` —
  17/17 pass.
- `uv run pytest tests/integration/test_kent_workflows.py::TestKentImportsModelo111Declaracion` —
  4/4 pass.
- `uv run aeat audit rulesets citations` — `OK` on `modelo_111.2024`,
  `modelo_111.2025`, `modelo_111.2026`; aggregate 100 %.
- `uv run vaultspec-core vault check all` — only the standard
  `feature index` warnings (parallel to all other in-flight features).

Final bundled gates (`just lint && just typecheck && just test &&
just hooks`) run as the last verification before the PR opens.
