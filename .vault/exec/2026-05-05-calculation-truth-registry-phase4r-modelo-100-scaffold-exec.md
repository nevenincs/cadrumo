---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-modelo-100-renta-source-dependency-reference]]'
  - '[[2026-05-05-modelo-100-renta-aggregation-audit]]'
  - '[[2026-05-05-calculation-truth-registry-phase4r-renta-direct-estimation-review-audit]]'
---



# `calculation-truth-registry` `Phase 4R` `modelo-100-scaffold`

Created the first central Modelo 100 registry scaffold under the accepted
calculation truth registry architecture.

- Created: `registry/aeat/modelos/100.toml`
- Created: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- Created: `corpus/aeat_official/renta_web_open/renta-web-open.html`
- Updated: `registry/aeat/legal/irpf.toml`
- Updated: `src/aeat/domain/calculations/registry/_ids.py`
- Created: `src/aeat/domain/calculations/registry/_constructs.py`
- Created: `corpus/aeat_official/instructions/modelo_100/files/modelo-100-procedure.html`
- Updated: `src/aeat/domain/calculations/registry/_schema.py`
- Updated: `src/aeat/domain/calculations/registry/_remote_state_guard.py`
- Updated: `src/aeat/domain/calculations/registry/_snapshot.py`
- Updated: `src/aeat/domain/calculations/registry/_validate.py`
- Updated: `src/aeat/domain/calculations/registry/_export_parse.py`
- Updated: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- Updated: `src/aeat/adapters/outbound/aeat/sede/_schema.py`
- Updated: `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`
- Updated: `src/aeat/core/errors/registry/_entrypoints.py`
- Updated: `pyproject.toml`
- Updated: `uv.lock`
- Updated: `src/aeat/domain/calculations/registry/__init__.py`
- Updated: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Updated: `.vault/audit/2026-05-05-modelo-100-renta-aggregation-audit.md`
- Created: `tests/fixtures/aeat-sede/submitted-files/modelo-100-2023-0A-redacted.xml`

## Description

The new Modelo 100 registry file declares the parent Modelo 100 identity,
ejercicio 2020 through ejercicio 2025 revisions, official AEAT record-design
source references, record-design layout parity decisions, and the ejercicio
2025 BOE annual order source/legal references.

The 2025 revision also declares initial cross-model dependency bindings and
relations for currently registered source modelos only: 111, 115, 123, 130,
131, and 180. The registry does not declare relations to source modelos that do
not yet exist as TOML authorities.

Renta WEB Open is registered as local AEAT corpus evidence and as a guarded
open-simulator cross-reference for ejercicio 2025. It allows synthetic parity
evidence without authentication and forbids authenticated filing, signing,
payment, server-side save, amendment, cancellation, and document-submission
actions.

This step does not claim full Renta calculation completion. Final-settlement
casillas, full formula coverage, extraction profiles, export/import layout
coverage, observation parsing, CCAA legal coverage, and full Renta subdomain
implementation remain open plan work.

The registry backend now supports generic revision constructs. A construct
references explicit revision members such as bindings, relations, workbook
parity refs, cross-references, extraction profiles, formulas, casillas, export
layouts, and application links. The validator checks that those members exist
and are covered by the construct legal/source refs. Modelo 100 ejercicio 2025
now declares `renta-source-foundation`, `renta-dependent-modelos`, and
`renta-payments-retentions` as the first construct records.

The scaffold now also has initial section constructs for `renta-work-income`,
`renta-real-estate-capital`, `renta-movable-capital`, and
`renta-economic-activities`. These constructs classify already registered
dependency relations only. They do not claim final filing-grade casilla or
formula coverage.

The live-read priority slice added `modelo-100-filed-declarations-read` for
AEAT `Consulta de declaraciones presentadas`. It is an authenticated read-only
observation surface, not executable parity and not legal authority. The
registry maps it to the remote-state guard, permits only read HTTP methods, and
requires encrypted observation handling before any captured value can feed a
filing-grade calculation.

The authenticated read surface is now declared for every supported Modelo 100
revision from ejercicio 2020 through ejercicio 2025. The Sede declaration
reader selects its remote-state guard from the validated registry snapshot once
a concrete declaration row identifies modelo, ejercicio, and period. The
generic declarations listing path still uses the generic authenticated
read-only policy until a row-specific snapshot can be selected.

Modelo 100 submitted-file parsing now has a generic `xml_dictionary` export
layout mode driven by official AEAT dictionary source references and parsed
with `defusedxml`. The 2020 through 2025 revisions declare XML dictionary
export layouts with export application links. A live read-only capture on
2026-05-05 for one available ejercicio 2023 row persisted the register row,
justificante, and submitted file as encrypted financial artefacts and produced
77 normalized casilla observations. No AEAT write operation was executed.

