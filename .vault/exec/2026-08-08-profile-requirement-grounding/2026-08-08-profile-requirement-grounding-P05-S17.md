---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:0f5412b6dcfd40dc12e28a89f0cadbab072f51592daf329db77e9905ce609c26'
step_id: 'S17'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# `profile-requirement-grounding` P05.S17

Add a parity gate failing with the field-level delta when the schema-required set and the `PROFILE_KEYS`-required set disagree, giving the deferred `ProfileKey` divergence a detector.

## Scope

- `src/cadrumo/application/user_profile/tests/test_profile_key_schema_required_parity.py`

## What landed

Commit `b08b6f9fa1` (1 file, +218). Test-only; no production code touched.

## The measurement it pins

Taken in-process against the real schema and the real compiled key space, not read off the earlier swarm report:

| | count |
|---|---|
| schema fields | 161 |
| schema `required` | 15 |
| `PROFILE_KEYS` entries | 75 |
| wizard `REQUIRED` | 1 (`identity.tax_id`) |
| schema-required, not wizard-required | **14** |
| wizard-required, not schema-required | 0 |
| wizard keys naming no schema path | 0 |

The divergence is **one-directional** — the schema is strictly stricter. That is a materially better position than the swarm's framing implied, and worth stating plainly: the wizard never demands a fact the schema considers optional, so no record the schema accepts is refused by the wizard.

All 14 diverging fields have principled causes. Twelve are columns of sections the schema marks `repeatable` and `effective_dated` (`attribution_entity_socios`, `attribution_received`, `usage_ratios`) — required *per row*, and the wizard key space is flat, with no row axis to express that on. The remaining two are present in the key space as `OPTIONAL` and raised to required by explicit conditionals elsewhere: `iva.regime` via `iva_regime_required(values)` (`_keys_validation.py:79`), and `activities.description` via the readiness gate's baseline (`_profile_readiness_gate.py:155,158`).

## Why it pins rather than closes

Reconciliation is the ADR's deferred work and needs the conditional-requirement grammar named in the 2026-08-09 amendment. Closing it here would mean either weakening the schema or forcing the wizard to demand row-scoped facts unconditionally — the second would refuse lawful filings from anyone with no socios, no attributions and no usage ratios. **The gate's job is to stop the divergence widening unobserved, not to remove it.**

## Causes are machine-checked, not prose

The part worth carrying forward. An allowlist whose reasons are only comments rots: the entries survive their cause and quietly pre-approve whatever later occupies the path. So each cause is verified against the thing it claims:

- `REPEATABLE_ROW` is checked against the schema's own `repeatable` flag. Make one of those sections non-repeatable and every field riding that excuse reds.
- `CONDITIONAL_RESCUE` is checked to name a field the wizard genuinely carries. A field absent from the key space entirely is a **larger** divergence and must not hide behind the milder cause.

Two further assertions guard properties that are clean today and should stay so: the divergence must remain one-directional, and no wizard key may name a path the schema does not declare.

## Verification

`pytest` — 7 passed; ruff check and format clean.

Six-way mutation proof, run from outside the repo by substituting the two fact-gathering helpers. Every assertion has its own killing mutation:

| mutation | result |
|---|---|
| new unpinned schema-required field | RED |
| pinned entry stops diverging | RED |
| repeatable-row cause made false | RED |
| rescue cause's path leaves the key space | RED |
| divergence becomes bidirectional | RED |
| wizard key names no schema field | RED |

Controls pass unmutated. This mattered more than usual: four of the six populations are **empty** today, and a gate over an empty population passes under every mutation while looking like coverage.

## Peer state observed, not actioned

`src/cadrumo/application/user_profile/_preflight.py` carries an uncommitted peer change removing the `modelo` parameter from `_requirement()` — which fixes the grounding tautology recorded in `2026-08-09-profile-requirement-grounding-per-operation-axis-and-silent-defaults-audit`, where a requirement row claimed the target modelo whether or not any binding consumed it. The implementation and all four of its call sites agree, but `tests/test_services.py` still passes `modelo=` and is **not** dirty, so two tests fail against the working tree with `TypeError: unexpected keyword argument 'modelo'`. HEAD is unaffected — the committed `_preflight.py` still accepts the parameter. Left for its author; reported to the coordinator.
