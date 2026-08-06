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
