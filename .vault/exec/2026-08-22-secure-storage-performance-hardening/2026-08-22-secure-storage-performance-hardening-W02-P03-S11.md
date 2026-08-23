---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ac7166e0229cbdf996e1df82a0bf1be4a03986f899934a3f04fda47e0f3ba43e'
step_id: 'S11'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Make schema and operator-help discovery consume registration metadata without materializing handler subtrees

## Scope

- `src/cadrumo/entrypoints/cli/_command_schema.py`

## Description

- Retain the historical latency observation while rejecting its generated-resource mechanism as nonconforming evidence.
- Re-prove result-schema identity, parameter, localized operator-help, policy, handler-target, and path discovery directly from the production CommandSpec graph.
- Remove dormant materialized-schema compatibility aliases rather than preserving a fallback or re-export.
- Move the remaining handler-owned toggle choices into immutable ValueContract data consumed by both runtime and schema projection, then delete the private behavior enum.
- Reject authored choices combined with a parser or Click type so competing value authorities fail during spec construction.
- Correct operator reconciliation provenance to identify production CommandSpec projections instead of a Click tree or schema registry.
- Add fresh-process zero-handler-import and exact graph-set proofs over all 296 current result-schema identities.

## Outcome

Runtime schema and operator-help discovery now consumes only the tracked production CommandSpec graph. The exact result-schema, input-schema, and operator-help sets are derived dynamically; paths, localized help, parameters, policies, choices, and lazy public targets remain owned by their specs. A fresh-process probe projects every identity while loading zero newly imported behavior target modules.

The original measurements remain useful historical latency observations: five metadata-oriented samples had a 648.8 ms median versus 5,216.0 ms for three materialized-tree samples on the same host, approximately eightfold lower. They do not validate the rejected generated JSON architecture, packaged-resource claim, old 300-row inventory, or former four-command gap. The post-S54 graph is the sole current authority and the retired passphrase path is absent.

Verification passed:

- scoped Ruff formatting and lint;
- scoped `ty` analysis;
- exact CommandSpec/result-schema/input-schema/operator-help parity;
- fresh-process zero behavior-target import proof;
- real operator action resolution from graph-owned paths and parameter contracts;
- physical absence of both command JSON files, their readers, and their development generators;
- independent code review with no open critical, high, medium, or low findings.

## Notes

The former generated-resource commits and their review remain historical provenance only and are superseded by S54 plus this reproof. Neither the generated runtime resource nor its generator was restored. S14 was not started. Concurrent Modelo registry and locale work remained unstaged.
