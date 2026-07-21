---
tags:
  - '#audit'
  - '#docs-static-deployment-hardening'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-07-12-docs-static-deployment-hardening-plan]]"
---
# `docs-static-deployment-hardening` audit: `Cadrumo delivery safeguard review`

## Scope

Review deployment controls, tests, and operator instruction.

## Findings

### legacy-location | medium | Legacy verification accepted a wrong redirect destination.

Require the canonical Cadrumo `Location` after `308`.

### live-contract-coverage | medium | Live contract tests did not assert every endpoint independently.

Assert canonical, legacy location, missing, and direct-S3 responses.

### live-test-taxonomy | medium | The AWS probe was mislabelled as offline integration.

Move the probe to an explicit `aeat_live` module.

### live-test-gate | medium | The deployment probe bypassed the repository live-test gate.

Move the probe under the governed test root.

### local-marker-shape | medium | The local test marker violated the marker-integrity gate.

Use a list literal for `pytestmark`.

### local-test-discovery | high | The local safeguards were outside routine test discovery.

Move the suite under the governed test root.

### final-gate | pass | Find no critical or high Cadrumo issue.

Require default local discovery, gated live discovery, exact endpoint checks, and CI refusal.

## Recommendations

Keep endpoint checks after invalidation.
