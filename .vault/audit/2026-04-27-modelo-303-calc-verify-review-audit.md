---
tags:
  - '#audit'
  - '#modelo-303-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-modelo-303-calc-verify-research]]'
  - '[[2026-04-27-modelo-303-calc-verify-adr]]'
  - '[[2026-04-27-modelo-303-calc-verify-plan]]'
  - '[[2026-04-27-modelo-303-rule-delta-reference]]'
  - '[[2026-04-27-modelo-303-l1-anchor-waiver-reference]]'
---

# `modelo-303-calc-verify` Code Review

M303-326-001 | MEDIUM | Unrelated dependency lockfile upgrades are mixed into the ruleset change
`uv.lock:1581`, `uv.lock:1767`, `uv.lock:2152`, `uv.lock:2684`, and `uv.lock:2984` upgrade `pathspec`, `prek`, `python-multipart`, `sse-starlette`, and `typer` without any corresponding `pyproject.toml` dependency change or issue-326 rationale. This creates avoidable supply-chain and reproducibility drift in a tax-ruleset PR: reviewers cannot distinguish Modelo 303 behavior from fresh third-party package changes, and future CI/local failures could be caused by packages that are unrelated to 2026 M303 calc verification. Remove the lockfile churn or document and test the dependency bump as an intentional separate change.

M303-326-002 | LOW | Vaultspec RAG MCP server is removed from local project configuration
`.mcp.json:27` through `.mcp.json:39` now keeps only `vaultspec-core` in `_vaultspecManaged` and removes the `vaultspec-rag` server. That is outside the Modelo 303 implementation scope and weakens the local research/tooling setup used by this vaultspec workflow. Restore the removed MCP server unless this PR is intentionally decommissioning it with a separate rationale.

M303-326-003 | LOW | Execution summary records a stale focused-test count
`.vault/exec/2026-04-27-modelo-303-calc-verify/2026-04-27-modelo-303-calc-verify-summary.md:77` says the focused command produced `174 passed`, but the reviewed command collected and passed 175 tests after the current changes. The executable evidence is green, but the persisted execution record is off by one and should be corrected so future audit readers can reconcile the exact verification run.

## Review Notes

No blocking correctness defect was found in the 2026 Modelo 303 ruleset, extractor registration, synthetic extractor/generator round-trip, citation coverage, L1 waiver framing, CLI import path, or mutation-harness coverage. The implementation keeps 2024 and 2025 behavior stable while adding `modelo_303.2026` with year-scoped formula IDs and a 2026 effective window.

Focused verification run reviewed:

`uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_303_2026.py src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py src/aeat/adapters/inbound/declaracion/test_modelo_303_v2025.py tests/integration/test_kent_workflows.py::TestKentImportsModelo303Declaracion src/aeat/domain/formulas/test_registry.py src/aeat/domain/formulas/test_cli.py src/aeat/domain/formulas/test_smoke.py`

Result: `175 passed`.

Citation audit reviewed:

`uv run aeat audit rulesets citations`

Result: all rulesets, including `modelo_303.2024`, `modelo_303.2025`, and `modelo_303.2026`, reported 100 percent computed-casilla citation coverage.

Residual risks: full gates (`just lint`, `just typecheck`, `just test`, `just hooks`, `just test-cov`) were not run during this review; public BOE/AEAT legal-source freshness was reviewed through the supplied grounding docs rather than re-browsed; the L1 path remains intentionally waived, so real completed-public-PDF extraction evidence is not present.

## Resolution Notes

- M303-326-001: accepted with explicit execution-record rationale. The dependency lockfile changed because the issue handoff mandated `uv sync --all-groups --upgrade` and `uv lock --upgrade` during bootstrap. Full gates passed after the lockfile update.
- M303-326-002: fixed. The `vaultspec-rag` MCP server entry was restored in `.mcp.json`.
- M303-326-003: fixed. The execution summary now records the reviewed `175 passed` focused rerun and the later post-documentation `167 passed` focused run.
