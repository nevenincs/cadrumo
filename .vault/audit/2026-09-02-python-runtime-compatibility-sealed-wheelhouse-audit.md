---
tags:
  - '#audit'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:7835fa9265e27af246d9f44f79a386077fe514337839305299785670c9aa3723'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
  - "[[2026-09-02-python-runtime-compatibility-adr]]"
  - "[[2026-09-02-python-runtime-compatibility-research]]"
---

# `python-runtime-compatibility` audit: `Sealed runtime wheelhouse review`

## Scope

Audited the runtime-specific sealed wheelhouse planner, immutable cohort handoff,
offline binary installer, plugin consumer, and detector tests against the accepted
runtime-compatibility decision and `P06.S71`. The review covered lock and cohort
digest binding, per-runtime selection, platform closure, archive member integrity,
missing-wheel attribution, and preservation of the exact CPython 3.13.11 builder.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW findings were identified. The binary probe now
extracts only the manifest-selected runtime subtree, installs every third-party
dependency with `--offline`, `--no-index`, `--find-links`, `--only-binary :all:`,
and `--require-hashes`, and records the observed runtime before a missing-wheel
selection failure. Real CPython 3.13 and 3.14 probes passed from one clean cohort;
the advisory 3.15 closure remains explicitly attributable to `pydantic-core` and
`pyyaml` wheel gaps.

## Recommendations

No blocking recommendations. Retain the per-runtime manifest rows and rerun the
same clean-cohort evidence when 3.15 reaches the promotion point.
