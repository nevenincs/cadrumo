---
tags:
  - '#audit'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:61629c0dcec78cc40f1ebe3b5a5d9c79c8544fcf5c312fe9384f7e97d695ff0c'
related:
  - '[[2026-09-11-justfile-design-research]]'
  - '[[2026-09-11-justfile-design-adr]]'
  - '[[2026-06-04-just-tooling-bootstrap-adr]]'
  - '[[2026-06-09-justfile-redesign-adr]]'
---
# `justfile-design` audit: ADR corpus and lifecycle-boundary reconciliation

## Scope

This audit reconciles the new justfile design decision against the existing justfile/tooling ADR cluster and checks the research-to-decision boundary. It covers the accepted `just-tooling-bootstrap`, `justfile-redesign`, `ci-lane-deconflation`, and `registry-authority-artifact-boundary` records and the new `justfile-design` research and ADR.

## Findings

### conflicting-public-taxonomies | high | two accepted ADRs governed incompatible command surfaces

`2026-06-04-just-tooling-bootstrap-adr` required `quality` and `quality-audit` surfaces. `2026-06-09-justfile-redesign-adr` replaced those names with an early prefix taxonomy and made the RAG lifecycle a first-class justfile concern. The approved `2026-09-11-justfile-design-adr` replaces both with operator-intent and subject boundaries and removes the RAG justfile cluster. Keeping all three accepted would leave contradictory authorities.

Action applied: both older records were superseded mechanically by `2026-09-11-justfile-design-adr`; their active-sounding introductions and implementation wording were revised to read as historical decisions.

### compatible-ci-determinism | low | CI verdict granularity remains an external constraint

`2026-08-05-ci-lane-deconflation-adr` governs determinism-based verdict granularity rather than the public command taxonomy. It remains accepted and constrains the new subject aggregates without duplicating their names or membership.

Action applied: none.

### compatible-runtime-authority | low | immutable registry publication remains an external constraint

`2026-09-10-registry-authority-artifact-boundary-adr` governs artifact-only runtime consumption and validated publication. It remains accepted. The new design exposes distinct validity, currentness, publication, and exact runtime-loadability questions without changing that underlying authority boundary.

Action applied: none.

### lifecycle-boundary | low | grounding and decision have one home

`2026-09-11-justfile-design-research` carries observed command/code facts and alternatives. `2026-09-11-justfile-design-adr` carries the approved mandates and consequences. The ADR cites its research instead of reproducing locator-level evidence.

Action applied: none.

### implementation-drift | medium | current code still reflects the superseded surface

The justfile and `dev/` tooling still implement the pre-decision taxonomy, overlapping environment convergence, mixed audit/check postures, generic `dev-*` pass-throughs, and the RAG public cluster. This is expected pre-implementation drift and requires one implementation plan; the ADR must not be rewritten to match it.

Action applied: defer rollout to the `justfile-design` plan.

## Recommendations

- Use one plan related to `2026-09-11-justfile-design-adr` for the entire public-surface and tooling-owner migration.
- Preserve `2026-08-05-ci-lane-deconflation-adr` and `2026-09-10-registry-authority-artifact-boundary-adr` as governing constraints in plan verification rather than restating them.
- Make the missing artifact-backed registry runtime-load verdict an explicit plan deliverable.
- Verify after rollout that no superseded RAG or generic command surface remains reachable through aliases, workflows, hooks, or documentation.
