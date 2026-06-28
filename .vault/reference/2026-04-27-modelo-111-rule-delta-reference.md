---
tags:
  - '#reference'
  - '#modelo-111-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-111-calc-verify-research]]"
  - "[[2026-04-27-modelo-111-calc-verify-adr]]"
  - "[[2026-04-27-modelo-111-calc-verify-plan]]"
---

# Modelo 111 rule-delta manifest — 2024 / 2025 / 2026

This manifest documents the per-year numerical and structural state
of Modelo 111 (retenciones e ingresos a cuenta del IRPF sobre
rendimientos del trabajo, actividades económicas, premios, ganancias
patrimoniales, contraprestaciones en especie y cesión del derecho de
imagen — trimestral) for tax years 2024, 2025, and 2026. It is the
authoritative reference cited by:

- `src/aeat/domain/formulas/_rulesets/modelo_111_2024.py`
- `src/aeat/domain/formulas/_rulesets/modelo_111_2025.py`
- `src/aeat/domain/formulas/_rulesets/modelo_111_2026.py`
- `src/aeat/adapters/inbound/declaracion/_extractors/modelo_111_v2025.py`
- the `#318` ADR / plan / research / exec records.

## Statutory grounding

| Reference                                                                  | Role                                                                                          | BOE id            |
| :------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------- | :---------------- |
| Ley 35/2006 IRPF (LIRPF) art. 99                                           | Obligación general de practicar pagos a cuenta del IRPF                                       | `BOE-A-2006-20764` |
| Ley 35/2006 IRPF (LIRPF) art. 101.2                                        | 19 % retención sobre rendimientos arrendamiento / ganancias gravadas                          | `BOE-A-2006-20764` |
| Ley 35/2006 IRPF (LIRPF) art. 101.7                                        | 19 % retención sobre premios en metálico                                                       | `BOE-A-2006-20764` |
| Real Decreto 439/2007 (RIRPF) art. 99                                      | Obligación reglamentaria de practicar pagos a cuenta — implementa LIRPF art. 99                | `BOE-A-2007-6820`  |
| Real Decreto 439/2007 (RIRPF) art. 100.1                                   | Tipo del 19 % sobre arrendamiento o subarrendamiento de bienes inmuebles urbanos              | `BOE-A-2007-6820`  |
| Real Decreto 439/2007 (RIRPF) art. 100.2                                   | Reducción del 60 % en Ceuta / Melilla (caller-gated, fuera del ruleset base)                  | `BOE-A-2007-6820`  |
| Orden HAP/2194/2013 (Modelo 111 form layout)                               | Forma + plazo del Modelo 111                                                                   | `BOE-A-2013-12489` |
| Real Decreto 633/2015                                                      | Última modificación numérica de RIRPF arts. 99-100 (rate sweep — fija 19 %)                    | `BOE-A-2015-7770`  |
| Real Decreto 1461/2018                                                     | Última modificación procedural a RIRPF (no toca arts. 99-100)                                  | `BOE-A-2018-17436` |
| Real Decreto 253/2025                                                      | Modifica RIRPF art. 69 (información obligatoria) — **NO** toca arts. 99-100                    | `BOE-A-2025-...`   |

The RIRPF consolidated text (last update 2026-02-28) and the LIRPF
consolidated text (last update 2026-03-21) carry no 2025 / 2026
modification notice that touches the rate-bearing 99-101 series of
the LIRPF or the 99-100 series of the RIRPF.

### Citation hygiene — wave 67a corrections (already landed)

The wave-67a citation audit (recorded in
`src/aeat/domain/modelos/_citation_registry.py` as `KnownBadCitation` rows)
established two non-negotiable mappings for M111:

- **Premios en metálico → 19 %**: rate is fixed by **LIRPF art.
  101.7** and implemented via the obligation hook in **RIRPF art.
  99**. Not RIRPF art. 105 (which covers IIC transmisiones).
