---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:6630a9c4d1ff0cc61a969d67bcf3f905af28f5b0b1e22deb6ea341bccc722576'
related: []
---

# `aeat-design-relayout-boundary` audit: `deliberately-refusing filing years`

## Scope

## Findings

## Recommendations

## Context

Every filing year this plan deliberately leaves refusing rather than correctly exported, stated beside what the standing goal still asks for that the narrowing excludes.

The Modelo 232 export trees were published while their revisions temporarily carried an `agent_reviewed` stamp that was reverted in the same session, so the committed trees validate under a review state the revisions no longer claim. The enrollment pins at `pending_review` assert the current state and the tree content does not depend on the stamp. Recorded so a later reader does not read the publication journal's validation as attesting a reviewed revision.

## Refusing years, per modelo

- Modelo 303: filing years 2009 through 2021 refuse by name (`select_revision`'s no-revision refusal; the renamed `2022` revision's selector starts at 2022). What the standing goal still asks: correct exports for those years — 14 years of quarterly IVA returns. The narrowing's grounds: the prescripcion-reachable window computed at 2026-08-08 starts at 2022, and the pre-window designs are not the revision's layout.
- Modelo 390: filing years 2010 through 2021 refuse by name (the `2022` revision is the earliest; `2010-y-siguientes` was retired). What the standing goal still asks: correct exports for those 12 annual years.
- Modelo 200: filing years 2022 and 2023 sit inside the prescripcion window while no registry revision claims them; they refuse today as a coverage gap rather than as a mis-write. What the standing goal still asks: those two in-window years served (tracked as the 200 export-layout backlog).
- Modelo 303 `2022`'s own export layout, deadline windows and the 200/390 export trees are gaps the exports refuse on — recorded per-step in S22/S31/S33/S34/S52 records with their owning rows in the export-fragment generator authority plan.

## Basis of the window

The four-year period is grounded on the tree's canonical retention floor (Ley 58-2003 arts. 66/67 are not bundled); the voluntary deadline it is measured from IS bundled (Orden EHA-3786-2008 art. 7 for 303, Orden EHA-3111-2009 art. 8 for 390). The window decays: 303 filing year 2022 loses its 3T period on 2026-10-20, so a later executor recomputes rather than reading the edge off this document.
