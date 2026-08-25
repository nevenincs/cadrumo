---
tags:
  - '#plan'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-25'
body_hash: 'sha256:004399c8984c8b3d840aa0b48f472886736ed55cf146711b1871c1758678e988'
tier: L2
related:
  - '[[2026-07-13-docs-terminology-search-research]]'
  - '[[2026-07-13-docs-terminology-search-adr]]'
  - '[[2026-08-01-user-docs-search-consolidation-adr]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-plan]]'
---

<!-- RETIRED: S13, S40 -->

# `user-docs-search-consolidation` plan

## Description

Executes the user-docs-search-consolidation ADR and its amendments: the user-facing documentation search architecture is the project's one search deliverable. The plan delivered the licence boundary, deterministic multilingual search and casilla enrollment, legal-corpus records, built-site recall gates, and the publisher's preflight and post-publish verification contract. The later Rung-2 ruling retired the unsuccessful static-embedding experiment while preserving the lexical authority and its measured recall statement. One-time deployment execution is release operations state owned by the canonical release pipeline, not an implementation step in this plan.

The deterministic casilla enrollment clarification is now explicit in Phase P06. Registry projection, exact target/index enrollment, localized definition completeness, and sparse RAG relevance are separate contracts. P06 closes that distinction before semantic widening or deployment is treated as complete.

## Steps

### Phase `P01` - Rule amendment and campaign gating

Amend the licence rule at its source per ruling R5 and gate rung-2 dispatch on the boundary campaign's close, so the amended constraint is in force before any artefact is built and the two campaigns never overlap in the tree.

- [x] `P01.S01` - Amend the shipped-search-licence-clean rule source to the licence-and-provenance-scoped form ruled in R5 and propagate it with vaultspec-core sync in a coordinated quiet window; `.vaultspec/rules/shipped-search-licence-clean.md`.
- [x] `P01.S02` - Confirm the semantic-search-precompile-boundary plan is closed through its honesty review and record that confirmation before any rung-2 step is dispatched; `.vault/plan/2026-07-31-semantic-search-precompile-boundary-plan.md`.
- [x] `P01.S38` - Record in the licence rule source that the narrow embedding exception has no consumer at HEAD pending the Rung-2 ruling, rather than re-narrowing it, because a permission that oscillates is worse than one that is documented and re-narrowing would have to be reversed under the recovery branch, editing the vaultspec rules source and propagating with vaultspec-core sync in a coordinated quiet window, never hand-editing a generated provider copy and never authoring a new rule file for it; `.vaultspec/rules/aeat-documentation.md`.

### Phase `P02` - Rung-2 semantic layer delivery

Deliver the fired rung-2 verdict: a pinned licence-clean static-embedding model compiles a bounded int8 term-embedding matrix over the closed vocabulary on the dev box, shipped as committed provenance-stamped data and consumed client-side as a cosine tier in the shared search controller.

