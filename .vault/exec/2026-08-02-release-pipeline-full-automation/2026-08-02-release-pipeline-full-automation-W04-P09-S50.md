---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:d3fe4e0896f07ffa142fb0f947c867474b3828f59f0d22b615290c40baed52c6'
step_id: 'S50'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Reconcile the plan Verification claim that a tree-wide search for the retired apply target matches only vault records and history, either by rewording the bump module docstrings that reference it or by narrowing the claim to the operator-facing surfaces it actually means, gate: rg -n release-apply over the tree matches only vault records, CHANGELOG history, and the conformance test asserting its absence

## Scope

- `dev/release/version_bump.py`
- `.vault/plan/`

## Description

- Reworded all 11 literal `release-apply` mentions in `dev/release/version_bump.py`
  (module docstring, `See Also` cross-reference, 6 function docstrings, 2
  inline comments) to "the retired manual bump checklist" / "the retired
  manual bump justfile recipe" -- paraphrases that preserve the genuine
  explanatory value the honesty review credited (mapping each new function
  onto the numbered step of the checklist it replaces) without the literal
  retired command token. Fixed one incidental mention in
  `dev/release/tests/test_version_bump.py`'s comments the same way.
- Reconciled the plan's own `## Verification` section bullet (previously
  "`rg -n CADRUMO_PUBLISH_ENABLED` and `rg -n release-apply` over the tree
  match only vault records and history") to state the narrower, now-true
  claim: `rg -n release-apply` matches vault records, `CHANGELOG.md` history,
  and the justfile-guidance conformance test asserting the recipe's absence
  -- explicitly narrower than "vault records and history" alone, with the
  reason stated (docstrings describe the checklist by paraphrase now, not by
  name). Chose reword-the-docstrings-AND-narrow-the-claim over either alone,
  since the Step's own gate text already specified the narrower target set.
- Left `W02.P03.S12` and `W04.P07.S33`'s own historical gate text unchanged
  (they correctly described their OWN narrower, already-satisfied claims at
  landing time -- the justfile only, and `CADRUMO_PUBLISH_ENABLED` only --
  neither needed correction).

## Outcome

Gate green: `rg -n release-apply` over the tree (scoped sweep over
`*.py`/`*.md`/`*.yml`/`*.yaml`/`justfile`/`*.json`, excluding `.venv`) matches
exactly three non-vault lines: `CHANGELOG.md:505` (history) and three
assertions in `dev/release/tests/test_justfile_release_guidance.py` (the
conformance test asserting absence). `uv run --no-sync pytest
dev/release/tests/test_version_bump.py dev/release/tests/test_justfile_release_guidance.py -q`
passes 33/33. `uv run --no-sync ruff check dev/release/version_bump.py
dev/release/tests/test_version_bump.py` clean.

## Notes

None.
