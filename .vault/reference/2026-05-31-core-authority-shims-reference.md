---
tags:
  - "#reference"
  - "#core-authority-shims"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-30-identity-primitives-adr]]"
---

# core-authority-shims reference: shim and re-export inventory across src/aeat/

Module(s): src/aeat/core/, src/aeat/application/, src/aeat/adapters/,
           src/aeat/entrypoints/, src/aeat/domain/
File(s):   see per-category listings below
Related:   `2026-05-30-identity-primitives-adr`

## Category 1 - Private-name re-aliases

The dominant codebase pattern is bare private-aliased imports inside non-__init__ files.
This is the accepted idiom and is NOT a shim unless the alias is then re-exported via
__all__ or left importable through the package surface.

True private re-alias shims found:

- src/aeat/adapters/outbound/llm/_providers/__init__.py:11-12
  Re-aliases _ProviderAdapter and _DeterministicAdapter from .base and .deterministic
  under the same private names. Module docstring calls them redundant aliases.
  Absent from __all__ but importable through the package.
  Canonical sites: .base._ProviderAdapter, .deterministic._DeterministicAdapter.
  Migration cost: 0 external callers (internal-only).

- src/aeat/core/errors/registry/__init__.py:7-11
  Five _DECLARED_ERROR_CODES tuples imported under distinct aliases then merged into
  _ALL_DECLARED_ERROR_CODES. Internal aggregation, not re-exported publicly. Not-a-shim.

## Category 2 - Public re-exports in __init__.py walls

### Legitimate package-API __init__.py files (do not eliminate)

src/aeat/core/identity/__init__.py
  BucketId, ProfileId, SnapshotId, TransactionId, SubjectTaxId, IdentityDocument,
  IdentityError, validate_identity, validate_spanish_tax_id.
  Caller migration cost: very high - identity primitives used across the entire codebase.

src/aeat/adapters/persistence/storage/__init__.py
  ~80 names across crypto, envelope, master-key, sql, rotation, namespace-registry.
  Persistence-layer public boundary contract. Caller migration cost: very high.

src/aeat/adapters/persistence/storage/sql/__init__.py
  SecureObjectRepository, engine, session, records, repositories (15 names).
  Caller migration cost: high (~20 direct callers).

src/aeat/domain/calculations/registry/__init__.py
  ValidatedRegistryAuthority, RegistryValidator, ~30 snapshot/calculation types.
  Caller migration cost: very high.

src/aeat/application/auth/__init__.py
  Aggregates catalogue, models, sessions, diagnostics, operator-view names.
  Caller migration cost: high.

### Name-hygiene shim __init__.py files

src/aeat/core/time/__init__.py:14-21
  Re-exports _now, _coerce_utc_aware, _validate_utc_aware with __all__ listing only
  underscore-prefixed names. A package whose entire public surface is private-named is
  a hygiene inconsistency. 11 callers import _now via this package. Either rename to
  now/coerce_utc_aware/validate_utc_aware and update callers, or have callers import
  directly from ._clock / ._utc.

src/aeat/core/parsing/__init__.py:15-18
  Re-exports _parse_bool, _parse_date, _parse_ddmmyyyy_date, _parse_iso8601_date;
  __all__ lists all four private-named symbols. Two domain callers alias _parse_date
  again as _parse_date_canonical (adapters/outbound/aeat/sede/_censo.py:158,
  domain/deadlines/_profiles.py:18).

## Category 3 - Compatibility wrappers (one-liner forwarders)

None found. application/auth/_sessions.py:85-93 documents error hierarchy inheritance
for catch-site compatibility in a docstring. SessionDeserializationError inheriting
AuthSessionUnavailableError is intentional error-hierarchy design, not a wrapper.

## Category 4 - Deprecated-name paths

One speculative dead import:

src/aeat/adapters/outbound/storage/_google_drive.py:698-699
  import json retained per inline comment about forward compatibility when appProperties
  payloads need stringification. No current caller uses it. Zero migration cost to delete.

All other grep hits for deprecated/legacy/compatibility are test descriptions, domain
comments about historical AEAT form revisions, or error-hierarchy docstrings.

## Category 5 - Conditional / version-guarded imports

Legitimate guards (not shims):

src/aeat/application/wizard/_prompter.py:59
  prompt_toolkit.output.win32 Windows-only platform guard.

