---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:bc359578d7ba06e989c51d82024c763e78b128b7d9d640c5faa376473f286b2b'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S226 Modelo 187 source-owner decision review`

## Scope

Independent review of `56e6dc2859`, the M187 research and accepted ADR, the
canonical legal and source catalogues, the M187 registry, source mesh, census,
binding and export surfaces.  The review recomputes the primary artefact
digests and checks that the decision does not promote a manual or temporal
surface into a source carrier.

## Findings

### research-boundary-and-template | medium | corrected

The committed research stated that it authorised no binding, resolver, export,
or census promotion, which is decision language reserved to the ADR, and it
retained empty scaffold headings.  The review rewrote it as factual grounding:
the Article 42 limb is independent; type 1 and type 2 are different record
grains; and the present codebase has no identified M187 carrier.  The accepted
ADR remains the sole decision record.

### primary-authority-and-grain | pass

The BOE Article-2 amendment remains `BOE-A-2018-17997`; the locally recomputed
SHA-256 of its bundled text is
`e5cda1824bc7f1e81cde77f366d076d395805143b0c15822cb4e9a7c1fefa21e`.
The BOE layout hash is
`0802029baafd09385fa160fb7927cec14755238157ef1f13f2131f042b8ef231`,
matching `boe-modelo-187-form-layout`.  The AEAT 2022 record-design hash is
`c7a21c1feb9619380bb0da3e73066fa3c58c628f430bf85ed9dbea15b1308eb1`,
matching `aeat-dr-187-2022`.  The design identifies type 1 as the declarant
record and type 2 as the operation record, which repeats declarant identity
before its operation/declared-party/IIC fields.  Neither is safely substituted
for the other.

### deferral-boundary | pass

The Article 42 person/entity limb is explicitly unresolved by the current
single withholding-payer selector.  Exact repository searches find no M187
source-mesh resolver, source-connectivity census candidate, binding, or
source-owned export route.  The four registry summary casillas remain manual
operator entry; they are not represented as source capture, durable identity,
provenance, secure persistence, replay, review, or connectivity evidence.
The ADR therefore makes no unsupported source, resolver, binding, export, or
census claim and preserves the real manual/direct path.

### adr-status-and-single-home | pass

`2026-08-25-source-casilla-integration-m187-source-owner-deferral-adr` is the
single accepted M187 source-owner decision and links the grounding research.
It does not conflict with the earlier registry decision that keeps Article 42
unresolved, and it does not redeclare an authority already owned elsewhere.
S226's execution record accurately reports a documentation-only evidence and
decision step.  Its plan checkbox remains a plan-owner operation outside this
independent review rather than an assertion that this audit has changed plan
state.

## Recommendations

Accept S226 as the bounded source-owner deferral decision only: preserve
direct/manual M187 entry and do not add a census disposition, canonical source,
binding, resolver, collision policy, or source-owned export until a separately
grounded and accepted, non-lossy carrier supplies both record grains and the
Article 42 identity.