- **Arrendamientos / ganancias gravadas → 19 %**: rate is fixed by
  **LIRPF art. 101.2** and implemented via **RIRPF art. 100.1**. The
  60 % reduction for Ceuta / Melilla rentals lives in art. 100.2.
  Not art. 100.3.a or art. 100.3.c — RIRPF art. 100 has no
  sub-letter structure.

The citation tuple in `src/aeat/domain/formulas/_rulesets/modelo_111_2025.py`
(re-imported by the 2024 + 2026 modules) encodes these corrected
mappings and is blocklist-clean.

## Per-year numerical state

| Element                                                          | 2024              | 2025              | 2026              | Source                            |
| :--------------------------------------------------------------- | :---------------- | :---------------- | :---------------- | :-------------------------------- |
| Premios en metálico (casilla 09 = % × 08)                        | 19 %              | 19 %              | 19 %              | LIRPF art. 101.7 + RIRPF art. 99 |
| Arrendamientos / ganancias gravadas (casilla 12 = % × 11)        | 19 %              | 19 %              | 19 %              | LIRPF art. 101.2 + RIRPF art. 100 |
| Total retenciones (casilla 28 = 03+06+09+12+15+18)              | active            | active            | active            | Instrucciones M111                |
| Resultado a ingresar (casilla 30 = 28-29)                        | active            | active            | active            | Instrucciones M111                |
| Number of computed casillas                                      | 4                 | 4                 | 4                 | Modelo 111 BOE template           |
| Number of user-supplied casillas (ruleset surface)               | 7                 | 7                 | 7                 | Modelo 111 BOE template           |
| Total casillas modelled in ruleset                               | 11                | 11                | 11                | Modelo 111 BOE template           |
| Total casillas printed on the BOE template                       | 21                | 21                | 21                | Orden HAP/2194/2013               |

The 21-casilla BOE template is wider than the 11-casilla ruleset
because the per-apartado perceptores + percepciones boxes (01, 02,
04, 05, 07, 10, 13, 14, 16, 17) are extractor-only — they appear in
the synthetic generator + the extractor's `casilla_ids` tuple, but
they are not modelled in the formula DAG. This split is deliberate
(see ADR `D13`).

## 2024 → 2025 diff narrative

**No amendment.** The 2024 and 2025 rulesets are mechanically and
numerically identical. The 2024 ruleset file
(`src/aeat/domain/formulas/_rulesets/modelo_111_2024.py`) re-imports
`_CASILLAS`, `_CITATIONS`, and `_FORMULAS` from the 2025 module and
declares only its own `_PARAMETERS` (with the same numerical values
bound to the 2024 effective range). The formula-id namespace is
shared (`modelo_111.2025.<reason>`) — the 2024 module does not declare
year-scoped formula-ids because the formulas are rate-parameterised
via the `ParameterTable`.

Source: BOE-consolidated text of LIRPF arts. 99-101 and RIRPF arts.
99-100, last update 2025-12-31, carries no 2025 modification notice
for these articles.

## 2025 → 2026 diff narrative

**No amendment.** The 2026 ruleset is a structural and numerical
clone of the 2024 / 2025 rulesets. RD 253/2025 (de 1 de abril) — the
only 2025 modification to the RIRPF — touched art. 69 (information
obligations), not arts. 99-100. No further 2025 or 2026 modification
to the rate-bearing articles has been published as of the
consolidated-text last-update dates (RIRPF 2026-02-28; LIRPF
2026-03-21).

The 2026 ruleset file (`src/aeat/domain/formulas/_rulesets/modelo_111_2026.py`)
re-imports `_CASILLAS_2025`, `_CITATIONS_2025`, and `_FORMULAS_2025`
from the 2025 module and declares its own `_PARAMETERS` (with the
same numerical values bound to the 2026 effective range of
2026-01-01 to 2026-12-31).

The `test_2026_no_drift_from_2025` regression in
`src/aeat/domain/formulas/_rulesets/test_modelo_111_2026.py` asserts the
no-drift invariant: an `Engine().audit_against(...)` pass over both
the 2025 and 2026 rulesets with the same fixture must produce
identical ledger entries.

