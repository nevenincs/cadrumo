---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S280'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove the retired evidence-bundle replay from the modelo-390 records-audit sequence prose, which contradicts its own blocked annotation

## Scope

- `docs/_sequences/contracts/how-to/modelo-390/`

## Description

- Read the live audit command group and confirm its three registered verbs.
- Remove the retired replay verb from the records-audit sequence step prose,
  which contradicted the blocked annotation two lines below it.
- Sweep the documentation tree for any other citation of the retired verb.

## Outcome

SATISFIED. The step prose announced "Inspect, check, export, and replay an
evidence bundle by id" while the blocked annotation directly beneath it
already stated the correct set: the audit show, check and export verbs only
read bundles. The prose is now "Inspect, check, and export an evidence bundle
by id."

The verb set was established from the subject rather than from the annotation
that happened to agree with it: the audit command group registers exactly
`show`, `check` and `export`, and an exact search for the retired verb inside
that module returns nothing.

A tree-wide sweep found no other stale citation. Every surviving mention of
the word in the documentation tree is an unrelated live concept - the registry
parity replay verb, the subprocess replay re-entry marker, revision replay
inputs, and generated API stubs - and every mention in the test tree is a
negative assertion that the retired verb is absent, which is the correct shape
rather than a residue.

Gates at HEAD `84e55bde570e1b9429c4b4411e89291d8a147ba3`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py -m "" -n0`
  collected 8 cases and exited `8 passed in 1.87s`.
- `uv run --no-sync pytest
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 354 cases and exited `354 passed in 8.63s`.

## Notes

Recorded because it nearly produced a false negative. An initial sweep run
through the shell reported matches whose matched text rendered as a single
stray character, which read as though the citations had already been removed.
Re-running the same search through the file-search tool showed the real
content: the matches were intact and were negative assertions. A search whose
output is mangled is indistinguishable from a search that found nothing
interesting, so the disposition was taken from a second reader rather than
from the first one's rendering.
