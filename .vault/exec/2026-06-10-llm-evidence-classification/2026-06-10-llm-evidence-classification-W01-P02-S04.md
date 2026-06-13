---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S04'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Add the cloud-upload consent-gate posture to central Settings (default-off, re-affirmed per invocation, gestor-barred)

## Scope

- `src/aeat/core/config.py`

## Description

- Add `aeat_evidence_cloud_upload_permitted` (default False) and `aeat_evidence_gestor_mode` Settings fields for the cloud-upload consent posture.

## Outcome

Commit `bf6bf3d88`.

## Notes

Part of Wave W01; reviewed in audit `2026-06-10-llm-evidence-classification-audit` (gate PASS).
