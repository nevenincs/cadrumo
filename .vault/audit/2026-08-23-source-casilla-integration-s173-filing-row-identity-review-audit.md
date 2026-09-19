---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6b61dbb6bca38f114f7ebf5395216c2d52663cd3bbef95efdfea5ea97c49d6b9'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `source-casilla-integration audit: s173 filing row identity review`

## Scope

Independent review of filing row-identity invariants, confidentiality, draft hashing, encrypted persistence, prepared-write parity, and M720 compatibility.

## Findings

### s173-filing-row-identity-review | high | resolved secure persistence omission

The identity is excluded from ordinary serialization, so the generic filing-draft writer initially omitted state that the draft hash retained. Both encrypted write paths now use an explicit secure serialization context, the namespace is version 2, and a real encrypted roundtrip preserves exact identity-bearing equality without plaintext canaries.

### s173-filing-row-identity-review | high | resolved prepared-write integrity bypass

Direct save and prepared batch write now invoke one durable content-address validator. A real prepared `save_many` roundtrip succeeds for an identity-bearing draft, while a stale identifier refuses before a write is constructed.

### s173-filing-row-identity-review | pass | final filing identity contract is coherent

The filing state preserves exact binding/row/source identity and fingerprint coordinates, rejects scalar and mismatched identity, keeps unidentified M720 rows valid, and does not propagate into S174 or later surfaces. Final independent review reported zero findings.

## Recommendations

Proceed with S174 using the explicit secure filing-state contract. Keep ordinary output redacted and do not reconstruct identities from binding values or row order.
