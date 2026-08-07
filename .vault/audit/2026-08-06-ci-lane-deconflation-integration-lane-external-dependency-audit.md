---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:045a9609be37f662359f022e95717030b0e5570dd14543f86836e574fcd16b71'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ci-lane-deconflation` audit: `integration parallel lane depends on a live ECB service`

## Scope

The integration parallel step of the full-conformance workflow, audited to determine whether
its non-blocking flag can be turned off. The step's own comment states the condition: thirteen
triaged real failures must close. This audit measures what remains and finds that the count was
never the operative question.

Two instruments were used and they are not equivalent. A working-tree run measures whatever
peers have uncommitted and is blind to masking in both directions. A guarded extraction of a
pinned commit measures committed source and is blind to anything requiring an installed package
or a generated artefact. Both were run; the divergence between them is itself a finding.

## Findings

### integration-lane-live-external-service | high | The lane makes live calls to a European Central Bank endpoint, so turning the flag off makes the release verdict depend on a third party

The foreign-exchange provider performs a real outbound request to a European Central Bank data
host at a fixed endpoint. The ledger corpus classification tests never name that host; they
reach it transitively through a multi-currency fixture, so the dependency is invisible from the
test identifier and appears only in assertion text.

During one working-tree pass the host returned repeated gateway timeouts and two tests failed on
that alone. A later direct probe of the same host returned three consecutive successes, and the
guarded extraction did not reproduce the failures at all. Three separate observations, same
source, opposite outcomes: a transient outage, not a defect.

That is precisely why it matters. Turning the flag off would make a release-verdict lane red
whenever a Frankfurt service is degraded, for reasons no commit caused and no engineer can fix.
The step's own comment gives the reason this is unacceptable: a lane that is always red is a
lane everyone learns to ignore. A healthy network on the day of measurement does not make the
lane independent of that service on any other day.

### integration-lane-one-real-defect | medium | One genuine defect survives at the pinned commit

A retención aggregation test fails at the pinned commit with a validation error reporting
missing perceptor observations. It was discriminated on both sides at the pinned commit using
literal patterns: the raise site exists and the message key is present in all four locale
catalogues, so the commit is self-consistent and the failure is a genuine code-path outcome
rather than a data-versus-code skew. Both instruments agree on this one, which here is
corroboration rather than coincidence, because they fail independently.

### extraction-blind-to-most-failures | high | Ninety-six per cent of failures are unmeasurable by the extraction instrument

Of twenty-eight failures at the pinned commit, one is a real defect, zero are working-tree
artefacts, and twenty-seven cannot be measured by an extraction at all. Twenty-three require the
console script to be installed, two require an installed service to spawn, one requires an
external binary, and one requires a generated documentation tree that is deliberately not
committed.

The estimate offered before the run was roughly correct in files and badly wrong in tests: three
heavily parametrised modules produced twenty-three failures between them. The unit of a count
must match the unit of the question it answers, or the number misleads in whichever direction
its author was not watching.

These twenty-seven would presumably pass in an environment where the package is installed. That
is inference, not measurement. An extraction certifies committed source and never committed
repository state, and this is that boundary appearing at full scale rather than as a footnote.

### verification-environment-unavailable | high | The only evidence that could settle the remainder is currently unobtainable

The workflow requires a self-hosted Linux runner. The sole runner carrying those labels is
offline; the one online runner is a Windows host and can never satisfy a Linux label. The
dispatched run is therefore not queued behind capacity, it is unsatisfiable until that runner
returns. The evidence needed to resolve the twenty-seven is not merely absent, it cannot
currently be obtained.

### docs-lane-sequence-nondeterminism | medium | Two documented sequences produce different output on consecutive identical runs

Two history sequences cannot be satisfied by any recorded golden. Refreshing one and
immediately re-checking it fails again, which is the discriminator between a stale
recording and an unstable producer. The output carries the same events in a different
order, all sharing one timestamp because the documentation sandbox freezes the clock.

This finding has now carried two wrong diagnoses, and both are corrected here
because a diagnostic copied forward with a bad first step is worse than none.

The first claimed the event ordering sorts on timestamp alone and wants a secondary
key. False: the canonical order key is already a pair of timestamp and event
identifier, and its own docstring describes this exact hazard.

The second claimed the tie-breaking identifier varies because the documentation
sandbox mints a fresh profile identifier each run. Also false: the sandbox pins a
fixed identifier through the canonical create, and its own docstring states that this
is precisely what makes profile-derived output deterministic.

What is established by measurement rather than inference:

