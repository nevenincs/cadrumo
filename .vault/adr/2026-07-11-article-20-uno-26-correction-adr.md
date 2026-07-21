---
tags:
  - "#adr"
  - "#article-20-uno-26-correction"
date: '2026-07-11'
related:
  - "[[2026-07-11-cross-domain-continuity-research]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
supersedes:
  - '2026-06-03-iva-exemption-article-adr'
modified: '2026-07-11'
---
# `article-20-uno-26-correction` adr: `Remove the Article 20.Uno.26 deductible casilla-61 route` | (**status:** `accepted`)

## Problem Statement

The accepted IVA exemption-article decision correctly introduced a narrow
sub-article discriminator, but its Article 20.Uno.26 branch is materially false.
It describes artistic services as exempt with deduction, claims a Modelo 303
casilla-61 route, and causes the special member to enter the deductible-prorrata
numerator. The current registry contains no casilla 61 in either Modelo 303
revision, and no production classifier or binding requires this exception.

Article 20.Uno.26 is a domestic exempt operation. Article 94 does not grant it a
deduction right, and Article 104 therefore puts its volume in the prorrata
denominator rather than its numerator. Historical casilla 61 was removed in
2021 and did not serve this Article 20 exemption. Retaining the exception risks
overstating recoverable IVA and inventing a form surface that the registry does
not declare.

## Considerations

This is a narrow correction, not a rejection of the discriminator architecture.
The generic `DOMESTIC_EXEMPT` category already supplies the lawful present route:
the operation contributes to the exempt-without-deduction volume. Other
sub-article members remain governed by their own facts and consumers.

The Modelo 303 registry is the authority for official casillas. Its current form
sequence has 59, 60, 120, and 122, with no 61. Neither a compatibility alias nor
an inferred casilla-83 route is an acceptable substitute for an official,
effective-dated registry binding.

The correction must preserve a clear distinction between a substantive IVA
classification and a form-box claim. A sound classification does not authorize a
new reporting destination without an official source and a registry declaration.

## Considered options

1. **Keep `ART_20_UNO_26` as a full-deduction casilla-61 route.** Reject: it
   contradicts Articles 94 and 104 and refers to an absent current-form box.
2. **Keep the member but send it through the generic exempt-without-deduction
   route.** Reject: legally sound but preserves an unused special axis with no
   independent consumer or reporting meaning.
3. **Remove the member, its prose, and its special prorrata routing.** Accepted:
   the operation falls through to `DOMESTIC_EXEMPT`, the complete lawful route.
4. **Replace casilla 61 with an inferred casilla 83 or another form mapping.**
   Reject: no reviewed official instruction or registry binding supports it.

## Constraints

The correction MUST be limited to Article 20.Uno.26. It MUST retain the generic
`DOMESTIC_EXEMPT` path and MUST NOT create a casilla-61 compatibility contract,
a phantom registry binding, or a casilla-83 inference. The registry remains the
single authority for form structure.

The existing discriminator and generic domestic-exemption route are stable parent
capabilities. The false special member has no current production classifier,
binding, or official-box consumer, so the pre-release no-legacy rule permits its
removal. If a persisted value is found before implementation, it requires an
explicit reviewed data decision; it must not be silently remapped into a new tax
claim.

This accepted ADR supersedes the accepted predecessor through the ADR
supersession workflow. The supersession is confined to the Article 20.Uno.26 /
casilla-61 branch, not to the discriminator principle or its other members.

## Implementation

After acceptance, the implementation removes `ART_20_UNO_26`, its
full-deduction/casilla-61 descriptions, and the sole special-exemption set that
classifies it as `con_derecho`. A repercutido domestic-exempt operation then
uses the existing ordinary route and contributes to total and
without-deduction volume, never to the deductible numerator.

The Modelo 303 registry, export layout, and binding declarations remain
unchanged: no official casilla is added, repurposed, or inferred. Domain and
calculation evidence will demonstrate the real rollup rule with actual
`DOMESTIC_EXEMPT` observations, while retaining the category-validation and
propagation coverage that protects the remaining discriminator members.

## Rationale

The related research reconciles the consolidated IVA law, current AEAT Modelo
303 instructions, the 2021 removal history, registry revisions, and the live
prorrata route. All sources agree that the present exception is unsafe; none
supports a replacement form box. Removing a dormant, false exception is more
honest than preserving a compatibility-shaped taxonomy that can overstate a
deduction.

## Consequences

If accepted, the correction eliminates a route that could inflate deductible IVA
and restores the ordinary exemption treatment without expanding reporting scope.
It intentionally breaks any uncommitted caller that attempts to construct the
removed enum member; that exposure is preferable to silently retaining an
unlawful tax result.

The formal supersession records this narrow correction while preserving the
discriminator principle. This ADR does not authorize a new Article 20 reporting
treatment or resolve any future casilla-83 question; either would require
separate legal grounding and a registry-authored decision.