The live capture now has a committed sanitized submitted-file fixture for
Modelo 100 ejercicio 2023. The fixture keeps the official XML structure and
dictionary paths, but replaces identity, address, reference, and amount values
with typed synthetic values. The Sede tests parse it through the 2023 registry
snapshot and official AEAT dictionary, then persist the resulting
`FiledDeclarationObservation` and XML artefact through the encrypted filed-data
store.

The filed-observation relation tests now cover Modelo 100 ejercicio 2025
dependency resolution from standardized observations across the declared source
modelos. That includes Modelo 130 and Modelo 131 quarterly payment observations
feeding the Renta final-settlement relation layer, with hard failures for
missing or duplicated source periods. The Sede observation schema now accepts
the same 32-character casilla id envelope as the central registry schema so
registered semantic ids such as annual-summary totals can flow through the
standard observation path.

The dependency classification gate now validates Modelo 100 relation ownership
against supported source modelos 111, 115, 123, 130, 131, and 180. Each
classification must cite existing legal and source references, target existing
constructs, point to existing relations, and keep the declared source modelo in
sync with the relation it classifies.

The first Renta calculation slice covers the ejercicio 2025 payments-on-account
settlement path. Casilla 0604 is computed from the registered Modelo 130 and
Modelo 131 filed-observation relations, and casilla 0609 totals the official
payments-on-account casilla set. The calculation is exposed through the generic
registry calculation application link, so the Python runtime executes validated
registry data instead of model-specific hardcoding.

The second Renta calculation slice covers ejercicio 2025 economic activity
direct-estimation subtotals. The registry now declares the official income
casillas 0171 through 0180, the direct-estimation expense casillas feeding 0218,
normal-method expense total 0220, intermediate difference 0221, simplified
expense total 0223, and irregular-income reduction input 0225. These formulas
cite the reviewed AEAT Renta 2025 manual as official source guidance, while the
record-design dictionary remains layout evidence.

The direct-estimation net-return branch is also now resolved in the registry.
Casilla 0224 selects the normal or simplified path based on the registered mode
binding, casilla 0226 applies the irregular-income and accounting adjustment
reduction chain, casilla 0231 propagates the reduced net return, and casilla
0235 applies the remaining direct-estimation reductions for the 2025 slice.
The corresponding registry tests exercise both mode branches against the real
calculator instead of asserting declaration-state metadata.

The objective-estimation reader surface now also round-trips the record-design
outputs 1479, 1553, and 1577 from the 2025 export layout. Those outputs remain
informational rather than calculated formulas, but they are now visible through
the same registry-backed export parser path and covered by behavior tests.

The registry validator now extracts text from reviewed AEAT manual PDFs and
normalizes source text accent-insensitively before checking formula citations.
That closes the gap where PDF manuals existed in corpus but could not
participate in source-citation validation.

The scoped review of this slice found no blocking issues. The review checked
that the new formulas are grounded in AEAT manual guidance, that construct
closure stayed strict, and that tests exercise calculation behavior rather than
development-state assertions.

The public registry package also exports generic construct resolution helpers
that turn construct member ids into concrete revision member objects after the
registry has been loaded and validated.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_registry_schema.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_catalogue_verification.py -q`
  passed.
- `uv run ruff check src\aeat\domain\calculations\registry\_ids.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\_snapshot.py src\aeat\domain\calculations\registry\__init__.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\_ids.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\_snapshot.py src\aeat\domain\calculations\registry\__init__.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_remote_state_guard.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py -q`
  passed.
- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py -q`
  passed.
- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py::TestFiledObservationRelations -q`
  passed.
- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_relation_closure.py -q`
  passed.
- `uv run ruff check src\aeat\adapters\outbound\aeat\sede\_schema.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `uv run ty check src\aeat\adapters\outbound\aeat\sede\_schema.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `uv run aeat app registry verify --json`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py::TestFiledObservationRelations src\aeat\domain\calculations\registry\test_relation_closure.py -q`
  passed.
- `git diff --check`
  passed.
- `git diff --check`
  passed.
- `uv run ruff check src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_export_parse.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\core\errors\registry\_entrypoints.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_export_parse.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\adapters\outbound\aeat\sede\_declarations.py src\aeat\core\errors\registry\_entrypoints.py`
  passed.
- `uv run aeat app registry list-filed-data --modelo 100 --from-year 2020 --to-year 2024 --json`
  completed read-only and found historical filed rows for ejercicios 2021,
  2022, and 2023.
- `uv run aeat app registry capture-filed-data --modelo 100 --year 2023 --period 0A --limit 1 --json`
  completed read-only with one encrypted observation and 77 normalized casilla
  observations.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py -q`
  passed with the dependency-classification and payments-on-account slice.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py::TestFiledObservationRelations src\aeat\domain\calculations\registry\test_relation_closure.py -q`
  passed.
- `uv run ruff check src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\adapters\outbound\aeat\sede\_schema.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\adapters\outbound\aeat\sede\_schema.py`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py -q`
  passed with the direct-estimation Renta slice.
- `uv run ruff check src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\_text.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\_text.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `uv run aeat app registry verify --json`
  passed.
