---
tags:
  - '#research'
  - '#modelo-111-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-111-calc-verify` research

Issue `#318` is the per-modelo Tier-L calc-verify-roundtrip delegation
for Modelo 111 under EPIC `#316`. This document surveys the current
state of the M111 surface (rulesets, extractor, integration tests,
mutation coverage), the 2024 → 2025 → 2026 statutory delta on the
LIRPF / RIRPF retention articles that ground M111, the scope decision
on whether the ruleset covers rendimientos del trabajo + actividades
económicas + premios + ganancias + retribuciones en especie + cesión
de imagen or a narrower subset, and the L1 anchor decision.

## Modelo 111 — what it is

Modelo 111 is the autoliquidación trimestral de retenciones e ingresos
a cuenta del IRPF que practica todo retenedor / pagador. The form
groups casillas in apartados, one per *rubro* of retention:

| Apartado | Rubro                                                | Casillas (perceptores / percepciones / retenciones) |
| :------- | :--------------------------------------------------- | :-------------------------------------------------- |
| I        | Rendimientos del trabajo                             | 01 / 02 / 03                                        |
| II       | Rendimientos de actividades económicas               | 04 / 05 / 06                                        |
| III      | Premios en metálico                                  | 07 / 08 / 09                                        |
| IV       | Ganancias patrimoniales — aprovechamientos forestales | 10 / 11 / 12                                        |
| V        | Contraprestaciones en especie                        | 13 / 14 / 15                                        |
| VI       | Cesión del derecho de imagen                         | 16 / 17 / 18                                        |

Plus the liquidación block:

- 28 — total retenciones + ingresos a cuenta (suma de casillas
  03 + 06 + 09 + 12 + 15 + 18).
- 29 — a deducir: exclusivamente en declaración complementaria.
- 30 — resultado a ingresar (= 28 - 29).

Total casillas printed on the BOE template: **21**. Computed casillas
(via the formula DSL): **4** (09, 12, 28, 30).

## Statutory grounding (LIRPF + RIRPF)

| Reference                                                                  | Role                                                                                     | BOE id            |
| :------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------- | :---------------- |
| LIRPF (Ley 35/2006) art. 99                                                | Obligación general de practicar pagos a cuenta del IRPF                                  | `BOE-A-2006-20764` |
| LIRPF (Ley 35/2006) art. 101.2                                             | 19 % retención sobre rendimientos arrendamiento de inmuebles urbanos / ganancias gravadas | `BOE-A-2006-20764` |
| LIRPF (Ley 35/2006) art. 101.7                                             | 19 % retención sobre premios en metálico (Ley de Loterías + IRPF)                        | `BOE-A-2006-20764` |
| RIRPF (RD 439/2007) art. 99                                                | Obligación reglamentaria de practicar pagos a cuenta — implementa LIRPF art. 99          | `BOE-A-2007-6820`  |
| RIRPF (RD 439/2007) art. 100                                               | Importe de las retenciones sobre arrendamiento de inmuebles urbanos — 19 % en art. 100.1 | `BOE-A-2007-6820`  |
| Orden HAP/2194/2013                                                        | Forma y plazo del Modelo 111                                                             | `BOE-A-2013-12489` |
| RD 633/2015                                                                | Última modificación numérica de RIRPF arts. 99-100 (rate sweep — fixes 19 %)            | `BOE-A-2015-7770`  |
| RD 253/2025                                                                | Modifica RIRPF art. 69 (información obligatoria) — **NO** toca arts. 99-100              | `BOE-A-2025-...`   |

Consolidated-text last-update dates (2026-04-27 retrieval):

- RIRPF (`BOE-A-2007-6820`): 2026-02-28.
- LIRPF (`BOE-A-2006-20764`): 2026-03-21.

Neither 2025 nor 2026 carries any BOE amendment notice that touches
the 99-100 series of the RIRPF or the 99-101.7 series of the LIRPF.

### Citation hygiene — wave 67a corrections (already landed)