- [x] `P02.S03` - Author the rung-2 research record sharpening the offline-measurement caveat, the token-coverage bound, and the candidate pinned licence-clean static-embedding models with their licences and footprints; `.vault/research/`.
- [x] `P02.S04` - Retire the dev-side matrix compiler row under ADR Update 12 (D12), which ruled the Rung-2 deletion intended on the measured evidence that the compiled tier missed at 0.3125 against the ratified 0.10 line with token coverage 0.748 against the 0.8 floor, so there is no matrix to compile and no committed artefact to stamp; `retired by ADR Update 12; no artefact produced`.
- [x] `P02.S05` - Retire the client-side cosine tier row under ADR Update 12 (D12), the tier having been excised from the shared controller at a3376362ef and that excision now ruled intended, so no semantic tier is composed into the ladder and the browser stays lexical-authoritative by decision rather than by fail-closed default; `retired by ADR Update 12; controller stays lexical`.
- [x] `P02.S06` - Retire the matrix-provenance extension of the licence gate under ADR Update 12 (D12), there being no shipped matrix whose stamp, model licence or size bound could be validated, while every standing oracle-output, NC-ND and heavy-index bar in that gate is left untouched and the bounded-embedding exception stays open and unused per D14; `retired by ADR Update 12; existing licence bars intact`.
- [x] `P02.S07` - Retire the post-Rung-2 re-measurement row under ADR Update 12 (D12), since no post-Rung-2 ladder exists to measure, and record the 0.1875 pre-Rung-2 held-out miss rate as the project's standing and final honest recall statement rather than as a baseline awaiting improvement; `retired by ADR Update 12; 0.1875 stands as final`.
- [x] `P02.S25` - Establish a shared canonical JSON byte contract or equivalent artifact evidence so the browser can fail closed on nested matrix, manifest, bridge, target-list, and bundle self-attestation hashes before Rung-2 artifact acceptance; `dev/docs/terminology/ and docs/_static/cadrumo-docs.js`.
- [x] `P02.S26` - Define and implement independent provider-package/model and tokenizer-content verification from an ADR-ratified byte-manifest contract before Rung-2 matrix compilation or artifact acceptance; `dev/docs/terminology/_model2vec_provider.py and the accepted ADR/schema`.
- [x] `P02.S31` - Capture the real Pagefind lexical observations for the held-out corpus through the browser controller, reconcile the composed-ladder drop against the semantic evaluator, and preserve any failed gate as evidence; `dev/docs/terminology/ and docs/_static/cadrumo-docs.js`.
- [x] `P02.S32` - Introduce an independent versioned query and alias authority from RAG-grounded project vocabulary, bind its provenance into Rung-2 inputs, and recompile and remeasure without using held-out terms; `src/cadrumo/_data/terminology/ and dev/docs/terminology/`.
- [x] `P02.S33` - Propagate the nested query-alias authority provenance through the Rung-2 bundle and browser validator, rejecting the pre-amendment shape; `dev/docs/terminology/_rung2_bridge.py, docs/_static/cadrumo-docs.js, and dev/docs/terminology/tests/`.
- [x] `P02.S35` - Correct the two prose sites asserting a Rung-2 mechanism the tree no longer has, the miss-rate evaluator docstring still calling itself the deferral gate for a possible rung-2 static term-embedding matrix and the injector comment naming a Rung-2 bridge module deleted at a3376362ef, both of which are dead references under either branch of the Rung-2 ruling so this row is gated on nothing and executes immediately; `dev/docs/terminology/_miss_rate.py, dev/docs/pagefind_inject.py`.
- [x] `P02.S36` - Delete or re-home the three orphaned Rung-2 build-time modules, which are not merely consumerless but REDECLARE capabilities whose canonical homes are in core, because the canonical JSON module reimplements a byte contract that core hashing already owns for forty-eight consumer files and imports nothing from it, and the raw-byte content manifest reimplements the relative-path plus byte-length plus digest shape that the core corpus manifest already owns while the amendment authorising it named that very corpus manifest as its implementation precedent, and both reach for hashlib directly rather than the canonical chunked file digest, and the divergence WAS justified while a browser validator needed stricter cross-runtime bytes than the core serializer emits but that consumer was deleted so the justification no longer has a subject, the FINDING being unconditional while the REMEDY stays gated on the Rung-2 ruling because under the recovery branch the browser consumer returns and the stricter contract is needed again, so nothing is deleted before that ruling and the re-home option means folding the surviving need into the core homes rather than keeping a second authority in the dev tree; `dev/docs/terminology/_jcs.py, dev/docs/terminology/jcs_vectors/, dev/docs/terminology/_content_manifest.py, dev/docs/terminology/__init__.py`.
- [x] `P02.S37` - Resolve the zero-entry query alias authority that ships inside the wheel, which sits under the packaged data root and reaches a reader disk while carrying zero entries by its own execution record and zero consumers at HEAD, making it the only one of the four residue findings that reaches a user, the FINDING being unconditional while the REMEDY is gated on the Rung-2 ruling, removal from the shipped data root if the removal is ruled intended and restoration of its entries and consumers if it is ruled unintended; `src/cadrumo/_data/terminology/rung2/query-alias-authority.json, dev/docs/terminology/_query_aliases.py`.

### Phase `P03` - Verification and honest close

Prove the multilingual recall claim against the built site, keep every existing search gate green, and run the mandated fresh-context honesty review before the campaign is declared structurally complete.

- [x] `P03.S08` - Prove per-root multilingual recall on the built site with worked-example queries in each supported language recalling the concept and casilla records through behavioral gates, with each localized build emitted to its own root; `dev/docs/tests/, justfile`.
- [x] `P03.S09` - Run the fresh-context honesty review against the closure summary and persist it as a vault audit, closing or formally deferring every surfaced item; `.vault/audit/`.
- [x] `P03.S18` - Sweep for surviving artefacts of the overtaken audit campaigns beyond the two named commits and for incomplete-landing residue on the search surface, grounding the sweep with vaultspec-rag over both code and vault and confirming each candidate site with rg, and record the result with any remediation opened as new steps, noting instances already closed at HEAD by their commit rather than re-opening them; `.vault/audit/`.
- [x] `P03.S42` - Derive the per-language build recipes from the canonical output-language set instead of hand-listing three codes, and gate that every per-language recipe carries the per-root output-directory flag. RAISED BY THE 2026-08-13 SPLIT-CLOSURE HONESTY REVIEW. The deploy treats English as a root like any other and derives its root set from the enum, so the hand-listed recipes already omit a published root and a fifth language would leave them silently short. The only justfile-scanning gate that touches these lines asserts the build directory literal and would have passed identically before and after the 2026-08-13 fix, so the exact defect class that cost this campaign two mis-diagnosed blockers remains ungated; `justfile, dev/docs/tests/`.

