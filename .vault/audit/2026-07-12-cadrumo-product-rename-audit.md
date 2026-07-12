---
tags:
  - '#audit'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-12-cadrumo-product-rename-adr]]"
---

# `cadrumo-product-rename` audit: `Cadrumo rename rolling formal review`

## Scope

Formal review of Phase `W01.P01` against the accepted Cadrumo research, ADR,
approved L4 plan, audit template, and execution records `S01` through `S04`.
The review tested safety, intent alignment, classification completeness,
evidence quality, cross-record consistency, and plan compliance. It reviewed
classification and execution evidence only; no production implementation was
in scope.

The phase correctly preserved the product-versus-authority distinction, kept
the hard-cut/no-migration policy explicit, treated external availability as a
non-reserving signal, and isolated Step commits in a heavily shared worktree.
All four planned Step records exist and all four Phase checkboxes are closed.

## Findings

### exec-template-hygiene | low | Completed S01-S03 records retain scaffold annotations

The first three completed Step records still contain the three instructional
HTML comment blocks emitted by the execution template. Their substantive bodies
are complete and the comments do not alter the decisions, but retaining
generator instructions in settled evidence produces avoidable vault-check noise
and makes completed records appear unfinished. `S04` correctly removed the same
annotations.

### diagnostic-dump-identity | high | S02 and S03 assign opposite owners to the wallet diagnostic setting

`S02` classifies `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR` as product-owned and requires
the rename to `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`. `S03` classifies the
corresponding `aeat_wallet_diagnostic_dump_dir` setting as authority-owned and
requires retaining the AEAT name because it captures the authority's cartera
surface. These outcomes are mutually exclusive. Both records present themselves
as complete classification authorities, so downstream configuration and
persistence Steps cannot implement the phase deterministically without choosing
one and contradicting the other. The accepted ADR's referent rule does not itself
resolve the conflict: the payload is authority-derived, while the setting controls
product-selected local custody. The phase therefore has one unresolved ambiguous
public setting despite `S02` reporting zero ambiguity.

### critical-findings | critical | No critical finding identified

No evidence shows destructive worktree handling, secret disclosure, external
reservation or publication, legal-corpus mutation, compatibility-shim approval,
or another critical safety or intent failure in `W01.P01`.

## Recommendations

1. Keep later configuration and persistence implementation blocked on the wallet diagnostic setting until the principal engineer records one referent decision. Prefer classifying the environment variable by what it controls: if it chooses Cadrumo's local output custody, rename the control to `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` while retaining AEAT terminology in the captured payload and description. If authority identity is intended to govern the setting name, explicitly amend `S02` and its zero-ambiguity count instead.
2. Add a review gate that compares overlapping environment-variable and persistence matrices before `W02.P04`, so every setting named in both records has one disposition.
3. Remove scaffold annotations from completed `S01` through `S03` records in a separately owned documentation-hygiene change; do not mix that cleanup into this review commit.
4. Preserve the existing release blockers from `S04`: availability observations are not reservations, and Spanish/EU trademark clearance remains outstanding.
5. Do not treat `W01.P01` as contradiction-free until the high-severity finding is resolved, even though its four administrative plan checkboxes are closed.
