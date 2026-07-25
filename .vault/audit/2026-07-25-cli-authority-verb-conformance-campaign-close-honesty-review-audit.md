---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
---

# `cli-authority-verb-conformance` audit: `Campaign-close honesty review`

## Scope

Fresh-context close review of the CLI authority verb conformance campaign,
run as Wave W06 before any completion is declared. The review covers three
questions: whether the five operator-facing surfaces the conformance gates do
not scan still carry removed verb spellings; whether the audit instruments
this campaign relies on can still discriminate a real failure from a green
result; and whether the plan's own completion state matches the evidence on
disk.

Written to be read by someone who was not present. Every claim below names
the command that produced it. Where a claim could not be established, it is
recorded as unverified rather than clean.

Two standing conditions constrain this wave and are stated once here rather
than repeated per finding. First, the semantic code index was truncated
throughout while reporting itself healthy — roughly 1027 chunks against
roughly 4546 files, with an empty degraded-reasons list — so a semantic miss
carried no evidential weight and absence was established by reading and exact
search only. Second, custody cases carrying the keychain marker fail with
`WinError 1312` under an agent logon; that is the network logon, not a code
defect, and those cases have never been observed green in any lane. Nothing
in this review verified them, and the closure must not imply otherwise.

## Findings

### write-guard-fail-open | critical | Every invoice mutation had fallen outside the profile-bound write guard

The runtime write-policy catalogue `PROFILE_BOUND_WRITE_VERB_PATHS` still named
`app ledger payable-invoice add|update|remove` and
`app ledger collectible-invoice add|update|remove`. Those two families had been
collapsed into a single `invoice` family discriminated by `--kind`, so the live
verbs are `app ledger invoice add|update|remove`. The guard matches by prefix,
so the stale entries matched nothing at all.

Proven behaviourally, not by reading: `inspect_storage_write_policy` answered
`app ledger invoice add` with `allowed=True` and
`code=non_profile_bound_verb`, meaning the call never reached route
classification and the root write guard could not refuse it under either the
root-fallback or explicit-database route. This is a fail-open, and it is the
exact failure mode the campaign's own CLI-standard rule predicts for a verb
rename that is not hand-swept through this surface. The stale spellings entered
with the package-root relocation and therefore predate this campaign; the
campaign's own step to update these tokens had not been executed.

Fixed at commit `5eaf4b0ee6`: the six dead entries replaced by the three live
mutating leaves. Read verbs (`list`, `view`) were deliberately left outside the
guard, so a bare `app ledger invoice` prefix was not used.

### write-guard-parity-gate-vacuous | high | The only gate over that catalogue cannot detect either drift direction

The catalogue has exactly two consumers: the policy module itself and
`test_write_policy_mutability_parity.py`. That test collects catalogue entries
whose command family classifies read-only and asserts the set is empty. It
cannot see the defect above, because `command_classification` returns
`read_only=False` for a command key that does not exist at all — verified by
passing the literal key `totally.bogus.key` and observing
`read_only=False, destructive=False`. A dead catalogue entry is therefore
indistinguishable from a live write verb at that gate, which stayed green
across the entire period the guard was failing open.

The same permissive default also classifies `ledger.invoice.list` and
`ledger.invoice.view` as not-read-only, so that gate's discrimination is weaker
than its name suggests wherever a key is absent from the risk table.

Closed at commit `5eaf4b0ee6` by binding the catalogue to the materialised live
command tree, with an anti-tautology proof asserting that the pre-collapse
spellings are rejected and the live ones accepted. Without that proof the new
gate would carry no more information than the one it supplements.

### lazy-tree-walk-blindness | high | The command tree yields one leaf unless its lazy registry is drained

The CLI registers heavy subtrees lazily. Walking the app with
`typer.main.get_command` and recursing over `.commands` returns exactly **one**
leaf and completes without error. Any whole-tree conformance assertion written
that way passes while blind to the entire surface it claims to check.

