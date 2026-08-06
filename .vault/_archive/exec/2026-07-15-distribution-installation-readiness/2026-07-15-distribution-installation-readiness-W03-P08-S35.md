---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:84ac10bb5634714637db9c068927f5ce6c1e3566bf9bddeebf8fd7c09eed0097'
step_id: 'S35'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Execute the complete cohort and installed tax oracle on the claimed Windows Python row

## Scope

- `.github/workflows/packaging-smoke.yml`

## Description

- Add the `cadrumo-packaging-smoke-windows` job to `.github/workflows/packaging-smoke.yml`, running on native `windows-latest` (x86-64, matching the claimed `python-windows-x86-64` row).
- Run the host-portable `just packaging-smoke` aggregate (dependencies, preflight tests, core, pip-core, sdist-core, extras, split, portable browser, installed oracles) so the cohort is built once and every portable lane consumes the same bytes; the Ubuntu-only `packaging-smoke-ci`, Docker, and `browser-linux` lanes are excluded.
- Mirror the Ubuntu leg's fail-fast preflights (dependency surface, shipped data source, preflight command tests) and the evidence checkpoint, and omit the Linux-only disk-reclamation step and the bash resource sampler.
- Pin the same uv 0.11.29 / Python 3.13 toolchain and upload per-OS artifacts (`cadrumo-python-cohort-windows`, `cadrumo-packaging-smoke-evidence-windows`) so names never collide with the Ubuntu leg.
- Extend the conformance gate `test_packaging_smoke_workflow.py` to pin the new three-job shape exactly: job keys, names, runners, the portable campaign command, per-OS artifact names, upload ordering, and cross-job artifact-name uniqueness.

## Outcome

The Windows leg is authored and the conformance gate pins it. This Step's row stays OPEN: the row is satisfied only when the leg actually executes green in CI on the rebuilt cohort. The workflow was NOT dispatched (per the brief), and the v0.2.1 cohort must be rebuilt after the in-flight performance work lands before the row's installed-behavior evidence is valid. Gates green locally: `test_packaging_smoke_workflow.py` 19 passed, YAML parses to the three expected jobs and runners, `ruff check`/`ruff format --check`/`ty check` clean on the test file.

The justfile already declares `set windows-shell := pwsh` and the smoke modules branch on `os.name`/`sys.platform` for Scripts-vs-bin and `.exe` layouts, so the portable lanes are built to run natively on Windows; `smoke_scoop` (PowerShell, host package-manager) is a separate workflow and is not part of `packaging-smoke`.

## Notes

I could not exercise the leg end-to-end: the cohort build requires a clean git snapshot and dispatching runs was out of scope, so the leg's real green run is deferred to the post-rebuild CI pass that closes this row. A miss there would surface as a lane failure named in the interleaved output, not a silent pass. No incidents; no scaffolds left in code. Committed together with S36 in one commit.
