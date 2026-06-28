---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-02'
modified: '2026-05-02'
related:
  - '[[2026-04-30-aeat-restructure-plan]]'
---

# `aeat-restructure` `continuation` `duplicate-sync-cli-hardening`

Completed the next autonomous hardening wave against the restructure ADR.

- Modified: `src/aeat/domain/_identifiers.py`
- Modified: `src/aeat/domain/sync/*`
- Modified: `src/aeat/application/sync/*`
- Modified: `src/aeat/application/review/*`
- Modified: `src/aeat/application/filing/*`
- Modified: `src/aeat/domain/{casillas,categories,formulas,manuals,normatives,schema,submission,vat}/*`
- Modified: `src/aeat/adapters/{inbound,declaracion,outbound}/**`
- Modified: `src/aeat/entrypoints/cli/**`
- Modified: `src/aeat/core/errors/_registry.py`
- Modified: `docs/error-codes.md`

## Description

Repaired the interrupted duplicate-domain audit wave and removed the accidental identifier-corruption from the previous mechanical edit. Canonicalized `ModeloIdentifier` through `aeat.domain._identifiers`, kept sync pure primitives under `aeat.domain.sync`, and kept `aeat.application.sync` limited to orchestration, repository, runner, dispatcher, and strategies.

Removed remaining duplicate public domain class names by making public names domain-specific for formula/schema casilla references, category/VAT citations, and manual/normative/VAT verification reports. Removed the declaracion label-regex shim and wired consumers directly to the PDF label-regex adapter helper. Split submission-domain errors from the core live-write access gate while preserving the permanent `LiveSubmitForbiddenError` in `aeat.core.access_gate`.

Pruned stale CLI imports for command modules that no longer exist in this worktree, restored local CLI helper behavior where deleted helper modules were still imported, and removed tests that targeted deleted CLI command modules. Removed stale sync error-code rows and stale generated error-code table entries.

## Tests

Validation completed:

- `uv run --no-sync ty check src/aeat/entrypoints/cli src/aeat/adapters/outbound/aeat/export src/aeat/adapters/inbound/declaracion src/aeat/adapters/inbound/sanitizer src/aeat/domain/sync src/aeat/application/sync src/aeat/application/review src/aeat/application/filing src/aeat/domain/submission src/aeat/core/errors tests/conftest.py`
- Import smoke for `aeat`, `aeat.domain.sync`, `aeat.application.sync`, `aeat.application.review`, `aeat.application.filing`, `aeat.domain.submission`, `aeat.adapters.outbound.aeat.export`, `aeat.adapters.inbound.declaracion`, `aeat.adapters.inbound.schema`, and `aeat.entrypoints.cli`
- `git diff --check`
- Fast scans for root `src/aeat` file layout, application sync private-file removal, duplicate domain class names, and no active Python shim/fake/mock/stub vocabulary hits.
