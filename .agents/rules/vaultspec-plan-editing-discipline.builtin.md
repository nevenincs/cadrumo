---
name: vaultspec-plan-editing-discipline.builtin
trigger: always_on
---

# Plan editing discipline: structure through the verbs, prose by hand

## Rule

Treat the plan as one cohesive document. Route every Wave, Phase, and Step
structural mutation through the `vaultspec-core vault plan {wave,phase,step}`
CLI verbs, and author the Description, Parallelization, and Verification prose
sections by direct file edit. Prose and structure may interleave freely: the
serializer preserves authored prose blocks verbatim across structural mutations.

## Rule: verify the whole file after any structural mutation

A structural verb **reserialises the entire plan document** to change one row,
so any defect in the writer rides along into rows you never touched — and
`--dry-run` renders only the intended line, so the preview does not show it.

The procedure that works:

1. Capture the file first: `git show HEAD:<plan> > before`.
2. Run the verb.
3. Diff the **whole file** against that capture — not the dry-run, and not just
   the row you meant to change.
4. Repair any collateral rows to their HEAD bytes.
5. Confirm the staged diff is exactly your row plus the machine-maintained
   `body_hash`, then commit.

## Why

Structural verbs once silently discarded author-written prose sections, forcing
a structure-first ordering; the serializer now preserves them and reports the
preserved block count. Prose *position* may still reflow, because the serializer
re-anchors blocks around the canonical structure on write — review the diff when
section ordering matters.

`--canonicalise` is the explicit opt-in that strips unknown prose blocks. Never
pass it on a plan whose prose you mean to keep.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (finding B6); sibling decision
ADR `2026-05-17-cli-plan-body-preservation-adr`.