The tree must be materialised through the shipped lazy-subcommand materialiser
and then walked through click's `list_commands`/`get_command`, because the
group class is not an `isinstance` of `click.Group` and an isinstance-gated
walk silently terminates. Correctly materialised, the tree is **289 leaf paths
with zero duplicates** at commit `82a04ead90`.

This is recorded as a finding rather than a note because it is a live
false-green vector for any future gate: the naive walk fails silently and
looks identical to a clean result. The gate added at `5eaf4b0ee6` asserts a
minimum leaf count for exactly this reason.

### surface-sweep-clean | medium | The five unscanned surfaces are clean, after two stale citations were corrected

All five surfaces the conformance gates do not scan were swept by extracting
every delimited command token and classifying it against the 289-leaf live
tree. The instrument was proven to discriminate before its output was trusted:
it parses delimited tokens correctly and classifies a known-removed spelling as
dead, a live leaf as live, and a live group as a group.

Token counts examined per surface: write-policy catalogue 65, error-registry
default suggestions 210, cross-period next-action builders 227, curated
operator help 81, envelope command identifiers 180. After the corrections
below, dead tokens are zero on every surface, with three residual hits
individually triaged as non-defects: a log message that begins with a command
noun, a documented deliberate retention of a stable machine token across an
operator-facing rename, and an explicit negative reference naming a retired
path as retired.

Two genuine stale citations were found and fixed at commit `f939f3b473`: a
module docstring advertising `config history` where the live verb is
`config profile history`, and one advertising `app modelo verify` where the
live verb is `app modelo work verify`. Both render into the generated API
reference, so both were live dead instructions.

### surface-corpus-by-filename | medium | A filename-shaped corpus produced a false clean on the error-registry surface

The first pass over the error-registry surface selected its corpus by filename
pattern and reported zero dead tokens from 25 tokens examined. That result was
false: the registry entries live in files named for their layer, not for
errors, and the pattern matched none of them. Selecting the corpus by the data
— every production file actually carrying a default suggestion — raised the
corpus to 10 files and 209 tokens.

The corrected result is genuinely clean, but the first one was indistinguishable
from it without checking the corpus size. This is recorded because the campaign
relies on several by-hand sweeps, and a sweep that reports zero findings over
the wrong corpus is the cheapest possible way to close a step dishonestly.

### duplication-runner-discriminates | medium | The duplication instrument is repaired and was proven to refuse false green

The duplication runner was previously found rendering zero clones green while
real clones existed. It now discriminates, proven across every failure mode
rather than by a single successful run: empty output, unparseable output, the
bare string `Found 0 clones.`, an absent `npx` binary, and an exceeded timeout
each classify as unavailable with green false. A real scan reports 12 clones
with file and line coordinates over a non-empty corpus.

The `Found 0 clones.` case is the important one: the instrument refuses to
report an unverified zero as clean, which is precisely the trap that produced
the earlier false green.

### plan-completion-overstated | critical | The wave was briefed as landed while 54 of its 55 steps are open

The campaign was handed over on the premise that Waves W03, W04 and W05 had
landed. W05 carries **1 closed step of 55**, with a single execution record.
The premise is false as stated.

The code position is better than the tracking: the live command tree already
carries W05's target grammar — passphrase change, the recovery family, flat
recover, and reset start/status/resume are all present, and the removed
lock, rekey and sandbox-use paths are absent from the tree and from all four
locale catalogues. Much of W05 therefore appears satisfied at HEAD, largely by
the sibling custody campaign. But "appears satisfied" is a claim, not evidence,
and exactly one W05 step was checked against its surface during this review —
the write-policy token step — which turned out to be the one genuinely not
done, and which was concealing a fail-open.

That is the whole argument against closing a wave on presumption. The
satisfied-at-HEAD conclusion must be established per step against its named
surface before any W05 step is checked.

### w06-p18-verified | high | P18 evidence is complete at HEAD, 13 of 13 records populated, 4 steps must stay open

