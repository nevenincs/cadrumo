---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-calculation-truth-registry-modelo-115-construct-workflow-closure-exec]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# Calculation Truth Registry Modelo 115 Construct Workflow Closure Review

## Topic

Review the Modelo 115 construct workflow closure slice against the accepted
calculation-truth-registry ADR.

## Audit Surface

- `registry/aeat/modelos/115.toml`
- `src/aeat/domain/calculations/registry/test_modelo_115_registry.py`
- `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-06-calculation-truth-registry-modelo-115-construct-workflow-closure.md`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Rewrite Scope

This review covers only the Modelo 115 construct, application links, and focused
behaviour tests added in this slice.

## Findings

No blocking findings.

The Modelo 115 construct keeps the filing-grade calculation and workflow
ownership inside the central TOML registry. The tests load the real registry,
validate the modelo, build a real snapshot, calculate the official 19 percent
withholding formula, and assert the emitted legal trace references. They do not
encode previous implementation state or migration progress.

## Residual Work

Live sanitized fixtures and old-authority teardown remain open Modelo 115 rows
before wave completion.
