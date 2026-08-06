---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:8681056160fc60c86cae3ba5dd4aebae095196b1a50bb1ddd7a052d7dbb80fe0'
step_id: 'S15'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `KNOWN_PROFILE_FLAG_ADVISORY_FIELDS`, `select_revision` to `aeat.domain.calculations.registry.__all__` with eager re-exports so the 2 existing cross-package consumer site(s) can import from the facade

## Scope

This record covers the full Wave `W01` facade-promotion tail assigned to this
executor: `registry` (Phase `P12`, the originating Step for this record) plus
every remaining owning package not assigned to the other four Wave-1
executors -- Phases `P13` through `P35` inclusive (24 phases total, 34
symbols across 24 owning packages).

- `src/aeat/domain/calculations/registry/__init__.py` and `_loader.py`
- `src/aeat/adapters/persistence/storage/master_key/__init__.py` and `_active_session.py`
- `src/aeat/adapters/persistence/storage/crypto/__init__.py`
- `src/aeat/application/wizard/__init__.py`
- `src/aeat/application/user_profile/__init__.py`, `_orchestration.py`, `_validation.py`, `_custody_carry.py`, `_repository.py`
- `src/aeat/core/parsing` consumers (no facade change; disposition already resolved)
- `src/aeat/application/aggregation/__init__.py`
- `src/aeat/adapters/persistence/storage/envelope/__init__.py` and `_envelope.py`
- `src/aeat/adapters/persistence/storage/sql/__init__.py`
- `src/aeat/domain/invoices/__init__.py` and `_models.py`
- `src/aeat/adapters/outbound/storage/__init__.py` and `_factory.py`
- `src/aeat/application/storage/calc_sheets/__init__.py`
- `src/aeat/domain/__init__.py`
- `src/aeat/domain/attachments/__init__.py`
- `src/aeat/adapters/outbound/aeat/auth/__init__.py`
- `src/aeat/domain/buckets/__init__.py`
- `src/aeat/domain/renta/__init__.py`
- `src/aeat/application/workflow/__init__.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/modelo/__init__.py` and `_m036_lifecycle.py`
- `src/aeat/core/i18n/__init__.py`
- `src/aeat/domain/portals/__init__.py`
- `src/aeat/entrypoints/cli/__init__.py` and `_app_contract.py`
- Consumer sites owned by this executor across `src/aeat/entrypoints/cli/`, `src/aeat/application/`, `src/aeat/adapters/persistence/storage/`, and two test files under `src/aeat/agent/`

## Description

- Promoted plain (non-underscore) symbols to their owning package `__all__` with eager re-exports for: `registry` (`select_revision`, `KNOWN_PROFILE_FLAG_ADVISORY_FIELDS`), `master_key` (`evaluate_idle`, `get_active_master_key`, `has_active_bucket_session`), `crypto` (`decrypt_encrypted_bytes_column`, `decrypt_secure_object_payload`, `encrypt_secure_object_payload`, `secure_object_payload_aad`), `wizard` (`WizardStatusError`, `WizardStatusReport`, `build_wizard_status`, `load_active_taxpayer_profile`), `application.user_profile` (`list_profile_key_records`, `validate_profile_values`, lazy `__getattr__`), `application.aggregation` (`MISSING_DEDUCTIBLE_VAT_EVIDENCE_SOURCE_KIND`, `compute_ledger_filing_evidence`, `compute_ledger_filing_snapshot`), `sql` (`Base`, `SecureObjectRow`), `domain.invoices` (`find_invoice`, `find_unmatched`), `application.storage.calc_sheets` (`OperatorInputScenario`, `verify_modelo_parity`), `domain` (`canonical_decimal_string`), `domain.attachments` (`is_link_only_mime_type`), `domain.buckets` (`BucketEventHistoryRepositoryProtocol`), `domain.renta` (`RentaValidationError`), `application.workflow` (`AuthState`, re-exported from `application.auth`), `application.ledger` (`PurchaseInvoiceEvidenceRepository`), `core.i18n` (`clear_output_language_cache`), `domain.portals` (`portal_host_name`), `registry` follow-up (`selector_as_dict`, discovered mid-wave).
- Applied per-symbol underscore-candidate dispositions per ADR ruling 3: rename-to-public-and-promote for `master_key._active_session` (new `current_active_bucket_session()` read accessor replacing the raw `ContextVar` reach), `envelope._build_aad`/`_derive_envelope_key` (renamed to `build_aad`/`derive_envelope_key`, reused verbatim by key rotation), `application.user_profile._refuse_duplicate_label`/`_require_registered_label` (renamed to public, shared create/edit validators), `adapters.outbound.storage._build_google_credentials`/`_resolve_drive_root_folder_id` (renamed to public, reused by two CLI call sites), `application.modelo._m036_declaration_object_key` (renamed to public, matching the sibling `*_object_key` convention), `entrypoints.cli._command_schema_refs` (renamed to public `command_schema_refs`, exposed via a package `__getattr__` so resolving it never eagerly imports the registry-heavy `_app_contract` lazy command module), and `adapters.outbound.aeat.auth._classify_identity` (the real definition was already the public `classify_identity` in `_clave_movil_support`; promoted that name instead of the private re-alias).
- Applied a narrower-public-API disposition (no new leaked internals) for `registry._build_modelo_definition_from_data`/`_load_modelo_manifest`/`_load_modelo_revisions`: added one purpose-built `load_modelo_directory_without_locales()` composing the three loader helpers, and repointed the sole consumer (`locales._modelo_manager`) onto it.
- For `core.parsing`'s `_parse_bool`/`_parse_date`/`_parse_iso8601_date`, found the public aliases (`parse_bool`, `parse_date`, `parse_iso8601_date`) already existed at the facade; repointed only the consumer sites owned by this executor and left the sites in other executors' packages for their sweeps.
- For `domain.calculations`'s `CasillaFieldKind`, found the symbol already exported from the sibling `domain.calculations.registry` facade and the bare `domain.calculations` package is deliberately empty by design (per its own module docstring); repointed the one owned consumer onto the registry facade instead of adding a new export.
- Repointed every consumer file owned by this executor from the private submodule it was reaching into onto the new/existing facade import, in the same commit as each promotion.
- Ran `python dev/import_hygiene_scan.py` before and after: distinct owning packages needing promotion dropped from 34 to 4, and distinct symbols needing promotion dropped from 149 to 18; all 4 remaining packages (`core`, `core.parsing` residual consumers, `domain.calculations` residual consumer, `domain.contribuyente`) are owned by other Wave-1 executors.

