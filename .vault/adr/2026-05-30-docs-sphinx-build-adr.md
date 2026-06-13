---
tags:
  - '#adr'
  - '#docs-sphinx-build'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-30-docs-architecture-research]]"
  - "[[2026-05-30-docs-architecture-adr]]"
  - "[[2026-04-17-relative-imports-adr]]"
  - '[[2026-06-04-docs-sphinx-build-research]]'
---



# `docs-sphinx-build` adr: `sphinx documentation build architecture and link conformance` | (**status:** `accepted`)

This is the second of three ADRs in the documentation epic. It builds on
the surface taxonomy and conventions ADR, which mandated Google-style
docstrings plus the Sphinx cross-reference vocabulary and deferred the
build wiring, the link gate, and the module-to-stub correspondence test
here. CLI-specific documentation conformance is decided in the third ADR.

## Problem Statement

A full Sphinx pipeline exists on disk but is unbuilt, ungated, and
internally inconsistent. `docs/conf.py` configures `furo`, autodoc over
the package, intersphinx to five projects, a markdown builder, and MyST,
and a 147-file API stub tree is hand-committed under `docs/api/`. Yet
there is no build entrypoint (a `pyproject.toml` comment claims a
`just docs` recipe that does not exist), `docs/index.rst`'s toctree
references narrative pages (`getting-started`, `architecture`) that were
deleted, and `conf.py`'s `exclude_patterns` names legacy narrative files
that are also gone. Worse, the configuration actively hides the defects a
conformance gate must catch: `suppress_warnings=['myst.xref_missing']`
silences cross-reference warnings, and a broad `autodoc_mock_imports`
list means autodoc renders pages for modules whose dependencies are not
importable.

The surface taxonomy ADR mandated the Sphinx cross-reference vocabulary
as a convention and required that every surface be generated from code or
pinned by a drift-detecting test. This ADR decides the build architecture
and the programmatic gates that make the generated-Sphinx surface
conformant: a clean, repeatable build; valid, standardized cross-linking;
a module-to-stub correspondence test; and the recipes and suite wiring
that run them.

## Considerations

The `docs-architecture` research and the conventions ADR establish the
baseline; the relevant build-specific factors:

- **The API stub tree is hand-committed and manually regenerated.** 147
  `docs/api/*.rst` automodule stubs are versioned and refreshed by hand on
  module renames. This is the drift surface: a renamed or new module
  silently desynchronizes the docs from the code unless a test enforces
  correspondence.
- **Autodoc import strategy is constrained.** Per the relative-imports
  decision, autodoc resolves the package through `sys.path` insertion of
  `src/` rather than an installed wheel, plus an `autodoc_mock_imports`
  allowlist for heavy native dependencies. Mock-imported modules cannot
  resolve their own type cross-references, so nitpicky mode will flag them
  unless they are in a curated ignore set — the mock list and the nitpick
  baseline are coupled.
- **Two output builders are configured.** `furo` HTML and
  `sphinx_markdown_builder` markdown. The HTML build is the
  contributor-facing API reference; the markdown output's consumer must be
  named or the builder dropped.
- **Cross-linking tooling.** `sphinx.ext.intersphinx` (python, pydantic,
  sqlalchemy, httpx, typer), `viewcode`, `add_module_names=False`,
  `python_use_unqualified_type_names=True`, and
  `autodoc_typehints='description'` are already set and define the
  semantic-linking baseline to standardize on.
- **Gate tooling.** `sphinx-build -b html -n -W --keep-going` is the
  nitpicky, warnings-as-errors, collect-all build; `sphinx-build -b
  linkcheck` validates external URLs; `doc8` (or `rstcheck`) standardizes
  RST formatting. These are additive to the conventions ADR's docstring
  gates.
- **Placement.** There is no top-level `tests/` root in this repo (the
  deleted `tests/test_docs.py` predated the restructure); the
  architecture-boundaries rule forbids adding one. Repo-level invariant
  tests live under `src/aeat/tests/` and surface-specific tests beside
  their code (for example `src/aeat/entrypoints/cli/test_root_help_shape.py`).
  Documentation conformance tests are colocated under `src/aeat/`
  accordingly.

## Constraints

- **English-only now; a declared multilang seam.** `conf.py` stays
  `language='en'`. This ADR does not wire gettext/`locale_dirs`/
  `sphinx-intl`; it only names where that wiring would attach for the
  deferred multilang user-docs surface.
- **Hard-cut, no suppression of real defects.** Consistent with the
  conventions ADR: the link gate runs nitpicky with warnings-as-errors and
  no blanket warning suppression. `nitpick_ignore` is a curated set of
  genuinely-external reference targets, not a silence-everything switch.
