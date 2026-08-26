---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:9a412a54bcbd8711580435a281a40002d40890ea856fd44f795422977576d37e'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `S101 M182 terminal deferral review`

## Scope

Independent current-head review of the mixed S101 implementation and tracking
commits `5ccbc15a69`, `a8377a6d0f`, `474f7fe37e`, `da8ad39cb3`, and
`3aefd321ea`. The review covers the canonical Modelo 182 census disposition,
the existing donor carrier and source mesh, the official 2025 type-1/type-2
evidence, the closure projection, execution record, and plan state.

## Findings

### S101 M182 terminal deferral review | medium | The reviewed census locator had drifted from the canonical donor dispatch

The Modelo 182 row entry still named the refund dispatch, while live source
discovery resolves `row_assembler:per_donativo_donor` at the donor dispatch.
The stale locator made the Modelo 182-specific capability proof and the
tree-wide census comparison fail closed. This review corrects both the
capability and grounding locators and adds a direct Modelo 182 locator check
with a stale-locator mutation bite. No source resolver, binding, persistence
route, connected claim, or export layout is introduced by the correction.

No other critical, high, medium, or low finding remains. The actual current
carrier is still the pre-existing deferred donor worksheet path: it is not
owned by a live mesh resolver, is excluded from connected proof fixtures,
produces the standing unhandled-source diagnostic, and the applicability-grade
2025 snapshot has no export layouts. The S100 evidence remains accurately
carried: the official 2025 design distinguishes type-1 declarant controls and
type-2 declared-person records, including nature-3 administrator/holder fields
and non-lossy record cardinality. S101 preserves, rather than replaces, real
manual and direct input surfaces.

## Recommendations

Approve S101 after the corrected focused test and Modelo 182-specific locator
proof pass. Keep S102 and S103 open: only accepted secure type-1 and type-2
carriers with durable identity/fingerprint and the required lifecycle and
repeated-record export proof may reconsider the current `ingress_blocked`
disposition. The tree-wide comparison remains separately refused by the
out-of-scope `inventory.stock-valuation` locator drift; that row's owner must
repair and revalidate it independently.
