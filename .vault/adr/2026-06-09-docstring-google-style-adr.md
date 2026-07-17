---
tags:
  - '#adr'
  - '#docstring-google-style'
date: '2026-06-09'
modified: '2026-07-17'
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
