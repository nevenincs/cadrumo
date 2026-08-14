---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0718369e123698782e4b2219fca4e9360dc03b19f58f9d2f473e737bfbb6edcd'
step_id: 'S101'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Derive the first-party corpus boundary from the tracked-file authority instead of a directory name list

## Scope

- `src/cadrumo/tests/test_every_test_module_is_collectable.py`

## Description

- Replace the hand-listed excluded directory names with the repository's own record of tracked files.
- Derive the discovered roots and the discovered module list from that one query.
- Hold the collection subprocess to the same boundary by excluding untracked directories nested inside tracked roots.
- Keep the planted-sample controls working, including the carve-out that stops an intended target excluding itself.

## Outcome

The proof now measures this repository rather than whatever happens to sit beside it. A concurrent campaign had copied the entire tree into an ignored scratch directory that was absent from the name list, so the collector walked the copy and reported two thousand and ninety-seven uncollectable modules against a true first-party figure of twenty-one. Roots resolve to the three real source trees and the module count is three thousand one hundred and seventy, the small reduction against a filesystem walk being untracked files the walk had counted as first-party.

The same defect ran in the opposite direction and mattered more: the plausibility floor that exists to catch an empty corpus could have been satisfied by a scratch copy alone, so the anti-vacuity control was itself defeatable.

## Notes

The module's own prose had warned against a hardcoded list of included roots while carrying a hardcoded list of excluded ones. The rot is symmetric, and only one direction had been seen.

An intermediate version of this fix failed open on the platform it runs on. The exclusion query was written through a text-mode pipe, which rewrote each line ending and left every path but the last carrying a trailing carriage return that matched no ignore rule, so almost nothing was reported as excluded. It was caught because the control ran rather than because the code was re-read, and the query is now byte-oriented and separator-explicit.

The first-party question is now asked once, in the module that already owned it, rather than answered independently in two places with two different tools and two different granularities.
