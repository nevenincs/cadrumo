---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:9cdfda02f37c6ba40468ca7c87b5975ac7e3a8d2bf4a9fccf2fd49c299dda11b'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
---

# `user-docs-search-consolidation` audit: `Rung-2 alias-authority sweep plumbing review`

## Scope

Fresh vaultspec-rag-grounded review of the bounded alias-authority continuation: the optional authority input on `run_sweep`, the cadence CLI option, the recorded-service regression, and their fit with the accepted Rung-2 ADR and execution plan. The review was restricted to these scoped changes; concurrent worktree changes were not reviewed or modified.

## Findings

### sweep-plumbing | low | PASS — explicit authority remains an independent build-time input

The sweep accepts a validated `Rung2QueryAliasAuthority` and threads it through the existing Handbook enumeration, retrieval, resolution, wrangling, and laundering pipeline. Omitting the argument preserves the committed-authority default. No runtime RAG, raw vectors, raw scores, target copying, or browser configuration change was introduced.

### cli-validation | low | PASS — the cadence surface exposes the same validated boundary

The `--alias-authority` option loads the typed authority before passing it to the common sweep runner. The existing authority validation therefore remains the single admission boundary; the CLI does not invent or bypass alias rows.

### test-boundary | low | PASS — regression uses the existing captured-service replay boundary

The focused regression exercises enumeration, the common sweep path, and deterministic originating-concept seeding with an explicit authority. The existing recorded client replays captured live-service hits and does not mutate production code or replace the resolver with a mock.

### verification | low | PASS — scoped quality gates are clean

Ruff, the focused sweep test module, basedpyright, and the CLI help smoke check all passed. The explicit four-locale integration parity selector also returned 25 passed, covering English, Spanish, Catalan, and Hungarian local roots.

No critical or high findings were identified.

## Recommendations

Keep P02.S32 open until an independently RAG-grounded alias has an unambiguous mapping and an accepted Rung-2 remeasurement exists. The independently swept `pro-rata` candidate remains ambiguous and must not be promoted. Keep the temporary Rung-2 artifact diagnostic-only; do not enable the browser tier or deploy while the held-out miss-rate and coverage gates remain red.
