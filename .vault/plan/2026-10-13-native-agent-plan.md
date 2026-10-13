---
tags:
  - '#plan'
  - '#native-agent'
date: '2026-10-13'
tier: L1
related:
  - '[[2026-10-13-native-agent-adr]]'
modified: '2026-10-13'
body_schema: body-v2
body_hash: 'sha256:679a06a7c46a47f6280f46ee09748c56a5cc1ff73a0752073ee679571cfa1e66'
---
# `native-agent` plan

Complete native dependency integration, then standardize agent integration verification around the built custom environment.

## Description

Approved 2026-10-13. Authorization is the owner's direct CMake integration brief and subsequent instruction to use Luna max reviews and Sol 6.1 consolidation and implementation. The accepted native-agent decision settles acquisition, build, dependency and test-environment ownership. Existing native dependency integration is under verification; these Steps preserve the remaining work and reviews. Provider secrets, consent and live model calls are outside this record's scope.

## Steps

- [ ] `S01` - Verify the native agent dependency lifecycle and the deployed package with its own interpreter; `native/cmake/Agent.cmake`.
- [ ] `S02` - Review developer agent lanes with Luna max and persist the developer ruling report; `.tmp/agent-environment-review/dev-review.md`.
- [ ] `S03` - Review runtime and entrypoint agent tests with Luna max and persist the runtime ruling report; `.tmp/agent-environment-review/runtime-review.md`.
- [ ] `S04` - Review the MCP harness and agent environment contracts with Luna max and persist the harness ruling report; `.tmp/agent-environment-review/harness-review.md`.
- [ ] `S05` - Consolidate the reviews and refine canonical environment corrections with Sol 6.1; `.tmp/agent-environment-review/action-plan.md`.
- [ ] `S06` - Standardize developer agent execution and verification lanes through Sol 6.1 implementation; `dev/agent_eval/`.
- [ ] `S07` - Standardize runtime and MCP agent tests through Sol 6.1 implementation; `src/cadrumo_harness/`.
- [ ] `S08` - Rebuild and verify the canonical package, required gates and integrated review; `native/tests/agent_smoke.py`.

## Parallelization

S01 must verify the installed package before reviews start. S02, S03 and S04 may run concurrently with Luna max: each reviewer owns only its named Markdown report under .tmp/agent-environment-review. They inspect developer lanes, runtime/entrypoints, and the MCP harness respectively, including governing rulings. Reports follow README.md in that directory. S05 uses Sol 6.1 to consolidate them and refine concrete corrections. S06 and S07 may run concurrently with Sol 6.1 only after disjoint source ownership is assigned from that report; the root owns shared CMake, justfile, pytest configuration, governance, checks and commits. Workers are not alone and must preserve other edits. S08 waits for all corrections and evaluates the stable integrated package.

## Verification

Only the CMake-built app interpreter and its custom site-packages establish agent/runtime/MCP product acceptance. Runtime consumers and test runners consume the private agent from that package; CMake alone acquires, builds and installs it. Verify native source and wheel checksums, exact compatible dependency closure, package interpreter and import origins, actual installed versions and inventoried bytes. Exercise install/uninstall/rebuild through their CMake owners. Preserve unchanged build outputs or verified copies for test inputs.

Developer tooling fixtures and source-level checks do not establish product acceptance. Distinguish their failures from defects in the deployed package. The root runs covering tests and required code, registry and test gates once per relevant change, retaining exact exit statuses. Review reports name locators, reproducible triggers, observed evidence, required behavior and owning corrections. Final review must resolve critical/high findings and rerun affected canonical verification; pending live-provider or desktop prerequisites are reported explicitly without fabricated passes.
