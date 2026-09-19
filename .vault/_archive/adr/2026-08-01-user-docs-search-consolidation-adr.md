---
tags:
  - '#adr'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:f1edecc6d1911c9ce4b4c76f3f1efefeb54cab181adef32a6d0cffe9830567c2'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-adr]]"
  - "[[2026-06-10-docs-terminology-search-adr]]"
  - "[[2026-06-15-docs-terminology-search-adr]]"
  - "[[2026-07-13-docs-terminology-search-adr]]"
  - "[[2026-07-15-docs-terminology-search-adr]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-06-10-docs-terminology-search-research]]"
  - "[[2026-07-31-corpus-search-model-cache-capability-gap-audit]]"
  - "[[2026-07-31-semantic-code-deduplication-campaign-audit]]"
  - '[[2026-08-04-user-docs-search-consolidation-deterministic-casilla-enrollment-research]]'
  - '[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]'
---

# `user-docs-search-consolidation` adr: `user documentation search: affirm the precompile pipeline, adjudicate rung 2, reconcile the corpus` | (**status:** `accepted`)

## Problem Statement

The operator's 2026-07-31 directive restates the intent behind every semantic-search request in this project: semantic search was always a documentation-facing deliverable. When users are online and enter search queries, the documentation must find meaningful answers; this requires precompiling and shipping search data built against the bundled legal, modelo, and casilla definitions, multilingual by the reader's query language, deployed with the documentation site. It was never a product runtime capability and never an agent capability; vaultspec-rag is dev tooling used to compile it.

The corpus recorded that intent faithfully in one family and contradicted it in another. The `docs-terminology-search` family (`2026-06-10`, `2026-06-15`, `2026-07-13`, `2026-07-15` ADRs) IS the operator's deliverable, decided and substantially shipped. Ruling R3 of `2026-07-02-agent-harness-refoundation-adr` independently decided a product-runtime semantic stack, contradicting the already-accepted precompile doctrine and the F3 structural finding of `2026-06-10-docs-terminology-search-research` without citing either. The accepted `2026-07-31-semantic-search-precompile-boundary-adr` amends R3 and deletes the runtime stack (in flight as this record is authored), but rules only the demolition half; it does not state what the user-facing deliverable is, whether it is complete, or how the remaining commitments (the fired rung-2 gate) proceed.

The unresolved half became an active collision: on 2026-08-01 at 06:48 and 06:53, commits `4dd9810c8f` and `71a89d0d2d` landed hardening and centralization improvements to the exact surface the boundary plan was concurrently staging for deletion. Three questions therefore need ruling: the target architecture for user documentation search (boundary, artefact shape, multilingual mechanics, buildable-versus-aspirational); whether genuine semantic recall is achievable under the `shipped-search-licence-clean` rule or the rule needs a licence-rationale amendment; and the disposition of every corpus record that bears on the surface, including the structural failure that let two campaigns pull one surface in opposite directions.

## Considerations

- **What is verifiably shipped at HEAD.** The precompile pipeline of the 2026-06-10 ADR exists end to end: the Terminology Handbook authoring tree (`src/cadrumo/_data/terminology/` with `concepts/`, `relevance/`, `ratification/`, `evaluation/`), the vaultspec-rag preprocess hook wiring (`.vaultragpreprocess.toml` mapping corpus source kinds to the `dev/docs/preprocess` extractors), the sweep-launder-commit relevance data, the Pagefind compile and injection (`dev/docs/pagefind_inject.py`, `pagefind_index.py`), the generated glossary and per-modelo casilla destination pages (`dev/docs/glossary_reference.py`, `casilla_reference.py`, landed in `6e9332297d`), the palette and the palette-hosted search page, and the destination/target contract gates of the 2026-07-15 ADR. The docs site is live and deployed.
- **The operator's hook assumption holds in substance, not in mechanism.** The vaultspec-rag preprocess hooks do exactly one stage of the job: they feed the bundled corpus sources (normatives HTML, Disenos workbooks, PDFs) into the dev-side RAG index so the sweep oracle can retrieve over them. The hooks do not themselves emit a shippable artefact; the compiler in `dev/docs/` does, by sweeping the closed query vocabulary through the oracle, laundering the outputs to identifiers and rankings, and injecting them into the Pagefind index at docs build. The operator's expectation that "the pre-processing hooks would add the required pre-processing so that user documentation can pre-compile the rag semantic search" is satisfied by the pipeline as a whole, with the hooks as its ingestion stage.
- **F3 is the binding structural constraint.** Arbitrary user queries cannot be pre-embedded; what can be precompiled is a term-to-result mapping plus bounded term-level semantics. Open-vocabulary semantic recall requires a runtime embedding model wherever it runs, and both the boundary ADR (for the product) and the 2026-06-10 ADR's rung-3 rejection (for the docs site) bar that.
- **The rung-2 gate fired and nothing delivered it.** Update 2 of `2026-07-13-docs-terminology-search-adr` de-tautologized the miss-rate gate, measured 0.1875 against the ratified 0.10 line, and by its own ratified rule fired IMPLEMENT-RUNG-2 as "committed follow-up scope in its own pipeline (research, ADR, plan under a new feature)". No such research, ADR, or plan exists anywhere in the vault at HEAD. The corpus records a fired verdict with zero delivery records - an undelivered commitment, stated here plainly.
- **The codified rule over-tightened its own source ADR.** The 2026-06-10 ADR's codification candidate for `shipped-search-licence-clean` reads: artefacts must come from licence-clean sources (no NC/ND/gated models or datasets); embedding-derived data ships only as plain, human-reviewed data files. The codified rule text hardened this into a categorical "never ship vectors, sparse term weights, raw retrieval scores, snippets" - correct for the SPLADE-tainted oracle outputs it was written against, but categorical enough to bar the rung-2 artefact (an int8 term-embedding matrix) that the same family's D3 gate later fired, even when computed by a pinned MIT/Apache model over project-authored vocabulary. The corpus currently holds a fired gate whose implementation a rule categorically forbids.
- **Multilingual reality at the injection seam.** The docs build pins the page language to English (`conf.py`); Pagefind auto-loads only the page-language index, so per-language index splits would make es/ca/hu records invisible to the palette. `pagefind_inject.py` therefore injects every record once into the primary index with content carrying every language's terms - the Spanish term, the Catalan/Hungarian forms, unaccented variants, and all four language sections' descriptions. Cross-lingual RECALL is real (an es/ca/hu query matches); the pages, cards, and destinations render in English (with Spanish authoritative labels). Casilla localisation coverage is 3,381 of 6,330 projected records and is bounded by registry locale authoring, a separate workstream.
- **How the corpus permitted concurrent hardening and deletion.** Two mechanisms, both structural. First, a doctrine fork: R3 (2026-07-02) decided a runtime semantic architecture without reconciling against the accepted precompile doctrine or F3; two accepted ADRs under different feature tags then claimed one concept with opposite trajectories for 29 days, and each downstream campaign could cite a valid authority. Second, annotation-free audits act as standing dispatch queues: `aeat-swarm-audit-cadence` mandates that findings be actioned rather than rot, so `2026-07-31-corpus-search-model-cache-capability-gap-audit` (whose recommendation the boundary ADR explicitly declined) and `2026-07-31-semantic-code-deduplication-campaign-audit` (whose ranking-centralization remediation the boundary ADR resolved by deletion) kept driving work after the ruling, because nothing on the audit documents said otherwise. The re-read-HEAD discipline catches stale FILE facts, not stale DECISION facts. Both audits carry adjudication-update annotations as of this record's date.

## Considered options

