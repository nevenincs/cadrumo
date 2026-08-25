---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5cee0b2d15a59e797e470c8a0b6b53b12cee2244224a330f8f957813fed2a1de'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-25-tui-architecture-s128-workspace-projection-composition-reference]]"
  - "[[2026-06-01-domain-boundary-audit-adr]]"
---

# `tui-architecture` audit: `Workspace owner seam architecture reconciliation`

## Scope

Read-only reconciliation of the accepted Workspace decision, the S125-S167 and
S128-S131 plan cohort, the S128 composition reference, the enforced layer graph,
and the live S125-S127 implementation. Two independent Sol architecture reviews
were combined with Vaultspec RAG semantic discovery, whole-file reads, and exact
symbol/import census. The audit specifically tested for an implementable
dependency direction, one canonical semantic owner per contributor, current-only
contract topology, and absence of shims, aliases, fallbacks, bridge modules, and
parallel Workspace authorities.

## Findings

### workspace-owner-seam | critical | S159 requires an illegal dependency

S126 canonically owns the `ModeloWorkspace*` producer contract family in
`cadrumo.application.modelo`, while S159 directs the domain registry authority
to implement that application contract. The accepted domain boundary forbids
`domain` importing `application`. The S128 reference simultaneously prohibits
application-side wrapping, private imports, early facade promotion, and bridge
modules, so the plan has no legal implementation path as written.

### workspace-owner-seam | high | Owner semantics and Workspace envelopes are conflated

The canonical contributors must own their native semantic projection and atomic
consistency coordinate. The application Workspace boundary must own the S126
contract, stamp, epoch envelope, and structural port realization. Treating either
layer as owner of both concerns creates a reverse dependency or a second semantic
authority. The application realization must therefore be stateless composition
metadata: exactly one native capture, no owner reread while projecting, and no
storage, cache, counter, selector, join, or semantic recomputation.

### workspace-owner-seam | high | Facade and delegation scope is missing

S159-S166 name private implementation files without consistently including the
canonical owning-package facade or the existing producer each step must delegate
to. Cross-package consumers would be forced toward private imports or premature
Workspace exports. Canonical facade promotion and the complete consumer sweep must
be atomic with each native surface; a facade is the owning package's public path,
not a non-`__init__` re-export bridge.

### workspace-owner-seam | high | Admission capture rules contradict each other

The S128 reference says static inspection reads only registry, manifest, and
locale coordinates, then says every request captures all eight contributors.
Static inspection still needs canonical work addressing but must not read secure
review, calculation, readiness, or closure state. The capture denominator must be
explicitly admission-specific while the global producer inventory remains the
fixed eight-kind set.

### workspace-owner-seam | high | Restart safety is underdeclared

An integer generation that restarts at one can collide with a baseline minted by
an earlier process. Persisting a shadow counter would create another authority,
while a payload digest or timestamp is explicitly forbidden. Native generations
must be monotonic for an owner process incarnation, and Workspace baselines and
cursors must bind an opaque application process-incarnation coordinate so every
pre-restart token refuses after restart.

### workspace-owner-seam | medium | Contributor identity fixed point is absent

S126 fixes eight contributor kinds but no governing record fixes the eight exact
owner and producer identities, native surface, or epoch scope. The field-manifest
contract currently declares `domain.calculations.registry` as owner even though
the manifest is an application-owned explanatory projection. Cardinality alone
cannot detect that semantic ownership drift.

### workspace-owner-seam | medium | Reference and audit prose displace or stale decisions

The S128 reference decides dependency and port topology rather than grounding it,
and its blocker prose conflicts with the accepted layer graph. The S126 review
still assigns later owner-port work to S128 although the plan now assigns it to
S159-S167. The Workspace ADR also describes the interface ADR as proposed even
though it is accepted.

### workspace-owner-seam | pass | Existing Workspace code is not redeclared

Semantic and exact censuses found the landed Workspace V1 definitions only in
`_workspace_models.py`, `_workspace_producers.py`, and `_workspace_manifest.py`
with their focused tests. No concrete atomic ports or Workspace assembler exist.
`ReviewOnlyWorkspace`, `ProjectionWorkspaceSummary`, and operation refresh DTOs
have distinct contracts and are not competing Workspace V1 authorities. No
deprecated reader, compatibility projection, shim, alias, fallback, or
non-`__init__` re-export bridge was found in the S125-S127 surface.

## Recommendations

Amend the accepted Workspace ADR in place to establish the two-level native
owner capture/application S126 seam; the exact contributor identity and
admission-capture fixed points; process-incarnation invalidation; and the
one-native-read/no-application-generation conformance rules. Amend S159-S167,
S128-S131, and downstream receipt rows to execute and attest that decision.

Correct the S128 reference so it records the resulting dependency map without
owning a competing decision. Update stale S126 audit wording and the accepted
interface-ADR status statement. Require every implementation step to repeat
Vaultspec RAG semantic discovery plus exact source census and to delete any
parallel implementation it finds before the step can close.
