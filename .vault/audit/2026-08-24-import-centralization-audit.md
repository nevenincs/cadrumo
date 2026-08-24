---
tags:
  - '#audit'
  - '#import-centralization'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e6a52835e70282bb60426f38bb045a25bec035db46bc6799e320993a75eb7768'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---
# `import-centralization` audit: `S403 import-integrity closure review`

## Scope

Reviewed the S403 import-hygiene closure: exact test-debt reconciliation, forwarding-wrapper retirement, dev-tooling detector scope, dangling first-party imports, canonical facade exports, and the legacy TUI census pins.

## Findings

### feature-index-preview | low | The feature-index CLI lacks a dry-run mode

`vaultspec-core vault feature index` rejects `--dry-run`, so its required feature-index refresh cannot receive the usual command preview. The call is constrained to the `import-centralization` feature and has one deterministic index target.

## Recommendations

Add `--dry-run` support to the feature-index command so its generated index diff is reviewable before writing.
