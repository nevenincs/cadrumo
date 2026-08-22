---
tags:
  - '#audit'
  - '#issue-233-external-import'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:7a638a6a005d03adedf70bbbbb50c2f6a478daae96e97d00a6641ef8f43b1600'
related: []
---

# `issue-233-external-import` audit: `implementation review`

## Scope

Independently reviewed commit `3ed1cf1fe1f4d1ea88f905764cb6da1f5f199e82`
against the narrowed issue 233 acceptance: a real PDF, live-capture, or CSV
source must be able to enter a complete casilla source, resolve/reuse/create its
work unit, preserve exact lexical tokens while validating their numeric shadow
and key set, atomically persist a secure external baseline, and immediately
amend it. The review inspected the complete parent-to-commit diff, every
production caller, registry validation, work-unit and filing units of work,
justificante identity checks, all three closed evidence kinds, refusal paths,
legacy API compatibility, and focused/adjacent tests. No production file was
modified.

## Findings

### source-adapters-remain-disconnected | high | No real evidence source invokes the new composition service

`import_external_filing_source` is defined in
`_external_import_actions.py`, re-exported from the application package, and
called only by its new tests. No PDF justificante, live-capture, CSV-register,
or CLI production path constructs `ExternalFilingBaselineSource` or invokes the
service. Consequently an operator still has to manually extract and construct
the entire lexical map in Python; the three parametrized tests vary only the
evidence enum over the same synthetic hand-authored map. This adds a safe
composition primitive but does not close the latest narrowed end-to-end
acceptance for any actual source kind.

### source-completeness-is-self-attested | high | A partial casilla map is accepted as complete

The public source service derives both `decimal_values` and `lexical_values`
from the same `source.casilla_lexicals` mapping. `_validated_source_lexicals`
therefore compares two key sets with the same origin, while
`reject_unknown_import_casillas` rejects malformed/unknown ids but never
requires the selected revision's complete imported casilla set. Any nonempty
canonical subset passes. The dropped-key unit test calls the private helper
with independently constructed maps and cannot bite on this public-path defect;
the positive E2E fixture supplies only two hand-selected M130 casillas and does
not prove registry-derived completeness. The application boundary must compare
the observed source set to an independent authoritative expected set (with an
explicit policy for legitimately absent optional fields) before persistence.

### create-then-import-is-not-one-command-unit | high | A refused baseline can leave a durable work unit and creation event

When no target exists, `import_external_filing_source` calls
`create_work_unit`, which immediately commits the work-unit catalogue and
`MODELO_WORK_UNIT_CREATED` event. Only afterward does
`import_external_filing_evidence` validate modelo support, justificante
existence/identity, source key equivalence, duplicate revision state, and the
remaining baseline preconditions. Any later refusal or baseline co-commit
failure leaves the newly created work unit durable despite the source import
failing. The filing/revision/work-unit-pointer/import-event quartet is atomic,
but the newly exposed source-only command is not. Prevalidate every fallible
source/evidence condition before creation and compose creation plus baseline
writes into one secure repository transaction (or otherwise guarantee rollback
of the complete command).

### adjacent-import-tests-are-red | high | Existing import/amendment compatibility is not currently green

The focused new file passes (`5 passed`), but the proportionate adjacent lane
finished `28 failed, 40 passed`. Most failures occur before the action because
established fixtures use hyphenated justificante CSV values now rejected by the
domain pattern (for example
`test_import_filing_is_current_and_accepted` receives
`JUST-2026-303-Q1-OPERATOR1`); the lane also includes
`test_amend_refuses_no_op_overrides`, which expected
`CalculationRevisionStateError` but did not raise. These failures may predate
this four-file diff, but they prevent compatibility and immediate-amendment
acceptance from being claimed on this head. The branch needs a green,
non-weakened adjacent import/amendment gate or a separately grounded baseline
accounting for every failure before integration.

## Recommendations

Do not integrate or close issue 233 at this commit. Wire at least the authorized
real source path(s) to the shared service, enforce completeness from independent
registry/source authority, make create-plus-import atomic, and restore the
adjacent import/amendment gate. Preserve the useful exact-token behavior: the
new focused test proves outer whitespace survives unchanged while Decimal
values and all three evidence enums reach an immediately amendable baseline.
