---
tags:
  - '#audit'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:06b697c4a1928a0990580cbe987c86799f4e3e5ecdd7fdc8c1a9594d1369677d'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
  - "[[2026-07-27-conformance-cli-adr]]"
---

# `conformance-cli` audit: `campaign-close honesty review`

## Scope

The mandatory fresh-context campaign-close honesty review, run by an independent
reviewer briefed to inherit the campaign rather than summarise it, and to treat
the closure narrative as a claim to be tested. Verified against a moving HEAD;
four campaign commits landed during the review and every finding was re-verified
at the final one.

Verification actually run by the reviewer: all four verbs against the real
registry including both JSON surfaces, a seeded-baseline gate reproduction, an
eight-probe laundering battery against the stamp writer over byte copies of a
shipped modelo tree, the full-tree collect gate, the stub drift check, the four
campaign-owned source gates, the filing suite, the dev CLI suite, and the quality
and import-hygiene gates. The measurement audit's figures were re-derived
independently rather than read.

Verdict: REVISION REQUIRED. No critical safety violation. Five high findings, of
which one reds the per-push CI lane and one is a tax-modelling gap the campaign
identified and then lost track of.

## Findings

### operator-name-committed-in-tracked-source | high | The campaign committed a real person's name eight times and left the per-push lane red

The conformance CLI test module carried the operator's real name as a fixture
constant and at seven further assertion sites, introduced by this campaign's own
commit and propagated by four later ones. The privacy gate that catches it is
marked unit and sits in the per-push CI selection rather than the dispatch-only
lane, so the default lane was red at HEAD.

The gate triage record claimed this campaign's half of the tree-wide gates was
clear, naming only a docs-sequences marker as the residual. That claim was wrong,
and the violation was owner-caused and present when it was written.

REMEDIATED. The constant was renamed away from the operator noun on the reasoning
that a constant named after the operator is what invited the operator's name into
it, and every assertion using it stamps an agent-tier review, so the name was
already a misnomer. The replacement is person-shaped rather than a token, because
what the surface defends against is a human name rendering identically under both
tiers. The fix also collapsed five hand-copied attribution literals into one
derivation, closing a latent defect where a seed rewrite would have left all five
checking a stale value and all five still passing.

### campaign-plan-cited-in-delivered-test-source | high | Tracked source referenced this project's own development records

Two dev test modules cited plan and exec documents in their docstrings, and one
carried a discovery-waiver process note. The code-stands-alone boundary names
tests explicitly and rules the reference direction one-way: vault documents cite
code by locator, code never cites the vault. A test whose docstring justifies its
own shape by quoting a plan becomes unreadable the moment the removable
scaffolding is removed.

REMEDIATED, and the sweep found two citations the finding had not enumerated,
including a bare plan step identifier standing as an entire test's subject line.
The durable engineering reasons were kept and restated self-contained; the
scaffolding references and the process note were removed rather than reworded.

### m303-regularizacion-casilla-lost-in-tracking | high | A genuine under-declaration-shape gap was attributed to a Step that does different work and never landed

An earlier audit identified the M303 regularización prorrata cuota casilla as a
computable value left to operator entry with a bundled AEAT figure beside it that
no gate consumes, and recorded it as tracked by a named Step. That Step was later
re-scoped to the rounding correction and the audit reference was never updated, so
no Step covered the casilla. At HEAD it is still declared as a manual input with
no formula.

Compounding it, a closed Step's own row text conditioned it on that modelling
having landed. It closed with the precondition unmet and no record acknowledged
it. Now tracked as its own Step, and both misstating records corrected.

### iva-tax-changes-filed-under-a-tooling-decision | high | Eleven Steps changed computed tax outcomes under an ADR that authorises only a governance surface

Eleven of the Steps added after the original plan changed IVA prorrata behaviour:
the percentage rounding, the zero-volume branch of the older revision, the
mandatory-regime predicate, and the supporting grounding and parity work. The plan
listed one governing ADR, whose Implementation authorises a governance CLI, fact
lifts, a provenance stamp and a boundary gate, and no change to computation. A
future reviewer searching the decision corpus for what changed prorrata rounding
would have found nothing.

REMEDIATED, and the remediation overturned both the finding's framing and the
coordinator's correction of it. A sweep of the decision corpus found seven prior
records touching this territory, not none and not one. The predicate correction
belongs to an accepted prorrata-especial record whose own Problem Statement names
the function and pins the multiple as a constant; it landed there as a new
decision rather than as a new document. More seriously, two accepted records were
found stating falsehoods about live behaviour: one pinned in its Constraints that
the predicate fires on strictly-greater-than while flagging the statute's contrary
wording as deferred, and another's carry model rested on premises that the
substrate rounds upward and the registry defaults to full deduction on zero
volumes, both only partly true. So the rounding and zero-volume corrections were
not new decisions at all; they made accepted records' premises true, and were
filed as amendments accordingly.

### capability-facts-are-a-second-authority | high | A per-revision capability fold duplicates an existing matrix CLI predicate for predicate

The conformance composer independently recomputes export-format and extractor
predicates that an existing dev matrix CLI already computes from the same bare
string literals, with the composer a strict superset in coverage. This is the same
silently-forked-authority shape the campaign identified for the boundary detector
and resolved by consolidating onto one authority; the same answer was available
here and was missed.