Two consecutive refreshes of the same sequence produce goldens carrying the same
events in a different order. The line multiset is identical; only the sequence
differs. No identifier anywhere in the two recordings differs, though the recorded
text masks identifiers, so that is weak evidence rather than proof. The affected
frame is text-mode, so its envelope is empty and comparing envelopes proves nothing -
a trap worth naming, since an empty-versus-empty comparison reads as agreement.

The two reordered lines are the lifecycle and maintenance events that one rename
co-emits by design, sharing an instant under the sandbox's frozen clock. So the
ordering rests entirely on the tie-break, and the tie-break is not producing a stable
order across runs. Why it does not is unresolved.

The repair is not attempted, and this time the reason is that the cause is not yet
known rather than that the fix is risky. Two plausible explanations have already
proved wrong on inspection; a third guess implemented without measurement would most
likely join them.

### docs-lane-teaches-an-export-that-cannot-succeed | high | The Modelo 100 export refuses for want of an authoritative value, and the docs teach it as working

Exporting Modelo 100 fails because the export layout has no declared auxiliary version.
Every schema for the modelo makes that block mandatory, no bundled dictionary declares
the rows, and no bundled source carries an authoritative value. The system therefore
refuses rather than inventing a token that would satisfy the schema while asserting
something unverified.

The refusal is correct and is exactly the grounding discipline this project requires.
The problem is that a documentation page teaches this export as a working step, so the
lane fails on a product gap rather than a documentation defect.

Deliberately not silenced. The sequence framework can declare a non-zero exit as
expected, which would turn the lane green while documenting a blocked feature as though
it were intended. That is a content decision for the documentation owner, and taking it
inside a lane-fixing change would hide a real gap behind a green signal.

### ci-full-was-never-observed-past-its-first-gate | high | The lane's later steps hid real debt behind a gate that always failed first

The full-conformance lane had never executed past its lint step in the repository's
history. Five dispatches existed: one reached a runner and died at lint, four recorded
no runner and no steps at all, having been cancelled while queued. Every claim about
this lane's later behaviour was therefore structural rather than observed, including
claims made inside this campaign's own briefs.

Clearing the gates one at a time moved it forward three steps in a single session, and
each newly reachable step revealed real, previously invisible debt:

The lint step turned out to be two checks in sequence, so clearing the first only
exposed the second. Thirty-two unsorted import blocks from a re-export bridge removal,
then four absolute in-package imports, then a dead suppression directive for a rule
enabled nowhere, then four more findings that landed from concurrent work between one
push and the next.

The import-architecture step then broke on four application-to-adapter edges. These
proved to be sanctioned coupling whose exception entries had not followed code that
moved, not new architectural debt.

The typecheck step, reached for the first time, reports seventy-five diagnostics across
more than thirty files, concentrated in one aggregation module. This reproduces
identically outside CI, so it is long-standing debt that no lane was positioned to
surface rather than anything introduced tonight.

The finding is not any individual defect. It is that a gate which always fails at its
first step certifies nothing beyond that step, and the absence of failures downstream
reads exactly like their absence in the code. Three gates deep, the lane is still
finding real work.

### m210-tipo-renta-validator-duplicated-and-unwired | medium | A validator is tested but never called; its logic is inlined at the only call site

The typecheck gate reports a Modelo 210 tipo-renta validator as never accessed. It is
not orphaned: tests exercise it directly, and its own docstring describes it as the
semantic-role fallback for the generic casilla override surface.

That surface does validate, but by inlining the same two steps the function performs -
validate the official code, then project it. So the function duplicates logic that
already exists at its intended call site rather than guarding a gap. Nothing is
currently unvalidated.

Not remediated here. Collapsing the duplication means editing an IRNR validation path,
and the call site also binds the intermediate official code that other fields consume,
so the substitution is not the one-line swap it appears to be. Left for someone with
the modelo context, since a wrong consolidation here changes what the CLI refuses on a
real filing surface.

### semgrep-cast-rule-promises-an-escape-it-does-not-implement | high | The rule's message documents a justification path its pattern cannot honour

Clearing the typecheck gate let the full lane reach its semgrep step, which had never
executed. It reported forty-two blocking findings under two rules. Twenty-two were
suppressions lacking an inline rationale and are now fixed: the codebase had justified
them in a tagged block above the line, and that rationale is now also inline, with the
tag preserved so both forms name the same case. Four of the forty-two were introduced
by this campaign and were fixed rather than deferred.

Twenty remain, all casts in the domain and application layers, and they cannot be
fixed the same way. The rule's own message tells the reader that a genuinely
irreducible cast "must carry an inline justification comment naming the rule and the
reason". Its pattern is a bare cast call with no exception, so a justified cast is
flagged identically to an unjustified one. The message promises an escape the
implementation does not have. Every one of the twenty already carries a tagged
cast-rationale block explaining, typically, that an isinstance check narrows a mapping
or sequence but cannot check its type parameters.

