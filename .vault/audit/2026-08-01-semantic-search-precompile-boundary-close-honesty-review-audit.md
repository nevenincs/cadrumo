---
tags:
  - '#audit'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:0551a903adb2951ca310b72ed7fcb9c3d0109fc834e09899e0017962e21ffa65'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
  - "[[2026-07-31-semantic-search-precompile-boundary-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace semantic-search-precompile-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `semantic-search-precompile-boundary` audit: `campaign close honesty review`

## Scope

The mandated fresh-context honesty review closing the semantic-search-precompile-boundary campaign, run under the `aeat-campaign-close-honesty-review` discipline before the campaign may be declared structurally complete. The review was conducted adversarially: the reviewer treated the campaign as inherited and asked what is missing, vague, or assumed-but-unverified, rather than confirming the closure summary.

Audited: whether anything in the tree still imports or advertises a removed capability; whether the deleted modules left references in configuration, gate allowlists, type-check suppressions, dead-code whitelists, or the lockfile; whether the `snowballstemmer` promotion to core actually happened and the lexical index is genuinely one shape everywhere; whether any test passes only because it is deselected or held out of a parallel lane; whether any vault record still asserts a product-shipped semantic capability; and whether each of the plan's own Verification criteria is proven by the mechanism it names.

Every prior read-only inventory finding was RE-MEASURED at current HEAD rather than inherited, because those inventories predate several commits. Discovery was semantic-first per the mandatory-discovery directive, with keyword search used only to confirm exact sites.

## Findings

### stale-hybrid-claim-server | low | The server's command-index construction comment still called the index hybrid.

The P02 rewire narrowed the command-search index to per-column BM25 plus token overlap but did not touch the construction-site comment in `src/cadrumo/entrypoints/mcp/_server.py`, which still read "The hybrid command-search index backing the `search` meta-tool". This is a decision-trail claim a maintainer would read as current architecture. Notably, the earlier read-only inventory concluded the MCP surface was clean; that conclusion was correct for the four model-facing tool descriptions it checked but did not cover this comment. Re-measuring rather than trusting the inherited finding is what surfaced it. CLOSED by commit `b2c0f125b6`; the harness rule-surface drift gate stays green (6 passed).

### refoundation-plan-unannotated | medium | The parent plan advertised the retired runtime embedder as delivered, while its ADR and audit siblings were both annotated.

The campaign correctly annotated ruling R3 of the agent-harness-refoundation ADR (step P01.S02) and the corpus-search model-cache capability-gap audit carries an explicit OVERTAKEN annotation. The refoundation PLAN did not. Its Wave W06 phases still read as current architecture: "Add the runtime query embedder behind the capability-gated extra, brute-force numpy cosine plus RRF fusion", with every Step row checked, including pinning model2vec and numpy in the search extra. A semantic vault search for "product ships hybrid semantic retrieval" returns that plan among the top results, so a reader can reach it without ever reaching R3's amendment. This is the decision-trail inconsistency the campaign's own P01 phase existed to prevent, applied to two of the three sibling documents but not the third. CLOSED: a dated annotation was added to the Wave W06 prose stating that the semantic half is retired, naming what survives, and explicitly preserving the Step rows as a true record of what was built rather than a description of current architecture. No Step row or identifier was altered.

### verification-criterion-names-a-nonexistent-mechanism | medium | The plan claimed a socket-blocking proof that was never built.

The plan's Verification section claimed `search_corpus` and the command-search index were proven to work without network access "by the rewritten shippability and ranking-golden tests running with sockets unavailable". No socket-blocking mechanism exists in those tests, and grep for socket, offline, and no-network across the shippability gate returns nothing. This is the assumed-but-unverified class this review exists to catch: a criterion whose stated evidence does not exist would have read to any later auditor as a discharged proof.

The criterion itself is nonetheless SATISFIED, by a stronger mechanism than the one claimed. `test_shipped_search_surface_imports_no_embedding_runtime` walks every shipped module of both search packages by AST and refuses any import of model2vec, huggingface_hub, numpy, onnxruntime, or torch, catching function-local and TYPE_CHECKING imports that a runtime socket blocker would miss, and carries an anti-vacuity floor asserting at least eight modules were walked so a collapsed walk cannot pass silently. Because no production search module imports a network client at all, the no-network property is compile-visible rather than per-test. CLOSED by correcting the plan's Verification bullet in place with a dated note recording both the wrong mechanism and the real one, following the precedent ADR Update 1 set for the lockfile criterion.

