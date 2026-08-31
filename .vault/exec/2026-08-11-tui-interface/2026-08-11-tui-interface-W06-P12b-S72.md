---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:96f12ab2df02f658635b68ae5623a1046258199e81cbdecd797c6df69c9e9c7e'
step_id: 'S72'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Define the memory-only ModeloEditSession and DraftRowId state machine with separate read and edit baselines, semantic dirty addresses, canonical typed staged values, ordered row intents, validation, and explicit abandon; `src/cadrumo/entrypoints/tui/modelo/edit/session.py`. BLOCKED ON A PREREQUISITE RELOCATION, MEASURED 2026-08-31, AND THIS ROW READS AS UNSTARTED WHEN IT IS NOT. The contract these five modules must consume has no public defining module: ModeloEditSubmissionV1, ModeloEditBaselineV1, ModeloScalarEditIntentV1, ModeloEditNewRowCorrelationV1 and 59 further exports live in application/modelo/_edit_models.py, with nine more in _edit_services.py, both underscore-private. Every current importer of either sits INSIDE application/modelo/, which is package-internal and legal; the TUI's existing workspace destinations by contrast reach their types through the PUBLIC application.modelo.workspace_models, and application.modelo itself is an inert namespace binding nothing. So a TUI editor module has NO legal route: the namespace yields nothing and the private module is the cross-package private import the architecture rule forbids at a hard-zero baseline. Found by writing the session module and hitting the wall; it was removed rather than left importing a private path. The unblocking step is a hard-move of both modules to public names with every consumer updated and the old paths deleted atomically -- 72 exported symbols, one indexed commit, owned by whoever holds that atomicity. DO NOT start S72 by importing the private module to get moving; that trades a blocked row for a hard-zero gate violation. ALSO MEASURED, so the build does not redeclare it: this row's DraftRowId already exists as ModeloEditNewRowCorrelationV1.client_correlation_id, the contract's own opaque correlation for a row not yet assigned persistence identity. The session holds that type; it does not mint a parallel identity.; `src/cadrumo/entrypoints/tui/modelo/edit/session.py`. CORRECTION 2026-08-31 TO THE 'BLOCKED ON A PREREQUISITE RELOCATION' BLOCK ABOVE: its central claim -- that the contract has no public defining module -- IS WRONG, and its proposed remediation is the opposite of what the code argues for. Disregard that block; it is left visible rather than rewritten. application/modelo/edit_contract.py IS the public face and is named as such in its own docstring. What it deliberately does NOT carry is the intent, address, admission, parsing, preflight, refusal and capability family, which stays in _edit_models by a STATED decision: publishing it 'would widen the contract to the shape of its implementation rather than the shape of its use', on the premise that 'no consumer outside the package addresses those'. It exports four symbols; of the eight this row's session module needs, only ModeloEditMutationFamily is among them. SO THE REAL QUESTION IS A DECISION, NOT A RELOCATION, and a hard-move of all 63 symbols is precisely the widening that docstring rejects. The C3 editor is the first consumer outside the package that WOULD address intents and submissions, so it falsifies the premise the private boundary rests on. Two shapes, and this row cannot pick between them alone: EITHER widen edit_contract deliberately to the subset a frontend genuinely stages -- submission, baseline, scalar intent and address, intent kind, new-row correlation, detail-row intent -- and record why each earned public status; OR keep the family private and give the editor a narrower application-owned facade that accepts operator-level calls and builds the intents inside the package, so the TUI never holds them. The second keeps the boundary the docstring defends; the first admits the frontend as a first-class consumer. ROOT CAUSE OF THE WRONG BLOCK: the search enumerated importers of _edit_models and read an empty result as 'no public route exists', without listing the package's own public modules -- edit_contract is the first name in that listing.; `src/cadrumo/entrypoints/tui/modelo/edit/session.py`. OPERATOR RULING 2026-08-31, and it resolves the boundary question above: NARROW FACADE IN THE APPLICATION LAYER. The intent, address and submission family STAYS private in _edit_models; edit_contract keeps its four symbols and is not widened. An application-owned facade accepts OPERATOR-LEVEL calls -- set a casilla from a lexeme, clear a declared value, open a draft row, abandon -- and builds the typed intents inside the package. The TUI holds no intent, address, baseline or submission type at all. CONSEQUENCE FOR THIS ROW'S OWN SUBJECT, which the ruling settles rather than leaves open: the session STORES staged intents, so under this boundary the session cannot live in entrypoints/tui at all -- it belongs in application/modelo behind the facade, and the TUI holds a handle plus operator-level calls. This row's scope therefore moves from 'define a TUI session' to 'define the application-owned session and its operator-level facade, and hold it from the TUI'. The memory-only, two-baseline, semantic-dirty-address, ordered-row-intent, explicit-abandon requirements are unchanged; only their home moves. DraftRowId remains ModeloEditNewRowCorrelationV1.client_correlation_id, now never crossing the package boundary at all.

