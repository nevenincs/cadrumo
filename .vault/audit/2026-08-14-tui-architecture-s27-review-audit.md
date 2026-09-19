---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d201c9e99b8af1eccbe4cb70d98ee10448b97059648f2bda50baf408493a75ae'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `S27 terminal lifecycle review`

## Scope

Independent read-only review of `W02.P05.S27` against accepted ADR decisions
D2, D3, and D5, the architecture research, the S24-S26 contracts and audits,
the production supervisor, journal, lease, cleanup, and persistence adapters,
and the complete `test_supervisor_lifecycle.py` integration module. Semantic
RAG remained under the recorded offline waiver. No production, test, plan,
execution-record, index, branch, commit, or worktree mutation was made by this
review.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW product finding remains open.

The six terminal conditions are exercised through the production supervisor
with legal independent effects: `SUCCEEDED` with `UPDATED`, `REFUSED` with
`PARTIAL`, `FAILED` with `UPDATED`, `CANCELLED` with `NONE`, `TIMED_OUT` with
`PARTIAL`, and `INTERRUPTED` with `UNKNOWN`. Each case owns a real open file,
holds its asynchronous close, and proves that neither a terminal journal event
nor `await_terminal` completion occurs before cleanup. The final durable
snapshot, terminal event, and receipt retain the requested effect.

The cleanup-error and cleanup-timeout cases separately prove that terminal
persistence is refused and the real journal remains nonterminal. The test uses
real encrypted operands, filesystem journal and lease adapters, and production
cleanup authority. It introduces no fake, mock, stub, patch, monkeypatch,
`skip`, `xfail`, mirrored validator, or test-owned business logic. Its scope and
execution record explicitly do not claim the later S94 or S95 exhaustive
phase, resource, process-tree, reaping, and deadline matrix.

Environment evidence, not a product finding: an earlier default-worker rerun
timed out while two stale copies of this exact pytest lane remained alive with
near-zero CPU. After their owner removed both verified stale process trees, the
required uncontended sequential command with `-n 0` passed all eight tests in
3.82 seconds and left no matching pytest, Python, or uv process. This isolates
the earlier timeout to shared worker-topology contention rather than silently
treating it as passing evidence or reproducing it as a supervisor defect.

Scoped Ruff check and format check pass. Scoped BasedPyright reports zero
errors, warnings, or notes. Feature-scoped markdown hygiene reports no S27
execution-record diagnostic. The repository-wide Vault check exits zero; its
shared warnings remain outside this S27 product verdict.

## Recommendations

Accept `W02.P05.S27` as PASS. Preserve the explicit `-n 0` focused-lane
boundary when collecting closeout evidence on the shared worker topology, and
leave S94 and S95 open for their separately commissioned exhaustive coverage.