## Formula-id namespace policy

M111 ships a **shared formula-id namespace** (`modelo_111.2025.<reason>`)
across all three years. This is divergent from the M130 reference
(which uses year-scoped formula-ids: `modelo_130.2024.<reason>`,
`modelo_130.2025.<reason>`, `modelo_130.2026.<reason>`).

Rationale: the existing M111 2024 ruleset re-imports `_FORMULAS` from
the canonical 2025 module because the formula DAG is rate-parameterised
(rates live in the `ParameterTable`, formula-ids are stable across
years). Migrating to year-scoped IDs would break ledger-key continuity
with audit history; the existing pattern is preserved as a deliberate
per-modelo style choice. A future cohort sweep that aligns all
per-modelo Tier-L rulesets to the year-scoped formula-id namespace can
ride elsewhere; it is not the goal of issue `#318`.

## Watch-list — overlays not in the base ruleset

Two prospective overlays sit outside the base ruleset's surface and
are tracked separately:

- **Ceuta / Melilla 60 % reduction (RIRPF art. 100.2)** — caller-gated
  reduction on retenciones de arrendamiento de inmuebles urbanos en
  Ceuta y Melilla. The engine does not own the territoriality flag,
  so the overlay applies to user-supplied casillas (post-clamp
  surface), not to the base ruleset's formula DAG.
- **Per-perceptor variable-rate retentions (apartados I / II / V /
  VI)** — the rates on rendimientos del trabajo (table-driven per
  LIRPF arts. 80-89), actividades económicas (categoría-profesional
  driven per RIRPF art. 95), retribuciones en especie + cesión de
  imagen (per-perceptor data) are not formula-DAG-derivable without
  per-perceptor inputs. Tracked under sub-EPIC `#305-Modelo-111-full`.

Both overlays are out of scope for issue `#318`.

## Citation completeness

| Ruleset            | `computed=True` casillas | with `LegalCitation` | Coverage  | Status (per `#339` audit CLI) |
| :----------------- | :----------------------: | :------------------: | :-------: | :---------------------------- |
| `modelo_111.2024`  | 4                        | 4                    | 100,00 %  | OK                            |
| `modelo_111.2025`  | 4                        | 4                    | 100,00 %  | OK                            |
| `modelo_111.2026`  | 4                        | 4                    | 100,00 %  | OK                            |

The 2024 + 2026 rulesets re-import `_CITATIONS` from 2025, so the
citation surface is identical: every `computed=True` casilla cites
LIRPF arts. 99 + 101.2 + 101.7 and RIRPF arts. 99 + 100 via the
existing `_CITATIONS` tuple.

`uv run aeat audit rulesets citations` reports
`OK modelo_111.2024 ... coverage=100.00%` and equivalently for 2025
and 2026.

## Mutation-harness fingerprint (issue `#338`)

| Ruleset            | `sub_op` | `percent_rate_param` | `mul_div_scalar` | `brackets_threshold` | Notes                                  |
| :----------------- | :------: | :------------------: | :--------------: | :------------------: | :------------------------------------- |
| `modelo_111.2024`  | 1        | 2                    | 0                | 0                    | Per `EXPECTED_COUNTS` in kill-rate test |
| `modelo_111.2025`  | 1        | 2                    | 0                | 0                    | Identical to 2024 (clone)              |
| `modelo_111.2026`  | 1        | 2                    | 0                | 0                    | Identical to 2024 / 2025 (clone)       |

The `sub_op` count (1 per year) is casilla 30's `28 - 29`. The two
`percent_rate_param` count is casillas 09 + 12. The aggregate mutation
kill-rate over the populated M111 surface is 100 % (well above the
issue-`#338` 90 % floor) with the addition of the 2026 row.

## Synthetic generator coverage

