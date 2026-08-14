---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:340bbb6d1b35506e515581736eb0532aeda234538df5f9607e3fe78bb09d03c5'
step_id: 'S96'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Run feature-scoped and repository-wide VaultSpec checks without rewriting unrelated debt

## Scope

- `.vault`

## Description

- Run the feature-scoped checks and resolve anything this feature owns.
- Rebuild the feature index after the phase added documents.
- Run the repository-wide checks and report their result without editing other campaigns' documents.

## Outcome

The feature-scoped checks pass with zero errors and zero warnings across all nineteen checks, including structure, frontmatter, links, dangling references, placeholders, orphans, execution mapping, schema, decision status and encoding. One warning was found and fixed: the feature index had fallen behind the documents added during the close phase, and it was rebuilt through the owning verb rather than by hand.

The repository-wide run reports zero errors and roughly thirteen hundred advisory warnings. Almost all are plans belonging to other campaigns that carry no reference to a research document. None is an error and none belongs to this feature.

## Notes

The repository-wide warnings are reported here and deliberately not touched. Editing other campaigns' documents to clear a count would manufacture a green rather than earn one, and the campaign's own verification asks for exactly this separation: feature-scoped debt resolved, repository-wide debt reported.
