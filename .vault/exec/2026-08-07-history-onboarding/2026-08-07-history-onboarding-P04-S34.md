---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:9185f139688c68af46696b3b369c906bd303a55e4bfeee9938a523349f13a18d'
step_id: 'S34'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
## Description

This row is a decision, and the decision is: the declaration stays empty, and the
prose stops claiming otherwise.

The two options were never equivalent. Populating the mapping is a tax review
against official sources, per entry, deciding which registry-less obligation
still carries a filing duty a taxpayer must be told about. Nothing in the
codebase can derive that, and no research tooling was available in this
execution, so inventing entries would have manufactured grounded-looking legal
claims out of nothing — a far worse outcome than an honestly empty set. The
conservative branch the row itself sanctions was taken.

## Outcome

- The false paragraph is gone from the declaration in `core`. It had claimed the
  set "covers the common retención autoliquidaciones and declaraciones
  informativas an autónomo, a PYME, or an entity may owe, grounded against AEAT's
  published catalogue". No such set was ever declared, so the prose asserted a
  property the module does not have — the specific failure this row names.
- Replaced with an explicit statement that the mapping is intentionally empty,
  that the surrounding sentences describe the MECHANISM rather than any present
  member, and why it stays empty: a per-entry tax review against official BOE and
  AEAT text, with human reviewer sign-off. The retirement of the censo
  simplificada by Orden HAC/1526/2024 is cited as the worked example of a fact
  that needs a source rather than an inference.
- The consuming disposition branch is explicitly preserved, and the reason is
  written down on both sides: it is unreachable from production input only
  because the out-of-scope partition resolves first, so it reads as dead code to
  anyone optimising for a green tree, while deleting it would silently withdraw
  the advisory capability for taxpayers whose obligation is registry-less.
- The overview coverage module's disposition docstring gained the matching note,
  so a reader arriving from the branch rather than from the declaration learns
  the same thing.
- Also recorded, because it is the part a later reader would misread: today's
  coverage proves the disposition classifies a SUBSTITUTED declaration correctly,
  not that any actually declared obligation is correct. The first real entry
  therefore inherits a gate that already bites.

## Verification

The same-object assertion this row requires kept was not touched, and still
reads `_coverage._UNMODELED_OBLIGATIONS is UNMODELED_OBLIGATIONS`.

    uv run --no-sync pytest src/cadrumo/core/tests/test_unmodeled_obligation_declaration.py src/cadrumo/application/overview/tests/ src/cadrumo/tests/test_modelo_authorization_gate.py -q -p no:randomly
    252 passed in 28.57s

`ruff check` and `ruff format --check` clean on both modified modules.

## Notes

No legal entries were invented, and none should be added by a coding pass.
Populating the mapping needs a dedicated legal-research pass against BOE and AEAT
sources with operator sign-off, tracked separately from this plan.

Both changes are prose only; no behaviour changed and no declaration gained a
member, so the branch remains unreachable from production input exactly as
before. That is the intended end state of this row, not an incomplete one.

A tree-wide documentation build gate was red during this work
(`test_rendered_site_identity_and_static_marks_are_canonical`, a legal-catalogue
directory missing under the build's temporary root). It is unrelated: the failing
handler runs at builder-inited, before any docstring is read, and it fails
identically serially and in parallel. Recorded here only so a later reader does
not attribute it to these edits.
