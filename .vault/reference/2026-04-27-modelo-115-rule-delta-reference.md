---
tags:
  - '#reference'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-115-calc-verify-research]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-115-calc-verify-plan]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# Modelo 115 rule-delta manifest — 2024 / 2025 / 2026

This manifest documents the per-year numerical and structural state
of Modelo 115 (retención IRPF sobre arrendamientos urbanos,
trimestral) for tax years 2024, 2025, and 2026. It is the
authoritative reference cited by:

- `src/aeat/domain/formulas/_rulesets/modelo_115_2024.py`
- `src/aeat/domain/formulas/_rulesets/modelo_115_2025.py`
- `src/aeat/domain/formulas/_rulesets/modelo_115_2026.py`
- `src/aeat/adapters/inbound/declaracion/_extractors/modelo_115_v2025.py`
- the `#319` ADR / plan / research / exec records.

## Statutory grounding

| Reference                                                              | Role                                                                                | BOE id              |
| :--------------------------------------------------------------------- | :---------------------------------------------------------------------------------- | :------------------ |
| Ley 35/2006 IRPF (LIRPF) art. 99                                       | General obligation to make pagos a cuenta                                           | `BOE-A-2006-20764`  |
| LIRPF art. 101.8                                                       | Hooks the retención obligation on rendimientos del capital inmobiliario             | `BOE-A-2006-20764`  |
| LIRPF art. 68.4                                                        | Hosts the Ceuta / Melilla 60 % deducción referenced from RIRPF art. 100 ¶ 2         | `BOE-A-2006-20764`  |
| Real Decreto 439/2007 (RIRPF) art. 100                                 | Numerical surface of Modelo 115 — fixes 19 % retention rate on arrendamientos urbanos | `BOE-A-2007-6820`   |
| Orden EHA/1658/2009                                                    | Modelo 115 form layout (six-casilla liquidación block)                              | `BOE-A-2009-10295`  |
| Real Decreto 253/2025 (de 1 de abril)                                  | Modifies RIRPF art. 69 (information obligations) — NOT art. 100                     | `BOE-A-2025-...`    |

The RIRPF consolidated text last update is **2026-02-28**. The
PDF (`https://www.boe.es/buscar/pdf/2007/BOE-A-2007-6820-consolidado.pdf`)
was retrieved 2026-04-27 for issue `#319` and verifies the
verbatim art. 100 surface. The list of modificaciones to RIRPF
since 2024 (28/02/2026, 04/02/2026, 28/01/2026, 24/12/2025,
02/04/2025, 07/02/2024, 31/01/2024) carries no entry that
touches the 100-series numerical surface.

## Verbatim BOE text (2026-02-28 consolidated, art. 100)

> Artículo 100. Importe de las retenciones sobre arrendamientos
> y subarrendamientos de inmuebles.
>
> La retención a practicar sobre los rendimientos procedentes
> del arrendamiento o subarrendamiento de inmuebles urbanos,
> cualquiera que sea su calificación, será el resultado de
> aplicar el porcentaje del 19 por ciento sobre todos los
> conceptos que se satisfagan al arrendador, excluido el
> Impuesto sobre el Valor Añadido.
>
> Este porcentaje se reducirá en el 60 por ciento cuando el
> inmueble urbano esté situado en Ceuta o Melilla, en los
> términos previstos en el artículo 68.4 de la Ley del Impuesto.

Two unnumbered paragraphs. The wave-67g/68 correction recorded
in `test_modelo_115_2025.py` documents that referencing
`100.3.a` was wrong; the existing 2025 ruleset cites `100.1`
(the first paragraph — the rate clause) and that convention is
preserved across 2024 / 2026.

## Per-year numerical state