- **O1, affirm the docs-terminology-search architecture and complete it** (deliver rung 2 under an amended, licence-scoped rule; keep the boundary ADR's deletion as the product half). **Chosen.**
- **O2, demolish and rebuild the docs search pipeline.** Rejected on measurement: the pipeline the operator described is the pipeline that exists - precompiled, shipped with the docs, built over the bundled authorities, multilingual at the query level, with vaultspec-rag strictly dev-side. The defect was never in this pipeline; it was the parallel product runtime stack (being deleted) and the corpus's failure to reconcile the two. Demolishing a delivered, gated surface to rebuild the same shape would be motion without change.
- **O3, affirm the pipeline but decline rung 2 (leave the fired gate unimplemented).** Rejected: D3's gate was ratified precisely to make the rung-2 decision falsifiable rather than vibes; overriding its fired verdict without new evidence re-tautologizes the gate. The measured 18.75 percent miss-rate is a real reader-facing recall gap, and the operator's stated bar is that queries "find meaningful answers".
- **O4, pursue open-vocabulary semantic recall (a browser transformer or a search backend service).** Rejected: rung 3 was rejected on footprint and licence grounds in 2026-06-10 and nothing has changed; a server-side search service contradicts the static-site deployment and adds a runtime the operator explicitly scoped out.

## Constraints

- The in-flight `2026-07-31-semantic-search-precompile-boundary-plan` owns the product-side deletion; this record does not duplicate or re-sequence any of its steps and its companion plan starts where that plan ends.
- `shipped-search-licence-clean` remains binding until amended through its `.vaultspec/rules/` source and `vaultspec-core sync`; the amendment is scoped in R5 below and is a correction of an existing rule, permitted under the codification retirement (no new rule is authored).
- The docs build stays offline-hermetic and CPU-only; everything embedding-derived runs on the dev box and lands as committed, reviewable data.
- Registry locale coverage (casilla labels in en/ca/hu) is registry authoring work outside this feature, exactly as the 2026-06-10 ADR scoped it.

## Implementation

**R1 - The deliverable, named.** The project's one semantic-search deliverable is the reader-facing documentation search: precompiled on the dev box, deployed with the documentation site, built over the bundled authorities (the legal catalogue and normatives corpus, the modelo and casilla registry, the Terminology Handbook, the introspected CLI tree), answering queries in the reader's language. The `docs-terminology-search` architecture is AFFIRMED as that deliverable. No product-embedded semantic surface exists or returns; the boundary ADR governs that side and stands untouched.

**R2 - The boundary, stated once.** Dev side (GPU box, never CI, never shipped): the vaultspec-rag service, the preprocess hooks in `.vaultragpreprocess.toml` running the `dev/docs/preprocess` extractors, the query-vocabulary sweep, the typed chunk-to-target resolution, and the laundering. Committed (reviewable light data only): the Handbook fragments, the laundered relevance mappings, synonym/ratification/evaluation data, and - once R5 lands - the rung-2 matrix with its provenance stamp. Build time (CI or dev box, CPU, offline, deterministic): glossary, casilla, and CLI reference generation, the Pagefind index, and record injection. Shipped: the built docs site only. Never anywhere: the RAG service at runtime, raw oracle outputs, NC/ND-derived data, model downloads, or a search server.

**R3 - The artefact, concretely.** The shipped search artefact is the Pagefind index over the built site plus the injected typed records (CONCEPT, CASILLA, CLI, PAGE) carrying display classes, laundered relevance weights, and D1-conformant destinations per the 2026-07-15 contract, queried entirely client-side by the shared search controller hosted in the Ctrl-K palette and the `search.html` page. It contains identifiers, orderings, ratified terms, and rendered text from the project's own bundled data - and, under R5, one bounded int8 term-embedding matrix.

**R4 - Multilingual, honestly.** Multilingual means multilingual QUERY recall over a single English-paged site: every injected record carries its Spanish authoritative term, its declared en/ca/hu forms, and unaccented variants, so a reader typing in any of the four languages recalls the record; destinations render the authoritative Spanish labels plus localised labels where the registry carries them. This is the buildable shape and it is shipped. Translated documentation PAGES are not part of this deliverable and must not be smuggled into it; if the operator wants a localised site, that is a separate docs-i18n decision with its own cost. Casilla-label coverage in en/ca/hu grows only through registry locale authoring.

**R5 - Semantic recall within the licence constraint; the rule is amended, and rung 2 proceeds.** Genuine open-vocabulary semantic recall is NOT achievable within the standing constraints, and this record does not pretend otherwise: it requires a runtime model, rejected at every tier. What is achievable is bounded term-level semantics: rung 1 (shipped - declared aliases, ratified synonym rings, per-language stemming) plus rung 2 (fired, undelivered - a pinned licence-clean static-embedding model computes an int8 matrix over the closed vocabulary and its token inventory on the dev box; the client computes cosine over the shipped matrix to bridge queries that share no token with the target). Rung 2's honest limit is token coverage: a query whose tokens are all outside the matrix still misses, and the standing miss-rate baseline re-measures after it lands. To unblock it, `shipped-search-licence-clean` is AMENDED at its source to restore the 2026-06-10 ADR's own scoping: the categorical bars remain on anything derived from NC/ND/gated sources (SPLADE above all), on raw oracle outputs (scores, snippets, sparse maps), and on committing the heavy generated index; embedding-derived data MAY ship in the built docs (never the wheel) only when computed by a pinned, named, MIT/Apache-licensed model over project-authored or project-bundled vocabulary, committed as bounded, reviewable, provenance-stamped plain data. The licence gate extends to validate the provenance stamp and the size bound. This satisfies Update 2's "own pipeline under a new feature" requirement: this feature is that pipeline.

**R6 - Corpus disposition, record by record.**
- `2026-06-10-docs-terminology-search-adr`: STANDS, affirmed as the deliverable's architecture.
- `2026-06-15-docs-terminology-search-adr`: STANDS (enrolment policy, commit boundary).
- `2026-07-13-docs-terminology-search-adr`: STANDS as updated; its Update-2 IMPLEMENT-RUNG-2 verdict was an undelivered commitment until this record; delivery is sequenced in this feature's plan.
- `2026-07-15-docs-terminology-search-adr`: STANDS; its destination contract is the shipped result-item contract.
- `2026-07-02-agent-harness-refoundation-adr`: STANDS AS AMENDED (the R3 amendment stamp is already in place; no further change).
- `2026-07-31-semantic-search-precompile-boundary-adr`: STANDS, complete for the deletion half; this record is its companion for the deliverable half; nothing in it is amended.
- `2026-07-31-corpus-search-model-cache-capability-gap-audit`: findings STAND as measurements; its recommendation is OVERTAKEN (declined by the boundary ADR); annotated 2026-08-01.
- `2026-07-31-semantic-code-deduplication-campaign-audit`: the `command-and-corpus-vector-ranking` finding is RESOLVED BY DELETION; annotated 2026-08-01; all other findings unaffected.
- `shipped-search-licence-clean`: AMENDED per R5, through the `.vaultspec/rules/` source and sync, never the generated copies.
- Nothing is RETIRED: once the R3 amendment and the audit annotations stand, no vault record asserts a product-shipped semantic capability. The refoundation exec records remain as history of what was built and later deleted.

**R7 - The structural failure, adjudicated.** The 2026-08-01 collision had two causes and each gets a standing remedy within existing discipline (no new rule is authored). Cause one, the doctrine fork: an ADR that decides an architecture for a concept another accepted ADR already governs MUST cite and reconcile that record or amend it explicitly - R3 did neither, and 29 days of dual authority followed. This is the `vaultspec-curate` reconciliation duty, and this record discharges it for this surface. Cause two, annotation-free audits as live dispatch queues: when an ADR declines, overtakes, or resolves-by-other-means an audit recommendation, the SAME change annotates the audit document with an adjudication update naming the ADR - because campaigns dispatch from audits, and a ruling that never reaches the audit never reaches the campaign, as commits `4dd9810c8f` and `71a89d0d2d` prove. Both audits are now so annotated; future rulings on audited surfaces follow the same pattern, which is the amendment-note discipline extended from ADRs to audits.

## Rationale

The operator's directive and the corpus's oldest accepted doctrine coincide exactly; the ruling therefore affirms rather than demolishes. The only demolition warranted - the product runtime stack - is already ruled and in flight, so re-ruling it would fork authority again. The rule amendment is the narrowest change that dissolves the fired-gate-versus-categorical-rule contradiction: it restores the source ADR's licence-scoped intent, keeps every SPLADE/oracle/heavy-index bar intact, and adds provenance and size gates the original candidate lacked. Declining rung 2 instead would have re-opened the gate-tautology defect Update 2 closed. The structural remedies are deliberately procedural rather than codified: the codification channel is retired, and both remedies are enactments of existing duties (curation reconciliation; the amendment-note pattern) rather than new law.

## Consequences

- The user-facing deliverable has a single named architecture with a single decision trail; the dual-authority window is closed and both 2026-07-31 audits now tell their campaigns the truth at the document they dispatch from.
- Rung 2 becomes deliverable: the companion plan sequences model selection, the matrix compiler, the client cosine tier, the extended licence gate, and the post-landing miss-rate re-measurement. Until it lands, the 0.1875 baseline stands as the honest recall statement.
- The amended rule slightly widens what may ship (one bounded, provenance-stamped, licence-clean matrix in the built docs) and in exchange gains explicit provenance and size gates; the wheel ships nothing new.
- Multilingual expectations are pinned to what is built: query-level recall in four languages, English pages, Spanish authoritative labels. A future localised-site ambition is a separate decision.
- The two 2026-08-01 commits' work products are acknowledged as overtaken, not refuted: `4dd9810c8f` correctly implemented a recommendation that was valid when written; `71a89d0d2d` correctly deduplicated a surface that was live when audited. Their deletion by the boundary plan is the ruling working as intended.
- A future ADR wanting open-vocabulary semantic recall (rung 3 or a search service) must supersede both this record and the boundary ADR explicitly.

## Update 6 (2026-08-05): Rung-2 contract ratified; source implementation authorized

The Rung-2 research record leaves the operative model, tokenizer, query encoding, result bridge, and acceptance boundary as ADR questions. The operator has now approved this in-place refinement of R5. It concretizes the implementation contract without changing the precompile-only architecture or waiving the evidence gates.

**R8 - Pinned model and query encoding.** Rung 2 selects `minishlab/potion-multilingual-128M` at immutable revision `e7421cd79c75fc506b88bb75723ae0a234994720`, SPDX `MIT`, and dimension `256`, subject to immutable-revision and licence verification before an artifact is accepted. The provider and tokenizer implementation are pinned by package/version and content hashes, not by a mutable repository name. One versioned normalization algorithm is shared across the compiler and browser: NFKC normalization, Unicode lowercase, accent preservation, Unicode letter/number token extraction, and separator collapsing. Query words may map to multiple model subword ids; query-token rows therefore carry the exact token text, the complete ordered model-token-id tuple, and its count. Covered rows are dequantized, pooled by deterministic equal mean in query order with multiplicity preserved, and L2-normalized using float32 arithmetic. Special-token insertion, silent truncation, unknown-token substitution, IDF weighting, and stopword suppression are not permitted by this contract.

**R9 - Coverage and stable result bridge.** A query is eligible for semantic scoring only when it has covered tokens and passes the separately measured minimum coverage rule; empty, unknown, non-finite, zero-vector, and below-coverage queries abstain. Each semantic term row is linked by hash to ordered `record_id` and ranking-weight targets derived from the same authoritative `SearchRecord` projection that feeds Pagefind. A compact manifest hydrates those ids and metadata; the browser never reconstructs URLs, parses opaque ids, or invents a second destination authority. A unique structured modelo/casilla match remains first refusal. Exact identity, title, and declared-alias matches precede semantic candidates; semantic results are deduplicated by `record_id`, capped at five, and enter the existing display-class bands without overriding them. Ties resolve by direct-match strength, descending cosine, existing relevance weight, and canonical UTF-8 `record_id` order.

**R10 - Bounded acceptance and fail-closed release.** The matrix, query-token rows, result bridge, and manifest share one measured serialized-data envelope capped at 3,000,000 bytes; splitting the payload cannot evade that bound. The float32 and int8 paths are compared, and no expected held-out top-five result may be lost to quantization. The cosine floor, best-versus-runner-up margin, minimum token-coverage ratio, maximum allowed cosine drift, and payload headroom remain evidence-derived acceptance values rather than invented defaults. Until those values are measured and separately accepted, the browser semantic tier is disabled and fail-closed. Rung 2 may not be declared shipped until the held-out miss-rate is at or below the ratified 0.10 line with no locale or record-kind regression.

This amendment authorizes source implementation only. It does not authorize tests, builds, model downloads, Pagefind or runtime probes, generated-artifact release, deployment, or live publication.

## Update 1 (2026-08-01): deployed-contract ground truth folded in

An independent read-only investigation, verified against the tree and the live site, corrects three factual premises of this record; the rulings survive but two claims are amended. Original text above is preserved; this update governs where they conflict.

**The deployed contract is pages-only, and no decision authorised it.** `dev/deploy/docs_static_site.py:132` sets `CADRUMO_DOCS_PAGEFIND_MODE=pages` for every deploy root, and `dev/docs/build.py` skips the record-injection seam entirely in that mode; the live pagefind entry carries one language and 75 pages. The concept, casilla, and CLI record kinds this ADR describes as shipped are BUILT but have never reached a reader: R1's "substantially shipped" is corrected to "substantially built; the deployment discards the record kinds". The mode arrived inside an env-key rename commit (`3dd9e8611e`) with no ADR naming it - an unadjudicated env value acting as de facto architecture, the same unowned-authority class as R7's causes. RULING: the deployed contract is FULL mode on every root, adjudicated here; a deployment-parity gate asserts the built site's pagefind entry carries every decided record kind and every language root, extending the 2026-07-15 lesson (silent target breakage needs a gate that observes the shipped artefact) from record targets to the deployment contract itself.

**The legal corpus - the operator's first-named domain - has no record kind at all.** The committed relevance mapping carries 398 `legal:` target ids (measured at HEAD; the majority of all targets) pointing at real BOE provisions: the dev-side sweep genuinely mined the legal corpus, and the injector, which emits only `concept:`, `casilla-record:`, `cli:`, and `cli-option:` ids, discards every one of them - compiled, then thrown away, so the 2026-07-13 D2 widening bought the reader nothing. RULING: a fifth record kind, LEGAL, is added under the 2026-07-15 contract - the legal catalogue's provisions project onto a generated per-law reference surface (the casilla-pages pattern: one shared anchor authority, D1-conformant site-relative targets, BOE permalinks rendered at the destination, a per-kind parity gate with destination-grounding coverage) - and the target-resolution gate is extended to refuse any relevance target id no injector emits, closing the dead-target class structurally.

**R4 is amended: localised page roots exist and are in scope.** The deploy matrix already builds per-language site roots (es, ca, hu) from committed gettext catalogues (`dev/docs/i18n.py`, `_build_language_roots`), each with its own Pagefind index; the live roots 404. R4's sentence "translated documentation PAGES are not part of this deliverable" is WITHDRAWN as contrary to the built surface: publishing the existing language roots is part of this deliverable, and the multilingual statement becomes query-level recall PLUS the per-language roots the deploy matrix builds. Growing the ~46 percent translation coverage remains its own authoring workstream, as before.

**The operator's hook assumption, restated without hedge.** No vaultspec-rag verb emits a deployable artefact: the preprocess hooks feed vaultspec-rag's OWN dev-box index so the sweep can mine the corpus, and everything shippable is compiled by this repo's `dev/docs/` pipeline. The Considerations paragraph's "holds in substance" is retired in favour of this plain statement.

The live 404 on `/_generated/casillas/303.html` is deployment staleness (the destination pages landed at HEAD after the last deploy) and is closed by the redeploy step. The companion plan gains two phases for this update (deployed-contract remediation, legal record kind), sequenced before rung-2 so the final miss-rate baseline is measured against the ladder a reader actually reaches.

## Update 2 (2026-08-01): operator scope clarification and the misattribution teardown

The operator's follow-up directive sharpens scope and adds one requirement; this update rules on both. Original text stands; this update governs where sharper.

**Scope boundary, read precisely.** "A legal grounding rag search from the cadrumo plugin" is OUT of scope: that is the agent-facing product capability the boundary ADR deletes, and its deletion is hereby re-confirmed with the door closed on revival. Legal material as a searchable USER-DOCS record remains IN scope: the operator's own specification for the docs feature names "the bundled actual legal and modelo and casilla definitions" as the search data, so the LEGAL record kind ruled in Update 1 (plan phase P05) proceeds. These are two different things - a runtime RAG capability in the product versus precompiled legal records in the docs index - and this record refuses to collapse them into one exclusion. vaultspec-rag itself remains exactly what the operator restated: the dev-side semantic discovery surface over the vault and the code, used by agents and by the docs compile, shipped nowhere.

**Live outcome is the acceptance bar.** The operator's overriding requirement - meaningful search over the user docs must ACTUALLY EXIST for a live reader - ratifies the Update 1 ordering (deployed-contract remediation first, machinery later) and hardens two plan surfaces: S08 now re-runs its multilingual recall probes against the DEPLOYED site so a full-mode CI build can never green-mask a pages-mode live site, and the deployment-parity gate plus the S13 live checks are the standing guard that the shipped contract equals the decided contract.

**The misattributed artefacts, ruled on individually.** The two commits R7 diagnosed were mapped file by file against the boundary plan's staged sweep at HEAD:
- `4dd9810c8f` (loader hardening executed after the ADR declined it): its `_model_loader.py`, `_embed_build.py`, and `test_query_embed.py` changes are all inside the boundary plan's staged deletion set; its `pyproject.toml` delta (the explicit dependency declaration the overtaken audit recommended) is retired by the boundary plan's packaging step that deletes the `search` extra and its pins. Fully covered; nothing survives.
- `71a89d0d2d` (ranking centralization executed after the ADR resolved the finding by deletion): the module it created (`_ranking.py`, `test_ranking.py`) is staged for deletion, and every consumer it rewired (`command_search/_index.py`, `corpus_search/__init__.py`, `_retrieval.py`, `_embed_build.py`) is inside the boundary plan's rewire-and-delete commit. Fully covered; nothing survives.
No separate teardown campaign is opened: opening one would duplicate the boundary plan's staged work, the exact double-authority failure R7 diagnosed. What this feature adds instead is the residual sweep (new step P03.S18): a vaultspec-rag-grounded pass over BOTH code and vault for artefacts of the overtaken audit recommendations BEYOND the two named commits, each candidate confirmed with rg, findings recorded and remediated as new steps. The sweep runs after the boundary plan lands so it measures the post-deletion tree, not the mid-sweep one.

## Update 3 (2026-08-01): locale capability ruled

The operator has escalated locale capability to a hard architectural requirement ("absolutely critical that we deploy an architecture that is locale capable"). This update tests R4 against measured ground truth rather than defending it, and rules on the four open questions. Scope stays inside this feature: the ruling sharpens R4 and Update 1; no new record is needed.

**Ground truth, verified.** The English build injects records correctly (one `en` language, 7,890 records beside 1,934 pages). Each localized root is a separate site with its own Pagefind index - a DECIDED shape, not drift: the accepted `2026-07-18-user-docs-localization-adr` establishes the gettext catalogues, the per-language roots, and per-language index regeneration at deploy, and its consequences explicitly name "localized search relevance work" as later work. The seam between that record and this feature's injection design is therefore UNDELIVERED, not forked. The delivery gap is one line of mechanism: `_PRIMARY_LANGUAGE = OutputLanguage.EN` is a hardcoded constant (`dev/docs/pagefind_inject.py:197`) and every record injects under it (`:306`), while a `--language es` build renders pages Pagefind indexes as `es` and the palette auto-loads only the page-language index - the injector's own comment states that a record in a non-loaded language index is invisible. Prediction from code, pending the in-flight artefact measurement: localized roots build an `es`/`ca`/`hu` page index plus an `en` record index their palettes never load, so their readers see pages-only search. The module's opening docstring still describes a per-language-section injection design its own implementation comment contradicts - a truth defect the fix corrects in passing.

**L1 - The per-root shape is sound; what fragments is the injection-language pin.** Separate per-root indexes are the standard localized-site shape and stand as decided. As built, however, the localized roots deliver locale-partitioned English - a Spanish reader on the Spanish root gets strictly less than an English reader - which is NOT locale capability. One bounded change makes the same shape locale-capable: the record-injection language follows the build language, so every root's records land in the index its palette loads. No architectural rebuild is warranted.

**L2 - What locale capable means here, testably.** For every shipped root L in {en, es, ca, hu}: (a) the root's own loaded language index carries the FULL injected record corpus, with record-count parity across roots; (b) a query using any of a record's declared terms in ANY of the four languages recalls that record on EVERY root - the all-language content blob is the mechanism, and it is SUFFICIENT for recall (non-root-language terms lose stemming quality but keep exact and prefix matching, an accepted graceful degradation); (c) the card prefers the root language's description where a language section exists (a rendering-quality follow-up, not a gate); (d) the destination renders the authoritative Spanish label plus the root language's label where authored. Per-locale record CONTENT beyond this is enhancement, not precondition: recall is the load-bearing half and the blob delivers it once injection lands per root.

**L3 - The registry-label gap is real, bounded, and belongs to a named separate feature.** The ~19,765 registry casilla rows collapse to 6,330 projected search records (latest-revision dedupe, per the 2026-07-15 ADR), of which ~3,381 carry a non-Spanish label - roughly 2,900 projected records are Spanish-only per non-Spanish language, concentrated in M200 and M100. No search machinery makes those findable by en/ca/hu prose terms until labels are authored; this record does not paper that over. It is NOT this feature's scope (sustaining the 2026-06-10 ADR's explicit boundary) and NOT an accepted permanent limitation: it is the separate feature `registry-casilla-locale-coverage`, authored exclusively through `python -m cadrumo.locales modelo` per the modelo-locales-cli-authority rule, sized at roughly 8,800 leaf translations across the three languages. It does not gate deploy or locale capability of the SEARCH: casilla identity is intrinsically Spanish AEAT vocabulary (numbers and official labels reach every root via the blob), and the fully four-language concept cards bridge concept-level queries to their casillas.

