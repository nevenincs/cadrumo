---
tags:
  - "#adr"
  - "#cli-action-envelope"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
  - '[[2026-08-23-cli-machine-secret-channel-unification-adr]]'
supersedes:
  - '2026-07-15-cli-authority-verb-conformance-adr'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6b8f8b1f5f092f7fc337ec29c856a0b6d412a1bfef62d53411bac06b56827de8'
---
# `cli-action-envelope` adr: `profile custody action envelope grammar` | (**status:** `accepted`)

## Problem Statement

The superseded CLI authority record mixed backend ownership with general command-cost and action-envelope rules. Custody needs canonical verbs without forking the accepted application-owned action-envelope architecture.

## Considerations

- `2026-08-09-cli-action-envelope-hardening-adr` remains authoritative for application verdicts and schema-resolved action chains.
- Custody semantics belong to `2026-08-13-profile-password-custody-rollup-adr`.

## Considered options

- Restate the action-envelope contract here: rejected as semantic duplication.
- Bind custody verbs to the existing owner and retain only command mapping: accepted.

## Constraints

Entrypoints render typed application outcomes and cannot infer storage backend, author security decisions, or carry secrets in argv or environment. Scalar-secret option declaration, payload metadata, and channel selection defer to `2026-08-23-cli-machine-secret-channel-unification-adr`.

## Implementation

The canonical commands are `aeat config profile restore`, `aeat config profile restore-recover`, and `aeat config profile delete`. The existing action-envelope hardening ADR owns request/result schema, action-chain resolution, refusal rendering, output formats, and authority checks. The custody roll-up owns operation semantics; `2026-08-23-cli-machine-secret-channel-unification-adr` owns scalar-secret transport requirements. This successor owns only their command-tree mapping and delegation boundary.

## Rationale

Delegation preserves one CLI envelope authority while removing backend-shaped command semantics.

## Consequences

Future custody verbs must extend the existing action-envelope schema before exposure; they cannot introduce a parallel envelope.

2026-08-18 amendment (campaign-close proof, S24): the canonical verb is `restore --artifact`, not `restore-recover`; the composite spelling was retired before shipping.