The wave-67a citation audit (recorded in
`src/aeat/domain/modelos/_citation_registry.py` as `KnownBadCitation` rows)
established two non-negotiable mappings for M111:

- **Premios en metálico → 19 %**: rate is fixed by **LIRPF art. 101.7**
  and implemented via the obligation hook in **RIRPF art. 99**. *Not*
  RIRPF art. 105 (which covers IIC transmisiones).
- **Arrendamientos / ganancias gravadas → 19 %**: rate is fixed by
  **LIRPF art. 101.2** and implemented via **RIRPF art. 100.1**. The
  60 % reduction for Ceuta/Melilla rentals lives in art. 100.2.
  *Not* art. 100.3.a or art. 100.3.c — RIRPF art. 100 has no
  sub-letter structure.

The citation tuple in `src/aeat/domain/formulas/_rulesets/modelo_111_2025.py`
already encodes these corrected mappings and is blocklist-clean
(`uv run aeat audit rulesets citations` reports `OK modelo_111.2025
... coverage=100.00%` per the issue-`#339` audit CLI).

## Current M111 ruleset state (audit 2026-04-27)

### `modelo_111.2024`

- File: `src/aeat/domain/formulas/_rulesets/modelo_111_2024.py`.
- Structural clone of 2025 — re-imports `_CASILLAS_2025`,
  `_CITATIONS_2025`, `_FORMULAS_2025`. Declares its own
  `ParameterTable` with the 2024 effective range.
- Parameters: `irpf.premios_rate = 0.19`,
  `irpf.ganancias_arrendamiento_rate = 0.19`.
- Citation coverage: 100 % (4 / 4 computed casillas).
- Status: **clean**. No back-fill required for the existing surface.

### `modelo_111.2025`

- File: `src/aeat/domain/formulas/_rulesets/modelo_111_2025.py`.
- Canonical year — declares `_CITATIONS`, `_CASILLAS`, `_FORMULAS`.
- Casillas (11 modelled, 4 computed): 03, 06, 08, 09, 11, 12, 15, 18,
  28, 29, 30. The 21-casilla BOE template prints additional perceptores
  / percepciones boxes (01, 02, 04, 05, 07, 10, 13, 14, 16, 17) which
  are extractor-only (not in the formula DAG).
- Formulas:
  - `09 = irpf.premios_rate × 08` (PercentFormula).
  - `12 = irpf.ganancias_arrendamiento_rate × 11` (PercentFormula).
  - `28 = 03 + 06 + 09 + 12 + 15 + 18` (AddFormula).
  - `30 = 28 - 29` (SubFormula).
- Citation coverage: 100 % (4 / 4 computed casillas).
- Status: **clean**.

### `modelo_111.2026` — does not exist

The 2026 ruleset is the primary new artefact this issue ships.

### Test coverage

`src/aeat/domain/formulas/_rulesets/test_modelo_111_2025.py` ships eight
worked-example tests (happy path + sum mismatch + complementaria
deduction + casilla count assertion + premios at 19 % + external
worked example LIRPF 99 + zero boundary + premios typo). The 2024
ruleset has **no colocated test file** — same gap M130 had pre-`#321`,
and the same pattern this issue closes.

## Scope decision — full retention domain or narrow

The current M111 ruleset covers the **full M111 retention domain**:
trabajo + actividades económicas + premios + ganancias forestales +
retribuciones en especie + cesión de imagen. The formulas only fire on
the casillas where the rate is fixed by statute (premios + ganancias
forestales arrendamientos at 19 %). The trabajo / actividades-económicas
/ retribuciones-en-especie / cesión-de-imagen rates are *variable*
(table-driven for trabajo per the LIRPF retention tables; categoría-
profesional-driven for actividades económicas; per-perceptor for
contraprestaciones en especie + cesión de imagen). Those land as
caller-supplied retention amounts on casillas 03, 06, 15, 18 — the
ruleset only sums them into casilla 28.

