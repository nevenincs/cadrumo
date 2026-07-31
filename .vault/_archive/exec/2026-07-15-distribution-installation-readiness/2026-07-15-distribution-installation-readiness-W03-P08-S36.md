---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S36'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Execute the complete cohort and installed tax oracle on the claimed macOS Python row

## Scope

- `.github/workflows/packaging-smoke.yml`

## Description

- Add the `cadrumo-packaging-smoke-macos` job to `.github/workflows/packaging-smoke.yml`, running on native `macos-latest` (Apple silicon / arm64, matching the claimed `python-macos-arm64` row).
- Run the same host-portable `just packaging-smoke` aggregate as the Windows leg, so the cohort is built once and every portable lane consumes the same bytes; Docker, the Ubuntu-only `packaging-smoke-ci`, and any Homebrew host package-manager lane are excluded.
- Mirror the Ubuntu leg's fail-fast preflights and evidence checkpoint; omit the Linux-only disk-reclamation step and bash resource sampler.
- Pin the same uv 0.11.29 / Python 3.13 toolchain and upload per-OS artifacts (`cadrumo-python-cohort-macos`, `cadrumo-packaging-smoke-evidence-macos`) so names never collide with the Ubuntu or Windows legs.
- Covered by the same conformance-gate extension as S35: the gate pins all three job keys, names, runners, portable campaign command, per-OS artifact names, ordering, and cross-job artifact-name uniqueness.

## Outcome

The macOS leg is authored and pinned by the conformance gate. This Step's row stays OPEN: it is satisfied only when the leg executes green in CI on the rebuilt cohort. The workflow was NOT dispatched, and the cohort must be rebuilt after the in-flight performance work before the row's installed-behavior evidence is valid. `macos-latest` is arm64, which matches the claimed `python-macos-arm64` distribution row exactly. Gates green locally: `test_packaging_smoke_workflow.py` 19 passed, YAML parses to the three expected jobs and runners, `ruff`/`ty` clean on the test file.

## Notes

The macOS and Windows legs share the portable lane set and the smoke modules' cross-platform layout handling, so they were authored and pinned together and committed in one commit with S35. The real green run that closes this row is deferred to the post-rebuild CI pass; dispatching runs was out of scope. No incidents; no scaffolds left in code.
