---
tags:
  - '#plan'
  - '#modelo-232-related-party-operations'
date: '2026-11-12'
tier: L1
related:
  - '[[2026-11-12-modelo-232-related-party-operations-adr]]'
modified: '2026-11-12'
body_schema: body-v2
body_hash: 'sha256:0093610c3bd8a28c534c37bee26a37c43e4060d68a83302ef9e9cd50e3a3261c'
---

# `modelo-232-related-party-operations` plan

Let a company state its related-party operations per ejercicio so the Modelo 232 verdict is decided from registry thresholds instead of staying undecided.

## Description

Approved 2026-11-12. Basis: the coordinator accepted the governing ADR on 2026-11-12 at 19:21 with conditions and ordered that "the record build follows after S32"; S32 is handed, so this plan sequences that authorized build.

Decision coverage: the governing ADR settles the record, the per-ejercicio none statement, the derived payer fact and its conditions (encrypted custody only and never logged; aggregation per related person for art. 2.1.a and per type and valuation method for 2.1.b and 2.3; art. 2.2 exclusions stated and shown; turnover with provenance, unknown turnover undecided; a withdrawable none; schema number in landing order). No other costly decision is involved. The thresholds already exist as dated cited parameters of the 232 2016-2017 revision, and the INCOMPLETE exclusion already gives the undeclared reason.

Design anchors from discovery: the retencion soportada absence attestation is the closest record (active and withdrawn states, per-ejercicio key, revision-guarded writes, state, list and withdraw operations end to end). Fact 0139's ledger-backed derivation is the closest payer fact; this plan adds a record-backed source kind beside it, read through the same filing-year evidence. A profile schema bump is taken only if the payer-fact token needs a profile path.

## Steps

- [ ] `S01` - Add the related-party operation record, the per-ejercicio none statement and the stated turnover with its source, each active or withdrawn, in an encrypted profile namespace with revision-guarded writes; `src/cadrumo/domain/renta, src/cadrumo/application/aggregation, src/cadrumo/adapters/persistence/profile, src/cadrumo/adapters/persistence/storage`.
- [ ] `S02` - Derive the Modelo 232 payer fact from the ejercicio's records under the pinned revision's parameters, aggregating per related person and per type and valuation method, keeping art. 2.2 exclusions shown and unknown turnover undecided, and require it in the 232 rule; `src/cadrumo/domain/calculations/registry/applicability_payer_facts.py, src/cadrumo/application/overview/applicability_evidence.py, src/cadrumo/_data/registry/aeat/facts/0139-modelo-payer-applicability-facts.toml, src/cadrumo/_data/registry/aeat/modelos/232`.
- [ ] `S03` - Bump the profile schema additively in landing order with a forward idempotent tested migration if the payer-fact token needs a profile path; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/domain/user_profile/schema_migration.py`.
- [ ] `S04` - Register state, list and withdraw operations with CLI commands, refusal words and locale keys, following the retencion soportada absence operations; `src/cadrumo/application, src/cadrumo/entrypoints/cli, src/cadrumo/entrypoints/operation_composition*.py, src/cadrumo/locales`.
- [ ] `S05` - Open the records from the TUI profile area with served words and hand the window door to FRONTEND; `src/cadrumo/entrypoints/tui`.
- [ ] `S06` - Prove the decided verdict per supported year with a company persona stating operations above, below and none, and hand ACCEPTANCE the rows; `dev/fixtures/personas, src/cadrumo/application/overview/tests`.

## Parallelization

Sequential. S02 reads what S01 stores, S03 follows S02's decision on a profile path, S04 and S05 expose S01 and S02, and S06 proves the whole. Frontend window work is handed to FRONTEND after S04 lands.

## Verification

- For every supported year from the registry envelope, the 232 verdict is INCOMPLETE with no records, NOT_APPLICABLE with a stated none or operations below every threshold, and APPLICABLE when any art. 2 ground is met, all through the real registry parameters.
- Withdrawing a none returns the ejercicio to INCOMPLETE; an excluded operation is listed and left out of the totals; unknown turnover leaves the 2.3 ground undecided.
- Stored records round-trip encrypted; no record content reaches logs.
- Registry gates, bindings strict, year independence, import boundaries, ruff and ty pass; the operation contract manifest is regenerated at landing.
- ACCEPTANCE approves the persona rows, and the plan-close review passes.
