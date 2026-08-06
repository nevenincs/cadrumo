---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:3edbf593ad0267a9c02ad7f3ec518b48c0e75ca33c99db3550775da90ff1d4d0'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename` `W02.P03` summary

Phase W02.P03 moved the complete Python package to `src/cadrumo`, removed the
former import root, and reconciled test imports, resources, registry callables,
dynamic module identities, exception registries, and the two AEAT semantic
boundaries.

- Moved: `src/aeat` to `src/cadrumo`
- Modified: 478 test/eval-test paths for canonical imports
- Modified: 250 registry fragments containing 621 executable targets
- Modified: packaged-resource and i18n anchors
- Modified: production dynamic imports and 566 exception registry keys
- Preserved: `src/cadrumo/adapters/outbound/aeat`
- Preserved: `src/cadrumo/_data/registry/aeat`
- Created: S09 through S16 Step Records
- Modified: plan and rolling formal audit

## Description

The atomic move cross-committed the dirty source tree under the user's explicit
instruction to preserve and work through overlaps. Git detected 21,668 renames,
16 additions, and nine deletions; the audit reconciled the source/target
cardinality and recorded the seven formerly untracked external-feature paths
whose first Git container is the move commit. No stash, reset, restore, clean,
or destructive history operation occurred.

Test code received 2,005 product-root replacements and production dynamic
surfaces received 86 targeted module retargets. All 16,273 registry TOMLs parse;
621 executable `consumer` and `parser` targets moved to Cadrumo while
authority IDs, URLs, legal evidence, hashes, and the `registry/aeat` taxonomy
remained unchanged. The error registry now contains 566 Cadrumo class keys and
retains 27 semantic `cadrumo.adapters.outbound.aeat` paths.

Review-driven remediation updated the missed i18n resource anchors, repaired
executable hard-cut tests, retargeted active production import guidance, recorded
cross-commit provenance, and removed every ignored
`*.pyc.relocated-aeat*` collision artifact. Fresh-process tests prove
`import cadrumo` succeeds and `import aeat` fails without a shim.

Verification includes complete Python compilation, focused Ruff and formatting
checks, 16,273 TOML parses, registry/model loader checks, representative adapter
imports, 15 i18n tests, seven executable import/scanner tests, ten registry cache
tests, and referent-aware residue checks. The independent closure review reports
no remaining HIGH or CRITICAL Phase findings.
