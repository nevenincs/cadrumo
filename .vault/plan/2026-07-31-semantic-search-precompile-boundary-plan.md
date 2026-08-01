---
tags:
  - '#plan'
  - '#semantic-search-precompile-boundary'
date: '2026-07-31'
modified: '2026-08-01'
body_hash: 'sha256:71b1cf0d11fadcac074b0a805080fe416301775e7a85fce75725af2db4386831'
tier: L2
related:
  - '[[2026-07-31-semantic-search-precompile-boundary-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace semantic-search-precompile-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `semantic-search-precompile-boundary` plan

<!-- One-line headline summary plan. -->

## Description

Executes the semantic-search-precompile-boundary ADR: retire the runtime embedding stack from the shipped product so the only semantic-search artefact the project depends on remains the dev-side precompiled, laundered docs-search data. The shipped retrieval surface narrows to the FTS5 lexical index with the Spanish stemmed column, the exact citation lookup, the terminology lookup, and the command-search BM25 ranker. The `cadrumo[search]` extra, the model2vec loader, the query embedder, the corpus-vector build, and every semantic fusion path are deleted outright, with no shim, per the pre-release no-legacy discipline. The plan is deletion-heavy and crosses gated collateral surfaces (apidocs stubs, error registry, locales, harness drift gate), each retired through its owning CLI. Phase P01 is a hard precondition: uncommitted peer work is in flight on the deletion targets and must be handed off first.

## Steps

### Phase `P01` - Coordination and decision-trail truth

Hand off the in-flight loader-hardening WIP and stamp the R3 amendment so no agent hardens a surface scheduled for deletion and no reader takes the refoundation ADR's semantic half as still in force.

- [x] `P01.S01` - Report the collision between this ruling and the in-flight loader-hardening WIP to the coordinator and obtain an explicit handoff of the uncommitted changes before any deletion touches those files; `src/cadrumo/application/corpus_search/_model_loader.py`.
- [x] `P01.S02` - Annotate ruling R3 of the agent-harness-refoundation ADR as amended by the semantic-search-precompile-boundary ADR, following the existing R2 and R8 amendment-note pattern; `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md`.

### Phase `P02` - Atomic rewire and deletion

One atomic explicit-pathspec commit rewires every consumer to lexical plus citation retrieval and deletes the semantic modules with their tests and apidocs stubs, so no intermediate tree state has a shipped surface importing a removed capability.

- [x] `P02.S03` - Rewire search_corpus and hybrid retrieval to lexical plus citation only, deleting the embedder wiring, vector loading, and semantic fusion, and reconcile every RetrievalMode consumer to the narrowed member set; `src/cadrumo/application/corpus_search/_runtime.py`.
- [x] `P02.S04` - Delete _model_loader.py, _query_embed.py, and _embed_build.py together with their facade exports and error-surface references; `src/cadrumo/application/corpus_search/`.
- [x] `P02.S05` - Rewire the command-search index to per-column BM25 plus token-overlap only, deleting the model2vec semantic side, the RRF fusion, and the query_embedder parameter on the meta-tools builder; `src/cadrumo/application/command_search/_index.py`.
- [x] `P02.S06` - Delete test_embed_build.py, test_query_embed.py, test_hybrid_real_model_recall.py, and test_hybrid_real_model_recall_live.py, and rewrite the semantic branches of the surviving corpus-search and command-search tests against the lexical-only shape; `src/cadrumo/application/corpus_search/tests/`.
- [x] `P02.S07` - Regenerate the apidocs stubs for the deleted modules, verify clean collect-only, and land the whole phase as one atomic explicit-pathspec commit; `docs/api/`.

### Phase `P03` - Packaging and diagnostics retirement

Remove the search extra and its dependency pins, promote the stemmer to core, and retire the dead dependency error with its registry row and locale keys through the owning CLIs.

- [x] `P03.S08` - Delete the search optional extra with its model2vec, huggingface-hub, and numpy pins, prune the all aggregate, promote snowballstemmer into the core dependency set, and refresh the lockfile; `pyproject.toml`.
- [x] `P03.S09` - Retire CorpusSearchDependencyError together with its error-registry row, and remove its locale keys through the locales CLI leaving scaffold check clean; `src/cadrumo/core/errors/registry/_application_part1.py`.
- [x] `P03.S10` - Sweep every remaining install hint naming the retired extra from production strings, the extras-reporting half of this step being vacated by ADR Update 1 because config check never named a search extra; `src/cadrumo/`.

### Phase `P04` - Surface truth sweep and verification

Make every operator-facing surface stop claiming semantic retrieval, rebuild the shippability and ranking gates around the single lexical shape, and close with the mandated fresh-context honesty review.

- [ ] `P04.S11` - Sweep the MCP corpus and meta tool descriptions and docstrings to describe lexical plus citation retrieval, keeping the harness rule-surface drift gate green; `src/cadrumo/entrypoints/mcp/`.
- [ ] `P04.S12` - Sweep the operator harness documents and user documentation for hybrid or semantic retrieval claims and verify the docs build gates; `docs/`.
- [ ] `P04.S13` - Run the corpus-search and command-search suites sequentially plus full collect-only, and record the gate outputs in the exec records; `src/cadrumo/application/corpus_search/tests/`.
- [ ] `P04.S14` - Run the fresh-context honesty review against the closure summary and persist it as a vault audit before declaring the campaign structurally complete; `.vault/audit/`.

## Parallelization

Phases are sequential: P01 gates everything (live peer WIP sits on the P02 deletion targets), P02 must land as one atomic commit before P03 removes the packaging metadata the P02 tree no longer references, and P04 sweeps surfaces whose truth depends on P02 and P03 having landed. Within P02 the steps are one work unit landing in a single explicit-pathspec commit and must not be dispatched to parallel agents. P03 steps S08 to S10 may run in parallel after P02. P04 steps S11 and S12 may run in parallel, S13 and S14 close sequentially.

## Verification

- No module under `src/cadrumo/` imports model2vec, huggingface-hub, or numpy, verified by grep over the production tree.
- `pyproject.toml` declares no `search` extra, the `all` aggregate omits it, and the PRODUCT closure (`uv tree --no-dev`) resolves without the three retired packages. Corrected 2026-08-01 per ADR Update 1: `huggingface-hub` and `numpy` legitimately remain in the lock as dev-group transitives of the vaultspec-rag oracle, so their absence from the lockfile is NOT a criterion and must not be "fixed" by removing the dev oracle.
- `search_corpus` and the command-search index return ranked results on a bare-core install with no network access, proven by the rewritten shippability and ranking-golden tests running with sockets unavailable.
- The full suite collects cleanly and the corpus-search, command-search, and MCP test trees pass sequentially.
- `python -m dev.docs.apidocs scaffold --check` exits clean, the docs build gates pass, and the harness rule-surface drift gate passes.
- No production string, tool description, harness document, or user doc references the retired extra or claims semantic or hybrid retrieval.
- The fresh-context honesty review audit exists in the vault and its surfaced items are closed or formally deferred before the campaign is declared complete.