REMEDIATED as a ruling. The investigation found a third site the finding had not
named, and that every field of the dev row is already returned by a public
builder the dev module's own cross-reference block cites. The package is retired
rather than made to delegate, because delegation would close four of ten fields
and leave the latest-revision selection — the axis the matrix is keyed on —
forked. The residue is diagnosed as a type gap rather than a second authority:
what forces both sites to re-spell the format tokens is that the export-format
closed set is a bare literal rather than a core enum. Both consequences are
tracked as Steps.

### ratchet-reds-on-ordinary-registry-growth | medium | An honest new revision fails the only gate, and clearing it requires asserting the ratchet is being weakened

Three governance ceilings are pinned at the full population, so a peer landing a
ninety-first revision takes all three past their ceilings. Re-recording is then
refused without the flag whose documented purpose is to mark a deliberately
suspicious capture, so an honest population increase and a deliberate weakening
are conflated. This matters most immediately for the stamping campaign the
measurement audit schedules, which will move these counters continuously.

### the-only-gate-runs-only-in-a-dispatch-only-lane | medium | The gating verb is never exercised on a push or a pull request

The gate module is honest about this in its own docstring and the wiring matches,
but the governing record states that a dev-side wrapper runs the check in CI,
which is literally true and practically misleading. The realistic failure mode is
that the gate first runs weeks later on a manual dispatch and reds for reasons
unrelated to whoever dispatched it. Defensible given the run cost, but it should
be a stated posture rather than a wiring detail a reader reconstructs.

### the-tool-has-no-operator-documentation | medium | A governance CLI other contributors must use is documented only in module docstrings

No page under the documentation tree mentions the tool. The only discoverable
surface is a task-runner recipe naming two of its four verbs. The stamping
campaign, which the measurement audit calls the campaign's most actionable
output, has no written procedure: nothing states the accepted status vocabulary,
that operator signoff requires a hand edit, that a registry-root flag exists, or
how to re-record the baseline afterwards. The prose exists and is unusually good;
it needs a reachable home.

### measurement-audit-recommendations-are-untracked | medium | The campaign's most actionable output has no owner

The measurement audit makes four recommendations and none is a Step, a follow-up
feature, or a named deferral. The campaign-close rule requires every surfaced item
to be tracked or formally deferred with a reference. As written, ninety unreviewed
revisions and twenty-four classification divergences are recorded in a document
and owned by nobody.

### coverage-was-never-reconciled-against-the-research | medium | A plan verification bullet was never performed and nothing records that

The plan required the coverage verb to reconcile with the research counts axis by
axis. No record performs it. It is not a formality: the research counts are
per-modelo and the verb reports per-revision, so the two are not comparable
without an explicit mapping, and the axes that are directly comparable do
reconcile, which makes the un-reconciled ones look checked when they are not.

### bare-operator-noun-is-still-a-writable-reviewer | medium | The one residual laundering vector on an otherwise well-defended writer

The tier-shape refusal catches a status-prefixed reviewer in every casing and
spacing tried, but the bare operator noun is not a status value and passes — and
that noun is exactly the convention the legal catalogue already uses to mean a
human signoff. The status field stays honest and the gate cannot be moved by it,
so this is narrow; the writer survived every other probe constructed against it.

### shipped-fields-with-no-reader | low | The campaign created its own instance of the defect class it measures

Two capability fields on the composer are computed, exported, and read by nothing.
The report's own doctrine is that a surface nothing declares cannot fail and
rendering that as clean is lying by omission; the same argument applies to a field
nothing reads.

## Recommendations

Fix the privacy red first, before anything else. Done.

Rule the two authority questions rather than leaving them archaeological: the
capability duplication and the governing decision for the tax corrections. Both
done, and both turned out larger than the findings stated.

Track what the measurement audit scheduled, so the unreviewed backlog, the
classification divergences, the unused axes and the regularización gap have
owners rather than prose.

Reconsider the population-pinned ceilings before the stamping campaign runs, since
that campaign moves them on every commit and meets the conflation immediately.

Correct the records that misstate their own state. Done.

## The growth from twenty-four Steps to seventy-eight

The reviewer's judgement, recorded because it is the assessment the campaign
cannot make about itself: honest discovery, but unflattering in a different way
than sprawl.

Roughly fifty-five per cent of the added Steps are remediation of the campaign's
own new code across four review rounds. Each closed a real hole and none is
padding, but twenty-three rounds of repair on about fifteen hundred lines of new
dev code — with each review round finding a fresh way through the same writer,
from annotation-only narrowing to re-attribution of an existing signoff to date
inheritance to a guard reading the wrong source — says those verbs landed
under-specified and were hardened by iteration rather than designed.

About a quarter are tax-correctness defects the tool surfaced, and these are the
campaign's strongest justification: a rounding that contradicted the binding
provision and a zero-volume branch that would have zeroed a fully-taxable trader's
deduction both sat inside the ninety-five per cent that nothing independently
checks, and the tool found them by making that fraction visible. There is no
evidence of work generated to justify the campaign; every late Step names a
concrete defect with a reproduction. The Step count is nonetheless a poor proxy
for what this feature cost, because two Steps cleared another campaign's debt
under an operator directive.

## Honest judgement

Not structurally complete at the time of review, and closer than the open-Step
count suggested. The tool works, its numbers reproduce, and the stamp writer
withstands attack. What was missing was not implementation but closure: a
committed privacy violation, two unresolved authority questions, and four pieces
of surfaced work existing only as prose.

The reviewer's shortest honest path was five items, none of them re-work and all
of them filing — which it noted is the correct shape for a campaign whose subject
is provenance, and a slightly pointed one.