## Scope

- `src/cadrumo/entrypoints/tui/modelo/edit/session.py`

## Changes

- `A` `src/cadrumo/application/modelo/edit_session.py`
- `A` `src/cadrumo/application/modelo/tests/test_edit_session.py`
- `verify:` `pytest test_edit_session.py` -> `7 passed`
- `verify:` `structural boundary probe over the session's public members` -> `no Edit Contract record reaches a frontend`
- `verify:` `ruff check` -> `All checks passed` on both files

## Notes

BUILT TO THE OPERATOR'S RULING: narrow facade in the application layer. The
intent, address and submission family stays private in `_edit_models`;
`edit_contract` keeps its four symbols and was NOT widened.

THE SCOPE PATH ON THIS ROW IS SUPERSEDED BY THAT RULING. The row names
`entrypoints/tui/modelo/edit/session.py`, but a session STORES staged intents,
so under this boundary it cannot live in the frontend at all. It lives in
`application/modelo/edit_session.py`; the TUI will hold a handle and call in
operator terms. Every requirement the row states is met -- memory-only, two
separate baselines, semantic dirty addresses, canonical typed staged values,
ordered row intents, validation, explicit abandon -- only their home moved.

WHAT A FRONTEND HOLDS: one opaque session, plus plain strings. Verified
structurally rather than by reading the source, so a later method returning a
baseline fails the gate instead of silently widening the boundary. The probe
carries its own non-vacuity assertion, because 'nothing forbidden found' and
'nothing inspected' are the same result otherwise.

FOUR DESIGN POINTS, each load-bearing rather than stylistic:
- `open_modelo_edit_session` admits AND opens in one call. Admission produces
  the baseline, so a caller that admitted separately would necessarily hold
  one. `_opened` is package-internal for the same reason.
- `refresh` takes operator coordinates, not a baseline, and re-admits
  internally. It moves only the READ baseline and returns whether the two
  still agree; advancing the edit baseline would silently re-target every
  staged edit, which is what the two-baseline split exists to prevent.
- Refusals are RETURNED, not raised. Being unable to edit a target is an
  ordinary answer on a read surface, and a frontend should not need an
  exception handler to render a disabled control. `message_key` is a
  localisation key, never prose and never the operator's raw lexeme -- the
  contract refuses to echo one, and a test asserts the outcome does not.
- Parsing delegates to `parse_modelo_edit_value`. A second parser beside the
  contract's would disagree the first time a locale changed.

`writable_scalars()` was added during the build because the tests exposed a
real gap: a frontend must know WHICH casillas are editable to render controls,
and reading `baseline.permitted_surface` would have handed it surface records.
It projects the same admitted fact into two plain strings per entry.

Rows are keyed by `(detail_row_kind, natural_key)` and NOT order-preserved,
following the intent kind's own documentation: no MOVE exists because every
row-producer sorts by a content key before assigning occurrence numbers, so
supply order cannot change the rendered fichero. Preserving it here would imply
a significance the fichero does not have.

CORRECTION 2026-08-31: THE "TWO SEPARATE BASELINES" CLAIM ABOVE IS STALE AND THE SESSION NOW HOLDS ONE.

What that record said was delivered as written. What it did not say is that the second baseline could not do the job it was kept for. Staleness was answered by comparing the two baseline RECORDS, and an admission carries its own identity and lifetime -- `baseline_id`, `issued_at`, `expires_at` -- so two admissions of an UNCHANGED tree are never equal. The comparison reported "stale" permanently, which is the exact failure a compare-and-swap exists to prevent: an operator warned of a conflict on every refresh learns to ignore the warning.

Found by a failing test in W06.P12b.S76, not by review, and the failure was in code this row had already been closed on.

Corrected design: staleness is asked of the contract's own `reconfirm_modelo_edit_baseline`, which compares the coordinate axes the guarded commit point judges -- catalogue revisions and the calculation revision id -- rather than the record. That is the same one-authority correction made earlier the same day to the work-target revision comparison, reintroduced here within hours.

The read baseline then had nothing left to do: written at open, never read. It was REMOVED rather than kept alive to preserve this record's wording. The requirement the split existed to serve is unchanged and still met -- a refresh must not silently re-target staged edits at whatever the tree looks like now -- and it is met directly, by never moving the one baseline a submission is judged against.

Recorded here rather than by rewriting the original notes, because a closed row asserting a shape the code no longer has is exactly the stale artefact this campaign keeps finding in other people's rows.
