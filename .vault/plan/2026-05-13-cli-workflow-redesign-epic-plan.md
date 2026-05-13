---
tags:
  - '#plan'
  - '#cli-workflow-redesign'
date: '2026-05-13'
tier: L4
related:
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-08-cli-backend-boundary-adr]]'
  - '[[2026-04-24-aeat-cli-wireframe-adr]]'
  - '[[2026-05-02-aeat-cli-redesign-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]'
  - '[[2026-05-07-user-profile-backend-schema-adr]]'
  - '[[2026-05-07-config-cli-profile-surface-adr]]'
  - '[[2026-05-12-aeat-cli-config-vs-setup-namespace-adr]]'
  - '[[2026-05-10-eliminate-user-cli-shim]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]'
  - '[[2026-04-21-auth-cli-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-config-doctor-shape-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-profile-output-language-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-04-30-inventory-management-cli-design-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-inventory-placement-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-actor-attribution-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-app-modelo-discard-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-live-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `cli-workflow-redesign` `epic` plan

## Epic intent

Implement GitHub milestone `CLI workflow redesign epic` milestone #12 as the complete apex ADR implementation for the CLI workflow redesign. The strategic goal is a coherent tax workflow CLI rooted only at `aeat config` and `aeat app`, with backend/application/domain behavior implemented before command exposure and no business logic in the CLI layer. The timeline horizon is the full milestone implementation cycle from foundation waves through final apex conformance, and the participating teams are coordinated coding agents working in shared worktrees without pull-request gates. Epic completion requires every Step row closed in this plan and milestone #12 closed in GitHub.

## Wave `W01` - apex cli workflow redesign

This Wave implements the `2026-05-12-cli-workflow-redesign-adr` decision for apex root and lifecycle contract. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W01.P001` - backend implementation

This Phase delivers backend implementation for apex root and lifecycle contract as required by `2026-05-12-cli-workflow-redesign-adr`.

- [x] `W01.P001.S0001` - Map the `2026-05-12-cli-workflow-redesign-adr` decision into non-CLI service ownership for apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P001.S0002` - Implement Pydantic command and result contracts for apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P001.S0003` - Wire application or domain services required by apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P001.S0004` - Connect persistence, bucket events, registry data, or provider adapters required by apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P001.S0005` - Route existing backend functionality into the canonical service for apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P001.S0006` - Record service-level error codes and log fields for apex root and lifecycle contract; `src/aeat/application`.

### Phase `W01.P002` - shadow duplicate removal

This Phase delivers shadow duplicate removal for apex root and lifecycle contract as required by `2026-05-12-cli-workflow-redesign-adr`.

- [x] `W01.P002.S0007` - Audit duplicate implementations that overlap apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P002.S0008` - Delete duplicate backend branches that compete with apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P002.S0009` - Remove stale aliases that bypass the canonical service for apex root and lifecycle contract; `src/aeat/entrypoints/cli`.
- [x] `W01.P002.S0010` - Migrate internal callers to the canonical service for apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P002.S0011` - Remove stale fixtures and tests that encode duplicate behavior for apex root and lifecycle contract; `tests/application`.
- [x] `W01.P002.S0012` - Update boundary inventory entries that describe duplicate behavior for apex root and lifecycle contract; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W01.P003` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for apex root and lifecycle contract as required by `2026-05-12-cli-workflow-redesign-adr`.

- [ ] `W01.P003.S0013` - Delete compatibility shims that preserve rejected behavior for apex root and lifecycle contract; `src/aeat/application`.
- [ ] `W01.P003.S0014` - Delete placeholder stubs that claim support for apex root and lifecycle contract; `src/aeat/application`.
- [ ] `W01.P003.S0015` - Replace stubbed paths with real backend service calls for apex root and lifecycle contract; `src/aeat/application`.
- [x] `W01.P003.S0016` - Remove deprecated command spelling and help text for apex root and lifecycle contract; `src/aeat/entrypoints/cli`.
- [x] `W01.P003.S0017` - Remove tests that assert shim or stub behavior for apex root and lifecycle contract; `tests/application`.
- [x] `W01.P003.S0018` - Record the removed shim and stub surfaces for apex root and lifecycle contract; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W01.P004` - real behavior verification

This Phase delivers real behavior verification for apex root and lifecycle contract as required by `2026-05-12-cli-workflow-redesign-adr`.

- [x] `W01.P004.S0019` - Add service contract tests for apex root and lifecycle contract; `tests/application`.
- [x] `W01.P004.S0020` - Add persistence or registry integration tests for apex root and lifecycle contract; `tests/application`.
- [x] `W01.P004.S0021` - Add negative tests proving rejected aliases do not reach apex root and lifecycle contract; `tests/entrypoints/cli`.
- [x] `W01.P004.S0022` - Add command behavior tests that exercise apex root and lifecycle contract through real services; `tests/entrypoints/cli`.
- [x] `W01.P004.S0023` - Add end-to-end workflow coverage for apex root and lifecycle contract; `tests`.
- [x] `W01.P004.S0024` - Run the targeted test slice for apex root and lifecycle contract without skips or xfails; `tests/application`.

### Phase `W01.P005` - thin cli exposure

This Phase delivers thin cli exposure for apex root and lifecycle contract as required by `2026-05-12-cli-workflow-redesign-adr`.

- [x] `W01.P005.S0025` - Expose accepted command handlers for apex root and lifecycle contract under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W01.P005.S0026` - Keep argument parsing for apex root and lifecycle contract separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W01.P005.S0027` - Delegate apex root and lifecycle contract execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W01.P005.S0028` - Render apex root and lifecycle contract results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W01.P005.S0029` - Handle apex root and lifecycle contract failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W01.P005.S0030` - Validate help text for apex root and lifecycle contract uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W60` - profile output language

This Wave implements the `2026-05-13-cli-workflow-redesign-profile-output-language-adr` decision for profile-owned output language. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services. This Wave is physically placed after W01 so the next execution pass handles profile language before continuing to the broader backlog.

### Phase `W60.P296` - backend implementation

This Phase delivers backend implementation for profile-owned output language as required by `2026-05-13-cli-workflow-redesign-profile-output-language-adr`.

- [x] `W60.P296.S1771` - Map the `2026-05-13-cli-workflow-redesign-profile-output-language-adr` decision into non-CLI service ownership for profile-owned output language; `src/aeat/core/i18n`, `src/aeat/core/errors`, `src/aeat/application/wizard`, `src/aeat/domain/profile`.
- [x] `W60.P296.S1772` - Implement Pydantic command and result contracts for profile-owned output language; `src/aeat/application/wizard`, `src/aeat/domain/profile`.
- [x] `W60.P296.S1773` - Wire application or domain services required by profile-owned output language; `src/aeat/application/wizard`, `src/aeat/application/profile`.
- [x] `W60.P296.S1774` - Connect persistence, bucket events, registry data, or provider adapters required by profile-owned output language; `src/aeat/application/workflow`, `src/aeat/application/profile`.
- [x] `W60.P296.S1775` - Route existing backend functionality into the canonical service for profile-owned output language; `src/aeat/core/i18n`, `src/aeat/core/errors`.
- [x] `W60.P296.S1776` - Record service-level error codes and log fields for profile-owned output language; `src/aeat/core/errors/registry`, `src/aeat/application/profile`.

### Phase `W60.P297` - shadow duplicate removal

This Phase delivers shadow duplicate removal for profile-owned output language as required by `2026-05-13-cli-workflow-redesign-profile-output-language-adr`.

- [x] `W60.P297.S1777` - Audit duplicate implementations that overlap profile-owned output language; `src/aeat/core/i18n`, `src/aeat/core/errors`, `src/aeat/entrypoints/cli`.
- [x] `W60.P297.S1778` - Delete duplicate backend branches that compete with profile-owned output language; `src/aeat/core/i18n`, `src/aeat/core/errors`.
- [x] `W60.P297.S1779` - Remove stale aliases that bypass the canonical service for profile-owned output language; `src/aeat/entrypoints/cli`.
- [x] `W60.P297.S1780` - Migrate internal callers to the canonical service for profile-owned output language; `src/aeat/core`, `src/aeat/application`, `src/aeat/entrypoints/cli`.
- [x] `W60.P297.S1781` - Remove stale fixtures and tests that encode duplicate behavior for profile-owned output language; `tests`, `src/aeat/**/test_*.py`.
- [x] `W60.P297.S1782` - Update boundary inventory entries that describe duplicate behavior for profile-owned output language; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W60.P298` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for profile-owned output language as required by `2026-05-13-cli-workflow-redesign-profile-output-language-adr`.

- [x] `W60.P298.S1783` - Delete compatibility shims that preserve rejected behavior for profile-owned output language; `src/aeat/core/i18n`, `src/aeat/core/errors`, `src/aeat/entrypoints/cli`.
- [x] `W60.P298.S1784` - Delete placeholder stubs that claim support for profile-owned output language; `src/aeat/application/wizard`, `src/aeat/domain/profile`.
- [x] `W60.P298.S1785` - Replace stubbed paths with real backend service calls for profile-owned output language; `src/aeat/core/i18n`, `src/aeat/core/errors`.
- [x] `W60.P298.S1786` - Remove deprecated command spelling and help text for profile-owned output language; `src/aeat/entrypoints/cli`, `src/aeat/locales`.
- [x] `W60.P298.S1787` - Remove tests that assert shim or stub behavior for profile-owned output language; `tests`, `src/aeat/**/test_*.py`.
- [x] `W60.P298.S1788` - Record the removed shim and stub surfaces for profile-owned output language; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W60.P299` - real behavior verification

This Phase delivers real behavior verification for profile-owned output language as required by `2026-05-13-cli-workflow-redesign-profile-output-language-adr`.

- [x] `W60.P299.S1789` - Add service contract tests for profile-owned output language; `tests/application`, `src/aeat/core/i18n`.
- [x] `W60.P299.S1790` - Add persistence or registry integration tests for profile-owned output language; `tests/application`, `src/aeat/application/wizard`.
- [x] `W60.P299.S1791` - Add negative tests proving rejected aliases do not reach profile-owned output language; `tests/entrypoints/cli`.
- [x] `W60.P299.S1792` - Add command behavior tests that exercise profile-owned output language through real services; `tests/entrypoints/cli`.
- [x] `W60.P299.S1793` - Add end-to-end workflow coverage for profile-owned output language; `tests`.
- [x] `W60.P299.S1794` - Run the targeted test slice for profile-owned output language without skips or xfails; `tests/application`, `tests/entrypoints/cli`.

### Phase `W60.P300` - thin cli exposure

This Phase delivers thin cli exposure for profile-owned output language as required by `2026-05-13-cli-workflow-redesign-profile-output-language-adr`.

- [x] `W60.P300.S1795` - Expose accepted command handlers for profile-owned output language under `aeat config`; `src/aeat/entrypoints/cli`.
- [x] `W60.P300.S1796` - Keep argument parsing for profile-owned output language separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W60.P300.S1797` - Delegate profile-owned output language execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W60.P300.S1798` - Render profile-owned output language results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W60.P300.S1799` - Handle profile-owned output language failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W60.P300.S1800` - Validate help text for profile-owned output language uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W02` - cli backend boundary

This Wave implements the `2026-05-08-cli-backend-boundary-adr` decision for central backend boundary enforcement. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W02.P006` - backend implementation

This Phase delivers backend implementation for central backend boundary enforcement as required by `2026-05-08-cli-backend-boundary-adr`.

- [x] `W02.P006.S0031` - Map the `2026-05-08-cli-backend-boundary-adr` decision into non-CLI service ownership for central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P006.S0032` - Implement Pydantic command and result contracts for central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P006.S0033` - Wire application or domain services required by central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P006.S0034` - Connect persistence, bucket events, registry data, or provider adapters required by central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P006.S0035` - Route existing backend functionality into the canonical service for central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P006.S0036` - Record service-level error codes and log fields for central backend boundary enforcement; `src/aeat/application`.

### Phase `W02.P007` - shadow duplicate removal

This Phase delivers shadow duplicate removal for central backend boundary enforcement as required by `2026-05-08-cli-backend-boundary-adr`.

- [x] `W02.P007.S0037` - Audit duplicate implementations that overlap central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P007.S0038` - Delete duplicate backend branches that compete with central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P007.S0039` - Remove stale aliases that bypass the canonical service for central backend boundary enforcement; `src/aeat/entrypoints/cli`.
- [x] `W02.P007.S0040` - Migrate internal callers to the canonical service for central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P007.S0041` - Remove stale fixtures and tests that encode duplicate behavior for central backend boundary enforcement; `tests/entrypoints/cli`.
- [x] `W02.P007.S0042` - Update boundary inventory entries that describe duplicate behavior for central backend boundary enforcement; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W02.P008` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for central backend boundary enforcement as required by `2026-05-08-cli-backend-boundary-adr`.

- [x] `W02.P008.S0043` - Delete compatibility shims that preserve rejected behavior for central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P008.S0044` - Delete placeholder stubs that claim support for central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P008.S0045` - Replace stubbed paths with real backend service calls for central backend boundary enforcement; `src/aeat/application`.
- [x] `W02.P008.S0046` - Remove deprecated command spelling and help text for central backend boundary enforcement; `src/aeat/entrypoints/cli`.
- [x] `W02.P008.S0047` - Remove tests that assert shim or stub behavior for central backend boundary enforcement; `tests/entrypoints/cli`.
- [x] `W02.P008.S0048` - Record the removed shim and stub surfaces for central backend boundary enforcement; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W02.P009` - real behavior verification

This Phase delivers real behavior verification for central backend boundary enforcement as required by `2026-05-08-cli-backend-boundary-adr`.

- [x] `W02.P009.S0049` - Add service contract tests for central backend boundary enforcement; `tests/entrypoints/cli`.
- [x] `W02.P009.S0050` - Add persistence or registry integration tests for central backend boundary enforcement; `tests/entrypoints/cli`.
- [x] `W02.P009.S0051` - Add negative tests proving rejected aliases do not reach central backend boundary enforcement; `tests/entrypoints/cli`.
- [x] `W02.P009.S0052` - Add command behavior tests that exercise central backend boundary enforcement through real services; `tests/entrypoints/cli`.
- [x] `W02.P009.S0053` - Add end-to-end workflow coverage for central backend boundary enforcement; `tests`.
- [x] `W02.P009.S0054` - Run the targeted test slice for central backend boundary enforcement without skips or xfails; `tests/entrypoints/cli`.

### Phase `W02.P010` - thin cli exposure

This Phase delivers thin cli exposure for central backend boundary enforcement as required by `2026-05-08-cli-backend-boundary-adr`.

- [x] `W02.P010.S0055` - Expose accepted command handlers for central backend boundary enforcement under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W02.P010.S0056` - Keep argument parsing for central backend boundary enforcement separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W02.P010.S0057` - Delegate central backend boundary enforcement execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W02.P010.S0058` - Render central backend boundary enforcement results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W02.P010.S0059` - Handle central backend boundary enforcement failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W02.P010.S0060` - Validate help text for central backend boundary enforcement uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W03` - aeat cli wireframe

This Wave implements the `2026-04-24-aeat-cli-wireframe-adr` decision for operator command journey wireframe. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W03.P011` - backend implementation

This Phase delivers backend implementation for operator command journey wireframe as required by `2026-04-24-aeat-cli-wireframe-adr`.

- [ ] `W03.P011.S0061` - Map the `2026-04-24-aeat-cli-wireframe-adr` decision into non-CLI service ownership for operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P011.S0062` - Implement Pydantic command and result contracts for operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P011.S0063` - Wire application or domain services required by operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P011.S0064` - Connect persistence, bucket events, registry data, or provider adapters required by operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P011.S0065` - Route existing backend functionality into the canonical service for operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P011.S0066` - Record service-level error codes and log fields for operator command journey wireframe; `src/aeat/application`.

### Phase `W03.P012` - shadow duplicate removal

This Phase delivers shadow duplicate removal for operator command journey wireframe as required by `2026-04-24-aeat-cli-wireframe-adr`.

- [ ] `W03.P012.S0067` - Audit duplicate implementations that overlap operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P012.S0068` - Delete duplicate backend branches that compete with operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P012.S0069` - Remove stale aliases that bypass the canonical service for operator command journey wireframe; `src/aeat/entrypoints/cli`.
- [ ] `W03.P012.S0070` - Migrate internal callers to the canonical service for operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P012.S0071` - Remove stale fixtures and tests that encode duplicate behavior for operator command journey wireframe; `tests/entrypoints/cli`.
- [ ] `W03.P012.S0072` - Update boundary inventory entries that describe duplicate behavior for operator command journey wireframe; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W03.P013` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for operator command journey wireframe as required by `2026-04-24-aeat-cli-wireframe-adr`.

- [ ] `W03.P013.S0073` - Delete compatibility shims that preserve rejected behavior for operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P013.S0074` - Delete placeholder stubs that claim support for operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P013.S0075` - Replace stubbed paths with real backend service calls for operator command journey wireframe; `src/aeat/application`.
- [ ] `W03.P013.S0076` - Remove deprecated command spelling and help text for operator command journey wireframe; `src/aeat/entrypoints/cli`.
- [ ] `W03.P013.S0077` - Remove tests that assert shim or stub behavior for operator command journey wireframe; `tests/entrypoints/cli`.
- [ ] `W03.P013.S0078` - Record the removed shim and stub surfaces for operator command journey wireframe; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W03.P014` - real behavior verification

This Phase delivers real behavior verification for operator command journey wireframe as required by `2026-04-24-aeat-cli-wireframe-adr`.

- [ ] `W03.P014.S0079` - Add service contract tests for operator command journey wireframe; `tests/entrypoints/cli`.
- [ ] `W03.P014.S0080` - Add persistence or registry integration tests for operator command journey wireframe; `tests/entrypoints/cli`.
- [ ] `W03.P014.S0081` - Add negative tests proving rejected aliases do not reach operator command journey wireframe; `tests/entrypoints/cli`.
- [ ] `W03.P014.S0082` - Add command behavior tests that exercise operator command journey wireframe through real services; `tests/entrypoints/cli`.
- [ ] `W03.P014.S0083` - Add end-to-end workflow coverage for operator command journey wireframe; `tests`.
- [ ] `W03.P014.S0084` - Run the targeted test slice for operator command journey wireframe without skips or xfails; `tests/entrypoints/cli`.

### Phase `W03.P015` - thin cli exposure

This Phase delivers thin cli exposure for operator command journey wireframe as required by `2026-04-24-aeat-cli-wireframe-adr`.

- [ ] `W03.P015.S0085` - Expose accepted command handlers for operator command journey wireframe under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W03.P015.S0086` - Keep argument parsing for operator command journey wireframe separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W03.P015.S0087` - Delegate operator command journey wireframe execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W03.P015.S0088` - Render operator command journey wireframe results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W03.P015.S0089` - Handle operator command journey wireframe failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W03.P015.S0090` - Validate help text for operator command journey wireframe uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W04` - aeat cli redesign

This Wave implements the `2026-05-02-aeat-cli-redesign-adr` decision for historical cli redesign consolidation. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W04.P016` - backend implementation

This Phase delivers backend implementation for historical cli redesign consolidation as required by `2026-05-02-aeat-cli-redesign-adr`.

- [ ] `W04.P016.S0091` - Map the `2026-05-02-aeat-cli-redesign-adr` decision into non-CLI service ownership for historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P016.S0092` - Implement Pydantic command and result contracts for historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P016.S0093` - Wire application or domain services required by historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P016.S0094` - Connect persistence, bucket events, registry data, or provider adapters required by historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P016.S0095` - Route existing backend functionality into the canonical service for historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P016.S0096` - Record service-level error codes and log fields for historical cli redesign consolidation; `src/aeat/application`.

### Phase `W04.P017` - shadow duplicate removal

This Phase delivers shadow duplicate removal for historical cli redesign consolidation as required by `2026-05-02-aeat-cli-redesign-adr`.

- [ ] `W04.P017.S0097` - Audit duplicate implementations that overlap historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P017.S0098` - Delete duplicate backend branches that compete with historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P017.S0099` - Remove stale aliases that bypass the canonical service for historical cli redesign consolidation; `src/aeat/entrypoints/cli`.
- [ ] `W04.P017.S0100` - Migrate internal callers to the canonical service for historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P017.S0101` - Remove stale fixtures and tests that encode duplicate behavior for historical cli redesign consolidation; `tests/entrypoints/cli`.
- [ ] `W04.P017.S0102` - Update boundary inventory entries that describe duplicate behavior for historical cli redesign consolidation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W04.P018` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for historical cli redesign consolidation as required by `2026-05-02-aeat-cli-redesign-adr`.

- [ ] `W04.P018.S0103` - Delete compatibility shims that preserve rejected behavior for historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P018.S0104` - Delete placeholder stubs that claim support for historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P018.S0105` - Replace stubbed paths with real backend service calls for historical cli redesign consolidation; `src/aeat/application`.
- [ ] `W04.P018.S0106` - Remove deprecated command spelling and help text for historical cli redesign consolidation; `src/aeat/entrypoints/cli`.
- [ ] `W04.P018.S0107` - Remove tests that assert shim or stub behavior for historical cli redesign consolidation; `tests/entrypoints/cli`.
- [ ] `W04.P018.S0108` - Record the removed shim and stub surfaces for historical cli redesign consolidation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W04.P019` - real behavior verification

This Phase delivers real behavior verification for historical cli redesign consolidation as required by `2026-05-02-aeat-cli-redesign-adr`.

- [ ] `W04.P019.S0109` - Add service contract tests for historical cli redesign consolidation; `tests/entrypoints/cli`.
- [ ] `W04.P019.S0110` - Add persistence or registry integration tests for historical cli redesign consolidation; `tests/entrypoints/cli`.
- [ ] `W04.P019.S0111` - Add negative tests proving rejected aliases do not reach historical cli redesign consolidation; `tests/entrypoints/cli`.
- [ ] `W04.P019.S0112` - Add command behavior tests that exercise historical cli redesign consolidation through real services; `tests/entrypoints/cli`.
- [ ] `W04.P019.S0113` - Add end-to-end workflow coverage for historical cli redesign consolidation; `tests`.
- [ ] `W04.P019.S0114` - Run the targeted test slice for historical cli redesign consolidation without skips or xfails; `tests/entrypoints/cli`.

### Phase `W04.P020` - thin cli exposure

This Phase delivers thin cli exposure for historical cli redesign consolidation as required by `2026-05-02-aeat-cli-redesign-adr`.

- [ ] `W04.P020.S0115` - Expose accepted command handlers for historical cli redesign consolidation under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W04.P020.S0116` - Keep argument parsing for historical cli redesign consolidation separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W04.P020.S0117` - Delegate historical cli redesign consolidation execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W04.P020.S0118` - Render historical cli redesign consolidation results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W04.P020.S0119` - Handle historical cli redesign consolidation failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W04.P020.S0120` - Validate help text for historical cli redesign consolidation uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W05` - root help shape

This Wave implements the `2026-05-13-cli-workflow-redesign-root-help-shape-adr` decision for root help and discovery behavior. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W05.P021` - backend implementation

This Phase delivers backend implementation for root help and discovery behavior as required by `2026-05-13-cli-workflow-redesign-root-help-shape-adr`.

- [ ] `W05.P021.S0121` - Map the `2026-05-13-cli-workflow-redesign-root-help-shape-adr` decision into non-CLI service ownership for root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P021.S0122` - Implement Pydantic command and result contracts for root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P021.S0123` - Wire application or domain services required by root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P021.S0124` - Connect persistence, bucket events, registry data, or provider adapters required by root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P021.S0125` - Route existing backend functionality into the canonical service for root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P021.S0126` - Record service-level error codes and log fields for root help and discovery behavior; `src/aeat/application`.

### Phase `W05.P022` - shadow duplicate removal

This Phase delivers shadow duplicate removal for root help and discovery behavior as required by `2026-05-13-cli-workflow-redesign-root-help-shape-adr`.

- [ ] `W05.P022.S0127` - Audit duplicate implementations that overlap root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P022.S0128` - Delete duplicate backend branches that compete with root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P022.S0129` - Remove stale aliases that bypass the canonical service for root help and discovery behavior; `src/aeat/entrypoints/cli`.
- [ ] `W05.P022.S0130` - Migrate internal callers to the canonical service for root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P022.S0131` - Remove stale fixtures and tests that encode duplicate behavior for root help and discovery behavior; `tests/entrypoints/cli`.
- [ ] `W05.P022.S0132` - Update boundary inventory entries that describe duplicate behavior for root help and discovery behavior; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W05.P023` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for root help and discovery behavior as required by `2026-05-13-cli-workflow-redesign-root-help-shape-adr`.

- [ ] `W05.P023.S0133` - Delete compatibility shims that preserve rejected behavior for root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P023.S0134` - Delete placeholder stubs that claim support for root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P023.S0135` - Replace stubbed paths with real backend service calls for root help and discovery behavior; `src/aeat/application`.
- [ ] `W05.P023.S0136` - Remove deprecated command spelling and help text for root help and discovery behavior; `src/aeat/entrypoints/cli`.
- [ ] `W05.P023.S0137` - Remove tests that assert shim or stub behavior for root help and discovery behavior; `tests/entrypoints/cli`.
- [ ] `W05.P023.S0138` - Record the removed shim and stub surfaces for root help and discovery behavior; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W05.P024` - real behavior verification

This Phase delivers real behavior verification for root help and discovery behavior as required by `2026-05-13-cli-workflow-redesign-root-help-shape-adr`.

- [ ] `W05.P024.S0139` - Add service contract tests for root help and discovery behavior; `tests/entrypoints/cli`.
- [ ] `W05.P024.S0140` - Add persistence or registry integration tests for root help and discovery behavior; `tests/entrypoints/cli`.
- [ ] `W05.P024.S0141` - Add negative tests proving rejected aliases do not reach root help and discovery behavior; `tests/entrypoints/cli`.
- [ ] `W05.P024.S0142` - Add command behavior tests that exercise root help and discovery behavior through real services; `tests/entrypoints/cli`.
- [ ] `W05.P024.S0143` - Add end-to-end workflow coverage for root help and discovery behavior; `tests`.
- [ ] `W05.P024.S0144` - Run the targeted test slice for root help and discovery behavior without skips or xfails; `tests/entrypoints/cli`.

### Phase `W05.P025` - thin cli exposure

This Phase delivers thin cli exposure for root help and discovery behavior as required by `2026-05-13-cli-workflow-redesign-root-help-shape-adr`.

- [ ] `W05.P025.S0145` - Expose accepted command handlers for root help and discovery behavior under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W05.P025.S0146` - Keep argument parsing for root help and discovery behavior separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W05.P025.S0147` - Delegate root help and discovery behavior execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W05.P025.S0148` - Render root help and discovery behavior results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W05.P025.S0149` - Handle root help and discovery behavior failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W05.P025.S0150` - Validate help text for root help and discovery behavior uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W06` - output rendering normalization

This Wave implements the `2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr` decision for central output rendering. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W06.P026` - backend implementation

This Phase delivers backend implementation for central output rendering as required by `2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr`.

- [ ] `W06.P026.S0151` - Map the `2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr` decision into non-CLI service ownership for central output rendering; `src/aeat/core`.
- [ ] `W06.P026.S0152` - Implement Pydantic command and result contracts for central output rendering; `src/aeat/core`.
- [ ] `W06.P026.S0153` - Wire application or domain services required by central output rendering; `src/aeat/core`.
- [ ] `W06.P026.S0154` - Connect persistence, bucket events, registry data, or provider adapters required by central output rendering; `src/aeat/core`.
- [ ] `W06.P026.S0155` - Route existing backend functionality into the canonical service for central output rendering; `src/aeat/core`.
- [ ] `W06.P026.S0156` - Record service-level error codes and log fields for central output rendering; `src/aeat/core`.

### Phase `W06.P027` - shadow duplicate removal

This Phase delivers shadow duplicate removal for central output rendering as required by `2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr`.

- [ ] `W06.P027.S0157` - Audit duplicate implementations that overlap central output rendering; `src/aeat/core`.
- [ ] `W06.P027.S0158` - Delete duplicate backend branches that compete with central output rendering; `src/aeat/core`.
- [ ] `W06.P027.S0159` - Remove stale aliases that bypass the canonical service for central output rendering; `src/aeat/entrypoints/cli`.
- [ ] `W06.P027.S0160` - Migrate internal callers to the canonical service for central output rendering; `src/aeat/core`.
- [ ] `W06.P027.S0161` - Remove stale fixtures and tests that encode duplicate behavior for central output rendering; `tests/entrypoints/cli`.
- [ ] `W06.P027.S0162` - Update boundary inventory entries that describe duplicate behavior for central output rendering; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W06.P028` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for central output rendering as required by `2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr`.

