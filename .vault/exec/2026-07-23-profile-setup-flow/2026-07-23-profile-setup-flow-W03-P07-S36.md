---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:eb1d5b7bdbfbdc33072072c9bdd36e11a0693b42fbe883ad633393355c4f9dd9'
step_id: 'S36'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Route interactive-edit descendant answers through the edit persist seam with count-shrink clearing, or gate the descendant group out of modify mode until that seam exists, closing the silent-no-op-on-write gap

## Scope

- `src/cadrumo/application/wizard/_persistence.py`

## Description

- Take the GATE branch: make the descendant-group splice mode-aware in `_setup_flow_definition`, attaching the count page and repeating group only for CREATE and withholding them for MODIFY, so the interactive edit walk never renders a descendant page whose answers the edit persist seam would silently drop.
- Thread the mode through both splice callers: `_prepare_interactive_flow` and `_run_scripted_walk` request the group only when the wizard mode is create.
- Surface the withheld surface loudly, never silently absent: every interactive modify run's final envelope carries a new info notice pointing the operator at the dedicated descendant-management command, mirroring the existing modify-no-resume disclosure and pre-rendered in the command output language.
- Close the create-resume seed gap the same cluster owns: add `descendant_answers_from_record` as the inverse of `descendant_facts_from_answers`, re-projecting the on-record `renta_family.descendiente.*` facts into the `descendientes-count` answer plus one `descendientes#<index>.<page>` answer per populated field, and wire it into `checkpoint_answers_from_record` so a resumed create re-seeds the group through the substrate resume walk.
- Add real-behaviour coverage: a save-then-resume round-trip proves the count page and both instances re-project, the substrate resume walk re-instantiates the group with no stale answer, and completing from the resumed answers reconstructs an identical descendant fact set; two envelope tests pin the door notice; one structural test pins that the modify definition carries no descendant pages, count page, or adoption validator while the create definition carries all three.

## Outcome

Landed as `9a21970bc8`. The edit persist seam full-implementation was assessed UNBOUNDED and gated instead: modify-mode seeding cannot instantiate the repeating group, because the modify frontend seeds render-time page defaults over a fresh `start_flow` state while instance pages are generated dynamically from the group count rather than being static items the default-seed mechanism can reach; the `resume_state` channel that would carry a `resume_flow`-built state exists on the line frontend but is not plumbed through the capability-selecting entrypoint runner. Rendering the group unseeded in modify would show existing descendants as an empty group whose commit, via the namespace-replacing clearing guard, would silently erase them. The gate is safe and honest, and the create-mode resume seeding it depends on is proven by round-trip test. The `pytest src/cadrumo/application/wizard src/cadrumo/application/flows` gate is 400 passed / 0 failed; ruff clean; collect-only clean.

## Notes

- Branch decision (gate vs full seam): the DECISION FRAMEWORK's full-seam preconditions are unmet within the modify model. The clearing guard fires whenever the count page carries an answer; the line frontend's full walk answers the count page at its zero default, so a full seam without instance seeding would wipe existing descendants. Correct instance seeding needs the resume walk, which the ADR excludes from modify and which is not wired through the entrypoint frontend runner. Gate is the ADR-sanctioned safe arm.
- One net-new locale key: `application.wizard.notices.modify_descendants_via_door` with a `{command}` placeholder, referenced through `tr(..., default=..., command=...)` so the code renders standalone; the four-locale copy belongs to the catalogue lane.
- Concurrent peer landings during the session: the one-shot prompter retirement and the apoderado configure-door both landed to HEAD mid-session; the commit sits cleanly on top and stages only its five authored files (verified zero foreign hunks before commit).
- The sibling descendiente-door step is left open: the just-landed apoderado configure door is the exact viable template (a self-contained flow hosted on the capability-selecting frontend in MODIFY mode with the flag path preserved), but it is a sizable additive door feature, not a bounded edit-seam change.
