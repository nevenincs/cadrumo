---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:2ffc344ac139fccf99919fb51e3693e0b3fe97336f348841568942e181b475ab'
step_id: 'S53'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Refuse a missing --total-amount on the slim invoice add CLI verb instead of silently defaulting the total to zero, since the total drives whether a counterparty is declared at all under the RD 1065/2007 art. 31 Modelo 347 threshold

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`
- `src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py`
- `src/cadrumo/entrypoints/cli/tests/test_m349_business_invoice_export.py`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py`

## Description

- Change `--total-amount` on `invoice add` from `typer.Option("0", ...)` to an unset-sentinel `str | None` option, and refuse an unset value up front with an instructive message naming the accepted form (a decimal amount), never asserting what the figure means.
- Scaffold and populate the new `cli.app.ledger.invoice.total_amount_required` locale key in all four catalogues through `python -m cadrumo.locales scaffold`, never by hand-editing the YAML.
- Fix the two test files this repository-wide requirement change reddened: `test_business_invoice_verbs.py` (six `add` calls that previously relied on the zero default) and `test_m349_business_invoice_export.py` (an intracom-exempt fixture at 0% IVA, where `--total-amount` equal to `--taxable-base` is the truthful figure, not a derived one).
- Add a refusal test and an acceptance test for the new required flag.
- Open this Step under `P06` and record it as one of three sequenced pieces; the other two — defining what `total_amount` means, and only then a cross-field identity guard, which needs an IVA-treatment axis the record does not yet carry — are explicitly out of scope here.
- Same-pass repair (landed at the dispatcher's request, both breaks their own): update `test_ledger_add_gross_mismatch_surfaces_clean_refusal_not_pydantic_repr` to assert the current three-term `taxable_base + iva_amount + recargo_amount must equal the gross to the cent` message instead of the stale two-term fragment the recargo-identity commit (`9a63250408`) left behind. Add a sibling test, `test_ledger_add_gross_mismatch_above_substrate_hints_recargo_amount`, since no test anywhere asserted the `--recargo-amount` instructive hint text end to end through the CLI.

## Outcome

The production fix (the CLI signature change and the refusal) was already present at `HEAD` when this Step began, landed by a parallel dispatch of the same underlying task; `git diff` against the committed `_ledger_business_invoice_cli.py` was empty; nothing further was committed for that file. What this Step actually delivered was discovering and repairing the fallout that commit left behind: `test_business_invoice_verbs.py` and `test_m349_business_invoice_export.py` were both broken at `HEAD` (an omitted `--total-amount` now refuses, where it previously silently defaulted to zero), and neither had been swept. Confirmed by temporarily restoring the pre-session `HEAD` copy of `test_business_invoice_verbs.py` over the working copy: 6 of 9 tests failed with `Error: Invalid value: Option --total-amount is required...`; the fixed copy was restored (byte-identical, sha256 `513f154911faed87ca79442d1474173946800ab644c4a657a94e48867c099b49`) and reran green.

`invoice update`'s own `--total-amount` (already `str | None = typer.Option(None, ...)` for the partial-patch verb, where `None` means "leave unchanged") was inspected and needed no change.

The dispatcher subsequently confirmed both `test_business_invoice_verbs.py`/`test_m349_business_invoice_export.py` and `test_ledger_validation_paths.py::test_ledger_add_gross_mismatch_surfaces_clean_refusal_not_pydantic_repr` were their own breaks: the recargo-identity commit (`9a63250408`) reddened the latter, but its own verification ran only `domain/transactions` (unit lane) and never selected the CLI integration file, so the break shipped unnoticed. Repaired in this same pass: the assertion now targets the emitted three-term message, and a new sibling test drives the cash-above-substrate branch through the real CLI and asserts the `--recargo-amount` hint text appears (`recargo de equivalencia`, `--recargo-amount`) — a property nothing previously exercised end to end.

## Verification

```
uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py -n 0 -q --no-header -m integration
11 passed in 7.11s
```

```
uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_m349_business_invoice_export.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_link_flow.py src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py -n 0 -q --no-header -m integration
31 passed in 40.87s
```

Every test file across `src/cadrumo` invoking the slim `invoice add` CLI verb was enumerated by grep (`"ledger", "invoice", "add"` and the `_invoke_invoice(["add", ...])` indirection) and confirmed clean.

Mutation proof on the test-file fix: reverting `test_business_invoice_verbs.py` to its pre-session `HEAD` content reddens 6 of 9 tests; restoring the fixed content (verified byte-identical by sha256) turns them green again.

```
uv run --no-sync ruff format --check src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_m349_business_invoice_export.py
2 files already formatted
uv run --no-sync ruff check src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_m349_business_invoice_export.py
All checks passed!
```

A broader run was also taken as a dispatch-requested sanity check:

```
uv run --no-sync pytest src/cadrumo/entrypoints/cli src/cadrumo/application/ledger -n auto -q --no-header -m "unit or integration"
19 failed, 4429 passed in 770.38s
```

Of the 19 failures, 2 (`test_business_invoice_verbs.py`, `test_m349_business_invoice_export.py`) were this Step's own not-yet-fixed state at the time the run started and were fixed above. A third — `test_ledger_validation_paths.py::test_ledger_add_gross_mismatch_surfaces_clean_refusal_not_pydantic_repr` — asserted a stale two-term gross-invariant message string against the already-landed three-term identity; also fixed, in the same-pass repair below. The remaining 16 (config custody/recovery lifecycle, cold-start wizard registration, a Catalan language-matrix parametrisation, and an M130→M100 projection case) show no relationship to `--total-amount` or the invoice CLI on inspection of their failure text, and are consistent with concurrent uncommitted peer work elsewhere in this shared worktree.

Same-pass repair verification:

```
uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py -n 0 -q --no-header -m integration
26 passed in 44.72s
```

Mutation proof: with `_gross_mismatch_detail`'s cash-above-substrate branch (`domain/transactions/_models.py`) temporarily replaced with `return ""` (copy backed up first, sha256 `dba12aa34c2ec4eeba89ff7e9c81b014bd082e2bd2eaf2fd32014b85a6e37c81`), the new `test_ledger_add_gross_mismatch_above_substrate_hints_recargo_amount` reddens on the missing `--recargo-amount` assertion; the file was restored and verified byte-identical by sha256, then the suite reran green:

```
uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py -n 0 -q --no-header -m integration
26 passed in 14.31s
```

```
uv run --no-sync ruff format --check src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py    1 file already formatted
uv run --no-sync ruff check src/cadrumo/entrypoints/cli/tests/test_ledger_validation_paths.py              All checks passed!
```

## Notes

The dispatch brief's premise ("Change ONE thing") had already been satisfied by another agent before this session reached the file; `git log -1 -- src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py` shows commit `d23547fb10` (`fix(cli): stop defaulting the slim invoice total to zero (task #59)`), whose commit message records the same three-piece sequencing this Step's brief specifies and the same three rejected alternatives (no model-level identity guard, no base+iva derivation, no help text asserting a meaning for `total_amount`). No second attempt at that same edit was made; the value added here is the fallout sweep the landed commit missed, which two live tests prove was real. `cli.app.ledger.invoice.total_amount_required` is populated with genuine, non-placeholder translations in all four locale catalogues (confirmed by `python -m cadrumo.locales scaffold --check` reporting clean, and by reading distinct Catalan, Spanish and Hungarian strings rather than an English echo).

The gross-mismatch break traces to the same generic failure mode from a different owner: a commit (`9a63250408`, an unrelated recargo-identity campaign) that changed a message string consumed by an integration-marked CLI test, verified only against the unit-marked domain package the change lived in. Every break this Step touched shares the same root cause — a verification run that selected fewer tests than the change actually affected, and reported clean because the unselected file never ran rather than because it passed.