DEFINITIVE. Supersedes the two entries below, both of which counted W06
coverage from working-tree snapshots taken while the phase was still running
and were wrong in different directions. Measured at HEAD by reading every
record out of the object store rather than the working tree: **13 W06.P18
records, 13 with a populated Outcome, zero empty.** They landed as one
explicit-pathspec commit.

P19 subsequently landed all 24 of its records too — see the entry below. Both
phases produced their evidence in full. Every claim in this review that either
had not is superseded.

The methodological point outlives the numbers. A count taken from the working
tree while a peer is mid-commit is not a measurement, and this review made that
error twice before reading HEAD. The reconciliation should read committed
state, not the tree.

P18's verdicts: eight satisfied, four failed, one satisfied-with-unverified.
Failures, none of which may be closed — the whole-directory CLI test gate at 16
failed of 2756, where 12 are peer clusters against uncommitted locale, error
taxonomy and sequence files and 3 are worker artefacts; the config suite at 8
failed of 131 on an order dependence; the evidence and audit suite passing on
code, command, schema and tests but failing on documentation; and the MCP
parity suite at 22 failed of 279, still 13 failed when re-run sequentially, so
not a parallelism artefact.

Six defects were surfaced and are tracked as Steps rather than left in prose.
The MCP identity break is the serious one: `cadrumo_whoami` resolves profile
health through a process-global registry seeded only as an import side effect
of the wizard package, and every production wizard import is deferred and
function-local, so nothing on the MCP path ever seeds it. A clean interpreter
importing the MCP entrypoint confirms the wizard is absent and the read raises,
and a stdio-subprocess client receives the error over the wire. The same root
cause explains failures in the config and agent-eval suites. The CLI
diagnostics path was driven end to end through the installed executable and is
unaffected.

A second false-green instrument was found, matching the pattern already
recorded here twice: the namespace-registry adoption gate walks 879 production
files, finds zero subjects, and asserts that the empty list is empty. It has no
anti-vacuity floor and covers three roots rather than every production root.
The invariant it claims is genuinely proven, but by a different named gate, so
the gate itself carries no information.

The constraint that makes the identity fix non-trivial, and the trap to avoid.
The profile-key registry has exactly two seeding points today, both test
conftests — one under the contribuyente domain, one under the registry
calculations tests — and neither is reachable from the MCP or CLI-config trees.
Every production wizard import is function-local by lazy-import policy, so
there is no import-time path that seeds it in a shipped process. A third
conftest import would turn all twelve failures green and leave the shipped
server exactly as broken as it is now. The fix needs an initialisation point
the entrypoints actually execute, and its proof needs to be a real server
process rather than a test-suite pass — which is how the defect was
established in the first place.

Six of the six os_keychain cases remain deselected by marker under the agent
logon: not skipped, not xfailed, not passed, and not verified.

### w06-evidence-partial | superseded | Counted 10 of 13 from a working-tree snapshot, wrong, see w06-p18-verified

CORRECTION to the entry below, which was written from a snapshot taken while
both agents were still running and is superseded on the counts. The P18 agent
subsequently filled 10 of its 13 records. The 36-of-37 figure was accurate when
taken and wrong within the hour; it is corrected here rather than silently
edited, because a close review that misreports its own coverage is the failure
it exists to catch.

Current state: of 37 W06 records, 10 carry evidence and 27 do not. All ten are
P18. The P19 agent produced 24 scaffolds and no evidence.

P18's landed verdicts are 8 satisfied and 2 failed. Satisfied: auth and
certificate suites (185 passed), ledger atomicity and rollback (442), profile
export and subject-access (271), evidence service and audit replay absence
(25), namespace registry adoption (27), filed observations (185), typed LLM
review routing (79), and the duplication runner and health report (11).

Two failures need owner attribution before any closure: the passphrase and
recovery lifecycle suite at 8 failed against 123 passed, and the MCP dispatch,
identity, input-schema, risk, mutability and telemetry parity suite at 22
failed against 257 passed. The first is the expected keychain remainder in
whole or in part; the second is not explained by that and has not been
triaged. Neither Step is closed.