- [ ] `W06.P028.S0163` - Delete compatibility shims that preserve rejected behavior for central output rendering; `src/aeat/core`.
- [ ] `W06.P028.S0164` - Delete placeholder stubs that claim support for central output rendering; `src/aeat/core`.
- [ ] `W06.P028.S0165` - Replace stubbed paths with real backend service calls for central output rendering; `src/aeat/core`.
- [ ] `W06.P028.S0166` - Remove deprecated command spelling and help text for central output rendering; `src/aeat/entrypoints/cli`.
- [ ] `W06.P028.S0167` - Remove tests that assert shim or stub behavior for central output rendering; `tests/entrypoints/cli`.
- [ ] `W06.P028.S0168` - Record the removed shim and stub surfaces for central output rendering; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W06.P029` - real behavior verification

This Phase delivers real behavior verification for central output rendering as required by `2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr`.

- [ ] `W06.P029.S0169` - Add service contract tests for central output rendering; `tests/entrypoints/cli`.
- [ ] `W06.P029.S0170` - Add persistence or registry integration tests for central output rendering; `tests/entrypoints/cli`.
- [ ] `W06.P029.S0171` - Add negative tests proving rejected aliases do not reach central output rendering; `tests/entrypoints/cli`.
- [ ] `W06.P029.S0172` - Add command behavior tests that exercise central output rendering through real services; `tests/entrypoints/cli`.
- [ ] `W06.P029.S0173` - Add end-to-end workflow coverage for central output rendering; `tests`.
- [ ] `W06.P029.S0174` - Run the targeted test slice for central output rendering without skips or xfails; `tests/entrypoints/cli`.

### Phase `W06.P030` - thin cli exposure

This Phase delivers thin cli exposure for central output rendering as required by `2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr`.

- [ ] `W06.P030.S0175` - Expose accepted command handlers for central output rendering under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W06.P030.S0176` - Keep argument parsing for central output rendering separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W06.P030.S0177` - Delegate central output rendering execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W06.P030.S0178` - Render central output rendering results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W06.P030.S0179` - Handle central output rendering failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W06.P030.S0180` - Validate help text for central output rendering uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W07` - observability wrapping decision

This Wave implements the `2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr` decision for central logging and error observability. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W07.P031` - backend implementation

This Phase delivers backend implementation for central logging and error observability as required by `2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr`.

- [ ] `W07.P031.S0181` - Map the `2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr` decision into non-CLI service ownership for central logging and error observability; `src/aeat/core`.
- [ ] `W07.P031.S0182` - Implement Pydantic command and result contracts for central logging and error observability; `src/aeat/core`.
- [ ] `W07.P031.S0183` - Wire application or domain services required by central logging and error observability; `src/aeat/core`.
- [ ] `W07.P031.S0184` - Connect persistence, bucket events, registry data, or provider adapters required by central logging and error observability; `src/aeat/core`.
- [ ] `W07.P031.S0185` - Route existing backend functionality into the canonical service for central logging and error observability; `src/aeat/core`.
- [ ] `W07.P031.S0186` - Record service-level error codes and log fields for central logging and error observability; `src/aeat/core`.

### Phase `W07.P032` - shadow duplicate removal

This Phase delivers shadow duplicate removal for central logging and error observability as required by `2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr`.

- [ ] `W07.P032.S0187` - Audit duplicate implementations that overlap central logging and error observability; `src/aeat/core`.
- [ ] `W07.P032.S0188` - Delete duplicate backend branches that compete with central logging and error observability; `src/aeat/core`.
- [ ] `W07.P032.S0189` - Remove stale aliases that bypass the canonical service for central logging and error observability; `src/aeat/entrypoints/cli`.
- [ ] `W07.P032.S0190` - Migrate internal callers to the canonical service for central logging and error observability; `src/aeat/core`.
- [ ] `W07.P032.S0191` - Remove stale fixtures and tests that encode duplicate behavior for central logging and error observability; `tests/entrypoints/cli`.
- [ ] `W07.P032.S0192` - Update boundary inventory entries that describe duplicate behavior for central logging and error observability; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W07.P033` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for central logging and error observability as required by `2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr`.

- [ ] `W07.P033.S0193` - Delete compatibility shims that preserve rejected behavior for central logging and error observability; `src/aeat/core`.
- [ ] `W07.P033.S0194` - Delete placeholder stubs that claim support for central logging and error observability; `src/aeat/core`.
- [ ] `W07.P033.S0195` - Replace stubbed paths with real backend service calls for central logging and error observability; `src/aeat/core`.
- [ ] `W07.P033.S0196` - Remove deprecated command spelling and help text for central logging and error observability; `src/aeat/entrypoints/cli`.
- [ ] `W07.P033.S0197` - Remove tests that assert shim or stub behavior for central logging and error observability; `tests/entrypoints/cli`.
- [ ] `W07.P033.S0198` - Record the removed shim and stub surfaces for central logging and error observability; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W07.P034` - real behavior verification

This Phase delivers real behavior verification for central logging and error observability as required by `2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr`.

- [ ] `W07.P034.S0199` - Add service contract tests for central logging and error observability; `tests/entrypoints/cli`.
- [ ] `W07.P034.S0200` - Add persistence or registry integration tests for central logging and error observability; `tests/entrypoints/cli`.
- [ ] `W07.P034.S0201` - Add negative tests proving rejected aliases do not reach central logging and error observability; `tests/entrypoints/cli`.
- [ ] `W07.P034.S0202` - Add command behavior tests that exercise central logging and error observability through real services; `tests/entrypoints/cli`.
- [ ] `W07.P034.S0203` - Add end-to-end workflow coverage for central logging and error observability; `tests`.
- [ ] `W07.P034.S0204` - Run the targeted test slice for central logging and error observability without skips or xfails; `tests/entrypoints/cli`.

### Phase `W07.P035` - thin cli exposure

This Phase delivers thin cli exposure for central logging and error observability as required by `2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr`.

- [ ] `W07.P035.S0205` - Expose accepted command handlers for central logging and error observability under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W07.P035.S0206` - Keep argument parsing for central logging and error observability separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W07.P035.S0207` - Delegate central logging and error observability execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W07.P035.S0208` - Render central logging and error observability results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W07.P035.S0209` - Handle central logging and error observability failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W07.P035.S0210` - Validate help text for central logging and error observability uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W08` - profile read path retirement

This Wave implements the `2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr` decision for workflow state profile read path. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W08.P036` - backend implementation

This Phase delivers backend implementation for workflow state profile read path as required by `2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr`.

- [ ] `W08.P036.S0211` - Map the `2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr` decision into non-CLI service ownership for workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P036.S0212` - Implement Pydantic command and result contracts for workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P036.S0213` - Wire application or domain services required by workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P036.S0214` - Connect persistence, bucket events, registry data, or provider adapters required by workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P036.S0215` - Route existing backend functionality into the canonical service for workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P036.S0216` - Record service-level error codes and log fields for workflow state profile read path; `src/aeat/application/workflow`.

### Phase `W08.P037` - shadow duplicate removal

This Phase delivers shadow duplicate removal for workflow state profile read path as required by `2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr`.

- [ ] `W08.P037.S0217` - Audit duplicate implementations that overlap workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P037.S0218` - Delete duplicate backend branches that compete with workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P037.S0219` - Remove stale aliases that bypass the canonical service for workflow state profile read path; `src/aeat/entrypoints/cli`.
- [ ] `W08.P037.S0220` - Migrate internal callers to the canonical service for workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P037.S0221` - Remove stale fixtures and tests that encode duplicate behavior for workflow state profile read path; `tests/application/workflow`.
- [ ] `W08.P037.S0222` - Update boundary inventory entries that describe duplicate behavior for workflow state profile read path; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W08.P038` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for workflow state profile read path as required by `2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr`.

- [ ] `W08.P038.S0223` - Delete compatibility shims that preserve rejected behavior for workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P038.S0224` - Delete placeholder stubs that claim support for workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P038.S0225` - Replace stubbed paths with real backend service calls for workflow state profile read path; `src/aeat/application/workflow`.
- [ ] `W08.P038.S0226` - Remove deprecated command spelling and help text for workflow state profile read path; `src/aeat/entrypoints/cli`.
- [ ] `W08.P038.S0227` - Remove tests that assert shim or stub behavior for workflow state profile read path; `tests/application/workflow`.
- [ ] `W08.P038.S0228` - Record the removed shim and stub surfaces for workflow state profile read path; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W08.P039` - real behavior verification

This Phase delivers real behavior verification for workflow state profile read path as required by `2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr`.

- [ ] `W08.P039.S0229` - Add service contract tests for workflow state profile read path; `tests/application/workflow`.
- [ ] `W08.P039.S0230` - Add persistence or registry integration tests for workflow state profile read path; `tests/application/workflow`.
- [ ] `W08.P039.S0231` - Add negative tests proving rejected aliases do not reach workflow state profile read path; `tests/entrypoints/cli`.
- [ ] `W08.P039.S0232` - Add command behavior tests that exercise workflow state profile read path through real services; `tests/entrypoints/cli`.
- [ ] `W08.P039.S0233` - Add end-to-end workflow coverage for workflow state profile read path; `tests`.
- [ ] `W08.P039.S0234` - Run the targeted test slice for workflow state profile read path without skips or xfails; `tests/application/workflow`.

### Phase `W08.P040` - thin cli exposure

This Phase delivers thin cli exposure for workflow state profile read path as required by `2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr`.

- [ ] `W08.P040.S0235` - Expose accepted command handlers for workflow state profile read path under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W08.P040.S0236` - Keep argument parsing for workflow state profile read path separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W08.P040.S0237` - Delegate workflow state profile read path execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W08.P040.S0238` - Render workflow state profile read path results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W08.P040.S0239` - Handle workflow state profile read path failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W08.P040.S0240` - Validate help text for workflow state profile read path uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W09` - user profile backend schema

This Wave implements the `2026-05-07-user-profile-backend-schema-adr` decision for profile backend schema. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W09.P041` - backend implementation

This Phase delivers backend implementation for profile backend schema as required by `2026-05-07-user-profile-backend-schema-adr`.

- [ ] `W09.P041.S0241` - Map the `2026-05-07-user-profile-backend-schema-adr` decision into non-CLI service ownership for profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P041.S0242` - Implement Pydantic command and result contracts for profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P041.S0243` - Wire application or domain services required by profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P041.S0244` - Connect persistence, bucket events, registry data, or provider adapters required by profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P041.S0245` - Route existing backend functionality into the canonical service for profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P041.S0246` - Record service-level error codes and log fields for profile backend schema; `src/aeat/application/profile`.

### Phase `W09.P042` - shadow duplicate removal

This Phase delivers shadow duplicate removal for profile backend schema as required by `2026-05-07-user-profile-backend-schema-adr`.

- [ ] `W09.P042.S0247` - Audit duplicate implementations that overlap profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P042.S0248` - Delete duplicate backend branches that compete with profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P042.S0249` - Remove stale aliases that bypass the canonical service for profile backend schema; `src/aeat/entrypoints/cli`.
- [ ] `W09.P042.S0250` - Migrate internal callers to the canonical service for profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P042.S0251` - Remove stale fixtures and tests that encode duplicate behavior for profile backend schema; `tests/application/profile`.
- [ ] `W09.P042.S0252` - Update boundary inventory entries that describe duplicate behavior for profile backend schema; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W09.P043` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for profile backend schema as required by `2026-05-07-user-profile-backend-schema-adr`.

- [ ] `W09.P043.S0253` - Delete compatibility shims that preserve rejected behavior for profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P043.S0254` - Delete placeholder stubs that claim support for profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P043.S0255` - Replace stubbed paths with real backend service calls for profile backend schema; `src/aeat/application/profile`.
- [ ] `W09.P043.S0256` - Remove deprecated command spelling and help text for profile backend schema; `src/aeat/entrypoints/cli`.
- [ ] `W09.P043.S0257` - Remove tests that assert shim or stub behavior for profile backend schema; `tests/application/profile`.
- [ ] `W09.P043.S0258` - Record the removed shim and stub surfaces for profile backend schema; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W09.P044` - real behavior verification

This Phase delivers real behavior verification for profile backend schema as required by `2026-05-07-user-profile-backend-schema-adr`.

- [ ] `W09.P044.S0259` - Add service contract tests for profile backend schema; `tests/application/profile`.
- [ ] `W09.P044.S0260` - Add persistence or registry integration tests for profile backend schema; `tests/application/profile`.
- [ ] `W09.P044.S0261` - Add negative tests proving rejected aliases do not reach profile backend schema; `tests/entrypoints/cli`.
- [ ] `W09.P044.S0262` - Add command behavior tests that exercise profile backend schema through real services; `tests/entrypoints/cli`.
- [ ] `W09.P044.S0263` - Add end-to-end workflow coverage for profile backend schema; `tests`.
- [ ] `W09.P044.S0264` - Run the targeted test slice for profile backend schema without skips or xfails; `tests/application/profile`.

### Phase `W09.P045` - thin cli exposure

This Phase delivers thin cli exposure for profile backend schema as required by `2026-05-07-user-profile-backend-schema-adr`.

- [ ] `W09.P045.S0265` - Expose accepted command handlers for profile backend schema under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W09.P045.S0266` - Keep argument parsing for profile backend schema separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W09.P045.S0267` - Delegate profile backend schema execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W09.P045.S0268` - Render profile backend schema results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W09.P045.S0269` - Handle profile backend schema failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W09.P045.S0270` - Validate help text for profile backend schema uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W10` - config profile surface

This Wave implements the `2026-05-07-config-cli-profile-surface-adr` decision for config profile service surface. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W10.P046` - backend implementation

This Phase delivers backend implementation for config profile service surface as required by `2026-05-07-config-cli-profile-surface-adr`.

- [ ] `W10.P046.S0271` - Map the `2026-05-07-config-cli-profile-surface-adr` decision into non-CLI service ownership for config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P046.S0272` - Implement Pydantic command and result contracts for config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P046.S0273` - Wire application or domain services required by config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P046.S0274` - Connect persistence, bucket events, registry data, or provider adapters required by config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P046.S0275` - Route existing backend functionality into the canonical service for config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P046.S0276` - Record service-level error codes and log fields for config profile service surface; `src/aeat/application/profile`.

### Phase `W10.P047` - shadow duplicate removal

This Phase delivers shadow duplicate removal for config profile service surface as required by `2026-05-07-config-cli-profile-surface-adr`.

- [ ] `W10.P047.S0277` - Audit duplicate implementations that overlap config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P047.S0278` - Delete duplicate backend branches that compete with config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P047.S0279` - Remove stale aliases that bypass the canonical service for config profile service surface; `src/aeat/entrypoints/cli`.
- [ ] `W10.P047.S0280` - Migrate internal callers to the canonical service for config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P047.S0281` - Remove stale fixtures and tests that encode duplicate behavior for config profile service surface; `tests/entrypoints/cli`.
- [ ] `W10.P047.S0282` - Update boundary inventory entries that describe duplicate behavior for config profile service surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W10.P048` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for config profile service surface as required by `2026-05-07-config-cli-profile-surface-adr`.

- [ ] `W10.P048.S0283` - Delete compatibility shims that preserve rejected behavior for config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P048.S0284` - Delete placeholder stubs that claim support for config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P048.S0285` - Replace stubbed paths with real backend service calls for config profile service surface; `src/aeat/application/profile`.
- [ ] `W10.P048.S0286` - Remove deprecated command spelling and help text for config profile service surface; `src/aeat/entrypoints/cli`.
- [ ] `W10.P048.S0287` - Remove tests that assert shim or stub behavior for config profile service surface; `tests/entrypoints/cli`.
- [ ] `W10.P048.S0288` - Record the removed shim and stub surfaces for config profile service surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W10.P049` - real behavior verification

This Phase delivers real behavior verification for config profile service surface as required by `2026-05-07-config-cli-profile-surface-adr`.

- [ ] `W10.P049.S0289` - Add service contract tests for config profile service surface; `tests/entrypoints/cli`.
- [ ] `W10.P049.S0290` - Add persistence or registry integration tests for config profile service surface; `tests/entrypoints/cli`.
- [ ] `W10.P049.S0291` - Add negative tests proving rejected aliases do not reach config profile service surface; `tests/entrypoints/cli`.
- [ ] `W10.P049.S0292` - Add command behavior tests that exercise config profile service surface through real services; `tests/entrypoints/cli`.
- [ ] `W10.P049.S0293` - Add end-to-end workflow coverage for config profile service surface; `tests`.
- [ ] `W10.P049.S0294` - Run the targeted test slice for config profile service surface without skips or xfails; `tests/entrypoints/cli`.

### Phase `W10.P050` - thin cli exposure

This Phase delivers thin cli exposure for config profile service surface as required by `2026-05-07-config-cli-profile-surface-adr`.

- [ ] `W10.P050.S0295` - Expose accepted command handlers for config profile service surface under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W10.P050.S0296` - Keep argument parsing for config profile service surface separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W10.P050.S0297` - Delegate config profile service surface execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W10.P050.S0298` - Render config profile service surface results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W10.P050.S0299` - Handle config profile service surface failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W10.P050.S0300` - Validate help text for config profile service surface uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W11` - config versus setup namespace

This Wave implements the `2026-05-12-aeat-cli-config-vs-setup-namespace-adr` decision for config namespace replacement for setup. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W11.P051` - backend implementation

This Phase delivers backend implementation for config namespace replacement for setup as required by `2026-05-12-aeat-cli-config-vs-setup-namespace-adr`.

- [ ] `W11.P051.S0301` - Map the `2026-05-12-aeat-cli-config-vs-setup-namespace-adr` decision into non-CLI service ownership for config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P051.S0302` - Implement Pydantic command and result contracts for config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P051.S0303` - Wire application or domain services required by config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P051.S0304` - Connect persistence, bucket events, registry data, or provider adapters required by config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P051.S0305` - Route existing backend functionality into the canonical service for config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P051.S0306` - Record service-level error codes and log fields for config namespace replacement for setup; `src/aeat/application/setup`.

### Phase `W11.P052` - shadow duplicate removal

This Phase delivers shadow duplicate removal for config namespace replacement for setup as required by `2026-05-12-aeat-cli-config-vs-setup-namespace-adr`.

- [ ] `W11.P052.S0307` - Audit duplicate implementations that overlap config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P052.S0308` - Delete duplicate backend branches that compete with config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P052.S0309` - Remove stale aliases that bypass the canonical service for config namespace replacement for setup; `src/aeat/entrypoints/cli`.
- [ ] `W11.P052.S0310` - Migrate internal callers to the canonical service for config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P052.S0311` - Remove stale fixtures and tests that encode duplicate behavior for config namespace replacement for setup; `tests/entrypoints/cli`.
- [ ] `W11.P052.S0312` - Update boundary inventory entries that describe duplicate behavior for config namespace replacement for setup; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W11.P053` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for config namespace replacement for setup as required by `2026-05-12-aeat-cli-config-vs-setup-namespace-adr`.

- [ ] `W11.P053.S0313` - Delete compatibility shims that preserve rejected behavior for config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P053.S0314` - Delete placeholder stubs that claim support for config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P053.S0315` - Replace stubbed paths with real backend service calls for config namespace replacement for setup; `src/aeat/application/setup`.
- [ ] `W11.P053.S0316` - Remove deprecated command spelling and help text for config namespace replacement for setup; `src/aeat/entrypoints/cli`.
- [ ] `W11.P053.S0317` - Remove tests that assert shim or stub behavior for config namespace replacement for setup; `tests/entrypoints/cli`.
- [ ] `W11.P053.S0318` - Record the removed shim and stub surfaces for config namespace replacement for setup; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W11.P054` - real behavior verification

This Phase delivers real behavior verification for config namespace replacement for setup as required by `2026-05-12-aeat-cli-config-vs-setup-namespace-adr`.

- [ ] `W11.P054.S0319` - Add service contract tests for config namespace replacement for setup; `tests/entrypoints/cli`.
- [ ] `W11.P054.S0320` - Add persistence or registry integration tests for config namespace replacement for setup; `tests/entrypoints/cli`.
- [ ] `W11.P054.S0321` - Add negative tests proving rejected aliases do not reach config namespace replacement for setup; `tests/entrypoints/cli`.
- [ ] `W11.P054.S0322` - Add command behavior tests that exercise config namespace replacement for setup through real services; `tests/entrypoints/cli`.
- [ ] `W11.P054.S0323` - Add end-to-end workflow coverage for config namespace replacement for setup; `tests`.
- [ ] `W11.P054.S0324` - Run the targeted test slice for config namespace replacement for setup without skips or xfails; `tests/entrypoints/cli`.

### Phase `W11.P055` - thin cli exposure

This Phase delivers thin cli exposure for config namespace replacement for setup as required by `2026-05-12-aeat-cli-config-vs-setup-namespace-adr`.

- [ ] `W11.P055.S0325` - Expose accepted command handlers for config namespace replacement for setup under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W11.P055.S0326` - Keep argument parsing for config namespace replacement for setup separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W11.P055.S0327` - Delegate config namespace replacement for setup execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W11.P055.S0328` - Render config namespace replacement for setup results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W11.P055.S0329` - Handle config namespace replacement for setup failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W11.P055.S0330` - Validate help text for config namespace replacement for setup uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W12` - eliminate user cli shim

This Wave implements the `2026-05-10-eliminate-user-cli-shim` decision for workflow state shim removal. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W12.P056` - backend implementation

This Phase delivers backend implementation for workflow state shim removal as required by `2026-05-10-eliminate-user-cli-shim`.

- [ ] `W12.P056.S0331` - Map the `2026-05-10-eliminate-user-cli-shim` decision into non-CLI service ownership for workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P056.S0332` - Implement Pydantic command and result contracts for workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P056.S0333` - Wire application or domain services required by workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P056.S0334` - Connect persistence, bucket events, registry data, or provider adapters required by workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P056.S0335` - Route existing backend functionality into the canonical service for workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P056.S0336` - Record service-level error codes and log fields for workflow state shim removal; `src/aeat/application/workflow`.

### Phase `W12.P057` - shadow duplicate removal

This Phase delivers shadow duplicate removal for workflow state shim removal as required by `2026-05-10-eliminate-user-cli-shim`.

- [ ] `W12.P057.S0337` - Audit duplicate implementations that overlap workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P057.S0338` - Delete duplicate backend branches that compete with workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P057.S0339` - Remove stale aliases that bypass the canonical service for workflow state shim removal; `src/aeat/entrypoints/cli`.
- [ ] `W12.P057.S0340` - Migrate internal callers to the canonical service for workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P057.S0341` - Remove stale fixtures and tests that encode duplicate behavior for workflow state shim removal; `tests/application/workflow`.
- [ ] `W12.P057.S0342` - Update boundary inventory entries that describe duplicate behavior for workflow state shim removal; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W12.P058` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for workflow state shim removal as required by `2026-05-10-eliminate-user-cli-shim`.

- [ ] `W12.P058.S0343` - Delete compatibility shims that preserve rejected behavior for workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P058.S0344` - Delete placeholder stubs that claim support for workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P058.S0345` - Replace stubbed paths with real backend service calls for workflow state shim removal; `src/aeat/application/workflow`.
- [ ] `W12.P058.S0346` - Remove deprecated command spelling and help text for workflow state shim removal; `src/aeat/entrypoints/cli`.
- [ ] `W12.P058.S0347` - Remove tests that assert shim or stub behavior for workflow state shim removal; `tests/application/workflow`.
- [ ] `W12.P058.S0348` - Record the removed shim and stub surfaces for workflow state shim removal; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W12.P059` - real behavior verification

This Phase delivers real behavior verification for workflow state shim removal as required by `2026-05-10-eliminate-user-cli-shim`.

- [ ] `W12.P059.S0349` - Add service contract tests for workflow state shim removal; `tests/application/workflow`.
- [ ] `W12.P059.S0350` - Add persistence or registry integration tests for workflow state shim removal; `tests/application/workflow`.
- [ ] `W12.P059.S0351` - Add negative tests proving rejected aliases do not reach workflow state shim removal; `tests/entrypoints/cli`.
- [ ] `W12.P059.S0352` - Add command behavior tests that exercise workflow state shim removal through real services; `tests/entrypoints/cli`.
- [ ] `W12.P059.S0353` - Add end-to-end workflow coverage for workflow state shim removal; `tests`.
- [ ] `W12.P059.S0354` - Run the targeted test slice for workflow state shim removal without skips or xfails; `tests/application/workflow`.

### Phase `W12.P060` - thin cli exposure

This Phase delivers thin cli exposure for workflow state shim removal as required by `2026-05-10-eliminate-user-cli-shim`.

- [ ] `W12.P060.S0355` - Expose accepted command handlers for workflow state shim removal under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W12.P060.S0356` - Keep argument parsing for workflow state shim removal separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W12.P060.S0357` - Delegate workflow state shim removal execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W12.P060.S0358` - Render workflow state shim removal results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W12.P060.S0359` - Handle workflow state shim removal failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W12.P060.S0360` - Validate help text for workflow state shim removal uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W13` - bucket storage boundary

This Wave implements the `2026-05-12-cli-workflow-redesign-bucket-adr` decision for profile scoped storage bucket. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W13.P061` - backend implementation

This Phase delivers backend implementation for profile scoped storage bucket as required by `2026-05-12-cli-workflow-redesign-bucket-adr`.

- [ ] `W13.P061.S0361` - Map the `2026-05-12-cli-workflow-redesign-bucket-adr` decision into non-CLI service ownership for profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P061.S0362` - Implement Pydantic command and result contracts for profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P061.S0363` - Wire application or domain services required by profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P061.S0364` - Connect persistence, bucket events, registry data, or provider adapters required by profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P061.S0365` - Route existing backend functionality into the canonical service for profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P061.S0366` - Record service-level error codes and log fields for profile scoped storage bucket; `src/aeat/adapters/persistence`.

### Phase `W13.P062` - shadow duplicate removal

This Phase delivers shadow duplicate removal for profile scoped storage bucket as required by `2026-05-12-cli-workflow-redesign-bucket-adr`.

- [ ] `W13.P062.S0367` - Audit duplicate implementations that overlap profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P062.S0368` - Delete duplicate backend branches that compete with profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P062.S0369` - Remove stale aliases that bypass the canonical service for profile scoped storage bucket; `src/aeat/entrypoints/cli`.
- [ ] `W13.P062.S0370` - Migrate internal callers to the canonical service for profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P062.S0371` - Remove stale fixtures and tests that encode duplicate behavior for profile scoped storage bucket; `tests/adapters/persistence`.
- [ ] `W13.P062.S0372` - Update boundary inventory entries that describe duplicate behavior for profile scoped storage bucket; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W13.P063` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for profile scoped storage bucket as required by `2026-05-12-cli-workflow-redesign-bucket-adr`.

- [ ] `W13.P063.S0373` - Delete compatibility shims that preserve rejected behavior for profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P063.S0374` - Delete placeholder stubs that claim support for profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P063.S0375` - Replace stubbed paths with real backend service calls for profile scoped storage bucket; `src/aeat/adapters/persistence`.
- [ ] `W13.P063.S0376` - Remove deprecated command spelling and help text for profile scoped storage bucket; `src/aeat/entrypoints/cli`.
- [ ] `W13.P063.S0377` - Remove tests that assert shim or stub behavior for profile scoped storage bucket; `tests/adapters/persistence`.
- [ ] `W13.P063.S0378` - Record the removed shim and stub surfaces for profile scoped storage bucket; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W13.P064` - real behavior verification

This Phase delivers real behavior verification for profile scoped storage bucket as required by `2026-05-12-cli-workflow-redesign-bucket-adr`.

- [ ] `W13.P064.S0379` - Add service contract tests for profile scoped storage bucket; `tests/adapters/persistence`.
- [ ] `W13.P064.S0380` - Add persistence or registry integration tests for profile scoped storage bucket; `tests/adapters/persistence`.
- [ ] `W13.P064.S0381` - Add negative tests proving rejected aliases do not reach profile scoped storage bucket; `tests/entrypoints/cli`.
- [ ] `W13.P064.S0382` - Add command behavior tests that exercise profile scoped storage bucket through real services; `tests/entrypoints/cli`.
- [ ] `W13.P064.S0383` - Add end-to-end workflow coverage for profile scoped storage bucket; `tests`.
- [ ] `W13.P064.S0384` - Run the targeted test slice for profile scoped storage bucket without skips or xfails; `tests/adapters/persistence`.

