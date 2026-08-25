---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:34d1fe7954ab4e06e5e84b8704db2acca29fde148209b69c57ef5ccddb679dc6'
step_id: 'S268'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Repair defining-source API docstring cross-references and public facade targets for every stable main nitpicky warning left after generated stub reconciliation, without promoting private implementation ownership

## Scope

- `src/cadrumo/, docs/api/, docs/conf.py, and dev/docs/apidocs/`

## Description

- Inventoried the stable main nitpicky surface from an initial coherent 359 warnings through defining symbol, module, and warning category, using Vaultspec RAG for canonical facade ownership and exact source searches for every declaration and re-export.
- Repaired malformed defining-source RST, qualified real public references, and rendered implementation-only type aliases as literals only when no documented object target exists.
- Added generator-owned canonical Python-domain targets for intentional public aliases and the registry fingerprint function, including `CasillaId`, `ContentDigest`, `SubjectTaxId`, and `TaxIdIdentityToken`.
- Excluded imported generic origins at concrete consumer stubs and skipped only Pydantic runtime specializations whose metadata declares a non-null origin, leaving each real generic origin documented once without adding a type or implementation declaration.
- Disconnected Napoleon's redundant member selector only when every private/special inclusion switch is false, preventing probes of excluded Pydantic descriptors without suppressing any warning class, and completed `ErrorEnvelope` through its canonical public facade before autodoc.
- Hardened documentation project-metadata typing with runtime shape validation and corrected the complete API-manager test fixture typing surface.
- Regenerated all API stubs through the owning scaffolder and preserved concurrent source, registry, profile, locale, and TUI work without repo-wide repair.

## Outcome

The full English main documentation tree now builds under nitpicky warnings-as-errors with zero warnings. Public aliases have one canonical facade target, Pydantic generic specializations no longer redeclare their origins in the Python domain, excluded private descriptors are not probed, and no private implementation was promoted. The anti-redeclaration review found no wrapper, alias implementation, type redeclaration, global warning suppression, or duplicate public owner.

Verification:

- `uv run pytest -q -n 0 dev/docs/apidocs/tests/test_manager.py dev/docs/tests/test_api_stubs.py` - 14 passed in 26.54 seconds on the final changed test surface.
- `uv run python -m dev.docs.apidocs scaffold --check` - conformant, no drift.
- Scoped Ruff over all S268-owned Python paths - passed.
- Scoped ty over `docs/conf.py`, the API manager and tests, and changed product modules - passed.
- Focused generic-owner builds - zero duplicate-object warnings for `LedgerAggregationResultBase`, `PreconditionOutcomeInvariant`, and `OutputRootSchema`.
- Focused provisioning and error-envelope builds - zero excluded Pydantic descriptor warnings.
- First full main terminal proof - 1 passed in 802.58 seconds.
- Final full main terminal proof after typing hardening - 1 passed in 610.96 seconds.
- Mandatory formal re-review - APPROVE, no findings at any severity; the initial fixture-annotation finding was fixed across the claimed module and independently rechecked.

## Notes

The stable warning count evolved 359 to 276 to 275 to 115 to 87 to 70 and finally zero. One diagnostic generic-listener experiment expanded the inventory and was removed before closure; an explicit generic-autoclass experiment was likewise disproven and removed through the owning generator. S269 commit `96404aa521` repaired the independently derived sequence-runner relocation blocker before terminal S268 proof.

Concurrent shared-tree commits captured S268 code and generated artifacts while verification was running, notably `828da1c71d`, `f664f0dd8b`, `5cacb0c25c`, `4c6429e93e`, and `6189fd605f`; this closure commit therefore contains the attested S268 execution record and plan transition, with provenance stated here rather than falsely claiming a single isolated code commit. Commit `5fee1a4369f` captured the later-disproved explicit-generic intermediate state; its invalid pieces were removed by the subsequent generator-owned commits above before the green terminal proofs.
