---
tags:
  - '#adr'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - '[[2026-07-01-import-centralization-research]]'
---

# `import-centralization` adr: `centralized top-level exports as the sole cross-package import surface` | (**status:** `accepted`)

## Problem Statement
The `2026-07-01-import-centralization-research` scan found the 104-facade
boundary is bypassed by 2465 cross-package private imports (866
production / 1599 test, 250 files, 34 owning packages), 8 Family-2 shim hits
(mostly documented bridges), and 578 Family-3 multi-sourced symbols (101
hierarchical-rollup non-violations, ~10 genuine duplicates). Fixing production
requires 149 facade promotions (302 sites) before 400 simple consumer rewrites
(937 sites).

## Decision (the 9 rulings)
1. POLICY + OWNERSHIP: one canonical public top-level export per symbol;
   cross-package consumers import ONLY from the owning package top-level
   `__all__`; ownership of `A.B._C...` is `A.B`; intra-package private
   imports and a package building its own facade are fine. Generalizes
   `service-imports-via-top-level-reexports` project-wide.
2. PROMOTION MECHANISM: add symbol to owning `__all__`; default eager
   `from .module import Name`; use lazy `__getattr__` (PEP 562) ONLY when
   the owning package already uses it or eager import risks a
   cycle/cost. Do not retrofit the ~93 eager facades to lazy.
3. 20 UNDERSCORE-NAMED promotion candidates: no blanket `_foo`->`foo`+`__all__`.
   Per-symbol: (i) rename-to-public+promote if it is a genuinely-shared public
   primitive (e.g. `_parse_bool`, `_build_aad`, `_active_session`); (ii) expose
   a purpose-built narrower public API if reached by one caller for one
   purpose; (iii) treat the reach as a design defect to remove if neither
   fits. An underscore name used by >=2 unrelated production packages -> (i);
   by exactly one narrow caller -> (ii). Decide per-symbol in Wave-1 planning.
4. FAMILY 2 bridges: a single DOCUMENTED non-`__init__` public re-export module
   is an acceptable canonical source (keep the 6 documented bridges:
   `registry/applicability.py`, `deadlines/taxpayer_model.py`,
   `transactions/_ids.py`, `cli/_schemas.py`,
   `outbound/aeat/_playwright.py`, `workflow/_utils.py` [add a one-line
   docstring]); `locales/__main__.py` is an entry-point FALSE POSITIVE (exclude
   `__main__.py` from the shim classifier). The one genuine violation
   `application/aggregation/_withholding_observations_repository.py` (real
   282-line M190 percepciones impl) is an English-stem name: RENAME to
   `_percepciones_observations_repository.py` (NOT `_retencion_...` which
   already exists as the distinct M180/193 store), sweeping module+tests+
   consumers in one atomic `relocation:` commit.
5. FAMILY 3 (~10 genuine duplicates) = RETIRE (operator-decided 2026-07-01,
   strict single-source): for the `CalculationRevision` /
   `CalculationRevisionAmendmentKind` / `ExternalEvidenceKind` / `WorkUnit`
   group (`application.modelo` re-exporting `domain.modelos` symbols) AND the
   `link_transaction` / `suggest_reconciliations` / `verify_link_consistency`
   group (`application.invoices` re-exporting `domain.invoices` symbols):
   RETIRE the app-layer re-export. The domain package (`domain.modelos` /
   `domain.invoices`) is the SOLE canonical source. Remove those symbols from
   `application.modelo.__all__` / `application.invoices.__all__`, and repoint
   ALL consumers (including app-layer siblings) to import from the domain
   facade. This adds ~180 consumer-site rewrites folded into the
   consumer-rewrite wave. `save_envelope` = two unrelated same-name funcs, no
   consolidation (optional cosmetic rename deferred, out of scope).
   `DEFAULT_IVA_GENERAL_RATE_PCT` = benign single-origin, no action.
   `OutputLanguage` = drop the redundant `entrypoints.cli._config` `__all__`
   entry, `core.i18n` sole facade.
6. DYNAMIC IMPORTS in `core/setup_answers.py`: keep the deferred
   `importlib.import_module` cycle-break technique, but retarget its module
   strings to PUBLIC facades: `_m()` -> `aeat.domain.deadlines.taxpayer_model`,
   `_ccaa()` -> `aeat.domain.contribuyente` (drop `._ccaa`). These are
   ordinary Ruling-1 fixes, not exceptions.
7. TEST-ONLY (1599 sites): deferred to a dedicated LAST wave after production
   facades stabilize; batch by owning package.
8. GATE: `dev/import_hygiene_scan.py` becomes the authoritative CI gate,
   superseding `test_public_api_boundaries.py` and
   `test_architecture_boundaries.py` (seed their existing allowlisted
   exceptions as named entries). Ratchet: checked-in production-Family-1
   baseline JSON; CI fails if current > baseline; every closing commit shrinks
   the baseline in the same commit; flip to hard `assert 0` once production
   reaches 0. Family-2 shim allowlist and the Family-3 pinned-symbol set are
   structural.
9. SEQUENCING: promotions before rewrites; batch promotions by OWNING package
   (largest first: `domain.modelos` 24 sym/67 sites,
   `adapters.outbound.google` 18/26, `core` 13/35, ...); batch consumer
   rewrites by IMPORTER area (`application.modelo` 708, `entrypoints.cli` 466,
   `application.user_profile` 221, ...); Family 2/3 + umbrella-retire after the
   production Family-1 wave; test wave last. Every batch:
   `pytest --collect-only -q` clean before commit (relocation atomicity),
   behavior-preserving substitutions only.

## Rationale
Grounded in the re-runnable AST scan (`python dev/import_hygiene_scan.py`);
every count reproducible. Ownership-first + promotion-before-rewrite is the
only shape keeping each commit small and correct. Every Family-2/3
disposition was verified by reading the actual module (caught the `_retencion`
naming collision and the fake-circular-workaround Ruling-1 violations).

## Consequences
Gains: single canonical import path project-wide; a ratcheting gate that only
moves toward zero; two ad-hoc gates retired into one; the
percepciones/retencion naming collision resolved; three latent violations
inside the circular-workaround fixed. Costs: 250 production files + ~180
additional consumer sites from the umbrella RETIRE decision;
ratcheting-baseline discipline (shrink-in-same-commit); underscore-promotion
per-symbol judgment. Deferred/out-of-scope: `save_envelope` cosmetic rename;
the 1599 test-only sites (last wave).

## Codification Candidates
Refine `service-imports-via-top-level-reexports` into the project-wide Ruling-1
policy + Ruling-2 promotion mechanism + Ruling-4 bridge distinction. New
candidate `dynamic-import-targets-the-public-facade` generalizing Ruling 6.