src/aeat/adapters/persistence/storage/master_key/_master_key.py:392
  keyring.backends.fail optional backend guard.

src/aeat/application/diagnostics.py:297-307
  Broad try-import block handling absent active-bucket session at diagnostics time.
  Availability guard, not a compatibility shim.

No graceful-degradation shims found in production code.

## Category 6 - Split-import paths (unintended shims)

### resolve_active_bucket_id - two extra import paths above canonical

Canonical declaration: src/aeat/core/_bucket_pointer_io.py:48

Shim path A: application/workflow/_models.py:29 imports resolve_active_bucket_id
from core._bucket_pointer_io as a bare module-level name (no as-alias, no __all__).
This makes it importable as aeat.application.workflow._models.resolve_active_bucket_id.

14 import sites on shim path A:
  entrypoints/cli/test_profile_census_verbs.py:65,176
  entrypoints/cli/test_repair_privacy_contract.py:19
  entrypoints/cli/test_ratios_verbs.py:14
  entrypoints/cli/test_profile_lifecycle_verbs.py:396,423,922,963
  application/user_profile/test_orchestration.py:168
  application/workflow/test_active_profile_resolution.py:23
  entrypoints/cli/_config/__init__.py:40,339,917,1242

Migration: update all 14 to:
  from aeat.core._bucket_pointer_io import resolve_active_bucket_id

### utc_now vs _now - two parallel time implementations

src/aeat/core/_time.py:8 - utc_now(), public name, 4 production callers:
  domain/user_profile/_values.py:16
  application/workflow/_utils.py:5
  application/auth/_actions.py:7
  application/filing/__init__.py:10

src/aeat/core/time/_clock.py - _now(), private name, re-exported via core/time/__init__.py,
11 callers including:
  application/workflow/_engine.py
  application/storage/calc_sheets/_records.py
  application/live/_verify.py, _notifications.py, _expedientes.py
  application/ledger/_evidence.py, _business_operation_invoice.py
  application/inventory/_service.py

Both functions call datetime.now(tz=UTC). One must be retired.
Total migration cost: 15 import sites.

## Worst offenders by re-export volume

1. adapters/persistence/storage/__init__.py - ~80 names. Legitimate.
2. application/live/__init__.py - ~28 public + ~60 private-aliased. Legitimate.
3. domain/calculations/registry/__init__.py - ~35 names. Legitimate.
4. core/identity/__init__.py - 9 names from 5 sub-modules. Legitimate.
5. adapters/persistence/storage/sql/__init__.py - 15 names. Legitimate.
6. core/time/__init__.py - 3 names, all private-named. Name-hygiene shim.
7. core/parsing/__init__.py - 4 names, all private-named. Name-hygiene shim.
8. adapters/outbound/llm/_providers/__init__.py - 2 private re-aliases. Minor shim.

## Worst offenders by caller-migration cost

1. resolve_active_bucket_id split via workflow._models - 14 sites.
2. core._time.utc_now vs core.time._now split - 15 sites, 2 parallel implementations.
3. core.time.__init__ private-named surface - 11 callers importing _now.
4. core.parsing.__init__ private-named surface - double-aliasing of _parse_date.
5. _google_drive.py dead json import - 0 sites, trivial deletion.

## Top 5 legitimate package APIs (must not be treated as shims)

1. aeat.core.identity - flat surface for all identity primitives; sub-modules
   are intentionally private.
2. aeat.adapters.persistence.storage - persistence-layer public contract.
3. aeat.domain.calculations.registry - registry authority public surface.
4. aeat.adapters.persistence.storage.sql - SQL substrate public surface.
5. aeat.application.auth - auth application public surface.

## Summary counts by category

Category 1 private re-aliases (shim): 1 package (_providers/__init__ x2 names)
Category 2 __init__ walls (legitimate): 5 - do not touch
Category 2 __init__ walls (name-hygiene shim): 2 - core/time, core/parsing
Category 3 compatibility wrappers: 0
Category 4 deprecated-name dead imports: 1 - _google_drive.py json import
Category 5 conditional guards (legitimate): 3 - no action needed
Category 6 split-import paths: 2 - resolve_active_bucket_id (14 sites), utc_now/_now (15 sites)

Total shims requiring action: 6
  1 redundant private-alias package
  2 name-hygiene __init__ walls
  1 dead import
  2 split-path patterns covering 29 import sites combined