M111 does **not** ship a dedicated synthetic generator. The integration
tests under `tests/integration/test_kent_workflows.py` use
`tests/fixtures/pdf_corpus/l3_synthetic/_generators/_generic_quarterly_generator.py`
(via `_synth_quarterly_pdf`) with the `_MODELO_111_LABELS` and
`_M111_HAPPY` mappings. The 21-casilla flat layout fits the generic
shape — no per-modelo generator is required.

The round-trip `generator(params) → PDF → extractor` invariant closes
via the `_synth_quarterly_pdf → Modelo111V*Extractor.extract` chain.
The `Modelo111V2024Extractor` and `Modelo111V2026Extractor` sibling
classes (added in `#318`) inherit `Modelo111V2025Extractor.casilla_ids`
verbatim because the M111 form layout is unchanged 2024 → 2025 → 2026.

## L1 public-anchor waiver — Modelo 111

**Decision.** No real public Modelo 111 declaración PDF is hash-pinned
under `tests/fixtures/pdf_corpus/l1_public_anchors/modelo_111/`.

**Rationale.**

Modelo 111 is the autónomo's quarterly *autoliquidación* of
retenciones e ingresos a cuenta del IRPF sobre los pagos efectuados a
perceptores. Every real Modelo 111 filing is a private autoliquidación
tied to a specific NIF and a specific quarter; AEAT does not publish
any specimen Modelo 111 declaración as a normative exemplar.

The closest public anchor available is the **AEAT instructions PDF**
for Modelo 111 (a guide for retenedores filling in the form). That
document is the *form instructions*, not a *filed declaración* — it
has no NIF, no quarter-specific values, and no CSV. It cannot serve as
a hash-pinned extraction-target fixture.

**What this means for the Tier-L bar.**

The calc-verify-roundtrip bar for Modelo 111 is met via the L3
synthetic generator + extractor round-trip, plus the L2 (contributor-
private) anchors that ride elsewhere in the project's fixture tier
infrastructure. The L1 tier cannot be filled for Modelo 111 without
either a NIF-private leak (which violates the project's privacy
mandate) or a synthetic-rendered AEAT-instructions exemplar (which
would not exercise the extractor's NIF / period / CSV header logic).

The same gap applies symmetrically to most per-form Tier-L modelos
including Modelo 130 (see `2026-04-27-modelo-130-rule-delta-reference.md`, the M130 waiver).
The project's audit trail covers this with the L3 synthetic round-trip
as the *primary* extraction-fixture bar; L1 anchors supplement when
available but are not gating.

**Closing the waiver.** This waiver expires on either of two triggers:

1. AEAT publishes a normative specimen Modelo 111 declaración on its
   open-data portal (no precedent for any modelo to date; unlikely).
2. A contributor obtains explicit consent from a real retenedor to
   contribute a single fully-scrubbed Modelo 111 declaración as an
   L1 anchor under the project's privacy + scrubbing discipline. If
   so, this waiver is replaced by a hash-pinned PDF + a colocated
   round-trip test, and the table above is amended.

## Audit trail

| Date          | Author                         | Change                                                                                                                                                                                                                                                                                                                                                       |
| :------------ | :----------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 2026-04-27    | Issue `#318` implementation    | Initial manifest. 2024 / 2025 / 2026 ruleset state recorded as identical. Sibling 2024 + 2026 extractor classes registered in `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py` alongside the existing 2025 class — closes the post-PR-440 registry gap surfaced on M130 / `#321`. Per-year mutation harness fingerprint (`sub_op = 1`, `percent_rate_param = 2`) extended to `modelo_111.2026`. |
| 2026-05-21    | `declaracion-extraction-architecture` ADR | The per-modelo extractor classes (`Modelo111V2024Extractor`, `Modelo111V2026Extractor`, `_extractors/__init__.py` registry) described in the 2026-04-27 audit-trail entry were deleted. Declaración extraction is now driven by registry `declaracion_pdf` extraction profiles. See ADR `2026-05-21-declaracion-extraction-architecture-adr`. |
