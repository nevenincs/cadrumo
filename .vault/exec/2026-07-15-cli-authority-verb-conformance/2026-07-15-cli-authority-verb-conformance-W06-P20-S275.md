---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S275'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Teach the documented-command conformance parser to recognise a blocked-row marker rather than reading its prose as a command path

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`

## Description

- Reproduce the reported conformance failure at current HEAD rather than
  inheriting the report.
- Locate the parser's handling of prose directives and read the regression
  test that pins it.
- Attribute the fix to the commit that landed it and confirm the proof is not
  tautological.

## Outcome

SATISFIED, by a peer commit, verified here rather than assumed.

The gate no longer reads a blocked-row marker as a command path. The parser
now skips prose directives by an explicit rule matching the blocked, capture,
expect and note directives, replacing a scheme that skipped them only because
their syntax happened not to contain the product name - which made the whole
gate depend on documentation prose never using that word. The blocked reason
that broke it read "No aeat verb creates an evidence bundle", and the sentence
after the product name was resolved as a verb path.

The fix landed one day before this verification, in a commit whose subject
states the mechanism exactly. Attribution was established with a content
search over the file's history rather than inferred from commit subjects
sitting near it in the log.

The accompanying regression test was read rather than counted, because a
regression test that only asserts the failing case is half a proof. It asserts
the blocked reason and two sibling prose directives all parse to nothing, AND
that a real setup frame still parses to its verb tokens - so the skip cannot
hide an invocation that should have been checked. That second assertion is
what makes it a discrimination proof.

Gates at HEAD `84e55bde570e1b9429c4b4411e89291d8a147ba3`:

- `uv run --no-sync pytest
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 354 cases and exited `354 passed in 8.63s`, including
  the blocked-reason regression.

## Notes

No work was needed here, and saying so is the point of the record. The close
review recorded this failure against a file that was uncommitted peer work at
the time; both the file and its parser fix have since landed. Had this Step
been executed on the review's description rather than re-measured, it would
have produced a second fix for a defect that no longer existed.
