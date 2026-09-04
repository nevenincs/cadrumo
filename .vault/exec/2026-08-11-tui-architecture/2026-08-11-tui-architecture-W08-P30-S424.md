---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:54927b34f895adfb01498a9c4bea054ff637be61ab7efa7c7ac84cca74b744f0'
step_id: 'S424'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Sweep every projection and gate still shaped by the retired redaction assumption. DECIDED 2026-09-04. Find each model documented as safe, redacted, or 'without values', each screen docstring promising never to reconstruct a payload, and each test asserting that operator data is ABSENT from a rendered surface. Re-derive the models from the accepted visibility record and rewrite or delete those gates -- a gate asserting the retired policy will otherwise block the fix and read as a safety property while doing it. Gates asserting absence from a log, an exception, a cache, a temporary file or an off-host payload are UNAFFECTED and stay required; do not weaken them while removing the others.

## Scope

- `src/cadrumo/application/ and src/cadrumo/entrypoints/tui/`

## Changes

- `M` `src/cadrumo/application/ledger/workspace.py`
- `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `M` `src/cadrumo/application/modelo/declarations_calendar.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_slice3.py`
- `M` `src/cadrumo/application/aeat_sync/tests/test_workspace.py`
- `M` `src/cadrumo/application/search/tests/test_workbench.py`
- `verify:` `pytest -n0 -m '' application/aeat_sync/tests application/search/tests` -> `pass` (26 + 40)

## Notes

Step left OPEN: the census and declaration-result values remain blocked as
recorded below. What this pass added is the gate half of the sweep.

FIXED EARLIER IN THIS STEP. `LedgerInvoiceReconciliationRefV1` reported
`amount_match` and `counterparty_match` as bare booleans, hiding the two values
compared. A `True` asks the operator to confirm a link while withholding the
amounts that supposedly agree; a `False` reports a disagreement without saying
between what and what. The ref now carries invoice total, transaction amount
and both counterparties, and the screen prints them beside the verdict. Teeth
proven by removing the values from the rendered line.

BLOCKED, unchanged. Census values have no producer outside fixtures. Declaration
result amounts need a registry-declared result casilla, which does not exist --
only ad-hoc constants for two modelos -- and guessing on a filing-facing list is
worse than showing none.

GATES SWEPT, and two were passing without proving their subject.

The search document prohibition banned a field NAMED `search_terms`, and the
`content_terms` field this campaign added does that job under another name. The
gate stayed green while the policy it described had been retired underneath it.
It now names the sanctioned channel -- matchable text arrives through
`content_terms` and nothing else -- which survives a rename.

The AEAT byte scan asserted that eight protected strings are absent from the
projection. `AeatSyncWorkspaceProjectionV1` declares `contract_version`,
`zones` and six tuples of typed rows: no `bucket_id`, no `subject_key`, no
identity field at all. Those live on `AeatSyncWorkspaceFactV1`, an INPUT the
projector consumes and never emits, so NO value in that tuple could reach the
output and the scan could not fail. Four of the eight were worse still --
`Protected Name`, the evidence URL and `document prose` appeared nowhere in the
file except the tuple, so nothing ever introduced them.

Two corrections were needed inside this fix, both recorded because the second
invalidated the first. Supplying `certificate-private` through a census fact
was tried, to make one sentinel meaningful; it changes nothing, because facts
are not part of the output, and it was reverted. Injecting a `__repr__` leak
onto the fact also proved nothing -- pydantic builds `__repr__` from fields --
and that inconclusive result is what prompted reading the projection's own
field list, which settled it.

The protection is the TYPE. The test now says so and asserts it structurally:
every field a row exposes must be a closed enum, a typed address component, a
state or a bounded identifier, so there is nowhere for prose to be carried.
Teeth proven by adding a free-text field to a census row -- `note is free text
(<class 'str'>), so protected prose could be carried there and the removed
sentinels would need reinstating`. The byte scan is kept as belt-and-braces
with its limits stated, rather than deleted or left reading as the guard.

SWEEP COMPLETED over the remaining absence assertions in this campaign's
surfaces, applying the rule the byte scan produced: an absence check needs a
route for the value to arrive by.

The notification selection-key check is the one absence assertion here that
holds up, and it was verified rather than assumed. `notification-alpha` is
genuinely supplied through a fact's `private_identity`, the projected row
carries a `selection_key` DERIVED from it, and the test asserts both that the
raw value is absent from json, repr and pickle and that the key is not the
plain digest of it. That is a real route: a wrong derivation would leak.
Injecting one -- returning the raw identity as the key -- fails eleven tests.
Restored by copy; 26 passed.

The first attempt at that injection did not apply, because the anchor string
contained an escape the edit script mangled, and the suite went green on
unmodified source. That is the second time in this campaign a teeth check
passed for that reason, so the injection is now confirmed present in the file
before the suite is trusted -- a grep, not an assumption.

No further vacuous absence checks were found in the ledger, AEAT Sync, search
or workbench-generation surfaces. The remaining `not in` assertions in the tree
belong to the aggregation and auth areas, which are outside this campaign and
were not audited.
