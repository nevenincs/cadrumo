---
tags:
  - "#plan"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: Filing Submission Engine — Plan
related:
  - "[[2026-04-12-submission-engine-research]]"
  - "[[2026-04-12-submission-engine-adr]]"
issue: wgergely/aeat#42
---

# implementation plan: filing submission engine

## scope

Deliver `aeat.adapters.outbound.aeat.export` per the ADR: strict pydantic v2 schema,
errors, preflight, Submitter ABC, Modelo130Submitter, SubmissionEngine,
Typer CLI sub-app, four new Settings fields, colocated unit tests,
one opt-in live dry-run test. No storage integration. No hard imports
from in-flight siblings.

## file map

```
src/aeat/adapters/outbound/aeat/export/
    __init__.py                        # public re-exports
    _errors.py                         # SubmissionError + subclasses
    _protocols.py                      # stubs for #6 #7 #8 #23 #38 #39 #44
    _models.py                         # SubmissionStatus, SubmissionAttempt,
                                       # SubmittedFiling, make_submission_id
    _preflight.py                      # Preflight validator
    _engine.py                         # SubmissionEngine
    _submitters/
        __init__.py                    # Submitter ABC + export
        _contract.py                   # BrowserSessionLike Protocol
        modelo130.py                   # Modelo130Submitter
        test_modelo130.py              # submitter unit tests
    test_models.py                     # strict+frozen validation
    test_errors.py                     # error hierarchy smoke
    test_preflight.py                  # four gates
    test_engine.py                     # dry-run default, double gate, JSON persist
    test_live_submission.py            # @pytest.mark.live dry-run only
src/aeat/entrypoints/cli/submission/
    __init__.py                        # typer sub-app wiring
    _helpers.py                        # build_engine, load_draft, stubs
    preflight.py                       # aeat submission preflight
    dry_run.py                         # aeat submission dry-run
    submit.py                          # aeat submission submit --i-understand-this-is-real
    show.py                            # aeat submission show
    list.py                            # aeat submission list
    test_cli.py                        # CliRunner unit tests
src/aeat/entrypoints/cli/__init__.py               # MODIFIED: add_typer(submission_module.app)
src/aeat/config.py                     # MODIFIED: four new Settings fields
env/.env.example                       # MODIFIED: four new env vars
```

## phases

### phase-1 — schema + errors + protocols

- `_errors.py` with `SubmissionError` / `SubmissionPreflightError` /
  `SubmissionFormFillError` / `SubmissionRejectionError`.
- `_protocols.py` stubs: `ModeloIdentifier`, `Portal`, `PortalCatalogue`,
  `LoadedCertificate`, `CertificateBackend`, `CasillaRecord`,
  `CasillaCatalogue`, `FilingFinding`, `FilingFindingSeverity`,
  `DraftStatus`, `FilingDraftLike`, `DraftLoader`,
  `DeadlineWindowChecker`, `Justificante`, `JustificanteParser`.
- `_models.py` with `SubmissionStatus`, `SubmissionAttempt`,
  `SubmittedFiling`, `make_submission_id`.
- `test_models.py`, `test_errors.py`.

### phase-2 — preflight + engine

- `_preflight.py` `Preflight.check` with the four ordered gates.
- `_engine.py` `SubmissionEngine.submit_draft` with dry-run default,
  double-gate, JSON persistence.
- `test_preflight.py`, `test_engine.py`.

### phase-3 — submitter ABC + modelo130

- `_submitters/__init__.py` `Submitter` ABC.
- `_submitters/_contract.py` `BrowserSessionLike` Protocol.
- `_submitters/modelo130.py` `Modelo130Submitter`.
- `_submitters/test_modelo130.py`.

### phase-4 — settings + CLI wiring

- Add four fields to `Settings`:
  `aeat_submissions_dir`,
  `aeat_submission_dry_run_default`,
  `aeat_submission_require_human_confirmation`,
  `aeat_submission_browser_trace_dir`.
- Mirror in `env/.env.example`.
- `src/aeat/entrypoints/cli/submission/` typer sub-app wired into root CLI.
- `test_cli.py`.

### phase-5 — live test + verification gates

- `test_live_submission.py` marked `@pytest.mark.live`, gated on
  `AEAT_LIVE_TESTS=1`, performs dry-run only.
- Run: `uv run pytest src/aeat/submission -q`,
  `uv run pytest src/aeat/entrypoints/cli/submission -q`,
  `uv run pytest tests/test_config.py -q`,
  `just lint`, `just typecheck`, `just test`, `just hooks`.

## test matrix

- Models: strict+frozen, extra-forbid, stable `make_submission_id` hash.
- Preflight: each of the four failure branches raises the right
  error; happy path silent.
- Submitter: dry-run aborts before final click; screenshots + trace
  start/stop recorded; casilla fills from `draft.values`.
- Engine: dry-run default does not call `submit`; live w/o override
  raises; live w/ override persists JSON.
- CLI: `submit` without flag exits 2; `submit --i-understand-this-is-real`
  invokes engine with live flags; `show` and `list` operate on
  persisted JSON.
- Config: `tests/test_config.py` enforces alignment.

## out of scope

- Actual live submission against AEAT (live test is dry-run only).
- Storage (#10) integration.
- Retry loops / auto-healing of rejections.
- Any modifications to `pyproject.toml [tool.pytest]`, banned-import
  lint rules, or other feature-15 territory.

## plan review

**Outcome:** APPROVED (self-review, no human in the loop per execution
contract).

**Rationale:** the plan aligns 1:1 with issue #42's authoritative
scope and uses the already-established Protocol-stub pattern from
`aeat.domain.deadlines`, so rebase against in-flight siblings is a mechanical
diff. Dry-run-by-default with the double-gate for live submission is
conservative enough that fat-fingering is impossible without explicit
intent at three layers (CLI flag, engine parameter, settings flag).
The colocated test layout and the BrowserSessionLike narrow Protocol
keep unit tests fast and mock-free, respecting the project's "no
mocks / no fakes / no stubs" mandate. No scope creep: the plan does
not touch `aeat.application.filing`, `aeat.domain.casillas`, `aeat.adapters.outbound.aeat.auth.certificate`,
`aeat.domain.portals`, or `aeat.domain.justificante`, all of which are sibling
territory.
