---
tags:
  - '#plan'
  - '#manual-practico'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-manual-practico-research]]'
  - '[[2026-04-12-manual-practico-adr]]'
---

# `manual-practico` `phase-1` plan

Implementation plan for `#25` phase 1, delivering the schema, loader,
query API, CLI skeleton, settings, and raw-PDF manifests. Backed by the
companion research and ADR. Layer C (structured content extraction,
trilingual translation, per-chapter rule files) is explicitly deferred
to follow-up issues that run after `#21` merges and include a real
human reviewer.

## Proposed Changes

New subpackage `src/aeat/domain/manuals/` with strict pydantic v2 schema,
deterministic rule IDs, file loader + query API, verification command,
and an `httpx` fetcher. New CLI subgroup `src/aeat/entrypoints/cli/manual.py` wired
into the existing `aeat` typer app. Additive settings in
`src/aeat/config.py` and `env/.env.example`. New `corpus/manuals/`
directory populated with committed `manifest.json` files for Renta 2025
Parte 1, Renta 2025 Parte 2, and IVA 2025; the raw `source.pdf` blobs
are git-ignored and materialised on demand by the fetcher.

No modifications to sibling branch territory: `aeat.corpus`, `aeat.adapters.outbound.llm`,
`aeat.domain.modelos`, `aeat.adapters.persistence.storage`, `pyproject.toml [tool.pytest]`, root
`conftest.py`, `tests/README`.

Every persisted record is a strict pydantic v2 model. Every trilingual
field uses `aeat.core.i18n.Translatable`. Every error inherits from
`aeat.core.errors.AeatError` via `ManualError`. Every module uses
`aeat.core.logging.get_logger(__name__)`.

## Tasks

- `phase-1-schema`
  1. Create `src/aeat/domain/manuals/__init__.py` with module docstring and
     `__all__` scaffolding (empty list initially, populated as modules
     land).
  1. Add `src/aeat/domain/manuals/_schema.py` with `ManualId`, `ManualPart`,
     `RuleKind` (`enum.StrEnum`), and pydantic v2 strict models
     `LLMProvenance`, `SectionSource`, `RuleSource`, `Paragraph`,
     `Rule`, `SectionRef`, `Section`, `Chapter`, `Manual`. Every
     reviewer-gated record exposes `reviewed_by: str` and
     `reviewed_at: date`. Trilingual fields use `Translatable`.
  1. Add `src/aeat/domain/manuals/_ids.py` with `generate_rule_id(...) -> str`
     producing `{manual_id}-{year}-{part}-{chapter_id}-{section_id}-
     rule{ordinal:04d}`; collapses `-single-` for `SINGLE` parts.

- `phase-1-errors-and-stubs`
  1. Add `src/aeat/domain/manuals/errors.py` with `ManualError(AeatError)`,
     `ManualParseError`, `ManualNotFoundError`, `RuleExtractionError`,
     `ManualReviewRequiredError`.
  1. Add `src/aeat/domain/manuals/_stubs.py` with `FetcherProtocol`,
     `LLMClientProtocol`, `TranslatorProtocol`, `BulkTranslatorProtocol`
     each marked `TODO(#17|#21)` in the docstring, plus the regex
     sentinel `MODELO_ID_PATTERN` marked `TODO(#6)`.

- `phase-1-loader-and-verify`
  1. Add `src/aeat/domain/manuals/_loader.py` with `load_manual(...)`,
     `ManualCatalogue`, `find_rules(...)`. Strict validation; raises
     `ManualNotFoundError` / `ManualParseError`.
  1. Add `src/aeat/domain/manuals/_verify.py` with `VerificationReport` model
     and `verify_manual_dir(path, *, review_required=True)`. Walks the
     directory, validates schema, checks cross-references, checks
     trilingual completeness against the authoritative-language
     contract, checks reviewer fields. Returns a report; the CLI turns
     non-empty error lists into a non-zero exit.

- `phase-1-fetch`
  1. Add `src/aeat/domain/manuals/_fetch.py` with `PartSpec`, `PART_SPECS`,
     `FetchedManualPart` pydantic model, and `fetch_manual_part(...)`.
     Streams the PDF via `httpx`, computes sha256 on the fly, writes
     `manifest.json`, returns the typed result.

