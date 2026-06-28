---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-calculation-truth-registry-modelo-180-workflow-linkage-exec]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# Calculation Truth Registry Modelo 180 Workflow Linkage Review

## Topic

Review the Modelo 180 annual-summary workflow linkage slice against the accepted
calculation-truth-registry ADR.

## Audit Surface

- `registry/aeat/modelos/180.toml`
- `src/aeat/domain/calculations/registry/test_modelo_180_registry.py`
- `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-06-calculation-truth-registry-modelo-180-workflow-linkage.md`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Rewrite Scope

This review checks only the Modelo 180 registry workflow-linkage change and its
focused behaviour tests.

## Findings

No blocking findings.

The Modelo 180 changes keep legal and workflow truth in the central registry
TOML file. The new tests exercise current registry loading, snapshot selection,
Modelo 115 source-period relation resolution, calculation execution, and
fail-fast missing-observation behaviour. They do not compare against a prior
implementation state, encode migration metadata, or use compatibility shims.

## Residual Work

Live filed-data discovery and sanitized fixture capture remain open Modelo 180
rows. Completion remains blocked until those rows, old-authority teardown, and
the model-wide quality gate close.