Still empty in P18: the pointer, switch, logout, reset and bootstrap-policy
suites, the hashing call-site suites, and the registry as-of query suites.

### w06-evidence-not-produced | superseded | Counted 36 of 37 empty from a working-tree snapshot, wrong, see w06-p18-verified

Thirty-seven execution records exist on disk for phases W06.P18 and W06.P19.
Thirty-six carry empty Description and Outcome sections: the scaffold exists,
the evidence does not. Both dispatched verification agents scaffolded their
full record set up front and filled almost none of it. Counted by file
existence alone, those 36 files read as 36 completed Steps.

No W06.P18 or W06.P19 step is closed by this review, and none should be until
its record carries the command, the collected count, the exit line and the
HEAD it ran against. The whole-surface conformance runs, the full unit and
integration lanes, the documentation build, the import-graph contracts and the
semantic duplication re-audit were not completed within this wave.

The vault check does not catch this: it validates frontmatter and links, not
whether a record says anything. Structural completeness of records has to be
asserted separately, which this review did by parsing section bodies.

### closure-state-uncommitted | high | The committed plan understates completion by 31 Steps

The campaign's closure commits landed execution records without the plan file.
Commit `e081a4d0c7`, whose message states that it closes W03.P09 S84 through
S89 with execution records, changed six record files and did not touch the
plan. The same shape recurs across earlier closure commits.

At HEAD the plan reads 122 closed and 132 open. In the working tree it reads
153 closed and 106 open. Thirty-one closures therefore exist only as
uncommitted working-tree state, twenty-seven of them authored by prior
handovers of this campaign and four by this review.

Two consequences. Anyone reading the repository at HEAD — including a future
handover, and including the completion figures quoted in any close summary —
sees a materially different campaign state from any agent's working tree. And
the closure state is held only in an uncommitted file, so it is one careless
working-tree operation away from being lost, while the evidence it depends on
is already committed.

The reconciliation in this review was computed against the working tree and
reported 153 closures each backed by a substantive record, so the closures
themselves are sound. What is missing is the commit that makes them durable
and visible. This review deliberately did not commit the twenty-seven peer
closures: they belong to their authoring handovers, and sweeping another
agent's plan state under this SHA is the failure this campaign's own
discipline forbids.

### import-contracts-never-ran | critical | Two stale ignores aborted the layered contracts before any were evaluated

Import-linter aborts on an ignore that matches nothing, so a single stale entry
disables the whole run. Two were present: one naming a test module renamed by
commit `04ca5436f6`, one naming a conftest that no longer exists in the
deadlines package. The five layered contracts were therefore not being checked
at all, and had not been for some time. The configuration's own comment records
that prior ignores had already gone stale once on a test rename, so this is the
second occurrence of the same failure.

The failure was masked twice over. The tool exits 1, but the exit code was lost
whenever the command was piped, and the aborted run prints no contract results
at all — so it reads as a short, unremarkable output rather than as a gate that
never ran.

Retargeted and removed at commit `b8ed7b3ccc`. Restoring the run made real
violations visible for the first time: **3 contracts kept, 2 broken**, with
roughly ten violating edges — three domain-to-application edges from a bucket
payload-version test, one from profile registration and two from a sandbox
notice into adapters persistence, and four TUI test modules importing
entrypoints. Every one belongs to another campaign and none was absorbed here.

This is the most consequential finding after the write guard, because unlike
the write guard it disabled an entire gate family rather than one catalogue
entry, and because the aborted state is indistinguishable from a healthy one
without reading the exit code.

### conformance-gate-residual | medium | Two conformance failures remain, both peer-owned, one now fixed

The five CLI conformance suites collected 539 cases: 537 passed and 2 failed.

The first was a live dead operator instruction. An evidence refusal told the
operator to run `aeat app ledger evidence add --file INVOICE.pdf`, but that verb
takes a positional path and has no such option, so following the instruction
fails. Every other citation of that verb in the tree already uses the positional
form, making this a lone outlier. Fixed at commit `b8ed7b3ccc`; the suite now
passes 8 of 8.

