---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S21'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Correct the apply_evidence_split and apply_evidence_classification docstrings to describe the single classified-children writer that ships instead of the removed split-then-patch path, gated on the API stub drift check staying clean

## Scope

- `src/cadrumo/application/ledger/_llm_classification.py`

## Description

- Rewrite the split applier's docstring to describe the single classified-children writer it actually calls, replacing the description of the removed path in which a split was followed by a per-child generic field patch.
- State the guarantee the writer provides, that the parent transition, every classified child, and all events persist in one transaction, so no child can rest split but unclassified or missing its evidence link.
- Correct the neighbouring in-place classifier's docstring, which compared itself to a per-child write the split path no longer performs.

## Outcome

The generated developer reference no longer ships a description of a write pattern this campaign deleted. Both docstrings now describe the shipped code: the split path delegates wholly to the classified-children writer and performs no follow-up patch, while the in-place path does still use the manual-field writer on the parent.

## Notes

The staleness entered when the body was rewired without touching the docstring above it, and two later commits on the same function did not catch it. Both modules are autodoc'd, so the stale text was operator-visible rather than merely internal. The API stub drift check is clean.
