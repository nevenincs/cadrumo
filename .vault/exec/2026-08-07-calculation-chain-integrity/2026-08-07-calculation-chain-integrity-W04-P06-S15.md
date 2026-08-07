---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:68ee9baf93d7e680f627223c3ab509aa884c506efd7c6e1297202726427c0fde'
step_id: 'S15'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W04.P06.S15

## Outcome

**Landed, and the condition it was held on turned out to gate a different thing.**

The row reads "required only if the ruling makes the classifier wireable", and the earlier pass correctly recorded that the ruling had not been made. Re-testing the blocker rather than trusting it showed that the ruling does not gate this row at all.

## The mapping is already right

`R13_services_b2b_eu_inbound` resolves an EU inbound B2B services leg to `INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE`, and `_CLAVE_BY_KIND_AND_CATEGORY` files that under `ADQUISICION_SERVICIOS` — clave `I`, servicios adquiridos. Goods go to `A`. The wrong-clave defect the row names is not present.

It was fixed by the enum work rather than here: the categories the M349 surface needs came into existence, and `_source_resolver`'s own docstring records the moment its earlier reasoning went stale — it had argued that services "map to no `IvaCategory` member at all", which the same module now refutes.

So the row's condition is satisfied trivially rather than pending. There was nothing left to fix.

## What was actually missing

The gate. Two suites covered the halves, and neither covered the join:

- the classifier suite proves `R13` reaches the services category
- the resolver suite proves an invoice already carrying that category maps to `I`

Nothing runs the chain. A change re-pointing `R13` at the goods category leaves both green while every acquired service files against VIES as an adquisición de bienes, because the resolver test starts from a category rather than from the facts the classifier reads.

`test_m349_clave_follows_the_classifier.py` runs it end to end and asserts the two claves DIFFER, which is the assertion the defect would break.

## Proven rather than asserted

Flipping `R13` to the goods category in the production classifier reds the module with `assert 'A' == 'I'`. The mutation was reverted and the file confirmed clean against HEAD.

The module carries its own positive control too. If the goods and services categories were ever collapsed into one member, the clave comparison would compare a value with itself and pass while the defect was fully present, so a separate assertion fails on that collapse.

## Why this went unguarded

Modelo 303 combines the legs — official boxes 10/11 are titled *adquisiciones intracomunitarias de bienes y servicios* — so both categories select the same bindings there and either would settle correctly. The separation is only load-bearing at the Modelo 349 surface.

That is the general shape worth keeping: a distinction that is invisible on the larger, better-tested surface and decisive on the smaller one will be under-tested exactly where it matters.

## The ruling, restated

Still unmade, and still real — it governs whether the classifier is wired as an inference source for `operation_type`, which is a question about whether the app may infer a clave the operator did not state. Nothing here touches it. This Step's contribution stands whichever way it goes, because the clave table has to be correct either way.
