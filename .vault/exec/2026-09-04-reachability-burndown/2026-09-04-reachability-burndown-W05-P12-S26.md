---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:009339543aacba8f40d2d5a32686e8ee583c354cc93a41db9daee9556a0243fb'
step_id: 'S26'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Classify with their owners the shipped modules that block the ratchet and fit no available disposition, since IntentionalReachabilityKind admits only design_time_authority and the allowed list is shrink-only

## Scope

- `dev/quality/unreachable_module_ratchet.toml`

## Changes

- `M` `dev/quality/unreachable_module_ratchet.py`
- `verify:` `uv run --no-sync python -m dev.quality.unreachable_module_ratchet` -> `fail, three modules unresolved by design of this step`
- `verify:` `uv run --no-sync ruff check dev/quality` -> `pass`

## Notes

Classification was attempted against the governing taxonomy and is recorded here
rather than in the ratchet, because none of the three earns an entry.

`cadrumo.application.ledger.import_preparation` is capability that should be
live. Its TUI caller was retired on 2026-09-05, but the ledger capability
contract in `dev/quality/clitui_ledger_capability_matrix.py` still names
`import_preparation:prepare_ledger_import_command` as required, and only its own
test imports it. The remedy for the class is wiring, not an intentional entry,
and the wiring belongs to the surface retirement in flight.

`cadrumo.domain.contabilidad` and `cadrumo.domain.is_compensation` are candidate
deliberately-staged capability: complete domain packages with tests and no
production importer. Staging must be evidenced by an accepted decision recording
the dependency being waited on, and no accepted decision names either package.
Classification is evidenced, not asserted, so the class cannot be recorded and
they stay visible.

The narrowness of the intentional taxonomy is NOT what blocks these. The kind
enum admits one value, design-time authority, while the governing taxonomy names
eight classes; but each of these three falls in a class whose remedy is wiring or
an owner's withdrawal decision, so no additional kind would let them pass, and
none was added.

One defect was found and fixed. The gate's own failure text offered two remedies
only, relocation or deletion, and directed the reader to delete capability that
lost its caller. Following it for `import_preparation` would have deleted a
module a live capability contract requires, breaking that contract. The text now
names re-wiring and owner withdrawal, and says to check what still DECLARES a
module before deleting it.

No threshold, exclusion, baseline, skip or allowlist was changed, and the
`allowed` list was not written.
