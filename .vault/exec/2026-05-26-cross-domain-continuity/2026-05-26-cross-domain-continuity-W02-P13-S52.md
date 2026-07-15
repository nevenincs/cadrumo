---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S52'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# dispatch round-8 persona fleet (landlord autonomo SL gestor multi-profile) CLI only

## Scope

- `.vault/audit/`

## Description

- Run the landlord/pensioner, autónomo, corporate, and gestor persona journeys through the shipped CLI in isolated encrypted stores.
- Confirm calendar suppression for a no-business pensioner/landlord and the clear Modelo 100 work-unit refusal for the absent filing-baseline activity description.
- Create a valid autónomo Modelo 130 work unit and confirm calculation refusals name the required prior-year inputs.
- Create valid corporate Modelo 200 and 202 work units, then confirm their calculation refusals name the missing statutory inputs.
- Re-run the gestor scenario with the canonical `aeat config switch <name>` command and verify active-profile changes across two real profiles.
- Reconfirm the existing Modelo 202 Article 27 high finding without treating it as a new persona-fleet defect.

## Outcome

All four persona routes completed with the shipped CLI. The gestor result passed after correcting the earlier operator command namespace: `aeat config switch Gestor-Cliente-A` and `aeat config switch Gestor-Cliente-B` changed the active pointer, and the status, overview, and profile-list surfaces reported the selected profile consistently.

The calendar correctly marked Modelo 100 applicable for the no-business landlord/pensioner, but work-unit creation refused the missing `activities.description` filing-baseline value. S53 subsequently confirmed this as a major calendar-to-readiness continuity defect. The autónomo and corporate calculation refusals were actionable missing-input refusals, not defects. The already-open Article 27 high finding was reproduced for a bare Modelo 202 work unit and remains open as S343.

The persona run itself had no new BLOCKER finding. Its Modelo 100 candidate was escalated to MAJOR only after S53 source grounding, which added corrective step S418.

## Notes

The initial gestor invocation used the nonexistent `aeat config profile switch` namespace. RAG-grounded CLI discovery corrected it to root-level `aeat config switch`; the rerun passed. The visible Madrid default notice when CCAA is omitted is explicit operator feedback, not a switching defect.
