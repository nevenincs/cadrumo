---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P06.S06'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P06.S06`

Ran the repo-wide grep gate for surviving `doctor` references in
`src/aeat/` and documented every survivor against the P06 scope
boundary.

- No edits in this step.

## Description

The grep gate matched `config doctor`, `aeat doctor`, `doctor"`, and
`'doctor'` across `src/aeat/`. Surviving hits classified against the
P06 contract:

Out-of-scope (P02 / P04 territory — `application/diagnostics.py`
group; explicitly forbidden in P06 constraints):

- `src/aeat/application/diagnostics.py` lines 64, 122, 261, 265
- `src/aeat/application/test_diagnostics.py` lines 249, 309
- `src/aeat/application/wizard/_status.py` lines 4, 38 (wizard
  status-report module; not in P06 plan)

Out-of-scope (P01.S06 grep-gate territory — test fixtures asserting
the absence of the old command shape; the literal `"doctor"` here is
a negative-test artefact, not live CLI text):

- `src/aeat/entrypoints/cli/test_workflow_surface.py` lines 206, 235

Out-of-scope (adapter-storage docstring; not in P06 named files;
defer to a later sweep):

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
  lines 99, 280, 353 — docstring text and a log-message fragment
  pointing at the renamed namespace. Plan P06.S06 explicitly accepts
  documenting why a survivor exists; this one is the storage adapter
  module and not the wizard / errors / live-app / common surfaces
  P06 owns.

In-scope and clean (all four P06-owned files):

- `src/aeat/application/wizard/_commands.py` — clean
- `src/aeat/core/errors/_registry.py` — clean
- `src/aeat/core/errors/registry/_domain.py` — clean
  (the only `aeat config doctor` literal was flipped to
  `aeat config repair` in P06.S03)
- `src/aeat/entrypoints/cli/_app_live.py` — clean
- `src/aeat/entrypoints/cli/_common.py` — clean

The four locale YAMLs and the `_config/__init__.py` Typer surface
remain owned by P01 / P05 and are explicitly excluded from this
phase's edit list.
