---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:d879539e76cfb412c92eaebf8d41f23418569d8d6babed884209c16a9892b2f1'
step_id: 'S03'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then expose only canonical profile-password and retained non-profile credential capabilities while removing stale exports and lazy mappings without aliases

## Scope

- `src/cadrumo/core/__init__.py`

## Description

- Ground the accepted contract, live facade, registration, rotation, CLI, TUI,
  and tests through semantic and exact-symbol discovery.
- Export the canonical profile-password bounds, assessment, refusal taxonomy,
  and assessor through the core public facade.
- Delete stale core, application, and TUI facade names and migrate every
  immediate compile-time consumer without aliases.
- Route registration and rotation through canonical prospective assessment
  before custody work and keep refusal context secret-free.
- Make TUI validation independent of advisory strength and preserve localized
  rendering through existing safe keys.
- Collect affected suites and run focused real application and headless-TUI
  behavior.

## Outcome

- The public import graph is coherent after S02; no consumer requests a
  deleted symbol or the changed strength signature.
- Registration, rotation, CLI composition, and TUI feedback share the same
  typed core assessment.
- The HIGH step-atomicity review finding is resolved and re-attested in its
  audit record.
- Public-facade probing and collection of 15 affected tests pass.
- The focused registration, rotation, and TUI suite passes all 22 tests.

## Notes

Detailed localized messages for the upper scalar, UTF-8 byte, and surrogate
reasons remain locale-owned S07 work. Until then those expected prospective
refusals use the existing localized generic custody-refusal key. The exhaustive
core boundary and exact-Unicode matrix remains S04 scope.

Full repository collection progressed through 25,773 tests before stopping on
an unrelated pre-existing missing `profile_bucket_session_open_resumed` harness
facade export. The feature-owned application and TUI modules collected cleanly,
and the focused behavior run remained green.

The broad import-hygiene gate reported six existing repository-baseline
failures across test-debt census, unrelated forwarding wrappers, tooling test
exclusions, and a legacy recovery-screen disposition. None names a changed
credential production import; the canonical credential edges use owning public
facades.