### Phase `W13.P065` - thin cli exposure

This Phase delivers thin cli exposure for profile scoped storage bucket as required by `2026-05-12-cli-workflow-redesign-bucket-adr`.

- [ ] `W13.P065.S0385` - Expose accepted command handlers for profile scoped storage bucket under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W13.P065.S0386` - Keep argument parsing for profile scoped storage bucket separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W13.P065.S0387` - Delegate profile scoped storage bucket execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W13.P065.S0388` - Render profile scoped storage bucket results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W13.P065.S0389` - Handle profile scoped storage bucket failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W13.P065.S0390` - Validate help text for profile scoped storage bucket uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W14` - bucket event history

This Wave implements the `2026-05-12-cli-workflow-redesign-bucket-event-history-adr` decision for bucket event history ledger. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W14.P066` - backend implementation

This Phase delivers backend implementation for bucket event history ledger as required by `2026-05-12-cli-workflow-redesign-bucket-event-history-adr`.

- [ ] `W14.P066.S0391` - Map the `2026-05-12-cli-workflow-redesign-bucket-event-history-adr` decision into non-CLI service ownership for bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P066.S0392` - Implement Pydantic command and result contracts for bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P066.S0393` - Wire application or domain services required by bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P066.S0394` - Connect persistence, bucket events, registry data, or provider adapters required by bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P066.S0395` - Route existing backend functionality into the canonical service for bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P066.S0396` - Record service-level error codes and log fields for bucket event history ledger; `src/aeat/adapters/persistence`.

### Phase `W14.P067` - shadow duplicate removal

This Phase delivers shadow duplicate removal for bucket event history ledger as required by `2026-05-12-cli-workflow-redesign-bucket-event-history-adr`.

- [ ] `W14.P067.S0397` - Audit duplicate implementations that overlap bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P067.S0398` - Delete duplicate backend branches that compete with bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P067.S0399` - Remove stale aliases that bypass the canonical service for bucket event history ledger; `src/aeat/entrypoints/cli`.
- [ ] `W14.P067.S0400` - Migrate internal callers to the canonical service for bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P067.S0401` - Remove stale fixtures and tests that encode duplicate behavior for bucket event history ledger; `tests/adapters/persistence`.
- [ ] `W14.P067.S0402` - Update boundary inventory entries that describe duplicate behavior for bucket event history ledger; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W14.P068` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for bucket event history ledger as required by `2026-05-12-cli-workflow-redesign-bucket-event-history-adr`.

- [ ] `W14.P068.S0403` - Delete compatibility shims that preserve rejected behavior for bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P068.S0404` - Delete placeholder stubs that claim support for bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P068.S0405` - Replace stubbed paths with real backend service calls for bucket event history ledger; `src/aeat/adapters/persistence`.
- [ ] `W14.P068.S0406` - Remove deprecated command spelling and help text for bucket event history ledger; `src/aeat/entrypoints/cli`.
- [ ] `W14.P068.S0407` - Remove tests that assert shim or stub behavior for bucket event history ledger; `tests/adapters/persistence`.
- [ ] `W14.P068.S0408` - Record the removed shim and stub surfaces for bucket event history ledger; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W14.P069` - real behavior verification

This Phase delivers real behavior verification for bucket event history ledger as required by `2026-05-12-cli-workflow-redesign-bucket-event-history-adr`.

- [ ] `W14.P069.S0409` - Add service contract tests for bucket event history ledger; `tests/adapters/persistence`.
- [ ] `W14.P069.S0410` - Add persistence or registry integration tests for bucket event history ledger; `tests/adapters/persistence`.
- [ ] `W14.P069.S0411` - Add negative tests proving rejected aliases do not reach bucket event history ledger; `tests/entrypoints/cli`.
- [ ] `W14.P069.S0412` - Add command behavior tests that exercise bucket event history ledger through real services; `tests/entrypoints/cli`.
- [ ] `W14.P069.S0413` - Add end-to-end workflow coverage for bucket event history ledger; `tests`.
- [ ] `W14.P069.S0414` - Run the targeted test slice for bucket event history ledger without skips or xfails; `tests/adapters/persistence`.

### Phase `W14.P070` - thin cli exposure

This Phase delivers thin cli exposure for bucket event history ledger as required by `2026-05-12-cli-workflow-redesign-bucket-event-history-adr`.

- [ ] `W14.P070.S0415` - Expose accepted command handlers for bucket event history ledger under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W14.P070.S0416` - Keep argument parsing for bucket event history ledger separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W14.P070.S0417` - Delegate bucket event history ledger execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W14.P070.S0418` - Render bucket event history ledger results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W14.P070.S0419` - Handle bucket event history ledger failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W14.P070.S0420` - Validate help text for bucket event history ledger uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W15` - config init shape

This Wave implements the `2026-05-12-cli-workflow-redesign-config-init-shape-adr` decision for first run configuration initialization. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W15.P071` - backend implementation

This Phase delivers backend implementation for first run configuration initialization as required by `2026-05-12-cli-workflow-redesign-config-init-shape-adr`.

- [ ] `W15.P071.S0421` - Map the `2026-05-12-cli-workflow-redesign-config-init-shape-adr` decision into non-CLI service ownership for first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P071.S0422` - Implement Pydantic command and result contracts for first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P071.S0423` - Wire application or domain services required by first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P071.S0424` - Connect persistence, bucket events, registry data, or provider adapters required by first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P071.S0425` - Route existing backend functionality into the canonical service for first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P071.S0426` - Record service-level error codes and log fields for first run configuration initialization; `src/aeat/application/setup`.

### Phase `W15.P072` - shadow duplicate removal

This Phase delivers shadow duplicate removal for first run configuration initialization as required by `2026-05-12-cli-workflow-redesign-config-init-shape-adr`.

- [ ] `W15.P072.S0427` - Audit duplicate implementations that overlap first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P072.S0428` - Delete duplicate backend branches that compete with first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P072.S0429` - Remove stale aliases that bypass the canonical service for first run configuration initialization; `src/aeat/entrypoints/cli`.
- [ ] `W15.P072.S0430` - Migrate internal callers to the canonical service for first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P072.S0431` - Remove stale fixtures and tests that encode duplicate behavior for first run configuration initialization; `tests/entrypoints/cli`.
- [ ] `W15.P072.S0432` - Update boundary inventory entries that describe duplicate behavior for first run configuration initialization; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W15.P073` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for first run configuration initialization as required by `2026-05-12-cli-workflow-redesign-config-init-shape-adr`.

- [ ] `W15.P073.S0433` - Delete compatibility shims that preserve rejected behavior for first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P073.S0434` - Delete placeholder stubs that claim support for first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P073.S0435` - Replace stubbed paths with real backend service calls for first run configuration initialization; `src/aeat/application/setup`.
- [ ] `W15.P073.S0436` - Remove deprecated command spelling and help text for first run configuration initialization; `src/aeat/entrypoints/cli`.
- [ ] `W15.P073.S0437` - Remove tests that assert shim or stub behavior for first run configuration initialization; `tests/entrypoints/cli`.
- [ ] `W15.P073.S0438` - Record the removed shim and stub surfaces for first run configuration initialization; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W15.P074` - real behavior verification

This Phase delivers real behavior verification for first run configuration initialization as required by `2026-05-12-cli-workflow-redesign-config-init-shape-adr`.

- [ ] `W15.P074.S0439` - Add service contract tests for first run configuration initialization; `tests/entrypoints/cli`.
- [ ] `W15.P074.S0440` - Add persistence or registry integration tests for first run configuration initialization; `tests/entrypoints/cli`.
- [ ] `W15.P074.S0441` - Add negative tests proving rejected aliases do not reach first run configuration initialization; `tests/entrypoints/cli`.
- [ ] `W15.P074.S0442` - Add command behavior tests that exercise first run configuration initialization through real services; `tests/entrypoints/cli`.
- [ ] `W15.P074.S0443` - Add end-to-end workflow coverage for first run configuration initialization; `tests`.
- [ ] `W15.P074.S0444` - Run the targeted test slice for first run configuration initialization without skips or xfails; `tests/entrypoints/cli`.

### Phase `W15.P075` - thin cli exposure

This Phase delivers thin cli exposure for first run configuration initialization as required by `2026-05-12-cli-workflow-redesign-config-init-shape-adr`.

- [ ] `W15.P075.S0445` - Expose accepted command handlers for first run configuration initialization under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W15.P075.S0446` - Keep argument parsing for first run configuration initialization separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W15.P075.S0447` - Delegate first run configuration initialization execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W15.P075.S0448` - Render first run configuration initialization results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W15.P075.S0449` - Handle first run configuration initialization failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W15.P075.S0450` - Validate help text for first run configuration initialization uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W16` - auth cli

This Wave implements the `2026-04-21-auth-cli-adr` decision for authentication cli migration. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W16.P076` - backend implementation

This Phase delivers backend implementation for authentication cli migration as required by `2026-04-21-auth-cli-adr`.

- [ ] `W16.P076.S0451` - Map the `2026-04-21-auth-cli-adr` decision into non-CLI service ownership for authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P076.S0452` - Implement Pydantic command and result contracts for authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P076.S0453` - Wire application or domain services required by authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P076.S0454` - Connect persistence, bucket events, registry data, or provider adapters required by authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P076.S0455` - Route existing backend functionality into the canonical service for authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P076.S0456` - Record service-level error codes and log fields for authentication cli migration; `src/aeat/application/auth`.

### Phase `W16.P077` - shadow duplicate removal

This Phase delivers shadow duplicate removal for authentication cli migration as required by `2026-04-21-auth-cli-adr`.

- [ ] `W16.P077.S0457` - Audit duplicate implementations that overlap authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P077.S0458` - Delete duplicate backend branches that compete with authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P077.S0459` - Remove stale aliases that bypass the canonical service for authentication cli migration; `src/aeat/entrypoints/cli`.
- [ ] `W16.P077.S0460` - Migrate internal callers to the canonical service for authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P077.S0461` - Remove stale fixtures and tests that encode duplicate behavior for authentication cli migration; `tests/application/auth`.
- [ ] `W16.P077.S0462` - Update boundary inventory entries that describe duplicate behavior for authentication cli migration; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W16.P078` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for authentication cli migration as required by `2026-04-21-auth-cli-adr`.

- [ ] `W16.P078.S0463` - Delete compatibility shims that preserve rejected behavior for authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P078.S0464` - Delete placeholder stubs that claim support for authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P078.S0465` - Replace stubbed paths with real backend service calls for authentication cli migration; `src/aeat/application/auth`.
- [ ] `W16.P078.S0466` - Remove deprecated command spelling and help text for authentication cli migration; `src/aeat/entrypoints/cli`.
- [ ] `W16.P078.S0467` - Remove tests that assert shim or stub behavior for authentication cli migration; `tests/application/auth`.
- [ ] `W16.P078.S0468` - Record the removed shim and stub surfaces for authentication cli migration; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W16.P079` - real behavior verification

This Phase delivers real behavior verification for authentication cli migration as required by `2026-04-21-auth-cli-adr`.

- [ ] `W16.P079.S0469` - Add service contract tests for authentication cli migration; `tests/application/auth`.
- [ ] `W16.P079.S0470` - Add persistence or registry integration tests for authentication cli migration; `tests/application/auth`.
- [ ] `W16.P079.S0471` - Add negative tests proving rejected aliases do not reach authentication cli migration; `tests/entrypoints/cli`.
- [ ] `W16.P079.S0472` - Add command behavior tests that exercise authentication cli migration through real services; `tests/entrypoints/cli`.
- [ ] `W16.P079.S0473` - Add end-to-end workflow coverage for authentication cli migration; `tests`.
- [ ] `W16.P079.S0474` - Run the targeted test slice for authentication cli migration without skips or xfails; `tests/application/auth`.

### Phase `W16.P080` - thin cli exposure

This Phase delivers thin cli exposure for authentication cli migration as required by `2026-04-21-auth-cli-adr`.

- [ ] `W16.P080.S0475` - Expose accepted command handlers for authentication cli migration under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W16.P080.S0476` - Keep argument parsing for authentication cli migration separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W16.P080.S0477` - Delegate authentication cli migration execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W16.P080.S0478` - Render authentication cli migration results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W16.P080.S0479` - Handle authentication cli migration failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W16.P080.S0480` - Validate help text for authentication cli migration uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W17` - config auth shape

This Wave implements the `2026-05-12-cli-workflow-redesign-config-auth-shape-adr` decision for authentication configuration surface. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W17.P081` - backend implementation

This Phase delivers backend implementation for authentication configuration surface as required by `2026-05-12-cli-workflow-redesign-config-auth-shape-adr`.

- [ ] `W17.P081.S0481` - Map the `2026-05-12-cli-workflow-redesign-config-auth-shape-adr` decision into non-CLI service ownership for authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P081.S0482` - Implement Pydantic command and result contracts for authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P081.S0483` - Wire application or domain services required by authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P081.S0484` - Connect persistence, bucket events, registry data, or provider adapters required by authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P081.S0485` - Route existing backend functionality into the canonical service for authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P081.S0486` - Record service-level error codes and log fields for authentication configuration surface; `src/aeat/application/auth`.

### Phase `W17.P082` - shadow duplicate removal

This Phase delivers shadow duplicate removal for authentication configuration surface as required by `2026-05-12-cli-workflow-redesign-config-auth-shape-adr`.

- [ ] `W17.P082.S0487` - Audit duplicate implementations that overlap authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P082.S0488` - Delete duplicate backend branches that compete with authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P082.S0489` - Remove stale aliases that bypass the canonical service for authentication configuration surface; `src/aeat/entrypoints/cli`.
- [ ] `W17.P082.S0490` - Migrate internal callers to the canonical service for authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P082.S0491` - Remove stale fixtures and tests that encode duplicate behavior for authentication configuration surface; `tests/application/auth`.
- [ ] `W17.P082.S0492` - Update boundary inventory entries that describe duplicate behavior for authentication configuration surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W17.P083` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for authentication configuration surface as required by `2026-05-12-cli-workflow-redesign-config-auth-shape-adr`.

- [ ] `W17.P083.S0493` - Delete compatibility shims that preserve rejected behavior for authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P083.S0494` - Delete placeholder stubs that claim support for authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P083.S0495` - Replace stubbed paths with real backend service calls for authentication configuration surface; `src/aeat/application/auth`.
- [ ] `W17.P083.S0496` - Remove deprecated command spelling and help text for authentication configuration surface; `src/aeat/entrypoints/cli`.
- [ ] `W17.P083.S0497` - Remove tests that assert shim or stub behavior for authentication configuration surface; `tests/application/auth`.
- [ ] `W17.P083.S0498` - Record the removed shim and stub surfaces for authentication configuration surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W17.P084` - real behavior verification

This Phase delivers real behavior verification for authentication configuration surface as required by `2026-05-12-cli-workflow-redesign-config-auth-shape-adr`.

- [ ] `W17.P084.S0499` - Add service contract tests for authentication configuration surface; `tests/application/auth`.
- [ ] `W17.P084.S0500` - Add persistence or registry integration tests for authentication configuration surface; `tests/application/auth`.
- [ ] `W17.P084.S0501` - Add negative tests proving rejected aliases do not reach authentication configuration surface; `tests/entrypoints/cli`.
- [ ] `W17.P084.S0502` - Add command behavior tests that exercise authentication configuration surface through real services; `tests/entrypoints/cli`.
- [ ] `W17.P084.S0503` - Add end-to-end workflow coverage for authentication configuration surface; `tests`.
- [ ] `W17.P084.S0504` - Run the targeted test slice for authentication configuration surface without skips or xfails; `tests/application/auth`.

### Phase `W17.P085` - thin cli exposure

This Phase delivers thin cli exposure for authentication configuration surface as required by `2026-05-12-cli-workflow-redesign-config-auth-shape-adr`.

- [ ] `W17.P085.S0505` - Expose accepted command handlers for authentication configuration surface under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W17.P085.S0506` - Keep argument parsing for authentication configuration surface separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W17.P085.S0507` - Delegate authentication configuration surface execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W17.P085.S0508` - Render authentication configuration surface results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W17.P085.S0509` - Handle authentication configuration surface failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W17.P085.S0510` - Validate help text for authentication configuration surface uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W18` - config doctor shape

This Wave implements the `2026-05-12-cli-workflow-redesign-config-doctor-shape-adr` decision for diagnostic and integrity surface. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W18.P086` - backend implementation

This Phase delivers backend implementation for diagnostic and integrity surface as required by `2026-05-12-cli-workflow-redesign-config-doctor-shape-adr`.

- [ ] `W18.P086.S0511` - Map the `2026-05-12-cli-workflow-redesign-config-doctor-shape-adr` decision into non-CLI service ownership for diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P086.S0512` - Implement Pydantic command and result contracts for diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P086.S0513` - Wire application or domain services required by diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P086.S0514` - Connect persistence, bucket events, registry data, or provider adapters required by diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P086.S0515` - Route existing backend functionality into the canonical service for diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P086.S0516` - Record service-level error codes and log fields for diagnostic and integrity surface; `src/aeat/application/diagnostics`.

### Phase `W18.P087` - shadow duplicate removal

This Phase delivers shadow duplicate removal for diagnostic and integrity surface as required by `2026-05-12-cli-workflow-redesign-config-doctor-shape-adr`.

- [ ] `W18.P087.S0517` - Audit duplicate implementations that overlap diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P087.S0518` - Delete duplicate backend branches that compete with diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P087.S0519` - Remove stale aliases that bypass the canonical service for diagnostic and integrity surface; `src/aeat/entrypoints/cli`.
- [ ] `W18.P087.S0520` - Migrate internal callers to the canonical service for diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P087.S0521` - Remove stale fixtures and tests that encode duplicate behavior for diagnostic and integrity surface; `tests/entrypoints/cli`.
- [ ] `W18.P087.S0522` - Update boundary inventory entries that describe duplicate behavior for diagnostic and integrity surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W18.P088` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for diagnostic and integrity surface as required by `2026-05-12-cli-workflow-redesign-config-doctor-shape-adr`.

- [ ] `W18.P088.S0523` - Delete compatibility shims that preserve rejected behavior for diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P088.S0524` - Delete placeholder stubs that claim support for diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P088.S0525` - Replace stubbed paths with real backend service calls for diagnostic and integrity surface; `src/aeat/application/diagnostics`.
- [ ] `W18.P088.S0526` - Remove deprecated command spelling and help text for diagnostic and integrity surface; `src/aeat/entrypoints/cli`.
- [ ] `W18.P088.S0527` - Remove tests that assert shim or stub behavior for diagnostic and integrity surface; `tests/entrypoints/cli`.
- [ ] `W18.P088.S0528` - Record the removed shim and stub surfaces for diagnostic and integrity surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W18.P089` - real behavior verification

This Phase delivers real behavior verification for diagnostic and integrity surface as required by `2026-05-12-cli-workflow-redesign-config-doctor-shape-adr`.

- [ ] `W18.P089.S0529` - Add service contract tests for diagnostic and integrity surface; `tests/entrypoints/cli`.
- [ ] `W18.P089.S0530` - Add persistence or registry integration tests for diagnostic and integrity surface; `tests/entrypoints/cli`.
- [ ] `W18.P089.S0531` - Add negative tests proving rejected aliases do not reach diagnostic and integrity surface; `tests/entrypoints/cli`.
- [ ] `W18.P089.S0532` - Add command behavior tests that exercise diagnostic and integrity surface through real services; `tests/entrypoints/cli`.
- [ ] `W18.P089.S0533` - Add end-to-end workflow coverage for diagnostic and integrity surface; `tests`.
- [ ] `W18.P089.S0534` - Run the targeted test slice for diagnostic and integrity surface without skips or xfails; `tests/entrypoints/cli`.

### Phase `W18.P090` - thin cli exposure

This Phase delivers thin cli exposure for diagnostic and integrity surface as required by `2026-05-12-cli-workflow-redesign-config-doctor-shape-adr`.

- [ ] `W18.P090.S0535` - Expose accepted command handlers for diagnostic and integrity surface under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W18.P090.S0536` - Keep argument parsing for diagnostic and integrity surface separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W18.P090.S0537` - Delegate diagnostic and integrity surface execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W18.P090.S0538` - Render diagnostic and integrity surface results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W18.P090.S0539` - Handle diagnostic and integrity surface failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W18.P090.S0540` - Validate help text for diagnostic and integrity surface uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W19` - config profile use and status

This Wave implements the `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr` decision for active profile selection and status. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W19.P091` - backend implementation

This Phase delivers backend implementation for active profile selection and status as required by `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr`.

- [ ] `W19.P091.S0541` - Map the `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr` decision into non-CLI service ownership for active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P091.S0542` - Implement Pydantic command and result contracts for active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P091.S0543` - Wire application or domain services required by active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P091.S0544` - Connect persistence, bucket events, registry data, or provider adapters required by active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P091.S0545` - Route existing backend functionality into the canonical service for active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P091.S0546` - Record service-level error codes and log fields for active profile selection and status; `src/aeat/application/profile`.

### Phase `W19.P092` - shadow duplicate removal

This Phase delivers shadow duplicate removal for active profile selection and status as required by `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr`.

- [ ] `W19.P092.S0547` - Audit duplicate implementations that overlap active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P092.S0548` - Delete duplicate backend branches that compete with active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P092.S0549` - Remove stale aliases that bypass the canonical service for active profile selection and status; `src/aeat/entrypoints/cli`.
- [ ] `W19.P092.S0550` - Migrate internal callers to the canonical service for active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P092.S0551` - Remove stale fixtures and tests that encode duplicate behavior for active profile selection and status; `tests/entrypoints/cli`.
- [ ] `W19.P092.S0552` - Update boundary inventory entries that describe duplicate behavior for active profile selection and status; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W19.P093` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for active profile selection and status as required by `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr`.

- [ ] `W19.P093.S0553` - Delete compatibility shims that preserve rejected behavior for active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P093.S0554` - Delete placeholder stubs that claim support for active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P093.S0555` - Replace stubbed paths with real backend service calls for active profile selection and status; `src/aeat/application/profile`.
- [ ] `W19.P093.S0556` - Remove deprecated command spelling and help text for active profile selection and status; `src/aeat/entrypoints/cli`.
- [ ] `W19.P093.S0557` - Remove tests that assert shim or stub behavior for active profile selection and status; `tests/entrypoints/cli`.
- [ ] `W19.P093.S0558` - Record the removed shim and stub surfaces for active profile selection and status; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W19.P094` - real behavior verification

This Phase delivers real behavior verification for active profile selection and status as required by `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr`.

- [ ] `W19.P094.S0559` - Add service contract tests for active profile selection and status; `tests/entrypoints/cli`.
- [ ] `W19.P094.S0560` - Add persistence or registry integration tests for active profile selection and status; `tests/entrypoints/cli`.
- [ ] `W19.P094.S0561` - Add negative tests proving rejected aliases do not reach active profile selection and status; `tests/entrypoints/cli`.
- [ ] `W19.P094.S0562` - Add command behavior tests that exercise active profile selection and status through real services; `tests/entrypoints/cli`.
- [ ] `W19.P094.S0563` - Add end-to-end workflow coverage for active profile selection and status; `tests`.
- [ ] `W19.P094.S0564` - Run the targeted test slice for active profile selection and status without skips or xfails; `tests/entrypoints/cli`.

### Phase `W19.P095` - thin cli exposure

This Phase delivers thin cli exposure for active profile selection and status as required by `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr`.

- [ ] `W19.P095.S0565` - Expose accepted command handlers for active profile selection and status under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W19.P095.S0566` - Keep argument parsing for active profile selection and status separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W19.P095.S0567` - Delegate active profile selection and status execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W19.P095.S0568` - Render active profile selection and status results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W19.P095.S0569` - Handle active profile selection and status failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W19.P095.S0570` - Validate help text for active profile selection and status uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W20` - apoderamientos surface

This Wave implements the `2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr` decision for representation capability surface. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W20.P096` - backend implementation

This Phase delivers backend implementation for representation capability surface as required by `2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr`.

- [ ] `W20.P096.S0571` - Map the `2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr` decision into non-CLI service ownership for representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P096.S0572` - Implement Pydantic command and result contracts for representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P096.S0573` - Wire application or domain services required by representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P096.S0574` - Connect persistence, bucket events, registry data, or provider adapters required by representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P096.S0575` - Route existing backend functionality into the canonical service for representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P096.S0576` - Record service-level error codes and log fields for representation capability surface; `src/aeat/application/auth`.

### Phase `W20.P097` - shadow duplicate removal

This Phase delivers shadow duplicate removal for representation capability surface as required by `2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr`.

- [ ] `W20.P097.S0577` - Audit duplicate implementations that overlap representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P097.S0578` - Delete duplicate backend branches that compete with representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P097.S0579` - Remove stale aliases that bypass the canonical service for representation capability surface; `src/aeat/entrypoints/cli`.
- [ ] `W20.P097.S0580` - Migrate internal callers to the canonical service for representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P097.S0581` - Remove stale fixtures and tests that encode duplicate behavior for representation capability surface; `tests/application/auth`.
- [ ] `W20.P097.S0582` - Update boundary inventory entries that describe duplicate behavior for representation capability surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W20.P098` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for representation capability surface as required by `2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr`.

- [ ] `W20.P098.S0583` - Delete compatibility shims that preserve rejected behavior for representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P098.S0584` - Delete placeholder stubs that claim support for representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P098.S0585` - Replace stubbed paths with real backend service calls for representation capability surface; `src/aeat/application/auth`.
- [ ] `W20.P098.S0586` - Remove deprecated command spelling and help text for representation capability surface; `src/aeat/entrypoints/cli`.
- [ ] `W20.P098.S0587` - Remove tests that assert shim or stub behavior for representation capability surface; `tests/application/auth`.
- [ ] `W20.P098.S0588` - Record the removed shim and stub surfaces for representation capability surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W20.P099` - real behavior verification

This Phase delivers real behavior verification for representation capability surface as required by `2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr`.

- [ ] `W20.P099.S0589` - Add service contract tests for representation capability surface; `tests/application/auth`.
- [ ] `W20.P099.S0590` - Add persistence or registry integration tests for representation capability surface; `tests/application/auth`.
- [ ] `W20.P099.S0591` - Add negative tests proving rejected aliases do not reach representation capability surface; `tests/entrypoints/cli`.
- [ ] `W20.P099.S0592` - Add command behavior tests that exercise representation capability surface through real services; `tests/entrypoints/cli`.
- [ ] `W20.P099.S0593` - Add end-to-end workflow coverage for representation capability surface; `tests`.
- [ ] `W20.P099.S0594` - Run the targeted test slice for representation capability surface without skips or xfails; `tests/application/auth`.

### Phase `W20.P100` - thin cli exposure

This Phase delivers thin cli exposure for representation capability surface as required by `2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr`.

- [ ] `W20.P100.S0595` - Expose accepted command handlers for representation capability surface under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W20.P100.S0596` - Keep argument parsing for representation capability surface separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W20.P100.S0597` - Delegate representation capability surface execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W20.P100.S0598` - Render representation capability surface results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W20.P100.S0599` - Handle representation capability surface failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W20.P100.S0600` - Validate help text for representation capability surface uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W21` - apoderado scope vocabulary

This Wave implements the `2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr` decision for representation scope vocabulary. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W21.P101` - backend implementation

This Phase delivers backend implementation for representation scope vocabulary as required by `2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr`.