- **No mocks/stubs as a shortcut, no `sphinx-build` mocking in the test.**
  The conformance test invokes a real `sphinx-build` and asserts a clean
  exit; it does not assert on a fabricated build result.
- **The lint recipe must be green first.** The conventions ADR flagged
  that the existing lint recipe references an absent
  `scripts/check_relative_imports.py`; the docs recipes are added
  alongside a lint recipe that the plan must first restore to green.

## Implementation

This ADR decides the following.

**1. `docs/` is the Sphinx source root, with a fixed layout.** `conf.py`
and `index.rst` at the root; `docs/api/` holds the per-module autodoc
stubs; `docs/_static/` and `docs/_templates/` hold assets and overrides;
`docs/_build/` is gitignored output (the conformance build writes to a
`tmp_path`, not the shared `docs/_build`, so concurrent worktrees and CI
lanes do not race on one output directory). The narrative pages
(`getting-started`, `architecture`) are a toctree dependency of this
surface, but their authorship belongs to the markdown bootstrap surface
(conventions ADR surface one); this ADR only requires that `index.rst`
reference them once they exist.

**2. Build pipeline and recipes.** Two new recipes are added: `just docs`
builds the `furo` HTML output, and `just docs-check` runs the conformance
gate (below). The documented-but-missing `just docs` recipe is thereby
made real. The `sphinx_markdown_builder` extension is **dropped**: it has
no consumer in this epic (its only prospective consumer, the multilang
user-docs surface, is out of scope), and a configured-but-unconsumed
builder is exactly the kind of dead output this epic exists to remove. If
the deferred multilang surface later needs a markdown rendering, the
builder is re-added then, against a real consumer.

**3. Link-and-display conformance gate.** The canonical gate is
`sphinx-build -b html -n -W docs <tmp-out>`: `-n` (nitpicky) flags every
unresolved cross-reference and `-W` turns warnings into errors. On the
project's Sphinx (>= 8.0) `-W` already collects all warnings before
failing, so `--keep-going` is not used (it is a deprecated no-op there).
The gate is wrapped as a pytest test colocated under `src/aeat/` that
shells a real `sphinx-build`, and is also exposed via `just docs-check`.
The test is made hermetic and fast-gate-safe: it builds into a `tmp_path`
(never the shared `docs/_build`), runs with intersphinx resolved from
cached inventories / offline so it is not a network test, and carries a
marker so it can be excluded from the fast unit lane and run in
`just docs-check` / CI. `doc8` (or `rstcheck`) standardizes RST
formatting and runs in the same lane. This is the enforcement the
conventions ADR's cross-reference vocabulary mandate was declared against.

External-URL validation (`sphinx-build -b linkcheck`) is **advisory and
CI-scheduled, not a blocking suite gate**: it is inherently
network-dependent and several AEAT/BOE endpoints rate-limit or block
automated clients, so a curated `linkcheck_ignore` covers those and
linkcheck failures never red the local `just test` gate.

**4. Remove the suppression and curate a nitpick baseline.**
`suppress_warnings=['myst.xref_missing']` is removed.
`nitpick_ignore`/`nitpick_ignore_regex` are populated with exactly the
genuinely-external Python-domain reference targets — including the types
exposed by `autodoc_mock_imports` modules, which cannot resolve and would
otherwise flood the gate. The mock-imports list and the nitpick baseline
are maintained together; adding a mock import without its nitpick entries
is treated as incomplete.

`nitpick_ignore` governs only nitpicky `(domain, target)` missing-
reference warnings; it does **not** cover MyST narrative cross-reference
warnings, which are emitted by a different code path. Narrative-MyST link
integrity is therefore achieved by fixing the references so they resolve
(the intended outcome). Where a MyST construct legitimately cannot resolve
(a deliberate external anchor), it is handled by a narrowly-scoped
`suppress_warnings` sub-category for that specific case — never by
re-adding the blanket `myst.xref_missing`, and not via `nitpick_ignore`,
which would not apply.

**5. Module-to-stub correspondence test.** A test colocated under
`src/aeat/` asserts *set* correspondence between the `src/aeat/` module
tree and the `docs/api/*.rst` automodule stub set: every in-scope module
has a stub and every stub points at a real module (no orphan stubs). The
assertion is on the module-versus-stub set, **not** a byte-diff against a
fresh `sphinx-apidoc` run (apidoc output is flag-sensitive and a content
diff would fail spuriously). The in-scope set excludes exactly what the
build already excludes: `test_*.py` / `_test_*.py` modules, the
`aeat.tests` package, the private `aeat._data` package, and `_`-prefixed
modules — named here so the boundary is unambiguous and matches
`conf.py`'s exclusions. A rename or new module therefore fails the gate
rather than silently drifting — the conventions ADR's
"generated-API-docs surface is pinned by a test" obligation, made
concrete. Whether the committed stubs are regenerated by `sphinx-apidoc`
or a project script is an implementation choice for the plan; the
contract is the set-correspondence assertion.

