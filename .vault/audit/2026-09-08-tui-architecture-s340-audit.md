---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:b435b7eeb3e59fd2357517fa3c04951ab4494f2d85c67d7c41ecba67bc5143bd'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `tui-architecture` audit: `S340 supervised Google Sheets export`

## Scope

The supervised Google Sheets export command, its terminal error projection, effect truth, asynchronous transport boundary, and journal-and-lease acceptance evidence were reviewed against S340 and the binding ADR amendment.

## Findings

### error-owner-allowlist | critical | CLI duplicated canonical error ownership

The first implementation filtered registered codes by declaring-module prefixes and missed valid Google authentication subclasses. Remediated by resolving stable codes directly through the canonical ErrorCode registry.

### actionable-message-loss | high | Instance-only credential failures lost actionable messages

OAuth client, token, and authentication-dependency failures previously shared broad exception classes with instance-specific messages. Remediated with specific registered export precondition errors at the composition boundary.

### preflight-effect-truth | high | Configuration failures could settle with unknown effect

Credential and root-folder resolution occurred after the apply effect became unknown. Remediated by preparing the transport before entering the irreversible section.

### blocking-async-transport | high | Google I/O blocked the supervisor event loop

The synchronous transport was called directly from the async executor. Remediated by moving preparation, preview, and apply calls through `asyncio.to_thread`.

### acceptance-evidence | high | Tests did not exercise the changed command or a live lease

The first proof observed only a released lease after direct supervisor execution. Remediated with command-level success and error projection coverage plus inspection of the lease while the command is held running.

### profile-error-classification | medium | Admission and subject corruption shared one error

Active-profile drift and subject/payload contradiction used one ERROR category. Remediated with separate REFUSED admission and ERROR invariant classes.

### canonical-code-validation | medium | Public failure codes accepted unregistered tokens

Receipt and projection validation checked shape but not registry membership. Remediated with one canonical stable-code resolver and negative validation coverage.

## Recommendations

Retain the prepared-transport boundary, canonical ErrorCode lookup, split profile errors, and live-lease command test as regression gates. Close S340 only after the final SOL review and focused verification pass.
