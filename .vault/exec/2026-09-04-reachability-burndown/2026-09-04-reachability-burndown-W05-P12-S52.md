---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:da917c1c1a5ccd9eaf465e3356d2705c7ff7520a92302c714e501531984bb6aa'
step_id: 'S52'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Adjudicate two supersessions whose displacing holder states the arrangement in its own docstring: the path-taking capsule restore wrappers are the second publication path that the shared authority explicitly exists to prevent, since a directory restore and an archive import differ only in how they obtain the capsule source and the live CLI reads the source then publishes; and the workspace manifest validators regenerate and compare a manifest that cannot differ, because the live capture is documented atomic with one generating authority whose own digest becomes the observation, so the comparison would always trivially pass

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

A limitation of the module-split tool surfaced here and is worth stating: it
counts references from OTHER modules, so `generate_modelo_workspace_field_manifest`
showed zero while `capture_modelo_workspace_manifest` calls it on the next line
of the same file. It is not a finding, and the audit agrees. Read a zero from
that tool as "no cross-module consumer", never as "unused".
