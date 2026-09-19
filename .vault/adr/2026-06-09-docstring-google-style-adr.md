---
tags:
  - '#adr'
  - '#docstring-google-style'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:018386e435e0740e9670756f464a4e65274fc7c8a00642adc4ad0d802d9cb3b9'
related:
  - '[[2026-06-09-docstring-google-style-research]]'
---

# `docstring-google-style` adr: `Enforce Google-style docstrings across src/cadrumo` | (**status:** `accepted`)

## Problem Statement

Docstring style across the codebase was inconsistent, undermining the generated API reference and reviewer expectations. No single style was enforced.

## Decision

Adopt Google-style docstrings across `src/cadrumo` and enforce the convention
through the documentation gate, so generated reference material and source
docstrings share one format.

## Status

Accepted.
