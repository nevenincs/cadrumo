---
tags:
  - '#audit'
  - '#casilla-reference-ambiguity-hardening'
date: '2026-06-24'
modified: '2026-06-24'
related:
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]'
---

# `casilla-reference-ambiguity-hardening` audit

## Scope

Audited the casilla-reference hardening path after implementation. The review covered the registry ambiguity validators in `_validate_revision_identity.py` and `_validate_revision_sections.py`, the validated-authority cache schema bump in `_authority.py`, the production static ratchet in `test_casilla_keying_convention.py`, typed casilla surfaces in calculation, filing, aggregation, verification, and observation paths, and the M303 refund e2e clock repair that prevented the workflow gate from masking refund-election behavior.

## Findings

No open findings.

Closed during verification: `test_modelo_303_refund_election_e2e.py` was pinned to filing year 2024 while the current M303 deadline-window registry begins at 2025. That made the real workflow gate abort with `NO_PENDING_OBLIGATION` before the refund-election logic ran. The test now uses filing year 2025, period-specific decision and verification clocks, and an in-window file clock derived from the real work-unit period.

## Recommendations

Keep the production static ratchet in `test_casilla_keying_convention.py` as a CI gate. Future casilla identity changes should update that ratchet in the same commit as the runtime change, not after a manual `rg` audit.

Do not collapse manual handbook references such as `MODELO:CASILLA` into registry `CasillaId`. They are source-citation filters, not engine identity keys.

## Codification candidates

No codification candidates. The relevant rule already exists in project form: production calculation, filing, verification, and export code must consume canonical `casilla.id` / `CasillaId`, while `number` remains documentary/export metadata.
