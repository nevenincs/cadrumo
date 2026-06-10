---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
related:
  - '[[2026-06-10-live-justificante-reconcile-plan]]'
---

# `live-justificante-reconcile` `P05` summary

Phase P05 (CLI surface, locales, and docs) is complete. All four Steps landed
with their gates green; the feature is operator-reachable via the live CLI.

- Created: `src/aeat/entrypoints/cli/_app_live_justificante_cli.py`
- Modified: `src/aeat/entrypoints/cli/_app_live_payloads.py`, `_app_live.py`
- Created: `src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py`
- Modified: `src/aeat/locales/{en,es,ca,hu}.yml`
- Modified/Created: `docs/api/aeat.application.live*.rst`

## Description

A new `aeat app live justificante` sub-app (`S11`/`S12`) mirrors the expedientes
CLI with `capture`, `list`, and `view` verbs and typed result payloads. `capture`
runs the live auth preflight and the `capture_justificante_snapshot` orchestrator
— this is the headline operator action the feature set out to deliver: the app
pulls the AEAT-signed justificante itself for a filed period and persists it, no
manual download. The sub-app is registered on the live read group; CLI verb tests
cover the local read paths and registration wiring. Locale keys for the five new
strings landed across all four catalogues with genuine translations (`S13`); the
API reference stubs were regenerated and pass the drift check (`S14`).

The code review returned PASS with two LOW notes: the EN catalogue initially
carried key-path placeholders (resolved to the code default at runtime; corrected
to the real text), and `--modelo` is typed `str` rather than the `Modelo` enum —
the established convention across the entire live-CLI family because the live
surface accepts any dynamically-registered registry modelo, and the closed set is
still enforced at the snapshot model boundary.

## Verification

CLI registration verified live (`aeat app live justificante --help` renders the
three verbs); locale parity, translation-honesty, and `apidocs scaffold --check`
all clean; the full feature sweep is 54 passed. Plus the two MEDIUM follow-ups
recorded in the P03 and P04 summaries (bucket event on the evidence stamp; an
operator verb to reconcile against a persisted capture) are formally deferred as
tracked increments.
