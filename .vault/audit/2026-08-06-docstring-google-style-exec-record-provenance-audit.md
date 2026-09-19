---
tags:
  - '#audit'
  - '#docstring-google-style'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:9d0f8ffd075251e0e058925b07f8e9352acce40597d74c37e7994ee1253c414b'
related: []
---
# `docstring-google-style` audit: `993 of 994 execution records are empty scaffolds from a single unrelated commit`

Written by the reviewer of a different campaign, which reached this feature by measuring a
tree-wide pattern. The finding is about the record, not the work, and this campaign's own
disposition is left to its owner.

## What was measured

    .vault/exec/2026-06-09-docstring-google-style/    994 records
      empty Outcome                                    993
      of those, ALSO empty Description                 993
    .vault/plan/2026-06-09-docstring-google-style-plan.md
      steps checked                                994 / 994
      steps unchecked                                    0

All 993 carry an empty `## Description` as well as an empty `## Outcome`. The only populated
sections are the heading and the Scope, both machine-filled from the Step row.

All 993 are dated `2026-07-10`, and a 40-record sample resolves to a single creating commit —
`0ba49df077`, **"reconcile architecture corpus and eliminate stale authorities"**, whose
subject describes something else entirely. The records were generated as a side effect of an
unrelated landing.

## What the campaign actually is, which changes the disposition

Every one of the 994 records carries the identical heading `verify docs`. That first reads as
994 copies of one step, but the plan rows disambiguate: each names a distinct file —
`locales/manager.py`, `locales/cli.py`, `locales/_fstring_registry.py`, and so on.

So this is a legitimate mechanical shape: **one verification step per file, 994 files.** The
campaign is a sweep, not 994 independent pieces of work.

**That matters, because it makes both remedies unavailable for a different reason than
elsewhere.** For a verification step, the expected outcome on most files is *nothing to
change*. A step that verified a file and found its docstrings already conformant produces no
commit, so:

- **Reconstruction from commits cannot work even in principle** for the majority of these
  steps, because most of them should have no commit. Absence of a commit is the expected
  result of a successful verification, not evidence the verification did not happen.
- **Unchecking is worse here than for a change-producing campaign.** It would assert that a
  verification did not occur, when the only artefact a successful verification leaves is the
  record itself — which is precisely what is missing.

The two failure modes compound: the campaign's evidence lived only in the records, and the
records were never authored.

## Disposition

**Recorded as accepted debt with a reason, which is one of the two dispositions the reviewing
campaign's gate allows.** The 993 are not adopted, and the reasons are:

- They belong to this campaign, and a CI-lane campaign has no standing to rewrite them.
- Their remedy does not exist. Reconstruction is impossible for a verification sweep whose
  successful steps produce no commits; fabrication from the step text is barred; and
  unchecking asserts something unestablished.

**What a reader of this campaign's plan should understand:** 994 of 994 steps are checked, and
for 993 of them the only evidence that the verification occurred is the checkbox. The work may
well have been done — a docstring sweep leaves little else behind — but the record does not
establish it, and no available operation makes it establish it retroactively.

## The tree-wide context, so this is not read as isolated

Measured across the whole exec tree, records that closed a Step with an empty Outcome:

    993  docstring-google-style          204  semantic-dedup-epic
     47  profile-lifecycle-cli            34  centralized-output-redaction
     11  emit-envelope-schema-burndown   ~1321 total across 15 features

**Deliberately excluded, and this must not be corrected upward later:** a further 1776 records
carry no `## Outcome` section at all. That is an older template rather than an unfilled one.
Anyone re-measuring will find 1776 + 1321 and should not report ~3100.

`semantic-dedup-epic` carries the same signature — 204 wholly-empty records, single date,
single creating commit — and is recorded separately. Two campaigns, one mechanism: **exec
records generated in bulk after the fact so that checked steps had files to point at.**

## What would change this

A gate refusing to check a Step whose exec record has an empty Outcome would prevent the next
instance, and would have prevented both of these. That is a decision for whoever owns the
harness rather than for this audit, which records the state rather than proposing the remedy.
