---
tags:
  - '#audit'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace canonical-release-pipeline with a kebab-case feature tag, e.g. #foo-bar.
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

# `canonical-release-pipeline` audit: `campaign close honesty review`

## Scope

A fresh reading of the canonical-release-pipeline campaign as if inherited,
asking what is missing, vague, or assumed-but-unverified rather than what was
delivered. Every gate the campaign claims was re-run at the head current when
this review ran, not trusted from the transcript that claimed it.

The campaign closed sixteen of eighteen Steps across seven phases: version
identity, ordering, retirement of the second index lane, marketplace
supersession, the privacy detector, documentation delivery, and test-lane
coverage.

## Findings

### The version reset left the lockfile at the abandoned number

Re-running the packaging suite at current head found the dependency-surface gate
refusing: the lockfile still recorded the pre-reset version for the root
distribution and both companions, while every other declaration had moved to the
zero version. That is the exact abandoned number the campaign exists to make
unmintable, sitting in the file that pins what a build resolves.

Caused by this campaign, and missed by it. The reset commit changed the
declarations and did not re-run the lock; the release suite was run afterwards
and passed, the packaging suite was not. Fixed under the commit subject
`fix(release): re-lock after the version reset, which left the lockfile at the
old number`, and the gate now passes.

The reusable part is the shape of the miss, not the miss itself: a change was
verified against the suite nearest to its intent rather than the suite nearest
to the files it touched.

### Three gate readings were reported that had not actually run

Across the campaign, three separate verification attempts produced a green or
zero-exit signal without executing what was claimed. A marker-filtered selection
matched nothing and exited zero. An exit status was read through a pipe and
belonged to the pipe. A parallel test run reported zero while its workers died
mid-flight.

Each was caught before it reached a record, and two are recorded in the exec
records they nearly corrupted. They share one property worth stating plainly: a
green result and an unrun result cannot be told apart from an exit code alone.
That is the same property the lane-reachability gate now enforces for the
repository, and it was reproduced by hand during the campaign that built it.

### A twenty-four minute suite measured a tree that no longer existed

The documentation lane was re-run serially to escape a worker crash. During
those twenty-four minutes three peer commits landed, one of which added a module
and its stub. The run reported a stub-coverage failure that had already been
fixed by the time it finished.

No action beyond awareness: in a shared worktree a long suite reports on a head
that has moved, so an attribution made from its output must be re-checked
against the current tree before it is believed in either direction.

### The documentation lane is not green, for reasons outside this campaign

Six failures remain in the documentation lane at current head, none attributable
to this work. Two are locale catalogue drift against peer working-tree changes
present since the session began. One is a page-coherence failure where a
documented sequence creates a work unit the command surface now refuses for a
profile without the relevant economic activity. One is a documented-command
conformance failure where an audit sequence cites a verb the live surface does
not provide.

The last two are the same class and need a domain decision this campaign has no
standing to make: which audit verbs should exist, and which profile paths the
documentation should describe. They are reported rather than absorbed, and the
runbook Step does not claim that lane green.

### One Step is genuinely blocked, and its pairing was deliberately broken

The plan paired the documentation delivery workflow with the removal of the
publisher continuous-integration refusal guard, to land together. The workflow
landed; the guard removal did not.

That removal is only safe in the same change that lands the deploy role, and the
role is an operator act that has not happened. Removing the guard alone would
strip a safety property in exchange for nothing, since the workflow still could
not authenticate. The workflow therefore ships inert and refuses instructively,
naming the operator decision that unblocks it, before checking anything out.

### The marketplace mechanism exists but has never run against the real target

Supersession is built, bounded by the unchanged ownership rule, and proven by
mutation against constructed trees. It has never executed against the live
marketplace, which still carries the retired identity with no recorded
publisher.

This is expected rather than a gap, because nothing has been published. It is
recorded so the first publication is understood as the first real exercise of
that mechanism, not as a routine repeat of something already demonstrated.

## Recommendations

Run the suite nearest the files a change touches, not only the suite nearest its
intent. The lockfile finding is the worked example: a version change is a
packaging change regardless of which record motivated it.

Treat any long-running suite result in this worktree as a claim about a past
head. Re-check an attribution against the current tree before acting on it,
including when the re-check is inconvenient because the failure looked like
somebody else's.

Resolve the two documentation-domain failures with the owner of that surface.
They are not release-pipeline defects and no amount of pipeline work will clear
them.

Treat the first publication as the first execution of the supersession
mechanism and of the identity guard against real destinations. Both are proven
against constructed inputs only, which is the strongest proof available before a
publication exists, and weaker than one afterwards.
