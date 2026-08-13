---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:528d4b2000dae2fe5d1360083aa5de4157516d50de75bf600685bd2bdb5cb9d9'
step_id: 'S29'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Write the custody gate proving a full fetch-and-store cycle writes the PDF bytes to no filesystem path: run the service against a temporary profile root, assert every file created is an encrypted store artefact and that the plaintext PDF magic bytes appear nowhere on disk, then the mutation proof writing the bytes to a temp file and confirming the gate reds

## Scope

- `src/cadrumo/application/live/tests/test_notification_document_custody.py`

## Description

- Replaced the single-file database scan with a full filesystem sweep: after a real fetch-and-store cycle against a temporary profile root, walk every file under the root and assert none of them contains the served PDF's magic bytes or any of its distinctive plaintext literals.
- Kept the assertion keyed on that property rather than on a hardcoded file count or filename list, so a future store artefact (a new sidecar, a new keystore file) is covered automatically instead of needing an allowlist update.
- Added anti-vacuity checks confirming the walk actually finds the real artefacts the cycle writes (the database file present, at least three files total) so the sweep cannot pass by finding nothing.
- Kept the pre-existing single-file database scan in place alongside the new sweep, cross-referenced in its docstring, since the database file is where every byte this service writes ultimately lands.
- Proved the new sweep is load-bearing with a runtime script driven from outside the tracked tree: it runs the real fetch-and-store cycle, writes the served PDF's plaintext bytes to a scratch file elsewhere under the profile root (simulating a leak the database-only scan would never see), and confirms the sweep's assertion reds on that leak file.
- Ran the real-adapter test suite, `pytest --collect-only`, and the docs build gate; all green.

## Outcome

Closed. The custody proof now covers the entire on-disk footprint of a fetch-and-store cycle, not only the database file, and its detection capability was proven against a real injected leak file rather than assumed.

## Notes

While closing this Step, absorbed a co-located regression: the notification-document custody module tree (the sanción reader package and its live application service) shipped without generated API doc stubs. Regenerated the stubs via the CLI-owned scaffold and staged only the entries naming those modules, leaving every other peer's regenerated stub untouched for its own owner.
