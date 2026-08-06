---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:369cc1e66d2c0a5f399d81892a409d80ca386bf3bcca0626d64e30eeaaa56164'
step_id: 'S348'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ANDREA-LOW period token notation inconsistency between ledger preflight (uses 2024Q1) and modelo work create (uses 1T)

## Scope

- `the system resolves internally but the operator needs to know which format is accepted where`
- `document or normalize`
- `src/aeat/entrypoints/cli/`

## Description

Verify-close. The period-token inconsistency this Step describes no longer exists at HEAD: the ledger `--period` surface was unified onto the exact AEAT token grammar the modelo surface uses, and the calendar-shape notation the Step calls `2024Q1` is now refused, not accepted.

- Confirm the ledger `--period` / `--year` composition resolves through `_canonical_period` in `src/aeat/entrypoints/cli/_common.py`, which accepts only the canonical AEAT modelo tokens (`0A` annual, `1T`-`4T` quarters, `01`-`12` months) validated through the registry period union, exactly as the modelo `--period` / `--year` surface does. A calendar shape (`2026Q1` / `2026-03` / `2026`) or a year-qualified hybrid (`2026-1T`) is refused with an instructive message naming the AEAT tokens and the `--year` argument.
- Confirm the ledger preflight verb help text in `src/aeat/entrypoints/cli/_ledger_read_cli.py` documents the accepted token set (`1T-4T (quarters), 0A (annual), 01-12 (months)`), with the year carried separately by `--year`.
- Confirm the dedicated grammar gate `test_ledger_period_grammar.py` pins the refusal, including a case asserting `ledger preflight --period 2026Q1 --year 2026` refuses and names the AEAT tokens.

## Outcome

No code change required. The single-format outcome the Step asks for was delivered by the ledger-filter-period work and is enforced by the `period-filter-single-boundary-authority` rule plus the `test_ledger_period_grammar.py` gate: ledger and modelo now read `--period 1T --year 2024` identically, and there is no `2024Q1` acceptance path anywhere on the live CLI surface. Verified against HEAD. The plan checkbox is deferred to the coordinated plan-reconciliation pass.

## Notes

The Step row predates the ledger-filter-period unification, which resolved the divergence it describes as an unrelated campaign's work. This is a stale-done verify-close, not new implementation.