| Element                                                          | 2024              | 2025              | 2026              | Source                  |
| :--------------------------------------------------------------- | :---------------- | :---------------- | :---------------- | :---------------------- |
| Retención rate on arrendamientos urbanos (casilla 03)            | 19 %              | 19 %              | 19 %              | RIRPF art. 100, ¶ 1     |
| Ceuta / Melilla reducción aplicable (caller-gated overlay)       | 60 %              | 60 %              | 60 %              | RIRPF art. 100, ¶ 2     |
| IVA exclusion from base (verifies "excluido el IVA" rule)        | active            | active            | active            | RIRPF art. 100, ¶ 1     |
| Casilla 03 formula                                                | 19 % × ref("02")  | 19 % × ref("02")  | 19 % × ref("02")  | RIRPF art. 100, ¶ 1     |
| Casilla 06 formula                                                | sub_op(add_op(03, 04), 05) | sub_op(add_op(03, 04), 05) | sub_op(add_op(03, 04), 05) | AEAT instrucciones M115 |
| Number of computed casillas                                      | 2                 | 2                 | 2                 | Orden EHA/1658/2009     |
| Number of user-supplied casillas                                 | 4                 | 4                 | 4                 | Orden EHA/1658/2009     |
| Total casillas (form coverage)                                   | 6                 | 6                 | 6                 | Orden EHA/1658/2009     |

## 2024 → 2025 diff narrative

**No amendment.** The 2024 and 2025 rulesets are mechanically
and numerically identical. The 2024 ruleset file
(`src/aeat/domain/formulas/_rulesets/modelo_115_2024.py`) re-imports
`_CASILLAS`, `_FORMULAS`, and `_CITATIONS` from the 2025 module
and declares only its own `ParameterTable` with the 2024
effective range and `irpf.arrendamientos_rate = Decimal("0.19")`.

Source: BOE-consolidated text of RD 439/2007 art. 100 (last
update 2026-02-28) carries no 2024 modification notice for art.
100. The 2024 modificaciones (07/02/2024, 31/01/2024) touch
sections of the reglamento outside the 100-series.

## 2025 → 2026 diff narrative

**No amendment.** The 2026 ruleset is a structural and
numerical clone of the 2024 / 2025 rulesets. RD 253/2025 (de 1
de abril) — the only 2025 modification to RIRPF — touched art.
69 (information obligations), not art. 100. The four 2026
modificaciones (28/02/2026, 04/02/2026, 28/01/2026,
24/12/2025) touch sections of the reglamento outside the
100-series; the verbatim art. 100 text quoted above is the
post-consolidation surface and has no modification footnote
attached.

The 2026 ruleset file
(`src/aeat/domain/formulas/_rulesets/modelo_115_2026.py`) re-imports
`_CASILLAS`, `_FORMULAS`, and `_CITATIONS` from the 2025 module
and declares its own `ParameterTable` with the same numerical
value bound to the 2026 effective range of 2026-01-01 to
2026-12-31.

The `test_2026_no_drift_from_2025` regression in
`src/aeat/domain/formulas/_rulesets/test_modelo_115_2026.py` asserts
the no-drift invariant: an `Engine().audit_against(...)` pass
over both the 2025 and 2026 rulesets with the same fixture must
produce identical ledger entries.

## Watch-list — overlays not in the base ruleset

One prospective overlay sits outside the base ruleset's surface
and is tracked separately under EPIC `#316`:

- **Ceuta / Melilla 60 % reducción (RIRPF art. 100 ¶ 2 — LIRPF
  art. 68.4)** — applies the 60 % reduction on the retention
  rate when the inmueble urbano is located in Ceuta or Melilla
  AND the contributor is eligible for the LIRPF art. 68.4
  deducción. Caller-gated: the engine does not own the
  territoriality flag, so the overlay applies via user-supplied
  casillas (notably the 03 retención surface), not to the base
  ruleset's formula DAG. The base 19 % rate is preserved in the
  ruleset.

This overlay is out of scope for issue `#319`; its
implementation lands in a dedicated future issue on EPIC `#316`
when Kent's autónomo profile demands it.

## Citation completeness

| Ruleset            | `computed=True` casillas | with `LegalCitation` | Coverage  | Status (per `#339` audit CLI) |
| :----------------- | :----------------------: | :------------------: | :-------: | :---------------------------- |
| `modelo_115.2024`  | 2                        | 2                    | 100,00 %  | OK                            |
| `modelo_115.2025`  | 2                        | 2                    | 100,00 %  | OK                            |
| `modelo_115.2026`  | 2                        | 2                    | 100,00 %  | OK                            |

The 2024 + 2026 rulesets re-import `_CITATIONS` from the 2025
module, so the citation surface is identical: every
`computed=True` casilla cites RIRPF art. 100.1 and LIRPF
art. 101.8 via the existing `_CITATIONS` tuple.

