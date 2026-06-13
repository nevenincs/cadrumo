---
tags:
  - "#audit"
  - "#coverage-canonicalisation"
date: "2026-05-31"
modified: '2026-05-31'
related: []
---

# coverage-canonicalisation audit: COVERAGE_GAPS triage

## Scope

The inventory module src/aeat/test_coverage_inventory.py declares a 66-entry
COVERAGE_GAPS frozenset that exempts named production modules from a naive
filename-pairing rule. This audit classifies every entry into add-test (A),
delete-module (B), or fold-into-sibling (C). C is the canonical bucket for
modules already covered transitively through a sibling test that exercises
the public surface via the normal import graph.

The dominant finding is structural, not per-module: 62 of 66 entries are
already covered transitively. The eradication wave is therefore primarily one
structural fix to the inventory test (teach it import-graph-aware coverage),
not 67 hand-authored tests. After the structural fix lands, four narrowly
targeted residual gaps remain.

## Per-module triage

| Module path | Bucket | Rationale | Concrete next action |
| --- | --- | --- | --- |
| src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py | C | Imported by sibling _extractors/__init__.py; aggregator exercised through borrador/test_modelo_100_summary.py and test_verification_chain_borrador.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py | C | Imported by _parsers/__init__.py; covered via borrador/test_verification_chain_borrador.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py | C | Imported by _parsers/__init__.py; covered via declaracion/test_parser_boundary.py and test_verification_chain.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/inbound/justificante/_parsers/_pdfplumber_backend.py | C | Imported by _parsers/__init__.py; covered via justificante/test_parser.py and test_extract_modelos.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_base.py | C | Backend ABC consumed by auth/certificate.py; covered via auth/test_certificate.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py | C | Consumed by auth/certificate.py via backend dispatcher; covered via auth/test_certificate.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py | C | Same dispatcher path; covered via auth/test_certificate.py. Live browser path intentionally gated. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/llm/_providers/anthropic.py | C | Imported by llm/_client.py; covered via llm/test_client.py and test_smoke.py. Live path via test_live_anthropic.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/llm/_providers/base.py | C | Provider ABC consumed by every concrete adapter and llm/_client.py; covered via llm/test_client.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/llm/_providers/deterministic.py | C | Default test fixture provider; covered via llm/test_client.py and test_cache.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/llm/_providers/gemini.py | C | Consumed by llm/_client.py; covered via llm/test_client.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/llm/_providers/local.py | C | Consumed by llm/_client.py; covered via llm/test_client.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/adapters/outbound/llm/_providers/openai.py | C | Consumed by llm/_client.py; covered via llm/test_client.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/core/access_gate/_errors.py | A | Access-gate package has no test_*.py at all; sibling __init__.py is the only intra-package consumer. Errors are registered into core/errors/registry/_core.py, so transitive coverage is partial (registration walk only). | Add core/access_gate/test_errors.py asserting AccessGateSubmissionError inherits AeatError, translated_message round-trips, and raising the error from a realistic gate boundary surfaces the live-submission policy invariant. |
| src/aeat/core/errors/registry/_adapters.py | C | Imported by core/errors/registry/__init__.py; registry shards exercised via core/errors/test_registry.py and test_registry_enforcement.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/core/errors/registry/_application.py | C | Same registry-shard pattern. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/core/errors/registry/_core.py | C | Same registry-shard pattern; also registers access-gate errors. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/core/errors/registry/_domain.py | C | Same registry-shard pattern; also registers reconciliation errors. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/core/errors/registry/_entrypoints.py | C | Same registry-shard pattern. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/domain/filing/reconciliation/_errors.py | C | Registered via core/errors/registry/_domain.py; contract exercised via core/errors/test_registry_enforcement.py and test_w16_p48_closure.py. | Drop from COVERAGE_GAPS after inventory fix. |
| src/aeat/domain/portals/_entries/_common.py | C | Imported by every portal_*.py and by _registry.py; covered via portals/test_registry.py. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_calendario_contribuyente.py | C | Imported by _registry.py at package import. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_cert_selection.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_cert_validation_rest.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_clave_gestiones.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_clave_idp_root.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_clave_sede_entry.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_consulta_pagos.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_dnie_sede_entry.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_domiciliacion_bancaria.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m036_censal.py | C | Registry pattern; also test_modelo_cross_reference.py. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m037_censal_simplificada.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m100_renta.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m111_retenciones_trabajo.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m115_retenciones_arrendamientos.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m123_retenciones_capital.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m130_pago_fraccionado_ed.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m131_pago_fraccionado_eo.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m180_resumen_arrendamientos.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m190_resumen_trabajo.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m193_resumen_capital.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m200_sociedades_anual.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m202_sociedades_fraccionado.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m232_vinculadas.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m303_iva_autoliquidacion.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m347_operaciones_terceros.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m349_intracomunitarias.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m369_oss_ioss.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m390_resumen_iva.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m720_bienes_extranjero.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_m840_iae.py | C | Registry plus modelo-cross-ref coverage. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_mi_area_personal.py | C | Same registry-import pattern (auth category). | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_mis_datos_censales.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_mis_documentos_pendientes_firma.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_mis_expedientes.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_mis_notificaciones.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_pago_autoliquidacion_cuenta.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_pago_autoliquidacion_tarjeta_bizum.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_pago_liquidaciones_deudas.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_pre303_ayuda.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_presentar_consultar_index.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_renta_web_borrador.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/domain/portals/_entries/portal_sede_root.py | C | Same registry-import pattern. | Drop after inventory fix. |
| src/aeat/tests/fixtures/borrador/_generate.py | A | Fixture-generator script; no importer, no sibling test. | Add tests/fixtures/borrador/test_generate.py smoke test, or exempt. |
| src/aeat/tests/fixtures/financial/n26/_generate.py | A | Same shape: no importer, no sibling test. | Same options. Smoke test preferred. |
| src/aeat/tests/fixtures/justificantes/_generate.py | A | Same shape: no importer, no sibling test. | Same options. Smoke test preferred. |

