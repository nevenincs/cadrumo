---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1964bee0624e3e32304fe23164677ded3d841b214661aedf20ec231e4b1393eb'
step_id: 'S68'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Adjudicate and canonicalize every remaining packaging fixture cluster in the census

## Scope

- `packaging`

## Description

- Inventory every fixture declared under `packaging` with the live AST census.
- Compare repeated fixture names, normalized bodies, scope, dependencies, artifacts,
  visibility, and current consumers.
- Adjudicate cross-tree cohort fixtures that resemble the packaging owners without
  treating shared names as proof of substitutability.
- Retain each owner whose lifecycle or consumer contract is distinct.

## Outcome

The live census found four packaging fixtures. The only repeated packaging name,
`built_cohort`, represents incompatible builders: Homebrew produces three source
distributions while Scoop produces three wheels and a Scoop release binding. The
remaining `real_cohort` and `client_install_evidence` fixtures own different stages
of the MCPB installation lifecycle.

The similarly named cross-tree `installed_cohort` fixtures were also adjudicated.
One establishes a six-artifact installed-oracle environment; the other establishes
separate core-only and LLM-extra environments for CLI provisioning behavior. No
fixture belongs to an exact-body or substitution-candidate group, and all packaging
fixtures remain module-local with distinct consumers. No source change was therefore
authorized or required.

## Notes

Semantic RAG discovery was attempted first but could not start because the available
environment exposed CPU-only Torch to a GPU-required service. Exact source discovery,
the live AST census, and an independent review supplied the fallback evidence. No
tests were run because this was a read-only retention adjudication with no runtime
change.