**L4 - Deploy gate, conditional and narrow.** If the pending measurement confirms the predicted gap, ONE thing lands before publish: the root-language-aware injection fix with its per-root parity gate (plan steps S19 and the sharpened S11) - it is a one-module change, and publishing without it would ship localized roots strictly poorer than English against the operator's stated criticality, when the fix costs less than the explanation. If the measurement instead shows records already landing per root, publish now - the shape is sound and later work extends it. Deploy is NOT blocked on anything else: not registry label coverage (separate feature), not the ~46 percent prose translation (English fallback inside a localized root is normal in-progress localization), not rung 2, not the legal record kind. Nothing in the current shape is hard to change after a static-site redeploy; the gate exists because the fix is cheap and the operator's requirement is explicit, not because the shape would be cemented.

**Addendum: why no existing gate can see the gap, and what the new gate must therefore be.** Three confirmed blind spots let an `es` root shipping zero records pass every gate in the tree today: the deploy test loops over localized languages but asserts only that the injector RESOLVES (decision level, not artefact); the real-artefact injection gate builds its fixture site in English only and never builds a localized root; and the deployment's localized-root validation accepts any non-empty index chunks, which rendered pages alone satisfy. This is the same blind-gate class as the 2026-07-15 dead-target history and the pages-mode env value: the shipped artefact was never the observed surface. The S11 gate contract is therefore sharpened: it MUST build at least one localized root and assert against that root's BUILT ARTEFACT that the root's own loaded language index carries the full record corpus, with count parity across roots - never an injector-decision assertion, never an English-only fixture, never a non-emptiness check. This gate is the answer in BOTH measurement branches: if records are absent (the code-predicted branch), S19 fixes injection and the gate pins it; if records turn out present despite the pin, the gate pins whatever mechanism delivers them so it cannot silently regress. Sequencing follows the 2026-07-15 born-red lesson: the gate lands with or after the S19 fix, not before it.

