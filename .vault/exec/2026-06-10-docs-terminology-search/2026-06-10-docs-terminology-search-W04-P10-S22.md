---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S22'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Vendor and pin the Pagefind binary/wheel for the offline-hermetic build and add the post-build index pass over the built HTML (addDirectory), keeping the nitpicky Sphinx gate untouched

## Scope

- `document the Orama fallback trigger (ADR D5)`
- `dev docs build pipeline + dependency pinning`

Implements ADR D5: Pagefind is the search backend, vendored/pinned for the
offline-hermetic build, indexing the built docs HTML post-build. Starts the
W04 track ending at the Ctrl-K palette. The palette wiring and the
custom-record injection are later steps; this stands up the vendored binary,
the post-build index pass, and the Furo search surface.

## Description

- FEASIBILITY PROBE FIRST: confirm Pagefind is obtainable in this
  environment (the decisive question).
- Vendor + pin `pagefind[extended]` in the dev dependency group; sync to
  lock it and install the bundled binary into the env.
- Author the post-build index pass `dev/docs/pagefind_index.py`: a standalone
  step (NOT a Sphinx `setup()` hook) that runs `add_directory` over the built
  HTML and writes the chunked per-language index into
  `docs/_build/html/pagefind/`, with a clearly-marked custom-record injection
  seam.
- Author `docs/pagefind.yml` (root_selector `article[role=main]`, exclude
  chrome) and the Furo `docs/_templates/search.html` override loading the
  Pagefind UI from the index output.
- Prove the pass end-to-end over real built HTML and a self-contained fixture
  (no full multi-minute build), including the es/ca/en per-language splits.
- Document the Orama fallback trigger.
- Verify: ruff + format + ty clean, the index-pass + config + template tests
  green, collect-only clean.

## Outcome

### FEASIBILITY: YES - Pagefind is vendorable in this environment

The decisive answer. Pagefind's Python packaging is three pieces: `pagefind`
(the ~10 KB pure-Python API wrapper, no binary) plus two binary-carrying
extras - `pagefind[bin]` (standard binary) and `pagefind[extended]` (the
binary WITH the es/ca/hu/en Snowball stemmers, ~50 MB per platform). PyPI is
reachable here, the `pagefind_bin_extended-1.5.2-py3-none-win_amd64.whl`
exists for this win32 env, and the binary is BUNDLED INSIDE the wheel - so
once the wheel is pinned, the post-build index pass invokes the bundled
binary and makes NO network fetch (offline-hermetic satisfied). All
MIT-licensed.

How it is pinned: `pagefind[extended]>=1.5,<2` added to the
`[dependency-groups] dev` block in `pyproject.toml`; `uv.lock` now records
`pagefind` (extra=extended) and `pagefind-bin-extended`. The install was
verified: `import pagefind` works and the bundled binary runs offline (proven
by the real index passes below). The standard `bin` extra would omit the
es/ca stemmers, so `extended` is the required choice for the per-language
splits the ADR mandates.

### Post-build index pass (location + contract)

`dev/docs/pagefind_index.py`, `build_search_index(html_root, *, inject=None)
-> SearchIndexResult`. Contract: it is a STANDALONE post-build step (NOT a
`conf.py` `setup()` hook) so it runs AFTER Sphinx and cannot affect the
nitpicky `-n -W` gate. It confirms the vendored package is importable (raising
the named `PagefindUnavailableError` if not), runs Pagefind's `add_directory`
over `html_root`, and writes the chunked per-language index into
`<html_root>/pagefind/` (an uncommitted build artifact, regenerated every
build like `docs/cli/`). The docs build driver / `just docs` calls it after a
successful build. Proven over the real existing `docs/_build/html` subset and
a self-contained fixture: the pass indexes the pages and emits `pagefind.js`,
`pagefind-ui.js`, `pagefind-ui.css`, and per-language `*_*.pf_index` /
`*.pf_fragment` chunks.

### The custom-record injection seam (where the next step plugs in)

`build_search_index` accepts an optional `inject` async callback invoked with
the open `PagefindIndex` AFTER `add_directory` and BEFORE `write_files`. The
custom-record step adds the unified search records plus the sweep-derived
relevance weights there via `index.add_custom_record(url=..., content=...,
language=..., meta=..., filters=..., sort=...)`. This module owns ONLY the
directory pass and the write, never the record content - a clean seam. Proven:
a test injects es and ca custom records through the seam and the resulting
index carries `es`, `ca`, and `en` per-language splits (which also proves the
extended binary's Spanish AND Catalan stemmers are vendored).

### Furo search-surface scaffold

`docs/pagefind.yml` scopes indexing to `article[role=main]` (the Furo content
element, confirmed in the built HTML) and excludes the sidebar tree, the TOC,
headerlinks, and copy buttons. `docs/_templates/search.html` overrides the
stock Sphinx search page (it lives in the already-loaded `templates_path`)
and loads `pagefind/pagefind-ui.{js,css}` to render the Pagefind search box -
the full-text surface the palette's full-text tier hands off to. (The palette
Ctrl-K wiring to Pagefind is a separate step; this only stands up the search
surface.)

### Orama fallback trigger (documented)

Pagefind is chosen as the only surveyed engine satisfying every hard
constraint at once (MIT, offline, native es/ca/hu/en stemming with
per-language splits, lazy chunked scaling, first-class custom-record API).
The documented fallback is Orama (Apache-2.0, pure JS). Trigger: switch to
Orama ONLY if the Pagefind binary proves unvendorable for the offline-hermetic
build - the `pagefind[extended]` wheel cannot be pinned for a target platform,
or a platform has no published bundled wheel and the build would need a
network fetch. In THIS environment vendoring succeeded, so the fallback is not
triggered; it is the documented escape hatch for a future platform-coverage
gap. Orama's cost: a sourced Catalan Snowball stemmer (Orama bundles none) and
whole-index loading instead of lazy chunking. The trigger is recorded in the
`pagefind_index.py` module docstring.

### What was tested vs feasibility-gated

EVERYTHING was tested with the real vendored binary - nothing is
feasibility-gated, because the vendoring succeeded. Tests
(`dev/docs/tests/test_pagefind_index.py`, 5 green): the real index pass over
HTML produces the index + UI bundle; the injection seam runs and yields
es/ca/en splits; the `pagefind.yml` scopes to the article body; the
`search.html` template references the UI bundle; the vendor-absent boundary
is a named error. ruff / format / ty clean; collect-only clean. The full
multi-minute docs build was deliberately NOT run - the index pass was proven
against an existing build subset and a self-contained fixture, per the brief.

## Notes

- No coordinator decision needed: Pagefind vendored cleanly (the
  feasibility risk the brief flagged did not materialise).
- During `uv sync` a peer process held `Scripts/aeat.exe`, so the full sync
  aborted on that file lock; `uv pip install "pagefind[extended]"` installed
  the package directly without rebuilding the locked `aeat` entrypoint. The
  lockfile pin and the env install are both in place; the `aeat.exe` lock is
  a transient peer-process artifact, not a pagefind issue.
- No PM wave/phase/step tokens in production code or tests (one `S23`
  reference in a test docstring was removed before commit; ADR ids only in
  this exec record). The one ty suppression on the test's dynamic
  `add_custom_record` call is justified inline (the pagefind index object is
  dynamically typed).
- The compiled Pagefind index is an uncommitted build artifact (written into
  `docs/_build/html/pagefind/`, already gitignored under `docs/_build/`);
  only the vendored wheel pin, the index-pass code, the `pagefind.yml`, and
  the search template are committed.
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` as the very last action,
  explicit paths only, never touching `index.lock`.
