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

NARROWED, and the reason matters more than the narrowing. This finding
originally implied the permissive default was a broad hazard. The P19 audit
challenged that, enumerated all six consumers, and was right that production is
safe — but its stated reason was wrong, and checking the reason changed what
should be recorded.

The claim under challenge was that the default is fail-closed everywhere in
production. It is fail-closed in the MCP identity gate, which asks whether a
command is read-only and returns early if so: an unknown key is not read-only,
so the gate enforces. It is fail-OPEN in the HITL confirmation gate, which
derives its policy from the destructive, live-write and handoff flags — all
three default false for an unknown key, so `confirmation_for_tool` returns
`AUTO_APPROVE` with no user interaction. Verified directly: a literal bogus key
yields `AUTO_APPROVE, interaction=False`, while `ledger.remove` and
`modelo.work.file` correctly yield `CONFIRM`.

Production is nonetheless safe, by reachability rather than by direction. The
HITL gate is only ever called with `descriptor.command_key`, drawn from the
live descriptor set, so an unclassified key cannot arrive. That is a real
guarantee and it is also a weaker one than fail-closed: it holds only while
every caller grounds its key, and nothing enforces that. A future caller
passing an unvalidated key would silently auto-approve a mutation.

The confirmed narrowing stands: of six consumers, only
`test_write_policy_mutability_parity.py` consumes the default without first
grounding its key against the live surface, which is precisely the grounding
the gate added at `5eaf4b0ee6` supplies. The risk-table parity gate is made
stricter by the default, and the two agent-eval goldens assert manifest
membership before classifying.

This is the S283 lesson in a third register. A permissive default is safe only
as long as its input is proven to be grounded — the same shape as a gate being
meaningful only as long as its subject is proven to be exercised.

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

The upstream half of the rule, which this review learned by propagating someone
else's unverified inference into its own findings. A downstream reader taking a
claim from a verification report is doing the normal and correct thing; the
failure was that the report stated an inference drawn from a coincidence in the
same register as a measurement, so nothing in it invited the one-command test
that later killed it. Both halves are needed. A report must mark its inferences
as inferences, and a reader must go to the subject before promoting any claim to
a finding. Where a report does distinguish the two — as the same author's later
work did, separating a memory measurement that stood from the conclusion hung on
it that did not — the reader can act on it safely and the correction costs one
command instead of a retraction.

A practical corollary for anything written to be read by someone who was not
present: state the instrument beside the claim. "Four workers reported abnormal
termination, written inline and independent of buffering" survives scrutiny in a
way that "the lane stalls at the same point" does not, and the difference is
visible on the page rather than only to the author.

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

### untracked-peer-modules-break-live-gates | high | Two uncommitted files are the single largest cause of the failing lanes

Both are untracked working-tree modules from other campaigns, and between them
they account for the great majority of the integration-lane failures. Neither
is this campaign's to fix, but the attribution matters because without it the
lane reads as broad campaign breakage.

A test module under the operator-output package registers the production schema
key `operator_output.tests.probe` for a command that does not exist. It is the
sole cause of 128 assertion failures and all 19 setup errors in the integration
lane, surfacing as a schema-resolution refusal that would otherwise ship an
argument-free schema. The refusal is the system working correctly. The defect
is a test module registering a production key at all — a test double reaching
into the production registry is the shape this project forbids, and it is
currently invisible because the file is untracked.

A wizard results module holds the `config.profile.create` and
`config.profile.edit` schemas outside the payload-discovery walk, which only
imports modules whose name contains `payload`. This breaks the live MCP
surface, not merely a docs gate: a focused input-schema run fails with a key
error on `config.profile.create`. It is also the second cause behind the single
non-identity MCP parity failure recorded elsewhere in this review.

### docs-lane-stall-claim-withdrawn | high | The stall this review recorded did not exist as described, and the real signal is worker deaths

WITHDRAWAL, superseding the entry below, which this review accepted from a
verification report and recorded without testing its mechanism. Reading the
captures as bytes rather than as rendered text overturned it.

