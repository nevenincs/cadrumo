---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-07-17'
body_hash: 'sha256:31e8beea88494a02c93d894a462634c4bc5fc9a59152c0c8159b7efd74690cd6'
step_id: 'S01'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---

# Define the unified internal multimodal evidence-input representation (media kind, bytes-or-handle, content hash)

## Scope

- `src/aeat/application/ledger/_evidence_input.py`

## Description

- Add `EvidenceInput` frozen strict pydantic model: media_kind, mime_type, in-memory `data` (excluded from repr), content_sha256 (validated to equal sha256(data)), evidence/attachment provenance.
- Refuse serialization structurally so decrypted bytes never leave memory.

## Outcome

Landed in commit `983143078`; serialization refusal hardened in `dbf92f608` after review (H1). ruff/ty/pyright clean.

## Notes

Part of Wave W01; reviewed in audit `2026-06-10-llm-evidence-classification-audit` (gate PASS).
