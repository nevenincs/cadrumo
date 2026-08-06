---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-17'
body_hash: 'sha256:d45f72b69fc45f4e02c34817730dd30f6e1b058a1ccf2c59e6b6c4adc104ccf5'
step_id: 'S06'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

# Re-author the inicio-actividad and cese-actividad agent skills onto the operator-manual censo mirror so the rule-surface conformance gate stays green

## Scope

- `src/aeat/_data/agent/skills/inicio-actividad/SKILL.md`
- `src/aeat/_data/agent/skills/cese-actividad/SKILL.md`

## Description

- Rewrite the inicio-actividad procedure step 3 from the retired
  `censo pull` / `compare` / `apply` mirror onto the operator-manual path:
  the taxpayer's filed Modelo 036 copy is read together and the facts are
  entered through `config profile edit`, with the
  `censo.enrolment_unverified` disclosure named explicitly.
- Rewrite the cese-actividad procedure step 3 the same way and align both
  skill descriptions and success assertions to record-by-hand wording.
- State in both skills that AEAT publishes no read-only censo view the
  application could fetch, so the profile mirrors AEAT only as faithfully
  as the taxpayer's own copy.

## Outcome

Both life-situation skills cite only live verbs (`config profile edit`,
overview verbs); no retired censo verb remains anywhere under the agent
harness tree. Rule-surface conformance
(`src/aeat/agent/tests/test_rule_surface_conformance.py`) passes together
with the operator-surface and MCP toolset suites (56 passed). Committed in
`3a48c4fe87` with an explicit pathspec.

## Notes

Executed against the working tree carrying the peer-authored P01 scrape
deletion (uncommitted at execution time); the skills themselves carried no
peer WIP. The rewritten wording preserves the honesty posture the ADR
mandates: operator-declared, never AEAT-verified.
