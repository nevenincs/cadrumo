---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1da1621355355c0791122475d009cad93faa882a8b430edce266380c1fac6229'
step_id: 'S01'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add the FiledDeclarationAvailability and FiledDeclarationAvailabilityReport pydantic v2 models, verified by a strict roundtrip test

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`

## Description

- Add the closed `FiledHistoryDiscoverySignal` StrEnum to `src/cadrumo/core/_filed_history_discovery_signal.py` and promote it on the core facade.
- Add `FiledDeclarationAvailability` and `FiledDeclarationAvailabilityReport` to the sole capture schema module, and promote both on the sede package facade.
- Add the strict JSON roundtrip, provenance-pinning and refusal proofs.
- Regenerate the API stub for the new core module.

## Outcome

Two strict frozen records now carry what the declaraciones register OFFERS,
kept deliberately distinct from what the taxpayer actually filed. The report's
provenance is a PINNED literal rather than a caller-supplied field, so an
option set whose NIF-scoping is unconfirmed can never be relabelled as the
taxpayer-specific applicability signal — the one substitution that would let an
uninformative denominator be presented to an operator as a completeness claim.

The signal enum ships with both members from the start, and its docstring
carries the asymmetry rather than leaving it to the call sites: a zero-row
result under the profile signal is an anomaly, under the register-options
signal it is a plain negative. The enum lives in `core` because both the
adapter boundary and the application layer read it.

`ejercicios` accepts the same 2000-2099 range every other record in the schema
module already enforces, so a malformed option token is refused at the boundary
rather than travelling as an integer nobody bounded. An absent ejercicio is
documented as NOT evidence that nothing was filed for it.

## Verification

    uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/sede/tests/test_filed_declaration_availability_roundtrip.py -q -n 0
    7 passed in 0.15s

    uv run --no-sync ruff check <the five touched source files>
    All checks passed!

    uv run --no-sync ty check <the three new-or-changed typed modules>
    All checks passed!

Mutation proof, run from OUTSIDE the repo tree so nothing under source changed.
Positive control first, then four runtime field mutations; each flipped the
corresponding proof from raising to not raising, i.e. each proof would go red:

    CONTROL ok: all three guards refuse on the real model
    MUTATION discovered_at-defaulted: PASS (proof would red)
    MUTATION signal-widened: PASS (proof would red)
    MUTATION item-extra-ignored: PASS (proof would red)
    MUTATION ejercicio-range-removed: PASS (proof would red)

Tree-wide gate sweep over the core suite, the import-hygiene gate and the
docstring core-struct link gate:

    uv run --no-sync pytest src/cadrumo/core/tests/ src/cadrumo/tests/test_import_hygiene_gate.py src/cadrumo/tests/test_docstring_core_struct_links.py -q -n 0
    6 failed, 915 passed, 8 warnings in 330.60s (0:05:30)

Owner triage of those six: none names a module this Step touched. The combined
period-string gate names financial provider and tabular-dialect test fixtures;
the import-hygiene test-debt count regression names a TUI login-screen import
of a CLI config private module; the two docstring-link failures name the
foreign-asset redeclaration, classifier-inputs, M720 redeclaration-gate, renta
income-ledger and ledger evidence-batch payload modules. All are concurrent
peer surfaces with live uncommitted work; none was modified here and none is
patched to make this closeout pass.

## Notes