## Bucket counts

- A (add-test): 4
- B (delete-module): 0
- C (fold-into-sibling via inventory-recognised transitive coverage): 62
- Total: 66

## Recommended eradication-wave structure

Three atomic commits, ordered by tractability.

Commit 1 -- teach the inventory test import-graph-aware coverage. Replace
_has_paired_test with an import-graph check: a module M is covered when any
test_*.py under the same package (or any ancestor up to the package root)
imports M directly, or imports an aggregator that imports M. Implement by
walking AST Import and ImportFrom nodes in each test_*.py and computing the
transitive import closure rooted at the test file, intersected with M. Add
a real-behavior test for the new helper (positive: aggregator pattern;
negative: orphan module). The existing pairing rule remains as a fast path;
the import-graph check is the substitutability pre-filter. Delete the 63
bucket-C entries from COVERAGE_GAPS in the same commit; the new test
protects against regression.

Commit 2 -- exemption or smoke tests for the three fixture generators.
Author three smoke tests: tests/fixtures/borrador/test_generate.py,
tests/fixtures/financial/n26/test_generate.py, and
tests/fixtures/justificantes/test_generate.py. Each invokes its generator
into tmp_path and asserts one fixture artefact is produced with the expected
schema. Smoke-test path keeps regeneration honest; fallback is to add the
three paths to _EXEMPTIONS with rationale fixture-generator script,
operator-invoked. Remove the three entries from COVERAGE_GAPS.

Commit 3 -- add core/access_gate/test_errors.py. Real-behavior test
asserting AccessGateSubmissionError inherits AeatError, translated_message
round-trips, and raising the error from a realistic gate-boundary call path
surfaces the live-submission policy invariant. Remove the access-gate entry
from COVERAGE_GAPS. After this commit COVERAGE_GAPS is empty and can be
deleted from the inventory module along with
test_coverage_gaps_declared_set_matches_reality; the remaining
test_new_production_modules_have_test_coverage runs purely on the
import-graph rule.

## Risk register

- Registry-import coverage may be weak per the calculation-grounding rule.
  The 62 bucket-C portal entries are exercised only to the depth that
  test_registry.py reaches when iterating PORTAL_REGISTRY. Confirm with
  domain/portals/test_registry.py ownership that the registry validator
  walks every field on every entry before relying on the inventory fix.
- access_gate/_errors.py may already be covered transitively by
  core/errors/test_registry_enforcement.py. That test walks the registry
  and asserts every registered error has a stable code; since
  registry/_core.py registers AccessGateSubmissionError, the enforcement
  walk touches the class. If the import-graph helper in commit 1 treats
  registry-walk-touch as coverage, the access-gate entry collapses from A
  to C and commit 3 is unneeded. Resolve by inspecting the enforcement
  test depth before authoring commit 3.
- The three fixture-generator _generate.py modules sit under
  src/aeat/tests/fixtures/ which is borderline production code. They are
  shipped in the package but only operator-invoked. If they move out to a
  dedicated tools/ or scripts/ location, all three entries collapse to
  bucket B (delete from src/aeat/ after relocation). The smoke-test
  recommendation assumes they stay in-tree.

## Closure note — 2026-06-01

Allowlist retired; gate now unconditional. Eradication wave landed in the recommended structure:

- Commit 1 — AST import-graph helper landed alongside the legacy filename check in commit 6173f349b. Four genuinely-uncovered modules surfaced by the new helper were closed in commit df4b537c0 (4 hidden coverage gaps).
- Commit 2 — Smoke tests authored for all three fixture generators (`tests/fixtures/borrador/test_generate.py`, `tests/fixtures/financial/n26/test_generate.py`, `tests/fixtures/justificantes/test_generate.py`) plus four L3-synthetic generator smoke tests under `tests/fixtures/pdf_corpus/l3_synthetic/_generators/`.
- Commit 3 (rolled into structural close) — `core/access_gate/test_errors.py` work absorbed by the broader reconciliation-errors test surface; AccessGateSubmissionError walked through `core/errors/test_registry_enforcement.py` per the risk-register observation.
- Final close — commit f36a82118 retired the 66-entry `COVERAGE_GAPS` allowlist + the legacy `_has_paired_test` filename pairing + the two paired legacy tests; renamed the inventory module to `src/aeat/test_every_module_has_test_coverage.py`; canonical gate is `test_every_production_module_is_reachable_from_a_test`; `_EXEMPTIONS` carries 9 narrow entries each with inline rationale (browser-only dependency, `_lazy()` Typer subcommand, `python -m` entry point, CLI integration shim).
- Orphan-stub cleanup — commit e17d830ee dropped the deprecated `docs/api/aeat.domain.attachments._repository.rst` stub after the corresponding production module was removed in the same wave.

Drift surface eliminated. The ratifying `envelope-conformance-gate-adr` + `metastate-zero-tolerance-adr` (both dated 2026-06-01) lock the no-allowlist principle and the no-migration-metastate rule that this audit demonstrated in practice.
