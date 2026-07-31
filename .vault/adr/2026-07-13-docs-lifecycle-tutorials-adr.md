---
tags:
  - '#adr'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:df19819aac67086162a8aa5c0aaca44c04dd510d17f13cb240fcb062734d478f'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-research]]"
  - "[[2026-06-01-docs-educational-surface-adr]]"
---

# `docs-lifecycle-tutorials` adr: `lifecycle tutorials and the filing-year documentation IA` | (**status:** `accepted`)

This ADR amends the still-accepted 2026-06-01 docs-educational-surface ADR in
two narrow places (the singular-tutorial charter and the how-to grouping) and
leaves the rest of that ADR — the Diataxis quadrant separation, the
single-source CLI-conformance contract, the per-document production
discipline — in force. Operator approval recorded 2026-07-13.

## Problem Statement

The educational surface answers neither the questions a taxpayer actually
asks ("How do I file my Modelo 130? My Modelo 349? How do I get my expenses
and invoices in so I can calculate?") nor the shape of the work they live in
(a filing year: quarterly instalments folding into an annual close). The
survey and gap analysis in the companion research found: only 3 of the 18
guided modelos have how-to pages (036, 303, 390); the single tutorial
duplicates ~80% of the quickstart; the five explanation pages are
deliberately non-actionable and each carries only 1-3 facts a how-to lacks;
the how-to index is a flat 34-page list with no organizing principle a
taxpayer recognises; and the IVA-credit opening-balance workflow exists only
as explanation prose with no actionable home. The parent ADR chartered the
Tutorial quadrant as "a single on-rails lesson", which structurally caps the
surface below what the filing year requires.

## Considerations

- The parent ADR's Diataxis separation is correct and stays binding: how-to
  pages remain theory-free recipes, explanation remains the mechanism
  quadrant, and no surface re-authors CLI help.
- The operator's standing mandate is CONDENSE, never bloat: every document
  must end highly actionable, well-grounded, and cross-referenced; receiving
  pages tighten as they absorb extracted signal; removal, renaming, moving,
  and merging are preferred over new prose.
- A taxpayer's mental model is the filing year, on three axes: the calendar
  (what is due when), the profile (what facts drive obligations), and the
  per-modelo filings. The ledger lifecycle (import through classification,
  evidence, and invoices) is the fourth, instrumental axis feeding all
  filings.
- Every documented command must keep passing the existing documented-command
  conformance gate and the nitpicky Sphinx build gate; longer lifecycle
  tutorials multiply the cited-verb count but need no new gate mechanism —
  the gate scans commands irrespective of page length.
- Renta (Modelo 100) is the one filing where users must understand how
  values arrive (ledger aggregation, Modelo 130 fold-in via relations,
  profile facts, registry bindings, cross-period carry), so it warrants the
  one sanctioned deeper-mechanism document.

## Considered options

- **Retire the explanation quadrant and merge everything into tutorials.**
  Rejected: violates the parent ADR's core separation, and the survey showed
  the explanation pages are over-weighted, not valueless; wholesale merging
  bloats the receiving recipes with theory — the cardinal Diataxis failure.
- **Keep the singular tutorial and grow only how-to pages.** Rejected: a
  single-quarter lesson cannot demonstrate the load-bearing year-scale
  behaviours (cumulative binding carry, IVA credit carry, annual
  reconciliation against four quarters), which are exactly where users get
  lost.
- **One lifecycle tutorial per filing lifecycle, plus a filing-year how-to
  IA, plus targeted gap-fill (chosen).** Amends the parent ADR minimally,
  keeps quadrant discipline, and concentrates net page growth exactly on the
  operator-named gaps.

## Constraints

- The `vaultspec-documentation` pipeline governs every page (wireframe,
  context, draft, technical review, editorial review); documentation prose
  is authored by the coordinating session itself, with subagents restricted
  to research, grounding verification, wireframes, and read-only review.
- Every cited CLI verb is verified against the live surface at authoring
  time — never from memory, never copied from research (the annual period
  token for Modelo 100/390 in particular must be re-verified when authored).
- User-facing language stays simple, singular, imperative, taxpayer-general
  (NIF/CIF/DNI/NIE/NII), per the user-docs hardening rules.
- The registry-backed behaviours the tutorials narrate (cross-period carry,
  IVA wallet, verification gates) are stable, shipped surfaces; no frontier
  dependency.

## Implementation

**Tutorial charter (amends the parent ADR).** The Tutorial quadrant holds one
on-rails lesson per filing lifecycle. Two are chartered now: the IRPF annual
lifecycle (quarterly Modelo 130 instalments through the annual Modelo 100
close, demonstrating cumulative and cross-period carry) and the IVA lifecycle
through one year (periodic Modelo 303 with the IVA-wallet opening seed and
credit carry, an optional Modelo 349 branch for intra-community operators,
closing with the annual Modelo 390 reconciliation). A future IS lifecycle may
enroll under the same charter without another amendment. Both tutorials share
one persona and one continuous year of ledger data. The mainline of each
tutorial has no decision points; clearly-marked optional stages are
permitted. Tutorials narrate the year and link to the per-modelo how-to pages
rather than superseding them. The existing tutorial's content is absorbed as
the IRPF tutorial's first-quarter stage; the quickstart survives unchanged as
the terse single-modelo copy-paste path.

**Filing-year IA.** The how-to surface is regrouped on the taxpayer's axes:
entry points (onboarding, quickstart), Your profile, Your calendar, Your
ledger, Your filings, plus two residuals (agent connection, troubleshooting).
The page-level disposition table in the companion research (Finding 3) is
binding: 7 merges (filing-periods into filing-calendar; review-queue into
classify-transactions; the three LLM pages into one consolidated
LLM-assisted-classification page; justificante-receipts into reconcile;
read-live-aeat-data retired with its content redistributed), 3 new Tier-1
modelo pages (130, 100, 349) templated on the existing modelo-303 page, and
the extracted explanation-page facts landing tightened on their named
receiving pages.

**Renta document.** One dedicated deep-dive document joins `explanation/`,
visually labelled as a deep dive (it is command-dense, unlike its five
siblings), explaining how the Renta filing and its bindings work: annual
build-up from the year's ledger, the Modelo 130 fold-in, profile-fact
bindings, cross-period carry, and the visible-gaps-not-guessed-zeros
guarantee. It is cross-linked from the new modelo-100 how-to page and the
IRPF tutorial's annual-close stage, and is explicitly a one-off, not a
template for other modelos.

**Document conventions.** Every tutorial — and every reworked user-facing
page — opens with a one-paragraph summary of what the document covers,
phrased in the form "This page covers the ...". Explanation pages are trimmed
after their actionable signal has a confirmed home elsewhere.

## Rationale

The companion research grounded every element: the two-segment survey and
per-page extraction findings, the 18-guided-modelo gap analysis, the
live-CLI-verified lifecycle wireframes, and the full disposition table. The
chosen option is the smallest amendment that lets the documentation answer
the taxpayer's real questions in the taxpayer's real timeframe, while the
condense mandate keeps the net surface roughly constant (34 how-to pages to
~27, plus growth only at the named gaps). Making the disposition table
binding prevents the restructure from decaying into ad-hoc page churn.

## Consequences

- Gains: the docs answer the operator-named taxpayer questions directly; the
  year-scale behaviours users most misunderstand are demonstrated live; the
  duplication between the tutorial and quickstart is resolved by
  differentiation instead of deletion; the IVA-wallet workflow finally has an
  actionable home; net page count stays flat.
- Costs: the lifecycle tutorials are long documents with a large cited-verb
  surface, so conformance failures will concentrate there after any CLI
  rename; the 7 merges and the retirement each require redirect-safe link
  sweeps and a full Sphinx gate run; the disposition table's IA regrouping
  touches most of `how-to/index.md` and the landing-page route grid.
- Pathways: a third IS lifecycle tutorial can enroll without amendment;
  per-modelo pages for the deferred families (withholding, IVA special
  regimes, IS) have an authoring template (modelo-303) and a waiting axis
  (Your filings).
- Pitfalls: receiving pages bloating as they absorb explanation signal (the
  condense mandate and editorial review are the guard); tutorials drifting
  into reference by enumerating flags instead of narrating the flow (the
  parent ADR's cardinal-failure clause still applies).
