---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:90770d345f469ac9119328e5aef2e28d3959ffdd7343c7a7343d893fe9a81042'
step_id: 'S142'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh repair the telemetry producer test that imports a private helper from a sibling test module which no longer defines it, the helper having been removed rather than renamed with no equivalent surviving, and rule on the shape independently since a test module importing another test module's private helper is fragile by construction

## Scope

- `src/cadrumo/core/telemetry/tests/`

## Description

- Ground truth check found the repair already landed at HEAD, in a prior commit on this
  same branch, before this Step was dispatched: `test_producers.py` previously imported
  `from .test_http_sink import _run_loopback_server, _stop_loopback_server` (a private
  pair defined only inside `test_http_sink.py`), and that import target had already been
  removed rather than renamed. The fix extracted the shared handler class into a
  dedicated, non-test-prefixed support module, `_telemetry_endpoint_support.py`, which
  exports `RecordingTelemetryEndpoint` (no leading underscore) via `__all__`; both
  `test_http_sink.py` and `test_producers.py` now import it from there, and neither
  imports from the other's test module.
- Confirmed no residual private cross-test-module import remains anywhere under
  `src/cadrumo/core/telemetry/tests/`.
- Ran the full telemetry test package (42 tests) to confirm green.
- Ran a process-external bite-proof: a scratch script (never landed under `src/`)
  monkeypatched `HttpTelemetrySink.send` to a permanent no-op before invoking pytest
  in-process, then restored nothing on disk because production code was never touched.
  Confirmed `git status` on `src/cadrumo/core/telemetry/` stayed clean throughout.

## Outcome

Ruling on the shape: a test module importing another test module's private helper is
fragile by construction, and the resolution already in the tree is the correct one of
the three options offered — a dedicated, properly-owned test-support module
(`_telemetry_endpoint_support.py`), not a `conftest.py` fixture and not inlining.
Grounds: the shared symbol is a concrete `BaseHTTPRequestHandler` subclass
(`RecordingTelemetryEndpoint`) consumed by two sibling suites
(`test_http_sink.py`, `test_producers.py`) that both need to construct it directly and
pass it to `run_loopback_server(...)`; a `conftest.py` fixture would work for the
`server, thread, events` triple but cannot cleanly hand back an unconstructed handler
*class* for `run_loopback_server` to receive as an argument, and inlining was rejected
because there are two callers, not one — duplicating the handler risks the two suites'
recorded-event shapes drifting apart, which is exactly the failure the module's own
docstring records happening once already (plumbing moved to its canonical home,
`cadrumo.tests.loopback_recording_server`, and the importing suite was left behind). The
new module's own docstring states this ruling in-repo already, so no independent
production-code change was needed for the ruling itself.

Verification: `uv run --no-sync python -m pytest src/cadrumo/core/telemetry/tests/ -v`
passed 42/42 (captured to
`s142_telemetry_run.log` under the session scratchpad). Bite-proof: with
`HttpTelemetrySink.send` monkeypatched to a no-op from a scratch script external to the
repo, the same two suites went red on exactly the six tests whose assertions depend on a
real POST reaching `RecordingTelemetryEndpoint` (`test_fully_permitted_invocation_posts_the_allowlisted_payload`,
`test_allowlisted_payload_cannot_carry_a_sensitive_field_over_http` in `test_http_sink.py`;
`test_command_invocation_permitted_dispatches_allowlisted_payload`,
`test_command_invocation_failed_run_increments_failed_counter`,
`test_llm_run_permitted_dispatches_allowlisted_payload`,
`test_error_frequency_dispatches_closed_non_sensitive_payload` in `test_producers.py`),
while the eight consent-gated tests that assert nothing is sent stayed green — proving
the repaired imports exercise real send behaviour through the shared endpoint, not a
vacuous path. No tracked file was touched for the proof; `git status` on the telemetry
tree was clean before and after.

## Notes

No repair work was required in this Step: the import breakage described by the row was
already fixed at HEAD by prior work on this branch, and the shape ruling the row asked
for was already recorded in the resulting module's own docstring. This Step's
contribution is independent confirmation (ground-truth re-check, full suite run,
bite-proof) rather than new code. Left the plan Step unchecked per instruction; the
dispatcher should mark it complete via the owning plan verb.
