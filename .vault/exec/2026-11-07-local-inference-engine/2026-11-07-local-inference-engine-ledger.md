---
tags:
  - '#exec'
  - '#local-inference-engine'
date: '2026-11-07'
modified: '2026-11-07'
body_schema: 'body-v2'
body_hash: 'sha256:7d4cdbda87201a9e118289722864913f832b42add4bb94170376438b70a07b90'
body_hash: 'sha256:999ab90d2b6afa03331c80d87930a90a6fbb46807ece09f9e19448a1e1de3238'
related:
  - "[[2026-11-07-local-inference-engine-plan]]"
---

# `local-inference-engine` ledger

## Changes

- `S01` `M` `.vault/adr/2026-10-18-dependency-provisioning-unified-setup-adr.md`
- `S01` `M` `.vault/adr/2026-10-24-rust-component-provisioning-adr.md`
- `S01` `M` `.vault/adr/2026-10-25-agent-owned-models-adr.md`
- `S01` `M` `.vault/adr/2026-06-13-llm-evidence-classification-adr.md`
- `S01` `verify:` `vaultspec-core vault check all` -> `pass`
- `S01` `by:` `vaultspec-high-executor`
- `S25` `M` `.vault/research/2026-11-07-local-inference-engine-research.md`
- `S25` `M` `.vault/adr/2026-11-07-local-inference-engine-adr.md`
- `S25` `verify:` `gpu_pass.py --go --cleanup` -> `pass`
- `S10` `A` `dev/env/llamacpp_pins.py`
- `S10` `A` `dev/env/tests/test_llamacpp_pins.py`
- `S10` `A` `native/llamacpp-pins.json`
- `S10` `M` `justfile`
- `S10` `M` `dev/quality/metadata/import_load_targets.json`
- `S10` `M` `dev/quality/metadata/import_load_targets.dev.json`
- `S10` `verify:` `pytest dev/env/tests/test_llamacpp_pins.py dev/env/tests/test_local_ai_pins.py dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S10` `verify:` `ruff check and format --check` -> `pass`
- `S10` `verify:` `ty check` -> `pass`
- `S10` `verify:` `dev.quality.import_gate` -> `pass`
- `S10` `by:` `vaultspec-standard-executor`
- `S12` `M` `native/application/src/provisioning/pins.rs`
- `S12` `M` `native/application/src/provisioning/engine.rs`
- `S12` `M` `native/application/src/provisioning/engine/tests.rs`
- `S12` `M` `native/application/src/provisioning/network.rs`
- `S12` `M` `native/application/src/provisioning/local_ai/program/tests.rs`
- `S12` `M` `native/manager/src/supervision/local_ai.rs`
- `S12` `verify:` `rustfmt --edition 2024 --emit stdout (six files)` -> `pass`
- `S12` `verify:` `pytest dev/quality/tests/test_no_model_definitions.py` -> `pass`
- `S12` `by:` `vaultspec-standard-executor`

## Notes

- `S12` Rust not compiled in this worktree; cargo test and clippy for cadrumo-application and the manager are owed in a root build slot
- `S14` `A` `native/application/src/provisioning/local_ai/registry.rs`
- `S14` `A` `native/application/src/provisioning/local_ai/registry/tests.rs`
- `S14` `M` `native/application/src/provisioning/local_ai/mod.rs`
- `S14` `M` `native/application/src/provisioning/local_ai/models.rs`
- `S14` `M` `native/application/src/provisioning/http.rs`
- `S14` `M` `native/application/src/provisioning/transfer.rs`
- `S14` `verify:` `rustfmt --edition 2024 --check` -> `pass`
- `S14` `by:` `vaultspec-high-executor`

## Notes

- `S14` cargo clippy and the registry tests are pending the root build slot; no cargo ran in the worktree
