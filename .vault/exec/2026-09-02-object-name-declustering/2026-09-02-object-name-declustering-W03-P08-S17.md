---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:73b600ca7d2413150e4aa054ba6ca0cd3adf9836de69dc3aa3b995513fbbbc7d'
step_id: 'S17'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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

The two live forwarding probes intentionally exercised safe CLI refusals and propagated exit code 2. A no-argument smoke was not executed because the S19 default manifest does not yet exist; dry-run proved the no-argument expansion. Repository-wide `just --unstable --fmt --check` remains red on broad pre-existing Justfile formatting drift, so no unrelated whole-file formatting was applied.
