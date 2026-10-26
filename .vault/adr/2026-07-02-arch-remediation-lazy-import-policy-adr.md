---
tags:
  - '#adr'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:c891ecb595ff44797466130631555a8242fc8d0326ae0575d0edd96ad60f73c7'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-06-03-user-profile-lazy-import-adr]]"
  - "[[2026-07-02-arch-remediation-ports-inversion-adr]]"
  - '[[2026-07-06-arch-remediation-lazy-import-policy-research]]'
---
# `arch-remediation-lazy-import-policy` adr: `function-local import policy: sanctioned classes, allowlist, ratchet` | (**status:** `accepted`)

## Problem Statement

The architecture review (finding fanout-lazy-import-soft-graph, register D7)
measured ~815 function-local relative imports in production against 160
`TYPE_CHECKING` blocks - several hundred genuine runtime-deferred imports.
The idiom spans very different intents: ADR-sanctioned lazy resource loaders
in core, ADR-sanctioned CLI cold-start deferrals, optional-dependency
guards, heavy-import deferrals in adapters - and, at the problematic end,
first-party module-cycle breaks and the domain-to-adapters runtime softening
that boundary-audit D4 introduced. The consequence is architectural: the
import graph the layered contracts audit is the import-TIME graph, while
the runtime graph is materially denser; a cycle "fixed" by deferring an
import is hidden, not removed. No policy separates the sanctioned classes
from the erosion; this ADR draws that line.

## Considerations

- Two accepted ADRs (user-profile lazy import and its cli-errors successor)
  ratified PEP 562 package-boundary laziness for the CLI cold-start budget;
  the resource-management ADR ratified the core loader deferral; the
  core-authority ADR's protect list already names specific cycle-breakers
  as accepted sites. Policy must inherit these, not re-litigate them.
- The ports-inversion campaign (accepted) deletes the largest unsanctioned
  population (the domain-repository substrate imports) as a side effect;
  the policy gate should ride on that reduction, not race it.
- A raw count is a weak instrument: the classes matter. The gate must
  classify sites, not just count them.
- Restructuring a genuine cycle is sometimes a real design task; the policy
  needs an honest holding state (a declared, reasoned allowlist entry), not
  a mute button.

## Considered options

- **Option A: no policy** - treat lazy imports as style. Rejected: the
  audit showed the gates' layering conclusions systematically understate
  coupling because of exactly this idiom.
- **Option B: ban function-local imports outside TYPE_CHECKING.** Rejected:
  it would revert four accepted ADRs and the cold-start budget.
- **Option C (chosen): a closed taxonomy of sanctioned classes + a declared
  allowlist for everything else + a count-ratchet + a periodic
  runtime-graph audit.**

## Constraints

- Sanctioned classes (inherited from accepted decisions, not new): (1) the
  core resource-repository deferred loaders; (2) CLI cold-start / PEP 562
  package-boundary deferrals; (3) `TYPE_CHECKING` blocks; (4) optional
  third-party dependency guards; (5) heavy third-party imports deferred
  inside adapter methods for startup cost. Everything else - notably
  first-party cycle-breaks and cross-layer softening - is UNSANCTIONED and
  requires an allowlist entry carrying the site, the class, the reason, and
  the restructuring disposition.
- The gate must not fight the ports-inversion campaign: its baseline is
  taken AFTER each domain migration lands (the ratchet only ever tightens).
- Zero new laziness in the unsanctioned classes: a new first-party
  cycle-break fails the gate unless its allowlist entry is added in the
  same change - making the erosion a reviewed decision.
- The error-registry deferred-bind queue and similar bootstrap machinery
  are accepted sites; they enter the allowlist with their existing ADR
  citations, not as new decisions.

## Implementation

One inventory gate and one cadence hook. The gate walks production modules,
collects function-local first-party imports, classifies each against the
sanctioned taxonomy (recognisable structurally: core resource repos, PEP 562
`__getattr__` bodies, `TYPE_CHECKING`, guarded optional imports, adapter
heavy-import sites) and against the declared allowlist for the remainder;
an unclassified site fails with the site path and the five classes named.
The allowlist is a typed declaration (site, class, reason, disposition)
co-located with the gate; its length and the per-class counts ratchet -
increases require editing the declaration in the same commit, decreases are
free. The cadence hook adds a runtime-graph pass (grimp over the executed
import graph) to the standing swarm-audit axes, so hidden coupling gets
re-measured on the same rhythm as the other structural audits.

## Rationale

The policy formalises a line the vault has already drawn four times in
accepted ADRs and once in the protect list - the new content is only that
crossing the line now requires a declared, reviewable entry instead of
being free. Deferral-as-data over comment-sanctioning is the same move the
program ADR mandates everywhere else, applied to the import idiom.

## Consequences

- The static-vs-runtime graph gap becomes measured and bounded instead of
  open-ended; layering claims regain honesty.
- Genuine cycles surface as allowlist entries with dispositions - a
  standing worklist instead of invisible debt.
- The gate is heuristic at the classification margins; a misclassified
  site costs an allowlist entry with a reason, which is the correct
  failure mode (visible, cheap, reviewable).
- Mild authoring friction on new lazy imports in unsanctioned classes -
  intended.
