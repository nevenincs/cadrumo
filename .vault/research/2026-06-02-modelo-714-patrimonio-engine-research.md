---
tags:
  - '#research'
  - '#modelo-714-patrimonio-engine'
date: '2026-06-02'
modified: '2026-06-29'
related:
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
---

# `modelo-714-patrimonio-engine` research: `Modelo 714 Patrimonio engine — phased registry+fidelity then calc, corpus-gap sequenced`

Modelo 714 (Impuesto sobre el Patrimonio, Ley 19/1991) was one of the no-engine modelos the
foundational multi-year-renta gate ADR flagged as requiring engine-build work before it could
be authorized. The original 2026-06-02 research grounded that build by confirming the then-empty
registry scaffold and corpus gap against the in-repo sources, resolving the legal article
numbers against authority, and establishing the two-phase sequencing (registry+fidelity first,
calc second) required by the no-tautological-calculation-tests and aeat-calculation-grounding
rules.

## 2026-06-29 currentization

This research record is historical. Its June 2 "empty scaffold" and "corpus gap"
findings are superseded in the current tree:

- The bundled legal corpus now carries Ley 19/1991 art. 4.Nueve, art. 28,
  art. 30, and art. 31 under `src/aeat/_data/corpus/normatives/html/`, with
  reviewed legal catalogue entries in
  `src/aeat/_data/registry/aeat/legal/patrimonio.toml` (`BOE-A-1991-14392`).
- The 714 registry revision `2021-y-siguientes` is no longer an empty scaffold.
  It has casillas, constructs, application links, a completeness manifest, the
  BOE-grounded state-scale parameter `patrimonio-escala-estatal`, and formulas
  `patrimonio-cuota-integra-escala-estatal` (casilla 29, art. 30) and
  `patrimonio-reduccion-limite-80-suelo` (casilla 39, art. 31).
- The remaining M714 calculation tail is not corpus ingest or the art. 30
  escala. It is the full art. 31 same-year M100 joint-limit relation and the
  downstream manual result boxes that depend on that cross-modelo IRPF evidence.
- Focused verification on 2026-06-29: the M714 registry/baseline tests passed
  (22 tests) and the catalogue verification gate passed (70 tests).

## Historical findings from 2026-06-02

### Historical current state (verified in-repo on 2026-06-02; superseded by currentization)

- The 714 registry tree is an **empty scaffold**: `modelos/714/revisions/2021-y-siguientes/`
  contains only empty `application_links/` and `workbook_parity_refs/` directories — no
  casillas, no formulas, no parameters, and 714 is not in the calculation registry.
- Legal corpus grounds **only `ley-19-1991:art-28`** (base liquidable + €700.000 mínimo
  exento, CCAA-variable) in `legal/patrimonio.toml`. The €700k threshold and CCAA variation
  are the only patrimonio facts currently authoritative in-repo.
- The corpus file `corpus/aeat_official/instructions/modelo_714/files/modelo-714-procedure.html`
  is a 943-byte stub, not a full diseño de registro. The fichero layout authority is the
  `boe-modelo-714-form` / `-layout` source (Orden HAC/1023/2021, BOE-A-2021-7593), already
  registered in `patrimonio.toml`.

### Historical corpus gap (BLOCKER on 2026-06-02; now superseded)

At the time of the research, the calculation engine could not be authored without these, and
none was in the corpus.
Article numbers were resolved against authority (the BOE consolidated text and Spanish tax
references) because the brief and the upstream scratch notes disagreed on the vivienda
article:

- **`ley-19-1991:art-4` apartado Nueve** — exención of the vivienda habitual up to €300.000
  per contribuyente (the concept of vivienda habitual is taken by remission to IRPF
  art.68.1.3.º Ley 35/2006). **Correction recorded:** the task brief cited "art.4.Cuatro";
  the correct apartado is **Nueve**. Apartado Cuatro covers a different exemption category.
- **`ley-19-1991:art-30`** — Cuota íntegra: the tarifa / escala de gravamen, the progressive
  bracket table (approx. 0,2% up to 3,5%, state default, CCAA-variable).
- **`ley-19-1991:art-31`** — Límite de la cuota íntegra: the límite conjunto IRPF + IP
  (the 60% combined-quota limit, with the 80% reduction floor on the IP quota).

These had to be ingested from BOE before any tarifa or límite formula was authored. Hand-typing
the brackets or the 60%/80% percentages would have violated aeat-calculation-grounding and
no-tautological-calculation-tests.

### Engine primitives that already exist (no new operator needed for the tarifa)

- The `FormulaOperator` set already includes `lookup_bracket` (alongside
  `lookup_bracket_by_ccaa` and `lookup_bracket_by_entity_type`) in
  `domain/calculations/registry/_schema.py`. The tarifa cuota is expressible once art.30 is
  grounded as a parameter bracket table; the CCAA-variant scale uses `lookup_bracket_by_ccaa`.
- The same-year cross-modelo relation needed for art.31 has a wiring **precedent**: the
  M200↔M202 same-year relations under `modelos/2xx/.../relations/` (e.g. the M202 self-pagos
  relations and `modelos/200/.../records/relations.toml`) show how a modelo references another
  modelo's same-period value. The art.31 límite, however, is structurally novel for a
  cross-renta hook because it reads a SAME-YEAR M100 (IRPF) result with `filing_year_delta = 0`
  rather than a prior-year copy.

### Historical phasing decision

- **Phase A (registry + fidelity, NO calc):** ingest arts 4.Nueve / 30 / 31 into the legal
  corpus (step one, blocking); author the casilla schema from the M714 diseño de registro
  (Orden HAC/1023/2021); add a fichero-BOE fidelity roundtrip test. No calculation formula is
  authored in Phase A. This phase alone enrolls 714 at data-fidelity strength.
- **Phase B (calc engine):** author the cuota tarifa via `lookup_bracket` over the art.30
  bracket parameter, then the art.31 60% límite conjunto. The límite needs a same-year M100
  cross-ref (`filing_year_delta = 0` reading M100 base liquidable + cuota) — the one
  structurally-novel piece. In the current tree, art.31 is grounded and casilla 39 computes the
  80%-floor reference; the remaining tail is the full same-year M100 joint-limit relation.

### Historical cross-renta enrollment hook

Two-renta evidence has two parts: (i) asset-base year-over-year — a prior-year base seed via a
`previous_filing` binding `filing_year_delta = -1` proving the wealth base carries across two
714 filings; and (ii) the same-year M100 cross-ref (art.31). Oracle: the AEAT Patrimonio manual
worked example for the límite conjunto. Currentization: art.31 is now in the corpus; the
remaining implementation boundary is the same-year M100 relation and downstream result boxes.
