---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:cc14fb9b9e9993180ffdd8973a9d24e142a1949011ea424183cd905970e3f18e'
step_id: 'S07'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Prove serialized catalogues require the canonical invoices wrapper

## Scope

- `src/cadrumo/domain/invoices/tests/test_catalogue.py`

## Description

- Prove a serialized payload lacking the canonical entries key refuses with the
  typed error.
- Prove the canonical wrapper is accepted and round trips.
- Prove construction with no entries is still accepted.
- Prove the iterable construction API keys by invoice identifier and refuses a
  duplicate.
- Populate the round-trip fixture so no defaultable field carries its default.

## Outcome

Landed in `7afcc4b` alongside the production change.

The pre-existing mismatched-keys test was read before the change to establish
whether it reached its assertion only via the arm being deleted. It did not --
it already passed the canonical wrapper -- so it needed no correction, and
confirming that was cheaper than discovering it from a red suite.

The round-trip fixture populates every defaultable field with a non-default
value. A fixture built from defaults cannot distinguish a boundary that preserves
a field from one that drops it on save and re-defaults it on load, because both
produce an equal object.

## Notes

No mocks, no monkeypatch, no skip and no expected-failure markers in the file.

One behaviour change rides inside what otherwise looks like a call-shape sweep
and is recorded so it is not later read as accidental: a consumer helper moved
from a dict comprehension to the iterable construction API, so duplicate invoice
identifiers now raise where the comprehension silently kept the last one. That is
a tightening and it was kept deliberately.
