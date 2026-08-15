---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:6f1d2cd0b6433430fa49d7abbd1ea4da4e4598a656afb582c4ef5b56cb1e8d7f'
step_id: 'S186'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---




# Have Sol Medium land the two enrolment consequences of striking the duplicate version literals, retiring the three detector-table entries whose literals no longer exist and binding the newly named hold-evidence constant into the durability inventory as regenerable, since the detector and the binding gate each now fail on the tidier state they themselves demanded

## Scope

- `src/cadrumo/core/tests/test_persisted_version_single_declaration.py and src/cadrumo/core/compatibility_lifecycle.py and src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`

## Description

- Confirm each of the three named `STANDING_LITERAL_VERSION_DECLARATIONS`
  entries against current source before touching anything.
- Retire the three confirmed-stale entries from the detector table.
- Read the closed rows arguing the hold-evidence durability class, then enrol
  `profile_custody_hold_evidence` as `REGENERABLE` in `PERSISTED_FORMATS` and
  bind `CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION` in
  `VERSIONED_FORMAT_IMPLEMENTATIONS`.
- Run the newly enrolled format through the wider enrolment-discovery gate
  (`src/cadrumo/tests/test_persisted_format_enrollment.py`), which surfaced a
  second, unassigned consequence the handover did not name: the derived
  evidence file has no `FILE` path definition of its own, so it needed a
  third entry in that gate's hand-listed discovery table.
- Bite-prove both the detector and the binding gate from a scratchpad script
  outside the repository.

## Outcome

**Both gates failed because the tree got tidier, exactly as flagged.** Each
was correctly reporting that its own bookkeeping was stale after the prior
Step (`S180`) fixed the sites the two gates exist to police.

**The three retirements, each verified against live source before deletion:**

- `RemoteMirrorNamespaceManifest.manifest_schema_version`
  (`src/cadrumo/adapters/outbound/storage/_records.py`): the field is now
  `manifest_schema_version: int = Field(ge=1)` — no `default=` keyword at
  all, so the AST scan's `_default_literal` sees nothing. Genuinely stale.
- `ProfileCustodyOwnerReceipt.schema_version`
  (`src/cadrumo/application/user_profile/_custody_transactions.py`): the
  field is now `schema_version: Literal[1]` with no assigned default —
  required, same shape. Genuinely stale.
- `ProfileCustodyHoldEvidence.schema_version`
  (`src/cadrumo/application/user_profile/_custody_hold_models.py`): the
  field is now `schema_version: Literal[1] = CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION`
  — the default is an `ast.Name` reference to a constant, not an
  `ast.Constant`, so `_authoring_literal` no longer matches it. Genuinely
  stale.

All three entries were deleted from `STANDING_LITERAL_VERSION_DECLARATIONS`
in `src/cadrumo/core/tests/test_persisted_version_single_declaration.py`.
Nothing else in the tree referenced any of the three tuple keys.

**The enrolment, argued rather than merely applied.** `profile_custody_hold_evidence`
is entered in `PERSISTED_FORMATS`
(`src/cadrumo/core/compatibility_lifecycle.py`) as `PersistedFormatClass.REGENERABLE`,
carrying the same argument the two closed rows already settled and that this
Step's handover restated rather than reopened: the shape clears the nested-
format boundary's independent-grammar half (its own `schema_version`,
distinct from any container's) and the durable-readback half in the loose
sense (its own bytes land on a per-owner file), but nothing in the tree ever
loads that file back through the typed model — `_ProfileCustodyHoldEvidenceOwner.refresh()`
in `src/cadrumo/application/user_profile/_custody_hold.py` unconditionally
recomputes the evidence from the two already-durable legal-hold and
filing-retention snapshots and overwrites the file on every call. That is
the participation-index shape: a derived, always-recomputed read-side
artefact for which delete-and-rebuild is the correct response to an
unreadable version, argued from loss rather than from proximity to its
`DURABLE` capsule neighbours. The matching binding,
`"profile_custody_hold_evidence": "CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION"`,
was added to `VERSIONED_FORMAT_IMPLEMENTATIONS` in
`src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`.

**A second consequence the handover did not name, found by running the
wider discovery gate rather than only the one it pointed at.** Enrolling the
new key in `PERSISTED_FORMATS` immediately reddened
`test_no_declaration_outlives_its_format` in
`src/cadrumo/tests/test_persisted_format_enrollment.py`: that gate discovers
the live persisted-format set independently, from the path registry plus
three hand-listed sources, and it read the new key as a declaration with
nothing behind it because the derived evidence file's location is joined at
its call site (`.../derived-evidence/<legal|filing>/<profile_id>.json` under
the `PROFILE_CUSTODY_HOLD_EVIDENCE` storage category) rather than declared
as a `FILE` path definition — the exact gap the closed `S130` row already
worked around for the two owner snapshots that live one level up in the same
tree. A third entry was added to that file's `_UNREGISTERED_FILE_FORMATS`
table, naming the same storage category and stating why the derived file
has no path definition of its own. This file is outside the ownership this
Step was handed (`src/cadrumo/tests/` rather than `src/cadrumo/core/tests/`),
but the regression was caused by this Step's own enrolment and no other
agent holds that specific test module, so it was absorbed here rather than
left standing red or reported as a handover.

**Bite proofs**, both run from a scratchpad script outside the repository,
importing the real production modules and mutating no tracked file:

- The detector's pure scan function still fires on a synthetic
  reintroduction of a literal default for `ProfileCustodyHoldEvidence.schema_version`
  (the exact class/field just retired), confirming the retirement removed
  only the stale table entry, not the detector's ability to catch that shape
  fresh. All three retired keys were also confirmed absent from the standing
  table.
- The binding gate's accounted-set logic still flags a synthetic
  never-enrolled constant as unbound, and separately, removing only the new
  `CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION` binding from the accounted set
  reproduces exactly the failure this Step fixed — proving the gate would
  have caught this Step's own change had the binding been omitted.

**Verification, all captured to disk and read back**: a combined run of the
detector (`test_persisted_version_single_declaration.py`), the binding gate
(`test_persisted_format_enrolment_binding.py`), both compatibility-lifecycle
gates (`test_compatibility_lifecycle.py`, `test_compatibility_lifecycle_gate.py`),
the wider enrolment-discovery gate (`test_persisted_format_enrollment.py`),
and the version-literal inventory (`test_persisted_version_literal_inventory.py`)
— `56 passed` with `-m "unit or integration" -n0`, zero failures.

## Notes

No mocks, stubs, skips, xfail, or tautological assertions were used anywhere
in this Step. The bite-proof script imports the real production
`version_authoring_sites`, `STANDING_LITERAL_VERSION_DECLARATIONS`,
`VERSIONED_FORMAT_IMPLEMENTATIONS` and `_declared_version_constants` and
exercises them against real and synthetic AST, never a mock.

The one deviation from the handover's literal file list
(`src/cadrumo/core/compatibility_lifecycle.py`,
`src/cadrumo/core/tests/test_persisted_version_single_declaration.py`,
`src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`) is the
fourth file touched, `src/cadrumo/tests/test_persisted_format_enrollment.py`,
made necessary by the enrolment itself rather than chosen. No other agent's
named ownership covers that file; it was not on the explicit "other agents
hold" list, and per the standing orchestration guidance a regression this
Step's own change caused is absorbed rather than reported as pre-existing.

This row is ready to be marked complete: both gates named in the handover
are green, the discovered third consequence is closed in the same change,
and every verification claim above was actually run and captured to
`s186-gates-final.log` and `s186-bite-proof.log` under the session
scratchpad.
