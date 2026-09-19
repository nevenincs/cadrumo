---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:c84f7e0c2e930b90a104096b63a1966e3e7ca54259976aa73b53b2eb5ee3e254'
related:
  - "[[2026-09-10-registry-temporal-coverage-plan]]"
---
# `registry-temporal-coverage` audit: `Provenance authority review`

## Scope

Review W01.P02's filing-authority provenance gate, its closed presumptive-evidence records, and the validated-authority projection.

## Findings

### presumptive-evidence-record | medium | A bare exception set did not preserve per-file review facts

The initial closed set bounded the legacy markup-only population but did not say why each path remained admissible. The implementation now uses path-keyed immutable records carrying a reason, reviewed citation, reviewer, and review date. A committed-catalogue proof requires every observed presumptive target to match a record and each record to agree with the cited entry's metadata.

### authority-resolution | high | A second corpus resolver would fork the validation contract

The authority projection must not reproduce corpus-path resolution. The accepted implementation validates the authority under its lock, retrieves the catalogue reference, and delegates classification to the canonical resolver using the authority source root. Review confirmed that no second resolver exists.

### real-registry-validation | medium | Full authority verification is pending host capacity

Focused classifier and refusal checks passed, but the full authority fixture reached the host-load guard during unrelated record-design workbook validation. The monitored run reported full CPU utilisation and a large concurrent Python population, then timed out without reaching the assertion. W01.P02 remains open until the real authority path returns a terminal result.

## Recommendations

Keep the exception mapping a ratchet: additions require a cited review record, and removal must happen when a corpus capture gains direct BOE attestation. Re-run the full validated-authority and committed-registry paths only after host load falls to a healthy level.