## Update 4 (2026-08-01): the seed-idempotence contradiction, ruled; publish unblocked

Two how-to pages (`how-to/verification-reports`, `how-to/modelo-130`) fail the documentation coherence tier at the single-evidence attach guard while their golden tiers are clean. Both sides are correct as written and re-verified here: the guard (`src/cadrumo/application/ledger/_actions_manual.py`) refuses only a DIFFERING evidence id on a transaction that already carries one - same-id re-attach passes - and `evidence add` is deliberately additive with genuine-duplicate disambiguation (ratified, exec record `2026-07-01-determinism-replay-residual-P02-S02`; a unification experiment already failed against it and was reverted). The root cause is structural: seed recipes are inlined before EACH sequence's frames (`dev/docs/sequences/_seeds.py`) while the coherence tier executes the page's sequences cumulatively in one sandbox (`_runner.py`, `_execute_page_in_root`), so a seed carrying a non-idempotent-guarded write re-executes per sequence and collides with itself. The golden tier's self-sufficiency premise and the coherence tier's cumulative premise cannot both hold for such a seed - the framework has no page-level once-only premise. One fact the escalation did not carry, measured here: the colliding seed `iva-evidence-2026` is shared by sequences on SIX-plus pages (filing-spine references it in FOUR sequences on one page; also file-at-aeat, modelo-303, iva-lifecycle), so the two failing pages are the visible edge of a class, not an anomaly.

