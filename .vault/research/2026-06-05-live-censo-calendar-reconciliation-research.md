---
tags:
  - '#research'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-adr]]'
---

# `live-censo-calendar-reconciliation` research: investigation backing the decision

This research captures the investigation that backed the `live-censo-calendar-reconciliation` ADR.

## Findings

The investigation traced the calendar's obligation-derivation path and found no recorded provenance: a deadline could rest on live censo, on profile facts, or on an assumed default with no way to tell them apart. It established the three-outcome contract (live / profile / refuse) and the per-obligation provenance stamp the ADR adopts.
