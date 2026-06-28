---
tags:
  - "#research"
  - "#casilla-schema-completeness"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-21-pdf-taxonomy-adr]]"
  - "[[2026-04-12-filing-draft-engine-adr]]"
---

# casilla-schema-completeness research

## Problem

The casilla corpus feeding the draft engine and the formula engine is an order of magnitude smaller than the real AEAT forms it purports to model. Any PDF-extraction work against real filing PDFs (clusters D, F) will produce `ExtractedCasilla` tuples whose IDs the corpus does not know about. The engine will silently drop them. Without fixing the corpus gap first, calc-verified import is unachievable.

## Grounded inventory

Audit of the repo produced these facts (file paths cite evidence):

- `corpus/casillas/modelo_130/2025Q4.json` — **4 casillas**: `01, 02, 03, 18`. Of these, `03` and `18` are computed with `formula_inputs` populated.
- `corpus/casillas/modelo_303/2025Q4.json` — **4 casillas**: `01, 03, 27, 71`.
- `corpus/casillas/modelo_390/2025.json` — **3 casillas**: `95, 96, 662`.
- `src/aeat/domain/formulas/_rulesets/modelo_130_2025.py` — declares **9 formula casillas**: `03, 04, 07, 09, 11, 12, 14, 17, 19`. Five of these nine (`04, 07, 09, 11, 12, 14, 17, 19`) have no entry in the corpus.
- `src/aeat/domain/formulas/_rulesets/modelo_303_2025.py` — declares **12 formula casillas** (referencing ~30 casilla IDs); only 1 of those 12 (`03`) is in the corpus.
- `src/aeat/domain/formulas/_rulesets/` has **no Modelo 390 ruleset** at all today — only rulesets for 130 and 303.

Cross-cutting gaps:

- `src/aeat/application/filing/runtime.py` — `build_runtime_schema_provider()` loads three hard-coded collections. No test asserts the collection's casilla IDs ⊇ ruleset's casilla IDs.
- `src/aeat/domain/schema/_boe_extractor.py` — can parse AEAT form PDFs to extract casilla definitions, but its pattern library only matches Modelo 130 (line 280–284). Blocked on live BOE verification (`TODO(#9-followup-live-boe-verification)` at `src/aeat/domain/schema/_fetch.py:132`).
- `src/aeat/domain/manuals/_schema.py` / `_stubs.py` — Manual práctico parser exists but is stub-level; not wired into corpus generation.
- No cross-validation test exists between corpus and rulesets. The two can drift silently and have already.

## Real-form casilla counts (from AEAT's published forms — not yet in the repo)

Derived from AEAT's official 2025 form templates on `sede.agenciatributaria.gob.es/Sede/modelos/`:

| Modelo | Real-form casilla count | Form structure | Corpus today |
| --- | --- | --- | --- |
| 130 | **19** (01–19) | Single-page quarterly | 4 (21%) |
| 303 | **~88** (01–88, plus *Anexo* casillas) | Multi-section monthly/quarterly; different layouts for estimación directa / módulos / SII filers | 4 (~5%) |
| 390 | **~680** (quarterly totals × 4 + annual reconciliation + Anexo operations) | Annual IVA summary | 3 (~0.4%) |
| 100 (RENTA) | **~hundreds** across Anexos A–K; structure varies by año | Multi-page multi-anexo | 0 |
| 111 | ~35 | Retenciones IRPF quarterly | 0 |
| 115 | ~15 | Retenciones arrendamientos quarterly | 0 |
| 180 | ~40 | Resumen anual retenciones arrendamientos | 0 |
| 190 | varies (~50) | Resumen anual retenciones trabajo | 0 |

The real-form casilla count for `130` (19) is **knowable** from a single published PDF; the ruleset at `_rulesets/modelo_130_2025.py` already hard-codes 9 formula casillas, implying knowledge of the rest. Nothing enforces that the rest land in the corpus.

## Sources of truth (ranked by authority)

The project has four potential sources for casilla definitions. Their authority ranks:

1. **AEAT BOE orders** (e.g., *Orden HAC/610/2024* for Modelo 130) — legally authoritative. Published as PDFs on the BOE website. `src/aeat/domain/schema/_boe_extractor.py` can parse these but is pattern-narrow and not on the mainline corpus build path.
2. **AEAT Manual práctico** — the operational reference AEAT publishes annually. `src/aeat/domain/manuals/` intends to parse it; currently stub.
3. **AEAT interactive form XML / HTML** — downloadable from Sede electrónica. Structured. Contains every casilla ID, label, data type, and some validation rules. No project surface reads it today.
4. **Printed form PDFs** — human-readable but lower fidelity for automation. Usable as a fallback.

