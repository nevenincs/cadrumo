---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:4116b86709f4c2e87df4ec266b9db9e60f0c023d572db8b1bf6e051d7074bf41'
step_id: 'S469'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Replace the em dash the operator directive forbids across nine workbench keys in all four catalogues, using the spaced hyphen the gate prescribes for a label and its qualifier and a bare hyphen for the value that is only a no-value placeholder

## Scope

- `src/cadrumo/locales/{ca,en,es,hu}`

## Changes

`test_committed_catalogues_carry_no_em_dash` passes. Nine keys across four
catalogues, thirty-six values.

The gate states the replacement itself -- "a spaced hyphen reads naturally" --
and states when an exemption is warranted: an em dash inside a verbatim official
AEAT designation or legal citation, added by exact key. None of the nine is
that. They are the label-and-qualifier pattern the gate's own docstring
describes:

    Locked — unlock the selected profile to view this information
    Available — %{count} requiring attention

so all nine take the hyphen and `_EM_DASH_EXEMPT_KEYS` stays empty.

TWO SHAPES, NOT ONE. `tui.aeat_sync.value.none` is not a separator: its whole
value IS an em dash, standing for "no value" in a table cell. A spaced hyphen
there would render as a cell of padded punctuation, so it takes the bare
hyphen. The manifest builder refuses rather than guesses on any third shape,
and refuses again if a replacement still carries an em dash.

ONE NEAR-MISS WORTH RECORDING. `tui.home.action_context` reads
`%{label} — %{reason} · %{context}` -- an em dash AND a middle dot, which the
console renders identically as a replacement character. Replacing "the dash
separators" would have taken both. The builder keys on U+2014 alone, so the
middle dot is untouched; the console rendering is not evidence about the
character.

Written through `dev.locales set-batch` rather than by editing the catalogue
files, which is what the locale contract requires.

Teeth: re-introducing an em dash into one value through the same verb fails the
gate; restoring it through the same verb passes. Both directions went through
the catalogue authority, so the proof exercised the shipping path rather than a
hand-edit.

## Notes

THIS COPY IS ANOTHER WRITER'S. The wording came in on the concurrent TUI and
sync commits, and only the character changed -- no phrasing, no placeholder, no
ordering. The gate is a repo-wide operator directive rather than a matter of
taste, which is what makes this a gate fix rather than an edit to someone
else's prose.

REMAINING FAILURES ARE NOW EXACTLY THE BLOCKED PAIR.
`test_committed_catalogues_pass_production_audit` and
`test_committed_catalogues_follow_contextual_product_identity_contract` both
fail on `codebase_missing=('tui.ledger.reconciliation.direction...` -- the same
collision as the parity and shadow gates, which is the operator decision
recorded in S455 and sharpened in S457.

That means every pre-existing failing gate in this campaign is now either
closed or waiting on one of three decisions.
