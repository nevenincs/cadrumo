---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:099270176a975d2ce7b9d6c3a1bc4cc970b28722e19f93bb5c159732f988ea43'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S227 Modelo 220 source deferral review`

## Scope

Independent review of `d7a3b5e471`, the M220 research/exec/plan tracking,
pinned 2024/2025 AEAT designs, and the M220/M200/M222/manual/export/source
surfaces.

## Findings

### research-decision-redeclaration | high | the ingress-blocked decision is authored outside an ADR

The S227 research adds a `## Decision` section that declares the M220 candidate
`ingress-blocked`, assigns an owner, and defines its reopening predicate.  The
accepted source-connectivity ADR governs the closed vocabulary but does not
make this M220-specific decision; research may ground alternatives, not decide.
The plan is checked on that unaccepted decision.  Amend the accepted ADR with
explicit approval, or create/accept a narrowly scoped ADR from this research,
then move the decision/reopening predicate there and retain factual evidence
only in research before closing S227.

### primary-evidence-and-boundary | pass

The recorded AEAT 2024 hash
`a8f398dd42db0b1142d5f2e98bf3a60d79069e31d63af32001373f459fee4f2e` and
2025 hash `69c3a234e96eb4485a31c65209348bbcede0a49a8c143223c952000784f3f2df`
are distinct official design artefacts.  The evidence correctly preserves
composite group/member grain and absent/inapplicable/zero distinctions; it
makes no secure-owner, source, resolver, binding, layout, export, or census
claim.  Manual/direct M220, Modelo 200 relationships, M222 identity, and
export coordinates are correctly excluded as acquisition/lifecycle proof.

## Recommendations

Do not approve S227 yet.  First obtain an accepted ADR decision for the
M220-specific ingress-blocked disposition and reopening predicate, then reopen
plan closure for independent review.  Preserve the existing no-runtime/no-
census boundary.
