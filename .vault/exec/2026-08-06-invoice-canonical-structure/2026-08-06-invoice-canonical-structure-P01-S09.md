---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:fce3ad87815accf038fd1b1fa7213a065bfbfd18390a850704bb9459b06665ba'
step_id: 'S09'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Remove the COLLECTIBLE_INVOICE default from InvoiceObservation.source_kind and make the direction axis required, after confirming every production construction site already passes it explicitly

## Scope

- `src/cadrumo/domain/calculations/registry/_invoice_bindings.py`

## Description

- Reopened the Step after an earlier pass left it deliberately unclosed on a refuted premise.
- Traced the counterpart supplier's filter order, which is what made the change safe.
- Made the direction axis required on the shared observation model.
- Stated the value explicitly at the one production site that omitted it, with its reason.
- Reconciled all 20 test construction sites in one coherent state, preserving today's behaviour.
- Added the refusal proof.

## Outcome

**Closed on a second pass, after the measurement that unblocked it.**

This Step was left OPEN earlier in the campaign, and the reasons were recorded then: its stated precondition — that every production construction site already passes the field — is false, and the one site that omits it, `_counterpart_to_invoice`, has no valid value to pass. A counterpart observation's source kind is drawn from a different taxonomy, one the invoice observation validates against the invoice family and would refuse. Requiring the field therefore looked as though it would convert a silent mis-stamp into a hard crash on the M347/M349 path.

The measurement that resolved it is the **filter order**. The counterpart supplier filters on the counterpart observation's OWN source kind *before* converting to the shared shape, so by the time a record reaches the adapter its family has already been decided, and the field the adapter sets is never compared against a binding source again. It is a dead value on that path. Stating it explicitly is therefore behaviour-preserving, and the crash the earlier pass feared cannot occur.

That also settles which of the three recorded options was right. Carrying the real direction is impossible — there is none to carry. Widening the invoice taxonomy would be a large blast radius for a value nobody reads. Stating it at the call site with its reason is the honest remaining option, and it is only honest because the value is unused; if it were read, a placeholder would be a lie rather than a shim.

**Why the field being required is worth the reconciliation.** It is not a label. The invoice-family resolver selects observations by matching this field against a binding's declared source, so a defaulted value decides which bindings a record feeds. A default on that axis means an omission silently declares an operation as issued — and the adapter's silent default did exactly that for every counterpart-derived record, including the received half.

The adapter now carries that reasoning in its own docstring, including the instruction that anything which later starts reading the field for a counterpart-derived record must change the function rather than trust the value.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/ -q --no-header
    3611 passed, 23 deselected, 2 warnings in 617.92s (0:10:17)

Targeted run over the five modules carrying the reconciled construction sites:

    uv run --no-sync pytest .../test_invoice_bindings.py .../test_modelo_349_operador_totals_parity.py .../test_modelo_349_registry_bindings.py .../test_modelo_347_registry_bindings.py .../test_counterpart_bindings.py -q --no-header
    59 passed in 13.58s

    uv run --no-sync ruff check <the five changed files>
    All checks passed!

The refusal proof constructs an observation with every other required field populated and omits only the direction axis, so the refusal is attributable to that axis rather than to an unrelated missing field.

## Notes

**All 20 test sites were reconciled to the collectible member, which preserves today's behaviour exactly** — that was the value the removed default supplied. This is deliberate: a ratchet Step should change what a caller must SAY, not what the system computes, so any behaviour change would have been an unrelated rider hidden inside a safety change.

The reconciliation landed as one coherent state rather than incrementally, per the enum-consumer rule: a partial sweep leaves the model requiring a field that some fixtures do not supply, which reds collection rather than failing a test and reads as unrelated breakage in a shared worktree.

**The two-pass shape is worth keeping visible.** The first pass was right to refuse: on the evidence then available, the change would have crashed a filing path. What changed was not the risk appetite but the evidence — one more measurement of where the filter runs. A Step left open with its blocker named is recoverable; the same Step forced through on the original reasoning would have shipped a crash.

**A second peer edit landed during this Step and is recorded so it is not attributed here.** A confirming re-run of the registry package, started after this Step's changes, failed with `NameError: name 'StringIO' is not defined` raised from the locale loader in `core/i18n/_render.py`. That file is dirty against `HEAD` — live peer work mid-refactor, with an import not yet added.

It is unrelated to this Step, which touches neither locale loading nor i18n, and it appeared only in the confirming run: the full registry package passed 3611 tests earlier in this same Step, before that edit existed. The Step's evidence therefore rests on that green full run plus the targeted runs over the five modules carrying the reconciled sites.

This is the second peer edit to transiently red a gate during this campaign. Neither was touched. Both are named with their exact failure signature so a later reader can tell peer churn apart from anything this campaign owns — the distinction the shared-worktree gate discipline exists to preserve.
