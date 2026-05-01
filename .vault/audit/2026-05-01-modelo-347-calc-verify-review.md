---
tags:
  - '#audit'
  - '#modelo-347-calc-verify'
date: '2026-05-01'
related:
  - '[[2026-05-01-modelo-347-calc-verify-research]]'
  - '[[2026-05-01-modelo-347-calc-verify-adr]]'
  - '[[2026-05-01-modelo-347-calc-verify-plan]]'
---

# `modelo-347-calc-verify` Code Review

M347-REVIEW-001 | HIGH | Detail extraction only works for synthetic marker lines

`src/aeat/adapters/inbound/declaracion/_extractors/modelo_347_v2025.py` extracts detail rows exclusively through `_DETAIL_RE`, which matches text lines beginning with `M347-RECORD |`. The new round-trip and Kent tests generate exactly that private marker in `src/aeat/adapters/inbound/declaracion/test_quarterly_extractors.py` and `tests/integration/test_kent_workflows.py`, so they prove the synthetic marker protocol rather than the Modelo 347 declaration layout. This misses the issue intent and the docs claim that Kent can import full Modelo 347 declaration PDFs for 2024/2025/2026 with typed per-counterparty rows. A real AEAT declaration PDF is unlikely to contain `M347-RECORD`, so per-counterparty extraction can silently produce an empty tuple or only synthetic rows.

M347-REVIEW-002 | HIGH | The typed record model omits BOE fields required by the research scope

`src/aeat/domain/modelos/m347/_records.py` models a useful subset, but it omits researched type-2 declared-record fields such as EU operator VAT ID, cash-accounting operation flag, reverse-charge flag, non-customs warehouse flag, annual cash-accounting amount, BDNS convocatoria, quarterly real-estate transmission amounts, record type, model, exercise, and declarant NIF. The research document explicitly lists these fields for the 2025+ BOE schema, and the plan says the extractor should produce strict detail records for every field. Because `record_fields` is derived from this incomplete model, the manifests make the subset look authoritative. The docs update then overstates the shipped surface as typed per-counterparty records and per-year schema manifests.

M347-REVIEW-003 | MEDIUM | Strict pydantic constraints are bypassed after normalization

`src/aeat/domain/modelos/m347/_records.py` validates `declared_tax_id` and `declared_name` with `min_length=1`, then strips and normalizes them in `mode="after"` validators. Inputs containing only whitespace pass the field constraint and are normalized to empty strings. I confirmed this with a direct construction that produced `declared_tax_id == ""` and `declared_name == ""`. That violates the strict boundary-record requirement and can allow invalid counterparty identity data into parity verification.

M347-REVIEW-004 | MEDIUM | Summary verifier publishes a synthetic ruleset id despite no ruleset

`src/aeat/application/verification/_verify_summary.py` returns `ruleset_id=f"modelo_347.summary.{declaracion.ejercicio}"`. The research and ADR require no formula ruleset for Modelo 347, with Tier-S verification returning the existing verdict shape using `ruleset_id=None`. Emitting a ruleset-looking identifier can mislead downstream status displays or audit logs into treating summary parity as a formula ruleset, which is exactly what the ADR avoids.

M347-REVIEW-005 | LOW | Test coverage misses row-drift and low-confidence extraction cases

The new tests cover happy paths across 2024/2025/2026 and a tampered resumen total, but they do not cover a tampered detail row while the resumen remains unchanged, partial or ambiguous detail extraction, missing detail rows, or preservation of the full BOE field set. This leaves the riskiest extractor behavior unguarded, especially because the current tests render and parse the same synthetic `M347-RECORD` marker format.

M347-REVIEW-006 | LOW | Import-linter could not be used as verification evidence

`uv run lint-imports` exited before evaluating contracts because `.importlinter` contains a stale ignored import entry for `aeat.domain.attachments._repository -> aeat.adapters.persistence.storage.*`. Targeted tests passed, but layered-import safety for this change was not confirmed by import-linter in this review run.

## Review Checks

Targeted tests run: `uv run pytest src/aeat/domain/modelos/m347 src/aeat/application/verification/test_verify_summary.py src/aeat/adapters/inbound/declaracion/test_quarterly_extractors.py::TestModelo347V2025Extractor tests/integration/test_kent_workflows.py::TestKentImportsModelo347Declaracion` passed with 15 tests.

No live-submit path was found in the reviewed M347 implementation diff. The only write-shaped hits in the searched scope were test fixture PDF writes and existing filing/reconcile guards outside the new M347 path.

## Closure Notes

M347-REVIEW-001 addressed: the extractor now supports both deterministic `M347-RECORD |` fixture rows and an AEAT-like human-readable `Declarado ... Clave ... Total ... 1T ...` detail-line shape, with round-trip coverage for both.

M347-REVIEW-002 addressed: `Modelo347RecordLine` now carries the BOE type-2 constants, ejercicio, declarante NIF, mutually exclusive Spanish NIF / EU VAT operator id, cash-accounting, reverse-charge, non-customs-deposit, real-estate quarterly amounts, cash-accounting annual amount, and BDNS call number fields.

M347-REVIEW-003 addressed: post-normalisation validators reject blank identity and name values.

M347-REVIEW-004 addressed: `verify_modelo_347_summary` now returns `ruleset_id=None`.

M347-REVIEW-005 addressed with additional tests for summary count mismatch, row drift, broader field preservation, and the human-readable detail extraction path.

M347-REVIEW-006 remains an external tooling/config blocker: `just lint-imports` first fails on stale ignored imports; removing them reveals broad pre-existing architecture-contract violations outside the M347 diff. The M347 diff itself follows the intended dependency direction.

## Gemini Closure Notes

The Gemini review findings were addressed after PR open. The human-readable M347 detail extractor now uses the shared Spanish decimal parser for `1.234,56`/`1 234,56`/`1234.56` formats, requires explicit `NIF` and `Nombre` delimiters, and preserves names that contain the word `Clave`. The Tier-S verifier now treats omitted optional zero-valued summary casillas as printed zero before applying tolerance, avoiding false `NEEDS_REVIEW` verdicts when AEAT omits zero cash totals.
