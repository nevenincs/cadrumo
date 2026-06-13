---
tags:
  - "#exec"
  - "#manual-practico"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-manual-practico-research]]"
  - "[[2026-04-12-manual-practico-adr]]"
  - "[[2026-04-12-manual-practico-plan]]"
  - "[[2026-04-12-manual-practico-phase-1-summary-exec]]"
---

# manual-practico phase-1 code review

## Verdict

APPROVED_WITH_NOTES

## Files reviewed

- src/aeat/domain/manuals/__init__.py
- src/aeat/domain/manuals/_schema.py
- src/aeat/domain/manuals/_loader.py
- src/aeat/domain/manuals/_verify.py
- src/aeat/domain/manuals/_fetch.py
- src/aeat/domain/manuals/_ids.py
- src/aeat/domain/manuals/_stubs.py
- src/aeat/domain/manuals/errors.py
- src/aeat/domain/manuals/test_schema.py
- src/aeat/domain/manuals/test_loader.py
- src/aeat/domain/manuals/test_verify.py
- src/aeat/domain/manuals/test_fetch.py
- src/aeat/entrypoints/cli/manual.py
- src/aeat/entrypoints/cli/test_manual_cli.py
- src/aeat/entrypoints/cli/__init__.py
- src/aeat/config.py
- env/.env.example
- tests/test_config.py
- .gitignore
- corpus/manuals/iva/2025/manifest.json
- corpus/manuals/renta/2025/parte1/manifest.json
- corpus/manuals/renta/2025/parte2-deducciones-autonomicas/manifest.json
- .vault/research/2026-04-12-manual-practico-research.md
- .vault/adr/2026-04-12-manual-practico-adr.md
- .vault/plan/2026-04-12-manual-practico-plan.md
- .vault/exec/2026-04-12-manual-practico/2026-04-12-manual-practico-phase-1-summary.md

## Findings

### Critical

None.

### High

None.

### Medium

- PartSpec is a dataclass exposed on the public surface — src/aeat/domain/manuals/_fetch.py lines 41-48 plus src/aeat/domain/manuals/__init__.py lines 36-44 and 101. The review brief explicitly flagged this for confirmation. As implemented PartSpec is a frozen+slots dataclass and is re-exported via __all__. The pydantic v2 mandate says every boundary-crossing record / schema / manifest must be a pydantic v2 model. PartSpec is not persisted and not parsed from untrusted input — it is a static table of hard-coded canonical AEAT URLs. Rather than a hard violation this sits on the edge of the rule. Two clean follow-up options: (a) drop PartSpec from __all__ while keeping PART_SPECS and lookup_spec public, since the table is closed and callers never construct a PartSpec directly; or (b) promote PartSpec to a _StrictFrozen pydantic model matching the rest of the public surface. Not blocking because the data is inert and read-only, but flagging per mandate hygiene.

### Low

