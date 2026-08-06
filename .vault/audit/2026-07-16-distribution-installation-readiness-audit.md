---
tags:
  - '#audit'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:6be1d7ccc22b9ad04a83b4a458f7a416dca112cdc7040a201fb16ee818bf4597'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-adr]]"
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
---

# `distribution-installation-readiness` audit: `Packaging ADR reconciliation`

## Scope

Reconcile the accepted 2026-07-03 Claude ecosystem packaging decision against
the accepted 2026-07-15 distribution installation readiness decision and the
live packaging/runtime surface. The audit covers the dependency closure,
physical corpus split, missing-corpus behavior, release authority, and the
older campaign plan's stale current-tense claims.

Grounding included complete reads of both ADRs, both campaign plans, the
distribution research and reference, the older close-honesty audit, the
dependency metadata and lock, the resource boundary, corpus catalogue and CLI
refusal surfaces, companion package metadata, and the relevant execution
records. Semantic search was attempted through `vaultspec-rag`; the resident
service was occupied by a stalled index-update job and returned HTTP 500 for
search, so exact-symbol and full-document CLI/grep discovery supplied the
fallback evidence.

## Findings

### packaging-adr-reconciliation | high | Two accepted ADRs assigned opposite dependency semantics to the same companion files

The earlier D1c ruling made corpus companions optional through
`cadrumo[corpus-sources]` and treated root-only execution as a supported
advisory mode. The later accepted ADR requires both exact-version companions
for every command-bearing installation and rejects a public slim-only product.
Installed-artifact research supplies the adjudicating evidence: the root wheel
could pass a shallow manifest yet fail real work creation on an absent official
corpus file, while the complete three-wheel cohort passed the grounded Modelo
200 calculation. The later mandatory closure is therefore the current
authority.

### packaging-adr-reconciliation | high | Whole-ADR supersession would regress unrelated accepted capability

The earlier ADR also owns the Claude plugin vehicle, generated marketplace
surface, physical corpus-file split, mirrored namespace, single resource
resolution seam, and present-byte integrity enforcement. Those decisions do
not conflict with the successor and remain implemented. Marking the entire ADR
superseded would discard valid architecture and make the corpus less accurate.
The correct resolution is an explicit partial amendment: retire only dependency
optionality, supported root-only degradation, and local publication authority.

### packaging-adr-reconciliation | high | Publication authority was contradictory

The earlier ADR selected local human-gated token publication and rejected
GitHub Actions OIDC. The later ADR explicitly replaces that ruling with one
protected GitHub Actions OIDC authority that promotes an immutable tested
cohort without rebuilding. The earlier ADR and plan now point readers to that
successor instead of continuing to present local upload as current authority.

### packaging-adr-reconciliation | medium | Historical plan prose could be mistaken for current architecture

The older plan correctly records that the optional extra, root-only smoke
diagnostic, and local publish recipes were implemented in that campaign. Its
current-tense prose and fully checked live-client wave could nevertheless be
read as the active distribution contract, despite its own close-honesty audit
retaining operator-gated gaps. The plan now labels those steps as historical
execution and delegates current acceptance to the successor plan without
rewriting or deleting valid execution history.

### packaging-adr-reconciliation | low | Concurrent implementation cleanup closed the optional-mode code drift

The dependency metadata and lock already require both companions and contain
no `corpus-sources` optional group. During the initial scan, the resource
boundary, corpus-catalogue hint, split-install smoke lane, companion READMEs,
and related tests still described an optional companion and the removed extra.
Those were decision-vs-code drift against the later ADR, not evidence that the
older ruling should remain. The concurrent implementation lane retired the
stale hint/advisory product semantics while preserving exact-byte verification
and a fail-closed incomplete-install diagnostic; final exact-symbol search
found no optional companion or `corpus-sources` runtime surface.

## Recommendations

- Treat the 2026-07-15 ADR as current authority for mandatory dependency
  closure and publication; retain the 2026-07-03 ADR as accepted for its
  non-conflicting plugin, physical-split, namespace, resolution, and integrity
  decisions.
- Do not use whole-document `supersedes` metadata between these ADRs because
  the relationship is partial and the canonical edge would falsely retire
  valid architecture.
- Keep historical execution records intact. They document what landed at the
  time and should not be rewritten as if the successor implementation had
  existed earlier.
