---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:054eea0522d956dcbd5c01c459a606505b8f56a3ab95b3cd2a0f4e617775a94e'
step_id: 'S40'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Adjudicate four registry and persistence families against the mechanisms that govern them: the counterpart and invoice binding builders whose source kinds sit in RESERVED_SOURCE_KINDS as taxonomy headroom carrying no binding and no resolver by declaration; the withholding family whose kind sits in DEFERRED_SOURCE_KINDS and raises a standing advisory rather than a silent blank; the secure-object schema upgrader registry, where the durability floor is the from-birth version while six namespaces declare version two and one declares four, so an older row has no registered upgrade hop and the fail-closed decode path returns a typed refusal rather than a placeholder; and the registry handoff path audit nothing runs, so an unconsumed relation is never reported

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py -m "" -n 0` -> `pass`

## Notes

The secure-object upgrader cluster carries the one finding here an owner may
want to act on. `SECURE_OBJECT_DURABILITY_FLOOR` is 1, meaning every read path
keeps version 1 readable, while six namespaces declare schema version 2 and one
declares 4. No production code registers an upgrader, so a row stored at an
older version in those namespaces has no upgrade hop. The decode path is
documented fail-closed and returns the typed error rather than a placeholder,
so this surfaces as a refusal rather than a mis-read. Whether such a row exists
is deployment state the tree cannot answer.