Complying with the message was attempted and measured rather than argued. Inlining
each existing rationale produced sixteen line-length violations, with lines reaching
two hundred characters against a limit of a hundred and twenty; eight of the twenty
sites have under forty characters of room for any reason at all. So the form the
message asks for does not fit the code it governs, and the attempt was reverted.

Both resolutions that leave the rule untouched were tested, and neither works.

Inlining each rationale, the form the message asks for, produced sixteen line-length
violations with lines reaching two hundred characters against a limit of a hundred and
twenty; eight of the twenty sites have under forty characters of room for any reason.

Removing a cast and relying on the declared annotation was tried on a site whose
target variable is already annotated with the exact type the cast asserts. The cast is
redundant to a reader and is not redundant to the checker: with it removed, the value
is still reported as partially unknown, because a declared annotation does not narrow
what the checker cannot see through. So the cast is load-bearing for the gate above it
even where it looks like ceremony.

That leaves changing the rule. The pattern could grow the exception its message
already documents, or accept the tagged block convention the codebase uses. Either
makes the implementation match the stated policy, and either relaxes a gate on the
strength of what the code already does, which is why it is recorded rather than
taken.

This is recorded rather than decided because every path changes a gate or twenty
production sites, and the rule's own text is the evidence that its author intended an
escape to exist.

## Recommendations

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### integration parallel lane depends on a live ECB service | {level} | {summary}

     followed by a paragraph carrying the detail. integration parallel lane depends on a live ECB service is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### docs-lane-sequence-nondeterminism | medium | Two documented sequences produce different output on consecutive identical runs

Two history sequences cannot be satisfied by any recorded golden. Refreshing one and
immediately re-checking it fails again, which is the discriminator between a stale
recording and an unstable producer. The output carries the same events in a different
order, all sharing one timestamp because the documentation sandbox freezes the clock.

The first diagnosis offered here was wrong and is corrected. It claimed the ordering
sorts on the timestamp alone and wants a secondary key. It does not: the canonical
order key is already a pair of timestamp and event identifier, and its own docstring
describes precisely this hazard and why the identifier breaks the tie. That mechanism
is sound and needs no change.

The real cause sits one level down. The tie-breaking identifier is content-addressed,
derived from the event body, and the body carries a profile identifier that is
generated afresh on every sandbox run. The recorded output masks that identifier to a
placeholder, so two runs render what look like identical events in a different order
while their true sort keys genuinely differ. The ordering is deterministic for a fixed
dataset and unstable across runs that mint new identifiers, which is why refreshing and
immediately re-checking still fails.

That points the repair at the documentation harness rather than at the audit-trail
ordering: a sandbox that seeded a fixed profile identifier would make the whole
sequence reproducible without touching production ordering semantics. Not attempted
here, and deliberately so, because the wrong repair was nearly committed on the first
reading and the harness is owned elsewhere.

This is worth fixing on its own merit rather than for this campaign: while it stands,
the documentation lane can never be green, and a permanently red lane is one everyone
learns to ignore.

### docs-lane-teaches-an-export-that-cannot-succeed | high | The Modelo 100 export refuses for want of an authoritative value, and the docs teach it as working

Exporting Modelo 100 fails because the export layout has no declared auxiliary version.
Every schema for the modelo makes that block mandatory, no bundled dictionary declares
the rows, and no bundled source carries an authoritative value. The system therefore
refuses rather than inventing a token that would satisfy the schema while asserting
something unverified.

The refusal is correct and is exactly the grounding discipline this project requires.
The problem is that a documentation page teaches this export as a working step, so the
lane fails on a product gap rather than a documentation defect.

Deliberately not silenced. The sequence framework can declare a non-zero exit as
expected, which would turn the lane green while documenting a blocked feature as though
it were intended. That is a content decision for the documentation owner, and taking it
inside a lane-fixing change would hide a real gap behind a green signal.

### ci-full-was-never-observed-past-its-first-gate | high | The lane's later steps hid real debt behind a gate that always failed first

The full-conformance lane had never executed past its lint step in the repository's
history. Five dispatches existed: one reached a runner and died at lint, four recorded
no runner and no steps at all, having been cancelled while queued. Every claim about
this lane's later behaviour was therefore structural rather than observed, including
claims made inside this campaign's own briefs.

Clearing the gates one at a time moved it forward three steps in a single session, and
each newly reachable step revealed real, previously invisible debt:

