---
tags:
  - '#plan'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_hash: 'sha256:b5de963257f1a44d8cdc82e18503069d782c1d03eef86cffc33bbedafe657a4e'
tier: L2
related:
  - '[[2026-08-04-minimo-descendientes-eligibility-adr]]'
  - '[[2026-08-04-minimo-descendientes-eligibility-research]]'
---

# `minimo-descendientes-eligibility` plan

## Description

Executes `2026-08-04-minimo-descendientes-eligibility-adr` in full. The Modelo 100
mínimo por descendientes derivation implements three of the seven conditions the law
states, and three of the omissions inflate the mínimo and under-declare tax. This plan
completes the eligibility predicate.

The ordering against `2026-08-04-profile-derived-selectors-plan` is a hard dependency,
not a courtesy: that plan closes the operator override which is today the only channel
by which a filer reaches a correct figure. Every Step here must land before that plan
reaches its refusal Phase.

## Steps

### Phase `P01` - Ground the thresholds in the registry

Author the Art. 58.1 rentas cap and the Art. 61 norma 2a own-return figure as registry money parameters across revisions 2020-2025, each with a legal-catalogue entry anchored to the bundled consolidated LIRPF text, so no regulatory literal enters Python.

- [x] `P01.S01` - Author the Art. 58.1 rentas-cap money parameter for revisions 2020-2025 with a legal-catalogue entry anchored to the bundled consolidated LIRPF clause; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/, src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P01.S02` - Author the Art. 61 norma 2a own-return money parameter for revisions 2020-2025 with its own legal-catalogue entry and corpus anchor; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/, src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P01.S03` - Verify every revision 2020-2025 loads with both new parameters resolvable and the legal-grounding gate green; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P02` - Complete the eligibility predicate

Add the two per-descendant factual inputs, extend the ordinary-eligibility test with the two exclusions, and generalise the norma 1a prorrata from the shared-custody special case to the entitlement rule, deriving it from profile signals with an explicit per-descendant override and a visible advisory.

- [x] `P02.S04` - Add the annual-rentas-excluding-exempt and own-return-filed facts to the descendiente axis in the profile schema and the descendant model; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/domain/contribuyente/family.py`.
- [x] `P02.S05` - Extend the ordinary-eligibility test with the Art. 58.1 cap and the Art. 61 norma 2a exclusion, taking both thresholds as caller-supplied registry parameters, and clear the twelve staging entries the drift gate carries for those parameters, deleting them outright if the consumer is visible to the gate AST scan or re-documenting each against its real consumer if it lands in the application-layer injector instead; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/domain/calculations/registry/tests/test_modelo_100_drift_detection.py`.
- [x] `P02.S06` - Generalise the norma 1a prorrata from the shared-custody special case to the entitlement rule, keeping shared custody as one trigger and adding an explicit per-descendant override; `src/cadrumo/domain/contribuyente/family.py`.
- [x] `P02.S07` - Derive the prorrata from marital status, spouse record, and declaration type when no explicit per-descendant answer exists, and raise a non-blocking advisory naming the descendant and the inference; `src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/domain/contribuyente/family.py`.

### Phase `P03` - Entry surface and grounded proof

Give the two new facts a production writer on the descendiente CLI flow, and prove each corrected scenario against an external oracle rather than against the formula under test.

- [x] `P03.S08` - Add the three new facts to the interactive descendiente flow, its prompts and its renderer, and correct the flag help string which still lists only the original keys so an operator refused at the write door cannot discover from help how to express the rentas figure, updating the four locale catalogues for that string through the locales CLI rather than by hand; `src/cadrumo/entrypoints/cli/_config/_descendiente.py, src/cadrumo/application/wizard/, src/cadrumo/locales/`.
- [x] `P03.S09` - Author two manual-oracle fixtures from the AEAT worked examples that carry printed figures, the Asturias two-entitled-filer example whose individual total is exactly half its conjunta total and which needs no CCAA correction because that comunidad exercised no normative competence, and the own-return-exclusion example grounded on its estatal column ONLY because its comunidad did diverge, then keep the cap and the anualidades flag as structural proofs since a zero, a preserved birth-order rank and a boolean flip are properties no printed figure would prove better; `src/cadrumo/_data/corpus/manual_oracles/, src/cadrumo/application/modelo/tests/`.
- [x] `P03.S11` - Replace the hardcoded ceiling literals in the two descendant test modules with reads of the registry parameters the campaign authored, matching how the new eligibility module already resolves them, because inlined regulatory figures decouple those tests from the authority and would keep them passing against a stale ceiling if a future revision moved it; `src/cadrumo/domain/contribuyente/tests/test_custodia_compartida.py, src/cadrumo/domain/contribuyente/tests/test_descendant_info.py`.
- [x] `P03.S10` - Confirm the autonomico aggregate and the anualidades eligibility flag are both corrected by the same predicate change; `src/cadrumo/application/modelo/tests/`.
- [x] `P03.S12` - Advise when a declared descendant contributes to the minimo with no rentas figure on record, because the existing undeclared diagnostic returns early whenever descendiente facts exist and that early return reasons about a declared ZERO, which does not hold for a declared descendant whose rentas are simply absent and who therefore over-claims silently; `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py, src/cadrumo/application/modelo/tests/`.

## Parallelization

`P01` and the schema half of `P02` are independent and may run concurrently. The
predicate work in `P02` depends on `P01` landing first, because the thresholds are
caller-supplied parameters rather than literals. `P03` depends on `P02`.

## Verification

The plan is complete when every Step is closed and all of the following hold: the two
new registry parameters resolve for every revision 2020-2025 and their legal-catalogue
entries pass the grounding gate; a descendant above the Art. 58.1 rentas cap contributes
zero to both aggregates; a household with two entitled filers receives a prorated
mínimo and an advisory naming the inference; the anualidades flag reads sin derecho for
a descendant excluded by the cap; and every expected figure in the new tests derives
from the bundled AEAT manual or the consolidated LIRPF text rather than from the
formula under test.
