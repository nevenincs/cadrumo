---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S281'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Resolve the seven unallowlisted tokens reddening the period combined-string gate at HEAD

## Scope

- `src/cadrumo/tests/`

## Description

- Reproduce the reported red at current HEAD rather than inheriting it, and
  find the gate already green.
- Attribute the repair to the peer commit that landed it, and read that
  commit's diff rather than its subject.
- Prove the repair's blanket path bucket is load-bearing for fourteen real
  sites, and separately prove it defeats the four text-scoped sibling rules
  whose stated reasons claim they still discriminate.
- Replace the unscoped bucket with the union of the three generated shapes it
  legitimately covers, keeping every real site allowlisted.
- Add a discrimination proof carrying a scan-corpus floor and a hostile-input
  probe, and mutation-check both.

## Outcome

SATISFIED, with the red resolved by a peer and its side effect repaired here.

The seven tokens no longer red the gate. Measured, not assumed: the gate was
re-run at HEAD and exited `1 passed in 27.13s` with 1 case collected, where
the prior record had it at `1 failed in 44.75s`. The repair landed one day
earlier in a peer commit whose message states the reasoning; the tokens were
allowlisted rather than removed, which this gate's design explicitly permits.

That repair introduced a defect this Step then owned. It allowlisted every
year-qualified quarterly token anywhere under the sequences tree by PATH
alone, with no text scope. Two probes established what that cost, each run
against the shipped module rather than reasoned about:

- The bucket is genuinely load-bearing. Removing it surfaces 14 findings
  across 8 capture files, and NONE of those files is named by any narrower
  sibling rule. So it could not simply be deleted.
- It nonetheless made four sibling rules vacuous. Those rules scope by text
  and their reasons claim a genuine token appearing elsewhere in the same
  capture still fails. Presenting a period INPUT on a line those rules do not
  match, in a file they name, the shipped allowlist returned allowed while the
  narrow rules alone returned refused. The claim was false.

The replacement scopes the bucket by text to the three shapes the captures
actually carry: the generated work-unit display-name field, its tab-separated
text render, and the canonical export filename. Verified to hold both ends at
once — 0 findings across the full corpus, the benign display name still
allowed, the period input refused.

The new discrimination proof asserts a scan-corpus floor above 500 files and
probes both a benign and a hostile line. Mutation-checked in both directions
rather than trusted on a green run: removing the text scope fails it on the
hostile probe, and collapsing the corpus to three files fails it on the floor.
Without those two proofs the test would carry no more information than the one
it supplements.

Gates at HEAD `26df176d16ee22107b14d0fcd8043bcf04e0ab18`:

- `uv run --no-sync pytest src/cadrumo/core/tests/test_period_combined_string_gate.py -n0`
  collected 2 cases and exited `2 passed in 42.43s`.
- `ruff check` and `ruff format --check` returned `All checks passed!` and
  `1 file already formatted`.

## Notes

The failure shape is this campaign's signature one in a new register, and
worth naming precisely. Every recurrence so far has been a gate asserting a
property of a set it never proves is non-empty. This is the inverse: a gate
whose subject IS proven non-empty, but whose exemption list quietly grew wide
enough to admit the thing it exists to refuse. The green is identical in both
cases, and in both cases the surrounding prose still claims discrimination
that no longer exists.

Recorded because it changes what an anti-vacuity floor has to cover. A floor
on the corpus would not have caught this — the corpus was intact and the scan
ran over every file. What was needed is the hostile-input probe: an assertion
that a known-bad line is still refused. Any gate carrying an exemption list
needs that probe alongside its floor, otherwise the exemption list is
unmeasured.

No peer work was disturbed. The gate module carried no uncommitted change, and
the mutation proofs ran against an in-memory rebinding rather than an edit, so
no peer could observe a transient red.
