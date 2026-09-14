---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:4c898b9472e99e9bf9b6da3dc4c503910ae522cb15cc1aca6467db7172142bf8'
step_id: 'S26'
related:
  - '[[2026-09-10-registry-authority-artifact-boundary-plan]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-remediation-result-reference]]'
  - '[[2026-09-14-registry-authority-artifact-boundary-authority-backend-final-review-audit]]'
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Capture compiler-schema identity and exact uncached or staged transitive input manifests for publication

## Scope

- `dev/registry/pipeline/authority_publication.py`
- `dev/registry/compiler/source_evidence_fingerprint.py`

## Changes

- `A` `dev/registry/compiler/build_identity.py`
- `M` `dev/registry/compiler/source_evidence_fingerprint.py`
- `M` `dev/registry/compiler/loader_fingerprints.py`
- `M` `dev/registry/pipeline/authority_publication.py`
