---
tags:
  - '#plan'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-01'
body_hash: 'sha256:b9dfa6b8832b441e938d26b81b438a378cfb5c702da4fe7b765988098810e803'
tier: L2
related:
  - '[[2026-07-31-semantic-search-precompile-boundary-plan]]'
  - '[[2026-07-13-docs-terminology-search-adr]]'
---

# `user-docs-search-consolidation` plan

## Description

Executes the user-docs-search-consolidation ADR and its Update 1: the user-facing documentation search architecture is affirmed as the project's one semantic-search deliverable, and this plan completes it against the measured deployed ground truth. The corpus detangle the ADR ruled (adjudication annotations on the two 2026-07-31 audits, R6 dispositions) was executed at ruling time and is not re-planned here. What remains: the shipped-search-licence-clean rule amendment (R5), the deployed-contract remediation Update 1 adjudicates (the pages-only env value never decided by any ADR, the unreachable language roots, the stale live site), the legal-corpus record kind no shipped surface ever carried despite hundreds of compiled legal relevance targets, the rung-2 semantic layer whose IMPLEMENT-RUNG-2 verdict the 2026-07-13 docs-terminology-search ADR fired and nothing delivered, and the verification close. This plan starts where the in-flight semantic-search-precompile-boundary plan ends and duplicates none of its deletion steps: every step here is docs-side or deploy-side, disjoint from the product tree that plan deletes.

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

- [ ] `P03.S08` - Prove multilingual query recall with Spanish, Catalan, and Hungarian queries recalling concept and casilla records through the behavioural gates on the built site, then re-run the same probes against the deployed site so a CI-built full-mode pass can never mask a pages-mode live site; `dev/docs/tests/`.
- [ ] `P03.S09` - Run the fresh-context honesty review against the closure summary and persist it as a vault audit, closing or formally deferring every surfaced item; `.vault/audit/`.
- [ ] `P03.S18` - Sweep for surviving artefacts of the overtaken audit campaigns beyond the two named commits and for incomplete-landing residue on the search surface, grounding the sweep with vaultspec-rag over both code and vault and confirming each candidate site with rg, and record the result with any remediation opened as new steps, noting instances already closed at HEAD by their commit rather than re-opening them; `.vault/audit/`.

### Phase `P04` - Deployed-contract remediation

Make the deployed site carry the decided search contract: the pages-only env value is retired for full mode on every root, the built language roots become reachable live, and a deployment-parity gate makes any future silent re-narrowing of the shipped contract a loud failure.

- [x] `P04.S10` - Retire the pages-only CADRUMO_DOCS_PAGEFIND_MODE deploy value so every root builds the full record-injected index, updating the deploy-environment test to pin full mode; `dev/deploy/docs_static_site.py`.
- [x] `P04.S11` - Add a deployment-parity gate asserting the built site's pagefind entry carries every decided record kind and every language root, so an env value can never silently re-narrow the shipped contract again; `dev/docs/tests/`.
- [ ] `P04.S12` - Close the gap that leaves the built language roots unreachable on the live site and prove es, ca, and hu roots respond after deploy; `dev/deploy/docs_static_site.py`.
- [ ] `P04.S13` - Redeploy and live-verify the full-mode index, the casilla destination pages, and the language roots, recording the live checks in the exec record; `dev/deploy/`.

### Phase `P05` - Legal-corpus record kind

Deliver the operator's core ask that no record kind ever served: project the legal catalogue's provisions into a fifth typed record kind with D1-conformant destinations on a generated legal reference surface, reconcile the hundreds of dead legal relevance targets to the new ids, and close the dead-target class in the gate.

- [ ] `P05.S14` - Build the generated legal reference surface rendering per-law pages with per-provision anchors from one shared slug authority, each entry carrying its BOE permalink and catalogue metadata; `dev/docs/`.
- [ ] `P05.S15` - Project the legal catalogue into the fifth search record kind with D1-conformant targets on the new surface and inject it beside the existing kinds with declared weights; `dev/docs/pagefind_inject.py`.
- [ ] `P05.S16` - Reconcile the committed legal relevance targets to the new record ids and extend the target-resolution gate to refuse any target id no injector emits; `src/cadrumo/_data/terminology/relevance/`.
- [ ] `P05.S17` - Add the legal per-kind parity gate proving anchor existence and destination-grounding coverage for every projected provision record; `dev/docs/tests/`.

## Parallelization

Execution order is P01, then P04, then P05, then P02, then P03; document order preserves append-only identifiers and does not encode sequence. P01 leads: S01 may land at any time in a coordinated sync window, and S02 gates rung-2 dispatch (P02) on the boundary campaign's close. P04 is the cheapest reader-facing win and goes first after P01: S10 and S11 in parallel, then S12, then S13 which needs both. P05 follows P04 so its live verification lands on a full-mode site: S14 then S15, S16 and S17 after S15 in parallel. Within P02 the order is S03 then S04, then S05 and S06 in parallel, then S07, which is the final measurement and must run after P04 and P05 so the baseline reflects the deployed ladder. P03 runs last: S08 after everything lands on the built site, S09 as the final close. No step here may touch the boundary plan's deletion targets under `src/cadrumo/application/corpus_search/` or `command_search/`.

## Verification

- The synced shipped-search-licence-clean rule carries the licence-and-provenance scoping in every generated provider copy, and vaultspec-core sync reports clean.
- The deploy environment pins full mode, and the deployment-parity gate fails when the built pagefind entry misses a decided record kind or a language root.
- Live checks pass and are recorded: the deployed pagefind entry carries the injected record kinds, `/_generated/casillas/303.html` resolves, and the es, ca, and hu roots respond.
- The legal record kind ships with D1-conformant targets, its parity gate proves anchor existence and destination-grounding coverage, and the target-resolution gate refuses any relevance target id no injector emits, so the dead-target count at HEAD is zero.
- The committed rung-2 matrix is int8, within the 1-3 MB bound scoped by the 2026-06-10 ADR, stamped with model id, licence, revision, and vocabulary fingerprint, and the extended licence gate fails when any stamp field is absent or the model licence is not MIT or Apache-2.0.
- The wheel content is unchanged: the matrix ships in the built docs only, proven by the packaging content gates.
- The re-taken held-out miss-rate report is committed and its figure is compared against the 0.1875 baseline in the exec record.
- Spanish, Catalan, and Hungarian palette queries recall the worked-example concept and casilla records on the built site, recorded by the behavioural gates.
- The docs build gates, the target-resolvability gates, and the Playwright ranking gates stay green.
- The fresh-context honesty review audit exists in the vault with every surfaced item closed or formally deferred before the campaign is declared complete.
