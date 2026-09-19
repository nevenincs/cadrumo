---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:a43a25099518c1ac8e11a784c8a32cfa161c85d909197b53fac161afbeb2d1c9'
step_id: 'S08'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Extend the overview CLI Notice composer to include deemed-served notifications in a warning-severity Notice carrying the P01.S03 legal catalogue entry id and the affected certificado ids on Notice.context, add the new locale keys through python -m dev.locales set with real es, en, ca and hu strings for every key, and run the locale scaffold check

## Scope

- `src/cadrumo/entrypoints/cli/_overview_rendering.py`
- `src/cadrumo/locales/es.yml`
- `src/cadrumo/locales/en.yml`
- `src/cadrumo/locales/ca.yml`
- `src/cadrumo/locales/hu.yml`
- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Add a dedicated warning-severity Notice composer for notifications the law
  already deems served, keyed on the deemed-served service state rather than on
  the procedural kind, and carry the catalogue entry id, the affected
  certificado ids and the count on `Notice.context`.
- Wire it into both calendar rendering surfaces beside the existing pending
  post-filing notice -- the single-profile output and the per-profile one,
  which tags each notice with its profile label.
- Add the new locale key with real es, en, ca and hu strings through the
  locales CLI, and run the scaffold drift gate.
- Add tests pinning the notice shape, its legal provenance resolving against
  the live registry catalogue, the negative cases, and the structural reason
  this notice has to exist at all.

## Outcome

The deemed-served row now reaches the operator with the one fact it needs: WHICH
certificados are already running their plazos, and under which provision. It
could not have been reported through the existing pending post-filing notice,
and one of the tests exists to pin exactly that. That notice builds both its
`kinds` list and its context map from `post_filing_kind`, filtering rows where
it is `None`. A plain notificacion whose concepto matches no sharper procedural
pattern has no kind, so after the previous Step's widening it made the pending
notice FIRE with an empty context -- the operator told that something needs
attention and never told what. The regression test asserts that empty context
directly, so a future refactor cannot quietly merge the two notices and
reintroduce the blind spot.

The catalogue entry id rides on the notice rather than being baked into the
prose, so a machine consumer keeps the provenance and an operator can trace the
claim that an unopened notification is nevertheless served back to the article
that says so. A test resolves that id against the live registry catalogue and
runs the corpus verification against it, so the notice cannot ship citing a
provision that does not exist.

The certificado id list is sorted and deduplicated, and the in-window rows are
excluded rather than merely deprioritised.

## Verification

    uv run --no-sync pytest .../test_overview_deemed_served_notices.py .../test_overview_post_filing_notices.py -q -p no:randomly -m integration
    11 passed in 60.86s

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok

    uv run --no-sync ruff check src/cadrumo/entrypoints/cli/_overview_rendering.py .../test_overview_deemed_served_notices.py
    All checks passed!

## Notes

The Catalan string shipped briefly as "de lAEAT": it was set through a shell
whose quoting concatenated the escaped apostrophe away, and the catalogue gates
have no opinion on a real word being misspelled. Corrected in its own commit.
The lesson is narrow and worth keeping -- a locale value routed through a shell
can lose characters silently, so read the written catalogue back rather than
trusting the CLI's "updated" line.

This Step's production edits were swept into peer commits by another agent's
bare commit while the work was in progress; the content in HEAD was verified to
be the authored content before the Step was closed.
