---
tags:
  - '#adr'
  - '#calculation-engine-foundations'
date: '2026-06-10'
modified: '2026-10-03'
body_hash: 'sha256:4b76b9927378314bde7440a1cab7321ac078ed43e8e85d40675d64ad2dd67758'
related:
  - '[[2026-06-10-calculation-engine-foundations-research]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
---

# `calculation-engine-foundations` adr: `Calculation-engine foundations: aggregation taxonomy and period-revision resolution` | (**status:** `accepted`)

## Problem Statement

The calculation engine's value channels had multiple overlapping aggregation mechanisms with implicit canonicality (the relation-vs-previous_filing overlap), and revision selection could be injected rather than law-determined. Both are foundational ambiguities that downstream fold-in campaigns surface as symptoms.

## Decision

Establish two foundations: (1) one canonical aggregation mechanism per calculation type per a declared taxonomy; and (2) law-determined period-to-revision resolution via select_revision, with any stored revision id only asserted-equal, never injected. Detailed decisions live in the sibling aggregation-taxonomy and period-revision-resolution ADRs.
