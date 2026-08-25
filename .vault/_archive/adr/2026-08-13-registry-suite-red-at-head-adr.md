---
tags:
  - '#adr'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:6f4224f2e073c600dc4254892af8ba4bf8132ebb187e15fc71d5f01fe15254f5'
related:
  - "[[2026-08-13-registry-suite-red-at-head-audit]]"
  - "[[2026-08-13-m303-compensacion-revision-split-research]]"
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

# `registry-suite-red-at-head` adr: `red suite triage is by cause, and the measurement is sequential` | (**status:** `accepted`)

## Problem Statement

The registry suite is red at HEAD and the red is being handled as a single
quantity. A count is not a defect: the authorising audit clustered its
measurement into nine root causes spanning several unrelated kinds of fault, and
the remedies for those kinds are not merely different but opposite. Worked as one
number, the surface admits three specific failures — a fixture swept to satisfy a
model that was itself wrong, a deliberately-red gate silenced along with the
noise, and a remedy declared complete because a tally moved. The plan governing
this work carries rows that are operator rulings rather than repairs, and it has
been closing rows against a self-documented missing-authority gap, so delivery
and closure currently wear the same checkbox. The decision needed now is the
classification discipline, not the repairs.

## Considerations

- Green must mean fixed, not muted: the prohibition on skips, xfail, raised
  baselines and allowlist mutes is settled in `2026-07-14-honest-all-green-adr`
  and is not re-argued here.
- Sequencing red work by blast radius rather than by count is settled in
  `2026-06-04-repo-health-triage-adr`; this record adds the classification axis
  that sequencing presumes.
- `pyproject.toml:936` sets the pytest addopts to `-n auto --dist=loadfile`, so
  an unqualified pytest run inherits xdist; the serial recipe is
  `just test-unit-serial`, which passes `-n0`. This worktree's backing share
  fails under concurrent I/O.
- The audit's own re-run demonstrated the consequence: its three-test delta over
  a prior capture fell entirely on loader-cache and snapshot-cache tests, so the
  race explained the delta and not the cluster.
- `test_revision_span_matches_published_designs.py:100` declares itself landed
  red deliberately, states the failures are the finding rather than a regression,
  and names its own remedy; weakening it to land green would, in its own words,
  delete the evidence.
- Whether a tightened model or its fixtures are at fault is decidable by
  inspection, not judgement: the question is whether a production writer supplies
  the field.
- The failure figure is disputed and no defensible number exists; see Constraints.

## Considered options

- **O1 — Work the red as one burndown against a failure count** (status quo): a
  single ordered list, complete when the number reaches zero. Rejected: it cannot
  distinguish a fixture lagging a correct tightening from a model tightened past
  what production writes, and it prices a deliberately-red gate identically to a
  broken one.
- **O2 — Classify by cause, remedy per class, and exclude by-design red
  explicitly** (chosen): each cluster is attributed to a fault kind before a
  remedy is chosen, and the by-design set is enumerated rather than swept.
- **O3 — Restore green first and reclassify afterwards**: fastest to a clean
  signal and the most dangerous, because the sweep that restores green is
  precisely the act that destroys the evidence distinguishing the classes.
  Rejected outright.
- **O4 — Defer every cluster to its owning campaign**: honest, but leaves the one
  gate watching relation source consistency firing on its own stale assumption
  indefinitely, so a real defect stays indistinguishable from the standing noise.
  Rejected.

## Constraints

- No remedy may gate on an exact failure count. A tally encodes a moment and
  detects nothing afterwards; verification is per-cause, against the authority
  that establishes the expected behaviour.
- The count is disputed and this record does not resolve it. After the 43-failure
  cluster closed, the expected residue was near 123; a peer measured 203. The
  candidates are collection-scope variance — one untracked peer test module
  exists at `src/cadrumo/entrypoints/cli/tests/test_overview_deemed_served_notices.py`
  — loader-cache races under concurrent load, and count-assertion fallout from a
  Modelo 145 casilla split. No figure in this record is offered as authoritative.
- The Modelo 145 claim cannot be settled by listing fragment directories; that
  revision is directory-mode, and coverage is assessed from the loaded snapshot.
- Four plan rows are operator rulings rather than implementations and are not
  unblocked by this record: widening or disclosing the scope of the registry
  verify verb, and the author-it-or-retire-the-claim choices on the Modelo 232
  and Modelo 720 revisions. Attributing published AEAT designs needs tax-review
  provenance.
