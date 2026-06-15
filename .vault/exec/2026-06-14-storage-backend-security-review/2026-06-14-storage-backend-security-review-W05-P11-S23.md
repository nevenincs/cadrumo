---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S23'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Resolve the fincas domain hexagonal inversion by relocating the ORM-coupled repository or exposing a typed boundary facade and fix the stale docstring path

## Scope

- `src/aeat/domain/fincas/_repository.py`

## Description

- (Prior, peer `1afb8a4d1`) Fix the stale `storage._orm` docstring reference.
- Author `domain/fincas/_repository_ports.py`: five read-side `Protocol`s
  (`FincaReader`, `ArrendamientoReader`, `FincaRendimientoReader`,
  `FincaGastoReader`, `FincaAmortizacionLedgerReader`), interface-segregated to
  exactly the methods `_aggregates` calls.
- Relocate the five concrete ORM repositories from `domain/fincas/_repository.py`
  to the persistence adapter `adapters/persistence/profile/fincas.py` (alongside
  the sibling `assets`/`inventory` repos); fix the cross-package import dots.
- Rewrite `_aggregates.py` to annotate against the ports (word-boundary rename of
  23 annotation sites); domain no longer imports SQLAlchemy or `_orm`.
- Re-export the ports (not the repos) from `domain/fincas/__init__.py`.
- Relocate the repo-CRUD test and the SQL-boundary roundtrip/anti-tautology test
  to `adapters/persistence/profile/tests/`, re-marked `hex_persistence_adapter`;
  `test_aggregates` stays in domain and imports the concrete repos from the adapter.
- Regenerate the API stubs (`apidocs scaffold`): drop the `_repository` stub, add
  the `_repository_ports` and adapter `fincas` stubs, update parent toctrees.

## Outcome

STEP COMPLETE. The domain→adapter hexagonal inversion is resolved via the typed
boundary façade: `aeat.domain.fincas` carries zero SQLAlchemy / `_orm` coupling,
and the concrete ORM repositories live in the persistence adapter where that
coupling belongs. Dependency direction is now inverted correctly (adapter depends
on the domain port). Committed as
`refactor(fincas): resolve domain->adapter hexagonal inversion via reader ports [relocation:FincaRepository] (S23)`
plus a one-line docstring follow-up.

Security dimension was CLEARED during the assessment: `FincaRow.address` (the
taxpayer-identifying PII) is `EncryptedString`-at-rest by deliberate design; the
non-identifying Catastro valuation columns are plaintext `Numeric` by documented
choice. This was a STRUCTURE finding, not a security one.

Gates: ruff clean, `apidocs scaffold --check` clean, docstring core-struct gate
green, 207 fincas + profile-adapter tests pass, both `user_profile` lazy-boundary
gates + the CLI lazy-command-tree gate pass, `test_ephemeral_key_hygiene`
(SQL-backed-constructor scan) passes, collection clean over the touched trees.

## Notes

The earlier deferral was discharged in a fresh-context focused slice with the full
fincas + profile-adapter suite as the gate, exactly as the deferral plan prescribed.
A third fincas test (`test_roundtrip_anti_tautology`) surfaced during the test run
(it imported the repos from the domain package) and was relocated with the others.
A transient linter auto-fix upgraded one port docstring to a `:class:` role
post-commit; folded into the follow-up. No incidents; the relocation landed as a
single atomic rename-detected commit.
