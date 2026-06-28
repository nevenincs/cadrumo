---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S07'
related:
  - "[[2026-05-21-taxpayer-type-applicability-plan]]"
  - "[[2026-05-21-taxpayer-type-applicability-adr]]"
---

# `cli-workflow-redesign` `W02.S07`

The modelo-applicability derivation engine: each modelo's `applicable`
verdict is now derived from the three-axis taxpayer model rather than
assumed from an autónomo default. This record covers the W02 core —
`W02.S07` (the derivation engine), `W02.S09` (the explicit `incomplete`
verdict for an undeclared taxpayer model), and the applicability half
of `W02.S10` (the persona test matrix).

- Created: `src/aeat/application/overview/_applicability.py`
- Created: `src/aeat/application/overview/test_applicability.py`
- Modified: `src/aeat/application/overview/__init__.py`
- Modified: `src/aeat/application/overview/_explain.py`
- Modified: `src/aeat/application/overview/_agenda.py`
- Modified: `src/aeat/application/overview/_backlog.py`
- Modified: `src/aeat/application/overview/test_explain.py`
- Modified: `src/aeat/application/overview/test_calendar.py`
- Modified: `src/aeat/application/overview/test_agenda.py`
- Modified: `src/aeat/application/overview/test_backlog.py`
- Modified: `src/aeat/entrypoints/cli/_overview.py`
- Modified: `src/aeat/application/user_profile/_testing.py`
- Modified: `src/aeat/entrypoints/cli/test_audit_remediation.py`
- Modified: `src/aeat/entrypoints/cli/test_workflow_surface.py`

## Description

### W02.S07 — derivation engine

The new `_applicability` module introduces a registry-grounded
applicability rule structure. `ModeloApplicabilityRule` carries, per
modelo, the closed sets of entity types and IRPF income categories
that trigger the modelo, the operator-facing reason prose, and the
`legal_refs` grounding. `derive_modelo_applicability` evaluates a rule
against a `TaxpayerProfile` and yields a three-state
`ApplicabilityVerdict` — `APPLICABLE`, `NOT_APPLICABLE`, or
`INCOMPLETE`.

The autónomo-by-default assumption is removed from the overview
surfaces. `build_overview_calendar` now filters obligations whose
verdict is `NOT_APPLICABLE` — a pure landlord's calendar no longer
lists Modelo 130. `build_overview_explain` derives its `applicable`
flag and a new `verdict` field from the rule table; the deadline
engine's scheduling text is demoted to a `scheduling_rationale` field
and no longer drives the applicability decision.

The seed rule table covers only the W02.S10 persona set — Modelos 100,
130, 303, 200, 202 — each grounded:

- Modelo 100 — `legal_refs = (ley-35-2006,)`. LIRPF (BOE-A-2006-20764):
  a natural person is an IRPF contribuyente and files the Renta; a
  legal entity does not.
- Modelo 130 — `legal_refs = (ley-35-2006, boe-a-2007-6032)`. LIRPF
  Arts. 27-32 and Orden EHA/672/2007: triggered only by the
  `actividad_economica` income category. A landlord, salaried-only
  taxpayer, or pensioner is excluded.
- Modelo 303 — `legal_refs = (ley-37-1992,)`. LIVA: triggered by an
  actividad económica subject to IVA; the seed gates on the
  `actividad_economica` category.
- Modelo 200 — `legal_refs = (ley-27-2014,)`. LIS Art. 124
  (BOE-A-2014-12328): applies to every legal-entity IS contribuyente,
  never to a natural person.
- Modelo 202 — `legal_refs = (ley-27-2014, boe-a-2017-2778)`. LIS
  Art. 40 and Orden HFP/227/2017: the IS pago fraccionado, legal
  entities only.

A modelo without a seed rule yields `INCOMPLETE`; the
`_W03_COVERAGE_MARKER` constant records that full per-entity /
per-regime coverage of every modelo is Wave W03 (W03.S11). No legal
behaviour was invented — every rule maps to a source transcribed in
the research document.

### W02.S09 — the explicit `incomplete` verdict

`taxpayer_model_is_declared` returns `False` when `entity_type` is
unset, or when a natural person has declared no IRPF income category.
When the taxpayer model is undeclared, `build_overview_calendar`
returns an empty calendar with `taxpayer_model_declared = False` and a
localised `incomplete_reason`; `build_overview_agenda` and
`build_overview_backlog` propagate the same. `build_overview_explain`
yields an `INCOMPLETE` verdict with the "declare your taxpayer type
first" rationale. The CLI `calendar` / `agenda` / `backlog` verbs
refuse with that guidance instead of computing the autónomo schedule.
The engine never reports a confident wrong obligation.

### W02.S10 — applicability-half persona tests

`test_applicability.py` proves the derived verdict for every persona:
a landlord gets Modelo 100 not 130; salaried-only and pensioner get
no quarterly modelos; the autónomo is unchanged (130 / 303 apply); a
sociedad limitada gets 200 / 202 not 100 / 130; an undeclared profile
gets `incomplete` for every modelo. `test_calendar.py` adds the same
proof at the calendar surface. Expected modelo sets are taken from the
research document, not hand-invented.

The `register_minimal_profile` test helper now declares a minimal
autónomo taxpayer model so existing fixtures produce a computable
calendar; tests needing a different taxpayer shape pass overrides. Two
CLI tests (`test_audit_remediation`, `test_workflow_surface`) declare
the taxpayer model via `config profile edit` because they asserted the
old autónomo-default behaviour.

## Tests

`uv run --no-sync pytest src/aeat/application/overview/` — 76 passed.
`uv run --no-sync pytest src/aeat/domain/deadlines/` — green.
CLI overview verb suites plus `test_audit_remediation` and
`test_workflow_surface` — green. `ruff` and `ty` clean on every
changed file. No mocks, skips, xfail, or tautological assertions; the
deadline engine, registry, and CLI run for real.

W03 follow-up: the seed rule table covers only the W02.S10 persona
modelos. Full per-entity / per-regime applicability for every modelo,
the missing Modelo 100 / 303 / 347 deadline windows (round-3 finding
R1), and the corporate / SII rule expansion remain Wave W03.
