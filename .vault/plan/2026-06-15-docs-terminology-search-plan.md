---
tags:
  - '#plan'
  - '#docs-terminology-search'
date: '2026-06-15'
modified: '2026-06-15'
tier: L2
related:
  - '[[2026-06-15-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-research]]'
---








# `docs-terminology-search` plan: grounding and glossary follow-up

Action every deferred docs-search follow-up: ground the staged legal
provisions, clear the glossary of internal-machinery concepts, and confirm the
committed-artefact boundary.

## Description

Closes the residuals recorded in the `2026-06-15-docs-terminology-search` audit
and the decisions in the `2026-06-15-docs-terminology-search` ADR. Three work
streams: (1) graduate the ten staged legal provisions in `tax-framework.toml`
from permalink-only to corpus-verified, fetching verbatim text from the BOE
Open Data API and adding the `required_text` the strict corpus gate checks;
(2) demote the internal search/calculation machinery concepts out of the
APPROVED taxpayer glossary tier to `deprecated` per the ADR enrolment policy;
(3) confirm the light precompiled data stays committed while the heavy generated
Pagefind index stays gitignored. Then codify the two ADR rules and run the
docs-search gates.

## Steps

### Phase `P01` - graduate the staged legal provisions to corpus-verified

Fetch verbatim BOE text for each staged provision, write its corpus excerpt, and
add the `required_text` the strict corpus gate verifies.

- [x] `P01.S01` - enrol corpus text for LIVA art. 148; `src/aeat/_data/corpus/normatives/html/ley-37-1992-art-148.html`.
- [x] `P01.S02` - enrol corpus text for LIVA art. 164; `src/aeat/_data/corpus/normatives/html/ley-37-1992-art-164.html`.
- [x] `P01.S03` - enrol corpus text for LIRPF art. 96; `src/aeat/_data/corpus/normatives/html/ley-35-2006-art-96.html`.
- [x] `P01.S04` - enrol corpus text for LIRPF art. 98; `src/aeat/_data/corpus/normatives/html/ley-35-2006-art-98.html`.
- [x] `P01.S05` - enrol corpus text for LGT art. 98; `src/aeat/_data/corpus/normatives/html/ley-58-2003-art-98.html`.
- [x] `P01.S06` - enrol corpus text for LGT art. 99; `src/aeat/_data/corpus/normatives/html/ley-58-2003-art-99.html`.
- [x] `P01.S07` - enrol corpus text for LGT art. 213; `src/aeat/_data/corpus/normatives/html/ley-58-2003-art-213.html`.
- [x] `P01.S08` - enrol corpus text for RGAT art. 3; `src/aeat/_data/corpus/normatives/html/rd-1065-2007-art-3.html`.
- [x] `P01.S09` - enrol corpus text for RGAT art. 18; `src/aeat/_data/corpus/normatives/html/rd-1065-2007-art-18.html`.
- [x] `P01.S10` - enrol corpus text for the sede electronica article, corrected to Ley 40/2015 art. 38; `src/aeat/_data/corpus/normatives/html/ley-40-2015-art-38.html`.
- [x] `P01.S11` - add the verified `required_text` to all ten entries; `src/aeat/_data/registry/aeat/legal/tax-framework.toml`.
- [x] `P01.S12` - run the strict corpus gate over the catalogue and confirm all thirteen tax-framework entries pass; `src/aeat/domain/calculations/registry/_legal.py`.

### Phase `P02` - demote internal machinery concepts out of the glossary

Set each internal search/calculation concept to `deprecated` with a scope_note,
removing it from the approved-only glossary and shipped search injection.

- [x] `P02.S13` - demote concept `barrido-rag`; `src/aeat/_data/terminology/concepts/barrido-rag.toml`.
- [x] `P02.S14` - demote concept `proyeccion-busqueda`; `src/aeat/_data/terminology/concepts/proyeccion-busqueda.toml`.
- [x] `P02.S15` - demote concept `mapa-relevancia`; `src/aeat/_data/terminology/concepts/mapa-relevancia.toml`.
- [x] `P02.S16` - demote concept `gancho-preprocesado`; `src/aeat/_data/terminology/concepts/gancho-preprocesado.toml`.
- [x] `P02.S17` - demote concept `clases-registro-busqueda`; `src/aeat/_data/terminology/concepts/clases-registro-busqueda.toml`.
- [x] `P02.S18` - demote concept `depuracion-licencia`; `src/aeat/_data/terminology/concepts/depuracion-licencia.toml`.
- [x] `P02.S19` - demote concept `manual-terminologia`; `src/aeat/_data/terminology/concepts/manual-terminologia.toml`.
- [x] `P02.S20` - demote concept `preflight`; `src/aeat/_data/terminology/concepts/preflight.toml`.
- [x] `P02.S21` - demote concept `binding`; `src/aeat/_data/terminology/concepts/binding.toml`.
- [x] `P02.S22` - demote concept `work-unit`; `src/aeat/_data/terminology/concepts/work-unit.toml`.
- [x] `P02.S23` - demote concept `verificado-completo`; `src/aeat/_data/terminology/concepts/verificado-completo.toml`.
- [x] `P02.S24` - confirm the generated glossary no longer renders any demoted concept and the handbook loads; `dev/docs/glossary_reference.py`.

### Phase `P03` - confirm the committed-artefact boundary

Confirm the heavy generated Pagefind corpus stays out of git while the light
precompiled data stays committed, after the corpus and concept changes land.

- [x] `P03.S25` - confirm the heavy Pagefind corpus is gitignored and untracked while the light precompiled data stays committed; `.gitignore`.

### Phase `P04` - codify and verify

Promote the two ADR decisions to project rules and run the docs-search gate
slice to verify the whole plan landed green.

- [x] `P04.S26` - promote the glossary-enrolment policy to a project rule; `.vaultspec/rules/rules/`.
- [x] `P04.S27` - promote the committed-light-data-not-heavy-index boundary to a project rule; `.vaultspec/rules/rules/`.
- [x] `P04.S28` - run the docs-search gates (terminology, glossary, relevance, pagefind, palette) and confirm green; `dev/docs/terminology`.







## Parallelization

Phases P01 and P02 are independent and may proceed in parallel (legal data vs
concept lifecycle, disjoint files). The ten corpus-fetch Steps P01.S01-S10 are
mutually independent; P01.S11 and P01.S12 depend on all of them. P03 is
independent of P01/P02. P04 is last: codification follows the landed decisions
and the gate run verifies the whole plan.

## Verification

- Every `tax-framework.toml` entry (all thirteen) passes the strict corpus gate
  (`verify_legal_catalogue(..., corpus_strict=True)`), so no provision remains
  permalink-only.
- The generated glossary renders zero internal-machinery concepts; the handbook
  loads with the demoted concepts at `deprecated`.
- `git check-ignore pagefind/` succeeds and `pagefind/` is untracked; the
  laundered `relevance.json` remains committed.
- The two ADR rules exist under `.vaultspec/rules/rules/` and `vaultspec-core
  spec rules show` resolves them.
- The docs-search gate slice (terminology, glossary, relevance, pagefind,
  palette) is green.

The plan is complete when every Step is closed.
