---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:43350875b9cb73de49019840631ce5866a7aa4adf16935ab826c2c9ad9d55c62'
step_id: 'S802'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# Introduce OutputLanguage StrEnum with members ES, EN, CA, HU at canonical home `src/aeat/core/external_constants.py`. Rebase SUPPORTED_OUTPUT_LANGUAGES to frozenset of OutputLanguage

## Scope

- `DEFAULT_OUTPUT_LANGUAGE to OutputLanguage.ES. Sweep ~200 consumer sites`
- `skip locale yml and normative-corpus json (data`
- `not control flow). One atomic commit. Tag relocation:OutputLanguage`
- `src/aeat/core/external_constants.py`

## Description

## Outcome

## Notes
