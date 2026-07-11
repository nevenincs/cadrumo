---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S06'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censo-operator-manual-enrolment with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-11-censo-operator-manual-enrolment-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Re-author the inicio-actividad and cese-actividad agent skills onto the operator-manual censo mirror so the rule-surface conformance gate stays green and ## Scope

- `src/aeat/_data/agent/skills/inicio-actividad/SKILL.md`
- `src/aeat/_data/agent/skills/cese-actividad/SKILL.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
