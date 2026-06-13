---
tags:
  - "#plan"
  - "#google-auth-ux"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-google-auth-ux-research]]"
  - "[[2026-04-21-google-auth-ux-adr]]"
  - "[[2026-04-21-google-auth-ux-contract-review-audit]]"
---

# `google-auth-ux` `phase-1` plan

Implement the phase-1 Google authentication UX scaffold by establishing one guided operator entrypoint, converging diagnostics and readiness reporting on deterministic path rules, rewriting Kent-facing auth guidance around the accepted two-path contract, and blocking rollout on executable verification plus explicit audit gates.

## Proposed Changes

- Establish one guided Google-auth entrypoint as the only normal setup path for human operators, with explicit sequencing for `Desktop OAuth local-dev` and `Service-account automation`.
- Classify every existing auth-facing command and recipe as either the primary entrypoint, a redirecting compatibility wrapper, a documented subordinate step, or an internal-only surface so legacy copy can no longer drift independently.
- Define one authoritative path-resolution and readiness model for CLI, bootstrap, MCP, and `aeat doctor`, including mixed-state precedence, ignored inactive-path artifacts, and partial-success splits.
- Rewrite help text, bootstrap guidance, env guidance, and success or failure messaging so each step explains purpose, required input, browser behavior, success evidence, and the exact next command.
- Add executable checks and review gates that lock the UX contract to runtime behavior and prevent recurrence of docs-versus-resolver drift.

## Tasks

- `Phase 1 — guided auth entrypoint and legacy command disposition`
  1. Define the phase-1 guided-entrypoint contract for both supported auth paths, including where any ADC-dependent work remains a labeled subordinate step rather than a third operator choice.
  2. Map the end-to-end step order for env setup, credential import or validation, token acquisition, MCP readiness, bootstrap readiness, and final diagnostics so the operator journey is owned by one flow.
  3. Inventory the current auth commands and recipes and assign each surface to one disposition: primary entrypoint, redirecting compatibility wrapper, documented sub-step, or internal implementation detail.
  4. Set the migration and deconfliction rules for legacy names and messages so no standalone auth surface keeps contradictory setup claims after the guided flow lands.

- `Phase 2 — path-aware diagnostics and deterministic resolution rules`
  1. Define the canonical resolution table for single-path, dual-path, stale-artifact, missing-artifact, and split-readiness states across CLI, bootstrap, MCP, and `aeat doctor`.
  2. Standardize the readiness vocabulary and remediation policy for blocking, advisory, ignored, partial-success, and success states so every auth surface reports the same truth.
  3. Reshape the diagnostic contract around explicit active path, CLI or bootstrap readiness, MCP readiness, inactive-path drift, and one exact next remediation step.
  4. Ensure the guided flow and any retained wrappers consume the same path-selection rules and labels instead of reinterpreting auth state independently.

- `Phase 3 — docs, help, and message rewrites`
  1. Rewrite the top-level Google-auth narrative so the repo consistently explains why Google auth exists and presents exactly two supported operator paths.
  2. Update command help, onboarding copy, bootstrap guidance, and env-facing instructions so each step answers purpose, action, source, browser expectations, success signal, and next command.
  3. Remove or replace ADC-first and one-command bootstrap claims that contradict runtime behavior, while making any remaining ADC acquisition an explicitly named subordinate step with bounded scope.
  4. Make CLI or bootstrap readiness and MCP readiness separate named outcomes in all user-facing success and failure surfaces.

- `Phase 4 — executable verification and audit gates`
  1. Add scenario-backed verification for active-path selection, mixed-state precedence, stale-config handling, and CLI-ready versus MCP-not-ready and MCP-ready versus CLI-not-ready outcomes.
  2. Add message and help-surface checks that assert the two-path contract, the required readiness labels, and the redirect behavior of retained legacy wrappers.
  3. Define the operator walkthrough and contract-review gates that must pass before the UX scaffold is considered ready for broader implementation work.
  4. Require the final phase evidence to include green local quality gates, explicit diagnostic proof for the active path, and updated execution or review records for any unresolved residual risk.

## Parallelization

The critical path is mostly sequential. Phase 1 and Phase 2 must settle the operator contract and resolution rules before broad message rewrites can be trusted. Phase 3 can begin once the entrypoint sequence and readiness vocabulary are stable. Phase 4 can be scaffolded in parallel with the later part of Phase 3, but the final verification and audit gates depend on the rewritten surfaces and deterministic rules being complete.

## Verification

Mission success requires all of the following:

- one guided auth entrypoint is clearly identified as the normal operator path, and every retained legacy command has an explicit disposition
- the repo presents exactly two supported auth paths everywhere user-facing copy appears
- ADC, if still required, is framed only as a subordinate step inside the relevant path and never as a third peer choice
- CLI, bootstrap, MCP, and `aeat doctor` share one deterministic path-resolution model and one readiness vocabulary
- `aeat doctor` and related diagnostics make the active path, CLI or bootstrap readiness, MCP readiness, inactive-path drift, and next remediation step explicit
- no user-facing surface implies that CLI or bootstrap success automatically proves MCP readiness
- scenario-backed verification catches mixed-state drift, stale inactive-path artifacts, and partial-readiness splits
- help and documentation checks catch regressions that would reintroduce contradictory path narratives or misleading legacy wrappers
- the final UX scaffold passes an operator walkthrough and a follow-up audit without requiring the operator to infer hidden prerequisites from source code
