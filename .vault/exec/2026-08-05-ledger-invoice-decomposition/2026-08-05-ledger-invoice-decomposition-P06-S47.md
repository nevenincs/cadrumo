---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:614743253856db0dbafce540e3e7b21de58b96fda49c8d291c45594dccedd216'
step_id: 'S47'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-invoice-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S47 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Wire route_invoice_retenciones into the invoice lifecycle so a received invoice's retencion reaches Modelo 111, asserting the filed figure moves rather than that the projection returns a value and ## Scope

- `src/cadrumo/application/aggregation/_invoice_retencion.py`
- `src/cadrumo/application/invoices` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Wire route_invoice_retenciones into the invoice lifecycle so a received invoice's retencion reaches Modelo 111, asserting the filed figure moves rather than that the projection returns a value

## Scope

- `src/cadrumo/application/aggregation/_invoice_retencion.py`
- `src/cadrumo/application/invoices`

## Description

- Added `InvoiceRetencionRouteRequest` (invoice_id, scheme wire shape) and
  `merge_manual_and_routed_retencion_observations` (set-union with a loud
  refusal on a `(source_kind, source_object_id)` collision) to
  `application/aggregation/_invoice_retencion.py`, re-exported through the
  package facade.
- Wired `aeat app modelo aggregate` with a new `--received-invoice-retencion`
  option: for each declared `(invoice_id, scheme)` pair it resolves the
  invoice from the active bucket's catalogue, runs the existing
  `route_invoice_retenciones`, merges the result with any hand-typed
  `--retencion-observation` rows, and persists the union through the single
  existing `persist_retencion_observations` write path (no second writer).
- Excluded invoices (e.g. an issued invoice's retención, which is a credit
  not a retenedor liability) surface as warning `Notice`s carrying the
  routing module's own remediation text, never dropped silently.
- Added four locale keys (`aggregation.retenciones.errors.invoice_retencion_collision`,
  `cli.app.modelo.aggregate.received_invoice_retencion_help`,
  `cli.app.modelo.aggregate.invoice_retencion_wrong_modelo`,
  `cli.app.modelo.aggregate.invoice_retencion_excluded_notice`) across all
  four catalogues via `python -m cadrumo.locales set`.
- Added unit tests for the merge/collision function and a CLI-level
  integration test asserting the Modelo 111 calculate path reflects a
  CLI-routed invoice's retención, plus a companion test for the
  excluded-invoice notice path.

## Outcome

The taxpayer-as-retenedor liability on a received invoice now reaches the
per-perceptor store the committed Modelo 111 bindings read, through the one
sanctioned write path. The trigger point is the `modelo aggregate` CLI
(aggregation time), not invoice create/confirm: the retención scheme
(trabajo / actividades económicas / profesionales / premios) is a legal fact
about the perceptor's activity the invoice record does not carry and is
explicitly deferred to its own decision elsewhere, so it cannot be inferred
at invoice-lifecycle time without guessing. The operator (or the LLM operator
on their behalf) declares the scheme per invoice at aggregation time, exactly
as the existing `--retencion-observation` surface already requires for every
other retención source.

Collision handling: `persist_retencion_observations` is a set-replace write
for the whole `(modelo, filing_year, period)` window, so a hand-typed
observation for the SAME invoice the routing also covers would either
double-count the invoice in the per-perceptor rollup or silently drop
whichever side lost if picked arbitrarily. `merge_manual_and_routed_retencion_observations`
refuses loudly on that collision (matched by `source_kind` +
`source_object_id`) rather than picking a winner.

## Verification

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_invoice_retencion_routing.py -q --no-header -n 0
    20 passed in 12.10s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_invoice_retencion_aggregate_cli.py -q --no-header -n 0 -m integration
    2 passed in 11.97s

    uv run --no-sync pytest src/cadrumo/application/aggregation src/cadrumo/application/calculations -n 0 -q --no-header
    1 failed, 1233 passed, 7 deselected in 111.89s (0:01:51)
    (the one failure, test_no_new_snapshot_revision_id_injection_outside_named_exemptions
    against domain/calculations/registry/_handoffs.py:255, is pre-existing and
    unrelated: that file is untouched by this Step -- `git status --short` reports
    it clean -- and the finding is outside the retención-routing scope)

    uv run --no-sync pytest src/cadrumo/locales -q --no-header -n 0
    34 passed in 174.14s

Mutation proof: captured the SHA-256 of `_modelo_aggregate_cli.py` after landing
the fix (`ed4d21018...`), removed the routing block (kept only the CLI option
parsing) so the file fell back to the pre-fix behaviour, re-ran the new CLI
test file and both tests reddened (`assert 0 == 1` on the persisted-observation
count; the excluded-invoice notice test's `not_a_retenedor_liability` assertion
also failed) -- confirming they are not tautological. Restored the file byte
for byte (`cp` from a pre-mutation backup); the SHA-256 matched the pre-mutation
value exactly and `git diff` against HEAD showed only the intended additions.

## Notes

- Plan Step P03.S20 is checked and its action text reads "Route received-invoice
  retención into the existing per-perceptor store behind retenciones_aggregation,
  never a second parallel retención path". The routing PRIMITIVE
  (`route_invoice_retenciones`) existed and honoured the never-a-second-path
  constraint, but nothing called it in production -- this Step is the actual
  wiring. P03.S20 should be treated as having covered the primitive only, not
  the production callsite; the coordinator should decide whether to reopen it
  or record this Step as its completion.
- Two other agents made concurrent, unrelated edits to
  `application/aggregation/_invoice_retencion.py` and
  `application/aggregation/__init__.py` while this Step was in flight (a new
  `MISSING_COUNTERPARTY_TAX_ID` defect member and a new `_invoice_devengo`
  import respectively). Both are compatible with this Step's additions; this
  Step did not revert or alter either.
- INCIDENT: committing these two shared files used
  `git commit --only -- <pathspec>`, believing it would commit the precisely
  staged index built via a HEAD-anchored `git apply --cached` patch. It does
  not: a pathspec-qualified `git commit` reads the WORKING TREE content of the
  named paths, not the index, so the peer's still-uncommitted
  `_invoice_devengo` import landed alongside this Step's changes in the first
  commit -- and because `_invoice_devengo.py` itself was never committed, that
  import was dangling at HEAD (breaks on any fresh checkout). Caught by a
  post-commit collection run. Fixed immediately with a second, isolated commit
  that removes only the dangling import line and its `__all__` entry, leaving
  the peer's untracked `_invoice_devengo.py` and its test untouched on disk.
  The peer's `MISSING_COUNTERPARTY_TAX_ID` addition to `_invoice_retencion.py`
  is self-contained (no external dependency) and was left as committed --
  correct in substance, merely mis-attributed to this Step's commit instead of
  its own. Reported to the team lead so the owning agent can verify and land
  their module properly.
- `python -m dev.docs.apidocs scaffold --check` reports drift, but every
  missing/stale stub it names belongs to other agents' new modules
  (`_invoice_devengo`, `cadrumo.core.prose_elision`,
  `_iva_wallet_relation_targets`); this Step added no new module, so no stub
  regeneration was needed or performed here.
- `ty check` on the touched production file reports 4 pre-existing
  `invalid-argument-type` diagnostics (bare-string args to `AggregationValidationError`
  instead of a `Translatable`) at lines this Step did not touch; left as-is,
  out of this Step's scope.
