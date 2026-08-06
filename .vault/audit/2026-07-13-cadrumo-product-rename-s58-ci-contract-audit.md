---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s58-ci-contract'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:991540be795d736d435fe514be7ce32ffbd5cac34b6ce830b3cd5114e8641bcb'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s58-ci-contract` audit: `Cadrumo product rename S58 CI contract audit`

## Scope

Independent formal review of commit `a822222b8a3db1689c67ef51c2e6840f9a51bc1a`
against the binding product-name authority and the reopened `W05.P11.S58`
contract. The review covered exact human-CLI commands, rejection of a second
human executable, former product import/package/source identities, production
workflow preservation, real-behaviour tests, quality gates, record truth, plan
state, and commit path isolation.

## Findings

### former-identity-gate-is-enumeration-incomplete | medium | The structural gate permits prohibited former import and package identities outside its short token list

The test claims to reject former product distribution, import, package, and
source identities, but its blacklist recognizes only six literal fragments.
For example, `from aeat import ...`, `uv pip install aeat`, and
`uv run --package aeat ...` are former Python package or distribution uses that
would pass the new loop. The exact `aeat` registry-command equality correctly
protects the two allowed human-CLI invocations, so the remaining product surface
can be checked contextually without treating every authority-owned or executable
token as forbidden. As committed, however, the durable gate does not prove the
full rejection asserted by the execution record.

### execution-scope-omits-the-only-implementation-path | low | The record scopes the production workflow although the commit changes only its structural test

The execution record Scope names only `.github/workflows/ci.yml`, while the
production workflow is intentionally untouched and the sole implementation
change is `dev/packaging/tests/test_ci_workflow.py`. The Description, Outcome,
and Notes accurately explain that no production edit was needed, but the formal
scope does not identify the path that actually closes the reopened defect.

## Recommendations

Verdict: **FAIL** until the former-identity test recognizes contextual Python
import and distribution/package forms beyond the current literals and the
execution Scope names the actual test surface.

The implementation state otherwise passed review. The production workflow is
unchanged by the target commit, retains `Cadrumo CI`, the Cadrumo-owned job and
`src/cadrumo/`, and invokes exactly
`uv run --no-sync aeat app registry verify --json` and
`uv run --no-sync aeat app registry audit-oracles --json`. The new executable
position check rejects `cadrumo` as a human command. Both integration tests
passed against the real YAML; direct YAML parsing, Ruff lint, Ruff format, Ty,
and scoped whitespace checks passed. The commit is isolated to the execution
record, plan checkbox, and structural test; it does not modify production CI,
documentation, release tooling, or other workflows.