- [ ] `W21.P101.S0601` - Map the `2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr` decision into non-CLI service ownership for representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P101.S0602` - Implement Pydantic command and result contracts for representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P101.S0603` - Wire application or domain services required by representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P101.S0604` - Connect persistence, bucket events, registry data, or provider adapters required by representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P101.S0605` - Route existing backend functionality into the canonical service for representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P101.S0606` - Record service-level error codes and log fields for representation scope vocabulary; `src/aeat/domain/auth`.

### Phase `W21.P102` - shadow duplicate removal

This Phase delivers shadow duplicate removal for representation scope vocabulary as required by `2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr`.

- [ ] `W21.P102.S0607` - Audit duplicate implementations that overlap representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P102.S0608` - Delete duplicate backend branches that compete with representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P102.S0609` - Remove stale aliases that bypass the canonical service for representation scope vocabulary; `src/aeat/entrypoints/cli`.
- [ ] `W21.P102.S0610` - Migrate internal callers to the canonical service for representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P102.S0611` - Remove stale fixtures and tests that encode duplicate behavior for representation scope vocabulary; `tests/domain/auth`.
- [ ] `W21.P102.S0612` - Update boundary inventory entries that describe duplicate behavior for representation scope vocabulary; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W21.P103` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for representation scope vocabulary as required by `2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr`.

- [ ] `W21.P103.S0613` - Delete compatibility shims that preserve rejected behavior for representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P103.S0614` - Delete placeholder stubs that claim support for representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P103.S0615` - Replace stubbed paths with real backend service calls for representation scope vocabulary; `src/aeat/domain/auth`.
- [ ] `W21.P103.S0616` - Remove deprecated command spelling and help text for representation scope vocabulary; `src/aeat/entrypoints/cli`.
- [ ] `W21.P103.S0617` - Remove tests that assert shim or stub behavior for representation scope vocabulary; `tests/domain/auth`.
- [ ] `W21.P103.S0618` - Record the removed shim and stub surfaces for representation scope vocabulary; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W21.P104` - real behavior verification

This Phase delivers real behavior verification for representation scope vocabulary as required by `2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr`.

- [ ] `W21.P104.S0619` - Add service contract tests for representation scope vocabulary; `tests/domain/auth`.
- [ ] `W21.P104.S0620` - Add persistence or registry integration tests for representation scope vocabulary; `tests/domain/auth`.
- [ ] `W21.P104.S0621` - Add negative tests proving rejected aliases do not reach representation scope vocabulary; `tests/entrypoints/cli`.
- [ ] `W21.P104.S0622` - Add command behavior tests that exercise representation scope vocabulary through real services; `tests/entrypoints/cli`.
- [ ] `W21.P104.S0623` - Add end-to-end workflow coverage for representation scope vocabulary; `tests`.
- [ ] `W21.P104.S0624` - Run the targeted test slice for representation scope vocabulary without skips or xfails; `tests/domain/auth`.

### Phase `W21.P105` - thin cli exposure

This Phase delivers thin cli exposure for representation scope vocabulary as required by `2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr`.

- [ ] `W21.P105.S0625` - Expose accepted command handlers for representation scope vocabulary under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W21.P105.S0626` - Keep argument parsing for representation scope vocabulary separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W21.P105.S0627` - Delegate representation scope vocabulary execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W21.P105.S0628` - Render representation scope vocabulary results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W21.P105.S0629` - Handle representation scope vocabulary failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W21.P105.S0630` - Validate help text for representation scope vocabulary uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W22` - invoice domain decoupling

This Wave implements the `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr` decision for invoice terminology and source kind separation. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W22.P106` - backend implementation

This Phase delivers backend implementation for invoice terminology and source kind separation as required by `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`.

- [ ] `W22.P106.S0631` - Map the `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr` decision into non-CLI service ownership for invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P106.S0632` - Implement Pydantic command and result contracts for invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P106.S0633` - Wire application or domain services required by invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P106.S0634` - Connect persistence, bucket events, registry data, or provider adapters required by invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P106.S0635` - Route existing backend functionality into the canonical service for invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P106.S0636` - Record service-level error codes and log fields for invoice terminology and source kind separation; `src/aeat/domain`.

### Phase `W22.P107` - shadow duplicate removal

This Phase delivers shadow duplicate removal for invoice terminology and source kind separation as required by `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`.

- [ ] `W22.P107.S0637` - Audit duplicate implementations that overlap invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P107.S0638` - Delete duplicate backend branches that compete with invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P107.S0639` - Remove stale aliases that bypass the canonical service for invoice terminology and source kind separation; `src/aeat/entrypoints/cli`.
- [ ] `W22.P107.S0640` - Migrate internal callers to the canonical service for invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P107.S0641` - Remove stale fixtures and tests that encode duplicate behavior for invoice terminology and source kind separation; `tests/domain`.
- [ ] `W22.P107.S0642` - Update boundary inventory entries that describe duplicate behavior for invoice terminology and source kind separation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W22.P108` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for invoice terminology and source kind separation as required by `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`.

- [ ] `W22.P108.S0643` - Delete compatibility shims that preserve rejected behavior for invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P108.S0644` - Delete placeholder stubs that claim support for invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P108.S0645` - Replace stubbed paths with real backend service calls for invoice terminology and source kind separation; `src/aeat/domain`.
- [ ] `W22.P108.S0646` - Remove deprecated command spelling and help text for invoice terminology and source kind separation; `src/aeat/entrypoints/cli`.
- [ ] `W22.P108.S0647` - Remove tests that assert shim or stub behavior for invoice terminology and source kind separation; `tests/domain`.
- [ ] `W22.P108.S0648` - Record the removed shim and stub surfaces for invoice terminology and source kind separation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W22.P109` - real behavior verification

This Phase delivers real behavior verification for invoice terminology and source kind separation as required by `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`.

- [ ] `W22.P109.S0649` - Add service contract tests for invoice terminology and source kind separation; `tests/domain`.
- [ ] `W22.P109.S0650` - Add persistence or registry integration tests for invoice terminology and source kind separation; `tests/domain`.
- [ ] `W22.P109.S0651` - Add negative tests proving rejected aliases do not reach invoice terminology and source kind separation; `tests/entrypoints/cli`.
- [ ] `W22.P109.S0652` - Add command behavior tests that exercise invoice terminology and source kind separation through real services; `tests/entrypoints/cli`.
- [ ] `W22.P109.S0653` - Add end-to-end workflow coverage for invoice terminology and source kind separation; `tests`.
- [ ] `W22.P109.S0654` - Run the targeted test slice for invoice terminology and source kind separation without skips or xfails; `tests/domain`.

### Phase `W22.P110` - thin cli exposure

This Phase delivers thin cli exposure for invoice terminology and source kind separation as required by `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`.

- [ ] `W22.P110.S0655` - Expose accepted command handlers for invoice terminology and source kind separation under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W22.P110.S0656` - Keep argument parsing for invoice terminology and source kind separation separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W22.P110.S0657` - Delegate invoice terminology and source kind separation execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W22.P110.S0658` - Render invoice terminology and source kind separation results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W22.P110.S0659` - Handle invoice terminology and source kind separation failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W22.P110.S0660` - Validate help text for invoice terminology and source kind separation uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W23` - ledger transaction management

This Wave implements the `2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr` decision for ledger transaction lifecycle. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W23.P111` - backend implementation

This Phase delivers backend implementation for ledger transaction lifecycle as required by `2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr`.

- [ ] `W23.P111.S0661` - Map the `2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr` decision into non-CLI service ownership for ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P111.S0662` - Implement Pydantic command and result contracts for ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P111.S0663` - Wire application or domain services required by ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P111.S0664` - Connect persistence, bucket events, registry data, or provider adapters required by ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P111.S0665` - Route existing backend functionality into the canonical service for ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P111.S0666` - Record service-level error codes and log fields for ledger transaction lifecycle; `src/aeat/application/ledger`.

### Phase `W23.P112` - shadow duplicate removal

This Phase delivers shadow duplicate removal for ledger transaction lifecycle as required by `2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr`.

- [ ] `W23.P112.S0667` - Audit duplicate implementations that overlap ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P112.S0668` - Delete duplicate backend branches that compete with ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P112.S0669` - Remove stale aliases that bypass the canonical service for ledger transaction lifecycle; `src/aeat/entrypoints/cli`.
- [ ] `W23.P112.S0670` - Migrate internal callers to the canonical service for ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P112.S0671` - Remove stale fixtures and tests that encode duplicate behavior for ledger transaction lifecycle; `tests/application/ledger`.
- [ ] `W23.P112.S0672` - Update boundary inventory entries that describe duplicate behavior for ledger transaction lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W23.P113` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for ledger transaction lifecycle as required by `2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr`.

- [ ] `W23.P113.S0673` - Delete compatibility shims that preserve rejected behavior for ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P113.S0674` - Delete placeholder stubs that claim support for ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P113.S0675` - Replace stubbed paths with real backend service calls for ledger transaction lifecycle; `src/aeat/application/ledger`.
- [ ] `W23.P113.S0676` - Remove deprecated command spelling and help text for ledger transaction lifecycle; `src/aeat/entrypoints/cli`.
- [ ] `W23.P113.S0677` - Remove tests that assert shim or stub behavior for ledger transaction lifecycle; `tests/application/ledger`.
- [ ] `W23.P113.S0678` - Record the removed shim and stub surfaces for ledger transaction lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W23.P114` - real behavior verification

This Phase delivers real behavior verification for ledger transaction lifecycle as required by `2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr`.

- [ ] `W23.P114.S0679` - Add service contract tests for ledger transaction lifecycle; `tests/application/ledger`.
- [ ] `W23.P114.S0680` - Add persistence or registry integration tests for ledger transaction lifecycle; `tests/application/ledger`.
- [ ] `W23.P114.S0681` - Add negative tests proving rejected aliases do not reach ledger transaction lifecycle; `tests/entrypoints/cli`.
- [ ] `W23.P114.S0682` - Add command behavior tests that exercise ledger transaction lifecycle through real services; `tests/entrypoints/cli`.
- [ ] `W23.P114.S0683` - Add end-to-end workflow coverage for ledger transaction lifecycle; `tests`.
- [ ] `W23.P114.S0684` - Run the targeted test slice for ledger transaction lifecycle without skips or xfails; `tests/application/ledger`.

### Phase `W23.P115` - thin cli exposure

This Phase delivers thin cli exposure for ledger transaction lifecycle as required by `2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr`.

- [ ] `W23.P115.S0685` - Expose accepted command handlers for ledger transaction lifecycle under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W23.P115.S0686` - Keep argument parsing for ledger transaction lifecycle separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W23.P115.S0687` - Delegate ledger transaction lifecycle execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W23.P115.S0688` - Render ledger transaction lifecycle results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W23.P115.S0689` - Handle ledger transaction lifecycle failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W23.P115.S0690` - Validate help text for ledger transaction lifecycle uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W24` - inventory management cli design

This Wave implements the `2026-04-30-inventory-management-cli-design-adr` decision for inventory command migration. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W24.P116` - backend implementation

This Phase delivers backend implementation for inventory command migration as required by `2026-04-30-inventory-management-cli-design-adr`.

- [ ] `W24.P116.S0691` - Map the `2026-04-30-inventory-management-cli-design-adr` decision into non-CLI service ownership for inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P116.S0692` - Implement Pydantic command and result contracts for inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P116.S0693` - Wire application or domain services required by inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P116.S0694` - Connect persistence, bucket events, registry data, or provider adapters required by inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P116.S0695` - Route existing backend functionality into the canonical service for inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P116.S0696` - Record service-level error codes and log fields for inventory command migration; `src/aeat/application/inventory`.

### Phase `W24.P117` - shadow duplicate removal

This Phase delivers shadow duplicate removal for inventory command migration as required by `2026-04-30-inventory-management-cli-design-adr`.

- [ ] `W24.P117.S0697` - Audit duplicate implementations that overlap inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P117.S0698` - Delete duplicate backend branches that compete with inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P117.S0699` - Remove stale aliases that bypass the canonical service for inventory command migration; `src/aeat/entrypoints/cli`.
- [ ] `W24.P117.S0700` - Migrate internal callers to the canonical service for inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P117.S0701` - Remove stale fixtures and tests that encode duplicate behavior for inventory command migration; `tests/application/inventory`.
- [ ] `W24.P117.S0702` - Update boundary inventory entries that describe duplicate behavior for inventory command migration; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W24.P118` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for inventory command migration as required by `2026-04-30-inventory-management-cli-design-adr`.

- [ ] `W24.P118.S0703` - Delete compatibility shims that preserve rejected behavior for inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P118.S0704` - Delete placeholder stubs that claim support for inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P118.S0705` - Replace stubbed paths with real backend service calls for inventory command migration; `src/aeat/application/inventory`.
- [ ] `W24.P118.S0706` - Remove deprecated command spelling and help text for inventory command migration; `src/aeat/entrypoints/cli`.
- [ ] `W24.P118.S0707` - Remove tests that assert shim or stub behavior for inventory command migration; `tests/application/inventory`.
- [ ] `W24.P118.S0708` - Record the removed shim and stub surfaces for inventory command migration; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W24.P119` - real behavior verification

This Phase delivers real behavior verification for inventory command migration as required by `2026-04-30-inventory-management-cli-design-adr`.

- [ ] `W24.P119.S0709` - Add service contract tests for inventory command migration; `tests/application/inventory`.
- [ ] `W24.P119.S0710` - Add persistence or registry integration tests for inventory command migration; `tests/application/inventory`.
- [ ] `W24.P119.S0711` - Add negative tests proving rejected aliases do not reach inventory command migration; `tests/entrypoints/cli`.
- [ ] `W24.P119.S0712` - Add command behavior tests that exercise inventory command migration through real services; `tests/entrypoints/cli`.
- [ ] `W24.P119.S0713` - Add end-to-end workflow coverage for inventory command migration; `tests`.
- [ ] `W24.P119.S0714` - Run the targeted test slice for inventory command migration without skips or xfails; `tests/application/inventory`.

### Phase `W24.P120` - thin cli exposure

This Phase delivers thin cli exposure for inventory command migration as required by `2026-04-30-inventory-management-cli-design-adr`.

- [ ] `W24.P120.S0715` - Expose accepted command handlers for inventory command migration under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W24.P120.S0716` - Keep argument parsing for inventory command migration separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W24.P120.S0717` - Delegate inventory command migration execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W24.P120.S0718` - Render inventory command migration results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W24.P120.S0719` - Handle inventory command migration failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W24.P120.S0720` - Validate help text for inventory command migration uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W25` - inventory placement

This Wave implements the `2026-05-12-cli-workflow-redesign-inventory-placement-adr` decision for inventory command placement and backend ownership. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W25.P121` - backend implementation

This Phase delivers backend implementation for inventory command placement and backend ownership as required by `2026-05-12-cli-workflow-redesign-inventory-placement-adr`.

- [ ] `W25.P121.S0721` - Map the `2026-05-12-cli-workflow-redesign-inventory-placement-adr` decision into non-CLI service ownership for inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P121.S0722` - Implement Pydantic command and result contracts for inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P121.S0723` - Wire application or domain services required by inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P121.S0724` - Connect persistence, bucket events, registry data, or provider adapters required by inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P121.S0725` - Route existing backend functionality into the canonical service for inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P121.S0726` - Record service-level error codes and log fields for inventory command placement and backend ownership; `src/aeat/application/inventory`.

### Phase `W25.P122` - shadow duplicate removal

This Phase delivers shadow duplicate removal for inventory command placement and backend ownership as required by `2026-05-12-cli-workflow-redesign-inventory-placement-adr`.

- [ ] `W25.P122.S0727` - Audit duplicate implementations that overlap inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P122.S0728` - Delete duplicate backend branches that compete with inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P122.S0729` - Remove stale aliases that bypass the canonical service for inventory command placement and backend ownership; `src/aeat/entrypoints/cli`.
- [ ] `W25.P122.S0730` - Migrate internal callers to the canonical service for inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P122.S0731` - Remove stale fixtures and tests that encode duplicate behavior for inventory command placement and backend ownership; `tests/application/inventory`.
- [ ] `W25.P122.S0732` - Update boundary inventory entries that describe duplicate behavior for inventory command placement and backend ownership; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W25.P123` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for inventory command placement and backend ownership as required by `2026-05-12-cli-workflow-redesign-inventory-placement-adr`.

- [ ] `W25.P123.S0733` - Delete compatibility shims that preserve rejected behavior for inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P123.S0734` - Delete placeholder stubs that claim support for inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P123.S0735` - Replace stubbed paths with real backend service calls for inventory command placement and backend ownership; `src/aeat/application/inventory`.
- [ ] `W25.P123.S0736` - Remove deprecated command spelling and help text for inventory command placement and backend ownership; `src/aeat/entrypoints/cli`.
- [ ] `W25.P123.S0737` - Remove tests that assert shim or stub behavior for inventory command placement and backend ownership; `tests/application/inventory`.
- [ ] `W25.P123.S0738` - Record the removed shim and stub surfaces for inventory command placement and backend ownership; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W25.P124` - real behavior verification

This Phase delivers real behavior verification for inventory command placement and backend ownership as required by `2026-05-12-cli-workflow-redesign-inventory-placement-adr`.

- [ ] `W25.P124.S0739` - Add service contract tests for inventory command placement and backend ownership; `tests/application/inventory`.
- [ ] `W25.P124.S0740` - Add persistence or registry integration tests for inventory command placement and backend ownership; `tests/application/inventory`.
- [ ] `W25.P124.S0741` - Add negative tests proving rejected aliases do not reach inventory command placement and backend ownership; `tests/entrypoints/cli`.
- [ ] `W25.P124.S0742` - Add command behavior tests that exercise inventory command placement and backend ownership through real services; `tests/entrypoints/cli`.
- [ ] `W25.P124.S0743` - Add end-to-end workflow coverage for inventory command placement and backend ownership; `tests`.
- [ ] `W25.P124.S0744` - Run the targeted test slice for inventory command placement and backend ownership without skips or xfails; `tests/application/inventory`.

### Phase `W25.P125` - thin cli exposure

This Phase delivers thin cli exposure for inventory command placement and backend ownership as required by `2026-05-12-cli-workflow-redesign-inventory-placement-adr`.

- [ ] `W25.P125.S0745` - Expose accepted command handlers for inventory command placement and backend ownership under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W25.P125.S0746` - Keep argument parsing for inventory command placement and backend ownership separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W25.P125.S0747` - Delegate inventory command placement and backend ownership execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W25.P125.S0748` - Render inventory command placement and backend ownership results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W25.P125.S0749` - Handle inventory command placement and backend ownership failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W25.P125.S0750` - Validate help text for inventory command placement and backend ownership uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W26` - app ledger ratios shape

This Wave implements the `2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr` decision for ledger usage ratio behavior. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W26.P126` - backend implementation

This Phase delivers backend implementation for ledger usage ratio behavior as required by `2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr`.

- [ ] `W26.P126.S0751` - Map the `2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr` decision into non-CLI service ownership for ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P126.S0752` - Implement Pydantic command and result contracts for ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P126.S0753` - Wire application or domain services required by ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P126.S0754` - Connect persistence, bucket events, registry data, or provider adapters required by ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P126.S0755` - Route existing backend functionality into the canonical service for ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P126.S0756` - Record service-level error codes and log fields for ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.

### Phase `W26.P127` - shadow duplicate removal

This Phase delivers shadow duplicate removal for ledger usage ratio behavior as required by `2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr`.

- [ ] `W26.P127.S0757` - Audit duplicate implementations that overlap ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P127.S0758` - Delete duplicate backend branches that compete with ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P127.S0759` - Remove stale aliases that bypass the canonical service for ledger usage ratio behavior; `src/aeat/entrypoints/cli`.
- [ ] `W26.P127.S0760` - Migrate internal callers to the canonical service for ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P127.S0761` - Remove stale fixtures and tests that encode duplicate behavior for ledger usage ratio behavior; `tests/domain/usage_ratios`.
- [ ] `W26.P127.S0762` - Update boundary inventory entries that describe duplicate behavior for ledger usage ratio behavior; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W26.P128` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for ledger usage ratio behavior as required by `2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr`.

- [ ] `W26.P128.S0763` - Delete compatibility shims that preserve rejected behavior for ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P128.S0764` - Delete placeholder stubs that claim support for ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P128.S0765` - Replace stubbed paths with real backend service calls for ledger usage ratio behavior; `src/aeat/domain/usage_ratios`.
- [ ] `W26.P128.S0766` - Remove deprecated command spelling and help text for ledger usage ratio behavior; `src/aeat/entrypoints/cli`.
- [ ] `W26.P128.S0767` - Remove tests that assert shim or stub behavior for ledger usage ratio behavior; `tests/domain/usage_ratios`.
- [ ] `W26.P128.S0768` - Record the removed shim and stub surfaces for ledger usage ratio behavior; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W26.P129` - real behavior verification

This Phase delivers real behavior verification for ledger usage ratio behavior as required by `2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr`.

- [ ] `W26.P129.S0769` - Add service contract tests for ledger usage ratio behavior; `tests/domain/usage_ratios`.
- [ ] `W26.P129.S0770` - Add persistence or registry integration tests for ledger usage ratio behavior; `tests/domain/usage_ratios`.
- [ ] `W26.P129.S0771` - Add negative tests proving rejected aliases do not reach ledger usage ratio behavior; `tests/entrypoints/cli`.
- [ ] `W26.P129.S0772` - Add command behavior tests that exercise ledger usage ratio behavior through real services; `tests/entrypoints/cli`.
- [ ] `W26.P129.S0773` - Add end-to-end workflow coverage for ledger usage ratio behavior; `tests`.
- [ ] `W26.P129.S0774` - Run the targeted test slice for ledger usage ratio behavior without skips or xfails; `tests/domain/usage_ratios`.

### Phase `W26.P130` - thin cli exposure

This Phase delivers thin cli exposure for ledger usage ratio behavior as required by `2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr`.

- [ ] `W26.P130.S0775` - Expose accepted command handlers for ledger usage ratio behavior under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W26.P130.S0776` - Keep argument parsing for ledger usage ratio behavior separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W26.P130.S0777` - Delegate ledger usage ratio behavior execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W26.P130.S0778` - Render ledger usage ratio behavior results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W26.P130.S0779` - Handle ledger usage ratio behavior failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W26.P130.S0780` - Validate help text for ledger usage ratio behavior uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W27` - bank provider expansion

This Wave implements the `2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr` decision for bank provider import coverage. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W27.P131` - backend implementation

This Phase delivers backend implementation for bank provider import coverage as required by `2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr`.

- [ ] `W27.P131.S0781` - Map the `2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr` decision into non-CLI service ownership for bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P131.S0782` - Implement Pydantic command and result contracts for bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P131.S0783` - Wire application or domain services required by bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P131.S0784` - Connect persistence, bucket events, registry data, or provider adapters required by bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P131.S0785` - Route existing backend functionality into the canonical service for bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P131.S0786` - Record service-level error codes and log fields for bank provider import coverage; `src/aeat/adapters/inbound`.

### Phase `W27.P132` - shadow duplicate removal

This Phase delivers shadow duplicate removal for bank provider import coverage as required by `2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr`.

- [ ] `W27.P132.S0787` - Audit duplicate implementations that overlap bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P132.S0788` - Delete duplicate backend branches that compete with bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P132.S0789` - Remove stale aliases that bypass the canonical service for bank provider import coverage; `src/aeat/entrypoints/cli`.
- [ ] `W27.P132.S0790` - Migrate internal callers to the canonical service for bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P132.S0791` - Remove stale fixtures and tests that encode duplicate behavior for bank provider import coverage; `tests/adapters/inbound`.
- [ ] `W27.P132.S0792` - Update boundary inventory entries that describe duplicate behavior for bank provider import coverage; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W27.P133` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for bank provider import coverage as required by `2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr`.

- [ ] `W27.P133.S0793` - Delete compatibility shims that preserve rejected behavior for bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P133.S0794` - Delete placeholder stubs that claim support for bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P133.S0795` - Replace stubbed paths with real backend service calls for bank provider import coverage; `src/aeat/adapters/inbound`.
- [ ] `W27.P133.S0796` - Remove deprecated command spelling and help text for bank provider import coverage; `src/aeat/entrypoints/cli`.
- [ ] `W27.P133.S0797` - Remove tests that assert shim or stub behavior for bank provider import coverage; `tests/adapters/inbound`.
- [ ] `W27.P133.S0798` - Record the removed shim and stub surfaces for bank provider import coverage; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W27.P134` - real behavior verification

This Phase delivers real behavior verification for bank provider import coverage as required by `2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr`.

- [ ] `W27.P134.S0799` - Add service contract tests for bank provider import coverage; `tests/adapters/inbound`.
- [ ] `W27.P134.S0800` - Add persistence or registry integration tests for bank provider import coverage; `tests/adapters/inbound`.
- [ ] `W27.P134.S0801` - Add negative tests proving rejected aliases do not reach bank provider import coverage; `tests/entrypoints/cli`.
- [ ] `W27.P134.S0802` - Add command behavior tests that exercise bank provider import coverage through real services; `tests/entrypoints/cli`.
- [ ] `W27.P134.S0803` - Add end-to-end workflow coverage for bank provider import coverage; `tests`.
- [ ] `W27.P134.S0804` - Run the targeted test slice for bank provider import coverage without skips or xfails; `tests/adapters/inbound`.

### Phase `W27.P135` - thin cli exposure

This Phase delivers thin cli exposure for bank provider import coverage as required by `2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr`.

- [ ] `W27.P135.S0805` - Expose accepted command handlers for bank provider import coverage under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W27.P135.S0806` - Keep argument parsing for bank provider import coverage separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W27.P135.S0807` - Delegate bank provider import coverage execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W27.P135.S0808` - Render bank provider import coverage results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W27.P135.S0809` - Handle bank provider import coverage failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W27.P135.S0810` - Validate help text for bank provider import coverage uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W28` - foreign currency normalization

This Wave implements the `2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr` decision for currency normalization layer. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W28.P136` - backend implementation

This Phase delivers backend implementation for currency normalization layer as required by `2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr`.

- [ ] `W28.P136.S0811` - Map the `2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr` decision into non-CLI service ownership for currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P136.S0812` - Implement Pydantic command and result contracts for currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P136.S0813` - Wire application or domain services required by currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P136.S0814` - Connect persistence, bucket events, registry data, or provider adapters required by currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P136.S0815` - Route existing backend functionality into the canonical service for currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P136.S0816` - Record service-level error codes and log fields for currency normalization layer; `src/aeat/domain/currency`.

### Phase `W28.P137` - shadow duplicate removal

This Phase delivers shadow duplicate removal for currency normalization layer as required by `2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr`.

- [ ] `W28.P137.S0817` - Audit duplicate implementations that overlap currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P137.S0818` - Delete duplicate backend branches that compete with currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P137.S0819` - Remove stale aliases that bypass the canonical service for currency normalization layer; `src/aeat/entrypoints/cli`.
- [ ] `W28.P137.S0820` - Migrate internal callers to the canonical service for currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P137.S0821` - Remove stale fixtures and tests that encode duplicate behavior for currency normalization layer; `tests/domain/currency`.
- [ ] `W28.P137.S0822` - Update boundary inventory entries that describe duplicate behavior for currency normalization layer; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W28.P138` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for currency normalization layer as required by `2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr`.

- [ ] `W28.P138.S0823` - Delete compatibility shims that preserve rejected behavior for currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P138.S0824` - Delete placeholder stubs that claim support for currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P138.S0825` - Replace stubbed paths with real backend service calls for currency normalization layer; `src/aeat/domain/currency`.
- [ ] `W28.P138.S0826` - Remove deprecated command spelling and help text for currency normalization layer; `src/aeat/entrypoints/cli`.
- [ ] `W28.P138.S0827` - Remove tests that assert shim or stub behavior for currency normalization layer; `tests/domain/currency`.
- [ ] `W28.P138.S0828` - Record the removed shim and stub surfaces for currency normalization layer; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W28.P139` - real behavior verification

This Phase delivers real behavior verification for currency normalization layer as required by `2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr`.

- [ ] `W28.P139.S0829` - Add service contract tests for currency normalization layer; `tests/domain/currency`.
- [ ] `W28.P139.S0830` - Add persistence or registry integration tests for currency normalization layer; `tests/domain/currency`.
- [ ] `W28.P139.S0831` - Add negative tests proving rejected aliases do not reach currency normalization layer; `tests/entrypoints/cli`.
- [ ] `W28.P139.S0832` - Add command behavior tests that exercise currency normalization layer through real services; `tests/entrypoints/cli`.
- [ ] `W28.P139.S0833` - Add end-to-end workflow coverage for currency normalization layer; `tests`.
- [ ] `W28.P139.S0834` - Run the targeted test slice for currency normalization layer without skips or xfails; `tests/domain/currency`.

### Phase `W28.P140` - thin cli exposure

This Phase delivers thin cli exposure for currency normalization layer as required by `2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr`.

- [ ] `W28.P140.S0835` - Expose accepted command handlers for currency normalization layer under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W28.P140.S0836` - Keep argument parsing for currency normalization layer separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W28.P140.S0837` - Delegate currency normalization layer execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W28.P140.S0838` - Render currency normalization layer results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W28.P140.S0839` - Handle currency normalization layer failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W28.P140.S0840` - Validate help text for currency normalization layer uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W29` - receipt ocr pdf evidence

This Wave implements the `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` decision for receipt evidence extraction. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W29.P141` - backend implementation

