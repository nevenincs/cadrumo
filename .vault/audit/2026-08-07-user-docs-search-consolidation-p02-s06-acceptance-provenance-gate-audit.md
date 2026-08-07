---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f948e98eea0686b1a61934a3b087bd42cd153fca5b744f8a1feaac150d79e58c'
related:
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-P02-S06]]"
---
# `user-docs-search-consolidation` audit: `P02.S06 acceptance provenance gate review`

## Scope

Fresh `vaultspec-rag` grounding identified the accepted consolidation ADR, the P02.S06 plan row and execution record, the Rung-2 provider/tokenizer manifest contract, the current acceptance module, and the shared browser fail-closed reader. The review covered the bounded LUNA EXTRA HIGH changes in `dev/docs/terminology/_rung2_acceptance.py` and `dev/docs/terminology/tests/test_rung2_acceptance.py`. It also verified the corrected constants against the current locally validated diagnostic bundle. No artifact was promoted, no browser configuration was enabled, no deployment was attempted, and unrelated shared-worktree WIP was not changed.

## Findings

### provenance-identity | low | PASS after correction: the gate binds the current pinned provider and tokenizer evidence

The acceptance boundary now requires the ratified Potion repository, immutable revision, MIT licence, dimension, model-snapshot digest, Model2Vec package/version/source digest, and tokenizer package/version/repository/revision/vocabulary/config digests. The values match the current validated diagnostic bundle: model2vec 0.8.2, tokenizers 0.23.1, Potion revision `e7421cd79c75fc506b88bb75723ae0a234994720`, model snapshot `869266e7140deabcaa3e5e0e69c7e017af5507d07006114690bb05d3ab06c9d6`, provider source `929a7ee94295436f3befb3f0836cf45c587fd91f34fe3f3f8f4039a5e126c4d7`, tokenizer vocabulary `16d9434a6dba49dffd2a831ceb73bcbab2662b32d7bd3d0c4a2544e3b4c22d3b`, and tokenizer configuration `83ae8f6fbf3124bd6d7e8d7c62677067f5cdd3885f377a7a787e8daa4f353299`. An initial worker hunk carried stale provider/config values; review caught and corrected them before the recorded proof.

### canonical-attestation | low | PASS: acceptance remains tied to exact bundle bytes and shared limits

The validator requires an already validated `Rung2SearchBundle`, recomputes canonical bundle bytes and SHA-256, checks the measured payload size against both the bundle and the 3,000,000-byte envelope, validates input fingerprints and bridge linkage, and retains the existing normalization and browser-approval flags. The test additions exercise stale hashes, stale sizes, matrix self-attestation tampering, licence/provenance mismatches, and acceptance success through the production bridge models.

### fail-closed-boundary | low | PASS: the patch does not enable an unaccepted semantic tier

The browser remains disabled unless an explicit configuration carries approved measurements, exact payload identity, quantization acceptance, no top-five loss, locale/kind parity, and a miss rate within the ratified threshold. The acceptance patch adds no default URL, threshold relaxation, generated artifact, raw vector output, or deployment behavior.

### runtime-acceptance | high | P02.S06 remains open as a plan row

The source and test boundary are proven, but the current diagnostic replay remains below the ratified gate at 22/32 semantic hits, 10 misses, 93/123 covered query tokens, and aggregate coverage 0.7560975609756098; the standing composed-ladder and all-locale acceptance evidence is not accepted. The temporary bundle is not a committed release artifact, so this review does not close P02.S04 through P02.S07 or enable Rung-2.

### verification | low | PASS: bounded quality gates are green

The post-correction bounded suite returned 98 passed. Ruff passed, basedpyright returned 0 errors, 0 warnings, and 0 notes, `node --check docs/_static/cadrumo-docs.js` passed, and the scoped diff check passed. The refreshed vaultspec-rag code index is consistent at 79,336 chunks with matching claimed and live counts.

## Recommendations

- Keep P02.S06 open until one committed bundle, accepted held-out/composed-ladder evidence, quantization proof, and locale/kind parity evidence satisfy the ADR gates.
- Keep the semantic browser configuration fail-closed and do not promote the temporary diagnostic bundle.
- Re-run the acceptance and locale/deployment gates after the shared worktree settles; preserve the current 404 live-root evidence for `es`, `ca`, and `hu`.