**Ruling: the coherence tier gains a once-per-page seed premise; both accepted decisions stand untouched.** A named seed recipe executes ONCE per page root in the coherence tier; sequences re-using it inherit its state, and the seed's captured values are hoisted to page scope so later sequences' placeholders resolve from the first execution (the one identified implementation complexity: the capture dict is currently reset per sequence in the page loop, `_runner.py` at `_execute_page_in_root`). The grounding is the seed rendering contract itself: a seed "runs and golden-gates like any frame, it merely renders collapsed" - collapsed setup is what a reader starting mid-page runs and what a cover-to-cover reader SKIPS, so blind per-sequence re-execution models a reader who does not exist. The premise makes the coherence tier MORE faithful to the page's reading model, not weaker; the golden tier keeps inlining seeds unchanged, so sequence self-sufficiency is untouched.

**Rejected alternatives, with reasons.** (a) Making `evidence add` idempotent: reverses a ratified product decision (genuine duplicate invoices must both persist) to serve a docs-harness need - tail wagging dog, already disproven by the reverted experiment. (c) Restructuring so the guarded write leaves the seed (per-sequence subjects): evaluated as requested, and workable for the two failing pages, but rejected as class-inadequate - it would fork the shared seed into per-page or per-sequence variants across six-plus pages, model a parallel-world-per-sequence reading experience no reader has, and leave the framework contradiction standing for the next seed that carries a guarded write.

**Publish adjudication.** The publish proceeds WITHOUT waiting for the framework change. The two coherence reds are harness-model artefacts, not reader-facing defects: the rendered pages are correct, every sequence is golden-verified standalone, the cover-to-cover reader skips collapsed setup by the rendering contract, and the literal-minded reader who re-runs it meets an instructive refusal that names its own remedy - not corruption, not silence. Green is NOT being redefined: the publish evidence MUST name the two red coherence runs and cite this adjudication, so the red is recorded, adjudicated, and temporary rather than silently waved through.

**Ownership and handoff.** The once-per-page premise with page-scoped seed captures belongs to the sequence-framework campaign (the `docs-cli-sequences` surface), which amends or extends `2026-07-13-docs-cli-sequences-adr` when implementing and whose fix un-reds the two pages and immunises the latent sharing pages. This feature carries only the publish-record annotation requirement; it absorbs no framework or docs-content steps.

## Update 5 (2026-08-01): the translation-drift adjudication; publish-evidence contract extended

**A premise of Update 3 is corrected.** The "roughly 46 percent prose translation" figure this record inherited from the briefing was WRONG - and wrong in an instructive direction: the catalogues were 100 percent complete against STALE source. Readers were served confident translations of English that had been rewritten under them since 2026-07-25 (drift across 22 of 58 pages), and the completeness gate stayed green because it measured the catalogue against itself rather than against current source. The resync surfaced the truth with zero translations lost: per language, 3123 total, 3022 translated, 40 fuzzy, 61 untranslated. Update 3's L4 reasoning survives strengthened: honest English fallback inside a localized root is not merely "normal in-progress localization", it is strictly better than the confidently wrong translations the live site would otherwise keep serving.

**The operator's ruling, recorded: publish now, track the 303.** The 101 strings per language needing HUMAN translation are named, per-page, in the audit `2026-08-01-user-docs-localization-catalogue-drift-audit`, which also carries the no-fabrication mandate - agents MUST NOT invent Catalan or Hungarian strings; a fabricated translation is a defect shipped in a language no agent here can verify - and notes the five mechanical `download.md` punctuation alignments per language as trivially clearable. The backlog belongs to the `user-docs-localization` feature line through its gettext catalogues; this feature absorbs no translation steps. The red `test_docs_localization.py` gate is the backlog's enforcement teeth: it cannot silently rot.

**The publish-evidence contract is extended.** The requirement set for the two coherence reds in Update 4 now covers the 6 localization-gate failures (3 untranslated-delta, 3 punctuation-stale), for the same reason in the same words: green is not redefined; the red is named and adjudicated in the publish record, citing this update and the drift audit. The masking mechanism itself - the third observed-surface false-green of this one day, after the Update 3 addendum's blind-gate trio and the pages-mode env - is recorded as the drift audit's durable gate-design finding.

**Operational note for the publish procedure**, reported honestly and not claimed as reproduced: the cli-sequence check runs a nested pool of child interpreters under Sphinx and wedged once under heavy concurrent load (about 15ms CPU across 45s, zero output, orphaned subprocess). Message extraction no longer runs it, but a production docs build still does, and `dev/docs/sequence_build_gate.py` states no production path sets the opt-out. If the publish build ever stalls with zero output, that pool is the first place to look.

