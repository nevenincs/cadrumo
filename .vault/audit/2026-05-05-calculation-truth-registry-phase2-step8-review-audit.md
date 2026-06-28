---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step8-exec]]'
---



# `calculation-truth-registry` Code Review

PHASE2-008 | LOW | Workflow JSON input shape is explicit

The review checked that the default workflow input provider no longer accepts a
root-level casilla object. Inputs must be scoped by modelo and period before the
filing draft builder receives them.

PHASE2-008 | LOW | Behaviour test covers accepted and rejected shapes

The review checked that adapter tests exercise a valid modelo/period input file
and rejection of root-level casilla payloads without local filing schemas.

PHASE2-008 | LOW | Workflow summaries match the strict schema

The review checked that the engine no longer casts multilingual dictionaries
into `WorkflowStep.summary`. The workflow schema declares a strict string and
the engine now writes a string.

PHASE2-008 | LOW | Workflow draft protocol carries registry schema identity

The review checked that workflow builder and preflight protocols now operate on
a registry-backed draft protocol with `schema_version`, and that the engine
aborts when the built draft does not match the resolved obligation identity.

No critical, high, medium, or low implementation defects are open for this
batch. Remaining workflow work is to continue engine, model, protocol, and
broader workflow tests against registry snapshots.
