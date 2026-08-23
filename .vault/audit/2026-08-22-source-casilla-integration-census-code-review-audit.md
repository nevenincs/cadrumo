---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:9b298f8c544d80ed0c008967cefb91d542531c4c2f2971ff179a1a9a95fbf411'
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

### destination-authority | resolved | Typed candidates resolve against validated registry authority

`advisory_destination_refs` are unconstrained strings. Manifest validation proves only uniqueness, and
`test_advisory_destination_candidates_have_one_census_owner` repeats that same uniqueness assertion.
Neither the loader nor the completeness check joins these references to `RegistryDestinationRecord`, even
though `derive_registry_destination_records` already exists beside the census loader. A misspelled,
invented, removed, or revision-ambiguous modelo/casilla destination therefore remains green. This leaves
the destination half of the promised source-to-casilla census unverified.

Resolution review 2026-08-23: PASS. Accepted destinations now use strict `RegistryDestinationCandidate`
records keyed by modelo plus either canonical semantic role or `BindingSourceKind`. Manifest validation
enforces one census owner and `validate_census_destination_candidates` resolves every candidate against
the loaded validated registry, refusing absent modelos, absent binding sources, absent semantic roles,
and revision-local ambiguity. Advisory strings remain explicitly non-authoritative. Positive live
resolution and absent/ambiguous mutation tests cover the boundary; their current live-registry run is
temporarily blocked by a concurrent malformed M200 fragment outside this feature scope.

### connected-gate-composition | resolved | Canonical live composition executes independent encrypted proof evidence

`check_capability_census` accepts a `proof_authority`, but `compare` never supplies one and the enrolled
tests load the bundled census without one. The core correctly refuses every connected row in that state.
Consequently, the first legitimate vertical slice promoted to `connected` will red the standard gate even
when its resolver, workflow, evidence digest, and encrypted revision are valid; alternatively, weakening
the loader would make the proof non-live. The concrete authority exists, but no canonical gate composition
owns its calculation-revision repository, workflow catalogue, repository root, and execution lifecycle.

Resolution review 2026-08-23: PASS. The enrolled comparison path now composes the existing live authority
automatically only when connected rows exist. Its independently authored, data-only M349 scenario
traverses canonical invoice construction and persistence, enrolled invoice resolution, the registry
calculation engine, canonical replay and observation construction, atomic encrypted calculation-revision
persistence, and encrypted reload. Production ownership, operator workflow, repository-root digests,
destinations, and exact primary provenance remain independent conjunctive gates. Focused proofs cover a
nonzero destination, source mutation changing fingerprint and revision identity, missing primary refusal,
zero-connected non-allocation, and deterministic session, engine, database, and temporary-directory
cleanup. Exact-one matching logic also refuses duplicate primaries.

### evidence-locator-drift | resolved | Stable capability identities retain re-fetchable live locators

Stable `capability_ids` correctly avoid line-number identity, but the evidence-bearing
`capability_locators` are checked only for intra-row uniqueness. The completeness gate never verifies that
the referenced path exists, that an optional line is valid, or that the locator still identifies the
capability claimed by the adjacent stable ID. Source edits can therefore leave a passing census whose
review links no longer re-fetch the evidence described by its grounding.

Resolution review 2026-08-23: PASS. `discovered_source_capability_evidence` independently projects one
current locator for every discovered stable capability. `check_capability_locators` refuses missing files,
out-of-range optional lines, absent identities, and locator-to-identity drift for explicit claims. Focused
mutation tests prove missing-line and correspondence failures. The current full-tree discovery invocation
is blocked by concurrent command-spec file replacement and unresolved command-spec authoring outside this
feature; the independent detector and mutation suite remains green.

### coverage-bucket-auditability | resolved | Comparison emits deterministic evidence for every assigned capability

Five digest-pinned coverage rows classify 412 capabilities under aggregate `not_applicable` or
`duplicate_or_stale` decisions. The digest prevents silent membership change, but it does not retain a
reviewed reason per member, and the comparison output reports counts rather than row membership. A later
auditor can prove that the frozen set is unchanged but cannot determine from the canonical artifact why a
particular secure repository, helper, ingress surface, assembler, or ownership declaration was excluded as
an independent candidate.

Resolution review 2026-08-23: PASS. Successful comparison retains deterministic per-candidate assignments,
and `project_census_memberships` expands every assigned capability into an operator-readable record carrying
candidate, disposition, reviewed decision reason, and grounding references. Ordering is stable by capability
identity, and a focused projection test asserts the complete record rather than only counts.

### static-check-surface | resolved | Census production and tests are clean on the intended strict type surface

The targeted type run reports avoidable unresolved attributes from `manifest: object` in both assignment
and governance functions, alongside project-wide lazy-export diagnostics on the imported core symbols.
Ruff and runtime tests pass, but the implementation does not currently satisfy the static-quality surface
expected of a gate module. The manifest APIs should carry their concrete protocol or model type, and the
selected type-check lane must be exercised after the lazy-import boundary is accounted for.

Resolution review 2026-08-23: PASS. Census assignment, governance, comparison, CLI projection, discovery,
and live-proof APIs now carry concrete manifest/result contracts. `uv run ty check dev/source_connectivity`
passes with zero diagnostics, and scoped Ruff passes across the census modules plus canonical authority and
core contract. A broader ad hoc authority-only `ty` invocation still exposes shared lazy-export/narrowing
diagnostics outside the intended S159 census surface; it is not evidence against this finding's remediation.

## Recommendations

- All five original findings are resolved. Proceed with `W01.P23.S161` closure once the CLI-managed audit,
  execution record, and plan mapping are written atomically.
- Preserve the full-tree gate failures as shared-worktree exclusions: disappearing passphrase command-spec
  input, unresolved modelo command-spec declarations, operator-surface reconciliation drift, and the
  malformed concurrent M200 registry fragment are not source-connectivity census regressions.
- As non-blocking hardening, add a direct duplicate-primary composition test and register the ephemeral
  bucket-session cleanup before temporary-directory and engine creation.
