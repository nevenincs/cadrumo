---
tags:
  - '#reference'
  - '#filing-test-topology'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:97f161c4ef599c104718b01f6563a9588ca643866378f3805e6a5a41c84c99ea'
related: []
---

# `filing-test-topology` reference: `Filing repository test ownership`

## Summary

The two filing repository suites are persistence-boundary tests, not inward
application behavior tests. `test_history_repository.py` exercises encrypted
AUDIT history storage, envelope classification, row-identity refusal, and
lock markers; `test_repository.py` exercises encrypted FINANCIAL draft storage,
classification, content-addressed payload round trips, and lock markers.

Both suites therefore belong under the profile persistence adapter test owner.
The history suite composes the application facade with `FilingHistoryPorts` and
`FilingHistoryRepositoryAdapter`, while the draft suite composes
`ModeloDraftRepository` directly against an isolated `SecureObjectRepository`.
Each moved module owns a fresh `isolated_runtime_profile` fixture, so encrypted
storage setup is no longer supplied by application filing test support.

The move preserves every test function: 16 history tests and 13 draft tests.
Application-facing filing contracts remain available to the history suite via
the public `history_models`, `history_ports`, and `history_repository` modules;
storage exceptions are observed through the translated
`FilingHistoryPersistenceError` at that boundary. No compatibility module or
forwarding import is required.