**Recommended primary source**: AEAT interactive form XML (source 3). It's machine-readable, cert-free to download (published publicly), and directly reflects the real form. We can cross-check against source 1 (BOE) for legal authority.

## Divergence patterns already in-repo

Two concrete divergences the audit surfaced:

1. **Ruleset ⊃ Corpus** — the 130 ruleset names casillas `04, 07, 09, 11, 12, 14, 17, 19` which the corpus does not know. When the builder computes casilla `03` from `01, 02`, the downstream computed fields `04, 07, …` are silently orphaned — they never appear in the draft's `values` tuple, because `Modelo130Builder.build()` iterates `collection.all()` (casilla set from corpus). So **Modelo 130 drafts built today are missing 15 of 19 casillas.**
2. **Corpus ⊃ Ruleset (partially)** — casilla `18` is in the 130 corpus but not in the ruleset. The `formula_inputs` field says `18 = f(02, 03)` but no formula is registered. The builder's `_compute()` (lines 200–221 in `_builders/modelo_130.py`) hard-codes `03, 04, 07` only; anything else hits the `unknown formula casilla` branch.

These are silent correctness bugs. A test asserting "corpus covers at least every casilla the ruleset mentions, and vice versa" would have caught them at landing.

## Cross-cluster implications

- **Cluster D (extractor)** blocked: extraction pipeline produces `(casilla_id, value)` tuples; the builder drops any casilla IDs not in the corpus. Pre-requisite: corpus ⊇ real-form casilla set.
- **Cluster E (verification)** blocked: `Engine.audit_against` can only verify casillas the ruleset knows. If the ruleset is missing casillas 04–19 on Modelo 130, verification is 4/19 = 21% of the form. Pre-requisite: ruleset ⊇ corpus.
- **Cluster F (Modelo 100)**: the 0-casilla corpus state means Modelo 100 is structurally unsupported. Fleshing out the 100 corpus is in scope for F; the cluster-B bar defines *how* to do it (sourcing policy, test bar).
- **Cluster C (fixtures)**: real PDF fixtures need corpus completeness first to be meaningfully tested. A real 130 receipt / declaración can be dropped into extraction only when the 19-casilla schema exists.
- **Cluster G (justificante reframing)**: unaffected.
- **Cluster H (CI)**: adds the "corpus ↔ ruleset" cross-validation test that this cluster defines.

## Open questions (to close in the ADR)

1. **Primary source**: AEAT interactive form XML, BOE order, or both? Recommendation: **XML as primary** for casilla enumeration + data type; BOE as audit reference for legal authority; Manual práctico as human-readable companion.
2. **Schema-complete bar**: defined per modelo as "every casilla IDs on the printed form is enumerated with a data type, a label (trilingual), a source citation, and — if derived — a formula referencing the same ruleset the corpus pairs with." Quantified: 19 casillas for 130; ~88 for 303; ~680 for 390 (likely split into annual + anexo sub-schemas); 0→hundreds for 100 (deferred to cluster F).
3. **Delivery order**: 130 first (smallest, ruleset exists), 303 second (largest ruleset, highest volume), 390 third (but parked until a ruleset lands — see #221), then 111, 115, 180, 190. Modelo 100 is cluster F.
4. **Ruleset-corpus divergence policy**: one lint test + one pytest, both added in this cluster, that fail when corpus and ruleset disagree on the casilla ID set.
5. **Schema versioning**: today one version per modelo. Once we extend, we need `schema_version` keyed on `(modelo, año)` (formulas and casilla sets change yearly). Existing `SCHEMA_VERSION_DEFAULT` in `src/aeat/application/filing/_schema.py` becomes a default for legacy code paths only.
6. **Provenance on every casilla**: extend the pydantic record with `source_citation: str` (BOE / manual reference) and `source_url: AnyHttpUrl | None`. Audit trail requirement.

## Risk register

- **Regeneration risk**: if the corpus is ever auto-generated from AEAT sources, we need a hash-pinned snapshot to detect upstream drift. Proposed: store both the generated corpus and the SHA-256 of the source-XML in-repo.
- **Year-over-year drift**: AEAT renumbers casillas across reform years (e.g., 303 revisions post-*autoliquidación rectificativa*). The corpus must carry `valid_from` / `valid_to` per casilla when IDs move.
- **Trilingual label burden**: 88 casillas × 3 languages = 264 label strings for Modelo 303. Recommendation: ES authoritative; EN/HU best-effort and auto-translation permitted with human-review flag.
