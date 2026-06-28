---
tags:
  - '#adr'
  - '#docstring-google-style'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-06-09-docstring-google-style-research]]'
---

# `docstring-google-style` adr: `Enforce Google-style docstrings across src/aeat` | (**status:** `accepted`)

## Problem Statement

Docstring style across the codebase was inconsistent, undermining the generated API reference and reviewer expectations. No single style was enforced.

## Decision

Adopt Google-style docstrings across src/aeat and enforce the convention through the documentation gate, so the generated reference and the source docstrings share one format.

## Status

Accepted.