- The AEAT-grounded oracles this work depends on are dark rather than passing, so
  no cluster may be closed on a swept fixture alone.

## Implementation

We will triage a red registry suite by cause and never by test count. A cluster is
attributed to a fault kind before any remedy is chosen, and the attribution is
recorded with the locator that establishes it.

We will treat the sequential run as the only admissible measurement. Any figure
produced without `-n0` is inadmissible for triage, because on this share the
parallel delta is a loader-cache artifact rather than a signal. A disputed count
is recorded as disputed.

We will enumerate gates that are red by design and exclude them explicitly from
every remedy scope. `test_revision_span_matches_published_designs.py` is the
current member: it names the spanning registry revisions as its own split
specification, and closing it without performing the split would produce a green
gate over a still-wrong tree — strictly worse than an honest red.

We will decide fixture-versus-model by finding the writer. Where a production
writer populates the tightened field, the fixture lagged a legitimate tightening
and the fixture is swept. Where no production writer populates it, the model was
tightened past what production produces and the model is the defect. This is
established by locating the writer, never assumed from the failure text.

Both current tightenings resolve to the fixture under that test, and the answer
was derived rather than presumed. The deduction-authority refusal on
`IvaLedgerObservation` at `_ledger_bindings.py:488` has production writers on the
classification and aggregation paths, including `_invoice_classification.py:293`
and `_iva_ledger.py:671`. The selector axes for observation role and cash
accounting treatment at `_ledger_bindings.py:522-523` are each supplied by 58
committed registry fragments.

One correction to the received clustering is carried here because it changes the
remedy scope: these are two models, not one. The category, observation-role and
cash-accounting-treatment axes are fields of the IVA ledger selector at
`_ledger_bindings.py:518-523`; only the deduction-authority refusal belongs to
`IvaLedgerObservation`. The clusters therefore cannot be a single tightening
event, and a sweep scoped to one model would leave the other red.

## Rationale

The knockout criterion is that the fixture and model remedies are opposite actions
on the same symptom. Sweeping a fixture to satisfy a model no production writer
feeds converts a live defect into asserted behaviour, which is the failure mode
the project's grounding rules exist to prevent and is far harder to find later
than the open gap. No count-ordered burndown can make that distinction, because
the distinction is not visible in the count. Only O2 forces the question to be
asked before the remedy is chosen.

The measurement mandate follows from the same audit that established the
clustering: its comparison of two full runs showed the parallel delta landing
entirely on cache-isolation tests. A parallel figure therefore carries a variable
error term of unknown size, which is disqualifying for a decision about which
clusters exist.

Excluding by-design red is not an exemption but the opposite. That gate's failure
text is the specification for the registry split it demands; the failures are the
deliverable's input, and a remedy scope that includes them invites their deletion.

The audit's largest-cluster diagnosis survived verification, and that is recorded
deliberately. Its attribution of 43 Modelo 100 failures to a single unswept
profile-binding harness gap — a test-harness fault with no production consequence
— held, and closed as authored in `c0a912da26`, which touched eight test modules
and no production code. An audit finding that survives independent re-derivation
is evidence the clustering method works, and is worth as much to a future reader
as the corrections are.

## Consequences

Triage becomes slower per cluster and sound per cluster. Attribution now precedes
remedy, which costs a writer search on every tightening-shaped failure and buys
the guarantee that a sweep never ratifies a defect.

The suite stays red longer and more visibly. With the by-design gate excluded by
name and the count refused as a completion signal, no number remains that can be
driven to zero to declare victory, and the honest position — that the engine is
not shown to compute wrong tax and, while the AEAT-grounded oracles are dark, not
shown to compute right tax either — must be stated rather than retired.

The count dispute is left open. Recording it as unresolved is the correct
disposition and also an admission that the surface is not yet measurable on
demand; until the scope variance is settled, two competent agents can measure the
same tree and disagree.

A structural finding is opened rather than closed: eighteen registry-layer test
modules carry their own Modelo 100 binding-values dictionary, one of them three
copies in a single file, and they are subsets of differing size rather than
duplicates. Consolidating them into one shared fixture would silently change what
several tests supply, so it is a deliberate refactor requiring its own decision,
not cleanup to be folded into a sweep.

This record governs classification only. It unblocks the repair rows that depend
on no ruling, and deliberately does not settle the four operator rulings or the
registry-split authoring those rows carry.
