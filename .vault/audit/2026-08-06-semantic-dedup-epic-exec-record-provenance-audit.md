---
tags:
  - '#audit'
  - '#semantic-dedup-epic'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:11dde14cbb9a564463b653f42e933981bde02de710aaa0c00d54b61198828468'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---
# `semantic-dedup-epic` audit: `204 of 239 execution records carry no authored content at all`

Written by the reviewer of a different campaign, which reached this feature through a plan row
scoped to it. The finding is about the record, not about the work.

## What was measured

    .vault/exec/2026-06-13-semantic-dedup-epic/          239 records
      genuinely authored                                  35
      no authored content whatsoever                     204
    .vault/plan/2026-06-13-semantic-dedup-epic-plan.md
      steps checked                                    239 / 239

**"Empty Outcome" understates it.** Of the 204, every single one has an empty `## Description`,
an empty `## Outcome` and an empty `## Notes`. The only populated sections are the `# heading`
and the `## Scope`, and both of those are machine-filled by `vaultspec-core vault add exec`
from the originating Step row.

So these are not records missing a section. They are scaffolds containing nothing a human
supplied — the entire content is the Step's own text, mechanically restated.

## When they were created

The 35 authored records are dated 2026-06-13 (8), 2026-06-14 (23) and 2026-07-04 (4), spread
across the campaign's working period, and carry substantial outcomes — one documents a
full-space equivalence probe over 0..99,999,999 with 0 mismatches.

**All 204 unauthored records are dated 2026-08-02 and were created in a single commit:**
`253aeab859`, "docs(vault): record semantic dedup execution", at 09:21:51.

That is the shape of a retro-scaffold: steps already checked, records generated afterwards in
one pass so that each checked step had a file to point at.

## Why the outcomes cannot be reconstructed

`plan-closure-requires-exec-records` permits reconstructing a record from a verifiable commit
— that is legitimate and was done elsewhere in the reviewing campaign. It is not available
here. Three instruments were tried and all three fail, for reasons that are properties of the
records rather than of the effort:

- **Date-constrained resolution is worthless**, because the date on these records is their
  SCAFFOLD date. Constraining to 2026-08-02 returns that day's unrelated commits; the first
  pass "resolved" `579fe525de` ("feat(cli): extend operator command contracts") as the
  implementing commit for a Google-credential dedup step. Confidently wrong.
- **Path resolution is ambiguous.** 114 of the 204 match multiple same-day commits, and the
  scope paths have been touched by several later campaigns, so `git log -- <path>` returns the
  most recent toucher rather than the implementer.
- **Symbol resolution is unavailable.** The headings are prose, and **zero** of the 204 carry a
  backticked identifier anywhere in their body — because their bodies are empty. There is no
  symbol to trace.

**0 of 204 can be reconstructed from a verifiable commit.**

## Why unchecking them would also be wrong

The natural remedy — uncheck every step whose record cannot be evidenced — asserts that the
work was not done. Spot-checks contradict that:
`entrypoints/cli/_config/_google_credential_source_payloads.py` exists and carries
canonical-validation code; `adapters/outbound/storage/_factory.py` carries the whitespace
normalisation its step describes.

So the code changes appear present. **Unchecking would replace an unevidenced record with a
false one**, at scale, in a plan this reviewer does not own.

## Disposition

Neither branch of fill-or-uncheck is correct here, and the honest position is the one neither
branch expresses: **the steps' completion is unevidenced, not disproven.**

- Filling from commits is impossible — 0 of 204 resolve.
- Filling from the step's own description is barred, and would be worse than the emptiness: an
  empty section is visibly incomplete, a fabricated one is not.
- Unchecking asserts incompleteness the tree contradicts.

**So the record stays as it is and the defect is recorded here instead.** A reader arriving at
any of the 204 should understand that its emptiness is not an oversight to be filled in later,
but the visible trace of records generated after the fact — and that the work they describe
does appear to have landed, on the evidence of the tree rather than of the record.

## What would actually settle it

Per-step evidence exists only in the campaign's own commit history, and recovering it means
someone who was present reconstructing the mapping, or a commit-by-commit walk of the
campaign's working period matched against 204 step descriptions. That is a substantial piece
of work and it should be a decision rather than a default.

**The one thing that should not happen is the emptiness being quietly filled by anyone
inferring outcomes from step descriptions.** That would convert a visible, honest gap into 204
records that read as verified and verify nothing — and unlike the current state, it would be
undetectable.
