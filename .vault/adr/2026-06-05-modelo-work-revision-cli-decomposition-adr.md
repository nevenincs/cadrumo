---
tags:
  - '#adr'
  - '#modelo-work-revision-cli-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-04-modelo-addressing-ux-research]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
  - '[[2026-06-05-modelo-addressing-ux-follow-up-queue-adr]]'
---

# `modelo-work-revision-cli-decomposition` adr: `revision commands are thin transports over modelo application facades` | (**status:** `accepted`)

## Problem Statement

The modelo CLI root had grown into a broad command module that mixed transport
registration with revision selection, verification, filing, rendering, and
residual command groups. That shape made the command surface hard to audit and
invited CLI-local business policy.

## Considerations

The accepted modelo addressing UX decision centralizes natural-key work-unit and
revision addressing in application facades. Revision command extraction can
therefore be a structural decomposition: command modules register CLI verbs and
delegate selection, verification, file, export, and projection behavior to
application services.

The follow-up queue records that hidden command state and non-singleton active
workspaces remain ADR-required future questions. This decomposition does not
introduce those behaviors.

## Constraints

CLI modules remain transports. They must not own work-unit selection policy,
revision-pick policy, registry authority, calculation behavior, verification
policy, or filing policy.

Existing command names, payloads, and selector behavior must remain stable
unless a separate ADR changes the operator contract.

Line-budget ratchets should shrink broad roots after extraction rather than
raising limits.

## Implementation

Extract revision listing, revision display, verification, and filing command
registration into focused CLI modules that call the public application facades.
Residual broad command groups are extracted into focused registrars until the
root-size guard passes.

Architecture and CLI behavior tests pin the transport-only boundary and command
compatibility.

## Rationale

This decomposition preserves the accepted addressing contract while making the
CLI easier to audit. Business policy remains in application/domain services;
the CLI only parses, delegates, and renders.

## Consequences

The CLI package gains more focused registrar modules. The root modules shrink,
and future command additions have clearer placement constraints.

## Codification candidates

- **Rule slug:** `modelo-cli-revision-commands-are-transport-only`.
  **Rule:** Modelo revision CLI commands must consume public application
  facades and must not implement revision selection, verification, filing, or
  registry policy locally.
