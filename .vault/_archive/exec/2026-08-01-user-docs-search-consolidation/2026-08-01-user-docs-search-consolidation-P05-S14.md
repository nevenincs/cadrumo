---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:e5e60267d8ef59714afc360fa271fc772e6daa3b472af32a7a9c8630457405a7'
step_id: 'S14'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Build the generated legal reference surface rendering per-law pages with per-provision anchors from one shared slug authority, each entry carrying its BOE permalink and catalogue metadata

## Scope

- `dev/docs/`

## Description

- Add a registry-backed legal reference generator with one page per legal
  document, provision anchors, site-relative HTML targets, and BOE grounding.
- Hook legal-reference generation into the documentation builder and register
  the generated legal index in the root reference toctree.
- Fail closed on schema drift, unsafe authored text or links, reserved slugs,
  output collisions, and stale generated pages; accept omitted optional fields
  without inventing metadata.
- Re-review the final source against the accepted ADR and P05 plan.

## Outcome

The source implementation was delivered through commits
`289a3e1020e4d349a96d872f70ea7ae018c88006`,
`a71beada259b251af41cd3bdc2c59f3376bf2412`, and
`46d1a42d7d85a9f0cb32e809b57baefa6b483307`. The final formal review returned
PASS with no blocking source findings. `vaultspec-rag` semantic searches
grounded the accepted ADR, the active P05 plan, and the P05.S14 audit; exact
current source was then retrieved with `get_code_file`.

## Notes

The code-search MCP alias remains unavailable because the `codebase` source
alias is rejected; this is tracked in vaultspec-rag issue #350. No reindex or
bypass was attempted. No tests, builds, Pagefind runs, live probes, deployment,
or other runtime gates were run. S14 remains open for the authorized runtime
and documentation-build acceptance; P05.S15-S17 remain outstanding.

### 2026-08-06 source audit: legal catalogue decode failure boundary

Fresh vaultspec-rag grounding and exact retrieval of `dev/docs/legal_reference.py` found that `load_legal_provisions()` catches `OSError` and `tomllib.TOMLDecodeError` around `read_text(encoding="utf-8")`, but not `UnicodeError`. A malformed catalogue fragment can therefore escape as a raw `UnicodeDecodeError` instead of the module's `LegalReferenceError` fail-closed boundary. The file is peer-modified with an unrelated strict-typing diff, so it was not edited in this tranche; the owner should extend that narrow exception tuple and then re-run the scoped static/behavioral evidence. No tests, builds, generated pages, runtime probes, or deployment were run.

### 2026-08-05 source continuation: legal-reference typing boundary

Fresh `vaultspec-rag` grounding over the P05 legal plan/ADR, legal projection, generated legal-reference authority, and current source audits identified a strict-typing gap at the untyped `tomllib` boundary: the legal surface behavior was already fail-closed, but direct strict analysis could not prove the table shapes or the shared catalogue-path authority. The source correction makes the shared catalogue path public, narrows TOML tables with explicit runtime-preserving casts after existing checks, and retains all existing field, permalink, duplicate-id, slug, anchor, and output-boundary validation. No legal id, generated target, BOE provenance rule, or search-record behavior changed.

Scoped Ruff and basedpyright pass with 0 errors, 0 warnings, and 0 notes for the legal-reference/glossary modules; AST parsing and focused diff checks pass. A broader Rung-2 static scope also passes Ruff, basedpyright, AST, Node syntax, and diff checks. No tests, builds, generated legal pages, Pagefind/runtime probes, live sweeps, reindexing, model downloads, deployment, or artifact release were run. P05.S14 remains open for its authorized build and runtime evidence.

### 2026-08-06 authorized execution

The registry-backed legal reference generator produced 140 generated legal pages, 594 provisions, and 594 grounded BOE permalinks. The legal anchor/parity path is included in the marker-aware source gate, which returned `63 passed in 180.00s (0:03:00)`. Strict full-site builds still stop earlier at the known sequence/product divergences, so this proves the generated legal surface and parity source path, not a deployed locale artifact.

## 2026-08-05 source continuation: legal-reference typing boundary

Fresh `vaultspec-rag` grounding over the P05 legal plan/ADR, legal projection, generated legal-reference authority, and current source audits identified a strict-typing gap at the untyped `tomllib` boundary: the legal surface behavior was already fail-closed, but direct strict analysis could not prove the table shapes or the shared catalogue-path authority. The source correction makes the shared catalogue path public, narrows TOML tables with explicit runtime-preserving casts after existing checks, and retains all existing field, permalink, duplicate-id, slug, anchor, and output-boundary validation. No legal id, generated target, BOE provenance rule, or search-record behavior changed.

Scoped Ruff and basedpyright pass with 0 errors, 0 warnings, and 0 notes for the legal-reference/glossary modules; AST parsing and focused diff checks pass. A broader Rung-2 static scope also passes Ruff, basedpyright, AST, Node syntax, and diff checks. No tests, builds, generated legal pages, Pagefind/runtime probes, live sweeps, reindexing, model downloads, deployment, or artifact release were run. P05.S14 remains open for its authorized build and runtime evidence.