This Phase delivers backend implementation for receipt evidence extraction as required by `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr`.

- [ ] `W29.P141.S0841` - Map the `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` decision into non-CLI service ownership for receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P141.S0842` - Implement Pydantic command and result contracts for receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P141.S0843` - Wire application or domain services required by receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P141.S0844` - Connect persistence, bucket events, registry data, or provider adapters required by receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P141.S0845` - Route existing backend functionality into the canonical service for receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P141.S0846` - Record service-level error codes and log fields for receipt evidence extraction; `src/aeat/application/evidence`.

### Phase `W29.P142` - shadow duplicate removal

This Phase delivers shadow duplicate removal for receipt evidence extraction as required by `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr`.

- [ ] `W29.P142.S0847` - Audit duplicate implementations that overlap receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P142.S0848` - Delete duplicate backend branches that compete with receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P142.S0849` - Remove stale aliases that bypass the canonical service for receipt evidence extraction; `src/aeat/entrypoints/cli`.
- [ ] `W29.P142.S0850` - Migrate internal callers to the canonical service for receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P142.S0851` - Remove stale fixtures and tests that encode duplicate behavior for receipt evidence extraction; `tests/application/evidence`.
- [ ] `W29.P142.S0852` - Update boundary inventory entries that describe duplicate behavior for receipt evidence extraction; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W29.P143` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for receipt evidence extraction as required by `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr`.

- [ ] `W29.P143.S0853` - Delete compatibility shims that preserve rejected behavior for receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P143.S0854` - Delete placeholder stubs that claim support for receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P143.S0855` - Replace stubbed paths with real backend service calls for receipt evidence extraction; `src/aeat/application/evidence`.
- [ ] `W29.P143.S0856` - Remove deprecated command spelling and help text for receipt evidence extraction; `src/aeat/entrypoints/cli`.
- [ ] `W29.P143.S0857` - Remove tests that assert shim or stub behavior for receipt evidence extraction; `tests/application/evidence`.
- [ ] `W29.P143.S0858` - Record the removed shim and stub surfaces for receipt evidence extraction; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W29.P144` - real behavior verification

This Phase delivers real behavior verification for receipt evidence extraction as required by `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr`.

- [ ] `W29.P144.S0859` - Add service contract tests for receipt evidence extraction; `tests/application/evidence`.
- [ ] `W29.P144.S0860` - Add persistence or registry integration tests for receipt evidence extraction; `tests/application/evidence`.
- [ ] `W29.P144.S0861` - Add negative tests proving rejected aliases do not reach receipt evidence extraction; `tests/entrypoints/cli`.
- [ ] `W29.P144.S0862` - Add command behavior tests that exercise receipt evidence extraction through real services; `tests/entrypoints/cli`.
- [ ] `W29.P144.S0863` - Add end-to-end workflow coverage for receipt evidence extraction; `tests`.
- [ ] `W29.P144.S0864` - Run the targeted test slice for receipt evidence extraction without skips or xfails; `tests/application/evidence`.

### Phase `W29.P145` - thin cli exposure

This Phase delivers thin cli exposure for receipt evidence extraction as required by `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr`.

- [ ] `W29.P145.S0865` - Expose accepted command handlers for receipt evidence extraction under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W29.P145.S0866` - Keep argument parsing for receipt evidence extraction separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W29.P145.S0867` - Delegate receipt evidence extraction execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W29.P145.S0868` - Render receipt evidence extraction results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W29.P145.S0869` - Handle receipt evidence extraction failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W29.P145.S0870` - Validate help text for receipt evidence extraction uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W30` - libros boe format exporters

This Wave implements the `2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr` decision for official ledger book export. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W30.P146` - backend implementation

This Phase delivers backend implementation for official ledger book export as required by `2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr`.

- [ ] `W30.P146.S0871` - Map the `2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr` decision into non-CLI service ownership for official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P146.S0872` - Implement Pydantic command and result contracts for official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P146.S0873` - Wire application or domain services required by official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P146.S0874` - Connect persistence, bucket events, registry data, or provider adapters required by official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P146.S0875` - Route existing backend functionality into the canonical service for official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P146.S0876` - Record service-level error codes and log fields for official ledger book export; `src/aeat/application/export`.

### Phase `W30.P147` - shadow duplicate removal

This Phase delivers shadow duplicate removal for official ledger book export as required by `2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr`.

- [ ] `W30.P147.S0877` - Audit duplicate implementations that overlap official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P147.S0878` - Delete duplicate backend branches that compete with official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P147.S0879` - Remove stale aliases that bypass the canonical service for official ledger book export; `src/aeat/entrypoints/cli`.
- [ ] `W30.P147.S0880` - Migrate internal callers to the canonical service for official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P147.S0881` - Remove stale fixtures and tests that encode duplicate behavior for official ledger book export; `tests/application/export`.
- [ ] `W30.P147.S0882` - Update boundary inventory entries that describe duplicate behavior for official ledger book export; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W30.P148` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for official ledger book export as required by `2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr`.

- [ ] `W30.P148.S0883` - Delete compatibility shims that preserve rejected behavior for official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P148.S0884` - Delete placeholder stubs that claim support for official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P148.S0885` - Replace stubbed paths with real backend service calls for official ledger book export; `src/aeat/application/export`.
- [ ] `W30.P148.S0886` - Remove deprecated command spelling and help text for official ledger book export; `src/aeat/entrypoints/cli`.
- [ ] `W30.P148.S0887` - Remove tests that assert shim or stub behavior for official ledger book export; `tests/application/export`.
- [ ] `W30.P148.S0888` - Record the removed shim and stub surfaces for official ledger book export; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W30.P149` - real behavior verification

This Phase delivers real behavior verification for official ledger book export as required by `2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr`.

- [ ] `W30.P149.S0889` - Add service contract tests for official ledger book export; `tests/application/export`.
- [ ] `W30.P149.S0890` - Add persistence or registry integration tests for official ledger book export; `tests/application/export`.
- [ ] `W30.P149.S0891` - Add negative tests proving rejected aliases do not reach official ledger book export; `tests/entrypoints/cli`.
- [ ] `W30.P149.S0892` - Add command behavior tests that exercise official ledger book export through real services; `tests/entrypoints/cli`.
- [ ] `W30.P149.S0893` - Add end-to-end workflow coverage for official ledger book export; `tests`.
- [ ] `W30.P149.S0894` - Run the targeted test slice for official ledger book export without skips or xfails; `tests/application/export`.

### Phase `W30.P150` - thin cli exposure

This Phase delivers thin cli exposure for official ledger book export as required by `2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr`.

- [ ] `W30.P150.S0895` - Expose accepted command handlers for official ledger book export under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W30.P150.S0896` - Keep argument parsing for official ledger book export separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W30.P150.S0897` - Delegate official ledger book export execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W30.P150.S0898` - Render official ledger book export results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W30.P150.S0899` - Handle official ledger book export failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W30.P150.S0900` - Validate help text for official ledger book export uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W31` - domain harvest normatives

This Wave implements the `2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr` decision for normative and manual harvest. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W31.P151` - backend implementation

This Phase delivers backend implementation for normative and manual harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr`.

- [ ] `W31.P151.S0901` - Map the `2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr` decision into non-CLI service ownership for normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P151.S0902` - Implement Pydantic command and result contracts for normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P151.S0903` - Wire application or domain services required by normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P151.S0904` - Connect persistence, bucket events, registry data, or provider adapters required by normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P151.S0905` - Route existing backend functionality into the canonical service for normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P151.S0906` - Record service-level error codes and log fields for normative and manual harvest; `src/aeat/domain/normatives`.

### Phase `W31.P152` - shadow duplicate removal

This Phase delivers shadow duplicate removal for normative and manual harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr`.

- [ ] `W31.P152.S0907` - Audit duplicate implementations that overlap normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P152.S0908` - Delete duplicate backend branches that compete with normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P152.S0909` - Remove stale aliases that bypass the canonical service for normative and manual harvest; `src/aeat/entrypoints/cli`.
- [ ] `W31.P152.S0910` - Migrate internal callers to the canonical service for normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P152.S0911` - Remove stale fixtures and tests that encode duplicate behavior for normative and manual harvest; `tests/domain/normatives`.
- [ ] `W31.P152.S0912` - Update boundary inventory entries that describe duplicate behavior for normative and manual harvest; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W31.P153` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for normative and manual harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr`.

- [ ] `W31.P153.S0913` - Delete compatibility shims that preserve rejected behavior for normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P153.S0914` - Delete placeholder stubs that claim support for normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P153.S0915` - Replace stubbed paths with real backend service calls for normative and manual harvest; `src/aeat/domain/normatives`.
- [ ] `W31.P153.S0916` - Remove deprecated command spelling and help text for normative and manual harvest; `src/aeat/entrypoints/cli`.
- [ ] `W31.P153.S0917` - Remove tests that assert shim or stub behavior for normative and manual harvest; `tests/domain/normatives`.
- [ ] `W31.P153.S0918` - Record the removed shim and stub surfaces for normative and manual harvest; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W31.P154` - real behavior verification

This Phase delivers real behavior verification for normative and manual harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr`.

- [ ] `W31.P154.S0919` - Add service contract tests for normative and manual harvest; `tests/domain/normatives`.
- [ ] `W31.P154.S0920` - Add persistence or registry integration tests for normative and manual harvest; `tests/domain/normatives`.
- [ ] `W31.P154.S0921` - Add negative tests proving rejected aliases do not reach normative and manual harvest; `tests/entrypoints/cli`.
- [ ] `W31.P154.S0922` - Add command behavior tests that exercise normative and manual harvest through real services; `tests/entrypoints/cli`.
- [ ] `W31.P154.S0923` - Add end-to-end workflow coverage for normative and manual harvest; `tests`.
- [ ] `W31.P154.S0924` - Run the targeted test slice for normative and manual harvest without skips or xfails; `tests/domain/normatives`.

### Phase `W31.P155` - thin cli exposure

This Phase delivers thin cli exposure for normative and manual harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr`.

- [ ] `W31.P155.S0925` - Expose accepted command handlers for normative and manual harvest under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W31.P155.S0926` - Keep argument parsing for normative and manual harvest separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W31.P155.S0927` - Delegate normative and manual harvest execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W31.P155.S0928` - Render normative and manual harvest results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W31.P155.S0929` - Handle normative and manual harvest failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W31.P155.S0930` - Validate help text for normative and manual harvest uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W32` - domain harvest vat classification

This Wave implements the `2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr` decision for vat classification harvest. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W32.P156` - backend implementation

This Phase delivers backend implementation for vat classification harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr`.

- [x] `W32.P156.S0931` - Map the `2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr` decision into non-CLI service ownership for vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P156.S0932` - Implement Pydantic command and result contracts for vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P156.S0933` - Wire application or domain services required by vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P156.S0934` - Connect persistence, bucket events, registry data, or provider adapters required by vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P156.S0935` - Route existing backend functionality into the canonical service for vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P156.S0936` - Record service-level error codes and log fields for vat classification harvest; `src/aeat/domain/vat`.

### Phase `W32.P157` - shadow duplicate removal

This Phase delivers shadow duplicate removal for vat classification harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr`.

- [x] `W32.P157.S0937` - Audit duplicate implementations that overlap vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P157.S0938` - Delete duplicate backend branches that compete with vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P157.S0939` - Remove stale aliases that bypass the canonical service for vat classification harvest; `src/aeat/entrypoints/cli`.
- [x] `W32.P157.S0940` - Migrate internal callers to the canonical service for vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P157.S0941` - Remove stale fixtures and tests that encode duplicate behavior for vat classification harvest; `tests/domain/vat`.
- [x] `W32.P157.S0942` - Update boundary inventory entries that describe duplicate behavior for vat classification harvest; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W32.P158` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for vat classification harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr`.

- [x] `W32.P158.S0943` - Delete compatibility shims that preserve rejected behavior for vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P158.S0944` - Delete placeholder stubs that claim support for vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P158.S0945` - Replace stubbed paths with real backend service calls for vat classification harvest; `src/aeat/domain/vat`.
- [x] `W32.P158.S0946` - Remove deprecated command spelling and help text for vat classification harvest; `src/aeat/entrypoints/cli`.
- [x] `W32.P158.S0947` - Remove tests that assert shim or stub behavior for vat classification harvest; `tests/domain/vat`.
- [x] `W32.P158.S0948` - Record the removed shim and stub surfaces for vat classification harvest; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W32.P159` - real behavior verification

This Phase delivers real behavior verification for vat classification harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr`.

- [x] `W32.P159.S0949` - Add service contract tests for vat classification harvest; `tests/domain/vat`.
- [x] `W32.P159.S0950` - Add persistence or registry integration tests for vat classification harvest; `tests/domain/vat`.
- [x] `W32.P159.S0951` - Add negative tests proving rejected aliases do not reach vat classification harvest; `tests/entrypoints/cli`.
- [x] `W32.P159.S0952` - Add command behavior tests that exercise vat classification harvest through real services; `tests/entrypoints/cli`.
- [x] `W32.P159.S0953` - Add end-to-end workflow coverage for vat classification harvest; `tests`.
- [x] `W32.P159.S0954` - Run the targeted test slice for vat classification harvest without skips or xfails; `tests/domain/vat`.

### Phase `W32.P160` - thin cli exposure

This Phase delivers thin cli exposure for vat classification harvest as required by `2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr`.

- [x] `W32.P160.S0955` - Expose accepted command handlers for vat classification harvest under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W32.P160.S0956` - Keep argument parsing for vat classification harvest separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W32.P160.S0957` - Delegate vat classification harvest execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W32.P160.S0958` - Render vat classification harvest results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W32.P160.S0959` - Handle vat classification harvest failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W32.P160.S0960` - Validate help text for vat classification harvest uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W33` - domain harvest oss ioss

This Wave implements the `2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr` decision for oss and ioss calculation facts. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W33.P161` - backend implementation

This Phase delivers backend implementation for oss and ioss calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr`.

- [x] `W33.P161.S0961` - Map the `2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr` decision into non-CLI service ownership for oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P161.S0962` - Implement Pydantic command and result contracts for oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P161.S0963` - Wire application or domain services required by oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P161.S0964` - Connect persistence, bucket events, registry data, or provider adapters required by oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P161.S0965` - Route existing backend functionality into the canonical service for oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P161.S0966` - Record service-level error codes and log fields for oss and ioss calculation facts; `src/aeat/domain/vat`.

### Phase `W33.P162` - shadow duplicate removal

This Phase delivers shadow duplicate removal for oss and ioss calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr`.

- [x] `W33.P162.S0967` - Audit duplicate implementations that overlap oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P162.S0968` - Delete duplicate backend branches that compete with oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P162.S0969` - Remove stale aliases that bypass the canonical service for oss and ioss calculation facts; `src/aeat/entrypoints/cli`.
- [x] `W33.P162.S0970` - Migrate internal callers to the canonical service for oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P162.S0971` - Remove stale fixtures and tests that encode duplicate behavior for oss and ioss calculation facts; `tests/domain/vat`.
- [x] `W33.P162.S0972` - Update boundary inventory entries that describe duplicate behavior for oss and ioss calculation facts; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W33.P163` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for oss and ioss calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr`.

- [x] `W33.P163.S0973` - Delete compatibility shims that preserve rejected behavior for oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P163.S0974` - Delete placeholder stubs that claim support for oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P163.S0975` - Replace stubbed paths with real backend service calls for oss and ioss calculation facts; `src/aeat/domain/vat`.
- [x] `W33.P163.S0976` - Remove deprecated command spelling and help text for oss and ioss calculation facts; `src/aeat/entrypoints/cli`.
- [x] `W33.P163.S0977` - Remove tests that assert shim or stub behavior for oss and ioss calculation facts; `tests/domain/vat`.
- [x] `W33.P163.S0978` - Record the removed shim and stub surfaces for oss and ioss calculation facts; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W33.P164` - real behavior verification

This Phase delivers real behavior verification for oss and ioss calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr`.

- [x] `W33.P164.S0979` - Add service contract tests for oss and ioss calculation facts; `tests/domain/vat`.
- [x] `W33.P164.S0980` - Add persistence or registry integration tests for oss and ioss calculation facts; `tests/domain/vat`.
- [x] `W33.P164.S0981` - Add negative tests proving rejected aliases do not reach oss and ioss calculation facts; `tests/entrypoints/cli`.
- [x] `W33.P164.S0982` - Add command behavior tests that exercise oss and ioss calculation facts through real services; `tests/entrypoints/cli`.
- [x] `W33.P164.S0983` - Add end-to-end workflow coverage for oss and ioss calculation facts; `tests`.
- [x] `W33.P164.S0984` - Run the targeted test slice for oss and ioss calculation facts without skips or xfails; `tests/domain/vat`.

### Phase `W33.P165` - thin cli exposure

This Phase delivers thin cli exposure for oss and ioss calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr`.

- [x] `W33.P165.S0985` - Expose accepted command handlers for oss and ioss calculation facts under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W33.P165.S0986` - Keep argument parsing for oss and ioss calculation facts separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W33.P165.S0987` - Delegate oss and ioss calculation facts execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W33.P165.S0988` - Render oss and ioss calculation facts results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W33.P165.S0989` - Handle oss and ioss calculation facts failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W33.P165.S0990` - Validate help text for oss and ioss calculation facts uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W34` - domain harvest rental

This Wave implements the `2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr` decision for rental calculation facts. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W34.P166` - backend implementation

This Phase delivers backend implementation for rental calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr`.

- [ ] `W34.P166.S0991` - Map the `2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr` decision into non-CLI service ownership for rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P166.S0992` - Implement Pydantic command and result contracts for rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P166.S0993` - Wire application or domain services required by rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P166.S0994` - Connect persistence, bucket events, registry data, or provider adapters required by rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P166.S0995` - Route existing backend functionality into the canonical service for rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P166.S0996` - Record service-level error codes and log fields for rental calculation facts; `src/aeat/domain/rental`.

### Phase `W34.P167` - shadow duplicate removal

This Phase delivers shadow duplicate removal for rental calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr`.

- [ ] `W34.P167.S0997` - Audit duplicate implementations that overlap rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P167.S0998` - Delete duplicate backend branches that compete with rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P167.S0999` - Remove stale aliases that bypass the canonical service for rental calculation facts; `src/aeat/entrypoints/cli`.
- [ ] `W34.P167.S1000` - Migrate internal callers to the canonical service for rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P167.S1001` - Remove stale fixtures and tests that encode duplicate behavior for rental calculation facts; `tests/domain/rental`.
- [ ] `W34.P167.S1002` - Update boundary inventory entries that describe duplicate behavior for rental calculation facts; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W34.P168` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for rental calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr`.

- [ ] `W34.P168.S1003` - Delete compatibility shims that preserve rejected behavior for rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P168.S1004` - Delete placeholder stubs that claim support for rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P168.S1005` - Replace stubbed paths with real backend service calls for rental calculation facts; `src/aeat/domain/rental`.
- [ ] `W34.P168.S1006` - Remove deprecated command spelling and help text for rental calculation facts; `src/aeat/entrypoints/cli`.
- [ ] `W34.P168.S1007` - Remove tests that assert shim or stub behavior for rental calculation facts; `tests/domain/rental`.
- [ ] `W34.P168.S1008` - Record the removed shim and stub surfaces for rental calculation facts; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W34.P169` - real behavior verification

This Phase delivers real behavior verification for rental calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr`.

- [ ] `W34.P169.S1009` - Add service contract tests for rental calculation facts; `tests/domain/rental`.
- [ ] `W34.P169.S1010` - Add persistence or registry integration tests for rental calculation facts; `tests/domain/rental`.
- [ ] `W34.P169.S1011` - Add negative tests proving rejected aliases do not reach rental calculation facts; `tests/entrypoints/cli`.
- [ ] `W34.P169.S1012` - Add command behavior tests that exercise rental calculation facts through real services; `tests/entrypoints/cli`.
- [ ] `W34.P169.S1013` - Add end-to-end workflow coverage for rental calculation facts; `tests`.
- [ ] `W34.P169.S1014` - Run the targeted test slice for rental calculation facts without skips or xfails; `tests/domain/rental`.

### Phase `W34.P170` - thin cli exposure

This Phase delivers thin cli exposure for rental calculation facts as required by `2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr`.

- [ ] `W34.P170.S1015` - Expose accepted command handlers for rental calculation facts under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W34.P170.S1016` - Keep argument parsing for rental calculation facts separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W34.P170.S1017` - Delegate rental calculation facts execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W34.P170.S1018` - Render rental calculation facts results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W34.P170.S1019` - Handle rental calculation facts failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W34.P170.S1020` - Validate help text for rental calculation facts uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W35` - domain portals harvest

This Wave implements the `2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr` decision for portal reference catalog. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W35.P171` - backend implementation

This Phase delivers backend implementation for portal reference catalog as required by `2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr`.

- [ ] `W35.P171.S1021` - Map the `2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr` decision into non-CLI service ownership for portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P171.S1022` - Implement Pydantic command and result contracts for portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P171.S1023` - Wire application or domain services required by portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P171.S1024` - Connect persistence, bucket events, registry data, or provider adapters required by portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P171.S1025` - Route existing backend functionality into the canonical service for portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P171.S1026` - Record service-level error codes and log fields for portal reference catalog; `src/aeat/domain/portals`.

### Phase `W35.P172` - shadow duplicate removal

This Phase delivers shadow duplicate removal for portal reference catalog as required by `2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr`.

- [ ] `W35.P172.S1027` - Audit duplicate implementations that overlap portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P172.S1028` - Delete duplicate backend branches that compete with portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P172.S1029` - Remove stale aliases that bypass the canonical service for portal reference catalog; `src/aeat/entrypoints/cli`.
- [ ] `W35.P172.S1030` - Migrate internal callers to the canonical service for portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P172.S1031` - Remove stale fixtures and tests that encode duplicate behavior for portal reference catalog; `tests/domain/portals`.
- [ ] `W35.P172.S1032` - Update boundary inventory entries that describe duplicate behavior for portal reference catalog; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W35.P173` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for portal reference catalog as required by `2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr`.

- [ ] `W35.P173.S1033` - Delete compatibility shims that preserve rejected behavior for portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P173.S1034` - Delete placeholder stubs that claim support for portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P173.S1035` - Replace stubbed paths with real backend service calls for portal reference catalog; `src/aeat/domain/portals`.
- [ ] `W35.P173.S1036` - Remove deprecated command spelling and help text for portal reference catalog; `src/aeat/entrypoints/cli`.
- [ ] `W35.P173.S1037` - Remove tests that assert shim or stub behavior for portal reference catalog; `tests/domain/portals`.
- [ ] `W35.P173.S1038` - Record the removed shim and stub surfaces for portal reference catalog; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W35.P174` - real behavior verification

This Phase delivers real behavior verification for portal reference catalog as required by `2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr`.

- [ ] `W35.P174.S1039` - Add service contract tests for portal reference catalog; `tests/domain/portals`.
- [ ] `W35.P174.S1040` - Add persistence or registry integration tests for portal reference catalog; `tests/domain/portals`.
- [ ] `W35.P174.S1041` - Add negative tests proving rejected aliases do not reach portal reference catalog; `tests/entrypoints/cli`.
- [ ] `W35.P174.S1042` - Add command behavior tests that exercise portal reference catalog through real services; `tests/entrypoints/cli`.
- [ ] `W35.P174.S1043` - Add end-to-end workflow coverage for portal reference catalog; `tests`.
- [ ] `W35.P174.S1044` - Run the targeted test slice for portal reference catalog without skips or xfails; `tests/domain/portals`.

### Phase `W35.P175` - thin cli exposure

This Phase delivers thin cli exposure for portal reference catalog as required by `2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr`.

- [ ] `W35.P175.S1045` - Expose accepted command handlers for portal reference catalog under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W35.P175.S1046` - Keep argument parsing for portal reference catalog separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W35.P175.S1047` - Delegate portal reference catalog execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W35.P175.S1048` - Render portal reference catalog results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W35.P175.S1049` - Handle portal reference catalog failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W35.P175.S1050` - Validate help text for portal reference catalog uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W36` - iva prorrata art 101 103

This Wave implements the `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr` decision for legal iva prorrata. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W36.P176` - backend implementation

This Phase delivers backend implementation for legal iva prorrata as required by `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr`.

- [x] `W36.P176.S1051` - Map the `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr` decision into non-CLI service ownership for legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P176.S1052` - Implement Pydantic command and result contracts for legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P176.S1053` - Wire application or domain services required by legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P176.S1054` - Connect persistence, bucket events, registry data, or provider adapters required by legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P176.S1055` - Route existing backend functionality into the canonical service for legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P176.S1056` - Record service-level error codes and log fields for legal iva prorrata; `src/aeat/domain/vat`.

### Phase `W36.P177` - shadow duplicate removal

This Phase delivers shadow duplicate removal for legal iva prorrata as required by `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr`.

- [x] `W36.P177.S1057` - Audit duplicate implementations that overlap legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P177.S1058` - Delete duplicate backend branches that compete with legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P177.S1059` - Remove stale aliases that bypass the canonical service for legal iva prorrata; `src/aeat/entrypoints/cli`.
- [x] `W36.P177.S1060` - Migrate internal callers to the canonical service for legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P177.S1061` - Remove stale fixtures and tests that encode duplicate behavior for legal iva prorrata; `tests/domain/vat`.
- [x] `W36.P177.S1062` - Update boundary inventory entries that describe duplicate behavior for legal iva prorrata; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W36.P178` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for legal iva prorrata as required by `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr`.

- [x] `W36.P178.S1063` - Delete compatibility shims that preserve rejected behavior for legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P178.S1064` - Delete placeholder stubs that claim support for legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P178.S1065` - Replace stubbed paths with real backend service calls for legal iva prorrata; `src/aeat/domain/vat`.
- [x] `W36.P178.S1066` - Remove deprecated command spelling and help text for legal iva prorrata; `src/aeat/entrypoints/cli`.
- [x] `W36.P178.S1067` - Remove tests that assert shim or stub behavior for legal iva prorrata; `tests/domain/vat`.
- [x] `W36.P178.S1068` - Record the removed shim and stub surfaces for legal iva prorrata; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W36.P179` - real behavior verification

This Phase delivers real behavior verification for legal iva prorrata as required by `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr`.

- [x] `W36.P179.S1069` - Add service contract tests for legal iva prorrata; `tests/domain/vat`.
- [x] `W36.P179.S1070` - Add persistence or registry integration tests for legal iva prorrata; `tests/domain/vat`.
- [x] `W36.P179.S1071` - Add negative tests proving rejected aliases do not reach legal iva prorrata; `tests/entrypoints/cli`.
- [x] `W36.P179.S1072` - Add command behavior tests that exercise legal iva prorrata through real services; `tests/entrypoints/cli`.
- [x] `W36.P179.S1073` - Add end-to-end workflow coverage for legal iva prorrata; `tests`.
- [x] `W36.P179.S1074` - Run the targeted test slice for legal iva prorrata without skips or xfails; `tests/domain/vat`.

### Phase `W36.P180` - thin cli exposure

This Phase delivers thin cli exposure for legal iva prorrata as required by `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr`.

- [x] `W36.P180.S1075` - Expose accepted command handlers for legal iva prorrata under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W36.P180.S1076` - Keep argument parsing for legal iva prorrata separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W36.P180.S1077` - Delegate legal iva prorrata execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W36.P180.S1078` - Render legal iva prorrata results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W36.P180.S1079` - Handle legal iva prorrata failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W36.P180.S1080` - Validate help text for legal iva prorrata uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W37` - festivos deadline shift

This Wave implements the `2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr` decision for business day deadline shift. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W37.P181` - backend implementation

This Phase delivers backend implementation for business day deadline shift as required by `2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr`.

