---
tags:
  - '#plan'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-02'
modified: '2026-07-08'
tier: L2
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-07-02-arch-remediation-lazy-import-policy-adr]]'
  - '[[2026-07-06-arch-remediation-lazy-import-policy-research]]'
---
# `arch-remediation-lazy-import-policy` plan

### Phase `P01` - allowlist declaration and classifier gate

Land the typed allowlist declaration and the classifier gate that structurally recognises the five sanctioned classes and fails an unclassified site naming the site and the five classes.

- [x] `P01.S01` - Declare the typed lazy-import allowlist entry model carrying site, sanctioned class, reason, and restructuring disposition co-located with the gate; `src/aeat/tests/test_lazy_import_policy.py`.
- [x] `P01.S02` - Implement the classifier gate that walks production modules, collects function-local first-party imports, and structurally recognises the five sanctioned classes: core resource-repository loaders, PEP 562 CLI cold-start deferrals, TYPE_CHECKING blocks, optional third-party dependency guards, and adapter heavy-import deferrals; `src/aeat/tests/test_lazy_import_policy.py`.
- [x] `P01.S03` - Make an unclassified site outside the allowlist fail the gate with the site path and the five sanctioned classes named in the message; `src/aeat/tests/test_lazy_import_policy.py`.

### Phase `P02` - baseline classification sweep

Populate the allowlist for every current unsanctioned function-local import site with its class, reason, and restructuring disposition, taking the baseline after ports-inversion domains land so the ratchet only tightens.

- [x] `P02.S04` - Sweep every current unsanctioned function-local import site and record each in the allowlist with its class, reason, and restructuring disposition, entering the error-registry deferred-bind queue and named cycle-breakers with their existing ADR citations; `src/aeat/tests/test_lazy_import_policy.py`.
- [x] `P02.S05` - Add the allowlist-length and per-class count ratchet so an increase requires editing the declaration in the same commit while a decrease is free; `src/aeat/tests/test_lazy_import_policy.py`.

### Phase `P03` - runtime-graph swarm-audit axis

Add the grimp runtime-graph pass to the standing swarm-audit axes as a documented audit-brief axis so hidden coupling is re-measured on the same cadence as the other structural audits.

- [x] `P03.S06` - Add the grimp runtime-graph pass as a documented axis in the swarm-audit cadence rule at its vaultspec source and run vaultspec-core sync, so the executed import graph is re-measured on the standing structural-audit rhythm; `.vaultspec/rules/aeat-swarm-audit-cadence.md`.

## Description

This plan implements the lazy-import-policy ADR, discharging deferral register
item D7. The architecture review measured ~815 function-local relative imports in
production and found the idiom spans very different intents: ADR-sanctioned core
resource loaders and CLI cold-start deferrals at one end, and first-party
module-cycle breaks plus the domain-to-adapters runtime softening at the other,
where a cycle fixed by deferring an import is hidden rather than removed and the
static graph the layered contracts audit systematically understates coupling.

Phase P01 lands the typed allowlist declaration and the classifier gate: the gate
walks production modules, collects function-local first-party imports, and
structurally recognises the five sanctioned classes (core resource-repository
loaders, PEP 562 CLI cold-start deferrals, TYPE_CHECKING blocks, optional
third-party dependency guards, adapter heavy-import deferrals); an unclassified
site outside the allowlist fails with the site path and the five classes named.
Phase P02 populates the allowlist for every current unsanctioned site with its
class, reason, and restructuring disposition, and adds the length and per-class
count ratchet. Phase P03 adds the grimp runtime-graph pass to the standing
swarm-audit cadence as a documented audit-brief axis, so hidden coupling is
re-measured on the same rhythm as the other structural audits.

The ADR inherits its sanctioned classes from four accepted ADRs and the
core-authority protect list rather than re-litigating them; the only new content
is that crossing the line now requires a declared, reviewable allowlist entry.
Critically, the gate must not fight the ports-inversion campaign: its baseline is
re-taken after each ports-inversion domain migration lands, so the ratchet only
ever tightens.

## Steps

## Parallelization

The phases are ordered. P01 lands the declaration and gate before P02 can
populate the allowlist against it. P02 has a scheduling dependency on the
ports-inversion campaign rather than on this plan's own phases: its baseline is
re-taken after each ports-inversion domain lands, so P02 is intentionally the
last-tightened phase and should not freeze a baseline while that campaign is
mid-flight. P03 (the swarm-audit axis) is independent of P01 and P02 and can land
at any point, since it edits the cadence rule at its vaultspec source rather than
the gate. This is a single-owner plan against one new test module plus one
vaultspec rule source; it does not touch the contended orchestrator files.

## Verification

- `test_lazy_import_policy.py` classifies every production function-local
  first-party import against the five sanctioned classes and the declared
  allowlist, and fails an unclassified site with the site path and the five
  classes named (P01.S03).
- Every current unsanctioned site is recorded in the allowlist with class,
  reason, and disposition (P02.S04), and the length plus per-class count ratchet
  rejects an unaccompanied increase (P02.S05).
- The grimp runtime-graph pass is a documented axis in the swarm-audit cadence
  rule at its vaultspec source, propagated by `vaultspec-core sync` (P03.S06).
- The plan is complete when every Step is closed and each Step carries an exec
  record per the plan-closure discipline.