- type ignore[override] on ManualCatalogue.__iter__ — src/aeat/domain/manuals/_schema.py line 319. BaseModel default __iter__ yields (field_name, value) pairs; overriding to iterate Manual records is intentional but the ignore is the only such directive in the diff. Consider documenting the override with an explicit Iterator[Manual] return annotation that ty accepts without an ignore, or exposing a named helper iter_manuals(self) -> Iterator[Manual]. Non-blocking.
- _stubs.py TODO tags live in docstrings rather than inline comments — src/aeat/domain/manuals/_stubs.py lines 13-19 and 36-92. The brief asked that every stub is flagged TODO(#N) with a matching sibling issue number. The issue numbers are present and correct (#17, #21, #6) inside class docstrings and the module preamble, but the explicit TODO(#N) token only appears once (for MODELO_CASILLA_PATTERN at line 30). Adding a matching TODO(#17) / TODO(#21) line above each Protocol class would make grep-based stub sweeps trivially deterministic when the sibling issues land. Non-blocking.
- stub_extracted_at() is unused in v1 — src/aeat/domain/manuals/_stubs.py lines 95-102. The function is exported from the private stub module but no caller in aeat.domain.manuals or its tests invokes it. The docstring says it is kept for follow-up tests. Either delete it until it is actually needed, or drop the note so the next reviewer does not have to re-verify the absence of callers. Non-blocking.
- verify_manual_dir silently ignores its own review_required parameter — src/aeat/domain/manuals/_verify.py lines 141-144. The docstring is honest about this (reserved for the future soft-review gate) and the schema-level non-empty reviewer enforcement means v1 behaviour is still correct, but the parameter is a no-op. Consider either removing it from the signature or wiring it through to downgrade reviewer-missing loader errors to warnings when False. Keeping the CLI shape locked is defensible; just make sure the Layer-C follow-up picks this up so the flag does not become permanent decoration.

## Verified against the brief

- Pydantic v2 mandate — All schema records in _schema.py use _StrictFrozen (ConfigDict strict=True, frozen=True, extra=forbid). VerificationIssue and VerificationReport (_verify.py lines 28 and 38) and FetchResult (_fetch.py line 86) all declare the same strict+frozen+forbid config. ManualCatalogue uses _StrictLoose (strict + extra forbid, frozen=False) with a justified rationale: loading is incremental and individual Manual instances are already frozen. No bare dict[str, Any] on public signatures — the single Any return is on the private _load_json helper. The only dataclass is PartSpec (see Medium finding).
- Public API discipline — __init__.py re-exports the full documented surface and the __all__ list matches. No cross-package imports reach into aeat.domain.manuals._schema / _loader / _verify / _fetch / _ids / _stubs. src/aeat/entrypoints/cli/manual.py imports only from aeat.domain.manuals and aeat.domain.manuals.errors (allowed by brief). _stubs is not re-exported.
- Review gate honesty — _Reviewer in _schema.py line 78 enforces strip_whitespace=True and min_length=1, rejecting empty and whitespace-only reviewers. test_schema.py line 200 asserts the three-space reviewer rejects. The three committed corpus/manuals manifest.json files contain only FetchedManualPart provenance fields (manual_id, year, part, source_pdf_url, relative_pdf_path, sha256, content_length, fetched_at, synthetic) — zero reviewer fields. The only "gw" reviewer strings exist in in-memory unit-test fixtures exercising the schema non-empty enforcement; no persisted corpus JSON carries a fabricated reviewer.
- Protocol stubs inert — _stubs.py is imported only by _schema.py (for MODELO_CASILLA_PATTERN). Nothing in aeat.domain.manuals instantiates or calls any of the four Protocols at runtime. All four classes carry pragma no cover stub.
- Sibling territory respect — No diff under src/aeat/corpus/, src/aeat/domain/modelos/, src/aeat/adapters/persistence/storage/, pyproject.toml, root conftest.py, or tests/README.md. src/aeat/adapters/outbound/llm/ does not exist on this branch. tests/test_config.py change is exactly one line (adding encoding=utf-8 on the env read).
- Error hierarchy — ManualError(AeatError) plus ManualNotFoundError, ManualParseError, ManualReviewRequiredError, RuleExtractionError, ManifestError all inheriting ManualError. CLI catches ManualError / ManualNotFoundError and converts to typer.Exit code 1 cleanly.
- Logging discipline — Every module (_fetch.py, _loader.py, _verify.py) uses aeat.core.logging.get_logger(__name__). No logging.getLogger, no print() calls in the subpackage or CLI (only typer.echo / typer.secho / rich.console.Console).
- Test discipline — 45 tests collected; every new test carries pytest.mark.unit (schema 13, loader 8, verify 6, fetch 9, cli 5, plus 4 pre-existing test_config.py). No unittest.mock, MagicMock, monkeypatch patching third parties, fake, or shadow. Tests use real pydantic models, tmp_path, and CliRunner. Colocation honoured (src/aeat/domain/manuals/test_*.py, src/aeat/entrypoints/cli/test_manual_cli.py).
- CLI shape lock — test_manual_help_lists_all_subcommands asserts the full seven subcommands (fetch, structure, extract-rules, translate, verify, list, show). Three blocker commands raise RuleExtractionError with a message containing #21 (_PENDING_21_MESSAGE at cli/manual.py line 37; assertions at test_manual_cli.py line 34).
- Dev loop green — Re-verified locally on this branch: uv run ruff check on touched paths is clean; uv run ty check src/aeat is clean; uv run pytest src/aeat/manuals src/aeat/entrypoints/cli/test_manual_cli.py tests/test_config.py returned 45 passed in 1.01s. I did not re-run just hooks end-to-end.
- ADR deferral rationale — 2026-04-12-manual-practico-adr.md sections Scope partition (lines 47-66), Primary structuring surface (107-115), and Rationale (249-291) justify the Layer-C deferral, the PDF-vs-HTML non-decision, and the Protocol-stub approach. The ADR is explicit that chapter-tree extraction is deferred rather than prematurely committed to a strategy, matching the brief expectation.
- Vault artefact completeness — Research, ADR, plan, and phase-1 summary all exist, all carry the required directory tag and #manual-practico feature tag, all cross-link via related wiki-links, all use lowercase kebab-case 2026-04-12-manual-practico-* names. The summary already links forward to 2026-04-12-manual-practico-phase-1-review (this document).

## Follow-up items

- When #21 lands, replace _stubs.LLMClientProtocol / TranslatorProtocol / BulkTranslatorProtocol with the real aeat.adapters.outbound.llm surfaces and swap the three pending commands (structure, extract-rules, translate) onto real implementations. Land Layer C one chapter at a time with a real reviewed_by.
- When #17 (corpus fetcher) lands, re-wire _fetch.py to delegate through aeat.corpus.Fetcher and drop the direct httpx usage; FetcherProtocol is the forcing function.
- When #6 (modelo identifiers) lands, replace _stubs.MODELO_CASILLA_PATTERN with a direct aeat.domain.modelos.ModeloId cross-reference in _schema._CasillaRef.
- Decide PartSpec final home — either un-export it or promote to pydantic — per the Medium finding.
- Revisit verify_manual_dir(review_required=...) in the Layer C PR and either wire it through to real soft-gate behaviour or drop it from the signature.
- Consider removing stub_extracted_at() or finding its first caller.
