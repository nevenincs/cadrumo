---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:6a58164c6fb4fdd07343ecfbfbbe36c4a3e8e5b07f526c3965162f9ede55e249'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S14 action schema resolution`

## Scope

Independent fresh-context review of `W02.P04.S14`: canonical catalogue action
resolution against reconciled live command, result-schema, and required-input
identities, including declarative action profiles and explicit no-recovery
outcomes. The review deliberately excluded the pending MCP projection owned by
S15.

## Findings

No findings. `ResolvedCatalogueAction` resolves only catalogue declarations and
rejects orphan targets, absent or mismatched result/input accounting, and
insufficient required-input sources while allowing declared extras. The profile
resolver rejects duplicate, orphan, ambiguous, and unknown identities and
retains explicit `NoRecoveryOutcome` cases without inventing a recovery action.
The live integration test derives both schemas from the materialized production
Click tree and iterates every canonical catalogue declaration. The S13
`ManifestActionProfile` facade import and export remained peer-owned and
unchanged by this review.

### formatting-boundary | low | The changed contract test fails the formatter gate

The public-facade import change in `test_contract.py` was semantically correct,
but the file's existing formatting and CRLF boundary made the formatter propose
unrelated whole-file changes.

Resolution: closed. The post-S14 import-hygiene edit was removed and the file's
Git blob now exactly equals HEAD, so it is no longer part of S14. The dedicated
S14 live-resolution test continues to consume the existing input-schema builder
through the MCP package facade. Every changed S14 file passes the exact Ruff
format check.

## Recommendations

No S14 remediation remains. S15 should consume this resolver for MCP projection
rather than introducing another action-to-schema join. The existing S07 private
test imports remain a classified broader-tree import-hygiene residual.
