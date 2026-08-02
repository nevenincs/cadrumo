---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:abc899c511d91b2219bbc9542cb7f9f26155a6482cf8a7090fff5c1b95f2cf52'
step_id: 'S03'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Rewrite the publication authority header comments that still promise an operator opt-in variable and an approval click, replacing them with the guard set that actually gates the run, and pin the corrected prose so the described gate and the enforced gate cannot drift apart again, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes with an assertion that the header names no approval click and no opt-in variable

## Scope

- `.github/workflows/publish-release.yml`
- `dev/release/tests/test_publish_release_workflow.py`

## Description

- Rewrite the workflow header to state that no human gates the run, and to enumerate the mechanical guard set that does: the all-destination version-identity authority, per-run identity verification, per-asset sha256 verification, the derived blocking evidence set, the leak sweep, the supersession preflight, and the reversible-first destination ordering.
- State in the header why `environment: release` survives, so a later sweep removing the gate does not remove the OIDC trust anchor with it.
- Rewrite the Gate 3 job comment, which described the environment as protected by operator required-reviewers.
- Add `test_the_header_describes_the_gate_that_actually_runs` and its positive control.
- Rewrite the `_COMMAND_POSITION` rationale comment flagged forward by S02, whose stated reason had been deleted with the retired job.

## Outcome

The gate reports 96 passed. The header now describes the guard set that runs, and the description is pinned rather than trusted.

The matcher was validated against the real original header recovered from the parent commit, where it caught two affirmative gate claims: the "inert until the operator opts in" sentence and the "Gate 1 (opt-in)" sentence. As with S02, the control is the actual removed prose rather than a synthetic one.

## Notes

The first version of this assertion was wrong and is worth recording, because the failure was instructive rather than mechanical. It banned the vocabulary outright, asserting `"approval click" not in header`. That immediately red on the new header, correctly: the clearest sentence the header can carry is the NEGATION, "there is no approval click and no opt-in variable", and a substring ban forbids exactly the sentence a reader most needs while still permitting a paraphrase that affirms the gate. The ban would have pushed the prose into silence about the change it exists to explain, and I would have been editing honest prose to satisfy a weak matcher.

The fix was to the matcher, not the prose: the check is now sentence-scoped and negation-aware, so it asks whether the header CLAIMS a human gates the run rather than whether it uses the words. Its positive control plants a restored gate claim, an honest negation, and an environment-survives sentence, so a matcher that rots into either "matches nothing" or "matches every mention" is caught.

One in-scope correction beyond the Step text. The old header cited a vault ADR stem, which the Code Stands Alone mandate forbids in source and configuration: vault documents cite code, never the reverse. Since S03 rewrites that exact block, the citation was dropped and the constraint it referenced is now stated directly. Removing it was in scope precisely because leaving a known violation inside lines I was authoring anyway is how such a violation acquires a second owner.
