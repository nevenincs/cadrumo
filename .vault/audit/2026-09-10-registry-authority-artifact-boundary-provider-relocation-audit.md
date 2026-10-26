---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:3c0ed1ad813b0ea0a114d41bf3176c4484047155a711d967de50e8277ad996d9'
related: []
---

# `registry-authority-artifact-boundary` audit: `provider relocation`

## Scope

The relocation of category, holiday, and IVA source compilers into development ownership was audited before the broader registry compiler closure proceeds.

## Findings

### provider-relocation | high | Production test collection still imports moved compilers

Category, holiday, and IVA-recarga fact-provider tests remain under `src` and import compiler symbols moved to development. Collection fails before behavior runs; authoring tests must move with the compiler.

### provider-relocation | high | Category source-path test outlived its runtime API

A production category test still calls the removed path-oriented loader. The supported runtime path is artifact resolution, while the source-path refusal belongs in development compiler coverage.

### provider-relocation | medium | Legacy IVA retirement check is implementation-shape inspection

The development suite contains an AST/string/ledger-shape test. It is not acceptable evidence for this campaign and should be removed or replaced with behavior that proves the intended authority boundary.

## Recommendations

- Move stale compiler tests to development and exercise category and holiday compilation through real candidate inputs.
- Replace runtime path-oriented test cases with staged artifact resolution behavior.
- Remove or replace the legacy implementation-shape test with a meaningful mutation or publication behavior gate.
