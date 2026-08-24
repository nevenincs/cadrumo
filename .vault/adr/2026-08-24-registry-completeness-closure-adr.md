---
tags:
  - '#adr'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:329a030596d6cd6292e3c39808fe38f1761e58cfdfd1ca564f89702e95386b61'
related:
  - '[[2026-08-24-registry-completeness-closure-research]]'
---
# `registry-completeness-closure` adr: `one derived release predicate for shipped registry completeness` | (**status:** `accepted`)

## Problem Statement

The existing temporal-coverage, source-casilla-integration, and export-fragment authorities each govern a necessary part of a filing-capable revision, but none alone authorizes a whole-registry completeness claim. Define one derived release predicate without creating a fourth implementation campaign. Grounding: `2026-08-24-registry-completeness-closure-research`.

## Considerations

- Authority grade and schema-family coverage govern what a revision may claim; source connectivity governs whether applicable taxpayer facts reach casillas; export authority governs whether a filing-grade revision can emit faithful bytes.
- A revision may be registered and useful below filing grade without trustworthy evidence to support filing emission.
- Unsupported or untrusted historical evidence must produce an actionable, reviewable refusal, never a guessed layout, an invented mapping, or a silent narrowing of the claimed corpus.
- Plan checkboxes, execution records, tests, and implementation can diverge; a broad implementation commit is not completion evidence by itself.

## Considered options

- Treat temporal coverage as registry completeness. Rejected: it cannot prove source connectivity or faithful export.
- Treat export capability as registry completeness. Rejected: it can certify bytes for values whose source path is incomplete or ungrounded.
- Create a separate closure implementation plan. Rejected: it duplicates the three approved campaigns' ownership.
- Adopt one derived predicate over the three existing authorities. Chosen: it makes the release claim testable while preserving each campaign's implementation ownership.

## Constraints

The predicate must inspect validated, law-selected snapshots and derived campaign evidence, not raw fragments, filesystem presence, similarity between designs, or hand-maintained modelo lists. It must remain fail-closed for absent, stale, unreviewed, conflicting, or scope-inadequate official evidence. Parent authority-grade, export-fragment, and source-casilla mechanisms remain stable only within their declared contracts; a change to one contract requires re-evaluation of this roll-up.

## Implementation

A release may claim **shipped registry completeness** only when every law-selectable registered revision satisfies this conjunction:

1. Its loaded coverage manifest satisfies its declared authority-grade ladder and its temporal window is supported by the evidence declared for that revision.
2. Every applicable source-to-casilla candidate has a current, evidence-backed terminal disposition under the source-casilla authority: connected, manual-by-design, not-applicable, duplicate-or-stale, or a bounded blocked disposition with an owner, review condition, and follow-up. No unclassified, expired, silently deferred, or unsupported connected claim remains.
3. A revision declaring filing grade has an exact-authority export semantic map, reviewed render profile, generated export fragments, and emitted-byte proof. A revision below filing grade is not represented as filing-capable.

The temporal-coverage plan remains the owner of grade, family coverage, revision horizons, and the final derived coverage matrix. The export-fragment plan remains the owner of official design interpretation, semantic maps, render profiles, generated trees, and byte proof. The source-casilla plan remains the owner of connectivity census, resolver enrollment, provenance, and source disposition. This ADR adds no parallel steps, migrators, inventory, or writer.

A revision lacking trustworthy or sufficiently scoped evidence must remain explicitly refused at its claimed capability boundary. Its refusal must expose the revision identity, affected capability, evidence deficiency or conflict, authoritative evidence provenance where available, responsible campaign disposition, and the condition for reconsideration. It must not acquire a filing layout, source mapping, expanded temporal window, or elevated grade until the relevant authority independently validates it.

Release reconciliation produces one derived cross-authority closure report from loaded snapshots and the three campaigns' owned evidence. For each revision, it records the three predicate limbs, any refusal, responsible existing plan step, execution evidence, and independent gate result. Implementation-versus-plan drift is resolved before the claim: independently verify the live behavior, then either correct the implementation or reconcile the owning plan's structural state and execution record. A commit hash, passing focused test, or unchecked plan row alone cannot satisfy reconciliation.

## Rationale

The derived conjunction is the only choice that prevents any one denominator from concealing another authority's gap while retaining one authoritative implementation home per concern. It preserves supported non-filing revisions honestly, prevents fabricated legal wire semantics, and turns evidence gaps into visible, bounded work rather than an implicit promise. The research establishes that existing campaigns already own the required layers and that current execution-record drift needs explicit reconciliation: `2026-08-24-registry-completeness-closure-research`.

## Consequences

A completeness claim becomes narrower, repeatable, and auditable: it means all three release conditions hold for every law-selectable registered revision. A missing or untrusted design, mapping, or coverage basis blocks the corresponding capability visibly rather than allowing partial filing support to appear complete. Campaign owners retain their existing plans, but release management must reconcile their evidence into the derived report and cannot close work by inference from code alone.