### ranking-gate-invisible-to-the-default-lane | medium | The ranking-golden gate is deselected by the default marker, so a green unit lane does not prove the ranking criterion.

The four tests in `test_command_ranking_golden.py` are `integration`-marked, and the project's default `addopts` selects `-m 'unit and not external_tool and not os_keychain'`. Measured directly: the default marker collects 45 of 49 tests in the two search trees, deselecting exactly the four ranking-golden tests; the override collects all 49. A maintainer running the default unit lane and seeing green has NOT exercised the gate that proves lexical-only ranking still surfaces the right commands, even though the plan's Verification cites those tests as the proof. CLOSED as verified, not as a defect: the `test-integration` recipe runs `-m "integration and not serial and not os_keychain"`, which selects them, so CI does cover the gate. Recorded here so no future reader mistakes a green default lane for discharge of this criterion.

### retrieval-mode-member-name-residue | low | LEXICAL_ONLY retains a suffix that referred to the now-deleted hybrid alternative.

`RetrievalMode` is correctly narrowed to exactly two members, CITATION and LEXICAL_ONLY, and its docstring states plainly that these are the only two shapes the product ships. The ONLY suffix originally contrasted with the deleted HYBRID member. NO ACTION, recorded deliberately to forestall churn: the name still reads correctly as the ranked lexical path as distinct from the citation short-circuit, and renaming a persisted enum member value for cosmetics would be unjustified churn against `no-legacy-compatibility` reasoning. A future reader who spots the residue should read this entry rather than open a rename.

### adr-update-1-claims-independently-confirmed | low | Both corrections the ADR recorded were verified rather than trusted.

ADR Update 1 asserted two things this review re-derived from scratch. First, that the extras-reporting instruction had no subject: confirmed, a search for a search extra in the config-check CLI and payload modules returns nothing, and no `cadrumo[search]` install hint survives anywhere under `src/cadrumo/`. Second, that only model2vec leaves the lock while huggingface-hub and numpy legitimately remain as dev-group transitives: confirmed, `uv tree --no-dev` carries none of the three, while huggingface-hub and numpy remain present in the full lock as expected. Recorded because an inherited correction is exactly the kind of claim that decays into an unexamined premise.

### deletion-collateral-verified-clean | low | No dangling reference to any deleted module survives outside the vault.

Swept and clean: no reference anywhere outside `.vault/` to `_model_loader`, `_query_embed`, `_embed_build`, `_ranking`, `QueryEmbedder`, or `CorpusSearchDependencyError`, and no surviving HYBRID or SEMANTIC retrieval-mode member. The dead-code and type-check surface is clean and honestly documented: the irreducible-external-gaps set in the quality tooling is EMPTY, with a dated comment recording that its single entry suppressed the model2vec unresolved-import in the deleted loader. Generated API stubs are conformant at 1246 source modules to 1246 stubs with zero missing, orphan, or stale. The locale catalogues pass scaffold check across all four languages. The third-party notices carry no model2vec, huggingface, potion, or numpy attribution. The operator harness tree returns zero hits for the entire stale-claim vocabulary.

The `snowballstemmer` promotion is real: it is declared in the core dependency list with a comment stating the rationale, both search packages import it unconditionally, and the corpus lexical index carries no unstemmed degraded branch. The command-search token-overlap fallback that remains is the one ruling R1 explicitly retains, not residue.

### dev-side-semantic-prose-is-correct-not-stale | low | The dev docs pipeline legitimately describes embedding and hybrid retrieval and must not be swept.

The dev-side terminology tooling describes embedding and hybrid retrieval in its own prose. This is NOT stale product messaging: that pipeline IS the build-time compilation oracle ruling R2 depends on, and its statements about itself are true. A future sweep agent matching on the stale-claim vocabulary will hit these files and must leave them alone. This tree was additionally out of bounds for this reviewer because a peer agent held uncommitted work there.

## Recommendations

- No follow-on ADR is required. Every item above is closed with verification; none reopens a decision, and the boundary ruling stands as accepted.
- Treat the ranking-golden deselection as a standing caveat when reading a green default lane, not as work: the integration lane covers it. Should the ranking criterion ever need to gate a routine run, the decision to re-mark those tests belongs to whoever owns the marker taxonomy, not to this campaign.
- Preserve the Wave W06 annotation on the refoundation plan. It is the only signal on that document that its runtime-embedder Steps describe history rather than architecture.
- When a later campaign writes a Verification criterion, name the mechanism that exists. Two of the four medium findings here were criteria whose stated evidence was wrong or invisible while the underlying property held; both would have read as discharged proofs to a later auditor.
