---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-31'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# restore production baseline, drain test-only import debt, document the remainder

## Description

**Task A - restore the production baseline.** Re-ran `dev/import_hygiene_scan.py`
and found the production Family-1 count had regressed from the documented
5-site cycle-break baseline to 20 sites across `runtime.py`,
`_language_resolver.py`, `_repository.py`, and `_profile_readiness.py` (peer
churn since the last landing). Promoted `read_bucket_output_language_hint` /
`write_bucket_output_language_hint` / `clear_bucket_output_language_hint`
onto `adapters.persistence.storage.bucket.__all__` and
`resolve_profile_output_language_hint` onto `application.user_profile.__all__`
(both symbols were already public-named but not yet exported), then rewrote
all 15 consumer sites onto their owning package's public facade.

**Task B - drain the test-only tail.** Re-scanned and found 269 test-only
Family-1 sites (151 distinct owner/symbol pairs). Split public-named (104
pairs / 228 sites) from underscore-named (47 pairs / 50 sites). For the
23 public-named pairs absent from their owning facade, promoted the symbol
(20 pairs via facade `__all__` additions across
`adapters.inbound.financial.providers`, `adapters.outbound.aeat.auth`,
`adapters.persistence.storage.bucket/sql`, `application.evidence`,
`application.invoices`, `application.workflow`, `core.errors`, `core.i18n`,
`core.observability`, `domain.calculations.registry` (re-routed via the
sibling facade rather than the no-`__all__` namespace `domain.calculations`),
`domain.filing`, `domain.fincas`, `domain.iva_compensation`, `domain.modelos`,
`domain.transactions`, `entrypoints.mcp`; 3 pairs deliberately NOT promoted:
`SETUP_FLOW` re-routed to the documented canonical
`core.wizard_catalogue.get_setup_flow()` accessor instead, and
`DeadlineEngine` re-routed to the already-public `domain.deadlines` facade).
Ran `dev/import_centralization_codemod.py --tests-only --apply`, rewriting
211 import statements across 150 files onto their owning facade in one pass;
resolved the resulting duplicate-import merges with
`ruff check --select I001 --fix`.

**Task C - document the underscore/internal remainder.** Re-scanned after
Task B: 54 test-only sites / 48 owner-symbol pairs remained, all private
evaluators, repository factories, module-level caches, or constants with no
sensible public-facade promotion, plus `LocalFileSystemProvider` (public-named
but intentionally private behind the `StorageProvider` Protocol per its owning
package's documented boundary) and one structural-introspection reach into a
submodule's own `__all__`. Authored `dev/import_hygiene_test_debt.json` with a
named, individually-reasoned entry per site, and wired two new gate checks
into `src/aeat/tests/test_import_hygiene_gate.py` (count ratchet + named-set
equality, mirroring the production Family-1 shape but governed entirely
separately -- a production violation is never tolerated by the test-debt
file). Verified the gate's honesty by observing it correctly fail against an
undocumented new site a peer landed mid-session, before that site was
resolved by a mechanical facade rewrite (already public, just needed the
import rewired) and removed from the live violation set.

Ran `pytest --collect-only -q src/aeat` and
`pytest src/aeat/tests/test_import_hygiene_gate.py` clean after each task;
ran broad background suites over the most-touched areas
(`application/modelo`, `entrypoints/cli`, `core`, `domain/calculations/registry`,
adapters/persistence/storage, and others) and manually verified every failure
observed traced to a file with zero diff under this dispatch (pre-existing
peer-owned regressions: an M100 cross-period clean-state test, an IVA-wallet
reconciliation blocked-error, two CLI module-size budget overruns, a donativo
binding-selector registry gap, and a modelo-100 completeness-manifest
drift -- all in files untouched by this session).

## Outcome

Three commits landed on `chore/eliminate-shims`:

- `07d5fc6239` -- restores production Family-1 to exactly the 5 documented
  cycle-break sites (gate green).
- `5726f5ff52` -- drains test-only Family-1 from 269 to 54 sites via facade
  promotions plus the codemod sweep (171 files).
- `f225f9719f` -- documents the 54-site test-only remainder as a named,
  reasoned allowlist and wires the two new gate checks (3 files).

Final state: `dev/import_hygiene_scan.py` reports production == 5 (the
documented cycle-break baseline) and test-only == 54 (the fully documented
`dev/import_hygiene_test_debt.json` set). `pytest
src/aeat/tests/test_import_hygiene_gate.py` is green (9/9). `pytest
--collect-only -q src/aeat` collects cleanly (11722 tests, 2465 deselected).

## Notes

Skipped/deferred: `src/aeat/application/modelo/_reconcile.py` and its
sibling casilla-divergence test module were mid-edit peer WIP for most of
this session (a declaración-reconciliation feature, GitHub issue #438) and
were left untouched; they landed via a peer commit
(`7a0ed699b6`, `feat(reconcile): casilla-level divergence detection first
slice - M303 (#438)`) partway through this session, which also introduced
one new mechanically-fixable test-only site
(`test_reconcile_declaracion_casillas.py` reaching
`application.user_profile._testing.register_minimal_profile`); that site
was rewritten onto the already-promoted facade export and folded into the
Task C commit rather than left as test debt.

Twenty-two pre-existing `.vault/exec/2026-07-01-import-centralization/`
Step Records under Wave W05 (`S301`-`S363`) already exist from an earlier
pass and describe a per-owning-package rewrite shape that closely matches
Task B's scope, but their `## Description` / `## Outcome` prose reads as
templated placeholder text rather than verified authorship, and none of the
corresponding plan checkboxes are checked. Per the harness mandate for this
dispatch ("Do NOT run vault plan step check / feature index / vault check
all"), those existing per-step records and the plan's checkbox state were
left untouched rather than reconciled; this record captures the actually-
executed and verified work as a single consolidated exec record instead.
