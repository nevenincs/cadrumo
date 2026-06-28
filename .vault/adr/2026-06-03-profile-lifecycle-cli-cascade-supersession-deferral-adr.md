---
tags:
  - '#adr'
  - '#profile-lifecycle-cli-supersession'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-16-profile-lifecycle-cli-plan]]'
  - '[[2026-06-03-profile-lifecycle-cli-cascade-supersession-adr]]'
  - '[[2026-06-04-profile-lifecycle-cli-supersession-research]]'
---

# `profile-lifecycle-cli-cascade-supersession` adr: 2026-05-18 cascade-closure variant superseded by 2026-05-16 canonical execution plan | (**status:** `accepted`)

## Problem Statement

The `2026-05-18-profile-lifecycle-cli-plan` and its companion `2026-05-18-profile-lifecycle-cli-adr` were authored to resolve four remaining architectural questions left open by the `2026-05-16-profile-lifecycle-cli-adr`:

1. Engine cutover (P02.S20/S21) — clarifying how `WorkflowState` moves into the active-bucket database.
2. Crypto cutover (P03.S27–S33) — specifying the `ContextVar`-backed session-scoped master-key resolution.
3. CI surface gate (P08.S65–S69) — defining realistic CI coverage on a no-PR factory-direct worktree.
4. NIST passphrase floor — adding 8-character minimum validation to `FileFallbackMasterKeyProvider._resolve_passphrase`.

The 2026-05-18 ADR and plan represent a genuine narrowing of scope: the plan's 69 original steps (across P01–P08 in the 2026-05-16 version) were decomposed into two tracks — the 47 steps of the canonical 2026-05-16 execution, and the 17 remaining cascade-closure steps split into the 2026-05-18 variant. The two plans were briefly pursued in parallel by different agents.

However, the two-plan split created a coordination problem: both plans reference overlapping model changes, field migrations, and test fixtures. The 2026-05-16 plan achieved higher fidelity and broader team consensus during execution, and the decision point to unify on that variant arrived naturally during review. The 2026-05-18 variant was later archived with its step evidence; it is structurally superseded as an execution surface, not a current implementation brief.

## Supersession Statement

The `2026-05-18-profile-lifecycle-cli-plan` is **explicitly superseded** by the `[[2026-05-16-profile-lifecycle-cli-plan]]` (the canonical execution plan that landed its 47 steps and continued to absorb the profile-axis work). The four architectural questions the 2026-05-18 variant addressed remain useful as historical reference, but they are not active executor instructions unless a later accepted ADR or plan re-enrols them.

The `2026-05-18-profile-lifecycle-cli-adr` formalised the cascade-closure decisions with precision and remains valuable as **reference material**. It is not the current operator-facing authority; the active direction is the 2026-05-16 plan plus the explicit supersession ADR.

## Decision

Treat the archived 2026-05-18 plan as structurally complete historical evidence but **superseded in execution** by the 2026-05-16 variant. Retain the 2026-05-18 ADR as reference material for provenance only; do not dispatch new work from it without a later accepted authority document.

## Consequences

- The canonical operator-facing profile-lifecycle surface lands via the 2026-05-16 plan execution (already in progress).
- The archived 2026-05-18 plan and ADR remain searchable provenance, not active sprint scope.
- The 2026-05-18 ADR's narrowed-scope findings (e.g., explicit CI gating strategy for the factory-direct model, NIST SP 800-63B section 5.1.1.1 compliance pathway) may inform future ADR authoring only if re-enrolled.
- No information loss: both plans, both ADRs, and the supersession decision are archived, so future agents can trace the decision history and the scope evolution.

## Successor Plan

No successor plan is active from this ADR. A future profile-lifecycle sprint must author its own accepted plan or ADR and cite this document only as historical context.
