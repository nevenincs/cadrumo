---
tags:
  - "#adr"
  - "#cli-action-envelope"
date: '2026-08-13'
related:
  - '[[2026-08-13-profile-password-custody-research]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-adr]]'
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
supersedes:
  - '2026-07-15-cli-authority-verb-conformance-adr'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:e68a82ad674f9eeff69cfc6a964e3713faa8f167eaf8282e6109ffb208128407'
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

The canonical commands are `aeat config profile restore` and `aeat config profile delete`; `restore --artifact` selects the explicit recovery-artifact proof door without creating a sibling command. The existing action-envelope hardening ADR owns request/result schema, action-chain resolution, refusal rendering, output formats, and authority checks. The custody roll-up owns operation semantics; `2026-08-23-cli-machine-secret-channel-unification-adr` owns scalar-secret transport requirements. This successor owns only their command-tree mapping and delegation boundary.

## Rationale

Delegation preserves one CLI envelope authority while removing backend-shaped command semantics.

## Consequences

Future custody verbs must extend the existing action-envelope schema before exposure; they cannot introduce a parallel envelope.
