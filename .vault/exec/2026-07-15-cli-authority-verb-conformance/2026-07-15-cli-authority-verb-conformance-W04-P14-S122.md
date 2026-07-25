---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S122'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove attach remains the sole evidence mutation, invoice link is atomic and invoice-only, and link rejects every removed evidence grammar

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`

## Description

Prove that `attach` remains the sole evidence mutation, that invoice `link` is atomic
and invoice-only, and that `link` rejects every removed evidence grammar.

## Outcome

`src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py` carries thirteen
integration cases covering the retained surface and the removals.

Invoice-only linkage and the removed grammar are pinned directly:
`test_link_requires_invoice_id` (`:39`) and
`test_link_rejects_removed_evidence_id_grammar` (`:46`). The instructive refusal
surfaces the ADR requires — rather than a bare "value invalid" — are covered by
`test_link_refuses_unknown_transaction_id` (`:55`),
`test_link_refuses_operator_invoice_add_id_instructively` (`:187`), and the two help
assertions `test_link_help_advertises_local_only` (`:65`) and
`test_link_help_names_catalogue_create_for_invoice_id` (`:76`), which prove the
operator is routed to the retained door instead of into a dead end.

Link atomicity is proven by its observable consequence rather than by inspection:
`test_check_reports_zero_link_inconsistencies_on_a_consistent_bucket` (`:243`) and
`test_check_reports_a_one_sided_invoice_link` (`:259`) establish that `check` can in
fact detect a half-applied, one-sided link, so the consistent-bucket case is a
meaningful pass and not a vacuous one.

The retained `check` surface is covered by `test_check_empty_catalogue_is_ready`
(`:86`), the period/year filter pair (`:120`, `:146`), the local-only help assertion
(`:155`), and the session refusal `test_check_refuses_foreign_bucket_id_without_unlocked_session`
(`:168`).

The module passed in the coordinator's W04 gate run
(`uv run --no-sync pytest <14 W04 files> -m "integration and not os_keychain"` →
`1 failed, 154 passed`), the single failure being the unrelated S112 control.

## Notes

The one-sided-link case at `:259` is what gives this module its anti-tautology
strength: without a test that can observe an inconsistent link, the zero-inconsistency
assertion would pass even if `check` reported nothing at all.

These are `integration`-marked modules; the repository default `addopts` is
`-m 'unit and not external_tool and not os_keychain'`, so a bare `pytest <path>`
collects zero tests and exits green.

`vaultspec-rag` is degraded (truncated code index reporting `degraded_reasons: []`);
all findings were confirmed with `rg` and direct file reads.
