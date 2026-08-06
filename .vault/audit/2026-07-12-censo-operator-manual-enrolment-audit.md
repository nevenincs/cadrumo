---
tags:
  - '#audit'
  - '#censo-operator-manual-enrolment'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:c226a21ece01acf5c9a6494bb192b223f7b21c09dd1871f14d538e7d79a55f9c'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

# `censo-operator-manual-enrolment` audit: `operator-manual migration residual audit`

## Scope

Reconcile the still-open operator-manual Censo plan rows after the accepted
retirement decision. The review used `vaultspec-rag` and targeted source/doc
searches to compare the current product surface with the active operator
guidance. No source, locale, or user-documentation content was changed in this
pass.

## Findings

### stale-operator-guidance | medium | Shipped how-to and agent guidance still instructs the retired CLI family

The current `docs/how-to/censo-update.md`, `docs/how-to/read-live-aeat-data.md`,
and `src/aeat/_data/agent/skills/inicio-actividad/SKILL.md` still direct users
to `config profile censo pull`, `compare`, or `apply`. Current source says the
opposite: `src/aeat/application/user_profile/_censo_sync.py` records that the
live scrape and command family are retired, and that `config profile edit` is
the operator-declared, non-official replacement. This is the concrete residual
for `P02.S05`; it must be corrected through the required documentation
workflow, not by treating the removal as fully complete.

### shared-locale-wip | info | The Censo locale subtree is staged shared work and cannot be safely claimed here

`src/aeat/locales/en.yml` is already staged in the shared worktree. The current
plan's locale-related cleanup therefore remains owned by that in-flight change;
this reconciliation does not alter, overwrite, or take credit for it.

### gate-battery-boundary | info | Full-plan gate closure remains correctly open

The existing `P03.S10` exec proves the retirement-surface collection and
conformance checks, while recording unrelated locale and apidocs scaffold drift
as owner-distinguished. The remaining `P02.S03`, `P02.S07`, and `P03.S10` rows
must stay open until their documentation/rule propagation and full gate scope
are independently clean. No row is checked by this audit.

### guidance-rescan-update | info | The documentation residual has narrowed to one authentication guide

A fresh post-audit scan finds the earlier Censo how-to, live-read guide, and
activity-start skill now route to `config profile edit` and no longer name the
retired command family. The prior broader list reflects shared-worktree state
at the time of the first scan and is superseded by this update. The remaining
current wording is in `docs/how-to/authenticate-with-aeat.md`, which still says
authentication supports pulling Modelo 036 census information. `P02.S05`
therefore remains genuinely open, but its scope is now one guide rather than a
three-surface rewrite.

## Recommendations

- Start the documentation workflow for the three stale guidance surfaces and
  rewrite them onto `config profile edit` with the non-official evidence
  disclosure.
- Superseding the broad recommendation above, start the documentation workflow
  for `docs/how-to/authenticate-with-aeat.md` only; remove the retired Modelo
  036 pull claim and retain the operator-declared evidence disclosure.
- Let the owner of the staged locale change complete and verify that work before
  reconciling the locale portion of the plan.
- Re-run the complete P03 gate battery only after the shared locale/apidocs
  drift and the remaining P02 documentation/rule work are resolved.
