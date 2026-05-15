---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/adr/ location)
# Feature tag (replace corpus-registry-packaging with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#adr'
  - '#corpus-registry-packaging'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-15'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-15-corpus-registry-packaging-research]]"
  - "[[2026-05-01-corpus-data-hydration-adr]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
  - "[[2026-04-25-error-code-registry-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `corpus-registry-packaging` adr: Bundle corpus and registry trees as in-wheel package resources | (**status:** `accepted`)

## Problem Statement

The repository persists Spanish-tax reference data across two
top-level trees outside the Python package source: `corpus/` (manuals,
normatives, official AEAT workbooks, parity replays) and `registry/`
(authoritative TOML registries for modelos, legal parameters,
calendars, categories, VAT rates, topics, user-profile schema). The
runtime resolves every read off a `PROJECT_ROOT` constant defined in
`src/aeat/core/config.py` as
`Path(__file__).resolve().parent.parent.parent.parent`, then joins
`PROJECT_ROOT / "corpus" / ...` or `PROJECT_ROOT / "registry" / "aeat"`.
This walk lands on the repository checkout when running from source,
but lands inside `site-packages` when running from an installed
wheel — where neither tree exists. The wheel build target in
`pyproject.toml` packages only `src/aeat` plus two explicit data files;
nothing under `corpus/` or `registry/` is included. The installed
package therefore cannot serve the calculations, legal grounding,
manuals, parity, or registry surfaces it claims. The decision needed
is how the curated data reaches an installed distribution.

## Considerations

The data is the product. The application's calculations, legal
citations, manual rules, registry-bound formulas, sede declarations,
deadline calendars, and parity-replay tapes all depend on these trees
being present and readable. Without them the installed wheel is a
shell.

The data is read-only at runtime. No consumer mutates corpus or
registry files; every access is a `Path.open`, `Path.read_text`, or
directory iteration. This makes a `Traversable`-backed boundary a
natural fit and removes any concern about file-system writability of
the bundled location.

Two precedents already use `importlib.resources` inside the codebase.
The BIP-39 wordlist in
`src/aeat/adapters/persistence/storage/master_key/_recovery.py` and the
i18n YAML packs in `src/aeat/core/i18n/_render.py` both call
`resources.files(...)` to read package data. A third small file
(`src/aeat/core/external_constants.toml`) is named in the hatch
include array but the loader still uses `Path(__file__).parent`. No
helper module abstracts resource access today. The packaging refactor
needs one canonical accessor so call sites stop choosing between the
file-system walk and ad-hoc `__file__` parent chains.

The corpus and registry trees can be shipped inside the wheel without
relocating them on disk. Hatchling's
`[tool.hatch.build.targets.wheel.force-include]` table maps any source
path on disk to a relative distribution path inside the wheel. The
trees stay at `corpus/` and `registry/` in the repository checkout;
the wheel sees them at `aeat/_data/corpus/...` and
`aeat/_data/registry/...`. Editable installs honour the same mapping,
so a developer running `uv sync` continues to read the in-tree
sources through the same `importlib.resources` API. Hatchling 1.19
raises an error if a force-included source path does not exist, which
guards against silent partial bundles when paths drift.

Three Settings fields (`aeat_manuals_root`, `aeat_normatives_root`,
`aeat_vat_catalogue_root`) currently expose env-override knobs for
operators who want to point the runtime at an external corpus mirror.
That capability is preserved: only the *default* changes from the
`PROJECT_ROOT` walk to a packaged-resource resolution. The
`registry/` tree has no Settings field today and the migration does
not introduce one — every `PROJECT_ROOT / "registry" / "aeat"` call
site routes through the resource locator directly.

## Constraints

The data sources cannot be re-derived at install time. The corpus and
registry trees encode AEAT-grounded legal content reviewed by a human
gate per the corpus-data-hydration ADR. Curation is the upstream
authority; the wheel ships the reviewed artefacts. Any solution that
defers data to a post-install download path is rejected by the user
for this ADR.

The data must remain readable through `Path`-like semantics. Existing
loaders iterate subdirectories with `Path.glob` and `Path.iterdir`
and open files with `Path.open`. `Traversable` covers the read
surface directly; `importlib.resources.as_file` covers the residual
cases that need a real disk `Path` (e.g. when a third-party library
demands one). No consumer needs write access.

Test gates may not use mocks, stubs, fakes, skip, xfail, or
tautological assertions. Both layout guards land as real-behaviour
tests against the actual bundled tree and the actual built wheel.

The architecture-boundary rule keeps the new accessor inside
`src/aeat/core/`. Domain, application, adapters, and entrypoints all
depend inward on the core boundary. No adapter-layer "resource
locator" parallel surface is introduced.

