---
tags:
  - '#reference'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-plan]]"
---

# Modelo 130 rule-delta manifest — 2024 / 2025 / 2026

This manifest documents the per-year numerical and structural state
of Modelo 130 (pago fraccionado IRPF para autónomos en estimación
directa, trimestral) for tax years 2024, 2025, and 2026. It is the
authoritative reference cited by:

- `src/aeat/domain/formulas/_rulesets/modelo_130_2024.py`
- `src/aeat/domain/formulas/_rulesets/modelo_130_2025.py`
- `src/aeat/domain/formulas/_rulesets/modelo_130_2026.py`
- the `#321` ADR / plan / research / exec records.

## Statutory grounding

| Reference                                                                  | Role                                                                  | BOE id            |
| :------------------------------------------------------------------------- | :-------------------------------------------------------------------- | :---------------- |
| Ley 35/2006 IRPF (LIRPF) art. 99                                           | General obligation to make pagos a cuenta                             | `BOE-A-2006-20764` |
| Real Decreto 439/2007 (RIRPF) art. 110                                     | Numerical surface of Modelo 130 (rates, brackets, deductions)         | `BOE-A-2007-6820`  |
| Orden EHA/672/2007                                                         | Modelo 130 / 131 form layout                                          | `BOE-A-2007-6032`  |
| Real Decreto 1003/2014 (modifies art. 110.3.c minoración brackets)         | Last numerical amendment to the casilla-13 minoración bracket scheme  | `BOE-A-2014-12369` |
| Real Decreto 960/2013 (modifies art. 110.3.d vivienda-habitual deduction)  | Last numerical amendment to the vivienda-habitual deduction           | `BOE-A-2013-12892` |
| Real Decreto 1461/2018                                                     | Last cited modification touching art. 110 (procedural)                | `BOE-A-2018-17436` |
| Real Decreto 253/2025                                                      | Modifies RIRPF art. 69 (information obligations) — NOT art. 110       | `BOE-A-2025-...`   |

The RIRPF consolidated text (last update 2026-02-28) carries no 2025
or 2026 modification notice that touches the 110-series numerical
surface.

## Per-year numerical state

| Element                                                          | 2024              | 2025              | 2026              | Source                   |
| :--------------------------------------------------------------- | :---------------- | :---------------- | :---------------- | :----------------------- |
| IRPF general rate (estimación directa, casilla 04)                | 20 %              | 20 %              | 20 %              | RIRPF art. 110.1.a       |
| Agraria / ganadera / forestal / pesquera rate (casilla 09)        | 2 %               | 2 %               | 2 %               | RIRPF art. 110.1.c       |
| Casilla-13 minoración bracket 1 boundary                          | 9 000,00 €        | 9 000,00 €        | 9 000,00 €        | RIRPF art. 110.3.c       |
| Casilla-13 minoración bracket 1 value                             | 100 €             | 100 €             | 100 €             | RIRPF art. 110.3.c       |
| Casilla-13 minoración bracket 2 boundary                          | 10 000,00 €       | 10 000,00 €       | 10 000,00 €       | RIRPF art. 110.3.c       |
| Casilla-13 minoración bracket 2 value                             | 75 €              | 75 €              | 75 €              | RIRPF art. 110.3.c       |
| Casilla-13 minoración bracket 3 boundary                          | 11 000,00 €       | 11 000,00 €       | 11 000,00 €       | RIRPF art. 110.3.c       |
| Casilla-13 minoración bracket 3 value                             | 50 €              | 50 €              | 50 €              | RIRPF art. 110.3.c       |
| Casilla-13 minoración bracket 4 boundary                          | 12 000,00 €       | 12 000,00 €       | 12 000,00 €       | RIRPF art. 110.3.c       |
| Casilla-13 minoración bracket 4 value                             | 25 €              | 25 €              | 25 €              | RIRPF art. 110.3.c       |
| Casilla-13 out-of-range value                                     | 0 €               | 0 €               | 0 €               | RIRPF art. 110.3.c       |
| Vivienda-habitual deduction rate                                  | 2 %               | 2 %               | 2 %               | RIRPF art. 110.3.d       |
| Vivienda-habitual deduction quarterly cap                         | 660,14 €          | 660,14 €          | 660,14 €          | RIRPF art. 110.3.d       |
| Casilla 12 clamp (Suma parciales ≥ 0)                             | active            | active            | active            | RIRPF art. 110           |
| Number of computed casillas                                       | 9                 | 9                 | 9                 | Modelo 130 BOE template  |
| Number of user-supplied casillas                                  | 10                | 10                | 10                | Modelo 130 BOE template  |
| Total casillas (form coverage)                                    | 19                | 19                | 19                | Orden EHA/672/2007       |

