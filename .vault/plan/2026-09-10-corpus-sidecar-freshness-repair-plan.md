---
tags:
  - '#plan'
  - '#corpus-sidecar-freshness-repair'
date: '2026-09-10'
tier: L2
related:
  - '[[2026-07-13-docs-terminology-search-adr]]'
  - '[[2026-09-10-corpus-sidecar-freshness-repair-research]]'
modified: '2026-09-10'
body_schema: body-v2
body_hash: 'sha256:73e000dd1d44706b62abb7a515df1fa6cb18fed4f9066bb10be2bd902af5ebfe'
---

# `corpus-sidecar-freshness-repair` plan

## Description

Implement the accepted corpus-sidecar ownership contract: one deterministic generator/check for normative HTML and record-design workbook derivatives, while retaining the separate PDF corpus-text producer.

## Steps

### Phase `P01` - Establish the enrolled corpus-sidecar command

Deliver one deterministic normal/check command that owns normative HTML and record-design workbook sidecars.

- [x] `P01.S01` - Add the sorted enrolled-source generator and fail-closed --check boundary, delegating to the existing HTML and workbook extractors.; `dev/corpus/extract_corpus_sidecars.py`.
- [x] `P01.S02` - Prove clean generation and no-write detection of stale, missing, orphaned, and unexpected multipart sidecars on temporary corpus fixtures.; `dev/corpus/tests/test_extract_corpus_sidecars.py`.
- [x] `P01.S03` - Route corpus HTML and workbook completeness assertions through the owner check while retaining orthogonal temporal and PDF evidence checks.; `dev/corpus/tests/test_extraction_sidecar_freshness.py`.

### Phase `P02` - Refresh the committed production derivatives

Regenerate the stale normative HTML and missing record-design workbook pairs from their current authoritative source bytes.

- [x] `P02.S04` - Regenerate and commit every normative HTML sidecar through the new owner, including the eight currently stale sources.; `src/cadrumo/_data/corpus/normatives/html/`.
- [x] `P02.S05` - Generate and commit complete sidecar pairs for the seven currently unpaired modelo 308, 309, and 353 workbooks.; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/`.

### Phase `P03` - Expose and enforce the maintenance contract

Make regeneration discoverable and ensure focused developer gates exercise the same no-write product-data check.

- [x] `P03.S06` - Add fix-corpus-sidecars and check-corpus-sidecars recipes and invoke the no-write check from test-dev-tooling, retaining separate PDF corpus-text recipes.; `justfile`.
- [x] `P03.S07` - Add independent detector-teeth coverage that proves incomplete enrolled source coverage cannot pass as a fresh corpus.; `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py`.

## Parallelization

P01.S02 can proceed once P01.S01 exposes the check seam. P02 depends on P01. P03.S06 can proceed after the command spelling stabilizes; P03.S07 follows P01. Final verification is sequential after all phases.

## Verification

Run `uv run --no-sync python -m dev.corpus.extract_corpus_sidecars --check`, `just check-corpus-sidecars`, and `just check-corpus-text`. Run the focused corpus and preprocess suites, then `just test-dev-tooling` to prove CI enrolment. Validate this plan with `vaultspec-core vault plan check`.
