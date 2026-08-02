---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:eff45f1a81c73eeea4ea828d0c1ea6b03fbf440b236758d7f887f752ad70b6b9'
step_id: 'S53'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Pin the polarity of the bump rehearsal-versus-real branch and the resume identity comparisons rather than their vocabulary

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/tests/test_release_orchestrator_workflow.py`

## Description

- Replace the inline rehearsal/real ternary with an explicit if/else assigning a `bump_mode` array, so the branch-to-flag mapping is parseable rather than merely present.
- Add `bump_polarity` / `assert_bump_polarity`, extracting which branch emits which flag.
- Add the mutation control that applies the exact inversion and asserts the gate reds.
- Do the same for the resume identity comparisons, capturing the OPERATOR alongside the expected value, with its own inversion control.

## Outcome

486 passed across `dev/release/tests`, the derivation suite, `dev/ci/tests`, and `dev/deploy/tests`.

Proven the way the reviewer proved the defect, by mutation on the real file rather than by argument: inverting the branch in `.github/workflows/release-orchestrator.yml` in place now reds two tests. Before this change the same inversion left the entire suite green. The file was restored immediately afterwards and `git diff --numstat` reports 15 insertions and 1 deletion - this Step's change alone, with the shipped polarity confirmed as `true -> --dry-run`, `else -> --push`.

## Notes

The finding is correct and it is the third instance of one pattern in my work, which is the part worth recording rather than the individual bug.

The old assertions were three independent substring presences: `--dry-run` appears, `--push` appears, and the condition text appears. Every one of those remains true when the two flags are swapped, so the test could not distinguish the correct wiring from its exact inversion. It read as a polarity check and was a vocabulary check.

The severity is what makes this worth fixing while it is not broken. `dry_run` defaults to true, so an inverted branch means a REHEARSAL pushes a real version bump and tag - the single irreversible act this whole design exists to gate - while a real dispatch never lands its version. A rehearsal is precisely what an operator runs first, and precisely when they are least expecting a permanent effect.

Two changes, not one. The workflow now uses an explicit if/else rather than a ternary, because the ternary was readable to a human and structurally opaque to a test; a mapping cannot be asserted against an expression whose branches are not separable. And every polarity assertion now carries a mutation control that applies the real inversion, because a polarity check that has quietly stopped checking polarity is indistinguishable from a correct one - which is exactly how the original survived.

The resume identity comparisons got the same treatment at lower severity. The parser captures the operator as well as the value, so flipping `=` to `!=` - which turns each check into accepting exactly what it was written to refuse - now reds rather than passing a vocabulary scan.

## Instrument note

`bash -n` fed through stdin reported a false syntax error on the new block. Writing the same block to a file and checking it reports OK, and the block is well-formed on inspection. The stdin path was the unreliable instrument, not the code; the file-based check is what this record relies on.