**6. Standardized semantic cross-linking.** The API reference mirrors the
package layout as its toctree hierarchy. The hexagonal cores
(`domain`, `adapters`, `application`, `entrypoints`, `core`) are the
primary axes, but the toctree covers every in-scope top-level subpackage —
which today also includes `diagnostics` and `locales` — with the exact
set governed by the correspondence test (decision 5) rather than a
hand-maintained list that can drift. Symbol links use the Sphinx
cross-reference roles mandated by the conventions ADR; intersphinx keeps
its five-project baseline; `viewcode`, `add_module_names=False`,
`python_use_unqualified_type_names=True`, and
`autodoc_typehints='description'` are retained as the display standard.
`index.rst`'s toctree is repaired to reference only existing pages
(narrative pages plus `api/aeat`), and the stale `exclude_patterns`
entries for removed legacy files are deleted.

**7. Multilang seam (declared, not wired).** `conf.py` documents the
single attachment point where `language`, `locale_dirs`, and a gettext
build matrix would later be introduced for the deferred multilang
user-docs surface. No gettext extraction, `.po` catalogues, or
`sphinx-intl` dependency are added by this ADR.

## Rationale

The build gate is chosen as a real `sphinx-build -n -W` wrapped in a
colocated test, rather than a bespoke link parser, because Sphinx's own
resolver is the authority on whether a cross-reference resolves;
re-implementing it would be both less accurate and a maintenance burden.
On Sphinx 8.0+ `-W` already collects every warning before failing, so a
remediation pass sees all failures at once without the legacy
`--keep-going` flag.

Removing `suppress_warnings` and curating `nitpick_ignore` — rather than
leaving suppression in place — is the only way the gate can be meaningful;
a gate that runs against silenced warnings proves nothing. Coupling the
nitpick baseline to the mock-imports list reflects the real dependency:
the mocks are why certain references cannot resolve, so the ignore set
must track them.

The module-to-stub correspondence test addresses the single largest drift
risk identified in the research — hand-committed stubs regenerated
manually — by making divergence a test failure. This is what turns
"docs are generated from code" from aspiration into an enforced invariant.

Keeping the build English-only with a declared seam, rather than wiring
multilang now, honors the epic's English-first scope while ensuring the
future surface has a single, documented attachment point instead of an
ad-hoc retrofit.

## Consequences

- **The gate cannot be switched on until the build is clean.** Repairing
  the toctree, removing suppression, curating the nitpick baseline, and
  bringing the API stub tree into correspondence are remediation work the
  plan must sequence before `just docs-check` and the suite test are
  wired as blocking — consistent with the conventions ADR's hard-cut
  full-tree remediation wave.
- **The nitpick baseline is ongoing maintenance.** Every new heavy
  dependency added to `autodoc_mock_imports` must add its nitpick-ignore
  entries in the same change; the correspondence and link tests will fail
  otherwise. This cost is accepted as the price of a meaningful gate.
- **New dev dependencies and recipes.** `doc8` (or `rstcheck`) is added;
  `just docs` and `just docs-check` recipes are added; the Sphinx deps are
  already present.
- **The Sphinx version floor matters to the gate's flags.** The flag
  semantics decided here assume Sphinx >= 8.0 (where `-W` collects all
  warnings and `--keep-going` is a no-op); the installed version is 9.x
  and `pyproject.toml` pins `sphinx>=8.1`. The plan keeps that floor (and
  may add an upper bound) so the gate invocation stays stable across the
  fleet.
- **The markdown builder is removed.** `sphinx_markdown_builder` is
  dropped from `conf.py` rather than left as a configured-but-unconsumed
  output; it is re-added only against a real consumer if the deferred
  multilang surface needs it.
- **The deferred multilang surface has a single attachment point.** The
  documented seam prevents a future scattered retrofit, at the cost of a
  few explanatory lines in `conf.py` now.
- **CLI documentation conformance is explicitly out of scope here.** The
  command-tree-driven CLI reference and its docs-vs-tree conformance are
  decided in the third ADR; this ADR governs only the Sphinx build and the
  docstring-derived API surface.
