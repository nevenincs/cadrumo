---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:603321d5f9903936d3a375dee038d2c5e29686f49bd6b4a19e80e56043086f34'
step_id: 'S03'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add the discover_filed_history application service wrapping the session bring-up shared with capture_filed_data around the new adapter function, verified by a test that a missing auth session raises the same SedeNavigationError the existing capture path raises

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `discover_filed_history`, wrapping the shared verified-session bring-up around the new adapter read and the profile-derived grid.
- Promote it on the `application.live` facade.
- Add the bring-up parity test asserting the discovery read refuses a missing auth session exactly as the shipped walk does.

## Outcome

The service reads the register's option lists through the SAME verified-session
and shared-Playwright bring-up every filed-capture path already uses, so an
operator who has not authenticated gets the refusal and the remediation they
already know rather than a discovery-specific error nobody has seen.

The profile argument is optional, and the consequence is made explicit rather
than left implicit: omitting it yields a report carrying NO taxpayer-specific
denominator, and the report exposes that as a queryable property so a caller
cannot read the pair count as coverage. Nothing is persisted and no pair is
queried.

## Verification

    uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_register_availability.py -q -n 0
    12 passed in 24.04s

The bring-up parity assertion compares the error type, the translated message and
the rendered message across the discovery read and the shipped register walk,
rather than only the type -- a second bring-up copy would most plausibly diverge
on the message, which is the part an operator reads.

## Notes

Landed in the same peer sweep as the sibling adapter Step (`24f8fd9add`);
content verified byte-identical and not re-committed.