### Phase `P04` - Deployed-contract remediation

Make the deployed site carry the decided search contract: the pages-only env value is retired for full mode on every root, the built language roots become reachable live, and a deployment-parity gate makes any future silent re-narrowing of the shipped contract a loud failure.

- [x] `P04.S10` - Retire the pages-only CADRUMO_DOCS_PAGEFIND_MODE deploy value so every root builds the full record-injected index, updating the deploy-environment test to pin full mode; `dev/deploy/docs_static_site.py`.
- [x] `P04.S11` - Add a deployment-parity gate that builds at least one localized root and asserts against the built artefact that every root's own loaded language index carries the full record corpus with count parity across the en, es, ca, and hu roots, never asserting at the injector-decision level or against an English-only fixture, so an env value or a language pin can never silently narrow any root's shipped contract; `dev/docs/tests/`.
- [x] `P04.S12` - Factor the publisher's build-and-validate prefix into one credential-free dry-run composition shared with publish, covering every language root, sitemap, record-bearing index, apex artifact, and language entry before upload; `dev/deploy/docs_static_site.py, dev/deploy/tests/test_docs_static_site.py, justfile`.
- [x] `P04.S19` - Make the record-injection language follow the build language with the card summary preferring the root language's description, so every localized root's records land in the index its palette loads, correcting the module's stale per-language docstring in the same change and citing the localized-root artefact measurement in the exec record; `dev/docs/pagefind_inject.py`.
- [x] `P04.S41` - Reconcile what the APEX root owes between the publisher's pre-upload validation and its post-publish index verification, then extend the dry run to cover it. RAISED BY THE 2026-08-13 SPLIT-CLOSURE HONESTY REVIEW. The shared validation covers the apex entry page and the language roots but not the apex root's own Pagefind bundle, while the post-publish verification includes the apex and raises when that built file is absent. That check runs after the upload and the cache invalidation, so an apex root that would fail the publish's own index check still passes the dry run and the dry run's verdict is not yet the publish's verdict. Settle the underlying contradiction first, because the entry validator's docstring states the apex no longer owes a Pagefind bundle since it correctly moved into the roots while the post-publish check still demands one, and decide the fate of the uncalled validator that would have covered exactly this and today has no production caller; `dev/deploy/docs_static_site.py, dev/deploy/tests/`.

### Phase `P05` - Legal-corpus record kind

Deliver the operator's core ask that no record kind ever served: project the legal catalogue's provisions into a fifth typed record kind with D1-conformant destinations on a generated legal reference surface, reconcile the hundreds of dead legal relevance targets to the new ids, and close the dead-target class in the gate.

- [x] `P05.S14` - Build the generated legal reference surface rendering per-law pages with per-provision anchors from one shared slug authority, each entry carrying its BOE permalink and catalogue metadata; `dev/docs/`.
- [x] `P05.S15` - Project the legal catalogue into the fifth search record kind with D1-conformant targets on the new surface and inject it beside the existing kinds with declared weights; `dev/docs/pagefind_inject.py`.
- [x] `P05.S16` - Reconcile the committed legal relevance targets to the new record ids and extend the target-resolution gate to refuse any target id no injector emits; `src/cadrumo/_data/terminology/relevance/`.
- [x] `P05.S17` - Add the legal per-kind parity gate proving anchor existence and destination-grounding coverage for every projected provision record; `dev/docs/tests/`.
- [x] `P05.S34` - Correct the three sites that ranked a legal provision in the DOC band above the modelo and casilla cards it grounds, and gate the agreement between a record's stamped weight and the class it displays under; `dev/docs/terminology/ and docs/_static/cadrumo-docs.js`.
- [x] `P05.S39` - Confine a per-query relevance boost to its own display-class band so a record that tops one query stops outranking whole classes above it for every query, deriving each band's ceiling from the one declared table rather than hand-listing it, and gate the invariant over the real committed corpus with a live-subject anchor that refuses to pass vacuously; `dev/docs/terminology/_unified_record.py, dev/docs/pagefind_inject.py, dev/docs/terminology/tests/test_relevance_boost_band_containment.py`.

### Phase `P06` - Deterministic casilla enrollment and definition contract

Close the distinction between registry projection, exact search enrollment, rich localized definition, and semantic relevance by making the deterministic casilla path measurable and reliable before further semantic widening.

