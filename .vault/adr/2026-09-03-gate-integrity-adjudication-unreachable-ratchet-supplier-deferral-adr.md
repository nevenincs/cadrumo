---
tags:
  - '#adr'
  - '#gate-integrity-adjudication'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:7a01911c816b5092f71a7df239fe8fbd1c7aa4c95ab77b5063fc0a7c8b79e7ce'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
  - "[[2026-09-02-cli-distribution-consolidation-adr]]"
  - "[[2026-09-02-tui-architecture-out-of-process-destination-protocol-adr]]"
  - "[[2026-09-02-gate-integrity-adjudication-tui-entrypoint-contracts-adr]]"
  - "[[2026-07-06-arch-remediation-gates-ratchet-adr]]"
  - '[[2026-09-02-gate-integrity-adjudication-research]]'
---
# `gate-integrity-adjudication` adr: `a frozen cluster's exclusive suppliers inherit its deferral` | (**status:** `accepted`)

## Problem Statement

The unreachable-module ratchet is the last failing static gate. It reports four shipped
application modules that no declared entrypoint reaches: `cadrumo.application.aeat_sync`,
`cadrumo.application.ledger.workspace`, `cadrumo.application.modelo.declarations_calendar`
and `cadrumo.application.modelo.declarations_workspace`. The gate names two remedies in
its own failure message -- relocate harness code beside its consumer, or delete capability
that lost its caller -- and neither is true of these four. Each is new capability whose
consumer is being built and has not been wired yet, and each is consumed exclusively from
inside `cadrumo.entrypoints.tui`, a cluster the same baseline has already declared outside
this gate's scope.

The collision is between two accepted decisions. The console-script consolidation leaves
one declared entrypoint, and the out-of-process destination protocol forbids any import
edge from it into the TUI, so an import-graph walk from the declared script can never
reach the TUI by design. The baseline absorbs that consequence for the TUI package itself
with a frozen prefix. It cannot absorb it for the application-layer projections those
screens consume, because the dependency direction requires the projections to live outside
the entrypoint package. The ratchet has no vocabulary for the intersection, and a gate
must not be left asserting a remedy that does not apply.

## Considerations

- The scanner is correct and no import edge is missing: nothing in the tree reaches these
  modules. `build_destination_catalogue` in `src/cadrumo/entrypoints/tui/navigation.py` has
  no production caller, and route factories are injected rather than imported, so the
  closed catalogue is genuinely unwired.
- `2026-09-02-gate-integrity-adjudication-tui-entrypoint-contracts-adr` establishes that a
  contract is not relaxed because a violation appeared; the same discipline binds a
  baseline.
- `2026-08-11-tui-architecture-adr` D11 and
  `2026-09-02-unreachable-capability-tui-navigation-join-adr` both forbid a CLI-to-TUI
  import edge, and both contracts are currently kept.
- `2026-09-02-cli-distribution-consolidation-adr` settles the single declared console
  script; reintroducing a TUI script to satisfy a gate would invert that decision.
- The frozen prefix's stated reason is churn in both directions under independent
  ownership. That reason holds identically for the projections, which move in lockstep
  with the screens that consume them.
- `2026-07-06-arch-remediation-gates-ratchet-adr` establishes the ratchet as an identity
  set compared in both directions, so any deferral must itself be visible and must force
  the baseline to shrink when it takes an entry over.
- A stale pin carrying an untrue rationale previously concealed 82 layered import
  violations in this repository, so a declared reason that can rot is itself a risk.

## Considered options

- **Add the four modules to the `allowed` backlog.** Rejected: the backlog's documented
  remedies are relocation and deletion, and neither applies, so each line would attach a
  false remedy. It would also need editing in both directions on every step of the TUI's
  construction -- exactly the churn the freeze exists to absorb.
- **Declare each module `[[intentional]]`.** Rejected: the closed kind is
  `design_time_authority`, whose meaning is a module that deliberately has no runtime
  caller. These modules want a runtime caller and will get one, so the claim would be
  false. Inventing an in-flight kind would encode a temporal assertion the gate cannot
  verify and nobody would return to remove.
- **Widen the frozen prefixes to cover the application layer.** Rejected: a prefix broad
  enough to include the projections would blind the gate to genuine application-layer debt
  it currently catches, and a prefix per module is the `allowed` list under another name.
