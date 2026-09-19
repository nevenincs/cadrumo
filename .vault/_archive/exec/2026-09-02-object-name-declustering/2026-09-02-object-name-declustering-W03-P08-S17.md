---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:865e1b558c708b8ce6747693e76820d7d5224edf01a0bd355bd7b7389c95ef74'
step_id: 'S17'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Add the grouped fix-object-names recipe with pass-through arguments and rehearsal as its no-argument default

## Scope

- `Justfile`

## Changes

- `M` `justfile`
- `verify:` `just --list` -> `pass`
- `verify:` `just --summary` -> `pass`
- `verify:` `just --show fix-object-names` -> `pass`
- `verify:` `just --dry-run fix-object-names` -> `pass`
- `verify:` `just --dry-run fix-object-names apply --receipt "receipt with spaces.json" --receipt-id "sha256:a&b" --json` -> `pass`
- `verify:` `just fix-object-names "mode with & spaces"` -> `pass`
- `verify:` `just fix-object-names apply --receipt "receipt with spaces.json" --receipt-id "sha256:a&b" --json` -> `pass`
- `verify:` `git diff --check -- justfile` -> `pass`
- `verify:` `independent current-byte S17 recipe safety review` -> `pass`

## Notes

The two live forwarding probes intentionally exercised safe CLI refusals and propagated exit code 2. A no-argument smoke was not executed because the S19 default manifest does not yet exist; dry-run proved the no-argument expansion. Repository-wide `just --unstable --fmt --check` remains red on broad pre-existing Justfile formatting drift, so no unrelated whole-file formatting was applied. Shared-tree commit `105b889e30` landed the recipe together with separately owned S16 test changes; this record claims only `justfile`. Mixed commit `37b6ecf94c` landed the review audit, Step Record scaffold, and plan closure with unrelated Vaultspec documents.
