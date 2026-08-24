---
tags:
  - '#research'
  - '#product-ux-reconciliation'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:4aa813c022b9f22239a9cba3429baadc953f0394cf8b1fa45d1a70a7a14bb5c9'
related: []
---

# `product-ux-reconciliation` research: `declarations and output contracts`

The reported issues separate into one declaration-surface gap, seven verb-owned
payload breaches, and one shared-envelope cost. M111 can be asked without a
default through an explicit choice. Persisted list detail can move behind a
resource only after an identity-addressed read exists; ephemeral results cannot.
The action tree is part of the advertised validation contract and its repeated
cost is already measured separately from verb payload.

## Findings

### Ask M111 contextually with an explicit choice

`colegio_concertado` is a nullable profile fact and export refuses `None`, so an
unanswered state must survive (`src/cadrumo/core/setup_answers.py:245`,
`src/cadrumo/application/filing/_producer_snapshot.py:1446`). The generic
`CONFIRM` helper defaults to false, but the wizard models support nullable
defaults and an explicit `SELECT` pattern already preserves unanswered versus
false (`src/cadrumo/application/wizard/_catalogue.py:45`,
`src/cadrumo/application/wizard/_descendant_group.py:778`). The evidence favors
a contextual M111 readiness/review prompt that writes through the canonical
profile-fact writer, rather than asking every taxpayer during general setup.

### Add stable read-back before thinning persisted listings

The thinning authority emits a resource URI and reconstructs removed arrays by
re-running a declared read verb
(`src/cadrumo-harness/src/cadrumo_harness/mcp/_result_thinning.py:77`,
`src/cadrumo-harness/src/cadrumo_harness/mcp/_result_thinning.py:139`).
`modelo.work.runs` returns rows with `summary_details` but has no singular run
read (`src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py:152`,
`src/cadrumo/entrypoints/cli/_modelo_work_command_specs.py:326`). The safe order
is `modelo.work.run <run_id>`, resource resolution, then list thinning.

`modelo.work.revisions` already has singular revision and observation reads, so
it can be summarized against existing recovery paths. The accepted calendar
decision rejects the same remedy for `overview.calendar`: it is clock-derived,
not persisted, and re-execution can change its rows
(`.vault/adr/2026-08-05-ci-lane-deconflation-overview-calendar-payload-adr.md:35`).

### Keep the expanded action tree until a compatible reusable schema exists

The notice model types its action as the full action union and tests pin the
transitive definitions (`src/cadrumo/core/json_contract.py:235`,
`src/cadrumo/core/errors/tests/test_envelope.py:72`). Replacing it with an
unconstrained object would weaken validation, not just compression. The budget
already separates the shared definitions from each verb's payload and applies a
6500-character spine ceiling
(`src/cadrumo-harness/src/cadrumo_harness/mcp/tests/test_result_size_budget.py:62`,
`src/cadrumo-harness/src/cadrumo_harness/mcp/tests/test_result_size_budget.py:88`).
No supported reusable external output-schema reference was established here.

### Do not blanket-thin the seven residual verbs

The residual population is `modelo.work.runs`, `app.quickfile`,
`modelo.work.review`, `overview.calendar`, `modelo.work.wizard`,
`modelo.work.calculate`, and `modelo.work.revisions`
(`.vault/audit/2026-08-18-profile-password-custody-storage-custody-green-sweep-audit.md:8847`).
Each nested collection must be classified as persisted-and-addressable,
persistable, or ephemeral. Only the first class fits the current resource-link
mechanism. This pass establishes the run, revision, calculation-observation, and
calendar cases; the other payloads require per-verb reshape decisions.

## Sources

- `src/cadrumo/core/setup_answers.py:245`
- `src/cadrumo/application/filing/_producer_snapshot.py:1446`
- `src/cadrumo/application/wizard/_catalogue.py:45`
- `src/cadrumo/application/wizard/_descendant_group.py:778`
- `src/cadrumo-harness/src/cadrumo_harness/mcp/_result_thinning.py:77`
- `src/cadrumo-harness/src/cadrumo_harness/mcp/_result_thinning.py:139`
- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py:152`
- `src/cadrumo/entrypoints/cli/_modelo_work_command_specs.py:326`
- `.vault/adr/2026-08-05-ci-lane-deconflation-overview-calendar-payload-adr.md:35`
- `src/cadrumo/core/json_contract.py:235`
- `src/cadrumo/core/errors/tests/test_envelope.py:72`
- `src/cadrumo-harness/src/cadrumo_harness/mcp/tests/test_result_size_budget.py:62`
- `src/cadrumo-harness/src/cadrumo_harness/mcp/tests/test_result_size_budget.py:88`
- `.vault/audit/2026-08-18-profile-password-custody-storage-custody-green-sweep-audit.md:8847`
