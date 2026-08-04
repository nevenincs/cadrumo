---
tags:
  - '#plan'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_hash: 'sha256:e556d986c56812a62c2f5c2576c272ae6303bb26e71a01a2832f9524049c13ed'
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

- [ ] `P01.S01` - Author the Art. 58.1 rentas-cap money parameter for revisions 2020-2025 with a legal-catalogue entry anchored to the bundled consolidated LIRPF clause; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/, src/cadrumo/_data/registry/aeat/legal/`.
- [ ] `P01.S02` - Author the Art. 61 norma 2a own-return money parameter for revisions 2020-2025 with its own legal-catalogue entry and corpus anchor; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/, src/cadrumo/_data/registry/aeat/legal/`.
- [ ] `P01.S03` - Verify every revision 2020-2025 loads with both new parameters resolvable and the legal-grounding gate green; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P02` - Complete the eligibility predicate

Add the two per-descendant factual inputs, extend the ordinary-eligibility test with the two exclusions, and generalise the norma 1a prorrata from the shared-custody special case to the entitlement rule, deriving it from profile signals with an explicit per-descendant override and a visible advisory.

- [ ] `P02.S04` - Add the annual-rentas-excluding-exempt and own-return-filed facts to the descendiente axis in the profile schema and the descendant model; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/domain/contribuyente/family.py`.
- [ ] `P02.S05` - Extend the ordinary-eligibility test with the Art. 58.1 cap and the Art. 61 norma 2a exclusion, taking both thresholds as caller-supplied registry parameters; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/application/modelo/_profile_binding.py`.
- [ ] `P02.S06` - Generalise the norma 1a prorrata from the shared-custody special case to the entitlement rule, keeping shared custody as one trigger and adding an explicit per-descendant override; `src/cadrumo/domain/contribuyente/family.py`.
- [ ] `P02.S07` - Derive the prorrata from marital status, spouse record, and declaration type when no explicit per-descendant answer exists, and raise a non-blocking advisory naming the descendant and the inference; `src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/domain/contribuyente/family.py`.

### Phase `P03` - Entry surface and grounded proof

Give the two new facts a production writer on the descendiente CLI flow, and prove each corrected scenario against an external oracle rather than against the formula under test.

- [ ] `P03.S08` - Add the two new facts as options on the descendiente CLI flow so a production writer exists before the sibling plan closes the override; `src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [ ] `P03.S09` - Prove each corrected scenario against the bundled AEAT manual or consolidated LIRPF text, never against the formula under test; `src/cadrumo/domain/contribuyente/tests/, src/cadrumo/application/modelo/tests/`.
- [ ] `P03.S10` - Confirm the autonomico aggregate and the anualidades eligibility flag are both corrected by the same predicate change; `src/cadrumo/application/modelo/tests/`.

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
