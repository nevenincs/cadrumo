---
tags:
  - '#research'
  - '#live-submit-excision'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-16-live-write-test-audit-research]]"
  - "[[2026-04-16-live-write-static-audit]]"
  - "[[2026-04-16-live-write-test-audit]]"
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
---



# `live-submit-excision` research: live-write reachability gaps identified ahead of cli excision

Charter #197 (produce-verify-export) and live-AEAT-write safety charter #116 jointly
mandate that the codebase carry no reachable mechanism to file a live return at this
stage of the roadmap. This research consolidates the audit work that identified three
specific live-write reachability gaps in the pre-excision codebase and established the
basis for the B-level remediation decision.

## Evidence base

The following documents form the evidence base consolidated here:

- `2026-04-16-live-write-test-audit-research` — a research-phase audit that surveyed
  test files for live-write exposure, confirming that `test_live_submission.py` held
  tests exercising the full `submit()` path and that no pytest collection gate prevented
  them from running in normal CI. Provided the test-layer evidence that the live path
  was reachable without intentional bypass.

- `2026-04-16-live-write-static-audit` — static code audit that located the three
  reachability gaps: (1) `aeat submission submit` registered at the default CLI surface
  in `src/aeat/entrypoints/cli/submission/__init__.py`; (2) `SubmissionEngine.live_transport_supported`
  defaulting to `True` in `src/aeat/adapters/outbound/aeat/export/_engine.py`; and (3) the literal
  `await session.click("button#firmar-y-enviar")` sign-and-send click present in
  `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py`. Multi-layer runtime gates existed but
  the code path was discoverable, contradicting the "no reachable mechanism" posture.

- `2026-04-16-live-write-test-audit` — companion audit to the static audit, confirming
  the test-coverage picture for the live-write path and establishing that the static +
  behavioural guardrail pair (D3 in the ADR) was the correct mechanical enforcement
  approach to prevent regression.

- `2026-04-17-export-first-adr` — the upstream product-direction ADR that established
  the produce-verify-export mandate and formally deferred live submission, providing the
  product rationale that made the CLI excision non-negotiable.

## Consolidated finding

The audits confirmed that while robust runtime gates protected against accidental live
filing, the code path remained statically discoverable and structurally reachable by
any caller who omitted an explicit opt-out. The research supported the B-level
remediation: unregister `aeat submission submit` from the default CLI, flip
`SubmissionEngine.live_transport_supported` to `False` by default, and add static plus
behavioural regression tests. The submitter-level click was designated out of scope for
this ADR as it required only explicit opt-in after D2. This position was later
strengthened by the 2026-04-27 permanent-forbid amendment, which rendered live
submission permanently out of scope rather than deferred.
