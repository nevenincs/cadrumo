---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1a205932936f65e9ae086c961a56825b22d8df17fba2281a53e72149d5b01265'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# `mcp-call-latency` ledger

## Changes

- `S01` `T` `src/cadrumo/domain/calculations/registry/_validate_verdict.py`
- `S02` `T` `src/cadrumo/domain/calculations/registry/_authority.py`
- `S03` `T` `packaging/cadrumo_data_official/hatch_build.py`
- `S04` `T` `src/cadrumo/domain/calculations/registry/tests/test_validation_verdict_cache.py`
- `S05` `T` `dev/packaging/extract_manual_corpus_text.py`
- `S05` `T` `src/cadrumo/_data/manual_corpus_text/`
- `S05` `T` `.corpus_text.json`
- `S06` `T` `src/cadrumo/domain/calculations/registry/_validate_evidence.py`
- `S06` `T` `src/cadrumo/domain/calculations/registry/tests/test_registry_reviewability.py`
- `S07` `T` `src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py`
- `S08` `T` `src/cadrumo/domain/calculations/registry/_compiled_cache.py`
- `S09` `T` `src/cadrumo/domain/calculations/registry/_loader.py`
- `S10` `T` `src/cadrumo/domain/calculations/registry/tests/test_compiled_registry_cache.py`
- `S11` `T` `src/cadrumo/entrypoints/mcp/_inprocess.py`
- `S12` `T` `src/cadrumo/entrypoints/mcp/_server.py`
- `S13` `T` `src/cadrumo/entrypoints/mcp/_call_runtime.py`
- `S14` `T` `src/cadrumo/entrypoints/mcp/_server.py`
- `S15` `T` `packaging/mcpb/build.py`
- `S16` `T` `src/cadrumo/entrypoints/mcp/tests/test_inprocess_envelope_parity.py`
- `S17` `T` `src/cadrumo/entrypoints/mcp/tests/test_server_loop_responsiveness.py`
- `S18` `T` `dev/packaging/serving_path_benchmark.py`
- `S19` `T` `dev/packaging/installed_mcp_oracle.py`
- `S20` `T` `dev/packaging/release_cohort.py`
