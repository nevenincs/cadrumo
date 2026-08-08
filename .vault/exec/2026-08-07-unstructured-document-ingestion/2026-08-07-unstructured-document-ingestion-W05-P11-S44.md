---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6962cbd5d2b19b473a1b8a36f141429faf9433894996e25fc78abfc1ab985069'
step_id: 'S44'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec: `W05-P11-S44`

## The amendment

`2026-08-06-llm-package-split-adr` gains a `## Partial supersession of D5
(2026-08-08)` section, in the same commit as the gate it rules on. D5 is
`accepted` AND was executed, so a reader arriving without the note sees a ruling
in force while HEAD carries its reversal.

The note separates three things rather than declaring D5 superseded wholesale.
What returns, over the in-memory HTTP providers only: the consent predicate, the
capability, the two deployment settings, and a per-invocation off-host
acknowledgement at the CLI. What stands permanently: the subprocess CLI-agent
family, its probe and its builder set, plus the prohibition on any file-writing
transport and any sticky enablement. What is unchanged: the on-host production
default, the gestor bar, per-invocation rather than stored consent, and
provenance recording.

The stamp consequence D5 authorised is the half that did not survive, and the
note says so explicitly, because that is the part with teeth: an apparatus built
on the collapsed axis would survey for a value that can no longer be assumed.

## The sibling record was stale in the opposite direction

The governing ADR's consolidated supersession note names a second record needing
the same follow-up, and it was still uncorrected.
`2026-06-10-llm-evidence-classification-adr`'s own "Partial supersession
(2026-08-07)" section states that D5 deleted the consent apparatus outright so
the cloud exception "no longer exists in the tree". True of D5 alone; false once
the reinstatement landed. Amending only the package-split record would have left
the corpus self-contradictory in the other direction -- one record saying the
exception is gone, another saying it returned.

Added as a dated follow-up rather than by rewriting the prior section: that
section was true when written, and reading it as an error would misdescribe the
corpus. Both notes together are the history; either alone is wrong about HEAD.

## The amendment is not self-executing, and the code it rules on landed with it

Grepping source for prose describing the old state found three sites still
asserting the collapsed axis as current, one of them as a positive instruction
to code authors. All three corrected in the same commit rather than deferred,
since "the ADR says X" is not evidence X is true of the tree.

One item is genuine implementation debt rather than stale prose and is carried
as its own row instead of being fixed here:
`application/ledger/_llm_classification.py:_transport_from_provenance` hand-rolls
the stamp grammar as `provenance.split(":")[1]`, which yields
`<transport>-<reader>` -- `local-text`, not `local`. The canonical parser splits
on the first hyphen. The audit payload's `provider` key therefore carries
transport and reader glued together, and with off-host reads reinstated it will
read `openai-text-extract`. Pre-existing, and made consequential by the
reinstatement rather than by this change.

## Verification

    uv run --no-sync vaultspec-core vault check all
    14/14 checks clean, exit 0

The 1174 warnings are the corpus-wide "plan has no references to research
documents" advisory across every plan; none is attributable to either edited
record. Both edits went through `vaultspec-core vault set-body` with
`--expected-blob-hash`, so frontmatter and the `modified:` stamp are
CLI-maintained.
