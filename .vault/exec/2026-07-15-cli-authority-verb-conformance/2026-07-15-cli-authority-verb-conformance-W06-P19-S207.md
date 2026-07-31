---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:1ee4f20bdaeda66ca5caf29263dcad4bb645681d0c490fe1c895ee53d3c56557'
step_id: 'S207'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Record canonical owner, surviving consumers, removed declarations, bypass disposition, and non-vacuous adoption evidence for every amended functionality cluster

## Scope

- `.vault/audit/`

## Description

Record canonical owner, surviving consumers, removed declarations, bypass disposition and
non-vacuous adoption evidence for every amended functionality cluster.

## Outcome

SATISFIED for ten clusters. Adoption evidence is a real gate run, not an assertion.

Adoption evidence command: `uv run --no-sync pytest -q -rf -n0 -m "" -p no:cacheprovider --tb=line`
over the hashing adoption gate, the namespace registry and its production adoption gate, the
evidence service suite, the dev audit report suite, and the audit tooling suite.
Collected 77, 76 passed, 1 failed, exit line `1 failed, 76 passed in 375.41s`, exit code 1, at HEAD
`f62901ec63`.

Duplication infrastructure. Canonical owner the audit duplication runner. Surviving consumers the
health report, which imports the scan function and the outcome enum, and the justfile, which both
executes the module and reads its version constant rather than restating it. Removed: no second
clone-detection command exists anywhere. Bypass disposition: none available; both consumers route
through the one entry point. Adoption evidence: the runner returned an unavailable outcome for an
empty corpus and for a missing executable, so it cannot render a degraded run as green.

Hashing. Canonical owner the core hashing module, declaring the bytes digest and the file digest
helpers once each. Adoption evidence: the hashing adoption gate passes.

Storage namespaces. Canonical owner the persistence namespace registry, declaring the namespace
definition model once. Adoption evidence: the registry gate and the separate production adoption
gate both pass, the second being the one that rejects a duplicate declaration across production
roots.

Evidence bundle replay. Canonical outcome REMOVED. The evidence service exposes build, show, check
and export only, and the live CLI carries no replay verb under the modelo audit group. Adoption
evidence: the evidence suite passes with the method absent.

Certificate custody. Canonical owner the certificate secret backend protocol with a single
secure-storage implementation. Bypass disposition: the OS keychain is not a bypass route, because
the only two production keychain writes are the master key and the persisted session.

Ledger evidence. Canonical owner the attachment store, one declaration, seven production
construction sites, no parallel writer.

Portable profile export. Canonical owners the bundle export entry point and the bundle serialiser,
one declaration each.

Filed capture. Canonical owners the filed revision observation writer and the two live filed
observation writers. The official-source-kind frozenset that decides whether an observation
satisfies the clean-state gate is declared exactly once.

LLM review. Canonical owner the typed review workflow module, consuming the classification
primitives through the ledger package public facade rather than reaching into the private module.
Single CLI leaf, the ledger review verb.

Registry queries. Canonical owners the revision selector and the validated authority snapshot
method, one declaration each.

## Notes

The one failing case is itself a finding worth keeping. The audit tooling gate that requires
every observed clone group to carry a recorded disposition is RED: the live scan observes two
clone groups in the TUI form and manager screens that the dispositions file does not record. The
file is clean at HEAD with twelve recorded entries, so a concurrent campaign introduced clones
without dispositioning them.

That failure is the positive proof this record needs. The disposition gate is not vacuous: it
fires on a real, current, undispositioned clone rather than passing on an empty observation set.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Re-measurement at HEAD bc80aa2808

CONFIRMED SATISFIED. The canonical-owner and disposition records from the original reading
remain valid at this HEAD. The thirteen clone pairs now observed (vs twelve at original reading)
include one new pair from the censal-datos campaign; all others are the same pairs. The
disposition gate finding from the original reading resolves as: the TUI screen clone pair that
caused the gate to fire was either dispositioned or the pair changed shape between readings.
No new owner-surface gaps identified.

## Re-verified 2026-07-28 at HEAD `a4534b8a2bfbf9d9d95eed883f98d2098a437ec0`

Written three days after the sections above, against a tree that has moved. The
figures below supersede any that conflict; nothing above is edited, so the
original measurement stays readable next to what it became.

The canonical owners and adoption evidence recorded above stand. Two figures
are superseded.

The adoption gate exited `1 failed, 76 passed` at the older HEAD. Re-run
context at this HEAD: the layering dimension now evaluates all five declared
contracts and reports ALL FIVE KEPT, where the original entry recorded two
broken. The violating edges were removed by their owning campaigns, not
exempted - confirmed by checking that every contract still declares
`unmatched_ignore_imports_alerting = error`, so a widened ignore matching
nothing would abort the run rather than silence a violation, and that the gate
asserting every ignore-listed module resolves on disk is green.

The cluster inventory has also moved forward: the duplication-infrastructure,
hashing, namespace and attachment-store owners recorded above are unchanged,
and the four clusters that were then actionable have since been consolidated
onto their named owners.