## Update 7 (2026-08-05): Rung-2 input provenance is a required bundle contract

Update 6 ratified the bounded Rung-2 model, encoding, bridge, and fail-closed acceptance boundary and authorized source implementation. This amendment refines that decision at the artifact boundary: the provenance already computed by the authoritative input assembler is part of the bundle identity, not an intermediate value that can be discarded. The source-implementation audit and the Rung-2 research/reference records identify this as a contract gap, not a change of semantic tier.

### Decision

`Rung2SearchBundle` MUST carry a required top-level `input_provenance` object. The bundle schema version increments with this field. The object is the existing immutable `Rung2InputProvenance` contract: a repository-relative source identity, the SHA-256 of the raw committed relevance bytes, and the canonical vocabulary and query-token fingerprints derived from the same authoritative inputs.

The compiler MUST propagate `Rung2CompilationInputs.provenance` into the bundle constructor. Bundle canonical JSON, the bundle artifact hash, and the measured serialized-byte envelope MUST include `input_provenance`; omitting it, substituting a second provenance source, or emitting a stale schema is a fail-closed error. The browser-visible bundle remains the sole shipped authority for this identity.

Python acceptance MUST validate the provenance shape, repository-relative source identity, and equality of its vocabulary/query-token fingerprints with the matrix contract. The browser validator MUST require and validate the embedded provenance object and its links to the matrix and bridge. It MUST NOT claim to recompute `source_sha256`: raw source bytes are not shipped. The browser therefore verifies the embedded, hash-covered provenance rather than inventing an independent source authority.

### Considered options

- **Discard the computed provenance.** Rejected: it leaves the compiler unable to prove which committed input set produced a shipped bundle.
- **Duplicate provenance in browser configuration.** Rejected: it creates a second authority and can drift from the bundle already carrying the matrix, bridge, manifest, hash, and size evidence.
- **Add required provenance to the bundle and validate it at both boundaries.** Chosen: one hash-covered identity travels with the artifact, with independent structural checks at the Python and browser seams.

### Constraints

This amendment does not authorize a model download, live RAG sweep, test run, build, generated artifact, Pagefind/runtime probe, artifact release, or deployment. It does not authorize raw source bytes or vectors to ship. The existing licence, vocabulary, query-token, matrix, bridge, record-manifest, size, and fail-closed decisions remain binding. The implementation is source-only until the deferred acceptance gates are explicitly run.

### Implementation

The source assembler remains responsible for reading the committed relevance bytes and deriving `Rung2InputProvenance`. The provider-backed compiler receives that value explicitly, constructs the schema-versioned bundle with the required field, and includes it in canonical hashing and byte accounting. Python acceptance checks the bundle-resident identity and cross-field fingerprints. The browser bundle validator checks the same required field and its matrix/bridge links before the semantic tier can become eligible. The implementation is governed by the source contract reference and the source-implementation audit, while the decision itself remains here.

### Rationale

The selected shape closes the exact provenance-loss finding without widening the runtime boundary or duplicating authority. It preserves Update 6's bounded, reviewable, licence-clean artifact rule while making the artifact's input identity durable and tamper-evident. The decision follows `2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research`, `2026-08-05-user-docs-search-consolidation-source-contract-reference`, and `2026-08-05-user-docs-search-consolidation-source-implementation-audit`.

### Consequences

Every future Rung-2 bundle consumer must understand the incremented schema and refuse bundles without provenance. Existing source-only acceptance and browser contracts require coordinated updates, and any measured artifact must be regenerated after those updates. The current relevance baseline and the deployment deferral are unchanged; this amendment makes the implementation traceable but does not turn the still-unbuilt Rung-2 tier green.

## Update 8 (2026-08-05): Rung-2 provider and tokenizer content attestation is a raw-byte manifest contract

Update 6 requires provider and tokenizer content hashes, but the source review found that the current fields do not define which bytes they cover or how an independent verifier recomputes them. This amendment resolves that semantic gap before provider verification is implemented. It does not authorize a model download, artifact generation, or release.

### Decision

Introduce one versioned `RawByteManifestV1` contract for the build-time evidence behind provider and tokenizer provenance. The same primitive is used for the provider distribution source, the pinned model snapshot, the tokenizer vocabulary role, and the tokenizer configuration role.

Each manifest contains a fixed purpose/role, the pinned repository/revision context, and entries with exactly `relative_path`, `byte_length`, and `sha256`. Entries cover regular files only. A verifier MUST reject symlinks, duplicate paths, absolute paths, traversal components, invalid POSIX spelling, case-colliding paths, missing evidence, unexpected files, and unclassified files consumed by the provider or tokenizer. Paths are normalized to repository-relative POSIX spelling and sorted by UTF-8 path bytes.

Each per-file digest is SHA-256 over the exact raw bytes. JSON is never parsed or reserialized before file hashing. The manifest root digest is SHA-256 over UTF-8 canonical JSON with a fixed schema version and fixed keys, sorted object keys, compact separators, no timestamps, and no machine-local root paths. The existing repository corpus-manifest pattern is the implementation precedent for deterministic relative paths, byte lengths, raw-byte hashes, and self-attesting canonical JSON.

The existing `ProviderProvenance.source_sha256`, `TokenizerProvenance.vocabulary_sha256`, and `TokenizerProvenance.config_sha256` fields become the roots of their corresponding manifests. The model metadata contract also gains a required whole-model snapshot root (named `model_snapshot_sha256`) because tokenizer vocabulary/config roots do not attest the embedding weights. The ADR MUST NOT guess tokenizer filenames: a reviewed manifest for the pinned revision declares the exact files and assigns their roles.

Verification is local-only and occurs before provider import and before `StaticModel.from_pretrained`. Missing or changed evidence MUST fail closed; no verifier may fetch a repository, package, cache entry, or model file to complete a manifest.

### Required later evidence

Before matrix compilation or artifact acceptance, the implementation and gate MUST require:

- the exact provider distribution identity and installed version, a provider-source manifest, and an independently recomputed `source_sha256`;
- the pinned repository, immutable revision, MIT licence evidence, complete model-snapshot manifest, and independently recomputed `model_snapshot_sha256`;
- reviewed vocabulary/configuration role manifests from that same snapshot, with independently recomputed `vocabulary_sha256` and `config_sha256`;
- proof that every consumed model/tokenizer file belongs to the pinned snapshot and is covered by exactly one declared role;
- exact agreement between recomputed roots and `ModelMetadata`; any missing, additional, changed, linked, or unclassified consumed file fails closed;
- binding of all manifest roots into matrix/bundle identity and serialized-size accounting;
- preservation of the local-path, no-download, immutable-revision, MIT/Apache-only, 3 MB shipped-envelope, quantization, held-out-recall, and fail-closed gates from Update 6.

### Considered options

- **Keep caller-supplied hashes with no byte-set contract.** Rejected: the fields are syntactically valid but cannot independently prove the implementation or loaded artifact.
- **Name a presumed tokenizer file set in code.** Rejected: Model2Vec artifact layout is not evidence, and a guessed filename convention can attest the wrong bytes.
- **Use one tokenizer hash for the whole model.** Rejected: tokenizer identity does not cover embedding weights and cannot replace a whole-model snapshot root.
- **Define a versioned raw-byte manifest with reviewed role membership.** Chosen: it is deterministic, locally verifiable, fail-closed, and reuses the repository's established manifest pattern without shipping raw model bytes or vectors.

### Consequences

P02.S26 must be completed before P02.S06 and before any Rung-2 artifact can be accepted. The provider adapter, metadata schema, compiler, Python acceptance, and browser-visible provenance must be updated together after the manifest evidence is available. Until then, the existing source seams remain disabled/fail-closed and all Rung-2, runtime, and deployment acceptance rows remain open.

