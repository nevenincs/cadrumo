---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` `W05.P69` summary

- Modified: `src/aeat/domain/modelos/_calculation_revision.py`
- Modified: `src/aeat/domain/modelos/__init__.py`
- Modified: `src/aeat/application/modelo/_calculation_actions.py`
- Modified: `src/aeat/application/modelo/_registry_helpers.py`
- Modified: `src/aeat/application/modelo/_revision_persistence.py`
- Modified: `src/aeat/application/modelo/_verification_actions.py`
- Modified: `src/aeat/application/modelo/tests/test_dormant_m369_oss_resolver_live.py`
- Created: `2026-05-26-cross-domain-continuity-W05-P69-S420.md`

## Description

S420 closes the fail-open Modelo 369 path found by the live OSS persona. Verification distinguishes no source, a positive observation that no M369 binding consumes, and a legitimate routed or zero-valued source. The first two are blocking and cannot export; the latter can be verified.

The correction preserves immutable revision history and legacy compatibility. Current M369 source-mesh calculations derive a sealed assessment marker; true state joins canonical revision identity and integrity rehash. Legacy drafts reconstruct source resolution from their encrypted invoice catalogue before verification. Direct legacy unresolved drafts fail before recalculation, while routed and zero legacy drafts can recalculate into new assessed revisions. Public calculation callers cannot supply provenance or issues: only the private bucket-mesh bridge carries resolver-derived evidence.

The focused M369/source-boundary suite passed 16 tests, scoped Ruff and diff checks passed, and two independent reviews approved the source-issue, legacy-fallback, marker-integrity, and trusted-mesh-boundary contracts.
