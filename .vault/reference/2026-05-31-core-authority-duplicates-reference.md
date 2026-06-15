
---
tags:
  - '#reference'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-adr]]'
---


# Core authority duplicates reference

Mechanical breadth scan of src/aeat/ for declarations with identical names across 2+ modules, classified as semantic duplicates vs accidental name collisions.

## Methodology

Extraction pattern: top-level `class Name(...)`, `def func(...)`, and `UPPER_SNAKE_CASE = ...` assignments. Test-file fixtures with `_` prefix are evaluated for isolation intent but still tracked.

## Semantic Duplicates - Consolidation Required

**_Holder** (5 files): BaseModel test fixture.
- src/aeat/domain/attachments/test_ids.py:15
- src/aeat/domain/invoices/test_ids.py:15
- src/aeat/domain/modelos/test_verification_report_id.py:15
- src/aeat/domain/transactions/test_id_normalization.py:15
- src/aeat/domain/user_profile/test_snapshot_hash_equality.py:15
- Action: Move to src/aeat/tests/fixtures/identity_holder.py.

**_EmptyAnswersBase** (4 files): Wizard test base.
- src/aeat/application/wizard/test_commands_helpers.py:41
- src/aeat/application/wizard/test_compile.py:35
- src/aeat/application/wizard/test_models.py:32
- src/aeat/application/wizard/test_audit_rules.py:28
- Action: Consolidate to src/aeat/application/wizard/test_fixtures.py.

**_DummyRepository** (3 files): Generic test mock.
- src/aeat/core/resources/test_registry.py:60
- src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py:46
- src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py:57
- Action: Move to src/aeat/tests/fixtures/repositories.py.

**_IsolatedSettings** (3 files): Settings sandbox.
- src/aeat/domain/manuals/test_loader.py:28
- src/aeat/domain/manuals/test_verify.py:19
- src/aeat/adapters/outbound/llm/test_client.py:32
- Action: Consolidate to src/aeat/tests/fixtures/settings.py.

**PROJECT_ROOT** constant (4 files): Path resolution.
- src/aeat/core/config.py:60 (production)
- src/aeat/core/paths.py:23 (production)
- src/aeat/tests/test_release_config.py:33 (test)
- src/aeat/entrypoints/cli/test_retired_cli_literals.py:9 (test)
- Action: Canonicalize in src/aeat/core/paths.py, replace with import.

**SCHEMA_VERSION** (2 files): Profile versioning.
- src/aeat/domain/profile/inventory/__init__.py:34
- src/aeat/domain/profile/assets/__init__.py:20
- Action: Define parent, import children.

**USER_PROFILE_*_NAMESPACE** (2 files each): Storage duplication.
- src/aeat/application/user_profile/_repository.py:44-45
- src/aeat/adapters/persistence/storage/_namespace_registry.py:221, 230
- Action: Remove re-bindings, import from registry.

## Name Collisions - Rename Required

**_ReconfigurableStream** (2 files): Protocol vs test helper.
- src/aeat/core/json_contract.py:112 (production)
- src/aeat/entrypoints/cli/test_stdio.py:95 (test)
- Action: Rename test to _MockRedirectableStream.

**_EnvelopePayload** (2 files): Master-key vs test.
- src/aeat/adapters/persistence/storage/master_key/_master_key.py:99
- src/aeat/entrypoints/cli/test_common_output.py:15
- Action: Rename test to _TestPayload.

**ExportFormatError** (2 files): Module boundary ambiguity.
- src/aeat/application/export/_errors.py:8
- src/aeat/adapters/outbound/aeat/export/_errors.py:12
- Action: Establish hierarchy clarity.

**PortalRow** (2 files): ORM vs domain model.
- src/aeat/adapters/persistence/storage/sql/_orm.py:52
- src/aeat/application/portals/_service.py:24
- Action: Rename application to PortalServiceRow.

**_DummyPayload / _Draft** (2+ files): Test fixture collisions.
- Action: Use domain-specific names.

## Test Fixture Functions (High Redeclaration)

Intentional isolation, consolidation recommended:
- _isolated_backend: 28 instances -> conftest
- secure_objects: 22 instances -> fixture module
- cli_runner: 21 instances -> CLI conftest
- _transaction: 17 instances -> domain fixture
- _isolated_cli_backend: 16 instances -> CLI conftest

## Summary

- Semantic duplicates: 6-8 requiring consolidation
- Name collisions: 5 requiring rename/clarification
- Total duplicate-name groups: 10 classes, 9 constants
- Function duplicates: 356 (mostly acceptable test isolation patterns)
