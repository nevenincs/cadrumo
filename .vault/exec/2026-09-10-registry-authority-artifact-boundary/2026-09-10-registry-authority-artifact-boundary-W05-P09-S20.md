---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:0356d1edf75b3a9eb69ce799b5e44dcab7efdd3b2fb91d387824b68a4fd3cfd1'
step_id: 'S20'
related:
  - '[[2026-09-10-registry-authority-artifact-boundary-plan]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-remediation-result-reference]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-authority-backend-final-review-audit]]'
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Separate source-manifest, compiler-schema build, component-dependency, and payload identities and enforce full canonical publication

## Scope

- `dev/registry/pipeline/authority_publication.py`
- `src/cadrumo/domain/calculations/registry/authority_artifact.py`

## Changes

- `A` `dev/registry/compiler/build_identity.py`
- `M` `dev/registry/pipeline/authority_publication.py`
- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
