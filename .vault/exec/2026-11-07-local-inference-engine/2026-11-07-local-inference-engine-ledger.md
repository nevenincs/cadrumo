---
tags:
  - '#exec'
  - '#local-inference-engine'
date: '2026-11-07'
modified: '2026-11-07'
body_schema: 'body-v2'
body_hash: 'sha256:de389b4c816d12fc1e18c29dffd500c73d7d1e20427825f4a01f9af0c1e1a08f'
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