- [x] `W37.P181.S1081` - Map the `2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr` decision into non-CLI service ownership for business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P181.S1082` - Implement Pydantic command and result contracts for business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P181.S1083` - Wire application or domain services required by business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P181.S1084` - Connect persistence, bucket events, registry data, or provider adapters required by business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P181.S1085` - Route existing backend functionality into the canonical service for business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P181.S1086` - Record service-level error codes and log fields for business day deadline shift; `src/aeat/domain/deadlines`.

### Phase `W37.P182` - shadow duplicate removal

This Phase delivers shadow duplicate removal for business day deadline shift as required by `2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr`.

- [x] `W37.P182.S1087` - Audit duplicate implementations that overlap business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P182.S1088` - Delete duplicate backend branches that compete with business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P182.S1089` - Remove stale aliases that bypass the canonical service for business day deadline shift; `src/aeat/entrypoints/cli`.
- [x] `W37.P182.S1090` - Migrate internal callers to the canonical service for business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P182.S1091` - Remove stale fixtures and tests that encode duplicate behavior for business day deadline shift; `tests/domain/deadlines`.
- [x] `W37.P182.S1092` - Update boundary inventory entries that describe duplicate behavior for business day deadline shift; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W37.P183` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for business day deadline shift as required by `2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr`.

- [x] `W37.P183.S1093` - Delete compatibility shims that preserve rejected behavior for business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P183.S1094` - Delete placeholder stubs that claim support for business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P183.S1095` - Replace stubbed paths with real backend service calls for business day deadline shift; `src/aeat/domain/deadlines`.
- [x] `W37.P183.S1096` - Remove deprecated command spelling and help text for business day deadline shift; `src/aeat/entrypoints/cli`.
- [x] `W37.P183.S1097` - Remove tests that assert shim or stub behavior for business day deadline shift; `tests/domain/deadlines`.
- [x] `W37.P183.S1098` - Record the removed shim and stub surfaces for business day deadline shift; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W37.P184` - real behavior verification

This Phase delivers real behavior verification for business day deadline shift as required by `2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr`.

- [x] `W37.P184.S1099` - Add service contract tests for business day deadline shift; `tests/domain/deadlines`.
- [x] `W37.P184.S1100` - Add persistence or registry integration tests for business day deadline shift; `tests/domain/deadlines`.
- [x] `W37.P184.S1101` - Add negative tests proving rejected aliases do not reach business day deadline shift; `tests/entrypoints/cli`.
- [x] `W37.P184.S1102` - Add command behavior tests that exercise business day deadline shift through real services; `tests/entrypoints/cli`.
- [x] `W37.P184.S1103` - Add end-to-end workflow coverage for business day deadline shift; `tests`.
- [x] `W37.P184.S1104` - Run the targeted test slice for business day deadline shift without skips or xfails; `tests/domain/deadlines`.

### Phase `W37.P185` - thin cli exposure

This Phase delivers thin cli exposure for business day deadline shift as required by `2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr`.

- [x] `W37.P185.S1105` - Expose accepted command handlers for business day deadline shift under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W37.P185.S1106` - Keep argument parsing for business day deadline shift separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W37.P185.S1107` - Delegate business day deadline shift execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W37.P185.S1108` - Render business day deadline shift results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W37.P185.S1109` - Handle business day deadline shift failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W37.P185.S1110` - Validate help text for business day deadline shift uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W38` - modelo work units

This Wave implements the `2026-05-12-cli-workflow-redesign-modelo-work-units-adr` decision for modelo work unit lifecycle. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W38.P186` - backend implementation

This Phase delivers backend implementation for modelo work unit lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-work-units-adr`.

- [x] `W38.P186.S1111` - Map the `2026-05-12-cli-workflow-redesign-modelo-work-units-adr` decision into non-CLI service ownership for modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P186.S1112` - Implement Pydantic command and result contracts for modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P186.S1113` - Wire application or domain services required by modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P186.S1114` - Connect persistence, bucket events, registry data, or provider adapters required by modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P186.S1115` - Route existing backend functionality into the canonical service for modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P186.S1116` - Record service-level error codes and log fields for modelo work unit lifecycle; `src/aeat/application/modelo`.

### Phase `W38.P187` - shadow duplicate removal

This Phase delivers shadow duplicate removal for modelo work unit lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-work-units-adr`.

- [x] `W38.P187.S1117` - Audit duplicate implementations that overlap modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P187.S1118` - Delete duplicate backend branches that compete with modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P187.S1119` - Remove stale aliases that bypass the canonical service for modelo work unit lifecycle; `src/aeat/entrypoints/cli`.
- [x] `W38.P187.S1120` - Migrate internal callers to the canonical service for modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P187.S1121` - Remove stale fixtures and tests that encode duplicate behavior for modelo work unit lifecycle; `tests/application/modelo`.
- [x] `W38.P187.S1122` - Update boundary inventory entries that describe duplicate behavior for modelo work unit lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W38.P188` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for modelo work unit lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-work-units-adr`.

- [x] `W38.P188.S1123` - Delete compatibility shims that preserve rejected behavior for modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P188.S1124` - Delete placeholder stubs that claim support for modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P188.S1125` - Replace stubbed paths with real backend service calls for modelo work unit lifecycle; `src/aeat/application/modelo`.
- [x] `W38.P188.S1126` - Remove deprecated command spelling and help text for modelo work unit lifecycle; `src/aeat/entrypoints/cli`.
- [x] `W38.P188.S1127` - Remove tests that assert shim or stub behavior for modelo work unit lifecycle; `tests/application/modelo`.
- [x] `W38.P188.S1128` - Record the removed shim and stub surfaces for modelo work unit lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W38.P189` - real behavior verification

This Phase delivers real behavior verification for modelo work unit lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-work-units-adr`.

- [x] `W38.P189.S1129` - Add service contract tests for modelo work unit lifecycle; `tests/application/modelo`.
- [x] `W38.P189.S1130` - Add persistence or registry integration tests for modelo work unit lifecycle; `tests/application/modelo`.
- [x] `W38.P189.S1131` - Add negative tests proving rejected aliases do not reach modelo work unit lifecycle; `tests/entrypoints/cli`.
- [x] `W38.P189.S1132` - Add command behavior tests that exercise modelo work unit lifecycle through real services; `tests/entrypoints/cli`.
- [x] `W38.P189.S1133` - Add end-to-end workflow coverage for modelo work unit lifecycle; `tests`.
- [x] `W38.P189.S1134` - Run the targeted test slice for modelo work unit lifecycle without skips or xfails; `tests/application/modelo`.

### Phase `W38.P190` - thin cli exposure

This Phase delivers thin cli exposure for modelo work unit lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-work-units-adr`.

- [x] `W38.P190.S1135` - Expose accepted command handlers for modelo work unit lifecycle under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W38.P190.S1136` - Keep argument parsing for modelo work unit lifecycle separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W38.P190.S1137` - Delegate modelo work unit lifecycle execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W38.P190.S1138` - Render modelo work unit lifecycle results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W38.P190.S1139` - Handle modelo work unit lifecycle failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W38.P190.S1140` - Validate help text for modelo work unit lifecycle uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W39` - modelo calculate revisions

This Wave implements the `2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr` decision for modelo calculation revisions. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W39.P191` - backend implementation

This Phase delivers backend implementation for modelo calculation revisions as required by `2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr`.

- [ ] `W39.P191.S1141` - Map the `2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr` decision into non-CLI service ownership for modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P191.S1142` - Implement Pydantic command and result contracts for modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P191.S1143` - Wire application or domain services required by modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P191.S1144` - Connect persistence, bucket events, registry data, or provider adapters required by modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P191.S1145` - Route existing backend functionality into the canonical service for modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P191.S1146` - Record service-level error codes and log fields for modelo calculation revisions; `src/aeat/application/modelo`.

### Phase `W39.P192` - shadow duplicate removal

This Phase delivers shadow duplicate removal for modelo calculation revisions as required by `2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr`.

- [ ] `W39.P192.S1147` - Audit duplicate implementations that overlap modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P192.S1148` - Delete duplicate backend branches that compete with modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P192.S1149` - Remove stale aliases that bypass the canonical service for modelo calculation revisions; `src/aeat/entrypoints/cli`.
- [ ] `W39.P192.S1150` - Migrate internal callers to the canonical service for modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P192.S1151` - Remove stale fixtures and tests that encode duplicate behavior for modelo calculation revisions; `tests/application/modelo`.
- [ ] `W39.P192.S1152` - Update boundary inventory entries that describe duplicate behavior for modelo calculation revisions; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W39.P193` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for modelo calculation revisions as required by `2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr`.

- [ ] `W39.P193.S1153` - Delete compatibility shims that preserve rejected behavior for modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P193.S1154` - Delete placeholder stubs that claim support for modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P193.S1155` - Replace stubbed paths with real backend service calls for modelo calculation revisions; `src/aeat/application/modelo`.
- [ ] `W39.P193.S1156` - Remove deprecated command spelling and help text for modelo calculation revisions; `src/aeat/entrypoints/cli`.
- [ ] `W39.P193.S1157` - Remove tests that assert shim or stub behavior for modelo calculation revisions; `tests/application/modelo`.
- [ ] `W39.P193.S1158` - Record the removed shim and stub surfaces for modelo calculation revisions; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W39.P194` - real behavior verification

This Phase delivers real behavior verification for modelo calculation revisions as required by `2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr`.

- [ ] `W39.P194.S1159` - Add service contract tests for modelo calculation revisions; `tests/application/modelo`.
- [ ] `W39.P194.S1160` - Add persistence or registry integration tests for modelo calculation revisions; `tests/application/modelo`.
- [ ] `W39.P194.S1161` - Add negative tests proving rejected aliases do not reach modelo calculation revisions; `tests/entrypoints/cli`.
- [ ] `W39.P194.S1162` - Add command behavior tests that exercise modelo calculation revisions through real services; `tests/entrypoints/cli`.
- [ ] `W39.P194.S1163` - Add end-to-end workflow coverage for modelo calculation revisions; `tests`.
- [ ] `W39.P194.S1164` - Run the targeted test slice for modelo calculation revisions without skips or xfails; `tests/application/modelo`.

### Phase `W39.P195` - thin cli exposure

This Phase delivers thin cli exposure for modelo calculation revisions as required by `2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr`.

- [ ] `W39.P195.S1165` - Expose accepted command handlers for modelo calculation revisions under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W39.P195.S1166` - Keep argument parsing for modelo calculation revisions separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W39.P195.S1167` - Delegate modelo calculation revisions execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W39.P195.S1168` - Render modelo calculation revisions results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W39.P195.S1169` - Handle modelo calculation revisions failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W39.P195.S1170` - Validate help text for modelo calculation revisions uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W40` - modelo verify

This Wave implements the `2026-05-12-cli-workflow-redesign-modelo-verify-adr` decision for modelo verification lifecycle. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W40.P196` - backend implementation

This Phase delivers backend implementation for modelo verification lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-verify-adr`.

- [ ] `W40.P196.S1171` - Map the `2026-05-12-cli-workflow-redesign-modelo-verify-adr` decision into non-CLI service ownership for modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P196.S1172` - Implement Pydantic command and result contracts for modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P196.S1173` - Wire application or domain services required by modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P196.S1174` - Connect persistence, bucket events, registry data, or provider adapters required by modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P196.S1175` - Route existing backend functionality into the canonical service for modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P196.S1176` - Record service-level error codes and log fields for modelo verification lifecycle; `src/aeat/application/modelo`.

### Phase `W40.P197` - shadow duplicate removal

This Phase delivers shadow duplicate removal for modelo verification lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-verify-adr`.

- [ ] `W40.P197.S1177` - Audit duplicate implementations that overlap modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P197.S1178` - Delete duplicate backend branches that compete with modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P197.S1179` - Remove stale aliases that bypass the canonical service for modelo verification lifecycle; `src/aeat/entrypoints/cli`.
- [ ] `W40.P197.S1180` - Migrate internal callers to the canonical service for modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P197.S1181` - Remove stale fixtures and tests that encode duplicate behavior for modelo verification lifecycle; `tests/application/modelo`.
- [ ] `W40.P197.S1182` - Update boundary inventory entries that describe duplicate behavior for modelo verification lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W40.P198` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for modelo verification lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-verify-adr`.

- [ ] `W40.P198.S1183` - Delete compatibility shims that preserve rejected behavior for modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P198.S1184` - Delete placeholder stubs that claim support for modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P198.S1185` - Replace stubbed paths with real backend service calls for modelo verification lifecycle; `src/aeat/application/modelo`.
- [ ] `W40.P198.S1186` - Remove deprecated command spelling and help text for modelo verification lifecycle; `src/aeat/entrypoints/cli`.
- [ ] `W40.P198.S1187` - Remove tests that assert shim or stub behavior for modelo verification lifecycle; `tests/application/modelo`.
- [ ] `W40.P198.S1188` - Record the removed shim and stub surfaces for modelo verification lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W40.P199` - real behavior verification

This Phase delivers real behavior verification for modelo verification lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-verify-adr`.

- [ ] `W40.P199.S1189` - Add service contract tests for modelo verification lifecycle; `tests/application/modelo`.
- [ ] `W40.P199.S1190` - Add persistence or registry integration tests for modelo verification lifecycle; `tests/application/modelo`.
- [ ] `W40.P199.S1191` - Add negative tests proving rejected aliases do not reach modelo verification lifecycle; `tests/entrypoints/cli`.
- [ ] `W40.P199.S1192` - Add command behavior tests that exercise modelo verification lifecycle through real services; `tests/entrypoints/cli`.
- [ ] `W40.P199.S1193` - Add end-to-end workflow coverage for modelo verification lifecycle; `tests`.
- [ ] `W40.P199.S1194` - Run the targeted test slice for modelo verification lifecycle without skips or xfails; `tests/application/modelo`.

### Phase `W40.P200` - thin cli exposure

This Phase delivers thin cli exposure for modelo verification lifecycle as required by `2026-05-12-cli-workflow-redesign-modelo-verify-adr`.

- [ ] `W40.P200.S1195` - Expose accepted command handlers for modelo verification lifecycle under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W40.P200.S1196` - Keep argument parsing for modelo verification lifecycle separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W40.P200.S1197` - Delegate modelo verification lifecycle execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W40.P200.S1198` - Render modelo verification lifecycle results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W40.P200.S1199` - Handle modelo verification lifecycle failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W40.P200.S1200` - Validate help text for modelo verification lifecycle uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W41` - verified complete

This Wave implements the `2026-05-12-cli-workflow-redesign-verified-complete-adr` decision for verified complete state. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W41.P201` - backend implementation

This Phase delivers backend implementation for verified complete state as required by `2026-05-12-cli-workflow-redesign-verified-complete-adr`.

- [ ] `W41.P201.S1201` - Map the `2026-05-12-cli-workflow-redesign-verified-complete-adr` decision into non-CLI service ownership for verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P201.S1202` - Implement Pydantic command and result contracts for verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P201.S1203` - Wire application or domain services required by verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P201.S1204` - Connect persistence, bucket events, registry data, or provider adapters required by verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P201.S1205` - Route existing backend functionality into the canonical service for verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P201.S1206` - Record service-level error codes and log fields for verified complete state; `src/aeat/application/modelo`.

### Phase `W41.P202` - shadow duplicate removal

This Phase delivers shadow duplicate removal for verified complete state as required by `2026-05-12-cli-workflow-redesign-verified-complete-adr`.

- [ ] `W41.P202.S1207` - Audit duplicate implementations that overlap verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P202.S1208` - Delete duplicate backend branches that compete with verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P202.S1209` - Remove stale aliases that bypass the canonical service for verified complete state; `src/aeat/entrypoints/cli`.
- [ ] `W41.P202.S1210` - Migrate internal callers to the canonical service for verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P202.S1211` - Remove stale fixtures and tests that encode duplicate behavior for verified complete state; `tests/application/modelo`.
- [ ] `W41.P202.S1212` - Update boundary inventory entries that describe duplicate behavior for verified complete state; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W41.P203` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for verified complete state as required by `2026-05-12-cli-workflow-redesign-verified-complete-adr`.

- [ ] `W41.P203.S1213` - Delete compatibility shims that preserve rejected behavior for verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P203.S1214` - Delete placeholder stubs that claim support for verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P203.S1215` - Replace stubbed paths with real backend service calls for verified complete state; `src/aeat/application/modelo`.
- [ ] `W41.P203.S1216` - Remove deprecated command spelling and help text for verified complete state; `src/aeat/entrypoints/cli`.
- [ ] `W41.P203.S1217` - Remove tests that assert shim or stub behavior for verified complete state; `tests/application/modelo`.
- [ ] `W41.P203.S1218` - Record the removed shim and stub surfaces for verified complete state; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W41.P204` - real behavior verification

This Phase delivers real behavior verification for verified complete state as required by `2026-05-12-cli-workflow-redesign-verified-complete-adr`.

- [ ] `W41.P204.S1219` - Add service contract tests for verified complete state; `tests/application/modelo`.
- [ ] `W41.P204.S1220` - Add persistence or registry integration tests for verified complete state; `tests/application/modelo`.
- [ ] `W41.P204.S1221` - Add negative tests proving rejected aliases do not reach verified complete state; `tests/entrypoints/cli`.
- [ ] `W41.P204.S1222` - Add command behavior tests that exercise verified complete state through real services; `tests/entrypoints/cli`.
- [ ] `W41.P204.S1223` - Add end-to-end workflow coverage for verified complete state; `tests`.
- [ ] `W41.P204.S1224` - Run the targeted test slice for verified complete state without skips or xfails; `tests/application/modelo`.

### Phase `W41.P205` - thin cli exposure

This Phase delivers thin cli exposure for verified complete state as required by `2026-05-12-cli-workflow-redesign-verified-complete-adr`.

- [ ] `W41.P205.S1225` - Expose accepted command handlers for verified complete state under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W41.P205.S1226` - Keep argument parsing for verified complete state separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W41.P205.S1227` - Delegate verified complete state execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W41.P205.S1228` - Render verified complete state results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W41.P205.S1229` - Handle verified complete state failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W41.P205.S1230` - Validate help text for verified complete state uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W42` - modelo file

This Wave implements the `2026-05-12-cli-workflow-redesign-modelo-file-adr` decision for internal filed state. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W42.P206` - backend implementation

This Phase delivers backend implementation for internal filed state as required by `2026-05-12-cli-workflow-redesign-modelo-file-adr`.

- [ ] `W42.P206.S1231` - Map the `2026-05-12-cli-workflow-redesign-modelo-file-adr` decision into non-CLI service ownership for internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P206.S1232` - Implement Pydantic command and result contracts for internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P206.S1233` - Wire application or domain services required by internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P206.S1234` - Connect persistence, bucket events, registry data, or provider adapters required by internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P206.S1235` - Route existing backend functionality into the canonical service for internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P206.S1236` - Record service-level error codes and log fields for internal filed state; `src/aeat/application/modelo`.

### Phase `W42.P207` - shadow duplicate removal

This Phase delivers shadow duplicate removal for internal filed state as required by `2026-05-12-cli-workflow-redesign-modelo-file-adr`.

- [ ] `W42.P207.S1237` - Audit duplicate implementations that overlap internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P207.S1238` - Delete duplicate backend branches that compete with internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P207.S1239` - Remove stale aliases that bypass the canonical service for internal filed state; `src/aeat/entrypoints/cli`.
- [ ] `W42.P207.S1240` - Migrate internal callers to the canonical service for internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P207.S1241` - Remove stale fixtures and tests that encode duplicate behavior for internal filed state; `tests/application/modelo`.
- [ ] `W42.P207.S1242` - Update boundary inventory entries that describe duplicate behavior for internal filed state; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W42.P208` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for internal filed state as required by `2026-05-12-cli-workflow-redesign-modelo-file-adr`.

- [ ] `W42.P208.S1243` - Delete compatibility shims that preserve rejected behavior for internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P208.S1244` - Delete placeholder stubs that claim support for internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P208.S1245` - Replace stubbed paths with real backend service calls for internal filed state; `src/aeat/application/modelo`.
- [ ] `W42.P208.S1246` - Remove deprecated command spelling and help text for internal filed state; `src/aeat/entrypoints/cli`.
- [ ] `W42.P208.S1247` - Remove tests that assert shim or stub behavior for internal filed state; `tests/application/modelo`.
- [ ] `W42.P208.S1248` - Record the removed shim and stub surfaces for internal filed state; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W42.P209` - real behavior verification

This Phase delivers real behavior verification for internal filed state as required by `2026-05-12-cli-workflow-redesign-modelo-file-adr`.

- [ ] `W42.P209.S1249` - Add service contract tests for internal filed state; `tests/application/modelo`.
- [ ] `W42.P209.S1250` - Add persistence or registry integration tests for internal filed state; `tests/application/modelo`.
- [ ] `W42.P209.S1251` - Add negative tests proving rejected aliases do not reach internal filed state; `tests/entrypoints/cli`.
- [ ] `W42.P209.S1252` - Add command behavior tests that exercise internal filed state through real services; `tests/entrypoints/cli`.
- [ ] `W42.P209.S1253` - Add end-to-end workflow coverage for internal filed state; `tests`.
- [ ] `W42.P209.S1254` - Run the targeted test slice for internal filed state without skips or xfails; `tests/application/modelo`.

### Phase `W42.P210` - thin cli exposure

This Phase delivers thin cli exposure for internal filed state as required by `2026-05-12-cli-workflow-redesign-modelo-file-adr`.

- [ ] `W42.P210.S1255` - Expose accepted command handlers for internal filed state under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W42.P210.S1256` - Keep argument parsing for internal filed state separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W42.P210.S1257` - Delegate internal filed state execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W42.P210.S1258` - Render internal filed state results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W42.P210.S1259` - Handle internal filed state failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W42.P210.S1260` - Validate help text for internal filed state uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W43` - modelo filing record

This Wave implements the `2026-05-12-cli-workflow-redesign-modelo-filing-record-adr` decision for filing record and submission status. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W43.P211` - backend implementation

This Phase delivers backend implementation for filing record and submission status as required by `2026-05-12-cli-workflow-redesign-modelo-filing-record-adr`.

- [ ] `W43.P211.S1261` - Map the `2026-05-12-cli-workflow-redesign-modelo-filing-record-adr` decision into non-CLI service ownership for filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P211.S1262` - Implement Pydantic command and result contracts for filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P211.S1263` - Wire application or domain services required by filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P211.S1264` - Connect persistence, bucket events, registry data, or provider adapters required by filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P211.S1265` - Route existing backend functionality into the canonical service for filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P211.S1266` - Record service-level error codes and log fields for filing record and submission status; `src/aeat/application/modelo`.

### Phase `W43.P212` - shadow duplicate removal

This Phase delivers shadow duplicate removal for filing record and submission status as required by `2026-05-12-cli-workflow-redesign-modelo-filing-record-adr`.

- [ ] `W43.P212.S1267` - Audit duplicate implementations that overlap filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P212.S1268` - Delete duplicate backend branches that compete with filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P212.S1269` - Remove stale aliases that bypass the canonical service for filing record and submission status; `src/aeat/entrypoints/cli`.
- [ ] `W43.P212.S1270` - Migrate internal callers to the canonical service for filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P212.S1271` - Remove stale fixtures and tests that encode duplicate behavior for filing record and submission status; `tests/application/modelo`.
- [ ] `W43.P212.S1272` - Update boundary inventory entries that describe duplicate behavior for filing record and submission status; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W43.P213` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for filing record and submission status as required by `2026-05-12-cli-workflow-redesign-modelo-filing-record-adr`.

- [ ] `W43.P213.S1273` - Delete compatibility shims that preserve rejected behavior for filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P213.S1274` - Delete placeholder stubs that claim support for filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P213.S1275` - Replace stubbed paths with real backend service calls for filing record and submission status; `src/aeat/application/modelo`.
- [ ] `W43.P213.S1276` - Remove deprecated command spelling and help text for filing record and submission status; `src/aeat/entrypoints/cli`.
- [ ] `W43.P213.S1277` - Remove tests that assert shim or stub behavior for filing record and submission status; `tests/application/modelo`.
- [ ] `W43.P213.S1278` - Record the removed shim and stub surfaces for filing record and submission status; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W43.P214` - real behavior verification

This Phase delivers real behavior verification for filing record and submission status as required by `2026-05-12-cli-workflow-redesign-modelo-filing-record-adr`.

- [ ] `W43.P214.S1279` - Add service contract tests for filing record and submission status; `tests/application/modelo`.
- [ ] `W43.P214.S1280` - Add persistence or registry integration tests for filing record and submission status; `tests/application/modelo`.
- [ ] `W43.P214.S1281` - Add negative tests proving rejected aliases do not reach filing record and submission status; `tests/entrypoints/cli`.
- [ ] `W43.P214.S1282` - Add command behavior tests that exercise filing record and submission status through real services; `tests/entrypoints/cli`.
- [ ] `W43.P214.S1283` - Add end-to-end workflow coverage for filing record and submission status; `tests`.
- [ ] `W43.P214.S1284` - Run the targeted test slice for filing record and submission status without skips or xfails; `tests/application/modelo`.

### Phase `W43.P215` - thin cli exposure

This Phase delivers thin cli exposure for filing record and submission status as required by `2026-05-12-cli-workflow-redesign-modelo-filing-record-adr`.

- [ ] `W43.P215.S1285` - Expose accepted command handlers for filing record and submission status under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W43.P215.S1286` - Keep argument parsing for filing record and submission status separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W43.P215.S1287` - Delegate filing record and submission status execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W43.P215.S1288` - Render filing record and submission status results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W43.P215.S1289` - Handle filing record and submission status failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W43.P215.S1290` - Validate help text for filing record and submission status uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W44` - actor attribution

This Wave implements the `2026-05-13-cli-workflow-redesign-actor-attribution-adr` decision for actor attribution for mutations. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W44.P216` - backend implementation

This Phase delivers backend implementation for actor attribution for mutations as required by `2026-05-13-cli-workflow-redesign-actor-attribution-adr`.

- [ ] `W44.P216.S1291` - Map the `2026-05-13-cli-workflow-redesign-actor-attribution-adr` decision into non-CLI service ownership for actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P216.S1292` - Implement Pydantic command and result contracts for actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P216.S1293` - Wire application or domain services required by actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P216.S1294` - Connect persistence, bucket events, registry data, or provider adapters required by actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P216.S1295` - Route existing backend functionality into the canonical service for actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P216.S1296` - Record service-level error codes and log fields for actor attribution for mutations; `src/aeat/application`.

### Phase `W44.P217` - shadow duplicate removal

This Phase delivers shadow duplicate removal for actor attribution for mutations as required by `2026-05-13-cli-workflow-redesign-actor-attribution-adr`.

- [ ] `W44.P217.S1297` - Audit duplicate implementations that overlap actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P217.S1298` - Delete duplicate backend branches that compete with actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P217.S1299` - Remove stale aliases that bypass the canonical service for actor attribution for mutations; `src/aeat/entrypoints/cli`.
- [ ] `W44.P217.S1300` - Migrate internal callers to the canonical service for actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P217.S1301` - Remove stale fixtures and tests that encode duplicate behavior for actor attribution for mutations; `tests/application`.
- [ ] `W44.P217.S1302` - Update boundary inventory entries that describe duplicate behavior for actor attribution for mutations; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W44.P218` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for actor attribution for mutations as required by `2026-05-13-cli-workflow-redesign-actor-attribution-adr`.

- [ ] `W44.P218.S1303` - Delete compatibility shims that preserve rejected behavior for actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P218.S1304` - Delete placeholder stubs that claim support for actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P218.S1305` - Replace stubbed paths with real backend service calls for actor attribution for mutations; `src/aeat/application`.
- [ ] `W44.P218.S1306` - Remove deprecated command spelling and help text for actor attribution for mutations; `src/aeat/entrypoints/cli`.
- [ ] `W44.P218.S1307` - Remove tests that assert shim or stub behavior for actor attribution for mutations; `tests/application`.
- [ ] `W44.P218.S1308` - Record the removed shim and stub surfaces for actor attribution for mutations; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W44.P219` - real behavior verification

This Phase delivers real behavior verification for actor attribution for mutations as required by `2026-05-13-cli-workflow-redesign-actor-attribution-adr`.

- [ ] `W44.P219.S1309` - Add service contract tests for actor attribution for mutations; `tests/application`.
- [ ] `W44.P219.S1310` - Add persistence or registry integration tests for actor attribution for mutations; `tests/application`.
- [ ] `W44.P219.S1311` - Add negative tests proving rejected aliases do not reach actor attribution for mutations; `tests/entrypoints/cli`.
- [ ] `W44.P219.S1312` - Add command behavior tests that exercise actor attribution for mutations through real services; `tests/entrypoints/cli`.
- [ ] `W44.P219.S1313` - Add end-to-end workflow coverage for actor attribution for mutations; `tests`.
- [ ] `W44.P219.S1314` - Run the targeted test slice for actor attribution for mutations without skips or xfails; `tests/application`.

### Phase `W44.P220` - thin cli exposure

