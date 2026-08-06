---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:80fea9488d66d784fdd1d1f0da0ed03baa5ec20fd4128abb20d643ff77cd48ba'
step_id: 'S13'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Preserve the occupied-by-a-file refusal message and its positive control through the materialiser rewrite, gated by the existing test asserting both the path substring and the occupied-by-a-file diagnosis appear

## Scope

- `src/cadrumo/core/config.py`

## Description

- Preserve the occupied-by-a-file refusal message and its positive control through the materialiser rewrite.

## Outcome

Landed in commit `d05e564cbf`; the refusal message string is verbatim-preserved through the rewrite. Gated by the existing test asserting both the path substring and the occupied-by-a-file diagnosis.

## Notes
