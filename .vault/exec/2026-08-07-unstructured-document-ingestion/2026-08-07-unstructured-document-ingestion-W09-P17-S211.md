---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d4308cddfb104e46363e22a7aa323b218876a81f44b6fd8fa07012486ed4d694'
step_id: 'S211'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Refuse an assimilation cycle at registry load

## Scope

- `src/cadrumo`

## Description

- Reproduce the defect independently before fixing, with an out-of-repo probe driving a synthetic two-row ring: both of the loader's chain checks pass on it, and the resolver then reaches `RecursionError`.
- Split the carve-out loader so the bundled file read and the judgement of what the file says are separate functions, making the validation callable against a table that does not exist on disk.
- Walk each assimilation chain at load and refuse one that revisits a code, raising the `IvaCatalogueError` every sibling malformation in that loader raises.
- Keep the self-pointer refusal beside it, so the length-one case still earns the diagnostic that names it directly rather than the general one.
- Rewrite the resolver comment that claimed a self-pointer check plus an unknown-parent check made unbounded recursion impossible; it now names the cycle walk as the reason and states why the other two are insufficient.

## Outcome

The code was fixed rather than the claim dropped. The claim was worth making true: the table admits a carve-out code as a resolvable parent by design, so the ring it opens is reachable by ordinary registry maintenance, and the failure mode was an unhandled crash at resolve time on the confirm path rather than a refusal at load. The five-line walk is cheaper than the alternative of narrowing what the table may point at, which would have removed a representable rule the article allows.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m unit
    674 passed in 28.16s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_carve_out_assimilation_cycle.py -n0 -q
    5 passed in 3.32s

    uv run --no-sync ruff check src/cadrumo/domain/iva/_establishment.py
    All checks passed!

    uv run --no-sync ty check src/cadrumo/domain/iva/_establishment.py
    All checks passed!

The refusal was proved to bite across two arms of the same synthetic ring rather than by opening a mutation window in a shared tree. Before the fix, an out-of-repo probe showed the loader's two chain checks both passing on that table and the resolver reaching `RecursionError`. After it, the identical table is refused at load with the cycle diagnostic, while the bundled table still resolves Monaco to France. The probe's rebinding is self-proving: the synthetic codes are absent from the shipped table, so an ineffective rebinding would have returned `None` rather than recursing.

The gate carries a terminating-chain control alongside the three refusals, because a check that refused every assimilation would satisfy all three and take the real table down with it, and a bundled-table case, because an anti-tautology proof over synthetic input cannot catch a check correct on synthetic input that refuses the only table that ships.

## Notes

Three failures in `domain/invoices` are the rate-window premise already rowed separately; they touch nothing here. basedpyright reports twenty diagnostics on the changed module, measured as identical against the committed content of the file before this change, so none is new.
