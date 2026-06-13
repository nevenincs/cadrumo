---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S277-001 | PASS | Wizard translation audit boundary

The `W12.P26.S277` review found that `src/aeat/application/wizard/_translations.py`
is a local locale-coverage audit helper. It walks wizard descriptors and statically
referenced CLI translation keys, then checks them through `tr(...)`. It does not own
secure-storage persistence, remote-provider mirroring, bucket manifests, master-key
material, or runtime profile state.

## S277-002 | PASS | Plain-file and remote-mirror disposition

The module's `Path` usage is limited to reading local CLI Python source files for
translation-key discovery. It does not read or write operator data, remote-provider
state, or mirror payloads. Remote-provider signal is therefore closed as a translation
surface false positive rather than a storage route.

## S277-003 | PASS | Locale catalogue repair

The canonical locale CLI audit found missing `cli.app.modelo.work.create_stub_*_refused`
keys and one stale `relation_not_decimal` extra. The repair was performed through
`python -m aeat.locales` only: scaffold reconciled the concrete source keys and the
final locale audit passed for `en`, `es`, `ca`, and `hu`.

## S277-004 | PASS | Duplication and validation

Vaultspec RAG semantic search clustered the slice with wizard translation audits, CLI
translation-key extraction, and locale parity tests. The implementation reuses the
shared locale manager and `tr(...)` resolver rather than carrying duplicate catalogue
parsing.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_translations.py src/aeat/application/wizard/test_translations_helpers.py src/aeat/application/wizard/test_wizard_translations_resolve.py src/aeat/application/wizard/test_flow_description_keys.py src/aeat/locales`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_translations_helpers.py src/aeat/application/wizard/test_wizard_translations_resolve.py src/aeat/application/wizard/test_flow_description_keys.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "wizard translations audit cli translation keys locales source introspection remote provider mirror" --type code --port 8766 --max-results 8`

Disposition: close `AFR-175`.
