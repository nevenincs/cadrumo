---
tags:
  - '#adr'
  - '#modelo-714-patrimonio-engine'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-714-patrimonio-engine-research]]"
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
---



# `modelo-714-patrimonio-engine` adr: `Modelo 714 Patrimonio engine — phased registry+fidelity then calc, corpus-gap sequenced` | (**status:** `accepted`)

## Problem Statement

Modelo 714 (Impuesto sobre el Patrimonio, Ley 19/1991) is one of the no-engine modelos the
foundational gate decision (`2026-06-02-modelo-multiyear-renta-adr`) flagged as requiring
engine-build work before it can be authorized. This ADR is a mechanism-specific ADR
co-backing the multi-year-renta campaign plan; it decides HOW 714 is built so its >=2-renta
enrollment becomes real.

The current state, verified in-repo: the `modelos/714/revisions/2021-y-siguientes/` tree is an
empty scaffold (only empty `application_links/` and `workbook_parity_refs/` dirs — no casillas,
formulas, or parameters; not in the calculation registry), and `legal/patrimonio.toml` grounds
only `ley-19-1991:art-28` (the €700.000 mínimo exento, CCAA-variable). The wealth-tax cuota
chain — the tarifa, the vivienda exemption, and the IRPF+IP combined-quota limit — is entirely
absent from the corpus. Building a calculation engine on top of that absence would mean
hand-typing tax brackets and percentages, which the project's grounding rules forbid.

The decision is therefore how to sequence the build so the calculation is grounded, and how to
express 714's cross-year behaviour (wealth base year-over-year, plus the same-year IRPF
cross-reference the límite conjunto requires).

## Considerations

- 714's genuine cross-year behaviour is the wealth base carried across two annual filings, plus
  a same-year dependency on the IRPF (M100) result for the art.31 límite conjunto.
- The engine primitives needed for the tarifa already exist: `FormulaOperator` includes
  `lookup_bracket` and `lookup_bracket_by_ccaa` (`domain/calculations/registry/_schema.py`), so
  no new operator is required once the bracket table is grounded as a parameter.
- A same-year cross-modelo relation has a wiring precedent (the M200↔M202 same-year relations
  under `modelos/2xx/.../relations/`). The 714→M100 art.31 reference is structurally novel only
  in that it reads a same-year IRPF result (`filing_year_delta = 0`) rather than a prior-year
  copy; the relation mechanism itself is established.
- Three legal articles are absent from the corpus and must be ingested first. Their numbers were
  resolved against authority because the upstream notes disagreed (see Constraints): art.4.Nueve
  (vivienda), art.30 (tarifa), art.31 (límite conjunto).

## Constraints

- **HARD GROUNDING PREREQUISITE — corpus-ingest is Phase-A step one and blocks all calc.** The
  tarifa brackets (art.30), the vivienda €300.000 exemption (art.4.Nueve), and the 60%/80%
  límite conjunto (art.31) MUST be ingested from BOE into the legal corpus before any tarifa or
  límite formula is authored. Hand-typing the brackets or the 60%/80% percentages would violate
  aeat-calculation-grounding and no-tautological-calculation-tests — the engine would assert
  numbers with no authoritative source on the snapshot. Until the ingest lands, Phase B does not
  start.
- **Legal-article correction recorded.** The vivienda habitual €300.000 exemption is
  Ley 19/1991 **art.4 apartado Nueve**, not "art.4.Cuatro" as the task brief stated. Verified
  against the BOE consolidated text and Spanish tax references (the vivienda concept is taken by
  remission to IRPF art.68.1.3.º Ley 35/2006, €300.000 per contribuyente). The tarifa is art.30
  (Cuota íntegra) and the límite conjunto is art.31 (Límite de la cuota íntegra). The plan must
  ingest under these corrected anchors.
- **Same-year M100 dependency is novel.** The art.31 límite reads the same-period IRPF base
  liquidable and cuota (`filing_year_delta = 0`). The relation mechanism exists, but a same-year
  IP→IRPF read has not been wired before; the plan must treat the wiring as a first-of-kind step
  and validate referential integrity at snapshot build.
- The exact art.31 límite formula is **deferred** until art.31 is grounded — the ADR fixes the
  shape (60% combined-quota limit with an 80% floor on the IP quota) but not literal coefficients.

## Implementation

A two-phase build. Phase A produces a grounded, fidelity-tested registry with no calculation;
Phase B adds the calculation engine on top of the now-grounded corpus.

**Phase A — registry + fidelity (no calc).**