The second is a sequence contract for a modelo-390 records audit whose
`@blocked unconverted` marker line is parsed as a command path. That file is
uncommitted peer work in flight from the docs-sequence conversion campaign,
last committed the same day by that campaign. It was left untouched. It is a
parser gap in how the conformance gate reads a blocked-row marker, not a
removed verb spelling, so it does not indicate a conformance regression in
this campaign's surface.

### what-was-actually-verified | low | The evidence this review does carry, so the next handover need not re-derive it

Recorded so the remaining work is bounded rather than restarted. All figures
were taken between commits `82a04ead90` and `c4ed7ea96b`.

The live command tree materialises to 289 leaf paths with zero duplicate paths.
The five CLI conformance suites collected 539 cases with 537 passing, and the
two failures are triaged above. The four-locale suite passed 60 of 60. The
layered import contracts, once able to run, stand at 3 kept and 2 broken. The
duplication runner reports 12 clones at 0.07 percent duplicated lines over a
non-empty corpus, and refuses five distinct failure modes as unavailable rather
than green. The write-guard and manifest-parity suites pass 13 of 13 serially
across both lanes. Repository-wide vault checks exit 0 with zero errors and no
finding attributable to this feature. Every one of the 153 closed Steps
reconciles to a substantive execution record.

What remains genuinely unverified in W06 is the full unit lane, the serial
integration lane, the documentation build and conformance gate, the generated
CLI reference and static-tree conformance, the repository ratchets for skips
and test doubles and tautology, the full collect-only classification, the
semantic duplication re-audit across functionality clusters, and the formal
code review over the campaign diff. None of those were run to completion, and
none should be recorded as satisfied.

### period-grammar-was-stale-tests | medium | The candidate accept-path regression was four tests stale against the --file conversion

Escalated as a possible functional break — a period token the canonical grammar
accepts being refused at the boundary — and resolved as neither a regression
nor an instructive-refusal breach.

All four cases passed the statement path positionally. The verb moved to a
required `--file` under the pull-and-file standard, so Click refused the
unexpected argument and every case died at parse time, before any period logic
ran. That is the whole explanation for the bare usage block: it was Click
refusing an extra argument, not a period refusal that had lost its accepted-set
prose.

Driven through `--file`, the real refusal names the accepted tokens and the
corrected invocation. The instructive-refusal requirement is met, and the three
message-quality concerns dissolve with it. Fixed at commit `e351ded266`: 18
passed, previously 4 failed and 14 passed.

Worth recording because the failure mode was well disguised. A stale invocation
against a renamed option surfaces as a refusal-shaped error at exactly the
boundary whose refusal text is under scrutiny, which is why it read as a
grammar defect from the failure output alone. The discriminator was cheap —
invoke the verb both ways by hand and compare — and no amount of reading the
assertion messages would have produced it.

The durability point stands regardless: these cases assert against rendered
operator prose, so a boundary change reds them rather than a behaviour change.
Asserting the accepted set on the error envelope's structured context would
survive the next wording pass.

### instruments-assert-unproven-sets | high | Three false-green gates, one shared failure mode, one cheap fix

Consolidating what were three separate observations, because they generalise
and the generalisation is the actionable part.

The write-guard parity gate collects catalogue entries whose family classifies
read-only and asserts that set is empty — but an unknown command key classifies
as not-read-only, so a dead entry never enters the set. The namespace-adoption
gate walks 879 production files, finds zero subjects, and asserts that empty
list is empty. A naive lazy command-tree walk yields one leaf and asserts over
it without error.

Each asserts a property of a set it never proves is non-empty. Each is green.
None can distinguish "the property holds" from "there was nothing to check".

The fix is a floor assertion — assert the subject count is non-zero, and where
a plausible size is known, assert against it — which is a few lines per gate
and would have caught all three. The write-guard gate added in this review
asserts a minimum leaf count for exactly this reason, so the pattern is already
demonstrated in-tree.