The forty minutes of silence was structurally guaranteed and carried no
information. Under quiet mode pytest's progress line is 72 marks plus a
percentage field, and the capture wrote only complete lines. The isolated run
reported as producing nothing for forty minutes was a module of 22 tests: 22
marks cannot reach 72, so a perfectly healthy run could not have emitted one
byte. Zero bytes was the correct output of a correct run. Confirmed
independently here against this review's own captures, where the progress line
is 79 characters wide in every case while the mark count varies from 13 to 72 —
the line is padded and terminated only at completion, so nothing flushes
mid-run.

The identical-stopping-point coincidence dissolves too. Each capture holds two
complete 72-mark lines plus a partial third that never terminated and so never
flushed as it grew. Counting the marks actually present on that partial line
gives 30 in the 24-worker attempt and 31 in the 4-worker attempt, so the two
runs had completed roughly 174 and 175 of 194 rather than stopping together at
144. They were read at the same buffer boundary. That is a property of the
capture, not of the lane, and the inference this review drew from it — that
matching stop points ruled out a resource explanation — is unsound and is
withdrawn. The memory measurement stands; the conclusion hung on it does not.

What survives every correction is the real finding, and it was always the
stronger one: four workers reported `node down: Not properly terminated` at 24
workers and two at 4. Those lines are written inline and are independent of
buffering. Abnormal worker termination is a genuine defect signal, unlike
slowness.

The lane is also simply expensive, and declared so in-tree: two modules override
the repository timeout ceiling with a 1800-second budget, eleven of 24 modules
shell a build or subprocess, and the resolvability sweep is a single test whose
own comment records that it measures about 840 seconds because it shells a full
single-worker documentation build and then reads every rendered page. A lane
that looks motionless for fifteen minutes is consistent with one such test
running normally.

The module still cannot be named, for two reasons worth recording: the
distribution mode decouples completion order from collection order, so a mark
position cannot be mapped back to a test; and both runs were killed, destroying
the evidence of whether they would have recovered and finished. The lane stays
UNVERIFIED and S287 is re-scoped to the worker-death question.

The method lesson generalises past this lane and is the reason this is filed at
high rather than medium. Every wrong conclusion in this thread came from
trusting a rendered view of a log instead of its bytes; a 324-byte file examined
with a control-character view overturned two filed claims. A partial line is
invisible in a normal read and looks exactly like a stalled process. That is the
vacuity problem this review has chased throughout, one level further down — in
the toolchain that reports the evidence rather than in the gate that produces
it.

### docs-lane-stalls-and-is-unverified | superseded | Recorded a stall that was a capture artefact, see docs-lane-stall-claim-withdrawn

Recorded as a finding rather than accepted as a slow run. The docs pytest lane
stopped progressing at the same point under 24 workers and under 4, with
roughly 78 GB of memory free and processors at around 60 percent, so it is
bounded by neither memory nor CPU. Because pytest emits its summary at the end,
no failure identities were produced at all.

The lane collects 194 cases, so this is not a zero-collection false green. It
is genuinely unverified in both directions, and a docs-lane result should not
be quoted either way until someone bisects it with no workers and names the
module whose worker exits. The elapsed time alone is not the signal — several
cases spawn full site builds and the module declares a thirty-minute budget.

### rag-index-degradation-measured | medium | The index is far worse than the wave was briefed, and it reports success

The brief described roughly 1027 indexed chunks. The measured figure is 466
indexed source-code sections against 3982 tracked Python files, with code
generation reporting `succeeded`.

The consequence is concrete rather than theoretical: all ten semantic sweeps in
the duplication re-audit missed. The index failed to return the duplication
runner for a query naming copy-paste detection, the hashing module for a query
naming file-byte hashing, and the namespace registry for its own name; two
unrelated probes returned the same file at the same offset. This is the
documented failure mode where a truncated index answers confidently instead of
refusing.

Every absence claim in this review was therefore established by reading and
exact search, and the semantic sweep steps are reported unverified rather than
clean. The service was not restarted or reindexed by anyone during the wave.

