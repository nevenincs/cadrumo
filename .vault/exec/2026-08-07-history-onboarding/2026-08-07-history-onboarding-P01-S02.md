---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9b1a785c57f19238ee5c97e582b586815b47b5467d1ba1466d8a3eed91002de9'
step_id: 'S02'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add discover_filed_declaration_availability reading the modelo combobox's full option set then, per modelo, the ejercicio combobox's full option set, tagged provenance AEAT_REGISTER_OPTIONS and treated as scoping-unconfirmed, verified by a synthetic-fixture test asserting the returned report matches a hand-authored fixture option list exactly

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py`

## Description

- Extract `_open_register_form` so the search driver and the availability reader share ONE way into the register form.
- Extract `_open_combobox` from the selection helper so enumeration opens a combobox through the same locator and read-action assertion.
- Add `_combobox_option_texts`, `filed_register_modelo_options` and `filed_register_ejercicio_options`.
- Add `discover_filed_declaration_availability`, promoted on the sede package facade.
- Widen the register diagnostics context to accept an absent modelo/ejercicio pair.
- Add the synthetic combobox fixture with a `synthetic_generated` provenance sidecar, and the option-set tests.

## Outcome

The register's option lists are now readable rather than only clickable. The
navigation was EXTRACTED rather than copied: a second way in would carry its own
copy of the login-wall check, the alert-modal dismissal and the landing prefix
rule, and the landing-refusal enrollment gate only proves a rule is CALLED, never
that a duplicate stayed in step with the original.

The bundled REAL capture changed the design twice, and both changes were defects
the synthetic fixture alone would have shipped. It offers a modelo `174` whose
description is EMPTY, so the first pattern -- which required a character after
the dash -- silently dropped a modelo out of the very signal this read exists to
widen. And it renders BOTH combobox popups into one DOM snapshot, so an
enumeration assuming "only the open popup is present" would mix the two option
sets. The two shapes are therefore classified as DISJOINT, grounded in the
option-match values the shipped selection path already uses against the live
form; the mutation proofs below show the dash requirement, not the year anchor,
is what carries that disjointness.

The two refusal postures are deliberately opposite. An empty MODELO list is
refused, because the register always offers modelos, so emptiness means the form
did not render or AEAT changed shape -- and reporting it as "nothing offered"
would turn a shape change into a silently empty filing history. An empty
EJERCICIO list is returned as-is, because a modelo with nothing under it is a
legitimate answer and is one of the two readings this unconfirmed signal cannot
distinguish between.

A modelo whose ejercicio enumeration fails is skipped with a logged diagnostic
rather than failing the read: this signal is additive, so losing one modelo's
options narrows a bonus while refusing would deny the caller the widening
entirely.

## Verification

    uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_register_availability.py -q -n 0
    12 passed in 24.04s

Full owning-package suite, before the concurrent M303 registry edits landed:

    uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/sede/tests/ -q -n 0
    738 passed, 12 deselected in 134.14s (0:02:14)

Re-run after a peer migrated the parse call onto the package's shared lxml-backed
parser, since the option extraction and its exact-equality assertions were
authored against the stdlib parser and a backend change is a real behaviour axis:

    uv run --no-sync pytest <the four discovery test modules> -q -n 0
    57 passed in 56.94s

Mutation proofs, run from OUTSIDE the repo tree so nothing under source changed.
Each names the property, the control reading and the mutated reading:

    MUTATION modelo-regex-requires-description: control=True mutated=False -> PASS (test would red)
    MUTATION modelo-regex-dash-optional: control=True mutated=False -> PASS (test would red)
    MUTATION empty-modelo-refusal-bypassed: control=True mutated=False -> PASS (test would red)

The first version of the disjointness mutation unanchored the EJERCICIO pattern
and did NOT flip the result, because no modelo option in the real capture begins
with four digits. That was the instrument being wrong rather than the test being
insensitive, and it is recorded because it locates where the property actually
rests: on the modelo pattern's dash, which the corrected mutation does flip.

## Notes

No live AEAT session was opened and none is required. What these tests do NOT
cover is stated in the test module rather than papered over: the Playwright
clicks that open each combobox need an authenticated session, no synthetic
fixture can honestly stand in for them, and no live probe is authorised. Coverage
runs from a rendered snapshot through to the assembled report.

The two option-set parsers were deliberately NOT promoted to the package facade:
nothing outside the package consumes them, and the owning tests reach them
intra-package.

This Step's source was swept into HEAD by peer tree-wide commits `24f8fd9add`
and `dec1e9e61d` before it could be committed under its own message. The landed
content was verified byte-identical to what was authored here (a normalising
`git diff` was empty across every file in scope) and was NOT re-committed.