Wheel size grows by approximately 139 MB of git-tracked data, of
which approximately 120 MB is the 66 tracked PDFs spanning the
Renta manual allow-list and the `corpus/aeat_official` diseño-registro
evidence files. PyPI imposes a default per-file cap of 100 MB.
Publishing publicly above the cap requires a per-project file-size
grant from PyPI admins. The cap is acknowledged here as a release-
time decision item — request the grant, trim the PDF surface via a
future extras split, or publish only via a private index. This ADR
does not decide which path is taken at release; it ratifies the
in-wheel bundling decision regardless.

## Implementation

A new boundary module ships under `src/aeat/core/resources.py`. It
exposes one function — `packaged_data(*parts: str) -> Traversable` —
that returns a Traversable rooted at
`importlib.resources.files("aeat").joinpath("_data", *parts)`. A
companion helper materialises a real on-disk `Path` for the cases
that require it: `as_path(traversable: Traversable) -> ContextManager[Path]`
wrapping `importlib.resources.as_file`. The module is the only
production surface that knows about `aeat/_data`; every other consumer
calls `packaged_data(...)`.

Hatchling configuration in `pyproject.toml` adopts the force-include
table:

```toml
[tool.hatch.build.targets.wheel.force-include]
"corpus" = "aeat/_data/corpus"
"registry" = "aeat/_data/registry"
```

The two narrow `include` entries that currently ship the BIP-39
wordlist and the external-constants TOML stay where they are (those
files live under `src/aeat/` and are not affected by this ADR). The
`packages = ["src/aeat"]` line stays; the new bundled trees ride
alongside it under the wheel-internal `aeat/_data/` prefix.

Consumer migration runs in four concentric buckets:

The first bucket is the boundary itself: `src/aeat/core/resources.py`
plus tests, plus the hatch configuration change, plus the
`PROJECT_ROOT` constant in `src/aeat/core/config.py` losing its
`corpus`/`registry` join responsibility. The constant may stay for
`var/` outputs but the corpus/registry resolution paths leave it.

The second bucket is the three Settings fields:
`aeat_manuals_root`, `aeat_normatives_root`, and
`aeat_vat_catalogue_root`. Their defaults switch from the
`PROJECT_ROOT` join to a resource-locator resolution that returns a
`Path` materialised through `as_file` at startup. Env-override
semantics are preserved verbatim — operators with an external corpus
mirror keep working. Domain loaders that read the field
(`src/aeat/domain/manuals/_loader.py`,
`src/aeat/domain/normatives/_loader.py`,
`src/aeat/application/registry/_corpus.py`) need no signature change.

The third bucket is every hard-coded `PROJECT_ROOT / "registry" / "aeat"`
and `PROJECT_ROOT / "corpus" / ...` call site under `src/aeat/`. The
production surface spans `src/aeat/application/diagnostics.py`,
`src/aeat/application/filing/runtime.py`,
`src/aeat/application/filing/__init__.py`,
`src/aeat/application/modelo/_actions.py`,
`src/aeat/application/verification/_verify.py`,
`src/aeat/application/topics/__init__.py`,
`src/aeat/adapters/inbound/declaracion/_parser.py`,
`src/aeat/adapters/outbound/aeat/sede/_declarations.py`,
`src/aeat/domain/vat/_rates.py`,
`src/aeat/domain/vat/_catalogue.py`,
`src/aeat/domain/vat/_recargo_equivalencia.py`,
`src/aeat/domain/rental/_imputacion_parameters.py`,
`src/aeat/domain/deadlines/_recargo.py`,
`src/aeat/domain/deadlines/_festivos.py`,
`src/aeat/domain/deadlines/_engine.py`,
`src/aeat/domain/categories/_registry.py`,
`src/aeat/domain/user_profile/_loader.py`,
`src/aeat/entrypoints/cli/_modelo.py`,
`src/aeat/entrypoints/cli/_common.py`,
`src/aeat/entrypoints/cli/_app_live.py`,
`src/aeat/entrypoints/cli/_config/_google.py`, and
`src/aeat/entrypoints/cli/registry.py`. Each call site replaces the
`PROJECT_ROOT` join with a `packaged_data(...)` call returning the
appropriate subtree. Signatures that already accept an optional
`registry_root: Path | None = None` keep that parameter as an explicit
override; the default value moves to `packaged_data("registry", "aeat")`.

The fourth bucket is the test surface. Approximately 90 test modules
share the same `PROJECT_ROOT / "registry" / "aeat"` pattern and
migrate to the same locator. The migration preserves real-behaviour
semantics — no test gains a mock, fake, or skip as part of this
change. The CLI default in `src/aeat/entrypoints/cli/registry.py` for
`corpus/aeat_official/disenos_registro` migrates similarly.

Two real-behaviour test guards land alongside the migration:

