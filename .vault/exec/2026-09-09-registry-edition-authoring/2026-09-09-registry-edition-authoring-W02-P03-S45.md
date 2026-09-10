---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8bb017947bc953b70fe66671ee46ae4c843bcaffa4aaf437257479fbb4b0aec1'
step_id: 'S45'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [L | opus-medium] Audit the thirty-six direct callers of the directory loader before the materialiser lands, because every one of them changes what it sees. Twenty-two are in the product tree and fourteen in development tooling, and three of those publish or validate generated trees — so whether a caller should observe declared or inherited rows is a real decision with a wrong answer. Classify each: correct with inherited rows, requires declared rows and needs a distinct accessor, or indifferent. Proof: every caller carries a verdict, and any that requires declared rows has one before the materialiser lands.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `.vault/adr/2026-09-09-registry-edition-authoring-adr.md`
- `M` `.vault/plan/2026-09-09-registry-edition-authoring-plan.md`

## Notes

Audit only; no loader file changed. The caller inventory grounds the materialiser step and is held in session scratch.
