---
tags:
  - '#research'
  - '#m100-dependent-modelo-applicability'
date: '2026-06-19'
modified: '2026-06-19'
related: []
---

# `m100-dependent-modelo-applicability` research: `Modelo 100 blocks on withholding-modelo deps the taxpayer never files (C3)`

Adversarial finding from the filing-campaign red-team (verified at HEAD). The original C3 testimonial ("Modelo 100 unreachable for a normal salary+rental taxpayer; verify raises ~33 blocking cross_period_dependency_unclean") is a GENUINE, still-unfixed defect with a modeling root cause. This document grounds the defect and the design options so it can be remediated correctly rather than with a risky heuristic.

## Findings

### The defect (confirmed at registry + clean-state level)

The M100 construct `renta-2024-dependent-modelos` declares UNCONDITIONAL cross-period dependencies (bindings + relations) on the withholding/instalment modelos `111`, `115`, `123`, `130`, `131`, `193` (`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0010-renta-2024-dependent-modelos.toml`, relations `0001-0006`). Each `relation` / `previous_filing` requirement is derived by `cross_period_dependency_requirements` and evaluated by `evaluate_cross_period_clean_state` (`src/aeat/application/calculations/_cross_period_clean_state.py`). For a normal employee (salary + rental) who never files these modelos, the upstream filings are absent, so each dep blocks with `MISSING_OBSERVATION` / `MISSING_CURRENT_FILING_RECORD` → BLOCKING `cross_period_dependency_unclean`, and M100 verify is unreachable.

There is NO not-applicable path. The first-filer pre-activity suppression (`partition_cross_period_requirements_by_activity_start`, ADR 2026-06-13-first-filer-attestation) only scopes out STRICTLY-pre-activity deps; for a same-year employee these withholding deps are in-activity, so they are not suppressed.

### The root cause (a modeling conflation)

The dependency direction is wrong for the payee case. The `111/115/123/193` retenciones a salaried/rental taxpayer SUFFERS are reported on the payer's withholding return and on the taxpayer's income certificate — they are an INCOME FACT for the taxpayer, not a return the taxpayer files. The same modelos, however, ARE filed by a taxpayer who WITHHOLDS (a payer: a business paying salaries/rent). The registry conflates these two:

- "retenciones I suffered" (income data → M100 retenciones casillas), and
- "retenciones I withheld and declared via 111/115/123/193" (a genuine cross-period filing dependency).

So the M100→111 dependency is correct for a payer and wrong for a payee. A naive suppression that scopes out the dep for everyone would break the payer case (silent under-declaration); keeping it blocks every payee (the current defect).

### Design options

1. **Profile-applicability suppression (bounded, heuristic).** Suppress a cross-period dependency on a source modelo that does not apply to the taxpayer, using the deadline engine's `applies_to(profile, modelo)` (the existing authority for which modelos a taxpayer files). A pure employee → `applies_to(111)` is False → the M100→111 dep is scoped out as not-applicable (analogous facet to `NoPriorObligationProvenance`). A withholding business → `applies_to(111)` True → the dep still blocks. Pro: reuses an existing grounded signal, mirrors the first-filer facet. Con: a taxpayer who is BOTH a payee and a payer still blocks on the (correct-for-the-payer) 111 dep while their suffered retenciones come from income data — the conflation is not fully resolved, only the pure-payee case.

2. **Registry remodeling (correct, larger).** Split the conflated concept: retenciones SUFFERED become income-sourced casilla inputs (no cross-period dependency); only the WITHHELD-and-filed case keeps the 111/115/123/193 cross-period dependency, gated by a profile predicate (`has_employees` / pays-rent-with-retencion / withholding-obligation). Needs grounding against the AEAT M100 dictionary for which casillas are payee-retenciones vs payer-declared.

### Recommendation

Option 1 as an interim unblock (it makes the common employee case reachable and is grounded in the deadline engine's applicability), paired with Option 2 as the correct durable fix once the payee-vs-payer casilla split is grounded against the AEAT dictionary. The change touches a safety-adjacent gate (`no-silent-under-declaration`): the suppression MUST be an explicit, auditable not-applicable facet (never a silent drop), and MUST NOT suppress a dependency on a modelo the taxpayer genuinely files. An ADR should ratify which signal (`applies_to`) and which facet shape before implementation, because a wrong suppression is a silent under-declaration.

### Why this was not patched in the red-team pass

The clean-state gate is safety-adjacent and `_verification_actions.py` carries active peer WIP. A heuristic suppression risks either re-blocking the payer case or silently dropping a real dependency; both are worse than a precise, grounded finding. The defect is therefore documented for an ADR-gated fix rather than a single-pass patch.
