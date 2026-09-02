---
tags:
  - '#audit'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9cc05cf64ff5bb1a5f5be7ad075dea9dd311582480ae86baf9c3f3eb79af9f94'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# `python-runtime-compatibility` audit: `Canary selector identity correction`

## Scope

Reviewed the canonical prerelease selector, its parser and matrix projection,
the target-runtime identity check, and the operator guidance after the final
compatibility review identified a selector/evidence mismatch.

## Findings

### canary-selector-identity | medium | The declared canary selector did not match the provisionable interpreter

The former fixed selector `3.15.0-rc.2` could not be provisioned offline,
while the available and evidenced interpreter was selected by rolling minor
`3.15` and reported CPython `3.15.0b4`. The correction accepts the rolling
minor for prerelease rows, projects it into both compatibility modes, and
retains the observed patch version in evidence. Stable rows, blocking policy,
and classifier eligibility remain unchanged. Focused matrix and workflow tests,
Ruff, lock validation, and offline provisioning all pass.

## Recommendations

Keep each rolling prerelease selector provisionable at canary rotation and
record the exact observed interpreter version in the mode-specific evidence.
Promote a canary only through the existing final-release evidence policy.
