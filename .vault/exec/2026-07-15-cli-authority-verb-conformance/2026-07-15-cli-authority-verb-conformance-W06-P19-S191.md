---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:d0a06720ed9b3eb1a44d5e67895f4a31999669c83de2100ea79a542654009a0e'
step_id: 'S191'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run four-locale catalogue and rendered-help coverage for every changed path

## Scope

- `src/cadrumo/locales/tests/`

## Description

Run four-locale catalogue and rendered-help coverage for every changed path.

## Outcome

SATISFIED for the locale catalogue suite, with a repo-level honesty-ratchet failure recorded
against a concurrent campaign.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider src/cadrumo/locales/tests`.
Collected 60, 60 passed, exit line `60 passed in 108.30s`, exit code 0, at HEAD `1844ef2ea0`.

## Notes

The four-locale translation honesty ratchet lives outside this directory and is red at HEAD:
the Catalan catalogue carries one key identical to English, a manager-flow section title, against
a ceiling of zero. That key belongs to the concurrent manager-flow campaign, not to this feature.
It is recorded here so the green result above is not read as proof that all four catalogues are
honest, and it is carried into the unrelated-failure record under S208.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Re-measurement at HEAD bc80aa2808

SATISFIED. Command: `uv run --no-sync pytest src/cadrumo/locales/tests/`.
Collected 53, 53 passed, exit line `53 passed in 38.72s`, exit code 0, at HEAD `bc80aa2808`.
Count differs from original (53 vs 60); tests were added and removed across intermediate
commits but the suite is entirely green at this HEAD.
