---
tags:
  - '#audit'
  - '#cli-root-help-profile-identity'
date: '2026-08-10'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:262ab67f1fa9c726a34eb6c00fe528d7250aee7b6d564e5b4a0b56c0b062a503'
related:
  - "[[2026-06-03-cli-ledger-testimonials-adr]]"
---

# `cli-root-help-profile-identity` audit: `Profile identity privacy and root help implementation review`

## Scope

Audit the bare-root active-profile projection, the centralized CLI privacy boundary,
the root landing and curated help rewrite, the four shipped locale catalogues, and
real CLI regression coverage. Verify that operator display labels remain visible,
opaque storage identifiers remain protected, every cited command resolves, and the
help never infers session or readiness state from profile selection alone.

## Findings

### degraded-active-profile | medium | A torn manifest is presented as no active profile

`src/cadrumo/entrypoints/cli/__init__.py:303` derives the landing report solely from `_active_profile_label()`, while the retired module deliberately collapses an absent, unreadable, or invalid active manifest to `None`. The landing model then equates that presentation failure with absent state: a real active pointer plus invalid `manifest.toml` exits successfully saying no profile is active, recommends `aeat config profile create NAME`, and emits `active_profile: null` in both the envelope and result. This loses the selected-but-degraded state and can direct an operator to create a duplicate profile instead of repair the existing one. Keep active selection separate from resolvable display identity, represent the degraded case explicitly, and cover the real torn-manifest text and JSON paths.

### uuid-shaped-label | medium | Valid display labels are mistaken for storage identifiers

The retired module admits any trimmed 1..160-character display label, including a UUID-shaped value, but the central redactor classifies every UUID-shaped value under `active_profile` as a profile identifier at `src/cadrumo/core/redaction/__init__.py:824`. A real profile whose label is `123e4567-e89b-42d3-a456-426614174000` therefore renders the text identity as `<profile-id>` and emits `<profile-id>` in both JSON identity anchors, contradicting the declared label-visible contract and making multi-profile reconciliation ambiguous. Preserve semantic provenance through redaction or reject identifier-shaped labels at their authoritative validation boundary, and add real text/JSON coverage for the chosen contract.

### root-help-command-citation | high | Root help prose is parsed as two dead commands

The retired module and the retired module begin explanatory paragraphs with `Use aeat config for` and `Use aeat app for`. The command-citation extractor exercised by the retired test consequently treats `for` as a verb and reports the dead citations `aeat config for profiles` and `aeat app for profile-scoped overview`, so the live-command conformance gate fails. Rephrase the paragraphs so command-family prose cannot be mistaken for an executable command, or narrow extraction to the typed command-bearing fields without weakening dead-citation coverage.

## Recommendations

- Keep selection state separate from display identity in the root landing contract.
  When a pointer exists but its live manifest label is unavailable, emit an explicit
  degraded state and direct the operator to `aeat config repair profile`; never infer
  blank state or recommend profile creation.
- Keep operator labels and storage identifiers as disjoint namespaces by rejecting
  UUID-shaped values at the shared `ProfileLabel` validation boundary. Preserve the
  central UUID redaction rule as defense in depth.
- Keep explanatory prose free of strings that resemble executable `aeat` command
  paths. Put command paths in typed help entries and retain the live command-citation
  conformance gate.
