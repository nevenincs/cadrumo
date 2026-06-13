---
tags: ["#audit", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# Declaration Extraction Convention Hardening Audit

## Scope

Audited the declaration extraction, inbound PDF, registry, core error, core
i18n, and core settings surfaces added or exercised by the current declaration
extraction wave.

## Findings

### W06-001 Raw User-Facing Parse Messages

`src/aeat/adapters/inbound/declaracion/_parser.py` raises
`DeclaracionParseError` and `TemplateNotDetectedError` with raw English
operator-facing strings. The exception classes inherit from the correct
`AeatError` chain, but the messages bypass `tr()` and should be migrated to
locale keys with structured context.

Tracked by `W06.P19.S113`.

### W06-002 Shared PDF Extraction Messages Bypass `tr()`

`src/aeat/adapters/inbound/pdf/_pdfplumber.py` builds raw error strings for
file-not-found, pdfplumber-open failure, and empty text-layer diagnostics. The
callers inject typed exception classes correctly, but the operator-facing
messages need `tr()` coverage or pre-rendered localized labels.

Tracked by `W06.P19.S113`.

### W06-003 Exception Hierarchy Mostly Holds

`DeclaracionParseError` descends from `PdfModeloImportError`, which is
re-exported from the justificante PDF-import root, and registry errors descend
from `AeatError`. The audited production surface does not show a new public
exception outside the core hierarchy. Existing private helper
`_BinaryXlsConversionError` is internal to workbook parity conversion and is
converted to `RegistryValidationError` at the public registry boundary.

Tracked by `W06.P19.S114` for explicit guard coverage.

### W06-004 Broad Exception Handling Needs Guard Coverage Beyond Registry

Registry production modules already have AST hygiene tests preventing bare
`except`, `contextlib.suppress`, pass-only handlers, and broad handlers without
raise/log. Declaration extraction's pypdfium2 fallback logs at debug before
returning `None`, and shared pdfplumber broad handlers re-raise typed errors.
The same AST hygiene should be extended to the inbound declaration/PDF
production modules so this convention stays enforced as parser code expands.

Tracked by `W06.P19.S115`.

### W06-005 Modelo 840 Label Test Is Source-Grounded But Should Be Hardened

`src/aeat/domain/calculations/registry/test_modelo_840_registry.py` validates
the registry label regexes against text extracted from the official AEAT
printed-form PDF. This is not a calculation tautology, but it should also pin
the printed labels `14 Ejercicio` and `15 Declaración de` explicitly so an
overly broad regex cannot satisfy the test without preserving the legal
printed labels.

Tracked by `W06.P19.S116`.

### W06-006 Settings Centralisation Is Preserved On The Audited Path

Declaration extraction and inbound PDF parsing do not add direct environment
access. The relevant central settings surface remains `src/aeat/core/config.py`.
`src/aeat/core/i18n/_render.py` intentionally samples selected environment
variables in its cache key before rebuilding `Settings`; this is an existing
performance-oriented exception documented in that module and not a new
declaration-extraction bypass.

Tracked by `W06.P19.S117`.

### W06-007 Shared Model Boundaries Are Present

Declaration parsing returns strict pydantic records from
`src/aeat/adapters/inbound/declaracion/_schema.py`, uses shared PDF extracted
casilla models from `src/aeat/adapters/inbound/pdf/_shared.py`, and consumes
registry extraction target definitions from
`src/aeat/domain/calculations/registry/_schema.py`. No new duplicated local
data model was found in the audited implementation slice.

Tracked by `W06.P19.S118`.

### W06-008 Justificante Repository Import Cycle Remains

Importing the PDF error root originally pulled `aeat.domain.justificante.__init__`,
which eagerly imported `JustificanteRepository` and reached secure-storage
crypto/sql modules during error-class import. The package-level repository export
was made lazy during `W06.P19.S113` so declaration/PDF error imports stay
lightweight. A direct `JustificanteRepository` import still exposes a storage
crypto/sql cycle and remains unresolved.

Tracked by `W06.P19.S120`.
