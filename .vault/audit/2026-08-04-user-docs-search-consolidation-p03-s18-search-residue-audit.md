---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:227f5f7ee5f8eb9ca2f7d240538929edb6aec8d3b3202bb7fefda938c4545bac'
related: []
---

# `user-docs-search-consolidation` audit: `P03.S18 search residue and incomplete landing sweep`

## Scope

Sweep the current worktree, Git history, and vaultspec-rag grounding for
surviving artefacts of the overtaken semantic-runtime/search campaigns and for
incomplete search-page landing residue. The sweep covers the two named
historical commits plus later history, production source, the shared search
page/controller, and the typed legal record boundary. It is source-only: no
test, build, browser, live-root, sweep, or deployment action is in scope.

## Findings

### runtime-stack-absence | low | Overtaken model runtime is absent at HEAD

Git history confirms the two named campaign commits changed the model loader,
embedding build, and centralized ranking paths. Those paths are absent at the
current HEAD. The current on-host corpus search is explicitly lexical and
exact-citation based, with no model, vectors, or network dependency. RAG
grounding surfaced the accepted precompile-boundary ADR, its close-honesty
review, and the adjudicated capability-gap audit; the current source agrees
with that ruling. No remediation is required.

### pagefind-ui-residue | low | Historical UI wording and vendor output are inactive

The search template and a Pagefind-index gate still mention the retired
PagefindUI bundle in explanatory prose, and Pagefind still emits its UI bundle
alongside the raw index. Direct source inspection shows the template contains
no script or link for that bundle; the shared controller imports the raw
Pagefind module and owns both the palette and inline search page. This is
historical/vendor residue, not an incomplete landing surface or active second
implementation. No new remediation step is opened; any prose cleanup is
deferred to the documentation workflow.

### page-kind-boundary | low | PAGE remains only the full-text fallback kind

The remaining PAGE projections are the intentional rendered-page/full-text
fallback path. The legal projection and unified-record funnel resolve legal
provisions as the dedicated LEGAL kind with typed BOE provenance and generated
page/anchor targets. The sweep found no surviving legal-to-PAGE production
projection. No remediation is required.

### p02-source-only-boundary | low | Rung-2 source seam has no shipped artefact

The newly committed P02.S04 query-token contract is source-only and does not
introduce a browser reader, model provider, or generated matrix. P02.S04
through P02.S07 remain open, as do the runtime/build acceptance rows; this is
an explicit open boundary, not residue to close opportunistically.

## Recommendations

- Close this static residue sweep with no source remediation. Preserve the
  existing P02/P04/P05/P06 open plan rows until their named runtime or model
  gates are authorized and evidenced.

## Evidence boundary

- vaultspec-rag semantic searches covered P03.S18, the accepted consolidation
  ADR, the precompile-boundary ADR/plan, the close-honesty audit, the legal
  P05 records, and the Rung-2 research.
- The CLI RAG code route was used for the current search controller, Pagefind
  build/injection, legal projection, and product corpus-search boundary; the
  rejected MCP codebase alias was not bypassed.
- Git history was inspected for the two named commits and later search/legal
  changes. Static `rg`, file existence, and source reads found no active
  overtaken semantic runtime path.
- No tests, builds, model downloads, matrix generation, Pagefind compilation,
  browser probes, live sweeps, runtime gates, or deployment were run.
