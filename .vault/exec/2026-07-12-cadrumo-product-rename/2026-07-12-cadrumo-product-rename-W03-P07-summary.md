---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename` `W03.P07` summary

Phase W03.P07 proved the renamed root and companion distributions through real
builds, fresh installed environments, and a clean Linux container.

- Completed: S36 through S42 Step Records
- Verified: root wheel payload, metadata, size, and executable pair
- Verified: slim-core refusal followed by both companion installs and full authority
- Verified: Docker/Linux installation, profile/config flow, storage round-trip, and optional boundary
- Modified: packaging probes and focused real-behavior coverage
- Modified: plan and rolling formal audit

## Description

The final core wheel is 41,883,465 bytes and exposes exactly `cadrumo` and
`cadrumo-mcp`. Its isolated smoke manifest is `ok: true` after frozen export,
payload, metadata, fresh-install, resource, attachment, optional-extra, and CLI
profile/config checks.

The split-install manifest is `ok: true`: the slim wheel refuses full authority
without the corpus companions and gives the canonical remedy, then
`cadrumo-data-manuals` and `cadrumo-data-official` install into their joined
namespace and pass byte-exact registry verification. The Docker manifest is
also `ok: true` on `python:3.13-slim` through `wsl:Ubuntu`.

Remediation followed observed failures rather than weakening gates. Pillow was
classified as a legitimate base-transitive dependency, the imported
operator-progress module was brought under source ownership, profile bootstrap
was allowed to derive its bucket database route, and the Docker profile fixture
was given an explicit tax-residence CCAA. The accidental commit coupling between
the split probe and dev-container work is preserved and disclosed in the rolling
audit without history rewriting.

The independent closure review found no HIGH or CRITICAL issues. Its plan-drift
MEDIUM was resolved by restoring the accepted sole `cadrumo` human command and
the `cadrumo-mcp` server command in the active plan.
