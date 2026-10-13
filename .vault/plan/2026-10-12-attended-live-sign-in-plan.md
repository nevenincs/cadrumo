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
body_hash: 'sha256:71ffa0edb9bf4e22bb7a869cc879c497fb07806d13ddfd39a2de504034d2a6fc'
---

# `attended-live-sign-in` plan

## Description

Approved 2026-10-12. The operator approved `2026-10-12-mcp-parity-attended-live-sign-in-adr` as proposed and asked for its flow to be implemented and proven on the rebuilt package under the current headless logon. That decision governs every Step. The Steps run sequentially in this session; review happens at plan close.

## Steps

- [x] `S01` - Runtime: held human sign-in, MCP attendance request, pending inventory and exact-request decision wired to the authority's delegation with a human parent and no grant; cascade on holder end, sign-out, lock, expiry, stop; `src/cadrumo/application/runtime, src/cadrumo/application/user_profile, src/cadrumo/entrypoints/runtime, src/cadrumo/adapters/local_runtime`.
- [x] `S02` - CLI: `config sign-in hold` (password on --secrets-fd, stdin lifetime and decisions, JSON events) and leaf-proven `config logout` for a non-persisted sign-in; `src/cadrumo/entrypoints/cli/config, src/cadrumo/locales`.
- [x] `S03` - MCP: request attendance when no key and no receipt resumes; admit only the approved attended child; typed refusals otherwise; `src/cadrumo_harness/mcp`.
- [x] `S04` - Docs and governance: separate-storage guide setup/teardown contract, amendments to the four related ADRs; `docs/how-to, .vault/adr`.
- [x] `S05` - Packaged lifecycle proof: rebuild the bundle and prove operator auth, attended MCP reads, review approval, refusals, logout/lock/expiry, runtime stop and no persistence; `dev/runtime_lifecycle, justfile`.

## Parallelization

## Verification
