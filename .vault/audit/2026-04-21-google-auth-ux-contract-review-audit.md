---
tags:
  - '#audit'
  - '#google-auth-ux'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-google-auth-ux-research]]'
  - '[[2026-04-21-google-auth-ux-adr]]'
---

# `google-auth-ux` Code Review

contract-001 | HIGH | The two-path contract still leaves ADC as an undefined hidden branch inside the Desktop OAuth story
The research correctly rejects ADC as a first-class operator path, but the ADR keeps "any required supporting ADC acquisition" inside the Desktop OAuth flow without defining when that branch is entered, what exact message must announce it, or whether it is blocking for CLI, MCP, or both. That gap recreates the current operator problem in a subtler form: Kent is told there are only two paths, yet the implementation still has room to open an unexpected gcloud/ADC sub-flow with different browser prompts and success conditions. The contract should explicitly state when ADC is required, which surfaces depend on it, and what wording is allowed so ADC cannot re-emerge as an implicit third path.

contract-002 | HIGH | Mixed-state drift detection is required, but the contract never defines the deterministic resolution rules
Both documents say mixed state must be handled explicitly, but neither one specifies the actual precedence or failure policy when both path families are configured, when inactive-path artifacts are present, or when one path is partially healthy. Without a normative resolution table, CLI, bootstrap, MCP, and doctor can each make different choices while still claiming ADR compliance. The UX contract needs explicit rules for path selection, blocking versus warning behavior, and the single remediation shown for each mixed-state case.

contract-003 | HIGH | The single-entrypoint decision does not say what happens to the existing auth commands and recipes that already carry conflicting copy
The research identifies current command names and messages as part of the problem, but the ADR only introduces a future guided entrypoint. It does not say whether `just bootstrap`, `just gcloud-auth`, `just gsuite-oauth-client`, `aeat oauth-client init`, and related surfaces become deprecated wrappers, hard redirects, or unsupported internals. If those legacy entrypoints continue to exist without a contract for their messages, the repo can still ship conflicting auth narratives even after the new scaffold lands.

contract-004 | MEDIUM | The verification scaffold is reviewer-driven, not executable enough to catch future docs/runtime drift
The documents are strong on human walkthrough criteria, but they stop short of requiring executable verification of resolver truth, active-path diagnosis, and doctor output across the named drift scenarios. Since the research explicitly identifies prior docs-vs-runtime divergence as the core failure mode, the contract should require automated acceptance coverage or fixture-based message verification for path selection, stale-config handling, CLI-ready/MCP-not-ready splits, and final doctor summaries. Otherwise this remains a one-time review standard rather than a durable anti-drift mechanism.

contract-005 | MEDIUM | The ADR weakens the message contract relative to the research by collapsing browser behavior and success criteria into broader buckets
The research requires every guided step to state browser side effects and what success looks like explicitly. The ADR compresses that into four questions and leaves browser outcome and success evidence implicit inside "Evidence." That is a real loss of specificity for the exact auth flow elements Kent is most likely to find surprising. The contract should preserve explicit browser-expectation and success-signal requirements rather than assuming implementers will infer them from a broader category.
