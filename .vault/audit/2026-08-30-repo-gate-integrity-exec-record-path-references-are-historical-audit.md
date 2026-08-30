---
tags:
  - '#audit'
  - '#repo-gate-integrity'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:fa72cca6847e1a7f406ea5ad4734222752a805d3198363cc6f519355ed6bf881'
related:
  - "[[2026-08-26-repo-gate-integrity-narrow-step-closes-audit]]"
---

# `repo-gate-integrity` audit: `Exec-record path references are a historical log, not links to repair`

## Scope

Forty-eight audit documents were re-tagged out of a campaign feature tag that had
been used as a general intake, and renamed to match their new features. The rename
verb rewrites incoming `related:` frontmatter automatically; it never touches body
prose, and says so. This audit records the class of reference that was therefore
left dangling on purpose, so that a later link-repair pass does not silently undo
it.

It also records a measurement error made while planning that move, because the
error shape recurs and is cheap to avoid.

## Findings

### exec-record-paths-are-a-log | high | Rewriting an exec record's path references falsifies the record

An execution record's `## Changes` and `## Scope` sections are a mechanical log of
the paths a Step actually touched, one `A`/`M`/`D`/`R` line per path. They are
evidence about a past event, not a navigational index of the present tree.

When a document is renamed, any exec record naming its old path now points at a
name that no longer resolves. The instinct is to repair the reference. That is
wrong: rewriting the line would assert that the Step touched a file under a name
that did not exist when the Step ran. The record would become internally tidy and
externally false, and the falsification is undetectable afterwards because the
repaired line looks exactly like a line that was always correct.

Six such references survive the re-tag and are deliberately left as they are. One
further reference of the same kind sits in a plan Step row's scope list, naming a
document that was held back from the move for an unrelated reason; the same
reasoning applies to it.

The general form: **a reference inside a record of what happened is dated evidence,
and must age with the event rather than track the present.** This separates it from
a cross-reference between two living documents, which should be repaired and was —
two such links were repointed during the same operation.

The hazard is that a dangling reference carrying no recorded justification is
indistinguishable from an oversight. A link check reports both identically, and the
good-faith response to an unexplained dangling link is to fix it. That is why this
finding exists as a document rather than as a note in a chat log.

### blast-radius-measured-in-one-notation | medium | A reference count is only as good as the notations it counted

Planning the move, the cross-document reference burden was measured by counting
double-bracket wiki-links in body prose. The count came back as three, and that
number is what made the operation look cheap enough to approve.

It was wrong. Plans and execution records refer to documents **by path**, not by
wiki-link, and the rename verb rewrites neither. Counted across both notations the
real figure was ten, and the additional seven were concentrated in exactly the
records where repair is forbidden by the finding above. The error was caught before
any document was mutated, by a pre-flight check for collisions with concurrent
work rather than by re-reading the original measurement.

The shape is worth naming because it is not specific to this tooling: **a blast
radius measured in one notation while the references live in several reports a
number that is precise, verifiable, and far too small.** The check is to enumerate
the notations a reference can take before counting any of them, and it costs one
question.

A related instance surfaced in the same operation's verification: a first sweep for
dangling links searched a single vault subdirectory and reported fifteen breaks,
every one a false positive, because the targets were reference, research and
decision documents living in sibling directories. Same defect, opposite direction —
the first count was too small, this one too large, and both came from a probe whose
domain was narrower than its question.

## Recommendations

Leave the six exec-record references and the one plan Step row reference exactly as
they are. Do not repair them, and do not add them to a link-check allowlist that
frames them as debt; they are correct.

Where a link-check surfaces them, the disposition is recorded here. A future check
that wants to suppress them should distinguish references inside a dated record of
past work from references between living documents, and report only the latter.

Before estimating the cost of any rename or relocation across this corpus,
enumerate the notations a reference can take — wiki-link, repository-relative path,
bare stem — and count all of them. A count in one notation is not an estimate.
