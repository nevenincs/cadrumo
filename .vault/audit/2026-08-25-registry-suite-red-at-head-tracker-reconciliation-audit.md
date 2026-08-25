---
tags:
  - '#audit'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6676cc23f90253f69aae52596ae7860fff80fe02c4d17e5492c754877305da86'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-suite-red-at-head with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `registry-suite-red-at-head` audit: `Registry red tracker reconciliation`

## Scope

Reconcile the nine unchecked rows against current production authority, later
campaign decisions, current tests, and execution evidence. The audit distinguishes
delivered work from superseded tracker debt and from remaining implementation.

## Findings

### superseded-rows | medium | Three old repair rows now contradict or duplicate later canonical campaigns

`P02.S09` was delivered by the canonical-identifiers campaign, which retired the
parallel Justificante CSV alias and made `AeatCsv` canonical. No local fixture
population remains. `P03.S12` names the obsolete empty `export_layouts` directory;
the design-relayout campaign published both Modelo 232 trees through the newer
five-fragment `export` shape. `P03.S14` requests historical Modelo 303 revisions
that the later reachable-filing-window decision deliberately refuses. These rows
were retired, never checked as work performed by this plan.

### delivered-rows | low | Three current authorities satisfy the surviving row intent

`P02.S07`'s old fixture population no longer exists. Every surviving
`_IvaLedgerSelector` construction declares the cash-accounting and observation-role
axes, and the refusal probes remain explicit. `P03.S15` is satisfied by the
grounded Modelo 720 authority whose 2013 design explicitly covers ejercicio 2012.
`P03.S16` is satisfied by the non-null English help text at both current M303
standard-rate projections. Each requires focused verification and execution
evidence before checking.

### implementation-residue | medium | Three rows remain genuine work

`P02.S08` still has M100 harnesses hand-authoring the maternidad binding instead of
using production derivation. `P02.S10` still lacks the exact 2024 2T-negative to
3T-compensacion end-to-end regression. `P03.S13` still has the guarded Modelo 390
position-1628 disclosure-split question. These are not tracker drift.

### live-suite-rebaseline | high | The old row inventory was not the current closure surface

A sequential registry run on 2026-08-25 completed 5,628 selected tests with 37
failures and 5,591 passes. Every failed node was then rerun alone because concurrent
registry writes can invalidate the loader's tree fingerprint. Seven passed alone and
were classified as contention noise; thirty reproduced. The reproducing set includes
the claimed-year layout-design divergence, temporal holes, filing-grade and export
capability residue, continuity enrollment, parser coverage, stale synthetic fixtures
and scenario declarations, public-boundary imports, validator reviewability, and
verdict-cache behavior.

The stale Modelo 390 diagnosis is independently resolved, but that does not make the
campaign complete. `P03.S22` owns the exact fourteen-revision layout-design gate and
routes its changes to existing authorities. `P03.S23` owns draining the remaining
isolated clusters without duplicating those authorities. Campaign closure still
requires the isolated nodes and a fresh sequential whole-tree run to pass.

### non-executable-rows | medium | Two checked findings were not plan work

`P03.S19` and `P03.S20` described adjudication findings and explicitly stated that
nothing was implemented. Keeping them checked would require fictional execution
records and make findings indistinguishable from delivered changes. Both identifiers
are retired through the plan CLI. Their durable content remains in the audit history;
any future implementation must be enrolled under the owning production campaign.

## Recommendations

- Retire S09, S12, and S14 through the canonical plan CLI and preserve the
  supersession evidence here.
- Rewrite S07 to the surviving selector census, run focused tests, and close it
  only with a completed execution record.
- Reconstruct focused evidence for S15 and S16, then close them through the plan
  CLI.
- Implement S08, S10, and S13 in that order without reviving superseded shapes.
- Treat the isolated 2026-08-25 failure set, not the historical checkbox count, as
  the live closure baseline and re-run it after every cluster lands.
