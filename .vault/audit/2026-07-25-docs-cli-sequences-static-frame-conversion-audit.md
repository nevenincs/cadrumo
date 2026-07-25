---
tags:
  - '#audit'
  - '#docs-cli-sequences'
date: '2026-07-25'
modified: '2026-07-25'
related: []
---

# `docs-cli-sequences` audit: `static-frame conversion: what the measurements missed`

## Scope

Converting purely-local `@static` display frames in the reader-facing CLI sequence
cards into executed frames with committed goldens, across the filing finish line
(`modelo export`, `modelo work file`, and the work-state verbs). Two agents worked
the corpus in parallel: the modelo and filing share, and the ledger-verb share.

The corpus moved from 105 fully-static / 166 fully-executed / 204 static frames to
95 / 176 / 190. This record is not about that arithmetic. It is about the
measurement errors both agents made while producing it, because every one of them
produced confident, cheap-looking, wrong data, and none was caught by the agent
who made it.

## Findings

### token-keyed-duplication-instrument | medium | A clone detector keyed on token sequences cannot see one concept written in two syntaxes

Five ledger projections in the aggregation package carried the same casilla fold,
differing only in an accumulator loop versus a comprehension. The clone report
found none of the five and instead flagged the import preambles those files share.
The cluster was found by reading the concept, not by reading the report. A low
duplication percentage is evidence that little copy-paste survives; it has never
been evidence that little duplication survives.

### verb-keyed-blocker-classification | high | Whether a frame can execute is a property of the verb AND its page sandbox, not of the verb

A classification of the 204 static frames keyed on the verb would have called
`ledger participation` convertible. It is not, on the `troubleshooting` page: that
page's sandbox deliberately runs without an unlocked profile, coherently, since
its neighbouring frames teach the no-active-profile failure modes. The identical
repository-opening pattern succeeds on the `ledger-evidence` page. The decisive
evidence is cross-page, which is the only shape that isolates the page as the
variable.

### text-keyed-annotation-sweep | high | A blocker that lives in the handler is invisible to a classifier reading the invocation

The `ledger providers` frame was annotated as having no verified blocker. Its
handler calls a provider PATH scan and a live model-list HTTP probe against the
configured local-inference URL, so its output depends on which CLIs are installed
and whether a daemon is running. The invocation text carries no provider flag and
no provider token, so a classifier reading the frame had nothing to catch. Same
axis error as the preceding finding, in a different instrument.

### classifier-instruction-encodes-the-axis-error | high | A taxonomy docstring told classifiers to key on the verb name, and generated a real misclassification

The live-AEAT blocker code's docstring names "the `pull` verb family" as a
criterion. A peer followed it and reclassified a Google Drive folder-fetch frame
as an AEAT read. The CLI naming standard states that an AEAT fetch must be named
`pull`; it does not state that everything named `pull` is an AEAT fetch, so the
verb in question breaches the standard's operator-knowledge intent without
breaching its letter. A wrong classifier is one bad row. A wrong instruction to
classifiers generates them indefinitely.

### unmeasured-tree-outside-the-scanned-root | medium | Deliberate scope is not the same as deliberate blindness

The standing duplication runner scans the product tree only, which is a decision
the governing audit supports. Nothing in the recipe ever surfaced that a whole
tree went unlooked-at, so two real clone groups in the tooling tree sat unseen
until someone pointed the same runner at a different root. The scoping decision
was sound; the silence about the scope was not.

### one-measurement-is-a-rumour | high | A number from a churning tree needs a settled tree and a second run before it means anything

A page check reported eight divergences, then eleven, then eight again. The middle
reading was contaminated by a mandatory-annotation gate landing mid-run, which
turns every not-yet-annotated frame into a failure until the sweep catches up. The
first and third numbers matched, but only the third deserved the confidence the
first was reported with.

### check-keyed-on-stdout-alone | critical | A search tool's clean empty result is indistinguishable from the tool refusing to run

Two independent instances in one session. One search suppressed stderr on a
pattern using unsupported look-around: the pattern never ran, and the empty
output read as a clean negative. Another suppressed stderr on a glob addressing a
module as though it were a package: the path did not exist, the tool errored, and
the empty output again read as a finished search. In both cases the suppression
was typed reflexively, to cut noise.

### line-keyed-question-of-wrapped-data | critical | The instrument works, the question is wrong, and there is no tell at all

A search for a full sentence in a locale catalogue returned nothing because the
value wraps across lines; the phrase is present in the parsed value and absent
from every single line. Exit zero, empty output, no error. Both agents hit this,
on the same file, within an hour, and one of them hit it inside the very check
being run to verify the other's report about it.

### conversion-has-a-prose-blast-radius | high | Converting a sequence falsifies the prose that described it as a display frame

Two guides read "this example omits that evidence, so the export and the filed
marker are shown as display frames". True before the conversion commit and false
after it: the conversion attaches the evidence inline and both frames execute. The
prose described the state before the commit that changed it. The converting agent
shipped it, then found it in their own diff. Every conversion changes what the
surrounding prose is describing, and the next converter will not be looking for
that.

### docs-and-cli-disagreed-about-an-optional-step | high | Four guides presented a window-gated optional verb as the unconditional next step

The local filed-marker verb refuses outside the AEAT obligation window, and its
refusal states plainly that export is the local finish line and the marker is an
optional internal step. Four guides presented it as the step that follows
uploading, unconditionally. The disagreement was invisible while the frames were
display-only, because nothing ran to surface the refusal.

### ownership-is-not-inferable-in-a-shared-worktree | high | Every agent commits under one identity, so no git query answers "whose work is this?"