This amendment is architecture authority only. It authorizes the subsequent source implementation of the manifest contract, but not tests, builds, model downloads, matrix generation, Pagefind/runtime probes, generated-artifact release, live sweeps, reindexing, or deployment.

## Update 9 (2026-08-05): Diseño hits require validated individual locators

The deterministic casilla enrollment research and the one-time SOL-high architecture review settle the remaining ambiguity at the RAG-to-target boundary. This is a refinement of the existing fail-closed target contract, not a new search surface or a relaxation of registry authority.

### Decision

Registry-backed casillas remain exhaustively projected from the validated registry authority and resolve through their canonical `(modelo, casilla.id)` identity. A non-TOML Diseño hit may resolve to a `CASILLA` record only when the hit carries a validated individual locator that maps uniquely to one registry casilla for the applicable revision. A modelo-only path, missing locator, ambiguous locator, unreadable locator, or locator without registry parity MUST return `NO_TARGET_ENTITY`; it MUST NOT select a representative or first record.

Full Diseño coverage remains a separate, off-load-path, non-blocking contract. It is not required to establish deterministic registry enrollment or to close this consolidation.

### Consequences

The current fail-closed resolver behavior is intentional and remains the acceptance baseline. Future Diseño locator work is deferred until an official source locator/parser contract exists. That work, if authorized, must define revision-aware identity, provenance preservation, unique mapping, ambiguity rejection, and parity against the validated registry projection. No source-only heuristic may infer a casilla from a modelo-level Diseño hit.

This amendment does not authorize a fresh RAG sweep, reindexing, test run, build, generated artifact, runtime probe, model download, artifact release, or deployment.

## Update 10 (2026-08-05): Cross-runtime canonical JSON and nested self-attestation

P02.S25 exposes a cross-runtime integrity gap: Python currently hashes parsed JSON values with its own serializer while the browser validates the outer bundle shape and hash links without independently reproducing every nested digest. This amendment defines the one canonical byte contract required before nested self-attestation is implemented. It refines the accepted Rung-2 artifact boundary; it does not authorize artifact generation or release.

### Decision

Adopt `cadrumo-jcs-utf8-lf-v1`: RFC 8785 JSON Canonicalization Scheme semantics followed by exactly one LF byte. The contract is shared by Python build tooling and the browser validator; there is no second serializer or compatibility path.

### Admissible values

- Values are I-JSON values with unique object keys.
- Strings are valid Unicode without lone surrogates and are not normalized during serialization.
- Integers are restricted to the safe binary64 domain `[-9007199254740991, 9007199254740991]`.
- Non-integral numbers are finite IEEE-754 binary64 values. NaN, infinities, negative zero, unsafe integers, and values outside existing schema bounds are rejected.
- Matrix scales retain the stricter existing requirement of exact binary32 representability.

### Canonical bytes

- Object keys are recursively sorted by unsigned UTF-16 code units; array order is preserved.
- Numbers use JCS/ECMAScript shortest-round-trip spelling.
- Strings use JCS escaping: lowercase control escapes and escaped quote/backslash, with other valid Unicode emitted unescaped.
- No BOM or inter-token whitespace is emitted.
- Bytes are strict UTF-8 followed by exactly one terminal `0x0A`; no other trailing bytes are allowed.
- Every serialized-byte field counts the complete canonical representation, including that terminal LF.

### Hash scopes

- Matrix `artifact_sha256`: canonical matrix excluding its own `artifact_sha256` and `serialized_bytes`.
- Record manifest `records_sha256`: canonical ordered `records` array.
- Each bridge target list `targets_sha256`: canonical ordered `targets` array for that bridge entry.
- Bridge `artifact_sha256`: canonical bridge excluding its own hash and size fields.
- Bundle `artifact_sha256`: canonical bundle excluding its own hash and size fields, including all nested hashes and provenance.
- Browser configuration `bundle_sha256`: SHA-256 of the complete canonical bundle bytes, including the terminal LF.

### Golden vectors and independent verification

A language-neutral committed vector corpus MUST cover RFC 8785 numeric edges, safe-integer boundaries and rejection cases, control escaping, multilingual and non-BMP Unicode, composed/decomposed strings, lone-surrogate rejection, nested arrays/objects, terminal-LF bytes, and every hash scope above with expected bytes and digests. Python and JavaScript consumers MUST reproduce every vector independently without invoking one another. Any mismatch, unsupported value, invalid encoding, missing hash, stale size, or unknown version fails closed and leaves Pagefind authoritative.

### Versioning and migration

The matrix, record-manifest, bridge, bundle, and browser-config schema versions increment respectively from 3 to 4, 1 to 2, 1 to 2, 2 to 3, and v1 to v2. Old hashes are not translated or accepted; artifacts are regenerated under the new contract. No dual canonicalization path or compatibility reader is permitted.

### Consequences

P02.S25 remains open until this amendment is accepted, the canonicalizer and nested self-attestation are implemented, and independent Python/JavaScript verification is authorized and passes. The amendment does not authorize tests, builds, model downloads, matrix generation, live RAG sweeps, reindexing, generated artifacts, Pagefind/runtime probes, artifact release, or deployment.

## Update 11 (2026-08-06): independent Rung-2 query/alias authority and provenance

The Rung-2 input assembler currently treats the committed relevance sweep and the current Handbook enumeration as one effective query authority. P02.S32 needs a separately owned, reviewed source for additional admitted aliases. This amendment narrows that addition without changing the accepted matrix representation, normalization, bridge, ranking order, thresholds, held-out evaluation corpus, 3 MB envelope, or runtime-no-RAG boundary. The decision is grounded in `2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research` and the fresh vaultspec-rag architecture review.

### Decision

Add one committed build-time authority at `src/cadrumo/_data/terminology/rung2/query-alias-authority.json`.

The artifact MUST use the exact schema version `cadrumo.docs-search.rung2-query-aliases.v1`, a positive monotonically increasing `authority_version`, and a strict `entries` array. Each entry MUST contain:

- `concept_id`, identifying an approved Terminology Handbook concept;
- `language`, using the existing four-language contract;
- `query`, a bounded non-empty admitted alias;
- `canonical_query`, matching a current preferred, admitted, or hidden Handbook query for the same concept and language;
- `status`, exactly `ratified`;
- `review_reason`, explaining the independent RAG-grounded project-vocabulary review; and
- `reviewed_at`, the review date.

The authority is the owner only of independently ratified additional aliases. The Handbook remains the user-facing terminology and existing lexical-query authority. `synonym-candidates.json` remains a mining and review queue, not this authority. `relevance.json` remains the RAG-produced target mapping, not the owner of alias admission. The held-out corpus remains evaluation-only and MUST never supply authority entries.

RAG grounds candidate discovery and review at build preparation time. Each admitted alias is swept independently through vaultspec-rag and receives its own laundered mapping. The implementation MUST NOT copy a canonical query's targets, persist vectors, snippets, raw scores, or RAG output, or invoke RAG at runtime.

The deterministic sweep vocabulary is the union of the current Handbook query enumeration and the ratified authority entries. The assembler MUST require exact one-to-one parity between that combined query set and the committed relevance mappings, then derive the canonical combined vocabulary, query-token inventory, fingerprints, and sweep from that same set. `Rung2CompilationInputs` MUST carry the validated authority model rather than an untyped dictionary.

### Provenance contract

Extend the immutable `Rung2InputProvenance` with a required nested `query_alias_authority` identity containing:

- the repository-relative authority path;
- the exact authority schema version;
- the positive authority version; and
- the SHA-256 digest of the raw committed JSON bytes.