- `phase-1-public-surface`
  1. Update `src/aeat/domain/manuals/__init__.py` to re-export the public API.
     Add Google-style docstrings to every public symbol.

- `phase-1-cli`
  1. Add `src/aeat/entrypoints/cli/manual.py` with `app = typer.Typer(...)` and
     seven subcommands: `fetch`, `structure`, `extract-rules`,
     `translate`, `verify`, `list`, `show`. `fetch`/`verify`/`list`/
     `show` call into `aeat.domain.manuals`. `structure`/`extract-rules`/
     `translate` raise `RuleExtractionError`.
  1. Register the subgroup in `src/aeat/entrypoints/cli/__init__.py` via
     `app.add_typer(manual_module.app, name="manual", ...)`.

- `phase-1-settings`
  1. Add `aeat_manuals_root: Path = Field(default=PROJECT_ROOT /
     "corpus" / "manuals", ...)` and `aeat_manuals_review_required:
     bool = Field(default=True, ...)` to `aeat.core.config.Settings`.
  1. Add matching entries to `env/.env.example`. Verify
     `tests/test_config.py` still passes.

- `phase-1-tests`
  1. Add `src/aeat/domain/manuals/test_schema.py` covering model validation,
     required fields, round-trip, trilingual completeness, deterministic
     rule ID.
  1. Add `src/aeat/domain/manuals/test_loader.py` covering the loader happy
     path, malformed-record rejection, cross-reference validator, and
     `find_rules` filters.
  1. Add `src/aeat/domain/manuals/test_verify.py` covering the verify report
     and the rejection of unreviewed records.
  1. Add `src/aeat/domain/manuals/test_fetch.py` covering `FetchedManualPart`
     validation and `PART_SPECS` table integrity. No live HTTP in unit
     tests (the live fetch is exercised in step `phase-1-materialise`).
  1. Add `src/aeat/entrypoints/cli/test_manual_cli.py` smoke-testing the CLI via
     `typer.testing.CliRunner` for the planned-blocker commands and
     the happy-path commands that do not need the network.

- `phase-1-materialise`
  1. Run `aeat manual fetch --manual renta --year 2025 --part parte1`,
     `--part parte2-deducciones-autonomicas`, and `aeat manual fetch
     --manual iva --year 2025` once in the worktree. Commit the
     resulting `manifest.json` files only. Add
     `corpus/manuals/**/source.pdf` to `.gitignore`.

- `phase-1-hygiene`
  1. Run `just fmt && just lint && just typecheck && just test && just
     hooks` until all green. Fix at root, never skip.
  1. Record exec step results under `.vault/exec/2026-04-12-manual-
     practico/`.

- `phase-1-review`
  1. Run the `vaultspec-code-review` skill over every changed file.
     Record the report at `.vault/exec/2026-04-12-manual-practico/
     2026-04-12-manual-practico-phase-1-review.md`. Fix any issues
     before opening the PR.

- `phase-1-pr`
  1. Commit focused changes referencing `#25`. Open the PR with a body
     that links the vault research, ADR, plan, exec, and review
     artefacts and explicitly calls out the Layer C deferral.

## Parallelization

Schema, errors, stubs, IDs, loader, verify, and fetch are straight-line
dependencies: schema → errors/stubs/IDs → loader → verify → public
surface → CLI → tests → materialise → hygiene → review → PR. There is
no meaningful parallelism inside this phase; the early foundation
blocks everything downstream. Settings and `.env.example` alignment
can land in parallel with any of the implementation tasks but are
grouped separately so `tests/test_config.py` does not flap.

## Verification

Mission success criteria, from the ADR:

- `src/aeat/domain/manuals/` subpackage exists with the full schema, loader,
  query API, deterministic rule ID generator, verification report,
  fetch command, error hierarchy, typed `__init__`, and colocated
  unit tests.
- `aeat manual` CLI subgroup exists with all seven subcommands
  registered; `fetch`/`verify`/`list`/`show` work end-to-end;
  `structure`/`extract-rules`/`translate` raise `RuleExtractionError`
  referencing `#21`.
