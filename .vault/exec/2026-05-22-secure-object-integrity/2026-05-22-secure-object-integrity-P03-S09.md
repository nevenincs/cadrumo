---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S09'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path
     (e.g., S03 at L1, P02.S03 at L2, W01.P02.S03 at L3 / L4). The
     step_id frontmatter field below carries the canonical identifier;
     the heading restates the display path as a reading hint. -->

# `secure-object-integrity` `P03.S09`

Routed real operator CLI invocations through a root-fallback refusal guard before profile-bound command bodies can write to the root fallback database.

- Modified: `src/aeat/entrypoints/cli/__init__.py`

## Description

The root active-session callback now classifies the effective storage route with `classify_storage_route()`. When a real console-script invocation resolves to a named profile-bound mutation verb and the route kind is `ROOT_FALLBACK_DATABASE`, the CLI raises the existing no-active-profile `CliRefusedBoundaryError` before opening a session or dispatching into the command body.

The guard intentionally ignores help/version surfaces and in-process cached Typer test-runner invocations whose `sys.argv[0]` is not an AEAT entrypoint. That preserves existing bootstrap-exempt repair, nested-help, and read-only registry contracts while still protecting real operator entrypoints such as `aeat` and `python -m aeat`.

## Tests

Focused gates passed:

- `uv run ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_cold_start_no_profile.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`
- `uv run pytest src/aeat/entrypoints/cli/test_cold_start_no_profile.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`

Real CLI smoke checks passed:

- Fresh root `uv run aeat app ledger list` refused with the no-active-profile boundary and exit code 2.
- Fresh root `uv run aeat config repair integrity attribution` remained bootstrap-safe and exited 0 with a metadata-only no-active-profile attribution report.
- Fresh root `uv run aeat config --help` exited 0.
- Fresh root `uv run aeat app ledger --help` exited 0.
- Fresh root `uv run aeat app registry legal view ley-37-1992:art-99` exited 0.
- Fresh root `uv run aeat config auth login` refused with the no-active-profile boundary and exit code 2.
- Direct guarded-verb check covered the profile-bound mutation paths surfaced in review: ledger link/export, modelo verify/file/amend/filing-record import/reconcile/export, live verify nif-iva/tgvi, profile census refresh/apply, and inventory valuation preview.
- Fresh root `uv run aeat app modelo work verify abc` refused with the no-active-profile boundary and exit code 2.
- Fresh root `uv run aeat config profile census refresh` refused with the no-active-profile boundary and exit code 2.
- Fresh root `uv run aeat app ledger link tx --invoice-id inv` refused with the no-active-profile boundary and exit code 2.
- Fresh root `uv run aeat config profile switch does-not-exist` reached the profile-switch resolver and refused with unknown-profile guidance, proving the on-ramp switch path is not blocked by the root-fallback guard.

Review audit: `2026-05-22-secure-object-integrity-P03-S09-review`.
