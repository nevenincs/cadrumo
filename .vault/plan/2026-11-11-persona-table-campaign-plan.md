---
tags:
  - '#plan'
  - '#persona-table-campaign'
date: '2026-11-11'
tier: L1
modified: '2026-11-11'
body_schema: body-v2
body_hash: 'sha256:4ed383e2a1454d7490f933cc2f81da20a03142cb168e72736286a563e8c18c8d'
---

# `persona-table-campaign` plan

Every row of the persona table green: calculate, verify and export, for all nine personas, every owed modelo and every supported year.

## Description

Approved 2026-11-11. Basis: the operator's directive of 2026-11-11 to CADRUMO-PRIME (the coordination directive that makes the persona table the single definition of done), and PRIME's tracking rules that assign this plan to ACCEPTANCE.

The persona table (`dev/acceptance/persona_table/`, run with `python -m dev.acceptance.persona_table run`) replays each catalogue persona under every supported horizon and takes every return the persona owes through create, calculate, verify and fichero-BOE export. A row is green only when a live calculation equals values grounded in an official source, verificado completo is granted and the file is written. The committed baseline in `dev/acceptance/persona_table/baseline/` is the ratchet; `persona_table check` fails when a baseline-green row turns red.

Each Step is one blocking cause shared by several rows, named with its cause id and owning lane. A Step is checked only by ACCEPTANCE, only when the rows it names are green on a feature/tui head, and its ledger row names that head. Lanes do not edit this plan. ACCEPTANCE adds a Step when the table shows a new shared cause.

Decision coverage: no costly decision is involved and no ADR governs this plan as a whole. A Step whose fix needs a decision records it in its own lane's ADR, and that ADR then governs the fix, not this plan.

## Steps

- [ ] `S01` - R1 (CALC-RENTA): make M100 calculate without ERROR_MODELO_WORK_INPUT_REQUIRED at the ledger phase; rows arrendador-jubilado, asalariada-familia, autonomo-alta-reciente, intracomunitario-desarrollador, minorista-recargo, traductora-profesional |100|horizon-2|0A; `src/cadrumo/application/aggregation`.
- [ ] `S02` - R2 (CALC-RENTA): resolve M100 operands 0604, 0609, 0610, 0670, 0695 and 0700; rows every activity persona |100|0A, every year; `src/cadrumo/_data/registry/aeat/modelos/100`.
- [ ] `S03` - R3 (CALC-RENTA): resolve the M100 inventory bindings 0177, 0181, 0182 and their casillas; rows electricista, intracomunitario, minorista, traductora, alta-reciente |100|horizon-1|0A; `src/cadrumo/domain/contribuyente/inventory`.
- [ ] `S04` - R4 (CALC-RENTA): clear verify finding xml_required_content_missing (Hijos/Hijo name); rows every M100 that reaches verify; `src/cadrumo/_data/registry/aeat/modelos/100`.
- [ ] `S05` - R5 (CALC-RENTA): clear export REFUSED_MODELO_REFUND_ACCOUNT_MISSING; rows arrendador-jubilado|100|0A; `dev/fixtures/personas/arrendador-jubilado`.
- [ ] `S06` - P1 (LIFECYCLE ruling A; harness ACCEPTANCE, data CALC-PAGOS): replay the prior-year M100 through live filed-capture so M130 1T verify is clean; rows electricista, fontanero, intracomunitario, minorista |130|1T, every year; `src/cadrumo/entrypoints/tests/persona_materialisation.py`.
- [ ] `S07` - P2 (CALC-PAGOS): state M130 under LIRPF DA 56a where it governs; rows fontanero, intracomunitario, minorista, alta-reciente |130|1T of the year the provision governs; `dev/fixtures/personas`.
- [ ] `S08` - P3 (ACCEPTANCE with LIFECYCLE): run quarterly modelos as a chain, filing each quarter locally before the next; rows every |130|2T..4T and |303| quarters now history-filed; `dev/acceptance/persona_table/sweep.py`.
- [ ] `S09` - L1 (LIFECYCLE): export after granted verify fails FAIL_MODELO_EXPORT; rows autonomo-alta-reciente|303|1T at the years before the horizon; `src/cadrumo/application/modelo/export.py`.
- [ ] `S10` - I1 (ACCEPTANCE then CALC-IVA): assert 303 values instead of history-filing them; rows electricista, fontanero, intracomunitario, sociedad-limitada |303|; `dev/acceptance/persona_table/sweep.py`.
- [ ] `S11` - I2 (CALC-IVA): alta-reciente 303 1T at the floor year calculates casilla 09 as 0 and verify reports printed_total_mismatch; row autonomo-alta-reciente|303|floor|1T; `src/cadrumo/application/aggregation`.
- [ ] `S12` - C1 (lanes, reviewed by ACCEPTANCE): state sourced values for owed returns that have none (no-oracle): 390, 349, 347, 190, 200 and the remaining 100, 130, 303 rows; `dev/fixtures/personas`.
- [ ] `S13` - F1 (ACCEPTANCE with persona data owners): replay personas whose history reaches horizon-2 at the floor year, so floor-year rows run instead of not-run; `src/cadrumo/tests/personas.py`.

## Parallelization

Steps owned by different lanes run in parallel. Ordering: S06 (P1) needs the persona aeat_filings data and the filed-capture harness together; S08 (P3) follows S06, because a 2T calculation needs a filed, verifiable 1T; S10 (I1) follows S08, because the 303 quarters stop being history-filed only once the chain files them; S07 (P2) restates the 2T to 4T values after S08.

## Verification

- Each Step closes when the table run on a feature/tui head shows every row it names as `pass`; the ledger row names that head and the table file.
- `python -m dev.acceptance.persona_table check <rows>` exits 0 on every new head against the committed baseline.
- The plan closes when the summary reads green equal to total, with no unverified, no-oracle, unsupported or not-run rows, and the final review passes.
