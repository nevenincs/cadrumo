---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/adr/ location)
# Feature tag (replace cli-backend-boundary with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#adr'
  - '#cli-backend-boundary'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-08'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-08-cli-backend-boundary-research]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-backend-boundary` adr: `CLI backend boundary` | (**status:** `accepted`)

## Problem Statement

The AEAT CLI has accumulated workflow, parsing, validation, persistence,
calculation, reconciliation, and reporting behavior that belongs in Python
backend services. This creates false confidence in CLI tests, hides missing
backend APIs, and lets the command surface become an application layer with
its own business rules.

The required architecture is that the CLI is a presentation and invocation
adapter only. It may bind command arguments, construct typed backend request
objects, call backend services, render backend result DTOs, and translate
typed backend errors into user-facing messages. It must not own tax,
financial, persistence, registry, deadline, import/export, or reconciliation
logic.

## Considerations

- The codebase already contains domain and application packages for ledgers,
  invoices, filing, deadlines, profile, registry, and diagnostics.
- Several CLI modules currently duplicate or shadow backend concerns rather
  than exposing backend services.
- Tests that assert CLI-owned business behavior produce regression risk
  because they can pass while backend APIs remain incomplete.
- The user-facing CLI still needs strong behavior, but that behavior must be
  supplied by typed backend services and covered by backend contract tests.

## Constraints

- No legacy compatibility layer is required for CLI-owned business logic.
- Existing shared-worktree changes by other agents must remain intact.
- Work must proceed in small, reviewable waves with commits between major
  steps.
- Tests must not use tautological assertions, transient development state,
  phases, stamps, broad mocks, skipped checks, or false-positive existence
  checks.
- Missing backend behavior is in scope and must be implemented in backend
  services rather than worked around in the CLI.

## Implementation

The rollout will follow `2026-05-08-cli-backend-boundary-research` and
`2026-05-08-cli-backend-boundary-reference`. Every CLI business-logic finding
is assigned a row ID. Each row moves through audit, backend API implementation,
CLI simplification, backend contract tests, CLI wrapper tests, and code review.

The CLI will be reduced to these allowed responsibilities:

- Typer command and option declaration.
- Minimal syntactic option normalization needed to construct typed backend
  request objects.
- Invocation of backend command services.
- Rendering of backend result DTOs.
- Translation of typed backend exceptions into stable CLI diagnostics.

Backend services will own import/export round trips, profile schema behavior,
ledger and invoice parsing, matching, reconciliation, filing inputs, deadline
readiness, registry queries, inventory calculations, and diagnostics.

## Rationale

This decision makes missing backend APIs visible instead of allowing the CLI
to compensate with command-local logic. It also creates a sharper test
boundary: business behavior is tested through backend APIs, while CLI tests
verify command wiring, rendering, and error translation.

The research inventory shows repeated examples where CLI modules own domain
grammar, persistence flows, import parsing, reconciliation mutation, registry
selection, filing input coercion, and overview status aggregation. Keeping
that logic in the CLI would preserve the root regression. Moving it behind
typed backend services aligns the implementation with the centralized schema
and Pydantic rollout already in progress.

## Consequences

The near-term implementation cost is higher because backend gaps must be
filled instead of papered over in CLI modules. Some existing CLI tests must be
deleted or migrated because they currently pin the wrong ownership boundary.

The long-term result is a stricter architecture: CLI surfaces become thinner,
backend APIs become reusable by Python callers, and regression tests validate
real behavior rather than command-local mirrors of business rules.
