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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-installation-readiness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S36 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Execute the complete cohort and installed tax oracle on the claimed macOS Python row and ## Scope

- `.github/workflows/packaging-smoke.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
