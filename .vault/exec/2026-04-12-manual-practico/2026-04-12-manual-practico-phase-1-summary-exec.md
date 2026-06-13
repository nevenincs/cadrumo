---
tags:
  - '#exec'
  - '#manual-practico'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-manual-practico-plan]]'
  - '[[2026-04-12-manual-practico-adr]]'
  - '[[2026-04-12-manual-practico-research]]'
  - '[[2026-04-12-manual-practico-phase-1-review-exec]]'
---

# `manual-practico` `phase-1` summary

Execution record for phase 1 of issue `#25`. Scope is the Layer A
(schema + loader + CLI skeleton + tests) and Layer B (raw PDFs +
manifests) delivery agreed with the operator on `2026-04-12`. Layer C
(structured content extraction, trilingual translation, per-chapter
rule files) is deferred to follow-up issues that run after `#21`
merges and include a live human reviewer.

## Tasks executed

- Landed `src/aeat/domain/manuals/` subpackage:
  - `_schema.py` with strict pydantic v2 models for `ManualId`,
    `ManualPart`, `RuleKind`, `LLMProvenance`, `SectionSource`,
    `RuleSource`, `Paragraph`, `Rule`, `SectionRef`, `Section`,
    `Chapter`, `Manual`, `FetchedManualPart`, `ManualCatalogue`. All
    boundary-crossing records are `ConfigDict(strict=True,
    frozen=True, extra="forbid")`. Spanish-authoritative translatable
    fields validated at construction time.
  - `_ids.py` with the deterministic rule-id generator. Collapses the
    `-single-` segment for IVA.
  - `_stubs.py` with `FetcherProtocol`, `LLMClientProtocol`,
    `TranslatorProtocol`, `BulkTranslatorProtocol`, and the
    `MODELO_CASILLA_PATTERN` regex; each marked `TODO(#17|#21|#6)`.
  - `_loader.py` with `load_manual`, `load_section`, `load_catalogue`,
    `resolve_part_root`, `iter_sections`, `find_rules`, and a
    `TypeAdapter`-based chapter reader that uses pydantic's JSON
    mode to accept list→tuple coercion under strict schema.
  - `_verify.py` with `VerificationIssue`, `VerificationReport`, and
    `verify_manual_dir`. The schema itself is the absolute review
    gate; verify surfaces schema failures as `load-failed` errors.
  - `_fetch.py` with the `PartSpec` table, `FetchResult`,
    `fetch_manual_part`, `load_manifest`, `write_manifest`, and
    `verify_fetched_pdf`. Uses `httpx` directly; flagged for
    migration to the `#17` corpus fetcher on rebase.
  - `errors.py` with the full `ManualError` hierarchy.
  - `__init__.py` re-exports the public surface (36 symbols in
    `__all__`).
- Extended `aeat.core.config.Settings` with `aeat_manuals_root` (default
  `<repo>/corpus/manuals`) and `aeat_manuals_review_required`
  (default `True`). Matching entries added to `env/.env.example`.
  `tests/test_config.py` stays green. Also added explicit
  `encoding="utf-8"` to `tests/test_config.py::_parse_env_example_vars`
  to unblock the Windows dev loop against the existing non-ASCII
  box-drawing characters in `.env.example` (minimal targeted fix).
- Added `src/aeat/entrypoints/cli/manual.py` with seven subcommands. `fetch`,
  `verify`, `list`, `show` are fully functional. `structure`,
  `extract-rules`, `translate` raise `RuleExtractionError` pointing
  at `#21`. Registered as `app.add_typer(manual_module.app, name=
  "manual", ...)` in `src/aeat/entrypoints/cli/__init__.py`.
- Materialised the three raw manual PDFs via the real `aeat manual
  fetch` CLI against AEAT's sede electrónica; wrote committed
  manifests and git-ignored the binaries.
- Added colocated unit tests under `src/aeat/domain/manuals/`
  (`test_schema.py`, `test_loader.py`, `test_verify.py`,
  `test_fetch.py`) and a CLI smoke test at
  `src/aeat/entrypoints/cli/test_manual_cli.py`. All `@pytest.mark.unit`, no
  mocks, no patches, no fakes, no stubs (beyond the typed
  `Protocol`s used for type-annotation only).

## Fetched artefacts

All three downloads succeeded against the URLs verified in the
research artefact. Committed manifests (one per part root):

- `corpus/manuals/renta/2025/parte1/manifest.json`
  - `sha256=60e6b2d71c97d93a9e0943e6ff8c886f4dd6d3741a797cb8001dcbcadfb33528`
  - `content_length=7,543,283`
- `corpus/manuals/renta/2025/parte2-deducciones-autonomicas/manifest.json`
  - `sha256=0df4a0b9018e8f18e4b5fa6e5120d70b456a6f21da3561bdae8cca9688e7ecd4`
  - `content_length=3,798,461`
- `corpus/manuals/iva/2025/manifest.json`
  - `sha256=e4f800972e06466ac39f893ed6a4118bf9594b0bad52301bc763eacb92db18a3`
  - `content_length=6,296,576`

Raw `source.pdf` blobs are git-ignored via
`corpus/manuals/**/source.pdf`. A fresh clone can re-materialise and
sha256-verify them with `aeat manual fetch`.

## Hygiene results

Final dev loop, run on Windows on `2026-04-12`:

- `uv run ruff check .` — clean.
- `uv run ty check src tests` — clean.
- `uv run pytest` — 154 passed, 1 skipped, 7 deselected (live tests
  opt-in). All new tests in `src/aeat/domain/manuals/` and
  `src/aeat/entrypoints/cli/test_manual_cli.py` green.
- `uv run prek run --all-files` — every hook passes
  (`trim trailing whitespace`, `fix end of files`, `check yaml`,
  `check toml`, `check for added large files`, `check for merge
  conflicts`, `detect private key`, `ruff (legacy alias)`,
  `ruff format`, `ty type check`).

## Deferrals

- Layer C (chapter trees, rule files, trilingual translations) is not
  delivered. It requires ``#21`` for the LLM client and a live human
  reviewer. Follow-up issues land one chapter at a time with a real
  `reviewed_by` signature.
- `#17` corpus fetcher integration is deferred; the `FetcherProtocol`
  stub is the forcing function for the follow-up that re-wires
  `_fetch.py` through the real fetcher.
- `#6` modelo cross-reference validation is deferred; string-level
  regex validation is the v1 substitute.
- The `@pytest.mark.live` opt-in test anticipated by the original
  `#25` scope is not implemented on this branch because it would
  need the real `#21` LLM client. Scheduled for the follow-up that
  adds Layer C.

## Verification beyond the test suite

- `aeat manual --help` lists all seven subcommands; the planned-
  blocker commands raise `RuleExtractionError` in the smoke tests
  and the error message names `#21`.
- `aeat manual fetch` was exercised three times against the real
  AEAT URLs; the manifests committed on this branch were produced
  by that exact invocation, not by a handcrafted payload.
- `aeat manual verify --manual renta --year 2025 --part parte1`
  succeeds against the committed state (reports a `missing-
  manifest` warning if the manifest is removed; no errors).
- `aeat manual list --manual renta --year 2025 --part parte1`
  exits cleanly with an empty result because `structure/` is
  intentionally empty for v1.
