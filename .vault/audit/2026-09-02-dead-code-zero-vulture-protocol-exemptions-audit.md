---
tags:
  - '#audit'
  - '#dead-code-zero'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:3f4ad937177e8e309d00453f9d841d00d7de39521e624227152c2086e2272fb3'
related: []
---

# `dead-code-zero` audit: `vulture protocol exemptions`

## Scope

Review the three Protocol-parameter exemptions introduced in commit `5521c625b0` against Vulture's real name-matching behavior, the live Protocol call surfaces, and the focused detector tests.

## Findings

### global-name-suppression | high | The exemptions can hide unrelated dead code

Vulture treats every loaded name in `dev/audit/vulture_whitelist.py` as globally used. The entries for `quota_project_id`, `clock_skew_in_seconds`, and `interaction_facts` therefore suppress every same-named occurrence in the scan, contrary to the file's claim that other occurrences remain detectable. The focused tests prove parsing and live execution but do not prove exemption freshness or masking teeth.

### protocol-surface-width | medium | The exempted names are not required runtime contracts

The Google parameters are optional upstream keywords that Cadrumo never passes, and the local Protocols do not mirror the full upstream signatures. The operation projector parameter is positional-only and the registry validates positional arity, so its spelling is not part of the runtime contract. None of the three warnings is evidence of an unwired capability.

## Recommendations

Remove the three global whitelist entries. Narrow the Google Protocols to the call surface Cadrumo actually uses and rename the positional-only operation parameter with a leading underscore. Add focused detector tests proving the live scan remains green without expanding global suppression.

Resolved by commit `bf49393e6d`: all three exemptions were removed, the Protocols were narrowed without changing runtime arity, and an isolated real-Vulture regression proves those names remain detectable. Focused runtime, type, lint, and dead-code checks pass; second-pass review found no residual issue.
