---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:5cf7e4a8b8f9cb84752bfa54b2b22902e9c1401eb6041fcb931822ac1ec34dfc'
step_id: 'S08'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Migrate the export family help, risk, and cleartext handoff-risk metadata to the accepted grammar with equal classification for both purposes

## Scope

- `src/cadrumo/application/operator_surface/_risk_table.py`

## Description

- Declare `config.profile.subject_access_request` as `handoff=True` in the operator-surface risk table, matching `config.profile.export`.

## Outcome

Both purposes emit the same portable profile bundle — equally readable cleartext once it leaves the vault — so they now carry equal cleartext handoff-risk classification. The operator-surface classification-parity suite and the subject-access CLI test pass. Committed in `85f19b6e52`.

## Notes

The risk grammar exposes only the `handoff` axis for this concern; no separate cleartext field exists, so equal classification is a single equal flag.