This is the campaign's most transferable finding. The duplication runner was
repaired against the same failure mode in an earlier wave, which means the
project has now hit it four times in four unrelated instruments.

### read-the-subject-not-a-reference-to-it | high | The reasoning-level form of the false-green pattern, hit three times in one wave

The instruments finding above has a counterpart in how this wave reasoned, and
the two are the same defect at different levels.

Three times, a conclusion about a subject was drawn from an artefact that
merely mentions the subject. A claim about what a refusal SAYS was drawn from
the assertion messages of the tests failing against it, rather than from
invoking the command. A claim about what those tests ASSERT was then drawn from
the fix's diff, rather than from reading the test file — "the fix added no
accepted-set assertion, therefore none exists" is a non-sequitur, since absence
in a diff says nothing about what pre-existed. And a claim about W06 coverage
was drawn twice from working-tree snapshots rather than from committed state.

The rule, stated at the level that covers all three: read the subject, never an
artefact that references the subject. Failure output, diffs, log lines and
working-tree snapshots all reference the subject; none of them is the subject.
Each was one cheap read away from the real thing.

This is the clean-negative shape at the reasoning level — absence within a
narrow view read as absence in the world — which is exactly what a gate does
when it reports a set clean without proving it looked at anything. The
instruments finding and this one are one defect in two registers, and the
instruments version is the one that ships.

Worth recording that every instance was caught, and caught cheaply, by going to
the subject: invoking the verb by hand, reading the test body, reading the
object store. The expensive part was never the verification.

### pathspec-commit-defeats-the-anti-sweep-guard | high | The staged-set check does not protect a shared document

The commit discipline in force pairs an explicit pathspec with a
`git diff --cached` inspection to prove the staged set carries only the
author's hunks. On a shared document that pairing has a hole, and this wave
walked into it.

A pathspec commit takes WORKING-TREE content for the named paths, bypassing the
index for exactly those paths. So the staged view can be empty, stale, or
correct and the commit still publishes whatever another agent has left in the
tree for that path. The guard inspects the index; the commit does not read it.

Observed directly: commit `83df56f216` carries a peer's full rewrite of an
audit note under a message describing a much smaller edit of the author's own.
The peer's write landed between the author's edit and the author's commit, its
own staged set came back empty, and nothing in the `git diff --cached` check
could have revealed it. The content was byte-identical to what the peer wrote
and nothing was lost, but the attribution and the message were wrong, and only
luck made the outcome benign.

The two protections that actually hold are serialising ownership of a document,
or committing from a HEAD-anchored patch staged with `git apply --cached` and
then committing the index with no pathspec — the shape this review used for
every plan-file change specifically because the plan carried peer closures.
Note the two guards are not interchangeable: the no-pathspec index commit is
what protects an entangled file, and the pathspec commit is what protects
against sweeping a peer's *other* staged files. Which one is correct depends on
whether the contention is within a file or across files.

### w06-p19-verified | high | P19 evidence is complete too, and its verdicts are honest, 12 of 24 steps must stay open

Measured at HEAD from the object store: **24 W06.P19 records, 24 with a
populated Outcome, zero empty.** W06 evidence is therefore complete across both
phases — 37 of 37 records — and this review's earlier statements that the wave
produced no evidence are wrong and superseded.

The verdict distribution is 12 satisfied, 9 failed, 2 unverified, 1 blocked.
The two unverified and the one blocked are the reason to trust the set: the
documentation build and the semantic duplication sweep are reported unverified
rather than green, and the agent-swarm dispatch is reported blocked by harness
policy with a substitute named. An audit that reports twelve satisfied and
nothing else would have been the less credible outcome.

Independent confirmation of this review's own import-contract finding, which is
worth more than the finding standing alone. P19 reached the same result by its
own route — three contracts kept, two broken, exit 1 — and recorded the corpus
size the tool itself reports, 3660 files and 17595 dependencies, so the result
is proof against the vacuity failure this review has now recorded four times.
It also attributes every violating site and finds none owned by this feature,
matching the attribution reached here.

