---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e0d820b69e0bf6642ac613751a378c29c8a7af9a3efd58dc48ca4904bbfc4b9e'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `registry-completeness-closure` audit: `S42 temporal refusal invariant review`

## Scope

Independent review of S42’s `TemporalRevisionCoverage` coordinate typing, filing-year bounds, refusal branches, authority-error handling, and regression proof.

## Findings

### branch-specific-refusal-invariants | medium | Public temporal rows accept contradictory refusal coordinates

`TemporalRevisionCoverage` requires a code and detail for every refusal, but it does not encode the facts that distinguish the five declared branches. Direct construction accepts `selected_revision_mismatch` and `snapshot_revision_mismatch` with `selected_revision=None`, and accepts `declared_grade_snapshot_refused` without either a selected revision or a declared authority grade. Those states cannot arise from the composer’s intended boundary sequence and make a public report row misstate what evidence was actually reached. The composer’s real-authority mutation tests cover all five outcomes and the typed `ModeloId`, `RevisionId`, `RegistrySelectorPeriodCode`, and 2000–2099 filing-year coordinates align with the existing snapshot-reference contract; this finding is limited to branch-specific refusal invariants.

## Recommendations

Implement W01.P02.S44 before the derived report is published: validate each refusal code’s required and forbidden selected-revision and authority-grade state, then add direct construction refusals and a mutation-bite proof for the validator.
