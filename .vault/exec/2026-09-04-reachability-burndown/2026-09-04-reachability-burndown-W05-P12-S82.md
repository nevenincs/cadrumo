---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:1d2d83c5ede6681fc351958a2cc960c746117a61341cec298c45265138ba03e4'
step_id: 'S82'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Record this campaign's own unpaid shrinkage in the symbol ratchet and extend the clean-path reporting fix to its sibling: eight of the ten failure lines were mine, six modules carrying fewer exact findings than recorded and three carrying none, which is the unrecorded-shrinkage direction the shrink-only baseline exists to catch and had been red on for several iterations. Lower the six and remove the three; leave the two peer-introduced regressions unabsorbed and named. Sweep every dev/quality entry point for the silence defect found in the module ratchet and fix the one real recurrence.

## Scope

- `dev/quality/unused_symbol_ratchet.toml`
- `dev/quality/docstring_reference_ratchet.py`
- `dev/quality/tests/test_docstring_reference_ratchet.py`

## Changes

- `M` `dev/quality/unused_symbol_ratchet.toml`
- `M` `dev/quality/docstring_reference_ratchet.py`
- `M` `dev/quality/tests/test_docstring_reference_ratchet.py`
- `verify:` `python -m dev.quality.unused_symbol_ratchet` -- all eight shrink
  lines gone; the two remaining are peer-introduced and deliberately unabsorbed
- `verify:` a clean `python -m dev.quality.docstring_reference_ratchet` now
  names four modules carrying five recorded dangling references, exit 0
- `verify:` `pytest dev/quality/tests/test_docstring_reference_ratchet.py`
  7 passed; `... test_docstring_reference_targets.py` 13 passed
- `verify:` `ruff check` and `ty check` clean

## Notes

The symbol ratchet had been red on MY debt. Six modules carried fewer exact
findings than recorded and three carried none, all of them modules this campaign
resolved -- `draft_review`, `calculation_actions`, `contribuyente.keys`,
`cli._common`, `cli._tty` among them. Paying a symbol down and not lowering the
entry is the unrecorded-shrinkage direction the shrink-only baseline exists to
catch, and I had been leaving it for several iterations while reporting the
module ratchet green beside it.

The two remaining regressions are not mine and are left named rather than
baselined: `recapture_ledger_filing_evidence`, from a peer's in-flight ledger
evidence recapture gate, and `non_filing_axis_parameters`, the standing
registry red. Resolving a peer's just-landed symbol would be absorbing their
work; the baseline's own instruction is to resolve rather than record, and
neither is mine to resolve.

The silence sweep across every `dev/quality` entry point found one real
recurrence and one false lead. `docstring_reference_ratchet` returned 0 without
writing while its baseline records four modules; it now names them.
`crud_contract_drift` also printed nothing, but it has no `main` at all -- it is
a library a test consumes, so an empty `python -m` run is the absence of an
entry point rather than a silent gate.