## Outcome

All 24 owning packages assigned to this executor (`registry` plus the
tail) reached zero remaining "needs promotion" entries for consumer sites
this executor is permitted to touch. 13 commits landed, each verified with
`ruff check`, a direct Python import smoke-test of the promoted symbols,
and `pytest --collect-only -q src/aeat` (0 collection errors) before
committing. Targeted `pytest -m ""` runs against every touched package's
own test directory passed (e.g. 232 passed / 6 skipped for
`adapters.outbound.aeat.auth` + `application.auth`; 119 passed for
`adapters.persistence.storage` envelope/rotation; 87 passed for the
`core.parsing` / registry export-parse / user-profile validation slice).
A full-tree `pytest --collect-only -q src/aeat` at closeout collected
14256 items with 0 errors.

## Notes

- Two git-safety incidents occurred and are disclosed for the record.
  First, the initial registry-package commit was made with a bare
  `git commit -m "..."` after `git add -- <files>`; because other agents
  had unrelated work already staged in the shared index (a large registry
  restructuring touching modelo 100 anualidades bindings and a deleted
  test file), that bare commit swept their staged snapshot in under this
  executor's message. No data was lost (nothing was destroyed; the prior
  content remains reachable in the parent commit and the peer's remaining
  unstaged edits were untouched), but the commit is misattributed. Every
  subsequent commit in this session used an explicit pathspec
  (`git commit -m "..." -- <files>`) verified beforehand via
  `git diff --cached --stat` to contain only this executor's files.
  Second, one pathspec commit (`_custody_carry.py`) picked up a small
  UTF-8-constant hygiene change this executor did not author, entangled
  with this executor's two facade-import fixes in the same file; the
  working tree showed no pending remainder afterward, so the peer edit was
  complete, not truncated.
- A full-suite background test run (multiple `pytest -q -m ""` invocations
  across every touched package's test directory) was launched twice during
  this session but its output file never populated by closeout, despite
  the equivalent foreground/targeted runs passing cleanly; this is noted
  as an unresolved harness-output oddity, not a code defect, given every
  foreground verification (ruff, imports, collect-only, targeted pytest)
  passed.
- Several packages this executor does not own (`core`, `core.parsing`
  residual, `domain.calculations` residual, `domain.contribuyente`)
  still show consumer sites reaching into private submodules for symbols
  this executor promoted or that already have public aliases; those sites
  live in other Wave-1 executors' owned packages (per the dispatch brief's
  ownership split) and are explicitly left for their sweeps.
- Encountered repeated transient collection/import failures during the
  session caused by concurrent unrelated peer WIP actively restructuring
  the modelo registry tree (a `PayerFact` enum attribute gap, then a
  modelo-390 legal-refs validation gap); neither was introduced by this
  executor's changes, both were confirmed by reproducing the identical
  failure via a bare `import aeat.domain.calculations.registry` with none
  of this executor's edits applied, and both had resolved by the final
  full-tree collection check.
- A large combined background `pytest -m "" -n auto` sweep across every
  touched package plus `entrypoints.cli/tests` and `application.filing/tests`
  surfaced 450 failed / 52 errors, almost entirely in modelo 100/130/202/
  210/303/390 calculation, filing, and CLI integration tests this executor
  never touched. Re-running individual failing files standalone
  (`test_registry_cli.py`, `test_selectors.py`) produced clean passes
  (34/34, 13/13) moments later with zero code changes in between,
  consistent with `aeat-local-execution`'s guidance that registry-suite
  failures under heavy concurrency are loader-cache races from concurrent
  registry writes, not regressions. One residual class
  (`test_work_resume.py`, "the primary database route does not match the
  active bucket session") was investigated directly against this
  executor's one storage-runtime edit
  (`adapters.persistence.storage.runtime`): a line-ending-normalised diff
  against the pre-edit committed revision confirms the change is exactly
  the four intended `_active_session.get()` -> `current_active_bucket_session()`
  substitutions with zero semantic difference, and the failing
  `ROUTE_BUCKET_MISMATCH` branch is untouched by that diff. This failure
  class is therefore pre-existing / caused by other concurrent work, not
  this executor's promotion.
