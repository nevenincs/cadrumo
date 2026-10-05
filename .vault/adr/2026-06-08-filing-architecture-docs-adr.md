---
tags:
  - '#adr'
  - '#filing-architecture-docs'
date: '2026-06-08'
modified: '2026-10-03'
body_hash: 'sha256:20e71ae03ba4b9a8dfb390073a672f3dab5cc8f21025988fc33ff70810ee66f9'
related:
  - '[[2026-06-08-filing-architecture-docs-research]]'
---

# `filing-architecture-docs` adr: `Filing documentation taxonomy: generalized identity, lifecycle coverage` | (**status:** `accepted`)

## Problem Statement

The AEAT text-filing architecture lacked systematic, generic documentation of the tax preparation, verification, and local-filing lifecycle. Identity terminology was group-specific rather than covering every Spanish filing entity (NIF / CIF / DNI / NIE / NII).

## Decision

Document the filing lifecycle as persona-driven tutorials with generalized identity terminology (NIF / CIF / DNI / NIE / NII), covering preparation, verification, and local filing. Coverage is audited against the live surfaces so the docs cannot silently drift from the CLI.