## 2024 → 2025 diff narrative

**No amendment.** The 2024 and 2025 rulesets are mechanically and
numerically identical. The 2025 ruleset file
(`src/aeat/domain/formulas/_rulesets/modelo_130_2025.py`) re-imports
`_CASILLAS` and `_CITATIONS` from the 2024 module and declares only
its own `_FORMULAS` (with a year-scoped formula-id namespace) and
`_PARAMETERS` (with the same numerical values bound to the 2025
effective range).

Source: BOE-consolidated text of RD 439/2007 art. 110 last updated
2025-12-31 carries no 2025 modification notice for art. 110.

## 2025 → 2026 diff narrative

**No amendment.** The 2026 ruleset is a structural and numerical
clone of the 2024 / 2025 rulesets. RD 253/2025 (de 1 de abril) — the
only 2025 modification to RIRPF — touched art. 69 (information
obligations), not art. 110. No further 2025 or 2026 modification to
art. 110 has been published as of the consolidated-text last-update
date 2026-02-28.

The 2026 ruleset file (`src/aeat/domain/formulas/_rulesets/modelo_130_2026.py`)
re-imports `_CASILLAS_2024` and `_CITATIONS_2024` from the 2024
module and declares its own `_FORMULAS` (with the
`modelo_130.2026.<reason>` formula-id namespace) and `_PARAMETERS`
(with the same numerical values bound to the 2026 effective range
of 2026-01-01 to 2026-12-31).

The `test_2026_no_drift_from_2025` regression in
`src/aeat/domain/formulas/_rulesets/test_modelo_130_2026.py` asserts the
no-drift invariant: an `Engine().audit_against(...)` pass over both
the 2025 and 2026 rulesets with the same fixture must produce
identical ledger entries.

## Watch-list — overlays not in the base ruleset

Two prospective overlays sit outside the base ruleset's surface and
are tracked separately under EPIC `#316`:

- **La Palma 60 % reduction (art. 110.2 / RD-ley specific)** — extends
  the existing 60 % reduction for activities with deduction rights to
  residentes en La Palma for 4T 2025 onwards. Caller-gated: the engine
  does not own the territoriality flag, so the overlay applies to
  user-supplied casillas (notably the post-clamp surface), not to the
  base ruleset's formula DAG.
- **Generic 60 % reduction (art. 110.2 — Ceuta / Melilla / Canarias)** —
  same caller-gated treatment.

Both overlays are out of scope for issue `#321`; their per-territory
implementations land in dedicated wave-2 issues on EPIC `#316`.

## Citation completeness

| Ruleset            | `computed=True` casillas | with `LegalCitation` | Coverage  | Status (per `#339` audit CLI) |
| :----------------- | :----------------------: | :------------------: | :-------: | :---------------------------- |
| `modelo_130.2024`  | 9                        | 9                    | 100,00 %  | OK                            |
| `modelo_130.2025`  | 9                        | 9                    | 100,00 %  | OK                            |
| `modelo_130.2026`  | 9                        | 9                    | 100,00 %  | OK                            |

The 2025 + 2026 rulesets re-import `_CITATIONS_2024`, so the citation
surface is identical: every `computed=True` casilla cites RIRPF
art. 110 and LIRPF art. 99 via the existing `_CITATIONS` tuple.

`uv run aeat audit rulesets citations` (the audit CLI from `#339`)
reports `OK modelo_130.2024 ... coverage=100.00%` and equivalently
for 2025 and 2026.

