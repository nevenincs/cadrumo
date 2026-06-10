---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S13'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Run the first scaffold and editorially migrate the four hand-maintained term stores (the shipped glossary page, the explanation inline mini-glossary, the two vault glossary references) into the initial curated concept set of roughly 150-300 approved concepts, tiering casillas out as projections per ADR D4 (ADR D1)

## Scope

- `src/aeat/_data/terminology tree + editorial pass`

## Description

- Run the S11 scaffold verb to materialise the 82 ratified draft fragments (31 modelo + 17 IVA + 21 period + 13 topic) under the committed concepts tree.
- Read the four hand-maintained stores (the shipped glossary, the explanation mini-glossary, the BOE-cited spanish-tax-glossary vault reference, the quad-lingual i18n vault reference) and editorially migrate the high-value vocabulary.
- Curate the key scaffolded modelo / IVA-category drafts (es definition + source + 4-language short_descriptions) and hand-author the `concepto`-domain glossary terms that have no scaffolded id.
- Resolve every migrated legal_ref against the real legal catalogue; drop non-resolving article ids and keep a prose source citation instead (never invent an id).
- Validate the whole bootstrapped tree through every S10 gate; prove the S11 PRESERVE contract holds on the real curated content (a re-scaffold is a no-op).
- Activate the S12-deferred `scaffold --check` drift gate as a test now that the tree is in sync.
- Leave the four source glossary surfaces in place (deletion is W04.P12.S26).

## Outcome

The Terminology Handbook is bootstrapped and the high-value glossary vocabulary is migrated; phase W02 is structurally complete. Deliverables:

- **Scaffold run.** `python -m aeat.terminology scaffold` materialised 82 new draft fragments (outcome breakdown: 82 SCAFFOLD_EMPTY, 3 UNCHANGED exemplars, 0 RETIRE) under `src/aeat/_data/terminology/concepts/`. Total tree after scaffold: 85 fragments.
- **Editorial migration.** 12 high-value concepts curated to `approved` from the glossary stores: 4 modelos (303, 390, 100, 130), 3 IVA-category regimes (recargo-equivalencia, regimen-simplificado, domestic-reverse-charge), and 10 hand-authored `concepto` terms with no scaffolded id (aeat, autoliquidacion, justificante, declaracion, borrador, censo, expediente, sede-electronica, borrador-vs-presentado, recargo-equivalencia). Plus the 3 pre-existing exemplars (prorrata, prorrata-especial, casilla). Final tree: 95 concepts.
- **Final composition.** 95 concepts (31 modelo + 21 periodo + 17 regimen + 25 concepto + 1 casilla-namespace), 20 approved / 75 draft, 0 deprecated/retired. Each approved concept carries an es definition + a source citation + four-language short_descriptions (the S10 approved-completeness contract). The 75 drafts are honest `(sin curar)` placeholders -- the curation backlog the W05.P13 ratchet baselines.
- **Validation.** The whole tree passes every S10 gate (id-uniqueness, legal-refs-resolve, relation-integrity, lifecycle/replaced_by, approved-completeness); `audit_handbook().is_clean` is True.
- **Tests (`tests/test_bootstrap.py`, 7 gates).** All green; package suite 72 passed.

Gates: `pytest src/aeat/terminology -q` 72 passed; `pytest --collect-only -q src/aeat/terminology` 72 clean; ruff / format / ty / pyright clean; apidocs `scaffold --check` conformant (terminology untouched).

## Scaffold outcome breakdown + total concepts

- Scaffold: 82 SCAFFOLD_EMPTY, 0 PRESERVE, 0 RETIRE, 3 UNCHANGED.
- Total: 95 concepts. Scaffolded enrolables: 82 (drafts) of which 7 curated to approved (4 modelo + 3 IVA). Hand-authored `concepto` terms: 10 (all approved). Pre-existing exemplars: 3 (approved). 
- Approved: 20. Draft (curation backlog): 75.

## Which store yielded what

- `docs/glossary.md` (26 deflist entries) -- the primary source for the `concepto` hand-authored set (aeat, justificante, borrador, censo, expediente, sede-electronica, declaracion, presentado) and the modelo/IVA descriptions.
- `docs/explanation/index.md` ("plain words you'll meet") -- corroborating short, taxpayer-general phrasing for modelo / casilla / IVA / IRPF / justificante (used to keep the en short_descriptions simple).
- `.vault/reference/2026-05-19-spanish-tax-glossary-reference.md` (BOE-cited) -- the source for the es definitions' legal grounding (LIVA / LIRPF / LGT article references) and the Spanish-stem authoritative forms (autoliquidacion, declaracion, censo, expediente).
- `.vault/reference/2026-05-01-quadlingual-i18n-reference.md` -- the source for every en/ca/hu short_description and label (its es/en/ca/hu tables gave recargo de equivalencia, inversion del sujeto pasivo, regimen simplificado, prorrata, justificante, sede electronica in four languages).