The existing relevance source identity and raw-byte digest remain separate. Vocabulary and query-token digests continue to cover the canonical combined sequence. The nested identity MUST be included in the hash-covered bundle provenance and in serialized-byte accounting. The applicable bundle/config schema versions MUST increment with the changed required provenance shape; old, missing, extra, or mismatched provenance MUST be rejected without a compatibility reader.

### Fail-closed boundary

Compilation or measurement MUST refuse when the authority is missing, malformed, wrong-versioned, unratified, path-invalid, tampered, duplicated, or non-canonical; when an entry names an unknown or non-approved concept; when its canonical query is not a current Handbook query for the same concept and language; when normalized aliases collide with one another or with existing Handbook queries; when an authority query equals a held-out evaluation query; when the combined relevance mappings are not an exact one-to-one match; or when the combined sweep, manifest targets, vocabulary, token inventory, fingerprints, or nested provenance disagree.

Remeasurement MUST retain the existing held-out query and digest. A changed evaluation corpus is a separately reviewed decision, not an input side effect of alias admission.

### Implementation and consequences

P02.S32 owns the strict loader/schema, deterministic ordering and anchoring checks, sweep union, combined-input parity, nested provenance binding, and the associated Python/browser contract tests. It does not change matrix rows, query-token pooling, semantic thresholds, D8 band-first lexical ordering, the legal/casilla record taxonomy, or the client runtime boundary. The browser remains lexical-authoritative and semantic-disabled until the existing Rung-2 acceptance gates pass.

This amendment adds one reviewable build-time data authority and its provenance identity. It does not authorize held-out leakage, a fresh artifact release, deployment, or runtime RAG.

## Update 12 (2026-08-11): Rung 2 is retired on measured evidence; documentation search stays lexical

The operator has ruled that the removal of the Rung-2 implementation at `a3376362ef` was intended. This amendment records that ruling, states the evidence it rests on, and supersedes the parts of R5 and R10 that assumed delivery. It is the ruling the companion plan's P02.S36 and P02.S37 rows were explicitly gated on.

### What the measurement showed

R5 chose O1 (deliver rung 2) and rejected O3 (decline it) on the ground that no new evidence contradicted the fired D3 gate. That evidence now exists, and it is the gate's own instrument rather than a judgement call. `2026-08-07-user-docs-search-consolidation-ranking-measurement-audit` (RANK-005), together with the P02.S04 and P02.S06 artifact reviews, measured the compiled tier end to end:

- held-out miss rate `0.3125`, against the ratified `0.10` line R10 makes a release precondition, and against the `0.1875` pre-rung-2 lexical baseline the tier was built to improve;
- query-token coverage `0.748`, below the `0.8` floor;
- 114 vocabulary rows against 8,507 injected records, so most queries never reach the matrix at all;
- the composed ladder scoring **worse** than the lexical baseline it was meant to supplement.

Rung 2 therefore fails its own ratified acceptance boundary in the direction that matters: enabling it would ship a recall regression. R10 already made that outcome fail-closed, so the tier was never eligible for release; this amendment stops carrying it as pending work.

RANK-005 also established why, and the diagnosis is not a code defect. Term labels across the 49 approved concepts stand at es 49, en 17, ca 3, hu 3 — exactly three concepts carry a term in all four languages. Where the vocabulary exists the mechanism works: for `casilla` and `prorrata-especial` all four languages return the same record set. The gap is authoring coverage, not model quality, ladder composition or normalization. Closing it is an authoring programme of several hundred terms across four languages, with Catalan and Hungarian starting from three each.

### D12 — Rung 2 is retired; the honest recall statement is lexical

Rung 2 is **retired**, not deferred-in-code. R5's ruling that "rung 2 proceeds" is superseded to this extent only: the bounded term-level semantic tier is not part of this deliverable. R8, R9 and R10 — the pinned model, encoding, bridge and acceptance boundary — are superseded in full; they governed an artifact that will not be produced. Updates 6, 7, 8, 10 and the Rung-2 half of Update 11 are historical: they refined a contract whose subject no longer exists.

The `0.1875` pre-rung-2 held-out miss rate stands as the project's standing, honest recall statement. No post-rung-2 baseline will be measured, because there is no post-rung-2 ladder.

Everything R2 places on the shipped side is unchanged and remains the deliverable: the Pagefind index, the four injected record kinds plus the legal kind delivered in P05, the declared aliases, the ratified synonym rings, per-language stemming, the structured modelo-plus-casilla exact route, and the display-class ladder.

### D13 — the retired surfaces are deleted, not preserved

Under `no-legacy-compatibility` the retirement is executed by deletion, with no bridge, alias or read-tolerance for the removed contract:

- The three orphaned build-time modules P02.S36 names — `dev/docs/terminology/_jcs.py`, `dev/docs/terminology/jcs_vectors/`, and `dev/docs/terminology/_content_manifest.py` — are deleted. The finding against them was unconditional: each redeclares a capability whose canonical home is in `core`, and the stricter-cross-runtime-bytes justification lost its subject when the browser validator was removed. The recovery branch that would have restored that consumer is now closed, so the remedy is unconditional too.
- The query/alias authority P02.S37 names is **not** deleted. Its finding — zero entries, zero consumers — is falsified at HEAD: it carries two independently ratified entries and is consumed by the live sweep. It was never a Rung-2 artifact in substance; it is the rung-1 alias authority, and rung 1 ships. What retirement requires of it is narrower: its `rung2` path segment and `rung2` schema token name a retired tier and are re-homed to names that state what the artifact is, atomically with its loader and tests.

### D14 — the licence exception stays open and unused

`shipped-search-licence-clean`, as amended by R5 and annotated by P01.S38, is **not** re-narrowed. P01.S38 already ruled that a permission which oscillates is worse than one documented as unused, and this amendment is precisely the branch that ruling anticipated. The bounded-embedding-matrix exception remains a deliberately unlocked, presently unused door with no consumer at HEAD; a future record wanting to use it makes a first use that needs its own ruling.

### Deferred carry-forward

The multilingual authoring programme RANK-005 identifies is recorded here as a formally deferred carry-forward, not as silently dropped scope. Reviving a semantic tier requires, in this order: the term coverage (several hundred terms across four languages, Catalan and Hungarian effectively from zero), then a fresh ADR re-deciding the model, encoding and acceptance boundary against the licence exception, then a re-measurement clearing the `0.10` line. Nothing in this amendment prejudices that record; it removes only the standing claim that the work is in flight.

The measured prose-recall gap RANK-003 and RANK-004 record is **not** carried forward to a semantic tier. RANK-004 established that the dominant cause is Pagefind term conjunction rather than semantics — dropping function words alone lifted `how do I file my quarterly VAT return` from 2 results to 36 and `what happens if I file late` from 2 to 41 — and that a corpus-frequency heuristic cannot separate the classes in this corpus. That is a lexical-tier fix under an explicit per-language function-word authority or progressive term relaxation, and it belongs to the lexical deliverable this record affirms.

### Consequences

- P02.S04 through P02.S07 are closed as retired: there is no matrix to compile, no client cosine tier to add, no matrix provenance for the licence gate to validate, and no post-rung-2 baseline to re-measure. The licence gate's existing oracle-output, NC/ND and heavy-index bars are untouched.
- P02.S36 executes unconditionally; P02.S37 executes as a re-homing rather than a removal.
- The campaign's completion criterion is not narrowed by this ruling. What the standing goal still asks for and this record excludes is open-vocabulary semantic recall for prose queries; what it delivers instead is the lexical ladder, the five record kinds, the exact structured route, and the recorded `0.1875` baseline. The gap is stated, not closed.
