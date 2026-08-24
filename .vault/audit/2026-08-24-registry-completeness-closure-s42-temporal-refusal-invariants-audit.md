---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:543681e9c9d68c94cdbe422da6232a107ca2f466eedce8cb87bb55cf8a3b0919'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `S42 temporal refusal invariant review`

## Scope

Independent review of S42’s `TemporalRevisionCoverage` coordinate typing, filing-year bounds, refusal branches, authority-error handling, and regression proof.

## Findings

### branch-specific-refusal-invariants | medium | Public temporal rows accept contradictory refusal coordinates

`TemporalRevisionCoverage` requires a code and detail for every refusal, but it does not encode the facts that distinguish the five declared branches. Direct construction accepts `selected_revision_mismatch` and `snapshot_revision_mismatch` with `selected_revision=None`, and accepts `declared_grade_snapshot_refused` without either a selected revision or a declared authority grade. Those states cannot arise from the composer’s intended boundary sequence and make a public report row misstate what evidence was actually reached. The composer’s real-authority mutation tests cover all five outcomes and the typed `ModeloId`, `RevisionId`, `RegistrySelectorPeriodCode`, and 2000–2099 filing-year coordinates align with the existing snapshot-reference contract; this finding is limited to branch-specific refusal invariants.

## Recommendations

Implement W01.P02.S44 before the derived report is published: validate each refusal code’s required and forbidden selected-revision and authority-grade state, then add direct construction refusals and a mutation-bite proof for the validator.
