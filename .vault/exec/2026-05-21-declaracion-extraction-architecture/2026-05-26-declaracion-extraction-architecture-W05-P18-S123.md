---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W05.P18.S123'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-auth-gated-acquisition-status-audit]]'
  - '[[2026-05-26-declaracion-extraction-architecture-W05-P18-S122]]'
---

# W05.P18.S123 - no synthetic data to Sede acquisition policy

Implemented the hard operator constraint that synthetic data must not be sent
to Sede or AEAT-hosted form surfaces.

## Changes

- Removed the prior "explicitly approved live preview/download" acquisition
  path from the declaration-extraction plan and acquisition audit.
- Reframed the remaining fixture paths as:
  - operator-provided authorised fixtures produced outside this automation
    session;
  - authenticated read-only retrieval of operator-owned filed declarations;
  - other non-synthetic official artifacts.
- Kept modelos 180, 036, 369, 720, and 840 blocked because no qualifying
  artifact is present in the local corpus and the read-only filed-declaration
  listing returned zero rows for them.

## Surfaced Follow-Up

The broader codebase still has accepted live-parity surfaces that permit
synthetic data on AEAT-hosted endpoints:

- Modelo 100 Renta WEB Open.
- Modelo 349 GROI Spanish-counterparty check.
- Modelo 349 IXVI foreign-EU VAT-ID check.

Those are tracked as `W05.P18.S124` because they require ADR/plan follow-up
before changing registry schema, registry TOML, and live parity tests.
