---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S15'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# implement RAG service daemon process control recipes

## Scope

- `justfile`

## Description

- Implemented `env-rag-start` to start the background `vaultspec-rag` HTTP service daemon on loopback port 8766.
- Implemented `env-rag-stop` to stop the background daemon.
- Integrated `check-rag` into `env-doctor` to provide local workstation health verification.

## Outcome

RAG service start/stop commands are exposed and verify daemon processes correctly.

## Notes