`uv run aeat audit rulesets citations` (the audit CLI from
`#339`) reports `OK modelo_115.2024 ... coverage=100.00%` and
equivalently for 2025 and 2026.

## Mutation-harness fingerprint (issue `#338`)

| Ruleset            | `sub_op` | `percent_rate_param` | `mul_div_scalar` | `brackets_threshold` | Notes                                 |
| :----------------- | :------: | :------------------: | :--------------: | :------------------: | :------------------------------------ |
| `modelo_115.2024`  | 1        | 1                    | 0                | 0                    | Per `EXPECTED_COUNTS` in kill-rate test |
| `modelo_115.2025`  | 1        | 1                    | 0                | 0                    | Identical to 2024 (clone)              |
| `modelo_115.2026`  | 1        | 1                    | 0                | 0                    | Identical to 2024 / 2025 (clone)       |

Two mutable nodes per ruleset — the smallest IRPF Tier-L
surface. The aggregate mutation kill-rate over the populated
M115 surface is **100 %**: the casilla-06 sub_op operand-swap is
killed by `test_operand_swap_mutation::test_sub_op_operand_swap_is_detected`
and the casilla-03 percent rate is killed by
`test_percent_rate_mutation::test_percent_rate_mutation_is_detected`
(both `+0.01` and `-0.01` directions). The 90 % issue-`#338`
floor is preserved.

## L1 public-anchor waiver — Modelo 115

**Decision.** No real public Modelo 115 declaración PDF is
hash-pinned under
`tests/fixtures/pdf_corpus/l1_public_anchors/modelo_115/`.

**Rationale.**

Modelo 115 is the *lessee's* quarterly autoliquidación of an
IRPF retención on rent paid for urban real estate. Every real
Modelo 115 filing is a private autoliquidación tied to a
specific NIF and a specific quarter; AEAT does not publish any
specimen Modelo 115 declaración as a normative exemplar. The
Manual práctico de IRPF (an AEAT publication) contains worked
numerical examples of art. 100 — the 19 % rate on a
representative base de retención — but those are textual
exemplars in a manual, not the *printed PDF declaración* the
lessee receives at the end of an autoliquidación.

The closest public anchor available is the **AEAT Modelo 115
instructions PDF**
(`https://sede.agenciatributaria.gob.es/Sede/.../instrucciones.html`).
That document is the *form instructions* (a guide for lessees
filling in the form), not a *filed declaración* — it has no
NIF, no quarter-specific values, and no CSV. It cannot serve
as a hash-pinned extraction-target fixture.

**What this means for the Tier-L bar.**

The calc-verify-roundtrip bar for Modelo 115 is met via the L3
synthetic generator + extractor round-trip plus the L2
(contributor-private) anchors that ride elsewhere in the
project's fixture-tier infrastructure. The L1 tier cannot be
filled for Modelo 115 without either a NIF-private leak (which
violates the project's privacy mandate) or a synthetic-rendered
AEAT-instructions exemplar (which would not exercise the
extractor's NIF / period / CSV header logic).

The same waiver applies symmetrically to Modelo 130 (issue
`#321`), the Tier-S modelos (190, 193, 347, 349), and the
Tier-R modelos (036, 037, 232, 369, 720, 840). The project's
audit trail covers this with the L3 synthetic round-trip as the
*primary* extraction-fixture bar; L1 anchors supplement when
available but are not gating.

**Closing the waiver.** This waiver expires on either of two
triggers:

1. AEAT publishes a normative specimen Modelo 115 declaración
   on its open-data portal (no precedent for any modelo to
   date; unlikely).
2. A contributor obtains explicit consent from a real autónomo
   to contribute a single fully-scrubbed Modelo 115 declaración
   as an L1 anchor under the project's privacy + scrubbing
   discipline. If so, this waiver is replaced by a hash-pinned
   PDF + a colocated round-trip test, and the table above is
   amended.

## Audit trail

| Date          | Author                         | Change                                                                  |
| :------------ | :----------------------------- | :---------------------------------------------------------------------- |
| 2026-04-27    | Issue `#319` implementation    | Initial manifest. 2024 / 2025 / 2026 ruleset state recorded as identical. Registered `Modelo115V2024Extractor` + `Modelo115V2026Extractor` sibling extractor classes mirroring the issue-`#321` pattern (M130 PR-440 post-review fix). |
