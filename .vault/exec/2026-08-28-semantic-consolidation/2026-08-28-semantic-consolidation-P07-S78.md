---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:2f8b08f59be5434273fe945a7f4cff5a01ec94f1ef45de9b533eaf36f8a85108'
step_id: 'S78'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the llm providers facade, whose lazy AnthropicAdapter arm had no caller because the client already imported that adapter from its own module, and publicise the ProviderAdapter contract four packages depend on

## Scope

- `src/cadrumo/llm/providers/`

## Changes

- `M` `src/cadrumo/llm/providers/__init__.py`
- `M` `src/cadrumo/llm/providers/base.py`
- `M` `src/cadrumo/llm/providers/anthropic.py`
- `M` `src/cadrumo/llm/providers/gemini.py`
- `M` `src/cadrumo/llm/providers/local.py`
- `M` `src/cadrumo/llm/providers/openai.py`
- `M` `src/cadrumo/llm/client.py`
- `M` `src/cadrumo/llm/tests/test_client.py`
- `M` `src/cadrumo/llm/tests/test_parameter_capability_boundary.py`
- `M` `src/cadrumo/llm/tests/test_vision_capability_boundary.py`
- `M` `src/cadrumo/application/ledger/evidence_draft.py`
- `M` `src/cadrumo/application/ledger/llm_classification.py`
- `M` `src/cadrumo/application/ledger/tests/test_evidence_corpus_parsing.py`
- `M` `src/cadrumo/adapters/outbound/llm/tests/test_evidence_consent_ledger.py`
- `verify:` `pytest src/cadrumo/llm src/cadrumo/adapters/outbound/llm -n 0 -m ""` -> `pass`

## Notes

Four of the 568 tests in the verification run reported failures that are not
this Step's. Two (`test_provenance_stamp_singularity`,
`test_evidence_marker_declared_at_every_builder`) walk the source tree and hit
a file a peer session deleted mid-run; both pass on re-run. One requires
`CADRUMO_LIVE_TESTS_ENABLED` and refuses by design. One raises
`NoRevisionForPeriodError` against registry TOMLs a peer is authoring.
