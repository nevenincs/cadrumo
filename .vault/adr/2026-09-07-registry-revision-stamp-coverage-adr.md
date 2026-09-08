---
tags:
  - '#adr'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:8bde73ee0f5df796ac5eabf763d2694c38d1730701915f982b3e46ad3daefc4e'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-research]]"
  - "[[2026-09-07-registry-revision-stamp-coverage-reference]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
  - "[[2026-06-10-calculation-engine-foundations-plan]]"
  - "[[2026-09-02-registry-declaration-hardening-identifier-grammar-adr]]"
---

# `registry-revision-stamp-coverage` adr: `Extend stamp-and-reconfirm to every persisted registry-derived value carrier` | (**status:** `accepted`)

## Problem Statement

The accepted period-revision architecture makes registry resolution authoritative,
and the closed calculation-engine foundations work established stamp-and-reconfirm
for carry observations. That protection is not expressed as a persistence-wide
invariant. Other durable artefacts retain registry-derived values without the
coordinate that gave those values meaning, leaving bare read-side consumers to
substitute identifier or string-shaped proxies.

The complete carrier sweep and the M349 failure are grounded in
`2026-09-07-registry-revision-stamp-coverage-reference`. The decision is needed
before the registry-shaped TUI exposes persisted values at a filing-decision
surface. This ADR extends the accepted decision; it does not reopen the closed
calculation-engine plan or decide identifier grammar.

## Considerations

- `ValidatedRegistryAuthority.select_revision` remains the sole resolver under
  `2026-06-10-period-revision-resolution-adr`.
- The carrier inventory includes direct, indirect, partial, nested, and
  immutable-external-format shapes; one field-placement rule cannot ignore those
  boundaries (`2026-09-07-registry-revision-stamp-coverage-reference`).
- The closed W01.P02.S03/S04 precedent supplies the write stamp, shared read gate,
  and divergence refusal; its earlier legacy-advisory wording is not retained
  (`2026-09-07-registry-revision-stamp-coverage-research`).
- The current gate and observation envelope require a stamp. That strict shape is
  the canonical baseline; missing-coordinate admission must not be reintroduced
  (`2026-09-07-registry-revision-stamp-coverage-research`).
- Identifier grammar can constrain spelling but cannot prove which revision
  produced a persisted value
  (`2026-09-02-registry-declaration-hardening-identifier-grammar-adr`).

## Considered options

**Patch `CalculationRevision` and M349 only.** Smallest immediate change, but
leaves the same unprovable-read defect in the other measured carriers and permits
the class to recur. Rejected.

**Give each carrier its own re-confirmation logic.** Fits local schemas, but
creates several definitions of registry agreement and violates the established
single-gate architecture. Rejected.

**Stamp every carrier and reject every unstamped row.** Establishes one canonical
invariant. Existing rows may be converted before admission only when durable
identity proves the complete coordinate; otherwise they remain invalid. Selected.

**Admit missing-coordinate rows through a typed advisory.** Preserves access to
old payloads, but necessarily adds a second, weaker validity state and compatibility
logic to every reader. Rejected: there is no supported legacy value shape.

## Constraints

- This extends the accepted period-revision decision and the closed W01.P02
  implementation; neither parent is reopened. Their authority boundary is stable,
  while the missing-stamp call shape needs an explicit compatible evolution.
- Re-confirmation stays in the application layer and receives registry authority
  through existing ports. Domain objects and adapters do not resolve revisions.
- `RegistrySnapshotRef` is the canonical coordinate. Locally distributed fields
  must have one constructor/validator that proves equivalence to it.
- Nested payloads inherit their owning aggregate's stamp. They do not duplicate or
  redeclare registry identity.
- Official-format bytes remain unchanged; their nearest durable
  application-owned envelope carries the stamp.
- Conversion tooling, if required by a storage migration, may emit only canonical
  stamped rows and must fail when the complete coordinate cannot be proved. No
  runtime legacy schema, optional stamp, fallback, shim, or advisory arm exists.

## Implementation

On acceptance, every newly persisted application-owned carrier of
registry-derived values will carry the canonical registry coordinate at its
aggregate boundary. Creation paths copy the coordinate already selected by the
validated authority; deserializers validate completeness and agreement with any
existing identity fields. Derived reports, reconciliation records, and package or
custody manifests copy the producing aggregate's coordinate. Source-and-target
handoffs retain both coordinates.

The encrypted AEAT `FiledDeclaracionObservation` is included in this rule. Its
optional opaque `registry_snapshot_id` is replaced by required
`RegistrySnapshotRef`; the digest-only field is deleted rather than retained as
a compatibility alias.

Every read that uses a stamped value against live registry meaning will call the
existing `revision_carry_outcome` gate, evolved only as needed to accept the
canonical coordinate. A divergent stamp fails closed. A missing stamp is invalid
at schema or repository admission and never reaches the gate.

Carrier-specific application helpers may translate that shared outcome into a
bounded-context error, but they may neither resolve a revision themselves nor
admit an alternate comparison. Repository catalogue, verification, filing,
export, review, reconciliation, summary, workspace, advisory, and live-capture
reads are all included; a gate on only the originally observed UI projection is
insufficient.

Migration may convert only coordinates proved by durable identity joins. It will
not guess from current selection, identifier grammar, prefixes, layout ids, or
other string proxies. Rows that cannot be proved are rejected rather than exposed
through a compatibility representation.
Once `CalculationRevision` supplies its coordinate, the M349 prefix proxy is
removed and membership is re-confirmed from the law-determined revision through
the shared gate.

Coverage tests will enumerate durable registry-derived carrier schemas and their
write/read boundaries so a new carrier cannot persist interpreted values without
declaring its stamp strategy. Exact carrier locators and complete precedents live
in `2026-09-07-registry-revision-stamp-coverage-reference`.

## Rationale

The coverage-wide strict option is the only one that closes the defect class
rather than its first visible instance while retaining one validity model.
Reusing the shared gate preserves one semantic owner for registry agreement.
Rejecting unstamped values prevents compatibility behavior from becoming a second
authority, and proof-only conversion distinguishes evidence from convenience. The
comparison and migration trade-offs are grounded in
`2026-09-07-registry-revision-stamp-coverage-research`.

## Consequences

Persisted values become self-describing enough for lawful re-confirmation, and
the TUI can no longer combine live registry form with silently proxy-interpreted
revision data. The same invariant protects future carriers and removes M349's
prefix dependency.

Schemas, serializers, secure-storage records, repository interfaces, and fixtures
will change across several bounded contexts. Canonical conversion requires
evidence-preserving joins and fails for rows whose coordinate cannot be proved.
Reads now incur authority resolution or an equivalent validated snapshot lookup.
Deprecated proxy, fallback, optional-stamp, and compatibility branches are removed
where the canonical coordinate makes them obsolete.
Modelo 303 has no exceptional legacy envelope: disposition-aware normalization is
mandatory at its sole supported write ingress, and an unnormalised stored payload
is rejected during model admission.
