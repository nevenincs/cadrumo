---
tags:
  - '#adr'
  - '#calculation-engine-foundations'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-10-calculation-engine-foundations-research]]'
---

# `calculation-engine-foundations` adr: `Calculation-engine foundations: aggregation taxonomy and period-revision resolution` | (**status:** `accepted`)

## Problem Statement

The calculation engine's value channels had multiple overlapping aggregation mechanisms with implicit canonicality (the relation-vs-previous_filing overlap), and revision selection could be injected rather than law-determined. Both are foundational ambiguities that downstream fold-in campaigns surface as symptoms.

## Decision

Establish two foundations: (1) one canonical aggregation mechanism per calculation type per a declared taxonomy; and (2) law-determined period-to-revision resolution via select_revision, with any stored revision id only asserted-equal, never injected. Detailed decisions live in the sibling aggregation-taxonomy and period-revision-resolution ADRs.

## Status

Accepted.