Twelve steps must stay open: the nine failures, the two unverified and the one
blocked. Several failures are explicitly peer-owned working-tree churn, and one
records a defect that was fixed between measurement and writing — that one
should be re-run rather than closed on the record alone.

### stale-snapshot-error-recurred-four-times | high | The method finding is evidenced by this review's own repeat failures

Recorded because the count matters more than any single instance. This review
drew a conclusion from a working-tree or point-in-time snapshot, and was wrong,
**four separate times**: W06 coverage reported as 1 of 13, then as 10 of 13,
then P19 reported as having landed nothing, and separately a verdict-extraction
pattern that did not fit the records' actual shape and returned no verdicts at
all where twenty-four existed.

Every one was corrected by going to the subject — reading committed state out
of the object store, or reading the record bodies rather than pattern-matching
a heading that was never there. Every one was cheap to check and expensive to
leave standing.

Four occurrences in a single review, by the reviewer whose explicit remit was
to catch exactly this class in others, is the strongest available argument that
the discipline cannot rest on care. It needs the mechanical form recorded in
the recommendations: reconciliation reads committed state, and a pattern is
proven against the data's real shape before its silence is believed.

## Recommendations

Each recommendation below is tracked as a Step with a verification gate, per
the campaign-close discipline. None is left as prose.

Verify each W05 step against its named surface before checking it, rather than
inferring satisfaction from the live command tree. The write-policy step is the
proof that the inference is unsafe: it was the one step actually checked and the
one step genuinely undone. Ties to plan-completion-overstated.

Complete the W06.P18 and W06.P19 evidence, and refuse to close any step whose
record lacks a command, a collected count, an exit line and a HEAD reference. A
non-zero collected count is part of the gate: the default marker selects nothing
for integration modules and exits green, and a marked run still holds serial
cases out under parallel execution. Ties to w06-evidence-not-produced.

Decide whether the remaining mutation-shaped command leaves outside the write
guard belong inside it. Forty-eight live leaves whose final token is a mutation
verb are neither guarded nor bootstrap-exempt. Many are certainly correct as
they stand — profile creation cannot require an active profile, registry
verification reads bundled data, several exports write files rather than bucket
state — so this is a per-verb judgment, not a sweep, and it should not be
performed mechanically. This is the one item here that needs a decision
recorded in a follow-on ADR rather than a fix: the ADR must state the criterion
by which a command path is or is not profile-bound, so the catalogue stops being
a hand-maintained list. Ties to write-guard-fail-open.

Extend the anti-vacuity treatment to the command-classification default. A key
absent from the risk table classifies as not-read-only and therefore imitates a
live write verb; any gate resting on that default inherits the blindness
demonstrated here. Ties to write-guard-parity-gate-vacuous.

Add a structural assertion that an execution record carries a populated Outcome
before its Step may be checked. The existing vault check passes empty
scaffolds, so the honesty property this campaign depends on is currently
enforced by author discipline alone. Ties to w06-evidence-not-produced.

Make a stale ignore entry fail loudly and separately from a contract breach, so
an aborted import-linter run cannot be mistaken for a quiet one. A gate whose
configuration has rotted should be as visible as a gate whose contract is
broken. Ties to import-contracts-never-ran.

Resolve the two broken layered contracts with their owning campaigns. They are
newly visible rather than newly introduced, and they should not be closed by
widening the ignore list, which is what produced the stale entries in the first
place. Ties to import-contracts-never-ran.

Teach the documented-command conformance parser to recognise a blocked-row
marker instead of reading its prose as a command path. Ties to
conformance-gate-residual.

Commit the plan alongside the execution records in every closure commit, and
land the 31 closures currently held only in the working tree. Any completion
figure quoted from HEAD is understated until that happens. The 27 peer
closures should be landed by their authoring handover rather than swept by a
later one. Ties to closure-state-uncommitted.
