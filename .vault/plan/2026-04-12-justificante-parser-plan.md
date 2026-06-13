---
tags:
  - '#plan'
  - '#justificante-parser'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-justificante-parser-research]]'
  - '[[2026-04-12-justificante-parser-adr]]'
---

# `justificante-parser` plan

Implementation plan for `#44`, delivering the strict pydantic v2
:class:`Justificante` record, the pdfplumber-backed parser, the opt-in
live CSV verifier, the CLI, the settings, the fixture corpus, and the
unit + live test suites.

## Proposed Changes

New subpackage ``src/aeat/domain/justificante/`` with:

- ``__init__.py`` exposing the public API (``Justificante``,
  ``JustificanteParserBackend``, the error hierarchy,
  ``parse_justificante``, ``verify_csv``).
- ``_schema.py`` — strict frozen pydantic v2 ``Justificante`` + enum.
- ``_errors.py`` — four error classes under ``aeat.core.errors.AeatError``.
- ``_extract.py`` — regex-driven field extractor.
- ``_parser.py`` — public ``parse_justificante`` entry point.
- ``_verify.py`` — async ``verify_csv`` against the Sede electrónica.
- ``_parsers/__init__.py`` + ``_parsers/_pdfplumber_backend.py`` — private
  backend registry and the pdfplumber implementation.
- ``test_parser.py`` — 12 colocated unit tests (@pytest.mark.unit).
- ``test_verify_live.py`` — 1 opt-in live test (@pytest.mark.live).

New CLI subgroup ``src/aeat/entrypoints/cli/justificante/__init__.py`` with ``parse``
and ``verify`` subcommands, wired into ``aeat.entrypoints.cli.app``.

Additive settings in ``src/aeat/config.py``:

- ``aeat_justificantes_dir`` (Path, default ``var/justificantes``)
- ``aeat_justificante_parser_backend``
  (:class:`JustificanteParserBackend`, default ``PDFPLUMBER``)

Matched entries in ``env/.env.example``.

New fixture corpus under ``tests/fixtures/justificantes/``:

- ``_generate.py`` — reportlab-based deterministic generator.
- ``modelo_130_2026Q1.pdf``
- ``modelo_303_2026Q1.pdf``
- ``modelo_100_2025A.pdf``

Dependency changes in ``pyproject.toml``:

- runtime: ``pdfplumber>=0.11.9``
- dev: ``reportlab>=4.4.10`` (fixture generation only)

Vault artefacts:

- ``.vault/research/2026-04-12-justificante-parser-research.md``
- ``.vault/adr/2026-04-12-justificante-parser-adr.md``
- ``.vault/plan/2026-04-12-justificante-parser-plan.md`` (this file)
- ``.vault/exec/2026-04-12-justificante-parser/…`` — execution log.

No modifications to sibling branch territory: ``src/aeat/adapters/outbound/aeat/export/``
(`#42`), ``src/aeat/status/`` (`#43`), ``src/aeat/domain/modelos/`` (`#6`),
``pyproject.toml [tool.pytest]`` (`#15`), or root ``conftest.py``.

## Plan review

**Reviewer:** autonomous pipeline (self-review at plan-approval gate).
**Outcome:** APPROVED.

Checks performed:

- Scope in the plan ≡ scope declared in `#44` — every issue bullet maps
  to a concrete task below.
- No file lives outside ``src/aeat/``, matching the base-module-structure
  mandate (`#12`).
- All boundary-crossing types are strict pydantic v2 (`Justificante`);
  all closed enumerations are ``StrEnum`` (`JustificanteParserBackend`);
  no bare ``dict[str, Any]`` in the public surface.
- Unit tests are colocated (``src/aeat/domain/justificante/test_parser.py``)
  per the Rust-style convention.
- Every error class inherits from ``aeat.core.errors.AeatError``.
- ``verify_csv`` takes a **string** CSV (not a typed ``Expediente``) so
  `#43` does not need to import from ``aeat.domain.justificante``.
- The live test ``pytest.skip``s on ``JustificanteVerificationError``
  so the known `#41` ``playwright_stealth`` bug cannot red-line the
  suite.
- Public API imports only from ``aeat.domain.justificante`` — all
  private ``_*`` modules are hidden.
- No hard imports from ``aeat.adapters.outbound.aeat.export``, ``aeat.status``,
  ``aeat.domain.modelos``, ``aeat.adapters.outbound.aeat.auth.certificate``.

## Tasks

1. Add ``pdfplumber`` runtime dep + ``reportlab`` dev dep, ``uv sync``.
2. Create the synthetic fixture generator under
   ``tests/fixtures/justificantes/_generate.py`` and run it once to
   commit three fixture PDFs (Modelo 130, 303, 100).
3. Create ``src/aeat/domain/justificante/`` subpackage with the schema, errors,
   extractor, public parse entry point, pdfplumber backend, and the
   async ``verify_csv`` helper.
4. Create the ``src/aeat/entrypoints/cli/justificante/`` sub-app and wire it into
   ``aeat.entrypoints.cli.app``.
5. Add the two settings fields to ``aeat.core.config.Settings`` and to
   ``env/.env.example`` so ``tests/test_config.py`` stays green.
6. Write ``test_parser.py`` (12 unit tests) covering: per-modelo parse,
   sha-256 capture, determinism, both backends (one raises), missing
   file, missing CSV, frozen model, extra-field rejection, sha-256
   pattern validation.
7. Write ``test_verify_live.py`` (1 opt-in live test).
8. Run ``just lint && just typecheck && just test && just hooks`` until
   green.
9. Land vault exec record + commit focused changes referencing `#44`.
10. Run final code review (vaultspec-code-review skill) and open the PR.
