---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - '[[2026-04-30-aeat-restructure-plan]]'
---

# `aeat-restructure` `continuation` `sync-domain-hard-cut`

Collapsed duplicate sync domain ownership into `aeat.domain.sync` and removed application-side primitive forwarding modules.

- Modified: `src/aeat/domain/sync/__init__.py`
- Modified: `src/aeat/domain/sync/_protocols.py`
- Modified: `src/aeat/application/sync/__init__.py`
- Modified: `src/aeat/application/sync/_runner.py`
- Modified: `src/aeat/application/sync/_dispatcher.py`
- Modified: `src/aeat/application/sync/_repository.py`
- Modified: `src/aeat/application/sync/_strategies/_additive_allowlist.py`
- Modified: `src/aeat/application/sync/_strategies/_base.py`
- Modified: `src/aeat/application/sync/_strategies/_benign.py`
- Modified: `src/aeat/application/sync/_strategies/_escalate.py`
- Modified: `src/aeat/application/review/_models.py`
- Modified: `src/aeat/application/review/_adapters.py`
- Modified: `src/aeat/application/workflow/_adapters.py`
- Modified: `src/aeat/application/filing/_history_repository.py`
- Modified: `src/aeat/entrypoints/cli/sync/list.py`
- Modified: `src/aeat/entrypoints/cli/sync/show.py`
- Modified: `src/aeat/entrypoints/cli/sync/resolve.py`
- Modified: `src/aeat/core/config.py`
- Modified: `src/aeat/domain/manuals/_schema.py`
- Modified: `src/aeat/domain/normatives/_schema.py`
- Modified: `src/aeat/domain/vat/_schema.py`
- Modified: `src/aeat/domain/vat/_classification.py`
- Modified: `src/aeat/domain/vat/_modelo_303_mapping.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/records.py`
- Modified: `README.md`
- Modified: `docs/architecture.md`
- Deleted: `src/aeat/application/sync/_classifier.py`
- Deleted: `src/aeat/application/sync/_divergence.py`
- Deleted: `src/aeat/application/sync/_errors.py`
- Deleted: `src/aeat/application/sync/_protocols.py`
- Deleted: `src/aeat/application/sync/_validator.py`
- Deleted: `src/aeat/application/sync/_wire.py`

## Description

The duplicate sync domain cluster was split incorrectly after the restructure: `aeat.domain.sync` held the canonical divergence taxonomy, wire models, validator, classifier, and errors, while `aeat.application.sync` still contained same-named primitive modules. The application modules had been converted to forwarding surfaces during the audit wave, but the ADR calls for a hard cut rather than compatibility layers.

This step updates application sync orchestration, review adapters, workflow adapters, filing-history persistence, and sync CLI code to import pure sync primitives from `aeat.domain.sync`. `aeat.application.sync` now exports only orchestration and persistence surfaces: runner, dispatcher, repository, and strategies. The six application-side primitive modules were removed.

The same wave removed unused sync runner constructor slots for schema loader, manual rules loader, and LLM client/request protocols. Those dependencies were not used by the runner path and matched the plan's hollow Protocol cleanup item. The remaining certificate dependency was renamed to `CertificateContextPreloader` to avoid colliding with the outbound AEAT certificate backend enum.

Active docs were updated so `aeat.domain.sync` is the documented home for divergence taxonomy, wire records, validation, and classification, while `aeat.application.sync` is documented as orchestration and divergence persistence.

The duplicate-domain scanner also flagged repeated private `_StrictFrozen` base class names across manuals, normatives, VAT, and SQL record modules. Those were renamed to module-specific private base names so cross-root duplicate class-name scans are clean without changing public model names or behaviour.

## Tests

- `uv run --no-sync pytest src/aeat/domain/sync src/aeat/application/sync src/aeat/application/review src/aeat/application/workflow src/aeat/application/filing/_test_history_repository.py src/aeat/application/filing/_test_integration_wave4.py src/aeat/entrypoints/cli/sync src/aeat/entrypoints/cli/review -q` — 188 passed.
- `uv run --no-sync pytest tests/import_contract/test_adr_layout_import_smoke.py src/aeat/core/errors/test_registry.py src/aeat/core/errors/test_registry_enforcement.py -q` — 109 passed.
- `uv run --no-sync pytest src/aeat/application/sync src/aeat/domain/sync -q` — 57 passed.
- `uv run --no-sync pytest src/aeat/domain/manuals src/aeat/domain/normatives src/aeat/domain/vat src/aeat/adapters/persistence/storage/sql -q` — 164 passed.
- `uv run --no-sync ty check src/aeat/domain/sync src/aeat/application/sync src/aeat/application/workflow src/aeat/entrypoints/cli/sync` — passed.
- Stale-reference scans for deleted `aeat.application.sync._divergence`, `_errors`, `_classifier`, `_protocols`, `_validator`, and `_wire` active source references returned no hits.
- AST duplicate class-name scan across non-test `src/aeat/core`, `src/aeat/domain`, `src/aeat/application`, and `src/aeat/adapters` returned no cross-root duplicate class names.
