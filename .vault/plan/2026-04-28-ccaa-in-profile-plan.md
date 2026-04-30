---
tags:
  - '#plan'
  - '#ccaa-in-profile'
date: '2026-04-28'
related:
  - '[[2026-04-28-ccaa-in-profile-research]]'
  - '[[2026-04-28-ccaa-in-profile-adr]]'
---

# `ccaa-in-profile` implementation plan

Implement durable tax-residence CCAA capture for Kent, wire it into the Modelo 100 import verification path, and document the behavior as local profile state.

## Proposed Changes

Add a new `aeat.profile` package with strict frozen models, registered errors, and atomic JSON persistence. Add a new `aeat profile` CLI group with human and JSON output. Extend setup wizard answers and persistence so first-run setup captures tax residence. Update Modelo 100 filing imports to require and consume the profile CCAA. Add unit and integration coverage, then record execution and review results.

## Tasks

- Add profile model, storage, and error API.
- Register profile errors in the shared error registry.
- Add CLI commands and JSON schema registration.
- Register the CLI group on the root Typer app.
- Wire M100 borrador and declaration import paths to load profile CCAA and fail REFUSED when absent.
- Extend setup models, wizard prompt, and writer.
- Add tests for model/storage/errors/CLI and the Kent M100 profile workflow.
- Add tax-residence concept docs and update Kent capability coverage.
- Run lint, typecheck, tests, hooks, and code review.

## Parallelization

The profile package and CLI can be implemented independently from documentation. The M100 filing wiring depends on the profile errors and loader being present. Documentation review can run through the required researcher/author workflow once code surfaces are visible.

## Plan Review

Path A persistence is chosen: a JSON file under the OS config directory, independent from `#216`. Namespace collision is avoided by creating `aeat.profile`, not extending financial/browser/category profile surfaces. The foral-regime path is explicit and points to `#424`. M100 import consumes `load_tax_residence()` rather than accepting silent caller defaults. CLI strings are trilingual through `Translatable`, with JSON output registered. UTF-8 output is preserved by Typer and the shared JSON writer.

## Verification

Run focused unit tests for profile model, storage, errors, CLI, setup, and M100 integration. Then run the project's lint, typecheck, test, hook, and coverage commands where feasible. The mandatory code review must cover changed files and the eight #452 safety invariants.
