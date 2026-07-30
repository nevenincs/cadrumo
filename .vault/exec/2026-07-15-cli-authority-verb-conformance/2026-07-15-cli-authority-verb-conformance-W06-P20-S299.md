---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S299'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Bound the shelled gettext build in the catalogue-drift POT fixture with a timeout so an upstream hang surfaces as a named failure instead of wedging the documentation lane indefinitely, since the call currently passes no timeout and the hang reproduces at zero workers

## Scope

- `dev/docs/i18n.py`
- `dev/docs/tests/test_docs_catalogue_drift.py`

## Description

- Bound both shelled documentation builds in the i18n module, not just the one
  that was observed hanging.
- Make the timeout a NAMED failure carrying the command and the bound.

## Outcome

SATISFIED. Both shell calls in the module are bounded and the bound is proven
to fire.

The module shelled two builds with no timeout: the gettext POT extraction, and
the sphinx-intl catalogue update. Only the first was observed hanging, but the
second has the identical shape and would fail identically, so both are bounded
rather than only the one that happened to be caught.

The ceiling is 900 seconds, deliberately generous. The full-scope nitpicky build
is documented in-tree at roughly 840 seconds and the gettext extraction covers a
subset of that page set, so a tight bound would convert slow-but-healthy runs
into failures. The point is not speed. An unbounded shell call converts any
upstream hang into an indefinite lane wedge carrying no diagnostic at all, which
is how this defect survived three separate investigations.

The failure is diagnostic rather than bare. It names the step, the bound, the
command, and - the part that matters for the next reader - what the hang looks
like from outside: an unresponsive pytest worker reported as `node down: Not
properly terminated`, or a lane that simply stops emitting output. Anyone who
meets either symptom now has a string to search for.

MUTATION-PROVEN, because a timeout argument that is present but never exercised
is indistinguishable from one that is absent. With the ceiling temporarily
lowered to 2 seconds, a deliberately-sleeping child raises `SystemExit` carrying
the expected message. Without the bound the same child runs to completion.

Gates at HEAD `8b1b64136606e99d9829d6a06b8c7f830f5e31d2`:

- `uv run --no-sync ruff check dev/docs/i18n.py`: All checks passed.
- Bound probe: a 30-second child under a 2-second ceiling raised `SystemExit`
  with `probe exceeded its 2s bound and was terminated. Command: ...`.

## Notes

This fixes the SYMPTOM's blast radius, not the underlying hang. Why the Sphinx
gettext build does not return on this host is still not established, and the
sibling record says so rather than guessing. What changes is that the next
occurrence fails in fifteen minutes with a named command instead of wedging a
lane indefinitely and being misread as a stall, a worker defect, or a
parallelism artefact - all three of which it was called before anyone read a
stack trace.