### size-budget-breach-is-peer-owned | medium | The one claimed feature-owned regression is not this campaign's

Both verification phases independently reported the config CLI module over its
size budget, and one attributed the growth to "the wizard-retirement and TUI
manager commits". The gate is genuinely red — 1385 lines against a budget of
1261, reproduced at HEAD with exit 1 — but the attribution is half wrong, and
the wrong half is the half that matters.

The line counts across the growth commits settle it. The module stood at 1254
lines, comfortably inside the budget, immediately before the commit that opens
the profile manager from create and edit. That commit took it to 1388. This
campaign's own wizard-retirement commit then reduced it to 1385, where it
stands.

So the breach was caused by a peer TUI campaign's addition, and this campaign's
contribution to that file was to make it smaller. It is not a feature-owned
regression, and the Step tracking it is re-scoped accordingly rather than
carried as this campaign's debt.

The wider consequence is worth stating, because it changes the shape of the
close. With this reattributed, no feature-owned regression has been identified
in any of the failing lanes: the unit-lane and integration-lane failures are
peer working-tree churn, two untracked peer modules, and environmental keychain
deselection. The campaign's own surface is not what is red. That is a
materially different close position from "nine failures outstanding", and it
was only reachable by attributing rather than counting.

Recorded also as a caution about attribution by commit subject. "Growth arrived
with the wizard-retirement and TUI manager commits" reads as a joint cause and
is how the misattribution entered; the numbers show one commit added 134 lines
and the other removed three. Attribute with `git show --numstat` against the
file, not with the commit subjects that happen to sit near it in the log.

### this-review-swept-a-peer-campaign | high | The reviewer committed 11 peer files under its own SHA, having verified the wrong scope

Recorded against this review rather than about someone else, because the whole
point of the finding above is that the guard has to be mechanical.

Commit `3f16615f6b`, whose message concerns a size-budget reattribution, carries
1913 insertions across 13 files. Two are this review's. The other eleven are the
censal-profile-autofill campaign's live work — a 749-line sede censal-datos
adapter, its tests, its fixtures, external constants and two generated API
stubs — staged by their owner and swept by a bare no-pathspec commit.

The verification that failed is the instructive part. The apply-cached plus
bare-commit shape was chosen correctly, because the plan file is co-authored.
The index was then checked with a PATH-SCOPED command against the plan file,
which correctly reported one changed Step row and zero foreign hunks. That
answer was true and irrelevant. A bare commit takes the whole index, so the
question it asks is "is the entire index mine?", and a scoped check cannot
answer it. Eleven files had been staged by their owner during the intervening
tool calls.

Content is intact — the peer's adapter and fixtures are all present at HEAD —
so the damage is attribution only. Un-bundling would require reset or revert
against a commit, both forbidden here and both risking the peer's work, so the
sweep is accepted rather than repaired, consistent with how every prior
occurrence in this worktree has been adjudicated.

The rule this yields: the bare commit's precondition is an UNSCOPED
`git diff --cached --name-only`, read immediately before committing and ideally
chained into the same command so nothing can be staged between the check and
the commit. A scoped check before an unscoped commit is a category error, and
it is one the existing discipline does not name — every prior incident in this
worktree was a pathspec commit taking working-tree content, which is the
opposite failure.

Stated plainly because the review's own credibility depends on it: this is the
same class of defect the review spent its length documenting in gates — a check
that runs, passes, and does not measure the thing the operation actually
depends on.

### s204-found-what-the-token-matcher-cannot | high | Four duplicate authorities invisible to the clone runner, one verified in full here

The swarm step was executed as a single structural scan rather than a fan-out,
because the semantic index could not serve as a discovery instrument at 466
sections against 3982 files. The substitute was an AST scan whose load-bearing
pass renames every local identifier to a positional placeholder and blanks every
string before hashing a function body, so a concept implemented twice under
different names, variables and messages still collides. Discrimination was
proven before use against a hand-built twin pair and an unrelated control, and
the corpus is quoted: 1372 production modules, all parsed, 8947 bodies hashed.

