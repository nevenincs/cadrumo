---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S16'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the modelos verification repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/modelos/_verification_repository.py`

## Description

- Verify at HEAD that the verification-report catalogue repository is already ports-compliant.
- Confirm the domain module `_verification_repository.py` holds only pure logic (`upsert_verification_report` and catalogue models) with zero `adapters` imports.
- Confirm the concrete `VerificationReportCatalogueRepository` lives under `adapters.persistence.profile.modelos_verification_reports`, importing domain types via the `domain.modelos` public facade and storage via the public `..storage` surface.
- Confirm the port `VerificationReportCatalogueRepositoryProtocol` is declared in `_protocols.py` and exported.
- Confirm zero production `domain.modelos -> adapters` edge remains and the verification-report roundtrip + anti-tautology suite passes.

## Outcome

Ports-compliant at HEAD. The concrete relocated in the properly tagged commit `5d1018a425` (`relocation:verification-report-repository ... W04.P09.S16`). No production `domain.modelos -> adapters` edge remains; only the sanctioned `test_verification_report_roundtrip.py -> adapters` test edges persist. Roundtrip `test_verification_report_roundtrip.py` green (anti-tautology classification-corruption case present). Independent read-only verification (agent, this session) confirmed with quoted evidence.

## Notes

A stale `.importlinter` comment (in the layered contract, authored by the S17 commit `8175c98e9a`) claimed the calculation/filing/verification sibling modules "still hold real lazy function-local adapters imports" — false at HEAD. Corrected in the W04.P10.S19+S20 closeout commit `be5ca85b22`.
