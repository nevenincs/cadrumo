---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S17'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01.S17`

Active-profile resolver. Single chokepoint that the OAuth flow and every secure-store read/write call to obtain the AEAT profile name a Google OAuth call is scoped to. Honours `--profile` overrides and falls back to `workflow_state_repository().load().active_profile`.

- Created: `src/aeat/adapters/outbound/google/_profile_binding.py` — `resolve_active_profile(profile_override: str | None = None) -> str`
- Created: `src/aeat/adapters/outbound/google/test_profile_binding.py` — 9 unit tests covering override precedence, whitespace handling, fallback semantics, error context, and stable error-code binding

## Description

The plan's drift-amended S17 specified: read `workflow_state_repository().load().active_profile` (real surface in `application/workflow/_models.py`), raise `GoogleAuthProfileUnboundError` when no profile is bound. This implementation does exactly that with two small refinements:

- Strips surrounding whitespace from both the override and the workflow-state value, so `--profile " business "` resolves the same as `--profile business` and a stored `active_profile="  primary  "` does not propagate the whitespace into HMAC keys downstream.
- The `GoogleAuthProfileUnboundError` raised carries `context={"override": ..., "active_profile": ...}` for renderer-side observability and `suggestion="aeat config init --tax-id <NIF>"` for the operator. The error class itself binds at import to `REFUSED_GOOGLE_PROFILE_UNBOUND` per the registry.

The function does not import or instantiate `SecureObjectRepository` directly; it goes through the application-layer `workflow_state_repository()` factory so the same encrypted-SQL backend the rest of the workflow surface uses is consulted. Tests stub the factory via monkeypatch on the resolver's own import path.

## Tests

- `pytest src/aeat/adapters/outbound/google/test_profile_binding.py -q` — 9 passed.
- Coverage: override wins, override is stripped, fallback to workflow state, fallback when override is empty / whitespace, workflow-state value is stripped, raises when both absent, raises when active_profile is blank, raised error carries stable registry code.
