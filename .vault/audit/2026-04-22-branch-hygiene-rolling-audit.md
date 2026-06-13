---
tags:
  - "#audit"
  - "#branch-hygiene"
date: "2026-04-22"
modified: '2026-04-22'
related:
  - "[[2026-04-21-google-auth-ux-adr]]"
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-04-21-n26-data-source-implementation-adr]]"
---

# `branch-hygiene` Code Review

AUTH-001 | HIGH | Resolved: upstream `aeat auth` package shadowed the Kent-first `aeat auth init` surface after the latest `origin/main` merge.
Integrated the guided Google auth entrypoint into `src/aeat/entrypoints/cli/auth/__init__.py`, removed the dead shadow module `src/aeat/entrypoints/cli/auth.py`, removed the duplicate root `auth` registration, updated the CLI tests, and reverified `aeat auth --help` plus `aeat auth init --help`.

CLI-002 | MEDIUM | Open: `aeat auth --help` and other root CLI help surfaces print unrelated portal/model registry load logs.
The root CLI imports the portal and modelo registries during command-tree assembly, and both registries emit successful import-time `INFO` logs. That pollutes help output with irrelevant lines and makes the Kent-facing CLI feel noisy even when the command only asks for static help text.

STATUS-003 | LOW | Triaged: hidden `aeat status` subcommands still contain repeated stub docstrings and a shared cert-backend bail path.
This is a deliberate hidden surface rather than active Kent-path drift. It is not currently shadowing public behavior, but it remains a candidate for future consolidation if the hidden commands are promoted.

CLI-002 | MEDIUM | Resolved: root CLI help no longer leaks unrelated registry load logs.
Demoted the successful import-time portal/model registry messages from `INFO` to `DEBUG`, updated the registry test expectation, and added a CLI regression test proving `aeat auth --help` stays free of the `loaded 42 portal entries` and `loaded 21 modelo entries` noise.

FIN-004 | MEDIUM | Resolved: two tracked financial placeholder modules were dead and unreferenced.
Deleted `src/aeat/domain/financial/attachments/_stubs.py` and `src/aeat/domain/financial/transactions/_stubs.py` after confirming they had zero imports across the live financial tree. The full financial pytest, `ruff`, and `ty` surfaces remained green after removal.

POOL-005 | LOW | Current active audit pool narrowed to non-blocking deferred placeholders only.
The remaining obvious placeholder language sits on intentionally hidden or explicitly deferred surfaces (`aeat status` follow-up commands, manuals cross-branch stubs, provider placeholders for not-yet-shipped AEAT auth kinds). No additional shadowing, duplicate command registration, or dead-file duplication was found in the active auth/N26/financial sweep.