This Phase delivers thin cli exposure for actor attribution for mutations as required by `2026-05-13-cli-workflow-redesign-actor-attribution-adr`.

- [ ] `W44.P220.S1315` - Expose accepted command handlers for actor attribution for mutations under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W44.P220.S1316` - Keep argument parsing for actor attribution for mutations separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W44.P220.S1317` - Delegate actor attribution for mutations execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W44.P220.S1318` - Render actor attribution for mutations results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W44.P220.S1319` - Handle actor attribution for mutations failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W44.P220.S1320` - Validate help text for actor attribution for mutations uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W45` - app modelo discard

This Wave implements the `2026-05-13-cli-workflow-redesign-app-modelo-discard-adr` decision for modelo discard behavior. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W45.P221` - backend implementation

This Phase delivers backend implementation for modelo discard behavior as required by `2026-05-13-cli-workflow-redesign-app-modelo-discard-adr`.

- [x] `W45.P221.S1321` - Map the `2026-05-13-cli-workflow-redesign-app-modelo-discard-adr` decision into non-CLI service ownership for modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P221.S1322` - Implement Pydantic command and result contracts for modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P221.S1323` - Wire application or domain services required by modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P221.S1324` - Connect persistence, bucket events, registry data, or provider adapters required by modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P221.S1325` - Route existing backend functionality into the canonical service for modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P221.S1326` - Record service-level error codes and log fields for modelo discard behavior; `src/aeat/application/modelo`.

### Phase `W45.P222` - shadow duplicate removal

This Phase delivers shadow duplicate removal for modelo discard behavior as required by `2026-05-13-cli-workflow-redesign-app-modelo-discard-adr`.

- [x] `W45.P222.S1327` - Audit duplicate implementations that overlap modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P222.S1328` - Delete duplicate backend branches that compete with modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P222.S1329` - Remove stale aliases that bypass the canonical service for modelo discard behavior; `src/aeat/entrypoints/cli`.
- [x] `W45.P222.S1330` - Migrate internal callers to the canonical service for modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P222.S1331` - Remove stale fixtures and tests that encode duplicate behavior for modelo discard behavior; `tests/application/modelo`.
- [x] `W45.P222.S1332` - Update boundary inventory entries that describe duplicate behavior for modelo discard behavior; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W45.P223` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for modelo discard behavior as required by `2026-05-13-cli-workflow-redesign-app-modelo-discard-adr`.

- [x] `W45.P223.S1333` - Delete compatibility shims that preserve rejected behavior for modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P223.S1334` - Delete placeholder stubs that claim support for modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P223.S1335` - Replace stubbed paths with real backend service calls for modelo discard behavior; `src/aeat/application/modelo`.
- [x] `W45.P223.S1336` - Remove deprecated command spelling and help text for modelo discard behavior; `src/aeat/entrypoints/cli`.
- [x] `W45.P223.S1337` - Remove tests that assert shim or stub behavior for modelo discard behavior; `tests/application/modelo`.
- [x] `W45.P223.S1338` - Record the removed shim and stub surfaces for modelo discard behavior; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W45.P224` - real behavior verification

This Phase delivers real behavior verification for modelo discard behavior as required by `2026-05-13-cli-workflow-redesign-app-modelo-discard-adr`.

- [x] `W45.P224.S1339` - Add service contract tests for modelo discard behavior; `tests/application/modelo`.
- [x] `W45.P224.S1340` - Add persistence or registry integration tests for modelo discard behavior; `tests/application/modelo`.
- [x] `W45.P224.S1341` - Add negative tests proving rejected aliases do not reach modelo discard behavior; `tests/entrypoints/cli`.
- [x] `W45.P224.S1342` - Add command behavior tests that exercise modelo discard behavior through real services; `tests/entrypoints/cli`.
- [x] `W45.P224.S1343` - Add end-to-end workflow coverage for modelo discard behavior; `tests`.
- [x] `W45.P224.S1344` - Run the targeted test slice for modelo discard behavior without skips or xfails; `tests/application/modelo`.

### Phase `W45.P225` - thin cli exposure

This Phase delivers thin cli exposure for modelo discard behavior as required by `2026-05-13-cli-workflow-redesign-app-modelo-discard-adr`.

- [x] `W45.P225.S1345` - Expose accepted command handlers for modelo discard behavior under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W45.P225.S1346` - Keep argument parsing for modelo discard behavior separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W45.P225.S1347` - Delegate modelo discard behavior execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W45.P225.S1348` - Render modelo discard behavior results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W45.P225.S1349` - Handle modelo discard behavior failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W45.P225.S1350` - Validate help text for modelo discard behavior uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W46` - app modelo shape

This Wave implements the `2026-05-12-cli-workflow-redesign-app-modelo-shape-adr` decision for app modelo command surface. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W46.P226` - backend implementation

This Phase delivers backend implementation for app modelo command surface as required by `2026-05-12-cli-workflow-redesign-app-modelo-shape-adr`.

- [ ] `W46.P226.S1351` - Map the `2026-05-12-cli-workflow-redesign-app-modelo-shape-adr` decision into non-CLI service ownership for app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P226.S1352` - Implement Pydantic command and result contracts for app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P226.S1353` - Wire application or domain services required by app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P226.S1354` - Connect persistence, bucket events, registry data, or provider adapters required by app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P226.S1355` - Route existing backend functionality into the canonical service for app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P226.S1356` - Record service-level error codes and log fields for app modelo command surface; `src/aeat/application/modelo`.

### Phase `W46.P227` - shadow duplicate removal

This Phase delivers shadow duplicate removal for app modelo command surface as required by `2026-05-12-cli-workflow-redesign-app-modelo-shape-adr`.

- [ ] `W46.P227.S1357` - Audit duplicate implementations that overlap app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P227.S1358` - Delete duplicate backend branches that compete with app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P227.S1359` - Remove stale aliases that bypass the canonical service for app modelo command surface; `src/aeat/entrypoints/cli`.
- [ ] `W46.P227.S1360` - Migrate internal callers to the canonical service for app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P227.S1361` - Remove stale fixtures and tests that encode duplicate behavior for app modelo command surface; `tests/entrypoints/cli`.
- [ ] `W46.P227.S1362` - Update boundary inventory entries that describe duplicate behavior for app modelo command surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W46.P228` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for app modelo command surface as required by `2026-05-12-cli-workflow-redesign-app-modelo-shape-adr`.

- [ ] `W46.P228.S1363` - Delete compatibility shims that preserve rejected behavior for app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P228.S1364` - Delete placeholder stubs that claim support for app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P228.S1365` - Replace stubbed paths with real backend service calls for app modelo command surface; `src/aeat/application/modelo`.
- [ ] `W46.P228.S1366` - Remove deprecated command spelling and help text for app modelo command surface; `src/aeat/entrypoints/cli`.
- [ ] `W46.P228.S1367` - Remove tests that assert shim or stub behavior for app modelo command surface; `tests/entrypoints/cli`.
- [ ] `W46.P228.S1368` - Record the removed shim and stub surfaces for app modelo command surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W46.P229` - real behavior verification

This Phase delivers real behavior verification for app modelo command surface as required by `2026-05-12-cli-workflow-redesign-app-modelo-shape-adr`.

- [ ] `W46.P229.S1369` - Add service contract tests for app modelo command surface; `tests/entrypoints/cli`.
- [ ] `W46.P229.S1370` - Add persistence or registry integration tests for app modelo command surface; `tests/entrypoints/cli`.
- [ ] `W46.P229.S1371` - Add negative tests proving rejected aliases do not reach app modelo command surface; `tests/entrypoints/cli`.
- [ ] `W46.P229.S1372` - Add command behavior tests that exercise app modelo command surface through real services; `tests/entrypoints/cli`.
- [ ] `W46.P229.S1373` - Add end-to-end workflow coverage for app modelo command surface; `tests`.
- [ ] `W46.P229.S1374` - Run the targeted test slice for app modelo command surface without skips or xfails; `tests/entrypoints/cli`.

### Phase `W46.P230` - thin cli exposure

This Phase delivers thin cli exposure for app modelo command surface as required by `2026-05-12-cli-workflow-redesign-app-modelo-shape-adr`.

- [ ] `W46.P230.S1375` - Expose accepted command handlers for app modelo command surface under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W46.P230.S1376` - Keep argument parsing for app modelo command surface separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W46.P230.S1377` - Delegate app modelo command surface execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W46.P230.S1378` - Render app modelo command surface results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W46.P230.S1379` - Handle app modelo command surface failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W46.P230.S1380` - Validate help text for app modelo command surface uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W47` - app modelo bindings shape

This Wave implements the `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr` decision for modelo bindings behavior. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W47.P231` - backend implementation

This Phase delivers backend implementation for modelo bindings behavior as required by `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr`.

- [x] `W47.P231.S1381` - Map the `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr` decision into non-CLI service ownership for modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P231.S1382` - Implement Pydantic command and result contracts for modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P231.S1383` - Wire application or domain services required by modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P231.S1384` - Connect persistence, bucket events, registry data, or provider adapters required by modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P231.S1385` - Route existing backend functionality into the canonical service for modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P231.S1386` - Record service-level error codes and log fields for modelo bindings behavior; `src/aeat/application/modelo`.

### Phase `W47.P232` - shadow duplicate removal

This Phase delivers shadow duplicate removal for modelo bindings behavior as required by `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr`.

- [x] `W47.P232.S1387` - Audit duplicate implementations that overlap modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P232.S1388` - Delete duplicate backend branches that compete with modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P232.S1389` - Remove stale aliases that bypass the canonical service for modelo bindings behavior; `src/aeat/entrypoints/cli`.
- [x] `W47.P232.S1390` - Migrate internal callers to the canonical service for modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P232.S1391` - Remove stale fixtures and tests that encode duplicate behavior for modelo bindings behavior; `tests/application/modelo`.
- [x] `W47.P232.S1392` - Update boundary inventory entries that describe duplicate behavior for modelo bindings behavior; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W47.P233` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for modelo bindings behavior as required by `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr`.

- [x] `W47.P233.S1393` - Delete compatibility shims that preserve rejected behavior for modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P233.S1394` - Delete placeholder stubs that claim support for modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P233.S1395` - Replace stubbed paths with real backend service calls for modelo bindings behavior; `src/aeat/application/modelo`.
- [x] `W47.P233.S1396` - Remove deprecated command spelling and help text for modelo bindings behavior; `src/aeat/entrypoints/cli`.
- [x] `W47.P233.S1397` - Remove tests that assert shim or stub behavior for modelo bindings behavior; `tests/application/modelo`.
- [x] `W47.P233.S1398` - Record the removed shim and stub surfaces for modelo bindings behavior; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W47.P234` - real behavior verification

This Phase delivers real behavior verification for modelo bindings behavior as required by `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr`.

- [x] `W47.P234.S1399` - Add service contract tests for modelo bindings behavior; `tests/application/modelo`.
- [x] `W47.P234.S1400` - Add persistence or registry integration tests for modelo bindings behavior; `tests/application/modelo`.
- [x] `W47.P234.S1401` - Add negative tests proving rejected aliases do not reach modelo bindings behavior; `tests/entrypoints/cli`.
- [x] `W47.P234.S1402` - Add command behavior tests that exercise modelo bindings behavior through real services; `tests/entrypoints/cli`.
- [x] `W47.P234.S1403` - Add end-to-end workflow coverage for modelo bindings behavior; `tests`.
- [x] `W47.P234.S1404` - Run the targeted test slice for modelo bindings behavior without skips or xfails; `tests/application/modelo`.

### Phase `W47.P235` - thin cli exposure

This Phase delivers thin cli exposure for modelo bindings behavior as required by `2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr`.

- [x] `W47.P235.S1405` - Expose accepted command handlers for modelo bindings behavior under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [x] `W47.P235.S1406` - Keep argument parsing for modelo bindings behavior separate from backend behavior; `src/aeat/entrypoints/cli`.
- [x] `W47.P235.S1407` - Delegate modelo bindings behavior execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [x] `W47.P235.S1408` - Render modelo bindings behavior results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [x] `W47.P235.S1409` - Handle modelo bindings behavior failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [x] `W47.P235.S1410` - Validate help text for modelo bindings behavior uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W48` - borrador 100 binding integration

This Wave implements the `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr` decision for modelo 100 borrador binding. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W48.P236` - backend implementation

This Phase delivers backend implementation for modelo 100 borrador binding as required by `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr`.

- [ ] `W48.P236.S1411` - Map the `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr` decision into non-CLI service ownership for modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P236.S1412` - Implement Pydantic command and result contracts for modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P236.S1413` - Wire application or domain services required by modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P236.S1414` - Connect persistence, bucket events, registry data, or provider adapters required by modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P236.S1415` - Route existing backend functionality into the canonical service for modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P236.S1416` - Record service-level error codes and log fields for modelo 100 borrador binding; `src/aeat/application/modelo`.

### Phase `W48.P237` - shadow duplicate removal

This Phase delivers shadow duplicate removal for modelo 100 borrador binding as required by `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr`.

- [ ] `W48.P237.S1417` - Audit duplicate implementations that overlap modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P237.S1418` - Delete duplicate backend branches that compete with modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P237.S1419` - Remove stale aliases that bypass the canonical service for modelo 100 borrador binding; `src/aeat/entrypoints/cli`.
- [ ] `W48.P237.S1420` - Migrate internal callers to the canonical service for modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P237.S1421` - Remove stale fixtures and tests that encode duplicate behavior for modelo 100 borrador binding; `tests/application/modelo`.
- [ ] `W48.P237.S1422` - Update boundary inventory entries that describe duplicate behavior for modelo 100 borrador binding; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W48.P238` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for modelo 100 borrador binding as required by `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr`.

- [ ] `W48.P238.S1423` - Delete compatibility shims that preserve rejected behavior for modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P238.S1424` - Delete placeholder stubs that claim support for modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P238.S1425` - Replace stubbed paths with real backend service calls for modelo 100 borrador binding; `src/aeat/application/modelo`.
- [ ] `W48.P238.S1426` - Remove deprecated command spelling and help text for modelo 100 borrador binding; `src/aeat/entrypoints/cli`.
- [ ] `W48.P238.S1427` - Remove tests that assert shim or stub behavior for modelo 100 borrador binding; `tests/application/modelo`.
- [ ] `W48.P238.S1428` - Record the removed shim and stub surfaces for modelo 100 borrador binding; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W48.P239` - real behavior verification

This Phase delivers real behavior verification for modelo 100 borrador binding as required by `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr`.

- [ ] `W48.P239.S1429` - Add service contract tests for modelo 100 borrador binding; `tests/application/modelo`.
- [ ] `W48.P239.S1430` - Add persistence or registry integration tests for modelo 100 borrador binding; `tests/application/modelo`.
- [ ] `W48.P239.S1431` - Add negative tests proving rejected aliases do not reach modelo 100 borrador binding; `tests/entrypoints/cli`.
- [ ] `W48.P239.S1432` - Add command behavior tests that exercise modelo 100 borrador binding through real services; `tests/entrypoints/cli`.
- [ ] `W48.P239.S1433` - Add end-to-end workflow coverage for modelo 100 borrador binding; `tests`.
- [ ] `W48.P239.S1434` - Run the targeted test slice for modelo 100 borrador binding without skips or xfails; `tests/application/modelo`.

### Phase `W48.P240` - thin cli exposure

This Phase delivers thin cli exposure for modelo 100 borrador binding as required by `2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr`.

- [ ] `W48.P240.S1435` - Expose accepted command handlers for modelo 100 borrador binding under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W48.P240.S1436` - Keep argument parsing for modelo 100 borrador binding separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W48.P240.S1437` - Delegate modelo 100 borrador binding execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W48.P240.S1438` - Render modelo 100 borrador binding results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W48.P240.S1439` - Handle modelo 100 borrador binding failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W48.P240.S1440` - Validate help text for modelo 100 borrador binding uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W49` - amend external filing path

This Wave implements the `2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr` decision for external filing amend path. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W49.P241` - backend implementation

This Phase delivers backend implementation for external filing amend path as required by `2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr`.

- [ ] `W49.P241.S1441` - Map the `2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr` decision into non-CLI service ownership for external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P241.S1442` - Implement Pydantic command and result contracts for external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P241.S1443` - Wire application or domain services required by external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P241.S1444` - Connect persistence, bucket events, registry data, or provider adapters required by external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P241.S1445` - Route existing backend functionality into the canonical service for external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P241.S1446` - Record service-level error codes and log fields for external filing amend path; `src/aeat/application/filing`.

### Phase `W49.P242` - shadow duplicate removal

This Phase delivers shadow duplicate removal for external filing amend path as required by `2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr`.

- [ ] `W49.P242.S1447` - Audit duplicate implementations that overlap external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P242.S1448` - Delete duplicate backend branches that compete with external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P242.S1449` - Remove stale aliases that bypass the canonical service for external filing amend path; `src/aeat/entrypoints/cli`.
- [ ] `W49.P242.S1450` - Migrate internal callers to the canonical service for external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P242.S1451` - Remove stale fixtures and tests that encode duplicate behavior for external filing amend path; `tests/application/filing`.
- [ ] `W49.P242.S1452` - Update boundary inventory entries that describe duplicate behavior for external filing amend path; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W49.P243` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for external filing amend path as required by `2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr`.

- [ ] `W49.P243.S1453` - Delete compatibility shims that preserve rejected behavior for external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P243.S1454` - Delete placeholder stubs that claim support for external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P243.S1455` - Replace stubbed paths with real backend service calls for external filing amend path; `src/aeat/application/filing`.
- [ ] `W49.P243.S1456` - Remove deprecated command spelling and help text for external filing amend path; `src/aeat/entrypoints/cli`.
- [ ] `W49.P243.S1457` - Remove tests that assert shim or stub behavior for external filing amend path; `tests/application/filing`.
- [ ] `W49.P243.S1458` - Record the removed shim and stub surfaces for external filing amend path; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W49.P244` - real behavior verification

This Phase delivers real behavior verification for external filing amend path as required by `2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr`.

- [ ] `W49.P244.S1459` - Add service contract tests for external filing amend path; `tests/application/filing`.
- [ ] `W49.P244.S1460` - Add persistence or registry integration tests for external filing amend path; `tests/application/filing`.
- [ ] `W49.P244.S1461` - Add negative tests proving rejected aliases do not reach external filing amend path; `tests/entrypoints/cli`.
- [ ] `W49.P244.S1462` - Add command behavior tests that exercise external filing amend path through real services; `tests/entrypoints/cli`.
- [ ] `W49.P244.S1463` - Add end-to-end workflow coverage for external filing amend path; `tests`.
- [ ] `W49.P244.S1464` - Run the targeted test slice for external filing amend path without skips or xfails; `tests/application/filing`.

### Phase `W49.P245` - thin cli exposure

This Phase delivers thin cli exposure for external filing amend path as required by `2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr`.

- [ ] `W49.P245.S1465` - Expose accepted command handlers for external filing amend path under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W49.P245.S1466` - Keep argument parsing for external filing amend path separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W49.P245.S1467` - Delegate external filing amend path execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W49.P245.S1468` - Render external filing amend path results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W49.P245.S1469` - Handle external filing amend path failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W49.P245.S1470` - Validate help text for external filing amend path uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W50` - modelo 036 037 foundation

This Wave implements the `2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr` decision for census modelo foundation. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W50.P246` - backend implementation

This Phase delivers backend implementation for census modelo foundation as required by `2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr`.

- [ ] `W50.P246.S1471` - Map the `2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr` decision into non-CLI service ownership for census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P246.S1472` - Implement Pydantic command and result contracts for census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P246.S1473` - Wire application or domain services required by census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P246.S1474` - Connect persistence, bucket events, registry data, or provider adapters required by census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P246.S1475` - Route existing backend functionality into the canonical service for census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P246.S1476` - Record service-level error codes and log fields for census modelo foundation; `src/aeat/domain/calculations/registry`.

### Phase `W50.P247` - shadow duplicate removal

This Phase delivers shadow duplicate removal for census modelo foundation as required by `2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr`.

- [ ] `W50.P247.S1477` - Audit duplicate implementations that overlap census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P247.S1478` - Delete duplicate backend branches that compete with census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P247.S1479` - Remove stale aliases that bypass the canonical service for census modelo foundation; `src/aeat/entrypoints/cli`.
- [ ] `W50.P247.S1480` - Migrate internal callers to the canonical service for census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P247.S1481` - Remove stale fixtures and tests that encode duplicate behavior for census modelo foundation; `tests/domain/calculations/registry`.
- [ ] `W50.P247.S1482` - Update boundary inventory entries that describe duplicate behavior for census modelo foundation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W50.P248` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for census modelo foundation as required by `2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr`.

- [ ] `W50.P248.S1483` - Delete compatibility shims that preserve rejected behavior for census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P248.S1484` - Delete placeholder stubs that claim support for census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P248.S1485` - Replace stubbed paths with real backend service calls for census modelo foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W50.P248.S1486` - Remove deprecated command spelling and help text for census modelo foundation; `src/aeat/entrypoints/cli`.
- [ ] `W50.P248.S1487` - Remove tests that assert shim or stub behavior for census modelo foundation; `tests/domain/calculations/registry`.
- [ ] `W50.P248.S1488` - Record the removed shim and stub surfaces for census modelo foundation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W50.P249` - real behavior verification

This Phase delivers real behavior verification for census modelo foundation as required by `2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr`.

- [ ] `W50.P249.S1489` - Add service contract tests for census modelo foundation; `tests/domain/calculations/registry`.
- [ ] `W50.P249.S1490` - Add persistence or registry integration tests for census modelo foundation; `tests/domain/calculations/registry`.
- [ ] `W50.P249.S1491` - Add negative tests proving rejected aliases do not reach census modelo foundation; `tests/entrypoints/cli`.
- [ ] `W50.P249.S1492` - Add command behavior tests that exercise census modelo foundation through real services; `tests/entrypoints/cli`.
- [ ] `W50.P249.S1493` - Add end-to-end workflow coverage for census modelo foundation; `tests`.
- [ ] `W50.P249.S1494` - Run the targeted test slice for census modelo foundation without skips or xfails; `tests/domain/calculations/registry`.

### Phase `W50.P250` - thin cli exposure

This Phase delivers thin cli exposure for census modelo foundation as required by `2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr`.

- [ ] `W50.P250.S1495` - Expose accepted command handlers for census modelo foundation under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W50.P250.S1496` - Keep argument parsing for census modelo foundation separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W50.P250.S1497` - Delegate census modelo foundation execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W50.P250.S1498` - Render census modelo foundation results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W50.P250.S1499` - Handle census modelo foundation failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W50.P250.S1500` - Validate help text for census modelo foundation uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W51` - modelo 145 foundation

This Wave implements the `2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr` decision for modelo 145 foundation. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W51.P251` - backend implementation

This Phase delivers backend implementation for modelo 145 foundation as required by `2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr`.

- [ ] `W51.P251.S1501` - Map the `2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr` decision into non-CLI service ownership for modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P251.S1502` - Implement Pydantic command and result contracts for modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P251.S1503` - Wire application or domain services required by modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P251.S1504` - Connect persistence, bucket events, registry data, or provider adapters required by modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P251.S1505` - Route existing backend functionality into the canonical service for modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P251.S1506` - Record service-level error codes and log fields for modelo 145 foundation; `src/aeat/domain/calculations/registry`.

### Phase `W51.P252` - shadow duplicate removal

This Phase delivers shadow duplicate removal for modelo 145 foundation as required by `2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr`.

- [ ] `W51.P252.S1507` - Audit duplicate implementations that overlap modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P252.S1508` - Delete duplicate backend branches that compete with modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P252.S1509` - Remove stale aliases that bypass the canonical service for modelo 145 foundation; `src/aeat/entrypoints/cli`.
- [ ] `W51.P252.S1510` - Migrate internal callers to the canonical service for modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P252.S1511` - Remove stale fixtures and tests that encode duplicate behavior for modelo 145 foundation; `tests/domain/calculations/registry`.
- [ ] `W51.P252.S1512` - Update boundary inventory entries that describe duplicate behavior for modelo 145 foundation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W51.P253` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for modelo 145 foundation as required by `2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr`.

- [ ] `W51.P253.S1513` - Delete compatibility shims that preserve rejected behavior for modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P253.S1514` - Delete placeholder stubs that claim support for modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P253.S1515` - Replace stubbed paths with real backend service calls for modelo 145 foundation; `src/aeat/domain/calculations/registry`.
- [ ] `W51.P253.S1516` - Remove deprecated command spelling and help text for modelo 145 foundation; `src/aeat/entrypoints/cli`.
- [ ] `W51.P253.S1517` - Remove tests that assert shim or stub behavior for modelo 145 foundation; `tests/domain/calculations/registry`.
- [ ] `W51.P253.S1518` - Record the removed shim and stub surfaces for modelo 145 foundation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W51.P254` - real behavior verification

This Phase delivers real behavior verification for modelo 145 foundation as required by `2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr`.

- [ ] `W51.P254.S1519` - Add service contract tests for modelo 145 foundation; `tests/domain/calculations/registry`.
- [ ] `W51.P254.S1520` - Add persistence or registry integration tests for modelo 145 foundation; `tests/domain/calculations/registry`.
- [ ] `W51.P254.S1521` - Add negative tests proving rejected aliases do not reach modelo 145 foundation; `tests/entrypoints/cli`.
- [ ] `W51.P254.S1522` - Add command behavior tests that exercise modelo 145 foundation through real services; `tests/entrypoints/cli`.
- [ ] `W51.P254.S1523` - Add end-to-end workflow coverage for modelo 145 foundation; `tests`.
- [ ] `W51.P254.S1524` - Run the targeted test slice for modelo 145 foundation without skips or xfails; `tests/domain/calculations/registry`.

### Phase `W51.P255` - thin cli exposure

This Phase delivers thin cli exposure for modelo 145 foundation as required by `2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr`.

- [ ] `W51.P255.S1525` - Expose accepted command handlers for modelo 145 foundation under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W51.P255.S1526` - Keep argument parsing for modelo 145 foundation separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W51.P255.S1527` - Delegate modelo 145 foundation execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W51.P255.S1528` - Render modelo 145 foundation results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W51.P255.S1529` - Handle modelo 145 foundation failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W51.P255.S1530` - Validate help text for modelo 145 foundation uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W52` - per modelo aggregation pipeline

This Wave implements the `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr` decision for per modelo aggregation. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W52.P256` - backend implementation

This Phase delivers backend implementation for per modelo aggregation as required by `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr`.

- [ ] `W52.P256.S1531` - Map the `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr` decision into non-CLI service ownership for per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P256.S1532` - Implement Pydantic command and result contracts for per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P256.S1533` - Wire application or domain services required by per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P256.S1534` - Connect persistence, bucket events, registry data, or provider adapters required by per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P256.S1535` - Route existing backend functionality into the canonical service for per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P256.S1536` - Record service-level error codes and log fields for per modelo aggregation; `src/aeat/application/aggregation`.

### Phase `W52.P257` - shadow duplicate removal

This Phase delivers shadow duplicate removal for per modelo aggregation as required by `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr`.

- [ ] `W52.P257.S1537` - Audit duplicate implementations that overlap per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P257.S1538` - Delete duplicate backend branches that compete with per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P257.S1539` - Remove stale aliases that bypass the canonical service for per modelo aggregation; `src/aeat/entrypoints/cli`.
- [ ] `W52.P257.S1540` - Migrate internal callers to the canonical service for per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P257.S1541` - Remove stale fixtures and tests that encode duplicate behavior for per modelo aggregation; `tests/application/aggregation`.
- [ ] `W52.P257.S1542` - Update boundary inventory entries that describe duplicate behavior for per modelo aggregation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W52.P258` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for per modelo aggregation as required by `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr`.

- [ ] `W52.P258.S1543` - Delete compatibility shims that preserve rejected behavior for per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P258.S1544` - Delete placeholder stubs that claim support for per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P258.S1545` - Replace stubbed paths with real backend service calls for per modelo aggregation; `src/aeat/application/aggregation`.
- [ ] `W52.P258.S1546` - Remove deprecated command spelling and help text for per modelo aggregation; `src/aeat/entrypoints/cli`.
- [ ] `W52.P258.S1547` - Remove tests that assert shim or stub behavior for per modelo aggregation; `tests/application/aggregation`.
- [ ] `W52.P258.S1548` - Record the removed shim and stub surfaces for per modelo aggregation; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W52.P259` - real behavior verification

This Phase delivers real behavior verification for per modelo aggregation as required by `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr`.

