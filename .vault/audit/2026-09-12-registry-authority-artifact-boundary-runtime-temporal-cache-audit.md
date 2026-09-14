---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:dcd21e85c000bd59977d75180fd1ddfd544478ce54261f3f011fddd97fcd3254'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` audit: `Runtime temporal admission and cache identity`

## Scope

Reviewed W04.P07.S15 against the accepted immutable-publication ADR, its research grounding, and the approved plan. The review covered only the S15 changes in `src/cadrumo/domain/calculations/registry/authority.py`, `src/cadrumo/application/filing/draft_construction.py`, `src/cadrumo/application/filing/runtime.py`, and their focused tests. It assessed central filing-year admission, ownership and isolation of the shared runtime snapshot cache, concurrent access, and invalidation across atomic republication or in-place artifact replacement.

Filing-year admission now delegates to `ValidatedRegistryAuthority.project_filing_year` and translates registry projection refusal at the application boundary. The filing runtime no longer owns a second memoization layer, while one decoded immutable artifact shares one authority-private cache and returns deep copies to callers. The artifact reader verifies file identity on every call and refuses corrupt replacements rather than serving the prior cached graph.

The final re-review inspected the unique artifact-incarnation coordinate and the same-digest changed-publication regression. A focused pytest invocation could not collect in the review environment because `pydantic` is absent, before either selected test executed; the implementation and regression were therefore verified statically against the live tree.

## Findings

### republished-artifact-coordinate-alias | high | A changed artifact can accept a capture from the publication it replaced

`_artifact_coordinate_domain` in `src/cadrumo/domain/calculations/registry/authority.py:128` derives the temporal comparison domain only from `AuthorityArtifact.identity_digest` and a process nonce, and both captures and current coordinates remain at generation zero (`src/cadrumo/domain/calculations/registry/authority.py:522` and `src/cadrumo/domain/calculations/registry/authority.py:533`). `published_authority` correctly creates a new authority and snapshot cache whenever `read_shared_authority_artifact` returns a new decoded artifact, but two distinct valid payloads carrying the same candidate-input digest therefore mint the same comparison domain. A capture taken from the old authority consequently passes `require_current` against the replacement authority even though the publication and cached projections changed. This is reachable when publication is repeated without source-input changes, including after compiler behavior changes; the artifact writer also permits a valid changed typed payload to retain the same identity digest. The republish tests prove object/cache replacement, but only vary the digest or republish identical bytes and never assert that an old capture is rejected by a semantically changed same-digest publication. This breaks the S15 temporal invalidation contract and leaves the step not closable.

Resolution (2026-09-13): resolved. `_artifact_coordinate_domain` now includes a freshly generated artifact-incarnation token in addition to the candidate digest and process nonce. The token is minted only when a new `ValidatedRegistryAuthority` is constructed; repeated reads of one unchanged artifact return that same cached authority under `_published_authorities_lock`, preserving one stable comparison domain and snapshot cache. A replacement artifact constructs a new authority and necessarily receives a distinct domain even when its candidate digest is unchanged. The regression republishes a structurally changed, valid artifact while retaining the original digest, proves authority and cache replacement, and requires the old capture to refuse comparison with the replacement coordinate. Moving the shared-artifact read inside the authority cache lock also prevents concurrent old/new reads from overwriting the cache out of publication order. No unresolved LOW-or-higher findings remain, and W04.P07.S15 is closable.

## Recommendations

- Bind the authority comparison domain to the verified publication payload or artifact incarnation, not only to the candidate-input identity digest. Add a regression that publishes two different valid payloads with the same `identity_digest`, captures from the first, republishes the second, and requires the second authority to reject the first capture while preserving shared cache identity for repeated reads of one unchanged artifact.
- Completed on 2026-09-13 by the unique constructed-artifact incarnation domain and the same-digest changed-publication regression. No further corrective action is required for S15.
