---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:71730a94ea6d588d0d2baa9f09e916dd0a644e098de4c39b3594ae8575bedb37'
step_id: 'S25'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---
# Add real-filesystem adversarial coverage for capsule summary and label-head behavior

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/tests/`

## Description

- Prove linked roots, candidates, labels, and heads refuse through anchored
  no-follow filesystem operations.
- Prove malformed commit, label, and head records and retired layouts refuse.
- Exercise real path obstruction, directory-generation replacement, and
  staging-only interrupted publication without synthetic verdicts.
- Bind commit and label bytes to one anchored capsule observation so concurrent
  replacement cannot splice generations.

## Outcome

Implemented in `bbe33b3dcd`. Independent current-HEAD verification passes 71
focused capsule, label-head, and path-identity tests. Ruff over the four changed
files and `git diff --check` pass.

## Notes

The adversarial matrix covers links, malformed records, retired layout, real OS
denial, real directory replacement, and interrupted staging publication. POSIX
returns a coherent old commit and old label through retained descriptors;
Windows may instead refuse the actual replacement under its no-delete anchors.
Only those real outcomes are accepted. Independent review found no duplicate
authority and no MEDIUM or HIGH issue.