That method matters because it explains the finding. The clone runner's twelve
groups and these four barely intersect, and none of the four appears in the
duplication dispositions — exactly what a token matcher blind to renamed twins
would produce.

The strongest cluster was verified independently here rather than accepted.
`_formula_runtime_ops.numeric_casilla_value` is public and its docstring states
it is the accessor shared by the M210, M131 and M303 formula-op families. The
formula-runtime module nevertheless carries its own `_m100_numeric_casilla_value`
with six call sites. Normalising only the function name and the error alias, the
two bodies diff to nothing but the missing docstring — the executable code is
identical. And the module already imports the ops module at line 40 and aliases
that module's `UnresolvedFormulaDependencyError` at line 49, which is the very
class its private copy raises.

This is precisely the wizard-prompter shape the project's own discovery rule
cites: a canonical owner whose docstring claims what ships, plus an undocumented
hand-copy that a symbol-name search would never surface. The rule exists because
that pattern cost hours once already, and it has now recurred in the calculation
engine.

The other three are a modelo copy of a public evidence-covers-snapshot invariant
that raises a wider error type than the canonical and is reached by a
cross-package private import from another package's test, and two byte-identical
helpers — an FTS or-group builder duplicated across two application packages
that may not reach into each other, and an export-field overlap predicate
duplicated across a layer boundary. A journal-repository substrate is recorded
separately as an extraction candidate rather than a duplication finding, because
the two classes are constraint-shape divergent even though their file substrate
is not.

Two candidates were correctly killed by the substitutability pre-filter, and the
name-collision pass was dominated by protocol methods rather than duplication —
both signs the filter is doing its job rather than inflating a count.

Novelty was established by exact search rather than assumed: no vault document
names three of the symbols at all, and the fourth appears only as an invariant,
never as a fact that two implementations of it exist.

The honest limit is recorded with the finding: the scan collides only exactly
equal normalised bodies, so one extra guard clause or a reordered statement pair
defeats it. A hit is strong evidence and a null is weak. Production only, with a
twelve-node floor. The four found are a lower bound, not an inventory.

### head-cannot-import-the-wizard-package | critical | A committed importer names an untracked module, so HEAD is broken for anyone who does not already have the file

Found while adjudicating the MCP identity fix, and it is the most consequential
thing in this review that has nothing to do with this campaign.

The committed `application/wizard/__init__.py` carries a module-level import of
`._results` at line 89. That module is UNTRACKED. It was introduced by a TUI
campaign commit that added the importer without adding the module, and it exists
as an ordinary file in every active agent's working tree — 2489 bytes, present,
working. So the package imports perfectly for everyone here and cannot import at
all from a clean checkout of HEAD.

The blast radius is not limited to the wizard. The CLI root reaches
`application.wizard` submodules to seed the profile-key registry, and importing
any submodule executes the package initialiser, so the shipped CLI inherits the
failure on a clean tree. That is consistent with the installed-CLI resolution
oracle failing, which had been attributed to skew without the cause being named.

This is the worst variant of the shared-worktree attribution problem this review
has documented repeatedly. Every prior instance broke attribution while
preserving content. This one breaks the artefact, and it is invisible from
inside the worktree by construction: no agent can observe it, because every
agent has the file. Only a clean checkout, a fresh clone, or an installed
distribution can see it, which is exactly the set of readers nobody is.

It also explains a second-order effect that would otherwise look like a defect
in the identity fix. Seeding the registry from the MCP server necessarily
imports the wizard package, which registers two schemas that live in that
untracked module, so the in-process transport reports 295 command schemas while
a subprocess reports 293. The transport-parity assertion had been passing only
because both sides were equally blind to those two — the same
assert-over-an-unproven-set shape recorded three times already in this review,
now in a fourth register and this time hiding a genuine under-report rather than
merely proving nothing.

Not this campaign's to fix, and deliberately not fixed here: committing another
campaign's untracked module would take ownership of work in flight. It is
recorded, tracked, and escalated instead.

