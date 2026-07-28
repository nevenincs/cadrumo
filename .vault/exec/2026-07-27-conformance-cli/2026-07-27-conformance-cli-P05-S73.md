---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S73'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
  - '[[2026-07-07-prorrata-especial-adr]]'
  - '[[2026-07-08-iva-prorrata-complexity-adr]]'
  - '[[2026-07-05-cross-period-prorrata-adr]]'
---

# author a decision record governing the IVA prorrata corrections this campaign made and list it on the plan, since eleven steps changed computed tax outcomes under an ADR that authorises only a governance surface

## Scope

- `.vault/adr`

## Description

- Read the eleven prorrata Step records and confirmed the campaign ADR
  authorises no change to computed tax.
- Scaffolded a standalone record for the cluster, then swept every accepted ADR
  mentioning prorrata or rounding before writing further, and found the territory
  already governed.
- Rejected the standalone record at birth and retired it as an honest routing
  tombstone rather than deleting it.
- Amended the record that owns the mandatory-especial gate with the two-redaction
  and year-aware ruling and its rejected alternatives.
- Corrected the sibling record whose stated boundary constraint the correction
  had made factually false.
- Amended the cross-period record whose two recorded premises the registry
  satisfied on one revision only.
- Repointed the campaign plan at the three governing decisions.

## Outcome

The Step's premise holds and its prescription did not. Eleven Steps changed the
M303 prorrata chain under a campaign ADR whose decision is a governance CLI, fact
lifts, a provenance stamp and a one-way boundary. But the corrective the row
names, one new record governing the cluster, was wrong, and finding out why was
the work.

A standalone record was scaffolded first, then abandoned on evidence. A sweep of
every accepted ADR mentioning prorrata or rounding returned a dense family: the
substrate placement record, the cross-period model, the prorrata-especial record,
an especial emit-audience record, and three sibling art. 104 and art. 105 records.
Between them they already govern every cluster the eleven Steps touched. Writing a
parallel record would have produced sibling accepted markers over one decision,
which is the failure the amend-versus-supersede discipline exists to prevent, and
it would have had to restate their content to be readable.

The mandatory-especial correction belongs to the prorrata-especial record, not to
the substrate-placement record. That record names the gate, the predicate and the
constant driving it in its own problem statement, states in its constraints that
the multiple stays that single constant, and decides in D3 when the advisory
fires. That is exactly what the correction changed. The substrate record decides
where prorrata lives and that it is not usage ratios, and says nothing about any
provision's reading, so amending it would have moved a rule-content ruling into a
placement decision and buried it under a CLI-redesign feature, which is the same
filing failure one level over. The amendment is filed as a new option block beside
the existing ones, carrying the two redactions, the cutover, the year-resolved
rule, and the two alternatives the law-invariance check disproved.

A second record was carrying a claim the correction had falsified. The
emit-audience record's constraints pinned the gate as firing on
strictly-greater-than with exactly the margin treated as silent, and even noted
the divergence from the statute's own wording while explicitly deferring the
reading to the substrate. After the correction that constraint no longer described
HEAD, so an accepted record was stating a false fact about live behaviour. It now
records the closure and routes to the owning ruling. Its own decision is
untouched, because it consumes whatever boundary the substrate owns.

The rounding and no-volume corrections turned out not to be new decisions at all.
The cross-period record's survey of HEAD states that the substrate computes with
ceiling rounding and that the M303 registry defaults to full deduction when no
volumes are declared. Both are premises its carry model rests on, and both were
only partly true: the registry rounded half-up while the substrate rounded up, and
the full-deduction default held on the newer revision only. So the two corrections
made an accepted record's premises true rather than deciding anything new. They
are filed as an amendment to that record, which is where a later reader relying on
those premises will look.

Two candidate amendments were considered and refused. The substrate-placement
record is unchanged because nothing it decides moved. The formula-engine authority
already carries the invariant that rounding is explicit registry and runtime
policy, and the choice to extend the rounding vocabulary rather than redefine a
shared code follows from that invariant plus the existing no-legacy and
single-aggregation-path rules, so it needed no new invariant; adding one would
have been decoration.

The retired record is a tombstone rather than a deletion. It carries the routing
table naming which record owns each cluster and why a parallel record was refused,
so the next agent reaching for the same shape finds the answer instead of nothing.
Its status is rejected, because the decisions themselves are accepted in other
records.

The plan now declares the real governing decisions. Its related frontmatter lost
the edge to the retired record and gained the three amended ones. Every write went
through an owning verb, and the plan body was diffed against a copy taken
immediately before each write and confirmed byte-identical both times; the file
carried uncommitted peer changes throughout and they were left untouched.

Verification. All three amended records still read status accepted and none was
superseded. The retired record reads status rejected. The vault check reports
structure, frontmatter, modified-stamp, links, dangling, body-links, placeholders,
orphans, references, adr-status, rename-integrity and encoding all clean; the
schema check's single remaining error is a peer's unrelated ADR, and the
grounding-reference error this Step's first attempt introduced is gone.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
semantic index is broken and the service is stopped, so it was neither started,
restarted, reindexed nor probed. Grounding was ripgrep over the decision corpus
plus whole-file reads of seven accepted records and the eleven Step records.

This Step made the error it was opened to correct, and caught it only after the
coordinator challenged the record. The first pass read the campaign ADR, judged
the territory ungoverned, and scaffolded a parallel record without sweeping the
decision corpus for existing owners, which is the same missing discovery pass that
let eleven Steps land under a tooling ADR. The correction also overturned the
coordinator's own expectation: the mandatory-especial gate is owned by the
prorrata-especial record rather than the substrate-placement record it named, and
two of the three clusters were not new decisions at all. The cheap guard is the
one that was skipped twice: sweep the accepted corpus by provision and by symbol
before concluding a decision has no home.

The record retired here is the only artefact left from the first pass. Nothing was
executed under it and no document depends on it.
