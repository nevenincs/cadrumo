---
tags:
  - "#adr"
  - "#secure-storage-hardening"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-06-30-bucket-custody-completeness-adr'
  - '2026-05-22-secure-storage-production-hardening-architecture-adr'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2fce6f5d56de5271945c11d13b3e66e0c426948d47fa12d5b4f7767cc380ae16'
---
# `secure-storage-hardening` adr: `non-custody secure storage hardening` | (**status:** `accepted`)

## Problem Statement

Secure storage still needs canonical data taxonomy, permission, validation, and diagnostic boundaries after shared-master custody is removed.

## Considerations

- Password and DEK authority belongs only to `2026-08-13-profile-password-custody-rollup-adr`.
- Financial payloads remain secure-storage-only.
- Diagnostics must not disclose profile secrets or financial content.

## Considered options

- Preserve provider-oriented hardening: rejected because provider fallback is superseded.
- Retain storage controls independent of custody: accepted.

## Constraints

Every durable artifact must have one taxonomy owner, bounded parser, no-follow path resolution, restrictive permissions, and explicit integrity handling.

## Implementation

The storage taxonomy remains the canonical inventory for profile data, transactions, caches, exports, and local deletion. Writers stage, fsync, atomically replace, and fsync parents where the owning protocol requires durability. Readers reject duplicate members, unknown schema, traversal, links, reparse points, and oversized input before allocation. Logs and typed errors expose operation, UUID-safe correlation, and error class, never passwords, keys, mnemonics, tax identifiers, or payload content. Custody files and their transactions follow the roll-up instead of a generic provider abstraction.

## Rationale

These controls remain valid for every encrypted storage format and do not depend on how its DEK is wrapped.

## Consequences

Hardening remains centralized while shared-master, AUTO, fallback, and legacy-read rules disappear.
