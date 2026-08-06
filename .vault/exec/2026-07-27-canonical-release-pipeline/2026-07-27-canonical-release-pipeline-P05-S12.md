---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:0a002d91c7b9ef1a1a1e8a58bd40d84431b1d7d98366a69d68289dba0ff8558e'
step_id: 'S12'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Widen the privacy scan scope from the tracked tree to tracked plus staged plus untracked-not-ignored files, gate: the same pytest invocation passes with a self-test that plants a violating untracked file in an injectable temporary repository root and asserts the gate reds, proving the extension is not tautological against the real repo state

## Scope

- `dev/quality/tests/test_doc_privacy.py`

## Description

- Widen the scan from the tracked tree to tracked plus untracked-not-ignored files.
- Exclude ignored files, which cannot reach a commit.
- Bound the read size so an accidental artefact cannot stall the gate.
- Prove the widened scan against an injectable root.

## Outcome

Landed in the same commit as the identifier class it scans for.

The previous scan read the tracked tree only, so a file that had never been
added was invisible to it. That gap is not theoretical: this campaign own
records carried an account identifier while untracked, and the gate was green
for the whole period they did. A tracked-only scan can catch that class of leak
only after the commit that introduces it, at which point removal is a history
rewrite rather than an edit.

Ignored files are deliberately excluded. They are not candidates for a commit,
so scanning them would produce refusals nobody can act on.

Gate: the privacy suite passes at nine tests.

Anti-tautology proof: blinding untracked discovery reds both of its tests, one
for fixed tokens and one for shape patterns, against an injectable temporary
root rather than the real tree. Without that the scan would pass because it read
nothing just as readily as because the tree is clean, and those two outcomes
cannot be told apart from the result alone.

## Notes

Honest residual, unchanged from the decision record: a pre-commit hook is
belt-and-braces only, since it is per-clone, absent on a fresh clone, and
bypassable. A continuous-integration checkout materialises no untracked files,
so this extension protects the machines that run the gate rather than the
pipeline. One ungated push remains the window, and only discipline closes it.
