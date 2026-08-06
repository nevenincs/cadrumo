---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:674a8b664ba18c5aabc2190d09d5c4e6934d4bfec4129a27e625b893d6068971'
step_id: 'S07'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Re-scoped cutover (ADR Update 1): exclude the extracted sidecars from the dev index via .vaultragignore, retarget the terminology resolver path rules to source-file paths, correct the stale preprocess docstring to describe the sidecars' product-payload role, keep the hook-vs-sidecar parity gate as a permanent lock, and prove an equal-or-superset sweep target set - one explicit-path commit

## Scope

- `the sidecar tree stays (it is the wheel's corpus payload and the shipped search's index source)`
- `.vaultragignore`
- `dev/docs/terminology/_resolution.py`
- `dev/docs/preprocess/__init__.py`
- `dev/docs/preprocess/tests/test_hook.py`

## Description

- Rescind the sidecar deletion mid-execution (ADR Update 1): the sidecars are
  product data (shipped corpus-search index source, wheel corpus payload,
  manual-oracle evidence anchors); re-scope the cutover to the dev index only.
- Exclude `*.extracted.md` / `*.extracted.json` from the dev walker via
  `.vaultragignore` (the hook feeds the same text under source paths).
- Retarget the terminology resolver path rules to source paths (Diseños
  `.xlsx/.xls/.pdf`, normatives `.html`); drop the sidecar suffix strip in the
  legal reverse lookup; update the resolution tests and the recorded
  `sweep-regla-de-prorrata.json` fixture hit paths.
- Correct the stale `dev/docs/preprocess/__init__.py` docstring (dual role)
  and re-frame the hook-vs-sidecar parity gate as a permanent lock.
- Restart the resident service with `VAULTSPEC_RAG_PREPROCESS_ENABLED=1`
  (repairing the CPU-only torch wheel the tool upgrade left behind), reindex,
  and run the full 72-query sweep post-cutover.
- Absorb an in-scope pre-existing red: author the never-committed
  `corpus/normatives/ley-37-1992.json` manifest (BOE-A-1992-28740 permalink)
  the html-extractor attribution test depends on.

## Outcome

Equal-or-superset proof, adjudicated PASS: the post-cutover sweep resolves
247 targets vs the committed 173 (+79 gained, 0 failed queries). Five targets
lost, each individually justified: `page:how-to/justificante-receipts` and
`page:how-to/read-live-aeat-data` were dead links to pages the docs
restructure deleted (stale committed targets - losing them is a correction);
`filing receipt` now leads with `concept:justificante`, `borrador` with
`concept:borrador`, and `value-added tax` gained LIVA art. 1/9 in place of
the filing-forms orden - ranking shifts where every replacement target is
more relevant. Zero `.extracted.md` chunks remain in the index; corpus hits
arrive under source paths. Refreshed mapping, regenerated coverage report
(legal coverage 11 -> 68 of 555, casillas 13 -> 16, targets 173 -> 247), and
re-measured baseline (still 5/5 hits, 0.0 miss, rung-2 keep-deferred) all
land with this step. Gates: terminology + preprocess + rag-dev-only suites
green (150 tests).

## Notes

The sidecar-retirement rescission is the load-bearing lesson: the D6
"interim" quietly became the product's corpus payload (wheel ships extracted
text INSTEAD of source binaries), so the original D1 cutover would have
broken shipped search and evidence anchors. Codify candidate: verify what a
derived-data surface FEEDS before scheduling its retirement.
