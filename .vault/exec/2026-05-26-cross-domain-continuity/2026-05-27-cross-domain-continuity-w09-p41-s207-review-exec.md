---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity S207 Code Review

## Verdict: REVISION REQUIRED

Two HIGH findings (unhandled exception in work_create + no wizard input path) and two MEDIUM quality findings.
The Art. 96.3 LIRPF detection rule, advisory surface, and tests are correct.
SAFETY-001 and WIZARD-001 must be resolved before merge.

---

## Gate Results

| Gate | Result | Notes |
|------|--------|-------|
| G1 no naked env reads | PASS | No os.environ/os.getenv in any modified file. |
| G2 typed pydantic at boundaries | PASS | TaxpayerProfile fields typed int-or-None and Decimal-or-None. OverviewStatusReport.filing_obligation_advisories is tuple[str, ...]. |
| G3 tr() for user messages | PASS | All four locale keys are tr()-routed at every call site. |
| G4 locale via scaffold + audit | PASS | es/en/ca have substantive translations. hu uses established passthrough delegation pattern. |
| G5 no shims/duplication | PARTIAL | See STYLE-001. Inline Decimal coercion reimplements _parse_decimal. resolve_filing_closes_on export is out of scope. |
| G6 no tautological tests | PASS | Four boundary tests cite Art. 96.3 Ley 35/2006 threshold. Anti-tautology structure is sound. |
---

## Critical Question Answers

**Q1 Detection rule correctness.**
evaluate_multiple_pagadores_obligation implements pagadores_count >= 2 AND secondary_income > 1500
with strict greater-than boundary. Both None inputs return False. Boundary tests confirm exactly
1500 does not trigger, 1500.01 does. Rule is correct per Art. 96.3 LIRPF.

**Q2 Advisory surface.**
overview status feeds raw_values through build_overview_status_report(raw_values=...) ->
build_filing_obligation_advisories -> OverviewStatusReport.filing_obligation_advisories ->
_filing_obligation_lines. work create --modelo 100 appends the advisory to lines before
_emit_envelope. Both surfaces are wired correctly.

**Q3 Wizard parity.**
irpf.pagadores_count and irpf.pagadores_secondary_income are added to TaxpayerProfile and
_profiles.py but have NO wizard catalogue questions and NO _SETUP_OPTION_INFOS entries.
The module-level parity assert at _commands.py:399 is silent because neither key is in
the catalogue. Fields are unreachable via aeat config setup / aeat config edit. See WIZARD-001.

**Q4 Verification finding.**
Not implemented. diagnostics.py has no pagadores check. Advisory fires at work create time
but does not block a draft. Out-of-scope follow-up.

**Q5 Locale parity.**
All four locales have the key. es/ca use unaccented caps (OBLIGACION, AVIS OBLIGACIO)
consistent with TTY-safe convention visible elsewhere in es.yml. hu uses passthrough
delegation consistent with existing hu entries.

**Q6 Anti-tautology.**
Confirmed. Single pagador 18000 EUR returns False. Three pagadores 1600 EUR returns True.
Test class docstring cites Art. 96.3 Ley 35/2006 as authority for the 1500 EUR threshold.

---

## Findings

### SAFETY-001 | HIGH | Unhandled ProfileNotFoundError in work_create pre-calificacion block

**Location:** src/aeat/entrypoints/cli/_modelo.py lines 1847-1851.

ProfileRepository().load() returns ProfileAggregate and never returns None. It raises
ProfileNotFoundError when the bucket is absent or tombstoned. The guard if _rec is not None
is permanently True (dead code) and provides no exception protection. If resolve_active_bucket_id()
returns a bucket id but the profile is tombstoned between the check and the load,
ProfileNotFoundError propagates unhandled through work_create as an uncaught exception at the CLI boundary.

The overview_status path avoids this correctly by using WorkflowState.active_profile_record()
which handles the not-found case internally and returns None.

Remediation: Guard the load with try/except ProfileNotFoundError and set _raw = None on the
except branch. Alternatively use WorkflowState.active_profile_record() if a state object
is available at that call site.

---

### WIZARD-001 | HIGH | No wizard input path for irpf.pagadores_count and irpf.pagadores_secondary_income

**Location:** src/aeat/application/wizard/_catalogue.py (absent) and src/aeat/application/wizard/_commands.py (absent).

The two new TaxpayerProfile fields and their _profiles.py mapping keys have no wizard catalogue
questions and no _SETUP_OPTION_INFOS entries. The parity assert at _commands.py:399 fires only
on catalogue-present/dict-absent gaps -- because neither key is in the catalogue, the assert is
silent. The advisory surface is inert for all profiles managed through the wizard.

Remediation: Add wizard catalogue questions for irpf.pagadores_count and
irpf.pagadores_secondary_income under the IRPF flow section in _catalogue.py, add matching
_SETUP_OPTION_INFOS entries in _commands.py, and add locale keys for the wizard prompts.
Required before the Art. 96.3 advisory is operationally reachable by any operator.

---

### STYLE-001 | MEDIUM | Inline Decimal coercion duplicates _parse_decimal and _parse_optional_int

**Location:** src/aeat/application/overview/__init__.py lines 128-147.

_to_decimal and _to_int helpers are defined inline in build_filing_obligation_advisories.
Equivalent helpers _parse_decimal and _parse_optional_int already exist in
src/aeat/domain/deadlines/_profiles.py (added in this same commit). The _to_decimal return
annotation is object | None instead of Decimal | None.

Remediation: Import and reuse _parse_decimal / _parse_optional_int from _profiles.py,
or promote to a shared utility. Fix the _to_decimal return annotation to Decimal | None.

---

### SCOPE-001 | MEDIUM | resolve_filing_closes_on export added out of scope

**Location:** src/aeat/domain/deadlines/__init__.py lines 80 and 120.

resolve_filing_closes_on is newly exported from the deadlines public API but is unrelated
to the pagadores feature. The only consumer imports it directly from the private _plazo module.
The new public export adds API surface without a consumer or stated purpose.

Remediation: Remove in a follow-up or document the intended consumer. Not a blocker.

---

## Safety Summary

- SAFETY-001: unhandled ProfileNotFoundError in work_create (HIGH, must fix before merge).
- evaluate_multiple_pagadores_obligation is a pure function; both None guards are correct.
- _check_representante_fiscal_required validator is well-scoped; ue_eee_status bool guard
  correctly excludes EU/EEA and IRPF-resident profiles via the country-is-not-None guard.
- profile_storage_session context manager RAII pattern is used correctly; no resource leak.
- No async or concurrency concerns; all paths are synchronous.

## Intent Completeness

Detection rule: complete. Advisory surface (overview status + work create): complete.
Tests: complete. Wizard input path: absent (WIZARD-001, HIGH). Verification finding:
absent (out of scope). Locale: complete for all 4 locales.
