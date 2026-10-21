---
tags:
  - '#plan'
  - '#attended-live-sign-in'
date: '2026-10-12'
tier: L1
related:
  - '[[2026-10-12-mcp-parity-attended-live-sign-in-adr]]'
modified: '2026-10-13'
body_schema: body-v2
body_hash: 'sha256:d021269dfb8b4c8304ef7642bdae8b607d1d7aaed20e14f6398d00e2eef43921'
---

# `attended-live-sign-in` plan

## Description

Approved 2026-10-12. The operator approved `2026-10-12-mcp-parity-attended-live-sign-in-adr` as proposed and asked for its flow to be implemented and proven on the rebuilt package under the current headless logon. That decision governs every Step. The Steps run sequentially in this session; review happens at plan close.

On 2026-10-13 the operator asked for the plan-close review findings in `2026-10-13-attended-live-sign-in-audit` to be fixed. S06 carries those fixes within the same decision. Each fix implements a constraint the decision already states, so no amendment is needed.

## Steps

- [x] `S01` - Runtime: held human sign-in, MCP attendance request, pending inventory and exact-request decision wired to the authority's delegation with a human parent and no grant; cascade on holder end, sign-out, lock, expiry, stop; `src/cadrumo/application/runtime, src/cadrumo/application/user_profile, src/cadrumo/entrypoints/runtime, src/cadrumo/adapters/local_runtime`.
- [x] `S02` - CLI: `config sign-in hold` (password on --secrets-fd, stdin lifetime and decisions, JSON events) and leaf-proven `config logout` for a non-persisted sign-in; `src/cadrumo/entrypoints/cli/config, src/cadrumo/locales`.
- [x] `S03` - MCP: request attendance when no key and no receipt resumes; admit only the approved attended child; typed refusals otherwise; `src/cadrumo_harness/mcp`.
- [x] `S04` - Docs and governance: separate-storage guide setup/teardown contract, amendments to the four related ADRs; `docs/how-to, .vault/adr`.
- [x] `S05` - Packaged lifecycle proof: rebuild the bundle and prove operator auth, attended MCP reads, review approval, refusals, logout/lock/expiry, runtime stop and no persistence; `dev/runtime_lifecycle, justfile`.
- [x] `S06` - Fix the plan-close review findings: expired attended leases refuse as session expired, the holder sees the asking program's path, a refused approval restores the recipient's client id, an ended approval makes no unclaimed ask, logout tries the stored sign-in before the password, and the attendance bounds are tested; `src/cadrumo, docs/how-to`.
- [ ] `S07` - Resolve the S06 re-review findings and read the asking program's path on Linux and macOS, then rebuild the bundle and rerun the packaged proof; `src/cadrumo, docs/how-to, build/windows-x64/stage`.

## Parallelization

None. One session executed the Steps in order, each building on the last; other sessions sharing the worktree owned none of these paths.

## Verification

Each Step closes on its own focused tests, lint and type checks, recorded in the ledger. Plan acceptance is the packaged proof `just verify-live-sign-in build/windows-x64/stage/Release/app` exiting 0 on a rebuilt bundle, with the expiry and reviewed-operation steps included; synthetic-login integration tests are not acceptance evidence. Desktop persisted sign-in stays a separate check that needs an interactive desktop logon.
