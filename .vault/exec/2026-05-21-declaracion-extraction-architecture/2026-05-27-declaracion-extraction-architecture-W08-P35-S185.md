---
step_id: S185
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-27-declaracion-extraction-architecture-audit]]"
---

# declaracion-extraction-architecture W08.P35.S185 — untrack .vault-scratch/ and add gitignore pattern

## Outcome

Commit `6dc1dd0bd`.

## Actions

- `git rm --cached` removed `.vault-scratch/checkpoint-post77.txt` and `.vault-scratch/checkpoint-post81.txt` from tracking (the `.json` sweep file was already not tracked at execution time but would have been ignored by the new pattern).
- Added `.vault-scratch/` blanket ignore pattern to `.gitignore` in the "Scratch / ad-hoc workspace / temp" block, alongside the existing `scratch/*` entry.
- Also added `tmp_*/` pattern to complete the family.

## Verification

- `git check-ignore -v .vault-scratch/bound_casilla_sweep.json` → `.gitignore:263:.vault-scratch/` confirmed ignored.
- `git status --short | grep vault-scratch` → no output; no tracked entries remain.

## Verdict

Confirmed: `.vault-scratch/` is untracked and gitignored. The `audit_docs_via_vaultspec_only` memory rule is now enforced by the gitignore layer.