The first guard is an in-process layout assertion under
`src/aeat/core/test_resources.py`. It imports `aeat`, calls
`packaged_data(...)` for a representative leaf in each top-level
subtree (`manuals/iva/2025/manifest.json`,
`normatives/html/ley-27-2014-art-100.html`,
`parity_replays/renta_web_open/<a known file>`,
`aeat_official/disenos_registro/modelo_100/manifest.json`,
`registry/aeat/modelos/100.toml`,
`registry/aeat/calendars/<a known file>`,
`registry/aeat/legal/iva-flow.toml`,
`registry/aeat/topics/<a known file>`,
`registry/aeat/user_profile/schema.toml`,
`registry/aeat/vat/rates.toml`), and asserts each returned
Traversable reports `is_file()` true. This guard exercises both
editable-install and installed-wheel layouts identically.

The second guard is a built-wheel manifest assertion under
`src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`. The test
shells out to `uv build --wheel` into a `tmp_path`, opens the
resulting wheel as a zip archive, enumerates every git-tracked path
under `corpus/` and `registry/` via `git ls-files`, and asserts that
every tracked path appears in the archive at the expected
`aeat/_data/<relative-path>` prefix. The test runs as part of the
default unit gate. It fails loudly when someone edits
`pyproject.toml`, moves a file, or drops a path without updating the
hatch configuration. It uses no mocks, fakes, or skips; the
subprocess and zip inspection are real.

The third small change is to `src/aeat/core/external_constants.py`:
its `Path(__file__).resolve().parent` walk migrates to
`resources.files(__package__).joinpath("external_constants.toml")` so
the codebase consolidates on a single resource-access idiom. The
hatch `include` entry for that file remains.

## Rationale

Force-include keeps the on-disk layout stable while making the wheel
self-sufficient. The repository's curators continue to author corpus
and registry content at the top-level paths they have always used.
Reviewers and editors do not relearn the layout. Git history for
those trees is untouched (no mass-rename), which keeps blame and PR
review tractable. The wheel is the only place the
`aeat/_data/...` prefix appears, and the resource locator is the only
place that prefix is written down in code. The hidden coupling
between the runtime and the checkout location dies.

A single `Traversable`-returning boundary is the smallest possible
surface that satisfies every consumer. It avoids parallel APIs for
"file" vs "directory" lookups, it composes through `joinpath`, it
covers iteration through `iterdir`, and it returns directly to
`Path` semantics through `as_file` for the residual cases that need
disk identity. The accessor is testable in isolation; every call
site is a one-line refactor.

The `corpus-data-hydration` ADR (status: accepted) locked the
authority for *what* is curated and *how* curation is reviewed; this
ADR locks how the curated outputs reach the installed artefact. The
two decisions compose: corpus-data-hydration writes to
`corpus/casillas/<modelo>/<year><period>.json` (and analogous paths);
packaging makes those same paths land at `aeat/_data/corpus/...`
inside the wheel with byte-for-byte equivalence.

Real-behaviour test guards align with the project's quality-gate
rules. The in-process leaf assertion exercises the same import
surface every production caller uses. The built-wheel zip assertion
exercises the actual build pipeline rather than re-asserting the
hatch configuration in prose. Both guards fail closed on layout
drift without falling back on tautological re-statement of the
schema.

## Consequences

Installed wheels become self-contained. `pip install aeat` (or the
equivalent uv path) lands a single archive that resolves every
runtime read through `importlib.resources` without any sibling
directory lookup. The "must run from a checkout" assumption is
removed.

The wheel grows by approximately 139 MB. Public PyPI publication
requires either a file-size-limit grant or a future trim. Internal
distribution via a private index is unaffected. The release-time
decision is captured for the release-engineering owner to resolve.

Editable installs and the dev loop keep working without changes to
the developer workflow. `uv sync` continues to install in-place;
`importlib.resources.files("aeat").joinpath("_data", ...)` resolves
to the in-tree sources under hatchling's editable-install behaviour.

Every `PROJECT_ROOT / "registry"` or `PROJECT_ROOT / "corpus"` call
site changes. The diff is wide (~120 source and test files) but
mechanical once the locator lands. The migration has no behavioural
test changes — every test continues to read the same files; only
the resolution path differs. Tests that already accept an injectable
`registry_root: Path | None` keep their injection seam.

The `PROJECT_ROOT` constant in `src/aeat/core/config.py` retains its
`var/` output role but loses every `corpus`/`registry` join. A
future cleanup may move the `var/` defaults to an operator-config
surface independent of the source-checkout layout; that is out of
scope here.

Future packaging refinements remain possible. An extras split
(`aeat[full-pdf]` vs `aeat[base]`) or a companion data distribution
could trim the wheel later without re-deciding the resolution
strategy: every consumer already reads through the locator, so a
later extras boundary would only re-source the bundled prefix. The
locator is the load-bearing decision; the bundling mechanism behind
it is replaceable.
