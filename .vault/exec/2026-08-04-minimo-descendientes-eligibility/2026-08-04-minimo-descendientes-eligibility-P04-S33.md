---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:0ef941bff97b0e6391b5baa9e1805142d7e359e458af41a62ac82bbe9459c694'
step_id: 'S33'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Point both maternidad remedies at a route that can edit a declared row

## Scope

- `src/cadrumo/locales/`
- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

## Description

- Replace the append-only remedy named by the two-authorities refusal and the withheld advisory with the remove-then-add route that can actually change a declared descendant.
- Update the same instruction in all four catalogues.

## Outcome

Both remedies now name a route an operator can execute. The previous instruction told them to clear the declared months using the descendant add verb, which only appends rows; the paged editing door refuses on a piped host, so for the autonomous-agent operator this CLI is built for there was no actionable path at all.

## Notes

The operator-facing text of a refusal carrying a translated message does NOT come from the Python exception string — it comes from a locale-catalogued key. So a change to the source leaves the operator reading the old sentence unless all four catalogues move with it, and nothing gates the two staying in sync. The locale audit does not flag it. That silent-divergence trap was found while executing this Step and is the reason its two halves had to land together.

They did not, at first. The code half committed on its own and the four catalogues were left staged for an automated sweep that never came, so HEAD briefly carried the corrected source alongside the old operator instruction — the exact divergence this Step exists to close, produced by the agent that had just identified the mechanism. Knowing about a divergence does not protect against it when the two halves land through different mechanisms. Closed by committing the catalogues explicitly.

An earlier attempt to isolate a single hunk against the shared index corrupted that index twice. The scratch-copy method anchored on the committed file behaved correctly on the third attempt: it reported nothing to apply, because the change was already staged. That is the method working, not failing.
