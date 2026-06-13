---
name: docs-rewrite-research
description: Survey of README / getting-started / RELEASING conventions and the on-main aeat surface that the rewrite must reflect
type: research
tags:
  - "#research"
  - "#docs-rewrite"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-docs-rewrite-adr]]"
  - "[[2026-04-12-docs-rewrite-plan]]"
issue: wgergely/aeat#67
---

# research: docs-rewrite

## context

`README.md` today is the GSuite-bootstrap walkthrough from issue #4. The
project has since landed every layer of the AEAT loop on `main`
(cert auth, browser, status reader, submission, filing draft, deadlines,
sync, manuals, normatives, LLM, storage, i18n) and the workflow engine
(#59) + setup wizard (#61) are landing. A first-time visitor cannot
answer "what is this?" or "how do I run it?" from the current README.

Issue [wgergely/aeat#67](https://github.com/wgergely/aeat/issues/67)
specifies the rewrite scope.

## constraints discovered

- **No `.github/workflows/release-please.yml`** — `tests/test_release_config.py`
  fails if it appears. GitHub Actions is permanently disabled on this
  account; local gates are authoritative. README **must not** carry a
  CI badge.
- **`AEAT_LIVE_TESTS_ENABLED`** is the canonical env var for opting
  into live tests (NOT `AEAT_LIVE_TESTS`).
- **Sibling branches in flight** own these surfaces and must not be
  edited from this branch:
  - `feature-15-pytest-only-testing` — owns `pyproject.toml [tool.pytest]`,
    `conftest.py`, `tests/README/`. The new project-meta test goes at
    `tests/test_docs.py` (repo-root level).
  - `feature-59-workflow-engine` — owns `src/aeat/application/workflow/`. README
    references `aeat workflow next` annotated as "(merging in #59)".
  - `feature-61-setup-wizard` — owns `src/aeat/application/setup/`. README
    references `aeat setup` annotated as "(merging in #61)".
  - `feature-62-modelo-303-390` — README "supported modelos" lists
    130, 303, 390 with a note that 303/390 land in #62.
- **`RELEASING.md` already exists on `main` (from #60)** and is
  authoritative. The rewrite leaves it untouched; the project-meta
  test only asserts existence + a `just release` reference.
- **All Python modules MUST live under `src/aeat/`**. The single
  project-meta test at `tests/test_docs.py` is justified in the ADR
  as a non-subpackage repo-root meta test, the same pattern used by
  `tests/test_config.py` and `tests/test_release_config.py`.
- **Tooling:** `ty` (not `mypy`), `prek` (not `pre-commit`), `uv`,
  `just`. Documented commands must match the on-main `justfile`.

## on-main subpackages (verified via `ls src/aeat/`)

`auth`, `browser`, `cli`, `corpus`, `deadlines`, `filing`, `i18n`,
`inbox`, `llm`, `manuals`, `models`, `normatives`, `portals`,
`schema`, `status`, `storage`, `submission`, `sync`, `testing`, plus
top-level modules `config.py`, `env_io.py`, `errors.py`, `logging.py`.

In-flight (referenced with merge callouts): `workflow` (#59),
`setup` (#61), `casillas` / `justificante` (referenced where the
filing draft engine consumes them — already part of `filing`).

## conventions surveyed

- **README structure** patterns from Cargo / Poetry / FastAPI / httpx:
  one-line description → status banner → what it does → what it does
  not do → quick start → architecture → roadmap → contributing →
  license → disclaimer. Quick start is a single copy-paste block.
- **getting-started** pattern from FastAPI / httpx / Typer: prose
  walkthrough that mirrors a real first-run, one section per command,
  ending with a FAQ.
- **RELEASING** pattern from cpython / poetry: human-gated workflow
  with explicit numbered steps, version-source-of-truth callout, and
  conventional-commits table. The on-disk `RELEASING.md` from #60
  already follows this.

## risks

- The README documents the *intended* state at the next milestone
  (`0.1.0-pre-alpha`); if #59 or #61 are not on `main` at PR-merge
  time, the relevant blocks must remain marked "(merging in #...)".
- The architecture diagram references at least 5 on-main subpackages
  by name — verified in the ADR acceptance check.
- The disclaimer about tax automation is non-negotiable and must
  appear verbatim in the README.