The internal tasklist for this phase is the canonical P06 Step queue below. Each completed Step Record will carry a `## Tracking` section with the smaller execution items and their status; no duplicate free-floating checklist is created.

Formal review follow-up is part of that queue: the P06.S22 Pagefind result contract and P06.S23 registry-header parser must be corrected and freshly reviewed before P06.S24 acceptance gates are run. Source-only implementation is not a closure signal.

- [x] `P06.S20` - Separate deterministic casilla enrollment from sparse semantic coverage by adding a coverage census for projected, exact-target, definition, locale, and relevance surfaces; `dev/docs/terminology/_coverage.py`.
- [x] `P06.S21` - Carry registry help, input-kind, data-type, formula, and locale metadata through the casilla search projection and unified record without changing the opaque identity; `dev/docs/terminology/`.
- [x] `P06.S22` - Add a structured modelo/casilla exact-search route that resolves the canonical record and destination before lexical fallback; `docs/_static/cadrumo-docs.js`.
- [x] `P06.S23` - Resolve casilla relevance hits at individual-record granularity and refuse file-level first-record fallback; `dev/docs/terminology/_resolution.py`.
- [x] `P06.S29` - Correct the structured modelo plus casilla route to carry and match canonical casilla_id while retaining display-number and segmento fallback, and add the real-authority gate for an id that differs from its display number; `dev/docs/pagefind_inject.py, docs/_static/cadrumo-docs.js, dev/docs/terminology/tests/test_casilla_projection.py`.
- [x] `P06.S24` - Add real-behaviour search gates for M130 casilla 15 exact resolution, projection parity, localized definition completeness, and target resolvability; `dev/docs/tests/`.
- [x] `P06.S27` - Defer a Diseño-specific locator/parser contract until an official revision-aware source locator is available while retaining fail-closed target resolution; `dev/docs/terminology/_resolution.py`.
- [x] `P06.S28` - Reconcile the Diseño source-resolution verification gate with the validated individual-locator contract before verification runs; `dev/docs/terminology/tests/test_resolution.py`.
- [x] `P06.S30` - Prove the RAG sweep composition emits only authoritative injected record targets while preserving deterministic structured casilla enrollment, then refresh the manifest-admissible relevance input; `dev/docs/terminology/_sweep.py, dev/docs/terminology/tests/test_sweep.py, src/cadrumo/_data/terminology/relevance/`.

## Parallelization

Execution followed P01, P06, P04, P05, P02, then P03; document order preserves append-only identifiers rather than sequence. Built-site recall and publisher verification are implementation evidence. Release-triggered deployment and its live post-publish verdict are owned by `2026-07-27-canonical-release-pipeline-adr`, `2026-08-02-release-pipeline-full-automation-adr`, `.github/workflows/docs-publish.yml`, and the publisher itself; they are not recurring plan steps here. No step touched the boundary plan's deletion targets under `src/cadrumo/application/corpus_search/` or `command_search/`.

## Verification

- The synced shipped-search-licence-clean rule carries the licence-and-provenance scoping in every generated provider copy, and vaultspec-core sync reports clean.
- The deploy environment pins full mode, and the per-root deployment-parity gate fails when any root's own loaded language index misses the full record corpus or record-count parity across the en, es, ca, and hu roots breaks.
- The publisher verifies every delivered root and destination after upload and compares each served Pagefind entry with the validated built artifact; the release workflow owns when that outward-facing operation runs.
- The legal record kind ships with D1-conformant targets, its parity gate proves anchor existence and destination-grounding coverage, and the target-resolution gate refuses any relevance target id no injector emits, so the dead-target count at HEAD is zero.
- The deterministic casilla census distinguishes registry/projection, exact target, definition, locale, and RAG-relevance coverage; a casilla can be exact-enrolled without requiring a semantic mapping.
- The casilla search projection preserves the opaque identity while carrying the registry-backed localized definition and formula metadata needed by the destination surface.
- A structured `modelo` plus `casilla` query resolves the canonical record and stable destination before Pagefind fallback, and the M130/casilla-15 worked example is covered by a real-behaviour gate.
- Casilla relevance resolution never selects an arbitrary first record from a file-level hit; every committed casilla mapping resolves to the exact projected record it names.
- The Rung-2 matrix and browser tier remain retired under the accepted ruling; the lexical ladder and its 0.1875 held-out miss-rate statement are the honest shipped boundary.
- Worked-example queries in each supported language recall the concept and casilla records on every built language root, and the behavioral gates enforce that contract before publish.
- The docs build gates, the target-resolvability gates, and the Playwright ranking gates stay green.
- The fresh-context honesty review audit exists in the vault with every surfaced item closed or formally deferred before the campaign is declared complete.
