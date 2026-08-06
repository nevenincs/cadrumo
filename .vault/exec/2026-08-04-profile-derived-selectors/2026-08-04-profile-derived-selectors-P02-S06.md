---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:7d42fb6af538424e6cbd8e42ca97ba3f05158119baac0013e3766b25d2024c07'
step_id: 'S06'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Confirm the refusal copy follows the validation module's own convention rather than adding a locale key, because every sibling issue message there is a formatted string and the translator is not imported, so a catalogue entry for this one message would be the inconsistent pattern and would leave the copy split across two homes

## Scope

- `src/cadrumo/application/user_profile/_validation.py`

## Description

## Outcome

Resolved by ruling rather than by execution: no locale key was added, deliberately.

The Step as written assumed the validation module was locale-backed. It is not. Every sibling
issue message there is a formatted string and the translator is not imported at all, so a
catalogue entry for this one message would have been the inconsistent pattern rather than the
consistent one, and would have split the copy across two homes.

The executor assigned this Step reached the same conclusion independently and then talked
itself back out of it, on the grounds that the Step text named locale copy as a deliverable.
Its own framing afterwards is the durable lesson: that is treating the Step text as authority
over the code, which is backwards, because the module is what tells you what the consistent
pattern is. The Step was re-scoped to record the ruling rather than executed against a module
that is not locale-backed.

This record was missing when the Step was checked, which breached the closure discipline and
was caught by the closing audit. The ruling had been written into a sibling Step's record
instead of its own, so the reasoning existed but was not where a reader of this Step would
look. Corrected here.

## Notes
