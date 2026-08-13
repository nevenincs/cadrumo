---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:a5ce0366da9f313a06fc1a966527db1e5eeb8c6d07d9e4f7a4b51a6ca2fab9dd'
step_id: 'S37'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# retype `short_work_unit_id` and `short_calculation_revision_id` onto the existing `core.Hex16Str` primitive rather than the full-length aliases

## Scope

- `src/cadrumo/application/workflow/_resume.py`
- `src/cadrumo/application/modelo/_selectors.py`

## Description

- Semantic-searched the codebase and the vault for this row's own prior
  investigation before writing anything, per the mandatory discovery
  sequence, and found the row's premise already measured and refuted: the
  S35 adjudication reference (2026-08-10) classifies these exact sites as
  Class D — "NOT this taxonomy, must not be retyped" — with a concrete
  reason: they are a **12-character** abbreviation, not 16.
- Re-verified that measurement independently at HEAD rather than trusting
  the reference blindly: `rg` for every `short_work_unit_id` /
  `short_calculation_revision_id` / `short_current_calculation_revision_id`
  / `short_filed_calculation_revision_id` site across the tree (12 files,
  including the two the row names plus ten it does not:
  `entrypoints/cli/_modelo_payloads.py`, `_modelo_cli_support.py`,
  `_modelo_rendering.py`, `_modelo_work_revision_cli.py`,
  `_modelo_work_runs_cli.py`, `application/modelo/_work_addressing.py`,
  plus four test files). Every production truncation site slices
  `[-12:]` or calls `short_id()` (`entrypoints/cli/_modelo_rendering.py`),
  which itself is `value[-12:] if value else None`. Zero sites anywhere in
  the tree slice to 16 characters.
- Located the reason 12 is load-bearing rather than an arbitrary choice:
  `application/modelo/_selectors.py`'s private `_WorkUnitLookupId` selector
  parses operator-supplied lookup input against
  `pattern=r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$"` — a deliberate 12-or-64
  alternation backing the CLI's "paste either the full id or the short one
  you were shown" contract. `core.Hex16Str` requires exactly 16 characters
  (`min_length=16, max_length=16`); retyping either the field or the
  selector onto it refuses every real 12-character value the CLI currently
  accepts and displays.
- Confirmed no adjacent primitive already fits: grepped `core/` for any
  existing `min_length=12`/`max_length=12` constrained alias or an
  `IdentifierNamespace` short-id member. None exists. The row's own
  authorized action set — retype onto `core.Hex16Str` "rather than the
  full-length aliases" — names exactly the two options the evidence rules
  out, and does not authorize minting a new primitive (that would be a
  design decision for its own ADR amendment, not this execution row).

## Outcome

**ADJUDICATED, ZERO SITES RETYPED — correctly, not by omission.** The
row's literal instruction is superseded by evidence: `core.Hex16Str` does
not admit a 12-character value, and no other existing alias does either,
so every one of the 14 short-form sites (2 in the row's own named scope,
12 more found by the tree-wide sweep) stays a bare `str`, matching the
disposition the S35 adjudication reference already recorded for this exact
population. This mirrors `W05.P07.S36`'s `RegistryRevisionId` reversal in
shape — a faithfully-executed literal instruction would have shipped a
regression that refuses live CLI input — except here the correction comes
from re-verifying a reference document's measurement against fresh `rg`
evidence, not from a formal ADR amendment. No ADR amendment currently
records this correction; the ADR's Wave `W05` amendment text (2026-08-07)
still asserts "the existing `core._hex.Hex16Str`... is the correct alias,"
written before the width was actually measured. Flagged to the team lead
so a formal correcting amendment can be authored if the ADR record should
say so explicitly — this Step Record is not the place to author one.

`ruff check` / `ruff format --check` were not run because no file changed.
No test suite was run for the same reason; the four test files that assert
`[-12:]` (`test_resume.py`, `test_work_addressing.py`, `test_selectors.py`,
`test_modelo_work_ux.py`) remain correct as written and were not touched.

## Notes

No incidents. No files were modified — the correct action, once the
premise was re-verified, was to change nothing rather than force a retype
that would have shipped a live-input-refusing regression. Recorded fully
so a future reader does not re-litigate this row from the same stale ADR
sentence: the working evidence (selector pattern, truncation call sites)
is quoted above rather than only cited by location.
