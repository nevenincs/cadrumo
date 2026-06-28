---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S246'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s246-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S246`

Closed `AFR-144` for the registry corpus application service.

## Description

- Reviewed `src/aeat/application/registry/_corpus.py` as a read-only corpus projection boundary for normatives, manuals, topics, and bundled registry operator surfaces.
- Verified the module does not persist profile, secure-object, master-key, or remote-provider state.
- Classified the filesystem access as plaintext-exception: operator/resource corpus roots are read through centralized settings and domain corpus loaders.
- Replaced raw English registry corpus refusal messages with `translated_message` keys and structured context.
- Added real behavior tests for localized registry topic locale, manual id, manual section, and manual rule-kind refusals.
- Enrolled the missing registry and modelo work CLI locale strings through `python -m aeat.locales`.
- Closed `S246` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-144` is closed as a `plaintext-exception` with `plain-file` signals. The module remains a corpus/read-model boundary: it reads bundled or configured corpus material and returns Pydantic projection reports, while user-facing refusals now route through the project translation and core error-envelope path.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/registry/_corpus.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py`
- `uv run --no-sync pytest -q src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The locale audit exposed pre-existing modelo work CLI keys that were still relying on embedded `tr(..., default=...)` values. Those strings were enrolled as part of this step because they are on the same localization consistency surface and the canonical locale audit covers the full catalog.