**Decision in this issue**: keep the existing scope (computed casillas
09, 12, 28, 30; user-supplied casillas 03, 06, 15, 18). Adding a rate
table to compute trabajo / actividades-económicas retentions
automatically would require modelling the LIRPF retention tables for
trabajo (table-based brackets per LIRPF arts. 80-89) and the categoría-
profesional + recipient-status mappings for actividades económicas
(15 % baseline + 7 % reduced rate per RIRPF art. 95). That is the
scope of the per-perceptor sub-EPIC tracked separately under
`#305-Modelo-111-full` and is **out of scope** for this Tier-L issue.

The PR body documents this scope boundary so a future per-perceptor
issue lands cleanly.

## 2024 → 2025 → 2026 rule delta

**No amendment.** The retention rates anchored in LIRPF arts. 99-101
and RIRPF arts. 99-100 are unchanged across 2024 → 2025 → 2026:

- 19 % on premios en metálico (LIRPF art. 101.7 → RIRPF art. 99).
- 19 % on rendimientos arrendamiento / ganancias gravadas (LIRPF art.
  101.2 → RIRPF art. 100.1).
- Ceuta/Melilla 60 % reduction (RIRPF art. 100.2) — caller-gated, not
  in the base ruleset.

RD 253/2025 — the only 2025 modification to the RIRPF — touched art. 69
(information obligations), not arts. 99-100. The RIRPF consolidated
text (last update 2026-02-28) and the LIRPF consolidated text (last
update 2026-03-21) carry no 2025 / 2026 amendment notice that touches
the rate-bearing articles.

The 2026 ruleset is therefore a structural clone of 2024 / 2025, with
its own `ruleset_id` (`modelo_111.2026`), `effective_from = 2026-01-01`,
`effective_to = 2026-12-31`, and a year-scoped formula-id namespace
(`modelo_111.2026.<reason>`). This mirrors the M130 reference
implementation under issue `#321`.

## Synthetic generator + extractor — current state

### Generator

M111 does **not** ship a dedicated generator. The integration tests
under `tests/integration/test_kent_workflows.py` use
`tests/fixtures/pdf_corpus/l3_synthetic/_generators/_generic_quarterly_generator.py`
(via `_synth_quarterly_pdf`) with the `_MODELO_111_LABELS` and
`_M111_HAPPY` mappings. The 21-casilla layout is rendered with one
label / amount line per casilla.

This works for the Tier-L bar — the round-trip
`generator(params) → PDF → extractor` invariant closes via the
`_synth_quarterly_pdf → Modelo111V2025Extractor.extract` chain. No
dedicated M111 generator is required to land this issue; the M130 +
M303 dedicated generators are bespoke because of layout idiosyncrasies
(M130's two-apartado split, M303's eight-segment envelope) that
M111's flat 21-casilla layout does not have.

### Extractor

`src/aeat/adapters/inbound/declaracion/_extractors/modelo_111_v2025.py` ships a
`Modelo111V2025Extractor` subclassing `GenericDeclaracionExtractor`
with `casilla_ids = ("01", "02", ..., "18", "28", "29", "30")`. The
`template_revision = ("111", 2025, "2025.01")` triple resolves at
registration time.

**Gap**: no sibling 2024 / 2026 extractor classes registered. The
post-PR-440 review on M130 (issue `#321`) surfaced this exact pattern
— the registry rejected 2024 / 2026 PDFs because only the 2025
template revision was registered. M111 has the same shape and needs
the same fix in this PR: subclass `Modelo111V2024Extractor` and
`Modelo111V2026Extractor` pinning their respective `template_revision`
ClassVars and inheriting `casilla_ids` from the 2025 base.

The form layout has not changed across 2024 → 2025 → 2026 (Orden
HAP/2194/2013 is the latest M111 form-layout amendment — published in
2013, last-update 2014; no 2025 / 2026 BOE amendment to the M111 form
layout has been published).

## Mutation coverage — current fingerprint