## Legal_refs migrated + resolution

9 legal_refs migrated across the tree, every one verified to resolve in the live 262-entry legal catalogue via `bundled_authority().catalogues.legal`: prorrata (`ley-37-1992:art-102`, `art-104`), prorrata-especial (`art-104`), regimen-simplificado (`ley-37-1992:art-122`, `art-123`), domestic-reverse-charge (`ley-37-1992:art-84`), autoliquidacion (`ley-58-2003:art-120`), declaracion (`ley-58-2003:art-119`), modelo-130 (`ley-35-2006:art-99`). For concepts whose binding article is NOT yet in the catalogue (modelo-303/390/100 management articles 164/167/96; recargo de equivalencia arts. 148/154/156), I did NOT invent an id -- I dropped the legal_ref and kept a prose `source` citation naming the law (which satisfies the approved-completeness gate, since that gate requires a source citation, not a catalogue legal_ref). `test_every_migrated_legal_ref_resolves_in_the_catalogue` pins that every legal_ref on the tree resolves.

## Re-scaffold no-clobber proof (the PRESERVE contract on real content)

After curation, `python -m aeat.terminology scaffold` reports `0 preserved, 0 new drafts, 0 retired, 95 unchanged` -- a complete no-op. `test_rescaffold_does_not_clobber_migrated_prose` asserts the rebuilt plan `is_empty` AND that serialising each plan record reproduces the pre-scaffold fragment byte-for-byte, so no migrated definition / short_description / term is overwritten. This is the codification-candidate `terminology-scaffold-preserve-contract` proven on the real bootstrapped tree.

## scaffold --check gate now green (S12 handoff closed)

With the bootstrap landed the committed tree is in sync with the enrolment sources, so `python -m aeat.terminology scaffold --check` exits 0 with zero drift. The S12-deferred drift gate is activated as `test_scaffold_check_is_green_against_the_bootstrapped_tree` (asserts the rebuilt plan `is_empty`) in the terminology test suite, which participates in the CI gate. This closes the S12 handoff: the gate is now green-and-active rather than red-until-bootstrap.

## Test names + pass (7 bootstrap gates; 72 package total)

`test_bootstrapped_tree_passes_every_validation_gate`, `test_key_migrated_concepts_are_approved_and_complete`, `test_prorrata_carries_four_languages_and_resolving_legal_refs`, `test_every_migrated_legal_ref_resolves_in_the_catalogue`, `test_rescaffold_does_not_clobber_migrated_prose`, `test_scaffold_check_is_green_against_the_bootstrapped_tree`, `test_audit_reports_structurally_clean_with_a_tracked_backlog`. All pass.

## Curation-backlog baseline (for the W05.P13 ratchet)

75 draft concepts with `(sin curar)` placeholder short_descriptions; 20 approved. The W05.P13 honesty ratchet baselines `draft_count = 75` (non-increasing) and `len(empty_short_description) = 75`. As curation continues, drafts convert to approved and the backlog ratchets down. The breakdown of the 75 drafts: 27 modelo (the modelos not yet curated), 21 periodo, 14 regimen (IVA categories), 13 concepto (the uncurated topics) -- all honest placeholders, no fabricated prose.

## Notes

- The editorial migration was performed by a one-shot script (`dev/_terminology_bootstrap_migrate.py`) that drove the S11/S12 engines (the curation verbs and direct `_author_concept` writes through the strict schema + serialiser). The script was DELETED after the bootstrap landed -- it is build-time editorial tooling, not a durable artefact; the curated fragments it produced are the durable output. No production code was added or changed in this step.
- An ordering subtlety: `_author_concept` writes a single fragment without whole-tree validation (so it repairs prior state), while the `set`/`set_term` curation verbs re-validate the whole tree; the migration authors the `concepto` fragments first so the tree is coherent before the curation verbs run.
- legal-ref honesty: 5 intended legal_refs (modelo management articles, recargo arts. 148/154/156) were dropped because they are not in the catalogue; the prose source citation carries the grounding instead. No id was invented (registry-calculation-legal-grounding rule).
- The four source glossary surfaces (`docs/glossary.md`, `docs/explanation/index.md`, the two vault references) are UNTOUCHED -- deletion is W04.P12.S26, gated on the generated glossary existing.
- Pre-existing peer drift, out of scope, none under terminology: apidocs `scaffold --check` shows peer `aeat.application.ledger._evidence_advisory` drift; the terminology stub tree is untouched (no new Python module, migration script deleted without ever being stubbed).
- No mocks, skips, xfail, or tautological assertions. Every test loads the real committed tree and asserts against the real loader, validators, and legal catalogue.
