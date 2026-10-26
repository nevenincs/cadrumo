---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:9c5bc5503692552e92a4121f7dfac55edda2c99a3d86f39118232cfb3d4dc087'
related: []
---

# M232 locator correction follow-up review

## Scope

Independent follow-up review of mechanical M232 locator correction `c4b7545cf8` only. This review covers the related-party dispatch location, census references, mutation-test structure, and preservation of the existing deferred governance. S116's full two-pass comparison remains out of scope.

## Findings

### locator-alignment | low | resolved

The census capability locator and repository-grounding locator both now name that same live line. The prior line 168 is the preceding withholding branch and is rejected by the focused mutation assertion as `census capability locator drift`.

### governance-preservation | low | verified

The commit changes only the two M232 locator strings from 168 to 170 and adds the focused locator test. The row remains `ingress_blocked` with its existing campaign owner, 2026-12-31 expiry, bounded follow-up, and full reopening condition; it does not create a binding, resolver, fixture, lifecycle, or source-owned export claim.

### verification | medium | shared-worktree collection blocker

Direct static locator checks confirm both live references at line 170 and reject 168 from the census. The focused M232 pytest file and its single mutation test cannot collect because concurrent CLI WIP imports a missing `ArgumentSpec` from `cadrumo.entrypoints.cli._app_ledger_command_spec_support`; this is outside the correction's paths and prevents test collection before any M232 assertion executes.

## Recommendations

PASS for the mechanical locator correction, subject to rerunning the focused M232 pytest lane once the shared CLI import surface is coherent. Keep S116 open until its separately owned full canonical comparison completes.

## Verification receipt

- `rg` direct locator check: passed (both census references 170; live RELATED_PARTY dispatch 170; no census 168)
- `git diff --check c4b7545cf8^ c4b7545cf8`: passed
- `uvx vaultspec-core vault check schema --feature source-casilla-integration`: passed
- `uvx vaultspec-core vault check adr-status`: passed
