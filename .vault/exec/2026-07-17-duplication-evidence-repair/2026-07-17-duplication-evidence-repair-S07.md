---
tags:
  - '#exec'
  - '#duplication-evidence-repair'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
---

# Record an explicit disposition for every observed clone group as cluster-owned, intentional, or advisory residue without treating the count as an elimination mandate

## Scope

- `dev/audit/duplication_dispositions.toml`

## Description

- Record one disposition block per observed clone group, each carrying exactly one classification of cluster-owned, intentional, or advisory residue.
- Record the contributing file locations and a rationale for each group.
- Consolidate one genuinely substitutable group found during triage by deleting a byte-identical redeclared repository protocol and importing the canonical one.
- Reconcile the record against a live scan and gate its coverage.

## Outcome

Every clone group the live scan observes carries an explicit recorded disposition, and the record is machine-checked rather than prose. Two gates bind it: one asserts the declared group inventory reconciles with the blocks and classifications actually present, and one asserts every group the live scan observes is covered by a recorded entry.

The coverage gate asserts coverage, never a count. The governing decision record keeps the clone count advisory, so a count assertion would fight that decision and go red on every genuine consolidation; the record is a superset by design, where a group disappearing is progress and a new unrecorded group is the regression the gate exists to catch.

Triage found one substitutable group rather than an elimination backlog: a single-property repository protocol had been redeclared byte-identically in a ledger command module, and was replaced by an import of the canonical declaration. The disposition record landed in `3cfa5fd65a` and was reconciled and gated in `3f07664375`.

## Notes

This step was the one the originating rescope record explicitly left unclaimed, and it landed after that record was written. Its first form was raised by the plan's close honesty review on three counts: the declared group count disagreed with the blocks present, the record had no consumer anywhere in the tree so its claim could not be checked, and the recorded counts had already gone stale against the live runner. All three are closed at the time of writing: the record now declares an observed-group inventory that reconciles with its contents and documents the one tracked group held above the scan inventory, and both gates named above read the file.

The record is a point-in-time reconciliation by nature. It is kept honest by the coverage gate rather than by the counts, which drift as consolidation lands in peer campaigns.

This record was authored on 2026-07-24, after the work landed, to close the missing-execution-record finding raised by the same review.