The lint step turned out to be two checks in sequence, so clearing the first only
exposed the second. Thirty-two unsorted import blocks from a re-export bridge removal,
then four absolute in-package imports, then a dead suppression directive for a rule
enabled nowhere, then four more findings that landed from concurrent work between one
push and the next.

The import-architecture step then broke on four application-to-adapter edges. These
proved to be sanctioned coupling whose exception entries had not followed code that
moved, not new architectural debt.

The typecheck step, reached for the first time, reports seventy-five diagnostics across
more than thirty files, concentrated in one aggregation module. This reproduces
identically outside CI, so it is long-standing debt that no lane was positioned to
surface rather than anything introduced tonight.

The finding is not any individual defect. It is that a gate which always fails at its
first step certifies nothing beyond that step, and the absence of failures downstream
reads exactly like their absence in the code. Three gates deep, the lane is still
finding real work.

### m210-tipo-renta-validator-duplicated-and-unwired | medium | A validator is tested but never called; its logic is inlined at the only call site

The typecheck gate reports a Modelo 210 tipo-renta validator as never accessed. It is
not orphaned: tests exercise it directly, and its own docstring describes it as the
semantic-role fallback for the generic casilla override surface.

That surface does validate, but by inlining the same two steps the function performs -
validate the official code, then project it. So the function duplicates logic that
already exists at its intended call site rather than guarding a gap. Nothing is
currently unvalidated.

Not remediated here. Collapsing the duplication means editing an IRNR validation path,
and the call site also binds the intermediate official code that other fields consume,
so the substitution is not the one-line swap it appears to be. Left for someone with
the modelo context, since a wrong consolidation here changes what the CLI refuses on a
real filing surface.

### semgrep-rules-and-codebase-convention-disagree-on-form | high | An unenforced gate and a parallel convention collided the first time the gate ran

Clearing the typecheck gate let the full lane reach its semgrep step, which had never
executed. It reports thirty-eight blocking findings under two rules: casts in the
domain and application layers, and type-checker suppressions without an inline
justification.

Thirty-seven of the thirty-eight are not undocumented. They carry a formal convention -
a rationale block directly above the line, tagged with a marker naming the case, for
instance a cast rationale explaining that an isinstance check narrows a mapping but
cannot check its type parameters. The convention is in active use: a peer commit added
another instance during this session.

So the gate's intent is already satisfied and its form is not. The suppression rule
wants the rationale on the same line as the directive; the codebase puts it in a block
above. The cast rule bans casts in those layers outright, while the architecture rules
permit a documented third-party boundary cast and ask only that it be justified inline.
The semgrep rule is therefore stricter than the architecture rule it enforces, which is
the same shape as a type checker reporting intra-package private reaches that the
import rules explicitly allow.

The reason this surfaced only now is that the step had never run. The rules were
committed but unenforced, and the codebase developed its convention in parallel without
either side learning of the other.

This needs a ruling rather than a repair, and it is genuinely two-sided. Reformatting
thirty-seven documented sites to carry a second, inline copy of a rationale already
stated above them duplicates the documentation and lengthens lines that already carry
three suppressions. Teaching the rules to accept the established marker convention
keeps one home for the rationale, but relaxes a gate on the strength of what the code
already does, which is the reasoning that lets real debt through.

The four findings this campaign introduced were fixed rather than deferred, so the
count is thirty-eight rather than forty-two. Those four were genuine: two were casts
placed in a layer that bans them, added without checking whether the layer permitted
them.

## Recommendations

Fix the retención defect. It is a real bug on a known surface and is worth closing whether or
not the flag ever changes.

Do not turn the non-blocking flag off on the strength of the failure count alone. The count can
reach zero while the lane remains dependent on a third-party service, and the flag would then be
turned off onto a lane that reddens for reasons no commit caused.

A follow-on decision record must rule on how the calculation lanes obtain foreign-exchange rates
under test. The decision is genuinely contested and is not recorded here: pinning rates to a
committed fixture removes the external dependency but introduces a staleness risk on values that
are regulated inputs, while keeping the live call preserves fidelity and couples the release
verdict to a service nobody here operates. A third position — allowing the live call but
refusing to let its failure count as a test failure — trades a red lane for a silent one, and
the grounding discipline of this project weighs against silence on regulated values. This is an
operator decision, not a bug fix, and it should not be taken inside a defect-closing change.

Do not treat the plan row as closeable by local work. Two of the four blockers require an
environment that does not presently exist, and the row will otherwise be reopened by whoever
next tries to verify it.

Re-measure rather than inheriting the numbers in this document. Both counts here moved
substantially within a single session as peers landed work, and a count taken against an older
tree is not a measurement of the current one.