`src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py::EXPECTED_COUNTS`
reports for both `modelo_111.2024` and `modelo_111.2025`:

- `sub_op = 1` (casilla 30's `28 - 29`).
- `percent_rate_param = 2` (casillas 09 + 12 — the two PercentFormula
  rates parameter-bound).
- `percent_rate_literal = 0`, `mul_div_scalar = 0`,
  `brackets_threshold_non_terminal = 0`, both compound-skipped counts
  zero.

The `test_percent_rate_mutation.py` harness covers the 2024 + 2025
rulesets via fixtures `_f111_premios_fixture` (drives casilla 09) and
`_f111_arrendamiento_fixture` (drives casilla 12). The
`test_operand_swap_mutation.py` harness covers `modelo_111.2025`
casilla 30 via `_modelo_111_fixture`.

**For 2026**: the new ruleset inherits the same fingerprint
(`sub_op = 1`, `percent_rate_param = 2`). The harness extension is
mechanical: add one row to `EXPECTED_COUNTS`, four `pytest.param`
entries to `_ruleset_cases` (2024+2026 currently absent — in fact the
2024 entries already exist; only 2026 needs to land), and one
`pytest.param` to `test_outer_sub_op_swap_detected` for
`modelo_111.2026`.

Aggregate kill-rate stays at the existing 100 % on the populated
M111 surface (well above the issue-DoD 90 % floor).

## Integration test — current state

`tests/integration/test_kent_workflows.py::TestKentImportsModelo111Declaracion`
ships **four** test cases (added by issue `#340`):

1. `test_happy_path_english` — clean PDF → `Verification status:
   VERIFIED` in English.
2. `test_happy_path_spanish_default` — Spanish-default verdict.
3. `test_partial_extraction_needs_review` — 11 of 21 casillas → PARTIAL.
4. `test_discrepancy_classified_correctly` — drifted casilla 09 →
   `cause=CORRECTNESS_DIVERGENCE`.

The optional fourth case is **already wired**. No further extension
needed for this issue — the integration class is at the Tier-L bar.

## L1 public-anchor decision

M111 is the autónomo's quarterly *autoliquidación* of retenciones
practicadas a perceptores. Every real M111 filing is a private
autoliquidación tied to a specific NIF + quarter. AEAT does not
publish any specimen Modelo 111 declaración as a normative exemplar.
The closest public anchor available is the AEAT *Instrucciones del
Modelo 111* PDF — a guide for retenedores filling in the form, not a
*filed declaración*. It has no NIF, no quarter-specific values, and
no CSV. It cannot serve as a hash-pinned extraction-target fixture.

**Decision**: file an explicit L1 waiver in
`.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md`, mirroring the M130 waiver.
The Tier-L bar is met via the L3 synthetic generator + extractor
round-trip + the integration test class. The waiver expires on either
of (a) AEAT publishing a normative specimen M111 (no precedent — same
status as M130), (b) a contributor obtaining explicit consent from a
real retenedor to contribute a fully-scrubbed M111 declaración as an
L1 anchor under the project's privacy + scrubbing discipline.

## Casilla inventory — Tier-L DoD enumeration

| ID  | Computed | Type            | Statute                                        |
| :-- | :------- | :-------------- | :--------------------------------------------- |
| 01  | No       | Integer         | LIRPF art. 99                                  |
| 02  | No       | Currency (EUR)  | LIRPF art. 99                                  |
| 03  | No       | Currency (EUR)  | LIRPF arts. 99-101 (table-driven)              |
| 04  | No       | Integer         | LIRPF art. 99                                  |
| 05  | No       | Currency (EUR)  | LIRPF art. 99                                  |
| 06  | No       | Currency (EUR)  | LIRPF art. 101 + RIRPF art. 95 (table-driven) |
| 07  | No       | Integer         | LIRPF art. 99                                  |
| 08  | No       | Currency (EUR)  | LIRPF art. 101.7                               |
| **09** | **Yes**  | Currency (EUR)  | **0,19 × 08** (LIRPF art. 101.7 + RIRPF art. 99) |
| 10  | No       | Integer         | LIRPF art. 99                                  |
| 11  | No       | Currency (EUR)  | LIRPF art. 101.2                               |
| **12** | **Yes**  | Currency (EUR)  | **0,19 × 11** (LIRPF art. 101.2 + RIRPF art. 100) |
| 13  | No       | Integer         | LIRPF art. 99                                  |
| 14  | No       | Currency (EUR)  | LIRPF art. 99                                  |
| 15  | No       | Currency (EUR)  | LIRPF arts. 99-101                             |
| 16  | No       | Integer         | LIRPF art. 99                                  |
| 17  | No       | Currency (EUR)  | LIRPF art. 99                                  |
| 18  | No       | Currency (EUR)  | LIRPF arts. 99-101                             |
| **28** | **Yes**  | Currency (EUR)  | **03 + 06 + 09 + 12 + 15 + 18** (Instrucciones M111) |
| 29  | No       | Currency (EUR)  | Instrucciones M111                             |
| **30** | **Yes**  | Currency (EUR)  | **28 - 29** (Instrucciones M111)               |

The four computed casillas (09, 12, 28, 30) ground 100 % of the formula
DAG. The remaining 17 casillas are user-supplied — perceptores +
percepciones inputs (which the ruleset does not derive) + the
table-driven retentions on apartados I / II / V / VI (which the
ruleset cannot derive without the per-perceptor sub-EPIC).

## Sibling per-modelo issues in flight

Four concurrent per-modelo Tier-L branches (post-`#321`):

- `feature/326-modelo-303-calc-verify` — IVA Tier-L; ZERO source
  collision.
- `feature/322-modelo-131-calc-verify` — IRPF módulos Tier-L; ZERO
  source collision.
- `feature/319-modelo-115-calc-verify` — IRPF rent retention; closest
  pattern twin (single rate × base aggregated). ZERO source collision.

PR-open soft collisions on three shared files:
`tests/integration/test_kent_workflows.py` (different test class),
`docs/coverage/modelos.md` (different row),
`src/aeat/domain/formulas/_rulesets/__init__.py` (different ruleset
register). Mechanical 4-way textual unions at PR-open time.

## Acceptance summary

This issue lands:

1. **2026 ruleset** — `src/aeat/domain/formulas/_rulesets/modelo_111_2026.py`
   as a structural clone of 2024 / 2025. Registered in `__init__.py`.
2. **2024 + 2026 sibling extractors** —
   `Modelo111V2024Extractor` + `Modelo111V2026Extractor` registered
   alongside the existing 2025 extractor. Same layout, year-pinned
   `template_revision`. (Post-PR-440 lesson.)
3. **2024 ruleset test file** — colocated
   `test_modelo_111_2024.py` mirroring the 2025 file's worked-example
   pattern. Closes the same gap M130 closed in `#321`.
4. **2026 ruleset test file** — colocated
   `test_modelo_111_2026.py` with no-drift regression + external-
   anchored worked example + zero-boundary + a typo-detection case.
5. **Rule-delta manifest** — `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md`
   listing the per-year numerical state with BOE citations + the L1
   waiver.
6. **Mutation harness extension** — one row to `EXPECTED_COUNTS`, two
   `pytest.param` entries to `test_percent_rate_mutation::_ruleset_cases`,
   one `pytest.param` to `test_operand_swap_mutation::test_sub_op_operand_swap_is_detected`.
7. **Coverage table flip** — `docs/coverage/modelos.md` M111 row to ✅.

Out of scope (per issue #318 + #316):

- Per-perceptor retention table (trabajo + actividades económicas) —
  separate sub-EPIC.
- Modelo 190 (informative annual summary of M111 retentions).
- Modelo 115 / 123 / 180 — separate Tier-L issues.
- Live AEAT submission — PERMANENTLY FORBIDDEN.
