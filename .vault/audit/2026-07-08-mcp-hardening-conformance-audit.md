---
tags:
  - '#audit'
  - '#mcp-hardening-conformance'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:dcab15e2dcab73266872d77035fa6de78960caf7fdab1bc9025f792aa30119ef'
related:
  - "[[2026-07-08-mcp-hardening-conformance-plan]]"
---

# `mcp-hardening-conformance` audit: `conformance close: step-to-commit evidence + exec-lineage rationale`

## Scope

Closure record for the `mcp-hardening-conformance` plan (17 steps, L2, 3 phases). All
17 steps are implemented, tested green before commit, and landed on
`chore/eliminate-shims` with explicit-pathspec commits. This audit is the execution
evidence of record in lieu of per-step exec records, because the vaultspec exec CLI
requires a same-feature ADR and this feature deliberately has none (see the lineage
finding below). It provides the step-to-commit mapping the
`plan-closure-requires-exec-records` rule requires so the steps can be marked complete
with auditable backing.

## Findings

### exec-lineage-no-same-feature-adr | low | the conformance plan grounds in existing ADRs, so per-step exec records cannot be CLI-scaffolded

The conformance plan is grounded in the two EXISTING accepted ADRs it remediates:
`2026-07-08-mcp-progressive-discovery-adr` (its P2 discovery-quality gaps, closed by
plan phases P02/P03) and `2026-07-08-mcp-protocol-hardening-adr` (its H3 declared-risk
model, closed by phase P01). Per the Fable adjudication that scoped this work, the
conformance remediation is CONFORMANCE DEBT under those two ADRs and does NOT warrant a
new architectural ADR — only the sibling identity-linked-operation feature was net-new
and got its own ADR. The `vaultspec-core vault add exec` lifecycle check requires an ADR
in the SAME feature as the plan, which this feature does not have, so per-step exec
records cannot be scaffolded through the CLI. This close audit records the execution
evidence instead, satisfying `plan-closure-requires-exec-records` via its close-audit
clause.

### step-to-commit-evidence | low | all 17 steps map to landed, tested commits

- P01.S01-S06 (declared per-command risk table + no-silent-default + write-policy parity
  gates; leaf-frozenset deletion): commit `057744c473`. The D7 lazy-import regression it
  introduced in `operator_surface._classification` was fixed in `347ee6ec0d` (imports
  lifted to module level, no cycle).
- P02.S07-S09 (hybrid command index: per-column BM25 + model2vec RRF fusion; quickfile
  outcome aliases; pinned retrieval golden set): commit `2ecf6ed0b5`.
- P02.S10-S12 (`describe` meta-tool; search overflow signal; server wiring): commit
  `f47ad9bd74`.
- P03.S13-S17 (long-tail discovery prose; toolsets/describe cross-refs; toolset
  non-empty gate; `--provider` enum fidelity; schema-fidelity tests): commit
  `48b1e0d77e`.

Each commit was verified green (focused suites + relevant conformance gates) before
landing and used explicit pathspec, leaving the busy shared worktree's peer WIP intact.

## Recommendations

- Mark P01.S01 through P03.S17 complete against this evidence (done at close).
- Two conformance-adjacent follow-ups surfaced during execution are tracked outside this
  plan: the `config.reset --scope` enum-fidelity gap (same class as the `--provider` fix)
  and the pre-existing M347-readiness `lifecycle_contradiction` failures (owned by the
  readiness surface, not this plan).
- No new conformance ADR is warranted; the two existing ADRs remain the authority.
