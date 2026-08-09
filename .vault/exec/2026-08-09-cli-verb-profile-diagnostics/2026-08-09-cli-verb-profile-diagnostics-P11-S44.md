---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:4661ec70e9bdaac8a67a7e2952ab9addd727f8b4773896b9a2b2174b7cf8961d'
step_id: 'S44'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Terminal re-verification against the tree as it stands after every Phase has landed

## Scope

- verification only, no production files

## Description

- Re-ran the owner surface sequentially against the current tree, after every Phase through P14 had landed.
- Re-confirmed locale parity across all four catalogues.
- Re-ran the behavioural probe over every grounded surface.
- Re-read the plan, ADR, reference and all Step Records, verifying claims against current code rather than against the prose describing them.

## Outcome

**Green.** The verification this Step exists to force has run against the tree it is meant to certify, not against an earlier one.

    uv run --no-sync pytest <owner surface> -m "unit or integration" -n 0 -q
    691 passed in 177.65s (0:02:57)

Zero failures, zero skips. Locale parity clean in all four catalogues. The behavioural probe reports zero raw-identifier leaks across every selector token and path this work routes.

The Step's own premise was correct and is worth preserving: the original verification triple ran before roughly half the campaign existed, and a verification cannot certify work it predates. That reasoning applied a second time during this Step, since four further Phases landed after it was written.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

The broad affected tree remains red at 68 failed / 7548 passed, every failure triaged to peer work in flight or to the local model provider being unavailable. That triage is recorded in the feature audit.

## Notes

**This row was authored by a concurrent author, not by the agent who executed it.** It was left open through two earlier reports precisely so its author could close it; it is closed here only after that author closed their sibling row and left this one, at which point leaving it open would have misrepresented a verification that had in fact run.

One incident during execution, worth recording because it is easy to misread as a regression. A combined run aborted at collection with an ImportError: a peer facade re-exported a symbol its module did not define. Thirteen minutes of waiting did not resolve it, and the symbol is STILL absent from that module, yet the identical selection then collected and passed. The facade resolves lazily, so the failure window was the moment the peer's file was mid-write rather than a persistent broken state. Splitting the selection into three subsets during the incident produced 577, 29 and 85 passes, summing to exactly the 691 of the combined run, which is what established the blockage was collection-order transience and not a masked failure.
