---
tags:
  - "#research"
  - "#multilang-externalization"
date: 2026-05-04
modified: '2026-05-04'
related:
  - "[[2026-05-04-multilang-externalization-phase1-adr]]"
  - "[[2026-05-04-multilang-externalization-phase1-plan]]"
---

# Multilang Externalization Phase 1 Research

## Scope

This research backfills the evidence basis for the phase 1 ADR and plan. The
surface is the user-facing localization layer and the removal of inline
translation structures from CLI and application messages.

## Findings

The prior approach embedded multilingual message variants directly in Python
call sites. That made wording hard to audit, encouraged incompatible local
translation helpers, and coupled domain logic to presentation-language choices.

A key-based externalization model is the appropriate replacement because it
centralizes translation assets, lets reviewers inspect wording by language, and
allows code paths to carry stable message identifiers instead of duplicated
text payloads.

## Implications

The ADR should require removal of compatibility wrappers and direct inline
translation payloads. The implementation plan should treat old helper APIs as
migration targets, not supported surfaces.