- [ ] `W52.P259.S1549` - Add service contract tests for per modelo aggregation; `tests/application/aggregation`.
- [ ] `W52.P259.S1550` - Add persistence or registry integration tests for per modelo aggregation; `tests/application/aggregation`.
- [ ] `W52.P259.S1551` - Add negative tests proving rejected aliases do not reach per modelo aggregation; `tests/entrypoints/cli`.
- [ ] `W52.P259.S1552` - Add command behavior tests that exercise per modelo aggregation through real services; `tests/entrypoints/cli`.
- [ ] `W52.P259.S1553` - Add end-to-end workflow coverage for per modelo aggregation; `tests`.
- [ ] `W52.P259.S1554` - Run the targeted test slice for per modelo aggregation without skips or xfails; `tests/application/aggregation`.

### Phase `W52.P260` - thin cli exposure

This Phase delivers thin cli exposure for per modelo aggregation as required by `2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr`.

- [ ] `W52.P260.S1555` - Expose accepted command handlers for per modelo aggregation under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W52.P260.S1556` - Keep argument parsing for per modelo aggregation separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W52.P260.S1557` - Delegate per modelo aggregation execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W52.P260.S1558` - Render per modelo aggregation results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W52.P260.S1559` - Handle per modelo aggregation failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W52.P260.S1560` - Validate help text for per modelo aggregation uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W53` - app overview shape

This Wave implements the `2026-05-12-cli-workflow-redesign-app-overview-shape-adr` decision for app overview surface. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W53.P261` - backend implementation

This Phase delivers backend implementation for app overview surface as required by `2026-05-12-cli-workflow-redesign-app-overview-shape-adr`.

- [ ] `W53.P261.S1561` - Map the `2026-05-12-cli-workflow-redesign-app-overview-shape-adr` decision into non-CLI service ownership for app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P261.S1562` - Implement Pydantic command and result contracts for app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P261.S1563` - Wire application or domain services required by app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P261.S1564` - Connect persistence, bucket events, registry data, or provider adapters required by app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P261.S1565` - Route existing backend functionality into the canonical service for app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P261.S1566` - Record service-level error codes and log fields for app overview surface; `src/aeat/application/overview`.

### Phase `W53.P262` - shadow duplicate removal

This Phase delivers shadow duplicate removal for app overview surface as required by `2026-05-12-cli-workflow-redesign-app-overview-shape-adr`.

- [ ] `W53.P262.S1567` - Audit duplicate implementations that overlap app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P262.S1568` - Delete duplicate backend branches that compete with app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P262.S1569` - Remove stale aliases that bypass the canonical service for app overview surface; `src/aeat/entrypoints/cli`.
- [ ] `W53.P262.S1570` - Migrate internal callers to the canonical service for app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P262.S1571` - Remove stale fixtures and tests that encode duplicate behavior for app overview surface; `tests/application/overview`.
- [ ] `W53.P262.S1572` - Update boundary inventory entries that describe duplicate behavior for app overview surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W53.P263` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for app overview surface as required by `2026-05-12-cli-workflow-redesign-app-overview-shape-adr`.

- [ ] `W53.P263.S1573` - Delete compatibility shims that preserve rejected behavior for app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P263.S1574` - Delete placeholder stubs that claim support for app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P263.S1575` - Replace stubbed paths with real backend service calls for app overview surface; `src/aeat/application/overview`.
- [ ] `W53.P263.S1576` - Remove deprecated command spelling and help text for app overview surface; `src/aeat/entrypoints/cli`.
- [ ] `W53.P263.S1577` - Remove tests that assert shim or stub behavior for app overview surface; `tests/application/overview`.
- [ ] `W53.P263.S1578` - Record the removed shim and stub surfaces for app overview surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W53.P264` - real behavior verification

This Phase delivers real behavior verification for app overview surface as required by `2026-05-12-cli-workflow-redesign-app-overview-shape-adr`.

- [ ] `W53.P264.S1579` - Add service contract tests for app overview surface; `tests/application/overview`.
- [ ] `W53.P264.S1580` - Add persistence or registry integration tests for app overview surface; `tests/application/overview`.
- [ ] `W53.P264.S1581` - Add negative tests proving rejected aliases do not reach app overview surface; `tests/entrypoints/cli`.
- [ ] `W53.P264.S1582` - Add command behavior tests that exercise app overview surface through real services; `tests/entrypoints/cli`.
- [ ] `W53.P264.S1583` - Add end-to-end workflow coverage for app overview surface; `tests`.
- [ ] `W53.P264.S1584` - Run the targeted test slice for app overview surface without skips or xfails; `tests/application/overview`.

### Phase `W53.P265` - thin cli exposure

This Phase delivers thin cli exposure for app overview surface as required by `2026-05-12-cli-workflow-redesign-app-overview-shape-adr`.

- [ ] `W53.P265.S1585` - Expose accepted command handlers for app overview surface under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W53.P265.S1586` - Keep argument parsing for app overview surface separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W53.P265.S1587` - Delegate app overview surface execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W53.P265.S1588` - Render app overview surface results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W53.P265.S1589` - Handle app overview surface failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W53.P265.S1590` - Validate help text for app overview surface uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W54` - app live shape

This Wave implements the `2026-05-12-cli-workflow-redesign-app-live-shape-adr` decision for read only live aeat signals. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W54.P266` - backend implementation

This Phase delivers backend implementation for read only live aeat signals as required by `2026-05-12-cli-workflow-redesign-app-live-shape-adr`.

- [ ] `W54.P266.S1591` - Map the `2026-05-12-cli-workflow-redesign-app-live-shape-adr` decision into non-CLI service ownership for read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P266.S1592` - Implement Pydantic command and result contracts for read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P266.S1593` - Wire application or domain services required by read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P266.S1594` - Connect persistence, bucket events, registry data, or provider adapters required by read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P266.S1595` - Route existing backend functionality into the canonical service for read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P266.S1596` - Record service-level error codes and log fields for read only live aeat signals; `src/aeat/application/live`.

### Phase `W54.P267` - shadow duplicate removal

This Phase delivers shadow duplicate removal for read only live aeat signals as required by `2026-05-12-cli-workflow-redesign-app-live-shape-adr`.

- [ ] `W54.P267.S1597` - Audit duplicate implementations that overlap read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P267.S1598` - Delete duplicate backend branches that compete with read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P267.S1599` - Remove stale aliases that bypass the canonical service for read only live aeat signals; `src/aeat/entrypoints/cli`.
- [ ] `W54.P267.S1600` - Migrate internal callers to the canonical service for read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P267.S1601` - Remove stale fixtures and tests that encode duplicate behavior for read only live aeat signals; `tests/application/live`.
- [ ] `W54.P267.S1602` - Update boundary inventory entries that describe duplicate behavior for read only live aeat signals; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W54.P268` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for read only live aeat signals as required by `2026-05-12-cli-workflow-redesign-app-live-shape-adr`.

- [ ] `W54.P268.S1603` - Delete compatibility shims that preserve rejected behavior for read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P268.S1604` - Delete placeholder stubs that claim support for read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P268.S1605` - Replace stubbed paths with real backend service calls for read only live aeat signals; `src/aeat/application/live`.
- [ ] `W54.P268.S1606` - Remove deprecated command spelling and help text for read only live aeat signals; `src/aeat/entrypoints/cli`.
- [ ] `W54.P268.S1607` - Remove tests that assert shim or stub behavior for read only live aeat signals; `tests/application/live`.
- [ ] `W54.P268.S1608` - Record the removed shim and stub surfaces for read only live aeat signals; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W54.P269` - real behavior verification

This Phase delivers real behavior verification for read only live aeat signals as required by `2026-05-12-cli-workflow-redesign-app-live-shape-adr`.

- [ ] `W54.P269.S1609` - Add service contract tests for read only live aeat signals; `tests/application/live`.
- [ ] `W54.P269.S1610` - Add persistence or registry integration tests for read only live aeat signals; `tests/application/live`.
- [ ] `W54.P269.S1611` - Add negative tests proving rejected aliases do not reach read only live aeat signals; `tests/entrypoints/cli`.
- [ ] `W54.P269.S1612` - Add command behavior tests that exercise read only live aeat signals through real services; `tests/entrypoints/cli`.
- [ ] `W54.P269.S1613` - Add end-to-end workflow coverage for read only live aeat signals; `tests`.
- [ ] `W54.P269.S1614` - Run the targeted test slice for read only live aeat signals without skips or xfails; `tests/application/live`.

### Phase `W54.P270` - thin cli exposure

This Phase delivers thin cli exposure for read only live aeat signals as required by `2026-05-12-cli-workflow-redesign-app-live-shape-adr`.

- [ ] `W54.P270.S1615` - Expose accepted command handlers for read only live aeat signals under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W54.P270.S1616` - Keep argument parsing for read only live aeat signals separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W54.P270.S1617` - Delegate read only live aeat signals execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W54.P270.S1618` - Render read only live aeat signals results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W54.P270.S1619` - Handle read only live aeat signals failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W54.P270.S1620` - Validate help text for read only live aeat signals uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W55` - app registry boundary

This Wave implements the `2026-05-12-cli-workflow-redesign-app-registry-boundary-adr` decision for registry and live boundary. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W55.P271` - backend implementation

This Phase delivers backend implementation for registry and live boundary as required by `2026-05-12-cli-workflow-redesign-app-registry-boundary-adr`.

- [ ] `W55.P271.S1621` - Map the `2026-05-12-cli-workflow-redesign-app-registry-boundary-adr` decision into non-CLI service ownership for registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P271.S1622` - Implement Pydantic command and result contracts for registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P271.S1623` - Wire application or domain services required by registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P271.S1624` - Connect persistence, bucket events, registry data, or provider adapters required by registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P271.S1625` - Route existing backend functionality into the canonical service for registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P271.S1626` - Record service-level error codes and log fields for registry and live boundary; `src/aeat/application/registry`.

### Phase `W55.P272` - shadow duplicate removal

This Phase delivers shadow duplicate removal for registry and live boundary as required by `2026-05-12-cli-workflow-redesign-app-registry-boundary-adr`.

- [ ] `W55.P272.S1627` - Audit duplicate implementations that overlap registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P272.S1628` - Delete duplicate backend branches that compete with registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P272.S1629` - Remove stale aliases that bypass the canonical service for registry and live boundary; `src/aeat/entrypoints/cli`.
- [ ] `W55.P272.S1630` - Migrate internal callers to the canonical service for registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P272.S1631` - Remove stale fixtures and tests that encode duplicate behavior for registry and live boundary; `tests/application/registry`.
- [ ] `W55.P272.S1632` - Update boundary inventory entries that describe duplicate behavior for registry and live boundary; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W55.P273` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for registry and live boundary as required by `2026-05-12-cli-workflow-redesign-app-registry-boundary-adr`.

- [ ] `W55.P273.S1633` - Delete compatibility shims that preserve rejected behavior for registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P273.S1634` - Delete placeholder stubs that claim support for registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P273.S1635` - Replace stubbed paths with real backend service calls for registry and live boundary; `src/aeat/application/registry`.
- [ ] `W55.P273.S1636` - Remove deprecated command spelling and help text for registry and live boundary; `src/aeat/entrypoints/cli`.
- [ ] `W55.P273.S1637` - Remove tests that assert shim or stub behavior for registry and live boundary; `tests/application/registry`.
- [ ] `W55.P273.S1638` - Record the removed shim and stub surfaces for registry and live boundary; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W55.P274` - real behavior verification

This Phase delivers real behavior verification for registry and live boundary as required by `2026-05-12-cli-workflow-redesign-app-registry-boundary-adr`.

- [ ] `W55.P274.S1639` - Add service contract tests for registry and live boundary; `tests/application/registry`.
- [ ] `W55.P274.S1640` - Add persistence or registry integration tests for registry and live boundary; `tests/application/registry`.
- [ ] `W55.P274.S1641` - Add negative tests proving rejected aliases do not reach registry and live boundary; `tests/entrypoints/cli`.
- [ ] `W55.P274.S1642` - Add command behavior tests that exercise registry and live boundary through real services; `tests/entrypoints/cli`.
- [ ] `W55.P274.S1643` - Add end-to-end workflow coverage for registry and live boundary; `tests`.
- [ ] `W55.P274.S1644` - Run the targeted test slice for registry and live boundary without skips or xfails; `tests/application/registry`.

### Phase `W55.P275` - thin cli exposure

This Phase delivers thin cli exposure for registry and live boundary as required by `2026-05-12-cli-workflow-redesign-app-registry-boundary-adr`.

- [ ] `W55.P275.S1645` - Expose accepted command handlers for registry and live boundary under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W55.P275.S1646` - Keep argument parsing for registry and live boundary separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W55.P275.S1647` - Delegate registry and live boundary execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W55.P275.S1648` - Render registry and live boundary results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W55.P275.S1649` - Handle registry and live boundary failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W55.P275.S1650` - Validate help text for registry and live boundary uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W56` - app review queue execution

This Wave implements the `2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr` decision for operator review queue. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W56.P276` - backend implementation

This Phase delivers backend implementation for operator review queue as required by `2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr`.

- [ ] `W56.P276.S1651` - Map the `2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr` decision into non-CLI service ownership for operator review queue; `src/aeat/application/review`.
- [ ] `W56.P276.S1652` - Implement Pydantic command and result contracts for operator review queue; `src/aeat/application/review`.
- [ ] `W56.P276.S1653` - Wire application or domain services required by operator review queue; `src/aeat/application/review`.
- [ ] `W56.P276.S1654` - Connect persistence, bucket events, registry data, or provider adapters required by operator review queue; `src/aeat/application/review`.
- [ ] `W56.P276.S1655` - Route existing backend functionality into the canonical service for operator review queue; `src/aeat/application/review`.
- [ ] `W56.P276.S1656` - Record service-level error codes and log fields for operator review queue; `src/aeat/application/review`.

### Phase `W56.P277` - shadow duplicate removal

This Phase delivers shadow duplicate removal for operator review queue as required by `2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr`.

- [ ] `W56.P277.S1657` - Audit duplicate implementations that overlap operator review queue; `src/aeat/application/review`.
- [ ] `W56.P277.S1658` - Delete duplicate backend branches that compete with operator review queue; `src/aeat/application/review`.
- [ ] `W56.P277.S1659` - Remove stale aliases that bypass the canonical service for operator review queue; `src/aeat/entrypoints/cli`.
- [ ] `W56.P277.S1660` - Migrate internal callers to the canonical service for operator review queue; `src/aeat/application/review`.
- [ ] `W56.P277.S1661` - Remove stale fixtures and tests that encode duplicate behavior for operator review queue; `tests/application/review`.
- [ ] `W56.P277.S1662` - Update boundary inventory entries that describe duplicate behavior for operator review queue; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W56.P278` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for operator review queue as required by `2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr`.

- [ ] `W56.P278.S1663` - Delete compatibility shims that preserve rejected behavior for operator review queue; `src/aeat/application/review`.
- [ ] `W56.P278.S1664` - Delete placeholder stubs that claim support for operator review queue; `src/aeat/application/review`.
- [ ] `W56.P278.S1665` - Replace stubbed paths with real backend service calls for operator review queue; `src/aeat/application/review`.
- [ ] `W56.P278.S1666` - Remove deprecated command spelling and help text for operator review queue; `src/aeat/entrypoints/cli`.
- [ ] `W56.P278.S1667` - Remove tests that assert shim or stub behavior for operator review queue; `tests/application/review`.
- [ ] `W56.P278.S1668` - Record the removed shim and stub surfaces for operator review queue; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W56.P279` - real behavior verification

This Phase delivers real behavior verification for operator review queue as required by `2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr`.

- [ ] `W56.P279.S1669` - Add service contract tests for operator review queue; `tests/application/review`.
- [ ] `W56.P279.S1670` - Add persistence or registry integration tests for operator review queue; `tests/application/review`.
- [ ] `W56.P279.S1671` - Add negative tests proving rejected aliases do not reach operator review queue; `tests/entrypoints/cli`.
- [ ] `W56.P279.S1672` - Add command behavior tests that exercise operator review queue through real services; `tests/entrypoints/cli`.
- [ ] `W56.P279.S1673` - Add end-to-end workflow coverage for operator review queue; `tests`.
- [ ] `W56.P279.S1674` - Run the targeted test slice for operator review queue without skips or xfails; `tests/application/review`.

### Phase `W56.P280` - thin cli exposure

This Phase delivers thin cli exposure for operator review queue as required by `2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr`.

- [ ] `W56.P280.S1675` - Expose accepted command handlers for operator review queue under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W56.P280.S1676` - Keep argument parsing for operator review queue separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W56.P280.S1677` - Delegate operator review queue execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W56.P280.S1678` - Render operator review queue results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W56.P280.S1679` - Handle operator review queue failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W56.P280.S1680` - Validate help text for operator review queue uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W57` - evidence bundle shape

This Wave implements the `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr` decision for evidence bundle lifecycle. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W57.P281` - backend implementation

This Phase delivers backend implementation for evidence bundle lifecycle as required by `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr`.

- [ ] `W57.P281.S1681` - Map the `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr` decision into non-CLI service ownership for evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P281.S1682` - Implement Pydantic command and result contracts for evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P281.S1683` - Wire application or domain services required by evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P281.S1684` - Connect persistence, bucket events, registry data, or provider adapters required by evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P281.S1685` - Route existing backend functionality into the canonical service for evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P281.S1686` - Record service-level error codes and log fields for evidence bundle lifecycle; `src/aeat/application/evidence`.

### Phase `W57.P282` - shadow duplicate removal

This Phase delivers shadow duplicate removal for evidence bundle lifecycle as required by `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr`.

- [ ] `W57.P282.S1687` - Audit duplicate implementations that overlap evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P282.S1688` - Delete duplicate backend branches that compete with evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P282.S1689` - Remove stale aliases that bypass the canonical service for evidence bundle lifecycle; `src/aeat/entrypoints/cli`.
- [ ] `W57.P282.S1690` - Migrate internal callers to the canonical service for evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P282.S1691` - Remove stale fixtures and tests that encode duplicate behavior for evidence bundle lifecycle; `tests/application/evidence`.
- [ ] `W57.P282.S1692` - Update boundary inventory entries that describe duplicate behavior for evidence bundle lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W57.P283` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for evidence bundle lifecycle as required by `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr`.

- [ ] `W57.P283.S1693` - Delete compatibility shims that preserve rejected behavior for evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P283.S1694` - Delete placeholder stubs that claim support for evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P283.S1695` - Replace stubbed paths with real backend service calls for evidence bundle lifecycle; `src/aeat/application/evidence`.
- [ ] `W57.P283.S1696` - Remove deprecated command spelling and help text for evidence bundle lifecycle; `src/aeat/entrypoints/cli`.
- [ ] `W57.P283.S1697` - Remove tests that assert shim or stub behavior for evidence bundle lifecycle; `tests/application/evidence`.
- [ ] `W57.P283.S1698` - Record the removed shim and stub surfaces for evidence bundle lifecycle; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W57.P284` - real behavior verification

This Phase delivers real behavior verification for evidence bundle lifecycle as required by `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr`.

- [ ] `W57.P284.S1699` - Add service contract tests for evidence bundle lifecycle; `tests/application/evidence`.
- [ ] `W57.P284.S1700` - Add persistence or registry integration tests for evidence bundle lifecycle; `tests/application/evidence`.
- [ ] `W57.P284.S1701` - Add negative tests proving rejected aliases do not reach evidence bundle lifecycle; `tests/entrypoints/cli`.
- [ ] `W57.P284.S1702` - Add command behavior tests that exercise evidence bundle lifecycle through real services; `tests/entrypoints/cli`.
- [ ] `W57.P284.S1703` - Add end-to-end workflow coverage for evidence bundle lifecycle; `tests`.
- [ ] `W57.P284.S1704` - Run the targeted test slice for evidence bundle lifecycle without skips or xfails; `tests/application/evidence`.

### Phase `W57.P285` - thin cli exposure

This Phase delivers thin cli exposure for evidence bundle lifecycle as required by `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr`.

- [ ] `W57.P285.S1705` - Expose accepted command handlers for evidence bundle lifecycle under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W57.P285.S1706` - Keep argument parsing for evidence bundle lifecycle separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W57.P285.S1707` - Delegate evidence bundle lifecycle execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W57.P285.S1708` - Render evidence bundle lifecycle results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W57.P285.S1709` - Handle evidence bundle lifecycle failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W57.P285.S1710` - Validate help text for evidence bundle lifecycle uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W58` - workflow engine harvest

This Wave implements the `2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr` decision for workflow engine backend harvest. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W58.P286` - backend implementation

This Phase delivers backend implementation for workflow engine backend harvest as required by `2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr`.

- [ ] `W58.P286.S1711` - Map the `2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr` decision into non-CLI service ownership for workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P286.S1712` - Implement Pydantic command and result contracts for workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P286.S1713` - Wire application or domain services required by workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P286.S1714` - Connect persistence, bucket events, registry data, or provider adapters required by workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P286.S1715` - Route existing backend functionality into the canonical service for workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P286.S1716` - Record service-level error codes and log fields for workflow engine backend harvest; `src/aeat/application/workflow`.

### Phase `W58.P287` - shadow duplicate removal

This Phase delivers shadow duplicate removal for workflow engine backend harvest as required by `2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr`.

- [ ] `W58.P287.S1717` - Audit duplicate implementations that overlap workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P287.S1718` - Delete duplicate backend branches that compete with workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P287.S1719` - Remove stale aliases that bypass the canonical service for workflow engine backend harvest; `src/aeat/entrypoints/cli`.
- [ ] `W58.P287.S1720` - Migrate internal callers to the canonical service for workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P287.S1721` - Remove stale fixtures and tests that encode duplicate behavior for workflow engine backend harvest; `tests/application/workflow`.
- [ ] `W58.P287.S1722` - Update boundary inventory entries that describe duplicate behavior for workflow engine backend harvest; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W58.P288` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for workflow engine backend harvest as required by `2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr`.

- [ ] `W58.P288.S1723` - Delete compatibility shims that preserve rejected behavior for workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P288.S1724` - Delete placeholder stubs that claim support for workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P288.S1725` - Replace stubbed paths with real backend service calls for workflow engine backend harvest; `src/aeat/application/workflow`.
- [ ] `W58.P288.S1726` - Remove deprecated command spelling and help text for workflow engine backend harvest; `src/aeat/entrypoints/cli`.
- [ ] `W58.P288.S1727` - Remove tests that assert shim or stub behavior for workflow engine backend harvest; `tests/application/workflow`.
- [ ] `W58.P288.S1728` - Record the removed shim and stub surfaces for workflow engine backend harvest; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W58.P289` - real behavior verification

This Phase delivers real behavior verification for workflow engine backend harvest as required by `2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr`.

- [ ] `W58.P289.S1729` - Add service contract tests for workflow engine backend harvest; `tests/application/workflow`.
- [ ] `W58.P289.S1730` - Add persistence or registry integration tests for workflow engine backend harvest; `tests/application/workflow`.
- [ ] `W58.P289.S1731` - Add negative tests proving rejected aliases do not reach workflow engine backend harvest; `tests/entrypoints/cli`.
- [ ] `W58.P289.S1732` - Add command behavior tests that exercise workflow engine backend harvest through real services; `tests/entrypoints/cli`.
- [ ] `W58.P289.S1733` - Add end-to-end workflow coverage for workflow engine backend harvest; `tests`.
- [ ] `W58.P289.S1734` - Run the targeted test slice for workflow engine backend harvest without skips or xfails; `tests/application/workflow`.

### Phase `W58.P290` - thin cli exposure

This Phase delivers thin cli exposure for workflow engine backend harvest as required by `2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr`.

- [ ] `W58.P290.S1735` - Expose accepted command handlers for workflow engine backend harvest under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W58.P290.S1736` - Keep argument parsing for workflow engine backend harvest separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W58.P290.S1737` - Delegate workflow engine backend harvest execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W58.P290.S1738` - Render workflow engine backend harvest results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W58.P290.S1739` - Handle workflow engine backend harvest failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W58.P290.S1740` - Validate help text for workflow engine backend harvest uses accepted vocabulary only; `tests/entrypoints/cli`.

## Wave `W59` - workflow resumption semantics

This Wave implements the `2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr` decision for workflow resumption semantics. It delivers backend behavior before CLI exposure, removes shadow paths, removes shims and stubs, proves the behavior with real tests, and then exposes only thin CLI adapters that call centralized services.

### Phase `W59.P291` - backend implementation

This Phase delivers backend implementation for workflow resumption semantics as required by `2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr`.

- [ ] `W59.P291.S1741` - Map the `2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr` decision into non-CLI service ownership for workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P291.S1742` - Implement Pydantic command and result contracts for workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P291.S1743` - Wire application or domain services required by workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P291.S1744` - Connect persistence, bucket events, registry data, or provider adapters required by workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P291.S1745` - Route existing backend functionality into the canonical service for workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P291.S1746` - Record service-level error codes and log fields for workflow resumption semantics; `src/aeat/application/workflow`.

### Phase `W59.P292` - shadow duplicate removal

This Phase delivers shadow duplicate removal for workflow resumption semantics as required by `2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr`.

- [ ] `W59.P292.S1747` - Audit duplicate implementations that overlap workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P292.S1748` - Delete duplicate backend branches that compete with workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P292.S1749` - Remove stale aliases that bypass the canonical service for workflow resumption semantics; `src/aeat/entrypoints/cli`.
- [ ] `W59.P292.S1750` - Migrate internal callers to the canonical service for workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P292.S1751` - Remove stale fixtures and tests that encode duplicate behavior for workflow resumption semantics; `tests/application/workflow`.
- [ ] `W59.P292.S1752` - Update boundary inventory entries that describe duplicate behavior for workflow resumption semantics; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W59.P293` - de-shim and de-stub cleanup

This Phase delivers de-shim and de-stub cleanup for workflow resumption semantics as required by `2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr`.

- [ ] `W59.P293.S1753` - Delete compatibility shims that preserve rejected behavior for workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P293.S1754` - Delete placeholder stubs that claim support for workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P293.S1755` - Replace stubbed paths with real backend service calls for workflow resumption semantics; `src/aeat/application/workflow`.
- [ ] `W59.P293.S1756` - Remove deprecated command spelling and help text for workflow resumption semantics; `src/aeat/entrypoints/cli`.
- [ ] `W59.P293.S1757` - Remove tests that assert shim or stub behavior for workflow resumption semantics; `tests/application/workflow`.
- [ ] `W59.P293.S1758` - Record the removed shim and stub surfaces for workflow resumption semantics; `src/aeat/entrypoints/cli/test_backend_boundary.py`.

### Phase `W59.P294` - real behavior verification

This Phase delivers real behavior verification for workflow resumption semantics as required by `2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr`.

- [ ] `W59.P294.S1759` - Add service contract tests for workflow resumption semantics; `tests/application/workflow`.
- [ ] `W59.P294.S1760` - Add persistence or registry integration tests for workflow resumption semantics; `tests/application/workflow`.
- [ ] `W59.P294.S1761` - Add negative tests proving rejected aliases do not reach workflow resumption semantics; `tests/entrypoints/cli`.
- [ ] `W59.P294.S1762` - Add command behavior tests that exercise workflow resumption semantics through real services; `tests/entrypoints/cli`.
- [ ] `W59.P294.S1763` - Add end-to-end workflow coverage for workflow resumption semantics; `tests`.
- [ ] `W59.P294.S1764` - Run the targeted test slice for workflow resumption semantics without skips or xfails; `tests/application/workflow`.

### Phase `W59.P295` - thin cli exposure

This Phase delivers thin cli exposure for workflow resumption semantics as required by `2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr`.

- [ ] `W59.P295.S1765` - Expose accepted command handlers for workflow resumption semantics under `aeat config` or `aeat app`; `src/aeat/entrypoints/cli`.
- [ ] `W59.P295.S1766` - Keep argument parsing for workflow resumption semantics separate from backend behavior; `src/aeat/entrypoints/cli`.
- [ ] `W59.P295.S1767` - Delegate workflow resumption semantics execution to centralized backend services; `src/aeat/entrypoints/cli`.
- [ ] `W59.P295.S1768` - Render workflow resumption semantics results with `_emit` or schema emitters; `src/aeat/entrypoints/cli`.
- [ ] `W59.P295.S1769` - Handle workflow resumption semantics failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `W59.P295.S1770` - Validate help text for workflow resumption semantics uses accepted vocabulary only; `tests/entrypoints/cli`.
