---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4b8b57385f49ba081f7d039f500983475f164435dfb986958ac7b38b91238101'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-research]]"
---



# `source-casilla-integration` audit: `census and ratchet foundation`

## Scope

Reviewed the canonical source-connectivity census, structural discovery, completeness assignment,
maintenance CLI, monotonic governance check, live connected-proof authority integration, mutation tests,
and quality-gate enrollment delivered through `W01.P04.S17` to `W01.P05.S29`. The review tested whether
the implementation proves the ADR and plan claims rather than merely accepting its current manifest.

## Findings

### destination-authority | high | Advisory destination references are not resolved against registry authority

`advisory_destination_refs` are unconstrained strings. Manifest validation proves only uniqueness, and
`test_advisory_destination_candidates_have_one_census_owner` repeats that same uniqueness assertion.
Neither the loader nor the completeness check joins these references to `RegistryDestinationRecord`, even
though `derive_registry_destination_records` already exists beside the census loader. A misspelled,
invented, removed, or revision-ambiguous modelo/casilla destination therefore remains green. This leaves
the destination half of the promised source-to-casilla census unverified.

### connected-gate-composition | high | The enrolled CLI and CI path cannot validate a connected row

`check_capability_census` accepts a `proof_authority`, but `compare` never supplies one and the enrolled
tests load the bundled census without one. The core correctly refuses every connected row in that state.
Consequently, the first legitimate vertical slice promoted to `connected` will red the standard gate even
when its resolver, workflow, evidence digest, and encrypted revision are valid; alternatively, weakening
the loader would make the proof non-live. The concrete authority exists, but no canonical gate composition
owns its calculation-revision repository, workflow catalogue, repository root, and execution lifecycle.

### evidence-locator-drift | medium | Reviewed capability locators can silently become stale

Stable `capability_ids` correctly avoid line-number identity, but the evidence-bearing
`capability_locators` are checked only for intra-row uniqueness. The completeness gate never verifies that
the referenced path exists, that an optional line is valid, or that the locator still identifies the
capability claimed by the adjacent stable ID. Source edits can therefore leave a passing census whose
review links no longer re-fetch the evidence described by its grounding.

### coverage-bucket-auditability | medium | Frozen remainder decisions lack per-capability review evidence

Five digest-pinned coverage rows classify 412 capabilities under aggregate `not_applicable` or
`duplicate_or_stale` decisions. The digest prevents silent membership change, but it does not retain a
reviewed reason per member, and the comparison output reports counts rather than row membership. A later
auditor can prove that the frozen set is unchanged but cannot determine from the canonical artifact why a
particular secure repository, helper, ingress surface, assembler, or ownership declaration was excluded as
an independent candidate.

### static-check-surface | medium | New census code is not clean under the repository type checker

The targeted type run reports avoidable unresolved attributes from `manifest: object` in both assignment
and governance functions, alongside project-wide lazy-export diagnostics on the imported core symbols.
Ruff and runtime tests pass, but the implementation does not currently satisfy the static-quality surface
expected of a gate module. The manifest APIs should carry their concrete protocol or model type, and the
selected type-check lane must be exercised after the lazy-import boundary is accounted for.

## Recommendations

- Resolve `destination-authority` before inventory adjudication by defining typed destination candidate
  identities and checking them against the validated registry projection, while retaining lexical matches
  as advisory-only evidence.
- Resolve `connected-gate-composition` before promoting any slice to connected. Record the gate execution
  model in a follow-on ADR if CI proof uses a deterministic encrypted fixture rather than an operator
  profile; the decision must preserve the existing live authority rather than create a second verifier.
- Resolve `evidence-locator-drift` by checking re-fetchability and capability correspondence without making
  line numbers part of stable identity.
- Resolve `coverage-bucket-auditability` by emitting deterministic selector membership and retaining a
  reviewed per-capability disposition reason or an equally auditable generated companion artifact.
- Resolve `static-check-surface` by replacing opaque object annotations with the canonical census contract
  and enrolling the relevant modules in the intended type-check surface.
