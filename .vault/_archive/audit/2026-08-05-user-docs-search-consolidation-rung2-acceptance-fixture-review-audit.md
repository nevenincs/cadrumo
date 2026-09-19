---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d8a7bca4f6d9a36974b1c3bf3211f24df0c79506eb2c8e95e079cc1022d66c23'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
---
# `user-docs-search-consolidation` audit: `Audit the Rung-2 acceptance fixture contract correction`

## Scope

LUNA EXTRA HIGH formal review of exactly the two-line working-tree diff in `dev/docs/terminology/tests/test_rung2_acceptance.py`: the added `RUNG2_CONFIG_SCHEMA_VERSION` import and the replacement of the fixture's stale `cadrumo.docs-search.rung2-config.v1` value. The review was grounded by fresh intent searches with `vaultspec-rag`, then exact source confirmation against `dev/docs/terminology/_rung2_acceptance.py`, the accepted consolidation ADR, the Rung-2 static-embedding boundary research, the active consolidation plan, and the P02.S04/P02.S26 execution records. No source files were modified; peer worktree WIP was preserved. No tests, builds, runtime probes, artifact generation, downloads, or deployment were run.

## Findings

### Audit the Rung-2 acceptance fixture contract correction | low | Schema-negative coverage remains implicit

The correction properly centralizes the fixture on the exported production marker, but this test module has no dedicated assertion that the retired `cadrumo.docs-search.rung2-config.v1` value is rejected. A coordinated future change to the exported marker and the model literal could therefore avoid detection by this fixture's positive setup. This is a pre-existing test-coverage limitation, not a weakening of runtime acceptance: the production model still requires the v2 literal and the browser has an independent v2 check. It is non-blocking follow-up only; the bounded diff itself passes.

### Audit the Rung-2 acceptance fixture contract correction | pass | No safety or acceptance-contract defect in the bounded diff

The added import resolves to a symbol listed in the production module's `__all__`, and the fixture now supplies the exact v2 value required by `Rung2BrowserConfig`. The change restores valid config construction for the targeted negative tests, so those tests exercise disabled-config, normalization, extra-field, and non-bundle guards rather than failing or passing on a stale schema mismatch. The patch adds no fallback, compatibility reader, artifact access, model selection, URL derivation, or acceptance bypass. It preserves the pre-artifact, source-only boundary and all fail-closed evidence requirements.

The accepted ADR's Update 10 explicitly advances the browser-config schema from v1 to v2 and rejects old versions without a compatibility path. The active plan keeps the Rung-2 implementation and acceptance rows open pending provider, artifact, licence, quantization, held-out, and runtime evidence; this fixture correction does not claim or manufacture any of that evidence. The current execution records likewise retain the source-only/no-verification boundary.

Review outcome: PASS, with one LOW non-blocking coverage follow-up recorded above.

## Recommendations

No action is required for this bounded correction. If schema-oracle coverage is expanded later, add a dedicated real-behaviour assertion for rejection of the retired v1 marker; that follow-up is outside this exact diff and does not block this PASS.
