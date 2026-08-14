---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:bc30966b6729080c9b53008858d48232e7c9ca929c2109a2f60724559cfb7f56'
step_id: 'S90'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Run the dedicated harness lane and verify non-vacuity and independent verdict

## Scope

- `justfile`
- `.github/workflows/ci.yml`

## Description

- Run the dedicated verdict end to end and time it.
- Confirm each declared member collects alone before the combined real-proof run.
- Confirm the verdict is a standalone blocking job that no routine lane invokes.
- Diagnose and repair whatever the run reveals about the lane itself.

## Outcome

The lane's mechanics are verified. Each member preflights alone, so a collapsed member surfaces as that member's own empty-collection exit rather than as a green aggregate; the combined pass then runs both proofs outer-serially. Five cases are selected across the two members, and the earlier measurement that routine parallel lanes now deselect all five stands. The verdict is enrolled as a standalone blocking job with no dependency edge, and no routine lane invokes the recipe.

Running it surfaced a real defect in the lane itself, which reasoning about the recipe had not. The verdict died at the global per-test wall ceiling. The member that recursively collects the entire first-party corpus takes minutes by design, measured at seventy-five seconds on a quiet tree and two hundred and seventy-two on a loaded one against a three hundred second default, so under load the default killed a healthy proof and reported it as a harness failure. The combined real-proof pass now carries its own raised ceiling, following the precedent and stated reasoning of the development lane, while the preflights stay on the default because a preflight needing more than the default is doing real work. After the repair the lane completes in one minute forty-one.

## Notes

The lane's content is red for causes outside this campaign. Twenty-one first-party modules genuinely fail collection, traced to a registry authority transition in another campaign that leaves a modelo revision pending review and refuses at snapshot build. That number is itself a repair: before the corpus boundary was corrected, the same proof reported two thousand and ninety-seven, because it was walking a gitignored copy of the whole repository.

So the verdict verified here is that the lane runs the right proofs, in the right isolation, under a ceiling that fits its subject, and reports independently. It is not a claim that the corpus is clean, and the distinction is recorded rather than blurred.
