---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W18-P38-S442]]'
---

# `secure-storage-production-hardening` `W18.P38.S442` Review

## S442-001 | PASS | Projection module does not own storage routing

Reviewed the S442 scope as `vaultspec-code-reviewer`. `src/aeat/application/modelo/_projection.py`
loads existing work units and calculation revisions through the application action
surface, reads bundled registry snapshots through `resources()`, and asks
`resolve_profile_sourced_bindings()` for profile-derived formula inputs. It does not
construct secure-object repositories, open SQL engines, inspect bucket manifests, or
persist files directly.

## S442-002 | PASS | Profile reads remain delegated and typed

The module resolves the active bucket id, then delegates profile fact projection to the
profile binding resolver. That resolver returns typed Decimal, enum, and date channels,
skips missing profile facts so the calculation engine can raise the actual missing
binding refusal, and logs only recoverable derived-fact parse failures at debug level.

## S442-003 | PASS | Error and locale contracts are enrolled

Projection and comparison exceptions derive from the project `AeatError` hierarchy.
The central application error registry contains entries for the projection base class,
M130 absence, invalid decimal override, compare-year shape, no work units, no
revisions, and no usable revisions. The locale audit passed through the canonical
`python -m aeat.locales audit` CLI.

## S442-004 | PASS | Validation

Focused ruff passed for the projection module, projection CLI registrar, and projection
CLI tests. Modelo projection integration tests passed with 4 tests. The modelo CLI spine
selection passed with 2 selected tests. Error-registry tests passed with 14 tests.
Locale audit passed for `ca`, `en`, `es`, and `hu`.

Disposition: close `AFR-294` as `manifest-discovery`.
