---
tags:
  - "#research"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: Filing Submission Engine — Research
related:
  - "[[2026-04-12-deadline-engine-research]]"
  - "[[2026-04-12-playwright-anti-bot-research]]"
  - "[[2026-04-12-trilingual-i18n-research]]"
issue: wgergely/aeat#42
---

# research: filing submission engine

## problem statement

Given a completed `FilingDraft` (from #39), drive a real AEAT portal
session to dry-run or submit the filing, collect the justificante, and
persist a typed `SubmittedFiling` record. This is the final leg of the
"autónomo tax filing" north star: research → compute deadlines →
draft → **submit** → archive.

## in-flight dependencies

The submission engine must compile and ship before these siblings merge:

- **#6 modelo enum** — `aeat.domain.modelos.ModeloIdentifier`.
- **#7 portal catalogue** — `aeat.domain.portals.PortalCatalogue`, `Portal`.
- **#8 certificate auth** — `aeat.adapters.outbound.aeat.auth.certificate.CertificateBackend`.
- **#23 casilla DB** — `aeat.domain.casillas.CasillaCatalogue`, `CasillaRecord`.
- **#38 deadline engine** — already on main as `aeat.domain.deadlines`, but
  we still rebase-decouple via a narrow `DeadlineWindowChecker` Protocol.
- **#39 filing draft engine** — `aeat.application.filing.FilingDraft`, `DraftLoader`,
  `FilingFinding`.
- **#44 justificante parser** — `aeat.domain.justificante.JustificanteParser`,
  `Justificante`.

Every one of these is stubbed as a `Protocol` inside
`src/aeat/adapters/outbound/aeat/export/_protocols.py`, mirroring the pattern from
`aeat.domain.deadlines._protocols` (see `[[2026-04-12-deadline-engine-research]]`).
Rebase-swap is mechanical: delete stub, import from the real package.

## architecture overview

- **Schema (`_models.py`)**: `SubmissionStatus` StrEnum,
  `SubmissionAttempt`, `SubmittedFiling`. Strict+frozen pydantic v2.
- **Errors (`_errors.py`)**: `SubmissionError` root, with
  `SubmissionPreflightError`, `SubmissionFormFillError`,
  `SubmissionRejectionError` subclasses; all inherit `AeatError`.
- **Preflight (`_preflight.py`)**: pure validator, four gates in order
  (draft-ready, no-ERROR-findings, window-open, cert-loads).
- **Submitter ABC (`_submitters/__init__.py`)**: `Submitter` ABC with
  `dry_run` / `submit` coroutines. `Modelo130Submitter` is the first
  concrete subclass.
- **Engine (`_engine.py`)**: composition root. `SubmissionEngine.submit_draft`
  is dry-run by default; live submission requires
  `override_confirmation=True` **and** the corresponding settings flag.
  Persists `SubmittedFiling` JSON under `aeat_submissions_dir`.

### browser composition pattern

The submitter consumes a narrow `BrowserSessionLike` Protocol defined
in `_submitters/_contract.py`. It lists exactly the methods the
submitter needs (`navigate`, `fill`, `screenshot`, `trace_start`,
`trace_stop`, `click`, `snapshot_form_state`). The production
`aeat.adapters.outbound.aeat.browser.BrowserSession` structurally conforms; unit tests pass a
deterministic Python class that records calls into a list. This avoids
Playwright startup in unit tests **and** respects the project "no
mocks" rule — the test double is a real Protocol implementation, not a
mock.

### dry-run-by-default rationale

`dry_run=True` is the default on every engine call and every CLI
subcommand except `submit`. `submit` requires an explicit
`--i-understand-this-is-real` flag to transition to live mode. The
engine double-gates: `override_confirmation=True` parameter AND
`settings.aeat_submission_require_human_confirmation=True` setting (the
latter is on by default). This is belt-and-braces because the live
submission is irreversible: once AEAT receives the form, it is filed.

### browser-trace + screenshot strategy

Every submission (dry-run or live) records:

- a Playwright trace to `aeat_submission_browser_trace_dir / submission_id.zip`
- a sequence of PNG screenshots to the same directory
- the pre-submit form-state snapshot as `form_state.json`

These are the audit trail the user reviews before flipping to live
submission.

### rejection runbook

If the submitter raises `SubmissionRejectionError`, the engine writes
an attempt with `status=REJECTED` and keeps the trace. The CLI prints
the translated error message and points at the trace file. No retry
loop in v1 — retries are a human decision.

## decisions deferred to ADR

- How to scope the `Submitter` ABC surface (minimum viable vs broad).
- Default values for the two `_require_human_confirmation` gates.
- Where `SubmittedFiling` JSON lives (flat dir vs per-modelo tree).
- Whether the CLI `submit` subcommand also archives to storage (#10).

See `[[2026-04-12-submission-engine-adr]]`.
