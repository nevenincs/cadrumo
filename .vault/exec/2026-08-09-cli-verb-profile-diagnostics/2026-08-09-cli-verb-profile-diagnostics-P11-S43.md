---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:22e835f18cc565ac7e5872862eddc1b4e115e4362f528a2d55ebf0e2be7d1ae4'
step_id: 'S43'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---

# Ground the three modelo-finding next_action messages that cite a nonexistent profile.* field path (m210_baseline_tipo_deferred, m210_convenio_rate_missing, representante_fiscal_required) at their real schema paths (taxpayer_type.country_of_fiscal_residence, taxpayer_type.representante_fiscal_nif) through the same schema-derived-label mechanism P08/P09/P10 use, verified by the same operator-label-not-raw-path assertion pattern those Steps use.

## Scope

- `src/cadrumo/locales/en.yml`
- `src/cadrumo/application/modelo (finding message sites)`
- `src/cadrumo/application/modelo/tests`

## Description

- Resolved each field's real schema location before editing: both live under the
  taxpayer-type section, and the `profile` section the messages named does not
  exist.
- Reused the existing selector renderer rather than adding a helper. A search for
  the canonical home found four modules already composing the same two
  primitives by hand, and a path-shaped and a selector-shaped renderer already
  published; these fields declare model selectors, so the selector one applies
  unchanged and no fifth copy was written.
- Threaded a requirement into the two M210 rate findings and the
  representante-fiscal predicate dispatch.
- Replaced the hard-coded paths with the requirements placeholder in all four
  catalogues through the locale CLI.
- Added a test asserting both halves, and proved it discriminates by replaying
  the pre-fix string through the same assertions.

## Outcome

All three messages now name their field the way the profile editor does, with
its legal grounding, and none carries the nonexistent path. The defect these
messages held was not only that they read as internal jargon: the path they
spelled resolves to nothing, so an operator following the instruction was sent
somewhere that does not exist while the sentence read as actionable.

The test pins the DEFECT as a literal and derives the expected LABEL from the
schema, so a label rename moves the test with it while the old path can never
come back silently.

**The code is committed-pending, not landed.** A repository lock has blocked
every commit for over an hour; the change is queued behind it with an own-only
patch for the two catalogue-and-service files that carry other agents' in-flight
work, so nothing of theirs is taken. This Step's box is checked against a
working tree, not against the branch head, and that distinction is recorded here
rather than left to be inferred.

## Verification

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_finding_next_action_field_grounding.py -q
    4 passed in 6.38s

    uv run --no-sync pytest src/cadrumo/application/modelo/tests -q -k "m210 or predicate or finding or verification"
    245 passed in 22.40s

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok

Discrimination proof: the pre-fix string was replayed through the new
assertions, and both halves failed on it - the label-present half and the
no-raw-path half - so neither passes vacuously.
