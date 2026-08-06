---
tags:
  - '#adr'
  - '#quality-hardening-campaign'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:3a274eec22a72862eddbd3bd720330eb9b61a54a2be490a0a2569621f288cb1c'
related:
  - '[[2026-06-09-quality-hardening-campaign-research]]'
---

# `quality-hardening-campaign` adr: `Quality-hardening baseline: every justfile lane is a standing gate` | (**status:** `accepted`)

## Problem Statement

The repository's quality lanes (lint, type-check, tests, docs, dependency and import gates) were exercised ad hoc. A baseline was needed that treats every justfile quality lane as a standing gate with a recorded starting state.

## Decision

Treat every quality lane exposed by the justfile as a standing gate, with a recorded 2026-06-09 baseline. Subsequent hardening work is measured against that baseline and may only ratchet the gates tighter.

## Status

Accepted.
