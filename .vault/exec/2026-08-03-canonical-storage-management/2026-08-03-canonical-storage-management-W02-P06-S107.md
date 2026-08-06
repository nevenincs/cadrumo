---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ee697584aea5c130ea0f64ce7d279dabb7f7a48804e838e7a1cda0bd8b561119'
step_id: 'S107'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare the five filename-template grammars using the now-landed StoragePathDefinition mechanism, which the blob-store, local-provider, and run-trace families already prove handles exactly this shape with no model change and no ADR ruling required, closing the open question this Step originally posed rather than answering it: llm-usage slash usage-star.jsonl, llm-run-telemetry slash run-telemetry-star.jsonl, tokens slash star-star-auth.lock, cache slash registry-verdict slash prefix-digest.json, and llm-cache slash provider slash model slash star-star.json

## Scope

- `src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py`

## Description

## Outcome

Landed by a peer lane, confirmed at pinned HEAD `b6287cd8f5`. All five `StoragePathDefinition` grammars are declared in `_storage_path_definitions.py`: `llm_usage_record` (`<root>/llm-usage/usage-<timestamp>.jsonl`), `llm_run_telemetry_record` (`<root>/llm-run-telemetry/run-telemetry-<timestamp>.jsonl`), `auth_acquisition_lock` (`<root>/tokens/<bucket_id>-<auth_provider_kind>-auth.lock`), `validation_verdict_cache_entry` (`<root>/cache/registry-verdict/cadrumo_validation_verdict_<sha256[:16]>.json`), and `llm_cache_entry` (`<root>/cache/llm-cache/<provider>/<model>/<sha256>-<sha256>.json`), no model change and no ADR ruling, confirming the open question this Step originally posed. A code comment on the declaration records that three of the five (usage, run-telemetry, llm-cache) are never materialised as files — their producers persist through encrypted SQL secure objects and the grammar documents the logical display-path contract only, not on-disk presence — which is a deliberate design note, not a gap in this Step.

## Notes
