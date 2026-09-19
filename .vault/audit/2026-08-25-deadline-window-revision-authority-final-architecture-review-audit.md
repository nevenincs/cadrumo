---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:2cfd5a4d57cd58947cf3c8e0e0a762c371a7d1a2fe031840d1605dbc327a4653'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
  - "[[2026-08-24-deadline-window-revision-authority-adr]]"
---

# `deadline-window-revision-authority` audit: `final architecture review`

## Scope

Review the completed implementation for canonical revision authority, source fidelity, cold and warm validation, consumer parity, transient reference-date handling, and absence of redeclared selectors, resolvers, parsers, cadence authorities, supported-year horizons, deadline catalogues, qualifier vocabularies, or downstream deduplication.

## Findings

### Final disposition | low | Approved with no remaining actionable finding

The first review found unsupported year-end citations, an inconsistent Modelo 303 Q4 endpoint, a cadence label that could contradict the canonical period vocabulary, and a stale comment. Those findings were corrected and re-reviewed.

The final reviewer approved HEAD after confirming:

- the exact AEAT February 1 evidence is bundled and hash-verified;
- Modelos 303 Q4 and 12M close consistently;
- Modelos 303, 322, and 353 use the grounded January 27 direct-debit cutoff;
- Modelo 349 combines its exact nominal presentation rule with Ley 39/2015 article 30.5;
- construct legal/source closure is complete;
- deadline cadence validation reuses `filing_schedule_period_kind_mismatches` and bites through `RegistryValidator`;
- completeness reuses the supported-filing-year catalogue, `select_revision`, and `schedule.is_periodic`;
- runtime “today” remains transient through explicit parameters or `today_madrid()`.

Vaultspec RAG discovery followed by exact-symbol sweeps found no competing authority path. Exact legal-date assertions remain source-fidelity tests; fleet architecture tests now derive the supported horizon from the catalogue and compare equivalent year-end rules relationally across modelos and cadences.

Verification evidence includes 123 focused four-model/invariant tests, 86 registry-engine-resolver tests, 91 corrected three-model tests, real CLI/workflow smoke coverage, a clean feature-scoped Ruff/format pass, and a clean Vaultspec feature check. The formal reviewer independently ran a 189-test focused suite before final approval.

## Recommendations

Keep exact official dates in source-grounded registry fixtures and their fidelity tests. Keep architecture behavior tests catalogue-driven and relational so advancing the supported horizon does not require a second hardcoded year list.
