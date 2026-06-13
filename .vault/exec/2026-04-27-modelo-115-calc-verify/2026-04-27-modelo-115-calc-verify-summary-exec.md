---
tags:
  - '#exec'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-115-calc-verify-research]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-115-calc-verify-plan]]"
  - "[[2026-04-27-modelo-115-rule-delta-reference]]"
---

# Phase summary — issue `#319` Modelo 115 calc-verify-roundtrip

## Per-year casilla inventory

| Casilla | Label                                                              | 2024     | 2025     | 2026     | Source                |
| :-----: | :----------------------------------------------------------------- | :------: | :------: | :------: | :-------------------- |
| 01      | Nº de arrendadores                                                  | input    | input    | input    | Orden EHA/1658/2009   |
| 02      | Base de retención                                                   | input    | input    | input    | Orden EHA/1658/2009   |
| 03      | Retenciones e ingresos a cuenta (= 19 % × 02)                       | computed | computed | computed | RIRPF art. 100, ¶ 1   |
| 04      | Ingresos a cuenta por retribución en especie                        | input    | input    | input    | Orden EHA/1658/2009   |
| 05      | A deducir: complementaria                                           | input    | input    | input    | Orden EHA/1658/2009   |
| 06      | Resultado a ingresar (= 03 + 04 − 05)                               | computed | computed | computed | AEAT instrucciones    |

**Computed casillas per ruleset:** 2 (03, 06).
**Total casillas per ruleset:** 6.

## BOE source list

| Source                                                                  | BOE id              | Used to anchor                                |
| :---------------------------------------------------------------------- | :------------------ | :-------------------------------------------- |
| RD 439/2007 (RIRPF) art. 100, ¶ 1                                       | `BOE-A-2007-6820`  | 19 % retention rate on arrendamientos urbanos |
| RD 439/2007 (RIRPF) art. 100, ¶ 2                                       | `BOE-A-2007-6820`  | Ceuta / Melilla 60 % overlay (caller-gated)   |
| Ley 35/2006 IRPF (LIRPF) art. 99                                        | `BOE-A-2006-20764` | Obligation to make pagos a cuenta              |
| Ley 35/2006 IRPF (LIRPF) art. 101.8                                     | `BOE-A-2006-20764` | Hooks the retención on rendimientos del capital inmobiliario |
| Ley 35/2006 IRPF (LIRPF) art. 68.4                                      | `BOE-A-2006-20764` | Hosts the Ceuta / Melilla deducción referenced from RIRPF 100 ¶ 2 |
| Orden EHA/1658/2009                                                     | `BOE-A-2009-10295` | Modelo 115 form layout (six-casilla liquidación) |
| RD 439/2007 consolidated text (last update 2026-02-28)                  | —                  | Confirms no 2025 / 2026 amendment to art. 100 |

The verbatim BOE text of art. 100 is reproduced in the rule-delta
manifest at `.vault/reference/2026-115-rule-delta.md`.

## Mutation-harness fingerprint

