---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:0cbe5cbe991f8ebc7f5acf0bad0f34fa85705310aebc976aabea28a3eb251031'
step_id: 'S312'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Measure whether the CLI redaction rule set matches a Spanish CIF in a free-text position, and record the answer as coverage gap or deliberate false-positive avoidance rather than assuming either

## Scope

- `src/cadrumo/core/redaction`

## Description

- Drive `redact_for_cli_output` with a CIF in three positions: bare, in a
  `label=value` assignment, and embedded in a free-text sentence.
- Repeat with a checksum-valid CIF and with a NIF as the discriminating control.

## Outcome

MEASURED, and the answer is NEITHER of the two the row anticipated: the CLI
rule set DOES match a Spanish CIF in a free-text position, so there is no
coverage gap and no deliberate false-positive avoidance to record.

The free-text sentence `The supplier CIF B12345674 appears here` returns with
the identifier replaced by `sha256:133cad41`; the bare form and the
`entity=B12345674` assignment form both redact identically. The letter-led
CIF `A20202024` and the NIF `12345678Z` behave the same way, so the arm is not
narrowly fitted to one kind letter.

The mechanism is why the answer is what it is: the CLI free-text path runs the
assignment substitution first and then hands the residue to `redact_for_log`,
which applies the shared `_DEFAULT_RULES` mapping. The `cif-hash` rule is a
member of that mapping, so free text inherits the whole default rule set
rather than a narrowed CLI-only subset. There is no separate CLI rule list to
be missing an arm from, which is the premise the row was written against.

No code change. The row's deliverable was the recorded answer and this is it.

## Notes

What this does NOT establish, stated so the measurement is not read as wider
than it is: it covers the CLI success-output funnel only. The structured
sibling and the error-document path were not driven, and a CIF printed inside
a value the assignment substitution rewrites to a placeholder is redacted by
the placeholder rather than by the CIF arm, so this measurement says nothing
about that arm's reach on those surfaces.
