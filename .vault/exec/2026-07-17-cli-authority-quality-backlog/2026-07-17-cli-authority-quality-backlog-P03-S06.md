---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S06'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Correct namespace registry metadata drift and make each namespace definition the sole authority for identifier, schema version, sensitivity, default object key, key grammar, owner, and custody

## Scope

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`

## Description

- Pin the exact object-key drift by cross-referencing the two suspect namespace definitions against the live keys their repositories write, not the declared strings.
- Correct `TRANSACTION_CATALOGUE_NAMESPACE.object_key_grammar` from `transaction-catalogue:{bucket_id}` — which is the `BucketEvent` audit `object_id` produced by `transaction_catalogue_object_id`, not a secure-object key — to the two real shapes the repository writes: `transaction:{bucket_id}:{transaction_id}` per-transaction rows (`transaction_object_key`) and `transaction-index:{bucket_id}` the per-bucket membership index (`transaction_index_object_key`).
- Correct `CALCULATION_OBSERVATIONS_NAMESPACE.object_key_grammar` from `{modelo}:{filing_year}:{period}` to `{modelo}:{filing_year}:{period}[:{member_nif}]`, restoring the optional per-grupo-member key variant `member_observation_key` writes for the 353-from-322 `per_grupo_member` fan-in.
- Add a real-behaviour gate that derives the keys from the production helpers and matches them against the declared grammar, with anti-tautology tests proving each retired grammar rejected the live keys.
- Promote `member_observation_key` to the `cadrumo.application.calculations` public facade as the gate's canonical import.

## Outcome

- Both grammars now describe the live object-key shapes; the correction is behaviour-preserving because `object_key_grammar` is descriptive metadata read only by tests, never by runtime key derivation (confirmed by a whole-tree scan of `object_key_grammar` reads).
- New gate `test_namespace_key_grammar.py` (4 tests) passes; the full storage tests folder passes (178 including the new file). `ruff`, `ty`, the docstring core-struct-links gate, and the changed-file surface are green.
- Committed as `7d28350783` (three files: the registry definition, the calculations facade, and the new gate).

## Notes

- Two repository-wide gates are red on committed HEAD from unrelated peer work in `application/user_profile` (the export-publication / P04-door quiescence zone): `test_sensitive_persistence_policy.py` inventories new `os.open`/`os.write` sites in `_bundle_export.py`, and `test_import_hygiene_gate.py` flags `test_bundle_export.py` reaching private `_portable_export.CoverageManifest`. Neither touches the S06 surface; both are owner-distinct and left for the owning campaign.
- The `transaction-catalogue:{bucket_id}` audit `object_id` (`transaction_catalogue_object_id`) is a legitimately separate concept and was deliberately left intact; a source comment now records that it must not be conflated with the secure-object key grammar.
