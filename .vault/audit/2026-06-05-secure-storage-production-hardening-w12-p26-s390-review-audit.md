---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S390]]'
---

# `secure-storage-production-hardening` `W12.P26.S390` Review

## S390-001 | PASS | CLI schema module is a re-export boundary

Reviewed the S390 scope as `vaultspec-code-reviewer`. `_schemas.py` imports and
re-exports the canonical schema registry, output base classes, envelope type, and JSON
emit helpers from `aeat.core.json_contract`. It does not create storage repositories,
read active-profile pointers, inspect manifests, load settings, access environment
variables, perform remote IO, or catch exceptions.

## S390-002 | FIXED | Config payload schema decorators were not loaded by conformance gate

The conformance gate's contract says it imports payload modules before comparing CLI
leaves to `SCHEMA_REGISTRY`, but the config payload module was not imported. Because
config command payload classes register schemas with decorators and config command
bodies import those classes lazily, the exact-match gate saw 37 config leaves as
unregistered. The test now imports `_config_payloads` before walking the command tree,
preserving the exact assertion instead of introducing an allowlist.

## S390-003 | PASS | IVA wallet seed errors have centralized base and registry entries

Validation surfaced existing Modelo IVA wallet seed error classes whose base still
derived from bare `Exception` and lacked central `ErrorCode` declarations earlier in the
shared-worktree run. Current HEAD now has the seed base deriving from `ModeloError`, and
the registry declares the seed classes with localized message keys and refusal/error
categories.

## S390-004 | TRACKED | Dirty cross-period clean-state locale leaf remains with owning slice

The shared dirty worktree also contains a cross-period clean-state implementation that
references `application.modelo.errors.cross_period_clean_state_incomplete`. The `en`,
`es`, `ca`, and `hu` leaves were added locally through `python -m aeat.locales set`, and
`python -m aeat.locales audit` passes in the current worktree. Those locale and registry
changes are intentionally left with the cross-period owning slice because its source
class is not present in committed HEAD.

## S390-005 | FIXED | Config repair extraction kept documented schema exceptions aligned

The config repair callback moved to `_config/_repair_cli.py`, but the zero-bare-emit
gate still hard-coded only the old `_config/__init__.py` exemption. The gate now uses
the documented exemption path set and includes the extracted repair callback. Missing
nested repair integrity help strings were added through `python -m aeat.locales`.

## S390-006 | PASS | Validation

Focused ruff passed for the S390 schema/test/error-registry surface. The CLI schema
conformance suite passed with 45 selected integration tests. Error-registry enforcement
passed with 14 selected tests. The locale audit passed through the canonical
`aeat.locales` CLI in the current shared worktree.

Reviewer note: no critical, high, medium, or low findings remain for the staged S390
slice. The dirty cross-period clean-state work remains tracked with its owning slice.

Disposition: close `AFR-288` as `plaintext-exception`.
