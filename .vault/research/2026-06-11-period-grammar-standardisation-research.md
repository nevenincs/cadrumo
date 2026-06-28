---
tags:
  - '#research'
  - '#period-grammar-standardisation'
date: '2026-06-11'
modified: '2026-06-11'
related:
  - '[[2026-06-11-period-grammar-standardisation-adr]]'
---

# `period-grammar-standardisation` research: investigation backing the decision

This research captures the investigation that backed the `period-grammar-standardisation` ADR.

## Findings

The CLI accepted multiple conflated period spellings (`2026Q1`, `2026-03`, `2026`, and the `2026-1T` hybrid) alongside the canonical `--year YYYY --period <AEAT-token>` shape. The investigation inventoried every conflated spelling and its call sites, and confirmed the D4 amendment of the `2026-06-10-cli-operator-surface-adr` (AEAT tokens only; year always a separate axis). It scoped the burn-down to the single typed `Period` value object the ADR adopts.