- `Settings` carries `aeat_manuals_root` and
  `aeat_manuals_review_required`, `env/.env.example` matches, and
  `tests/test_config.py` passes.
- `corpus/manuals/renta/2025/parte1/manifest.json`,
  `corpus/manuals/renta/2025/parte2-deducciones-autonomicas/manifest.
  json`, and `corpus/manuals/iva/2025/manifest.json` are committed with
  real sha256 values matching the verified AEAT URLs. Raw PDFs are
  git-ignored.
- `just lint && just typecheck && just test && just hooks` all green
  on Windows.
- `.vault/research/2026-04-12-manual-practico-research.md`,
  `.vault/adr/2026-04-12-manual-practico-adr.md`, this plan, the exec
  step records, and the mandatory code-review report all exist and
  cross-link via `related:`.

Tests can be cheated, so verification goes beyond `pytest` green:

- The verify CLI is exercised against a hand-authored temp-dir fixture
  containing a known-bad record (missing `reviewed_by`) and a known-
  good record; both branches are asserted.
- The fetch CLI is exercised once against the real AEAT URLs during
  `phase-1-materialise`; the resulting manifest sha256s are the
  committed truth.
- The Layer C deferral is explicit in the ADR, in this plan, in the
  PR body, and in the code itself (the three planned-blocker
  commands raise with a message that names `#21`). Any attempt to
  "fill in" Layer C on this branch is visible as a diff against the
  planned-blocker commands.

## Plan review

Self-review performed on `2026-04-12` before execution begins, per the
pipeline mandate to record an explicit plan-review outcome.

- **Scope coherence**: the three layers (schema, raw corpus, structured
  content) are cleanly separable; delivering A and B without C does
  not produce a broken intermediate state. `aeat manual list` over an
  empty `structure/` directory returns an empty iterator, not an
  error. `aeat manual verify` over an empty `structure/` directory
  returns an empty report. ✓
- **Review-gate honesty**: no task in this plan writes a `reviewed_by`
  value anywhere. The schema declares the fields as required, but the
  v1 PR does not construct any record that has them, because it does
  not construct any `Manual`/`Section`/`Rule` content. The only
  committed records are `manifest.json` files which are schema-typed
  via `FetchedManualPart` and do not carry reviewer fields (they
  describe provenance of a raw binary, not reviewed content). ✓
- **Sibling branch respect**: no task touches `src/aeat/corpus/`,
  `src/aeat/adapters/outbound/llm/` (does not exist), `src/aeat/domain/modelos/`,
  `src/aeat/adapters/persistence/storage/`, `pyproject.toml [tool.pytest]`, root
  `conftest.py`, or `tests/README`. The stub Protocols live under
  `src/aeat/domain/manuals/_stubs.py`, private to this subpackage. ✓
- **Dependency budget**: zero new runtime dependencies. `httpx`,
  `pydantic`, `pydantic-settings`, and `typer` are already present. No
  PDF parser is added (deferred to the follow-up that parses). ✓
- **Test discipline**: all new tests are `@pytest.mark.unit` with no
  mocks, patches, fakes, or stubs. The single live test envisioned by
  `#25` (one LLM round-trip per phase) is not implemented here because
  the LLM client is not available; the test file will be added in the
  follow-up that lands the LLM-dependent work. This is called out in
  the ADR. ✓
- **CLI surface lock**: all seven subcommands are defined in v1 so
  downstream users of the CLI can depend on the shape. Three of them
  fail fast with a typed error until `#21` lands. The exit code from
  the planned-blocker commands is the standard typer non-zero. ✓
- **Materialisation workflow**: `aeat manual fetch` must be run once
  locally to produce committable manifests. That step is recorded as
  a dedicated task (`phase-1-materialise`) so the exec record shows
  the command invocation and the resulting sha256 values. ✓
- **Review record and code review**: the mandatory
  `vaultspec-code-review` step (`phase-1-review`) runs after all
  implementation and hygiene tasks pass. Its report lands under
  `.vault/exec/2026-04-12-manual-practico/` and must be clean before
  the PR opens. ✓

Outcome: plan approved. Proceeding to execution.