RESOLVED, by its owner, before the escalation was delivered. The owning campaign
committed the module as `b482927401`, whose subject names the defect exactly —
"commit the results module HEAD already imports". Verified empirically rather
than by file presence: a HEAD-only tree extracted with `git archive`, containing
no untracked files at all, imports the wizard package successfully and exports
the result classes. The shipped CLI is no longer broken on a clean checkout.

Two things worth keeping from how this resolved. The first check reported the
module untracked; twenty minutes later it was tracked, and only re-running
against the current HEAD caught that. That is the fifth time in this review a
conclusion drawn at one HEAD was falsified at another, and the first time the
staleness worked in the campaign's favour — which is exactly why the rule has to
be mechanical rather than motivated.

The second is a distinction that matters for the held MCP fix and was almost
lost: **tracking is not enrolment.** The module is now in HEAD, but the schema
manifest still populates itself by importing modules named `*_payloads` under
two known payload packages, and this module is neither.

**That claim was wrong, and measuring it rather than reasoning about it is what
showed so.** The reasoning was sound and the premise was not. The walked payload
module `_config_payloads.py` imports the two result classes from the wizard
package at module level, so importing it executes the decorators that register
those schemas. Enrolment was never by filename; it was by that import chain.

What actually produced the 293-versus-295 divergence was the broken HEAD itself.
The walk tolerates a payload module failing to import — it collects the failure
and continues — so while the results module was untracked, importing
`_config_payloads` raised, the walk swallowed it, and exactly those two schemas
went missing. Committing the module repaired the import and with it the count.

Measured at HEAD after that commit: a tree extracted with `git archive`
containing no untracked files reports **295 schemas, both profile schemas
present, zero import failures**, identical to the working tree. The
transport-parity suite passes 8 of 8 with the held identity fix applied. So
tracking WAS sufficient, the enrolment step opened against this claim is
unnecessary, and the sequencing condition set for the identity fix is fully
satisfied on this axis.

Recorded rather than quietly corrected because the error is instructive. A
swallowed import failure presents as a missing entry, which looks exactly like
something never having been enrolled — and the difference is invisible until you
read the count and the failure list together.

**CORRECTED AGAIN — the correction above was itself wrong in its reason.** The
conclusion held, S295 is unnecessary and the identity fix is unblocked, but the
explanation was fabricated out of present state. The verification phase caught
it by testing the claim rather than agreeing with it.

Enrolment IS filename-filtered, exactly as originally recorded. The population
walk imports `*payload*`-named modules under two declared payload packages and
never reaches the wizard results module, which is under neither and carries no
such name. What changed is not that the claim was always false; it is that a fix
landed at `92b0dfd10b` on the morning of 2026-07-26 — thirteen hours after the
finding was filed, and a descendant of the HEAD it was measured at — bridging
the filter by importing the two result classes into a module the walk already
visits. That fix's own comment states the mechanism verbatim and marks the
imports LOAD-BEARING. Attributing the repair to the untracked-module commit was
wrong as well: that one fixed a broken import, not the enrolment.

So the true sequence is: the finding was correct when made, a peer repaired it in
the interim, and this review then measured the repaired state and invented a
history in which the problem had never existed.

The method failure is precise and worth more than the finding. Presence was
confirmed; history was not. `git log -S` on the import line answers "when did
this arrive" in one command — the same command that settled the size-budget
attribution earlier in this same review. The tool was in hand, recently used,
and not reached for, because the present state was consistent with the story
being told. Consistency with a story is not evidence for it.

A fragility created by the fix, surfaced by the verification phase. The bridge is
written in the re-export idiom, each name imported and rebound to itself, which
is visually indistinguishable from a redundant re-export that a tidy-up would
delete. Deleting it silently drops both profile verbs from the MCP surface again.
Two things hold the line: a load-bearing comment and the live-leaf-versus-registry
gate. Only the gate is a real guard, and it was confirmed by running it rather
than by reading it.

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
