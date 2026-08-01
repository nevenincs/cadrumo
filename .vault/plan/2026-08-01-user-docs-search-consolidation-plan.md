---
tags:
  - '#plan'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-01'
body_hash: 'sha256:8a70b180930b2741eb88dfcbeade7e457a35de5f59bfdb0e7b9294c786887924'
tier: L2
related:
  - '[[2026-07-31-semantic-search-precompile-boundary-plan]]'
  - '[[2026-07-13-docs-terminology-search-adr]]'
---

# `user-docs-search-consolidation` plan

## Description

Executes the user-docs-search-consolidation ADR: the user-facing documentation search architecture is affirmed as the project's one semantic-search deliverable, and this plan completes it. The corpus detangle the ADR ruled (adjudication annotations on the two 2026-07-31 audits, R6 dispositions) was executed at ruling time and is not re-planned here; what remains is the shipped-search-licence-clean rule amendment (R5), the rung-2 semantic layer whose IMPLEMENT-RUNG-2 verdict the 2026-07-13 docs-terminology-search ADR fired and nothing delivered, and the verification close. This plan starts where the in-flight semantic-search-precompile-boundary plan ends and duplicates none of its deletion steps: every step here is docs-side (dev docs tooling, shipped docs assets, terminology data), disjoint from the product tree that plan deletes.

## Steps

### Phase `P01` - Rule amendment and campaign gating

Amend the licence rule at its source per ruling R5 and gate rung-2 dispatch on the boundary campaign's close, so the amended constraint is in force before any artefact is built and the two campaigns never overlap in the tree.

- [ ] `P01.S01` - Amend the shipped-search-licence-clean rule source to the licence-and-provenance-scoped form ruled in R5 and propagate it with vaultspec-core sync in a coordinated quiet window; `.vaultspec/rules/shipped-search-licence-clean.md`.
- [ ] `P01.S02` - Confirm the semantic-search-precompile-boundary plan is closed through its honesty review and record that confirmation before any rung-2 step is dispatched; `.vault/plan/2026-07-31-semantic-search-precompile-boundary-plan.md`.

### Phase `P02` - Rung-2 semantic layer delivery

Deliver the fired rung-2 verdict: a pinned licence-clean static-embedding model compiles a bounded int8 term-embedding matrix over the closed vocabulary on the dev box, shipped as committed provenance-stamped data and consumed client-side as a cosine tier in the shared search controller.

- [ ] `P02.S03` - Author the rung-2 research record sharpening the offline-measurement caveat, the token-coverage bound, and the candidate pinned licence-clean static-embedding models with their licences and footprints; `.vault/research/`.
- [ ] `P02.S04` - Build the dev-side matrix compiler that embeds the closed vocabulary and its token inventory with the pinned model and emits the bounded int8 matrix as committed, reviewable, provenance-stamped data; `dev/docs/`.
- [ ] `P02.S05` - Add the client-side cosine tier over the shipped matrix to the shared search controller so both the palette host and the search-page host rank through it inside the existing compose ladder; `docs/_static/cadrumo-docs.js`.
- [ ] `P02.S06` - Extend the licence gate to validate the shipped matrix's provenance stamp, model licence, and size bound while keeping every oracle-output and NC-ND bar intact; `dev/docs/tests/`.
- [ ] `P02.S07` - Re-run the held-out miss-rate measurement over the rung-2-enabled ladder and commit the report as the new standing baseline beside the 0.1875 pre-rung-2 figure; `src/cadrumo/_data/terminology/evaluation/`.

### Phase `P03` - Verification and honest close

Prove the multilingual recall claim against the built site, keep every existing search gate green, and run the mandated fresh-context honesty review before the campaign is declared structurally complete.

- [ ] `P03.S08` - Prove multilingual query recall on the built site with Spanish, Catalan, and Hungarian queries recalling concept and casilla records through the behavioural search gates; `dev/docs/tests/`.
- [ ] `P03.S09` - Run the fresh-context honesty review against the closure summary and persist it as a vault audit, closing or formally deferring every surfaced item; `.vault/audit/`.

## Parallelization

P01 leads: S01 may land at any time in a coordinated sync window, and S02 is the hard gate on all of P02 (the boundary plan owns the product tree until its honesty review closes). Within P02 the order is S03 then S04, then S05 and S06 in parallel (disjoint files), then S07 which needs the full ladder. P03 runs last: S08 after P02 lands in the built site, S09 as the final close. No step here may touch the boundary plan's deletion targets under `src/cadrumo/application/corpus_search/` or `command_search/`.

## Verification

- The synced shipped-search-licence-clean rule carries the licence-and-provenance scoping in every generated provider copy, and vaultspec-core sync reports clean.
- The committed rung-2 matrix is int8, within the 1-3 MB bound scoped by the 2026-06-10 ADR, stamped with model id, licence, revision, and vocabulary fingerprint, and the extended licence gate fails when any stamp field is absent or the model licence is not MIT or Apache-2.0.
- The wheel content is unchanged: the matrix ships in the built docs only, proven by the packaging content gates.
- The re-taken held-out miss-rate report is committed and its figure is compared against the 0.1875 baseline in the exec record.
- Spanish, Catalan, and Hungarian palette queries recall the worked-example concept and casilla records on the built site, recorded by the behavioural gates.
- The docs build gates, the target-resolvability gates, and the Playwright ranking gates stay green.
- The fresh-context honesty review audit exists in the vault with every surfaced item closed or formally deferred before the campaign is declared complete.
