---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S239'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Rewrite profile export and subject-access documentation around the shared durable service, schema-derived categories, equivalent cleartext handoff risk, and separate sealed recovery archive

## Scope

- `docs/how-to/profile-setup.md`
- `docs/reference/import-export-and-evidence.md`
- `docs/reference/commands-and-configuration.md`

## Description

- Check the three named surfaces against the row's four requirements.
- Add the missing cross-reference where a reader doing a profile export would
  otherwise never learn the other two outputs exist.

## Outcome

SATISFIED. Two of the three named files were already complete; the third had a
navigational gap rather than a factual error.

The import-export reference carries all four requirements and carries them
well. It states that the portable export and the subject-access request are the
SAME bundle produced by one service, describes the schema-derived category
listing, and makes the equivalence explicit: the cleartext form is equally
readable once it leaves the application whichever purpose produced it, so both
carry the same handoff risk, with the instruction to delete it after handling
and not to email, sync or transfer it. The sealed custody archive is described
separately, as the encrypted backup-and-recovery artefact that neither export
substitutes for.

The commands reference correctly carries none of this. It is a delegating
lookup map that names live help as the command authority, so enumerating export
semantics there would duplicate the reference and then drift from it.

The profile guide was the gap. It taught export with both its cleartext and
encrypted forms, but never mentioned that the subject-access request produces
the same bundle, nor that the sealed archive is the thing you actually restore
from. A reader following that page to export a profile would reasonably believe
they had made a backup. The page now names all three and points at the
reference for the full treatment.

Gates at HEAD `136d17abc4c315bc1fa596dbb363867bf2324393`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed in 7.00s`.

## Notes

The gap is worth naming precisely, because nothing in the page was WRONG. Every
sentence about export was accurate. What was missing was the adjacency: three
outputs that look alike, one of which is a backup and two of which are not.
A page can be entirely correct and still leave a reader with a false belief,
and no conformance gate detects that - the commands all resolve either way.