- **Teach the scanner to treat these as reached.** Rejected: it would be a false
  reachability claim. No edge is missing; the modules really are unreached.
- **Give the TUI a declared console script again.** Rejected: it contradicts the accepted
  consolidation and would make packaging follow a gate rather than the product.
- **Make the existing deferral transitive over exclusive suppliers.** Chosen.

## Constraints

- The deferral must be derived from the live import graph, never declared, so it cannot go
  stale or carry a rationale that stopped being true.
- It must be anchored on a declared frozen prefix. A closure keyed on unreachability alone
  would exempt the entire backlog, since an unreached module's importers are themselves
  unreached.
- A module no shipped module imports must stay actionable. That is the
  lost-its-last-caller case the gate exists to catch, and an empty importer set must never
  read as no importer outside the cluster.
- A module with even one importer outside the deferred set must stay actionable.
- Every deferral must be reported with the importers that carry it, so an abandoned
  cluster leaves its suppliers named in the gate's own output rather than silent.
- A baseline entry the deferral takes over must be reported stale, so no module sits in
  the actionable list and the deferred set at once.

## Implementation

The scan gains one fact and the gate gains one disposition. The layering is that the
scanner reports and the ratchet adjudicates.

`dev/audit/unreachable_code.py` now records, on each module finding, the shipped modules
outside that finding's own span which still import it. Both runtime and type-checking
edges count, because the question is whether anything shipped still names the module.
Members of a collapsed package finding importing each other are internal traffic and are
excluded, or every multi-module finding would report a non-empty importer set and the
distinction the field exists to draw would vanish. The reach categories are unchanged:
these modules remain factual unreachable output.

`dev/quality/unreachable_module_ratchet.py` grows the deferral to a fixpoint over
exclusive suppliers. A finding whose every importer is frozen, or is itself deferred this
way, is deferred too; a finding with no importers, or with any importer outside that set,
stays actionable. The fixpoint rather than a single pass is what carries a supplier of a
supplier, which is as exclusively consumed by the deferred cluster as the first hop is.
Deferrals are carried in their own verdict channel, rendered with the importers that defer
them, and excluded from both failure directions. The stale message now says either the
debt was paid or only a deferred cluster still leads there, because asserting a repair
that did not happen was the previous wording's error.

The baseline records the consequence: six entries the closure now covers leave the
actionable list, and the header states that consumption by a frozen cluster is not a
reason to add a line.

## Rationale

The knockout is that the reported finding had no honest remedy. Its only resolution is to
finish wiring the deferred cluster, which is precisely the work the freeze declares this
gate does not adjudicate. A gate that defers a consumer while still failing on that
consumer's exclusive supplier is not measuring a boundary: the deferral leaks its
consequences into the adjudicated scope, and the leak is structural rather than incidental
because the dependency direction forces the two halves of one cluster into two locations.
Freezing by location can therefore never describe the cluster, which is why widening the
prefix fails on capability as well as on principle.

Deriving the closure from the graph is what separates it from every rejected option. Each
alternative that passes the gate does so because someone wrote a sentence -- a backlog
line, an intentional rationale, a prefix -- and a written sentence can become untrue while
the gate keeps passing. The exclusive-supplier property is recomputed on every run and
reported with its evidence, so it fails loudly instead: the moment a non-frozen importer
appears, or the last importer disappears, the module returns to the actionable set on its
own.

## Consequences

Ten modules are now deferred by derivation, rather than four failing while six sat in the
backlog with a reach category standing in for a remedy. The gate reaches a clean exit
without any module being baselined away, and the TUI's construction no longer requires a
baseline edit at each step.

The honest cost is that ten application-layer modules are no longer adjudicated by this
gate while the cluster is deferred. If the TUI navigation join is abandoned, they become
orphaned capability this gate reports as deferred rather than as debt. The mitigation is
visibility rather than adjudication: each is named with its deferring importers in the
gate's output, and retiring the frozen prefix returns all of them to the actionable set in
one move.

A second cost is that the deferral is inferred, so a reader consults the report rather
than a list to learn what is deferred and why. That is the deliberate trade against a
declared exemption that can rot.

The mechanism generalizes to any cluster the baseline freezes in future, which is both a
gain and a risk: a broad or careless frozen prefix now defers more than its own subtree.
The two teeth bound it -- no importers at all, or any importer outside the deferred set,
keeps a module red -- and both are exercised against a planted tree in the same suite as
the positive path.