| Ruleset            | `sub_op` | `percent_rate_param` | All other classes | Kill-rate (#338 floor 90 %) |
| :----------------- | :------: | :------------------: | :---------------: | :--------------------------: |
| `modelo_115.2024`  | 1        | 1                    | 0                 | 100 %                        |
| `modelo_115.2025`  | 1        | 1                    | 0                 | 100 %                        |
| `modelo_115.2026`  | 1        | 1                    | 0                 | 100 %                        |

The aggregate kill-rate over the full M115 mutable surface is
**100 %** — the `#338` floor of 90 % is preserved.

## Citation completeness — `aeat audit rulesets citations`

Output (relevant rows):

```
OK  modelo_115.2024  modelo 115 2024-01-01…2024-12-31  computed=2  with_citation=2  coverage=100.00%
OK  modelo_115.2025  modelo 115 2025-01-01…2025-12-31  computed=2  with_citation=2  coverage=100.00%
OK  modelo_115.2026  modelo 115 2026-01-01…2026-12-31  computed=2  with_citation=2  coverage=100.00%
OK  aggregate        modelo all 2024-01-01…2026-12-31  computed=100 with_citation=100 coverage=100.00%
```

The aggregate coverage moves from 98 / 98 (pre-#319) to
100 / 100 (post-#319) computed casillas; the issue contributes
two new computed casillas (M115 2026 c03 + c06).

## L1 anchor decision

**Waiver.** Same reasoning as M130 (`#321` waiver section
authored under that issue). M115 is a private autoliquidación
of an IRPF retención; AEAT does not publish a normative specimen
PDF. Documented in
`.vault/reference/2026-115-rule-delta.md` §"L1 public-anchor
waiver".

## Verification suite — final state

- `just lint` → All checks passed.
- `just typecheck` → All checks passed.
- `uv run pytest --ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py
  --ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`
  → 3 708 passed, 13 skipped.
  (The two ignored modules carry pre-existing flaky network /
  TLS handshake tests unrelated to this issue —
  `test_reauthenticate_does_not_deadlock` was confirmed to fail
  on the pre-`#319` baseline via `git stash`.)
- `just hooks` → All prek hooks passed (trim trailing whitespace,
  fix end of files, check yaml / toml / large files / merge
  conflicts / private key, ruff check, ruff format, ty type
  check, relative-imports enforcement).
- `uv run aeat audit rulesets citations` → aggregate
  100,00 % across all 20 rulesets.

## Files changed (summary)

- **NEW** `src/aeat/domain/formulas/_rulesets/modelo_115_2026.py`
- **NEW** `src/aeat/domain/formulas/_rulesets/test_modelo_115_2026.py`
- **NEW** `.vault/research/2026-04-27-modelo-115-calc-verify-research.md`
- **NEW** `.vault/adr/2026-04-27-modelo-115-calc-verify-adr.md`
- **NEW** `.vault/plan/2026-04-27-modelo-115-calc-verify-plan.md`
- **NEW** `.vault/reference/2026-115-rule-delta.md`
- **NEW** `.vault/exec/2026-04-27-modelo-115-calc-verify/...`
  (5 files)
- **EDIT** `src/aeat/domain/formulas/_rulesets/__init__.py`
- **EDIT** `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`
- **EDIT** `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py`
- **EDIT** `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py`
- **EDIT** `src/aeat/adapters/inbound/declaracion/_extractors/modelo_115_v2025.py`
- **EDIT** `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`
- **EDIT** `src/aeat/domain/formulas/test_smoke.py`
- **EDIT** `src/aeat/domain/formulas/test_registry.py`
- **EDIT** `src/aeat/domain/formulas/test_cli.py`
- **EDIT** `tests/integration/test_kent_workflows.py`
- **EDIT** `docs/coverage/modelos.md`

## Eight safety invariants — closure

1. **Cent-exact correctness** — every parametrised case in
   `test_modelo_115_2026.py` and the existing 2024 / 2025 tests
   pass within the audit `tolerance=Decimal("0.01")` floor.
2. **External anchoring** — the new
   `test_external_worked_example_rirpf_art_100_2026` derives
   expected values from RIRPF art. 100 ¶ 1 (19 %), not from the
   ruleset's `ParameterTable`.
3. **Per-annum coverage 2024 / 2025 / 2026** — three rulesets
   registered with non-overlapping `effective_from / to`
   windows; the registry's
   `test_registry_ships_modelo_130_and_303_rulesets` enumerates
   all three.
4. **Citation enforcement** — `aeat audit rulesets citations`
   reports `OK ... coverage=100.00%` for every M115 row.
5. **Mutation harness** — `EXPECTED_COUNTS` row added; per-class
   harnesses kill every M115 mutable node.
6. **PDF round-trip** — `_synth_quarterly_pdf` for 2024 / 2025 /
   2026 generates a clean PDF that the registry-resolved
   sibling extractor parses to `COMPLETE` / `VERIFIED`.
7. **Integration test** — `TestKentImportsModelo115Declaracion`
   ships 7 cases (4 mandatory + 3 per-year parametrisations);
   all pass via Typer `CliRunner`.
8. **L1 anchor decision** — waiver documented in the rule-delta
   manifest with the same closure-trigger discipline used for
   M130.
