---
tags:
  - '#research'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ed190159ddd0ab06052dcb9585cb6f3abf63b8898d7a6629cc10d67fa2605b88'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# `synced-history-consumption` research: who consumes pulled AEAT filing history

## Question

A brand-new profile pulls its AEAT-stored filing history. Which of those pulled facts actually reach the calculation engine, and which are persisted and then never read? Specifically: when a work unit is derived from a pull rather than authored locally, how do its ledger-derived and previous-filing-derived values get filled, given that a freshly-onboarded profile has an EMPTY transaction ledger and no local app filings?

## Findings

### The pulled filing record has exactly one consumer in the calculation engine

The AEAT-pulled filing observation is consumed by calculations through a single channel: the Modelo 303 IVA compensacion history, via `iva_compensation_state_from_filed_observation` and `iva_compensation_annual_summary_from_filed_observation` in `src/cadrumo/application/calculations/_iva_compensation_history.py`, declared as a port in `src/cadrumo/application/calculations/_ports.py`. Those two functions are the only calculation-layer readers of the pulled record.

### Every other previous-filing carry reads the LOCAL store

The general previous-filing prefill is `resolve_bindings_from_local_store` in `src/cadrumo/application/calculations/_binding_prefill.py`. Its gathered observations default to a local-filing provenance constant, and its merge path reconciles app-filing observations with secure IVA-history projections. It resolves from what this application persisted locally, not from what was pulled from AEAT.

Consequence: outside the IVA wallet, a synced history does not feed a previous-filing binding. Previous renta values, carried retenciones, prior pagos fraccionados and cross-modelo relation sources all resolve against a store that a freshly-onboarded profile has not written to.

### An empty ledger produces a legally valid zero, which is why this is silent

A first-period filer with an empty ledger files a valid zero Modelo 303, grounded in the art. 164.Uno.6.º LIVA obligation to present a declaration even with no activity. The behaviour is correct for a genuine no-activity filer. It is also indistinguishable, at every operator-facing surface, from a taxpayer whose history WAS synced and whose values were never wired in. There is no signal that separates the two.

This is the load-bearing observation. The gap does not present as an error, a refusal or a blank; it presents as a complete, plausible, legally-defensible zero.

## What this does not establish

The scope of the harm is NOT measured. Naming the one wired channel does not establish how many binding sources, relations and cross-period carries would have had a pulled value available to them. That census is the first thing the plan must do, and it must be derived from the loaded snapshot rather than from a directory listing, because a binding's `source` field determines whether an absent value is a ledger silent-zero, a profile fact, or a legitimately deferred kind.

Whether any pulled value SHOULD feed a calculation input is a separate and unresolved question. A pulled filing is evidence of what was declared; it is not automatically an authorised input to a new computation, and the non-official-evidence rules already distinguish local app filings from AEAT filing evidence for exactly that reason. The decision record has to rule on which pulled facts are inputs, which are reconciliation targets only, and which must stay display-only.

The direction of error is also unexamined. The existing apparatus watches under-declaration; a synced history that silently fails to reach the engine can produce either direction, and an over-payment produces valid output, no refusal and no signal to the taxpayer.
