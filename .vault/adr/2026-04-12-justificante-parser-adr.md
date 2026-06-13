---
tags:
  - '#adr'
  - '#justificante-parser'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-justificante-parser-research]]'
  - '[[2026-04-12-justificante-parser-plan]]'
  - '[[2026-04-12-playwright-anti-bot-adr]]'
---

# `justificante-parser` adr: pdfplumber backend, strict pydantic v2 record, read-only live verify | (**status:** `accepted`)

## Problem Statement

Issue `#44` asks for a parser that turns AEAT-issued *justificantes de
presentación* (the PDF receipts produced after every filing) into a typed,
strict, deterministically-derivable record usable by the submission engine
(`#42`) and the status reader (`#43`). Without this, the project cannot
prove to a human auditor that a filing actually went through, cannot
correlate filings against the AEAT archive, and cannot store a durable
local record of what was submitted. The parser is load-bearing for every
downstream filing workflow.

## Decisions

### 1. Parser backend: pdfplumber (default), pymupdf reserved

We adopt **pdfplumber** as the default backend because it gives the highest
text-extraction fidelity on AEAT's structured PDF layouts and has an MIT
licence that imposes no downstream obligations on the project. We reserve
the ``JustificanteParserBackend.PYMUPDF`` enum member as a future
speed-optimised backend but do not implement it now — the PoC fidelity
target matters more than speed on one-page receipts, and pymupdf's AGPL
licence would otherwise force us to publish source for every downstream
consumer.

### 2. Pydantic v2 strict + frozen record

:class:`Justificante` is declared with
``ConfigDict(strict=True, frozen=True, extra="forbid")``. Rationale:

- ``strict=True`` prevents silent coercion of wire data into incorrect
  types (e.g. an integer into a ``datetime`` field).
- ``frozen=True`` makes the record immutable post-construction, which
  matches its role as an audit artefact: once the parser has extracted
  the fields, nothing downstream should be allowed to mutate them.
- ``extra="forbid"`` rejects unknown keys so a future parser regression
  that smuggles in an extra field fails loudly instead of silently.

Monetary fields (``total_a_ingresar``, ``total_a_devolver``) are
:class:`decimal.Decimal` to preserve the printed precision; never floats.

### 3. Regex-driven, tolerant extractor

Field extraction is regex-driven against the concatenated page text, not
a layout-aware parser. Rationale: AEAT's justificante layout has been
stable since the mid-2010s; the field labels are consistent; and pdfplumber
flattens the layout into text-line order anyway. A regex extractor is
easier to reason about, easier to test, and trivially deterministic.

We deliberately accept *both* accented and unaccented label variants
("Código Seguro de Verificación" and "Codigo Seguro de Verificacion")
because historical PDFs sometimes embed fonts whose ``ToUnicode`` cmaps
lose accents on text extraction. The extractor normalises via
:func:`unicodedata.normalize` before regex matching as a fallback.

### 4. Error hierarchy

All justificante errors inherit from :class:`aeat.core.errors.AeatError`:

- ``JustificanteError`` — root.
- ``JustificanteParseError`` — any parse failure.
- ``JustificanteCsvNotFoundError`` — parse failed specifically because
  no CSV could be located. Callers can catch this subclass to distinguish
  "wrong PDF passed in" from "parser bug".
- ``JustificanteVerificationError`` — live CSV verification round-trip
  failed (browser / network / probe).

### 5. ``verify_csv`` is opt-in and read-only

The live verification helper is a coroutine that accepts a CSV string
(never a typed ``Expediente``), constructs or reuses a
:class:`BrowserSession`, navigates to AEAT's public
"verificación de integridad" page, submits the CSV, and reads back the
result. **It never mutates AEAT-side state** — the public verify page is
read-only by design, and we rely on that guarantee in the ADR.

Because the live layer has a known flakiness in ``playwright_stealth``
(`#41`), the live test ``pytest.skip``s on
:class:`JustificanteVerificationError` instead of failing, so the unit
suite remains the authoritative proof of parser correctness.

### 6. Fixture corpus: synthetic, committed, reference generator

Real justificantes contain real taxpayer identifiers and cannot be
committed to a public repo. We therefore generate **synthetic** redacted
PDFs with reportlab, commit them to ``tests/fixtures/justificantes/``, and
ship the generator script (``_generate.py``) alongside the fixtures for
reproducibility. Every identifier in the fixtures is fictitious:
``NIF=00000000T``, ``CSV=ABCD1234EFGH5678`` (and analogous constants for
303 and 100). Unit tests load the committed PDFs; reportlab is therefore
only needed as a **dev dependency**, not a runtime dependency.

### 7. Public API surface

Callers outside the subpackage must import **only** from
:mod:`aeat.domain.justificante`. The private modules (``_schema``, ``_extract``,
``_parser``, ``_parsers.*``, ``_verify``, ``_errors``) are implementation
details and may be refactored without notice. The public exports are:

- :class:`Justificante` (strict frozen BaseModel)
- :class:`JustificanteParserBackend` (StrEnum)
- :class:`JustificanteError` and its three subclasses
- :func:`parse_justificante` (synchronous)
- :func:`verify_csv` (async coroutine)

## Consequences

- The submission engine (`#42`) can replace its Protocol stub for
  ``Justificante`` with the real type on rebase.
- The status reader (`#43`) can pass a CSV string directly to
  ``verify_csv`` without depending on the justificante subpackage's
  persistence layer.
- The parser is trivially re-runnable against any historical corpus we
  later acquire; because it is deterministic and strict, regressions are
  loud.
- Adding a new modelo to the supported corpus is a matter of adding a
  fixture + a test; no parser code changes are expected unless AEAT
  changes the label conventions.