## Mutation-harness fingerprint (issue `#338`)

| Ruleset            | `sub_op` | `percent_rate_param` | `mul_div_scalar` | `brackets_threshold` | Notes                                  |
| :----------------- | :------: | :------------------: | :--------------: | :------------------: | :------------------------------------- |
| `modelo_130.2024`  | 8        | 2                    | 0                | 0                    | Per `EXPECTED_COUNTS` in kill-rate test |
| `modelo_130.2025`  | 8        | 2                    | 0                | 0                    | Identical to 2024 (clone)              |
| `modelo_130.2026`  | 8        | 2                    | 0                | 0                    | Identical to 2024 / 2025 (clone)       |

The aggregate mutation kill-rate over the populated surface remains
≥ 90 % (the issue `#338` floor) with the addition of the 2026 row.

## L1 public-anchor waiver — Modelo 130

**Decision.** No real public Modelo 130 declaración PDF is hash-pinned
under `tests/fixtures/pdf_corpus/l1_public_anchors/modelo_130/`.

**Rationale.**

Modelo 130 is the autónomo's quarterly *autoliquidación* of the IRPF
pago fraccionado. Every real Modelo 130 filing is a private
autoliquidación tied to a specific NIF and a specific quarter; AEAT
does not publish any specimen Modelo 130 declaración as a normative
exemplar. The Manual práctico de IRPF (an AEAT publication) contains
worked numerical examples *of art. 110* — e.g., a 4-quarter scenario
showing the cumulative-YTD calculation across 1T → 4T — but those
are textual exemplars in a manual, not the *printed PDF declaración*
the user receives at the end of an autoliquidación.

The closest public anchor available is the **AEAT instructions PDF**
(`https://sede.agenciatributaria.gob.es/Sede/.../instrucciones.html`).
That document is the *form instructions* (a guide for autónomos
filling in the form), not a *filed declaración* — it has no NIF, no
quarter-specific values, and no CSV. It cannot serve as a hash-pinned
extraction-target fixture.

**What this means for the Tier-L bar.**

The calc-verify-roundtrip bar for Modelo 130 is met via the L3
synthetic generator + extractor round-trip, plus the L2 (contributor-
private) anchors that ride elsewhere in the project's fixture tier
infrastructure. The L1 tier cannot be filled for Modelo 130 without
either a NIF-private leak (which violates the project's privacy
mandate) or a synthetic-rendered AEAT-instructions exemplar (which
would not exercise the extractor's NIF / period / CSV header logic).

The Tier-S modelos (190, 193, 347, 349) and Tier-R modelos (036, 037,
232, 369, 720, 840) face the same gap on the same grounds. The
project's audit trail covers this with the L3 synthetic round-trip
as the *primary* extraction-fixture bar; L1 anchors supplement when
available but are not gating.

**Closing the waiver.** This waiver expires on either of two
triggers:

1. AEAT publishes a normative specimen Modelo 130 declaración on its
   open-data portal (no precedent for any modelo to date; unlikely).
2. A contributor obtains explicit consent from a real autónomo to
   contribute a single fully-scrubbed Modelo 130 declaración as an
   L1 anchor under the project's privacy + scrubbing discipline. If
   so, this waiver is replaced by a hash-pinned PDF + a colocated
   round-trip test, and the table above is amended.

## Audit trail

| Date          | Author                         | Change                                                                  |
| :------------ | :----------------------------- | :---------------------------------------------------------------------- |
| 2026-04-27    | Issue `#321` implementation    | Initial manifest. 2024 / 2025 / 2026 ruleset state recorded as identical. |
| 2026-04-27    | Issue `#321` post-review fix   | Registered `Modelo130V2024Extractor` + `Modelo130V2026Extractor` sibling classes after Gemini PR-440 review surfaced that the registry was keyed only on `(modelo="130", año=2025, revision="2025.01")` and rejected 2024 / 2026 PDFs. Sibling classes inherit the `Modelo130V2025Extractor` extraction logic verbatim and pin only their own `template_revision` ClassVar — the form layout is unchanged across all three years. |
