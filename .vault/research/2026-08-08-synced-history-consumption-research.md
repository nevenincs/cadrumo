---
tags:
  - '#research'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7a86b8e61d3135556b6c897a5c62242c066b1ed76da1a6534eed85b93c4e075e'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# `synced-history-consumption` research: who consumes pulled AEAT filing history

## Question

A brand-new profile pulls its AEAT-stored filing history. Which of those pulled facts actually reach the calculation engine, and which are persisted and then never read? Specifically: when a work unit is derived from a pull rather than authored locally, how do its ledger-derived and previous-filing-derived values get filled, given that a freshly-onboarded profile has an EMPTY transaction ledger and no local app filings?

## Findings

**These findings were falsified by measurement and are retained as the campaign's starting premise, not as fact.** The plan's `P01.S01` census, derived from the loaded registry authority, established the corrected picture recorded in the census reference. Read that reference for the measured position. This section stays because the ADR and the plan's original row texts were written against it, and deleting it would leave those documents' reasoning unexplained.

### What was claimed, and what is actually true

The claim was that the pulled AEAT filing record has exactly one consumer in the calculation engine, the Modelo 303 IVA compensacion history, and that every other previous-filing carry resolves from a local app-filing store a freshly-onboarded profile has never written to.

That is true of one repository and false of the engine. `persist_filed_calculation_observation` writes **every** pulled modelo's active filed observation into the calculation observation repository with an official AEAT source kind, reached by all three capture routes. The M303 branch inside it is an ADDITIONAL write, not the only one. The general carries then read that same store with **no provenance filter**: the local-filing provenance constant that reads like a gate is a model field DEFAULT, not a predicate, and the source kind is reported rather than enforced. Both resolvers are enrolled on the live mesh.

Measured result: **72 of the 81 carry bindings have a pull-reachable source.** The nine that do not are all Sociedades, because neither Modelo 200 nor Modelo 202 declares the authenticated read surface on any revision.

### Why the wrong reading was reachable

The strict IVA-compensacion persistence helper genuinely raises for any modelo but 303, which makes the single-consumer reading look confirmed by a real refusal. Searching for consumers of the pulled record finds that repository and its two functions; nothing in that search surfaces the unfiltered general read, because the general read does not mention the pulled record at all. It reads observations by key and reports whatever provenance they carry.

The lesson worth keeping: a constant named for a provenance, used as a field default, is indistinguishable at a glance from a provenance filter. Establishing that something is NOT consumed requires reading the consumer, not enumerating the producers.

### The part that survived

An empty ledger produces a legally valid zero, and the failure mode this lane was opened to examine has no error, no refusal and no blank. That remains true and remains the reason nothing in this lane may use a blank or a refusal as its signal. What changed is the scope: the silent-zero risk is real for ledger-derived casillas on a pulled work unit, and it is NOT the general picture for previous-filing carries.

## What this does not establish

The scope of the harm is NOT measured. Naming the one wired channel does not establish how many binding sources, relations and cross-period carries would have had a pulled value available to them. That census is the first thing the plan must do, and it must be derived from the loaded snapshot rather than from a directory listing, because a binding's `source` field determines whether an absent value is a ledger silent-zero, a profile fact, or a legitimately deferred kind.

Whether any pulled value SHOULD feed a calculation input is a separate and unresolved question. A pulled filing is evidence of what was declared; it is not automatically an authorised input to a new computation, and the non-official-evidence rules already distinguish local app filings from AEAT filing evidence for exactly that reason. The decision record has to rule on which pulled facts are inputs, which are reconciliation targets only, and which must stay display-only.

The direction of error is also unexamined. The existing apparatus watches under-declaration; a synced history that silently fails to reach the engine can produce either direction, and an over-payment produces valid output, no refusal and no signal to the taxpayer.