- *Step one (blocking):* ingest `ley-19-1991:art-4` (apartado Nueve, vivienda €300.000),
  `ley-19-1991:art-30` (tarifa / escala de gravamen), and `ley-19-1991:art-31` (límite conjunto)
  into `legal/patrimonio.toml` from BOE (Ley 19/1991, BOE-A-1991-14461), each with `corpus_ref`,
  reviewed status, and `required_text` anchors, alongside the existing `art-28`.
- Author the 714 casilla schema from the M714 diseño de registro (Orden HAC/1023/2021,
  BOE-A-2021-7593) into `modelos/714/revisions/2021-y-siguientes/`. Casillas are `input_kind =
  manual` in Phase A.
- Add a fichero-BOE fidelity roundtrip test (per the roundtrip-discipline rule) proving the 714
  record serialises and parses against the BOE annex layout. This phase alone enrolls 714 at
  data-fidelity strength.

**Phase B — calc engine (after the corpus ingest).**

- Author the art.30 bracket table as a parameter and compute the cuota íntegra via
  `lookup_bracket` (CCAA-variant via `lookup_bracket_by_ccaa`), and the vivienda exemption from
  art.4.Nueve, reducing the base.
- Author the art.31 límite conjunto formula reading a SAME-YEAR M100 cross-ref
  (`filing_year_delta = 0` over M100 base liquidable + cuota), capping the combined IRPF+IP quota
  at 60% with the 80% reduction floor on the IP quota. The exact coefficients come from the
  art.31 corpus text ingested in Phase A; the formula is deferred until then.
- Wire the `modelo-714-...-calculation` application link (consumer
  `aeat.domain.calculations.registry`, `requires_snapshot = true`) only once the formulas exist.

**Cross-renta enrollment.** Two-renta evidence is (i) a `previous_filing` binding
`filing_year_delta = -1` seeding the prior-year wealth base, proving the base carries across two
714 filings, and (ii) the same-year M100 cross-ref. The enrollment E2E drives the real engine for
two distinct filing years; the oracle for the límite is the AEAT Patrimonio manual worked example,
usable only once art.31 is grounded — until then the E2E asserts structure and fichero-fidelity.

## Rationale

Sequencing registry+fidelity before calc is the only way to satisfy the grounding rules: the
calculation cannot be authored honestly while its tarifa and límite live nowhere in the corpus.
Phase A delivers real value (a grounded schema and a fidelity roundtrip) and a legitimate
enrollment path at data-fidelity strength, so 714 is not blocked end-to-end on the calc engine.
Re-using `lookup_bracket` and the established same-year relation mechanism keeps the new surface
minimal: the only genuinely-novel piece is the same-year IP→IRPF read for art.31, which is called
out explicitly so the plan and executor treat it as first-of-kind. Resolving the vivienda article
against authority — rather than copying the brief's "art.4.Cuatro" — keeps the corpus ingest
pointed at the correct statute, which matters because a wrong anchor would ground the engine on
the wrong text (the same failure mode the 721 ADR is correcting for monedas-virtuales).

## Consequences

- **714 gains a grounded, honest build path.** Phase A enrolls it at data-fidelity strength
  immediately; Phase B lifts it to a full cuota calculation once the corpus is complete.
- **Engine-build debt is real and sequenced, not hidden.** 714 cannot be authorized at calc
  strength until three BOE articles are ingested; the `authorized N/30` gate line will lag for
  714 until Phase B lands, which is the honest representation.
- **The same-year M100 cross-ref is a first-of-kind dependency** and a risk concentration: a
  wrong or missing same-year IRPF read silently breaks the límite. The plan must validate
  referential integrity at snapshot build and treat this as the riskiest step.
- **Pitfall — corpus shortcut.** The tempting failure is to hand-type the tarifa to "unblock"
  Phase B. The hard constraint exists precisely to forbid that; a reviewer must reject any 714
  calc formula whose brackets or percentages are not traceable to the ingested art.30/31 corpus.
- **Article-number correction propagates.** Any downstream plan step or fixture that copied
  "art.4.Cuatro" from the brief must be corrected to art.4.Nueve.

## Codification candidates

- **Rule slug:** `corpus-ingest-precedes-calc-authoring`.
  **Rule:** When a modelo's calculation engine depends on tax brackets, rates, or statutory
  limits not yet present in the legal corpus, the corpus-ingest of the governing BOE articles is
  a blocking prerequisite that must land before any calc formula is authored — hand-typed
  brackets or percentages with no authoritative snapshot source are forbidden, and the governing
  article numbers must be verified against authority rather than copied from a brief.