Two misattributions in one exchange, from opposite directions. One agent inferred
ownership from who was working nearby; the other nearly inferred it from which
guide the file sits in. Both heuristics are plausible and both are wrong. Had the
second acted on it, six files of a peer's in-flight annotation would have been
destroyed while "tidying up leftovers".

### least-defended-number-is-the-one-that-costs-nobody | medium | A figure whose wrongness harms no party is the figure nobody audits

Two agents who had spent a session auditing each other's measurements to the exit
code closed by exchanging a mutual-correction tally that was wrong in both
directions and inflated in favour of each. It was caught only because one of them
went back to the other's earlier message and read what it had actually said. The
structural point is not about credit: a claim that flatters both parties gives
neither an incentive to check it, so it survives scrutiny that far harder numbers
did not. Any figure whose wrongness costs nobody anything is the least-defended
number in a report, and it is worth locating deliberately rather than trusting
that rigour elsewhere generalises to it.

### claims-round-upward-in-retelling | medium | A hedged observation becomes a firm assertion across successive messages with no new evidence

Three instances from one agent in one session, each a claim getting rounder one
message after it was correctly qualified: "in someone's working tree" became
"in your working tree"; a routed item became an owned item; a self-correction
against a third party's sweep became a correction supplied by the other agent.
Nothing new arrived between the hedged and the firm version in any of the three.
The drift is invisible from inside the conversation because each restatement is
consistent with the speaker's memory of the last one rather than with the
evidence.

### review-above-the-work-launders-premise-false-errors | critical | A reviewing layer does not filter a false-premise error, it adds authority to it

The false-premise finding in this session travelled five steps through three
agents: one classifier produced a wrong diagnosis, a second agent challenged it,
the first retracted, the coordinator had by then already relayed the original
claim onward as fact, and the coordinator then issued a correction. The
coordinator read the report, found it plausible, and passed it on with more
authority than it arrived with.

That is the expected behaviour of review, not a lapse in it. Review asks whether
the reasoning is sound, and in a false-premise error the reasoning IS sound —
every observation is true and only the unstated premise is false. So a layer
above the work cannot filter this class; it launders it, converting a single
agent's plausible error into a coordinated position. The only reader who catches
it is one holding the specific domain fact, and that reader has to be looking at
the same artefact at the same time. **A second reader must sit beside the
classifier, not above it.**

### flawed-instrument-contaminated-half-the-annotation-corpus | critical | One exit-status blind spot produced ninety unverified rows before anyone noticed

The `@static` annotation sweep classified the corpus using a check carrying the
exit-status blind spot recorded above. Ninety of the 185 shipped annotations —
just under half — carry the code meaning "no verified blocker known", and the
sweep's owner has since disclosed that all ninety were produced by that
instrument rather than by a per-frame verdict, splitting them by risk and
re-deriving the roughly two dozen where a wrong answer is dangerous. The row
count is verified here; the attribution is the owner's own disclosure.

This is the concrete cost of the earlier findings and the reason they are graded
critical rather than noted. A blind spot in a one-off check wastes minutes. The
same blind spot inside an instrument that sweeps a whole corpus produces a
plausible, uniformly-formatted, machine-readable body of claims that reads as
evidence, and every consumer downstream inherits it. The ratchet that counts that
code would have driven agents at ninety rows, of which an unknown number cannot
be retired.

## Recommendations

Treat a measurement's key as the first thing to audit, before its result. Each
finding above has the same shape: the instrument was keyed on a proxy that
underdetermines the property being measured, and it returned a clean answer to
the wrong question. Asking what the instrument cannot see is cheaper than
re-running it.

Separate the failure kinds, because only one is gateable. A search that did not
run leaves a non-zero exit and a diagnostic line, so it is catchable and the
discipline is never to redirect the diagnostic channel of a check whose result
will be believed. A search that ran and answered a different question leaves
nothing, and a search resting on a false premise about the codebase leaves less
than nothing. The first is defeated by hygiene, the second by repeating the
search along a different route, and the third only by a second reader who happens
to hold the domain fact.

Make the second reader a standing control rather than a courtesy, and place them
beside the classifier rather than above. Across every finding above, the rescue
was a second look by a different route or a second person, never care, never
confidence, and never the instrument. Two agents classifying the same set from
different starting points corrected four errors neither would have found alone,
in both directions. Escalating to a reviewer does not substitute: a
false-premise error passes review intact, because review checks the reasoning and
the reasoning holds. Size dispatches so that no corpus-wide classification is
produced by a single agent, and treat a sole classifier's output as a hypothesis
carrying an undetected error rate rather than as findings.

For structured data, parse it rather than searching its text. A line-oriented
query of wrapped YAML or TOML returns a confident zero. On a registry surface
that zero could underpin a much more expensive wrong conclusion than a missing
locale string, such as concluding that a casilla carries no binding or that a
legal reference is absent.

Pair every sequence conversion with a read of the prose around it. The prose
frequently describes the frame's execution status explicitly, and the conversion
falsifies it. Verify a converted frame proves what the page claims rather than
merely that it runs.

For uncommitted work you did not personally write, route rather than edit, and
name the owner you believe it is so the assumption can be checked. A blocker
whose fix requires editing a file a peer is demonstrably inside has no safe
mechanical escape when the change builds on a symbol that does not exist at
`HEAD`.

An annotation vocabulary needs a code for every verified blocker before the
sweep hardens around it. Two blockers in this corpus fit none of the shipped
codes, and the code meaning "no blocker known, awaiting conversion" feeds a debt
ratchet that drives to zero. Filing a verified blocker there guarantees repeated
rediscovery, which is the cost the annotation exists to prevent. Leaving those
frames unannotated and loudly failing was the correct interim.
