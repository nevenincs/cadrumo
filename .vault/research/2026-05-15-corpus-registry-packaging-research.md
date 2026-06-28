---
tags:
  - '#research'
  - '#corpus-registry-packaging'
date: '2026-05-15'
modified: '2026-05-15'
related:
  - "[[2026-05-01-corpus-data-hydration-adr]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
  - "[[2026-04-25-error-code-registry-adr]]"
  - "[[2026-04-18-rename-corpus-review-schema-adr]]"
---



# `corpus-registry-packaging` research: bundling the corpus and registry trees inside the installed wheel

The repository ships ~139 MB of git-tracked Spanish-tax reference data
across two top-level trees that the Python runtime resolves through
`Path(__file__).resolve().parent.parent.parent.parent` walks. The
project's own build target packages only `src/aeat` plus two explicit
data files, so a wheel installed into `site-packages` cannot locate
either tree. This research enumerates the consumers, documents the
existing `importlib.resources` precedents, surveys the hatchling
mechanism for shipping out-of-source data, and captures the costs of
the user-fixed in-wheel bundling strategy. The findings here ground the
upcoming packaging ADR.

## Findings

### 1. Inventory: who reads `corpus/` and `registry/`?

Production consumers (grouped by mediation path):

- **Settings-mediated (env-override friendly).** Three pydantic-settings
  fields in `src/aeat/core/config.py` ground the corpus surface:
  `aeat_manuals_root` (default `corpus/manuals`), `aeat_normatives_root`
  (default `corpus/normatives`), `aeat_vat_catalogue_root` (default
  `corpus/financial/vat`). Their defaults are joined off the
  `PROJECT_ROOT` constant at line 57. Domain loaders honour the field:
  `src/aeat/domain/manuals/_loader.py` reads
  `settings.aeat_manuals_root`; `src/aeat/domain/normatives/_loader.py`
  reads `settings.aeat_normatives_root`;
  `src/aeat/application/registry/_corpus.py` line 745 reads
  `resolved.aeat_manuals_root`.
- **PROJECT_ROOT hard-codes (no env override).** The `registry/` tree
  has no Settings field. Every consumer joins
  `PROJECT_ROOT / "registry" / "aeat"` directly. Production sites
  include `src/aeat/application/diagnostics.py` (twice),
  `src/aeat/application/filing/runtime.py`,
  `src/aeat/application/filing/__init__.py`,
  `src/aeat/application/modelo/_actions.py`,
  `src/aeat/application/verification/_verify.py`,
  `src/aeat/application/topics/__init__.py`
  (`_TOPIC_REGISTRY_ROOT`), `src/aeat/adapters/inbound/declaracion/_parser.py`,
  `src/aeat/adapters/outbound/aeat/sede/_declarations.py`,
  `src/aeat/domain/calculations/registry/_loader.py` callers via
  `load_registry_tree(...)`, `src/aeat/domain/vat/_rates.py`,
  `src/aeat/domain/vat/_catalogue.py`,
  `src/aeat/domain/vat/_recargo_equivalencia.py`,
  `src/aeat/domain/rental/_imputacion_parameters.py`,
  `src/aeat/domain/deadlines/_recargo.py`,
  `src/aeat/domain/deadlines/_festivos.py`,
  `src/aeat/domain/deadlines/_engine.py`,
  `src/aeat/domain/categories/_registry.py`, and
  `src/aeat/domain/user_profile/_loader.py`. Entrypoints repeat the
  same pattern: `src/aeat/entrypoints/cli/_modelo.py` line 1771,
  `src/aeat/entrypoints/cli/_common.py`,
  `src/aeat/entrypoints/cli/_app_live.py`,
  `src/aeat/entrypoints/cli/_config/_google.py`,
  `src/aeat/entrypoints/cli/registry.py` (which also carries a CLI
  default of `corpus/aeat_official/disenos_registro` as a typer
  argument).
- **PROJECT_ROOT corpus hard-codes outside Settings.** Beyond the three
  Settings-backed roots, production paths also hard-join
  `PROJECT_ROOT / "corpus" / "aeat_official" / ...` and
  `PROJECT_ROOT / "corpus" / "parity_replays" / ...`. The `aeat_official`
  tree carries the diseño-de-registro manifests and `.properties`
  dictionaries used at registry-load time; `parity_replays` carries
  Sede replay tapes consumed by adapter capture tests.

Test consumers reuse the same pattern (~90 occurrences across
`test_*.py`/`_test_*.py` modules under `domain/calculations/registry`,
`domain/vat`, `application/filing`, `application/aggregation`,
`application/storage/calc_sheets`, `domain/manuals`, `domain/normatives`,
`adapters/outbound/aeat/sede`, and `entrypoints/cli`). Tests fail
identically to production once the tree is no longer adjacent to the
installed package.

Pattern summary: the codebase has one Settings-mediated entry point for
the manuals + normatives + VAT-catalogue slice of the corpus, and a
much larger un-mediated surface (everything under `registry/aeat`, the
`corpus/aeat_official` workbook + diseño tree, and the
`corpus/parity_replays` tapes). The latter is the larger refactor
target.

### 2. Existing `importlib.resources` precedents in this codebase

Only three precedents exist; each is small and read-only:

- `src/aeat/adapters/persistence/storage/master_key/_recovery.py` line
  119 uses `resources.files(__package__).joinpath("_bip39_wordlist.txt")`
  to load the 13 KB BIP-39 wordlist at import time. The file is named
  in the `pyproject.toml` `[tool.hatch.build.targets.wheel].include`
  array so the wheel ships it.
- `src/aeat/core/i18n/_render.py` lines 49 and 181 call
  `importlib.resources.files("aeat").joinpath("locales", ...)` for
  the YAML translation packs. Those files sit at
  `src/aeat/locales/*.yml` and ride along automatically because they
  are inside the packaged `aeat` tree.
- `src/aeat/core/external_constants.py` line 19 names a third
  small file (`external_constants.toml`) and explicitly listed it in
  the hatch include array, but the loader uses
  `Path(__file__).resolve().parent / "external_constants.toml"` rather
  than `importlib.resources`. The two patterns coexist; no helper
  module abstracts resource access today.

No `importlib.resources.as_file` usage exists; no `Traversable`
boundary is in place. The packaging refactor needs to introduce one
canonical accessor so call sites stop choosing between the file-system
walk and ad-hoc `__file__` parent chains.

### 3. Hatchling mechanism: how to ship `corpus/` and `registry/` inside the wheel

The current build configuration in `pyproject.toml` lines 107-115 uses
`[tool.hatch.build.targets.wheel].packages = ["src/aeat"]` plus an
`include` array carrying two explicit files. Two hatchling features
relevant here:

- `[tool.hatch.build.targets.wheel.force-include]` maps any source
  path on disk to a relative distribution path inside the wheel,
  without requiring the source layout to move. The published docs
  (`docs/config/build.md`) show entries such as
  `"../artifacts" = "pkg"` and `"~/lib.h" = "pkg/lib.h"`. The mechanism
  preserves directory shape; nested files appear under the mapped
  target prefix. Hatchling 1.19 raises an error if the source path
  does not exist at build time — a useful guard for our case.
- `force_include_editable` is the editable-install counterpart for
  the wheel target. Editable installs honour `force-include` mappings;
  `force_include_editable` overrides them when an editable build
  needs a different layout (it should not be needed here because the
  in-tree source paths already exist when running from a checkout).

The minimal hatch change is therefore additive: keep the existing
`packages` array, drop the two narrow `include` entries into a single
`force-include` block, and add the two top-level trees:

```toml
[tool.hatch.build.targets.wheel.force-include]
"corpus" = "aeat/_data/corpus"
"registry" = "aeat/_data/registry"
```

Once published, every file under `corpus/` lands at
`<wheel>/aeat/_data/corpus/...` and is reachable through
`importlib.resources.files("aeat").joinpath("_data", "corpus", ...)`.
No source-layout migration of the on-disk trees is required.

A clean alternative is to move the two trees physically under
`src/aeat/_data/` and let the `packages` directive pick them up
automatically. That avoids `force-include` entirely but is a noisier
diff (hundreds of git renames) and breaks every call site simultaneously.
Force-include lets the migration land file-by-file with green tests.

### 4. Wheel-size implications

Tracked size of the bundled trees:

- `corpus/` git-tracked: 448 files. `corpus/aeat_official` dominates
  (74 .xlsx, 59 .pdf, 29 .json, 27 .xls, 15 .xsd, 12 .properties);
  `corpus/manuals` carries an allow-listed subset of `source.pdf`
  binaries (the `.gitignore` keeps untracked years out of the tree);
  `corpus/normatives` is 201 HTML files; `corpus/parity_replays` is
  small.
- `registry/` git-tracked: 73 files (mostly TOML).
- Combined tracked total: 521 files, **~139 MB on disk**, of which
  ~120 MB is the 66 tracked PDFs.

PyPI imposes a default per-file cap of 100 MB on uploads. Anything
above the cap requires a per-project file-size-limit grant from the
PyPI admins. A 139 MB wheel exceeds the default; before publishing
to PyPI we either request the grant or trim. (Internal-only
distribution via a private index is unaffected by the public cap.)
Per the scope decision the project will ship the data in-wheel
regardless, but the ADR must call out the PyPI-cap interaction so a
release-time surprise does not block a launch.

Install-time UX is otherwise unremarkable: the wheel decompresses
once, and `importlib.resources.files("aeat")` resolves against the
already-on-disk layout with no extra IO at import.

### 5. PDF handling and curation-vs-runtime split

`.gitignore` already separates curation artefacts from durable assets:
the rule `corpus/manuals/**/source.pdf` is general-deny, with seven
explicit allow-list exceptions for the Renta IRPF 2020-2025 part
PDFs. Those exceptions exist because the registry catalogues cite
specific page ranges in those PDFs (`relative_pdf_path = "source.pdf"`
in `src/aeat/domain/manuals/_schema.py` and the registry source
catalogues). `corpus/aeat_official/disenos_registro/modelo_*/files/*.pdf`
are not behind any allow-list; they are tracked because the
diseño-registro manifests reference them as evidence locators.

Runtime PDF reads exist in production code: `pypdfium2` is a runtime
dependency and `src/aeat/domain/manuals/_loader.py` plus the
registry-source-citation validator can open `source.pdf` for excerpt
verification. The `aeat_official` PDFs are evidence files; their
contents are not parsed at request time but are required for the
oracle-replay parity tests that run as part of the unit suite. Both
sets must therefore be present in any environment that runs the
default unit gate — which means they belong in the wheel for the
"installed application can serve its full surface" criterion. The ADR
should however revisit whether an extras-split (e.g. `aeat[full-pdf]`
vs `aeat[base]`) is worth it solely as a wheel-size optimisation; the
user-fixed bundling decision does not preclude declaring a future
trim.

### 6. Editable-install parity

In a uv-managed editable install (the standard developer flow here),
hatchling materialises the editable target using the same wheel
target. `force-include` mappings are honoured by the editable path
unless overridden by `force_include_editable`. That means
`importlib.resources.files("aeat").joinpath("_data", ...)` returns a
`Traversable` rooted at the in-tree source location, so the dev loop
keeps working without symlinks or post-install hooks. The migration
keeps a single resolution path active in dev and prod.

The one caveat hatchling raises in 1.19+: `force-include` fails the
build if the source path does not exist. That property protects us
from silent partial bundles when someone moves or deletes the data
trees without updating `pyproject.toml`.

### 7. Migration shape: a single resource-locator boundary

The proposed boundary is a single module — call it
`src/aeat/core/resources.py` — exposing one function that returns a
`Traversable`:

```python
from importlib.resources import files
from importlib.resources.abc import Traversable

_PACKAGE_DATA = files("aeat").joinpath("_data")

def packaged_data(*parts: str) -> Traversable:
    """Return a Traversable rooted at <wheel>/aeat/_data/<parts...>."""
    node = _PACKAGE_DATA
    for part in parts:
        node = node.joinpath(part)
    return node
```

`Traversable` exposes `is_dir`, `iterdir`, `joinpath`,
`open`, and `read_text/read_bytes`. The vast majority of consumers in
this codebase only need `Path`-like read access, and the existing
`load_registry_tree`, manual loader, and normatives loader iterate
subdirectories using `Path.glob` / `Path.iterdir`. For those a small
context-managed `as_file` shim (`with as_file(node) as p: ...`)
produces a real `Path` for the cases that need disk semantics. Most
production paths can switch to `Traversable.joinpath(...).read_bytes()`
without `as_file`.

The Settings fields keep their override semantics: the *default*
becomes the packaged Traversable resolved at startup
(`packaged_data("corpus", "manuals")`), but operator-supplied
`AEAT_MANUALS_ROOT=/var/lib/...` continues to win. This preserves
the existing operator-knob surface while fixing the broken default
and eliminates the `PROJECT_ROOT` walk. The hard-coded
`PROJECT_ROOT / "registry" / "aeat"` call sites migrate to call the
locator directly; they have no env-override surface today so none is
added.

### 8. Test guards that prevent silent regression

Two real-behaviour guards (no mocks, no skips) close the loop:

- **In-process layout assertion.** A unit test imports `aeat`, calls
  `packaged_data("registry", "aeat", "modelos", "100.toml").is_file()`
  and the same for a representative leaf under each top-level
  subtree (manuals, normatives, parity_replays, aeat_official,
  registry/aeat/calendars, registry/aeat/legal). This works under
  editable install and under installed-wheel install identically.
- **Built-wheel manifest assertion.** A unit test that calls `uv build`
  into a temp directory, opens the resulting wheel as a zip, and
  asserts that every git-tracked path under `corpus/` and `registry/`
  is present in the archive at the expected `aeat/_data/...` prefix.
  This is the test that catches the silent class of regression where
  someone tweaks `pyproject.toml` and breaks bundling without breaking
  the dev loop. The test is slower (it shells out to the build
  backend) and should live in the unit suite gated by its own marker
  so contributors can opt out locally but CI runs it on every push.

Neither guard uses fakes, monkeypatching, or skips; both fail loudly
when the layout drifts.

### 9. Cross-references to prior decisions

The corpus-data-hydration ADR established *how* the trees are curated
(source lock-in to BOE/AEAT, review gate, JSON shape). It explicitly
did not address how the curated data reaches an installed package. The
real-PDF-fixture ADR established the on-disk PDF expectations for the
test suite, which is what makes shipping the allow-listed Renta PDFs a
hard requirement rather than a nice-to-have. The error-code-registry
ADR sits adjacent — the error registry is one of the TOML trees under
`registry/aeat` and shares the broken resolution pattern.

This research does not surface any prior decision touching the
`PROJECT_ROOT` walk in `core/config.py`. The hidden assumption that
the runtime always runs from a checkout has never been formally
acknowledged.

## Recommendation forward

The packaging ADR should:

1. Introduce `aeat/_data/` as the canonical bundled prefix and
   declare hatchling `force-include` as the shipping mechanism — no
   on-disk move of `corpus/` or `registry/` required.
2. Introduce `aeat.core.resources` as the single boundary that all
   call sites use to obtain a `Traversable` for a bundled subtree.
3. Migrate the three Settings fields (`aeat_manuals_root`,
   `aeat_normatives_root`, `aeat_vat_catalogue_root`) so their
   defaults resolve through the resource locator while preserving
   env-override semantics.
4. Migrate every `PROJECT_ROOT / "registry" / "aeat"` and
   `PROJECT_ROOT / "corpus" / ...` call site (production and test)
   to the resource locator. The migration can land in slices.
5. Add the two real-behaviour test guards (in-process and built-wheel)
   to lock the contract.
6. Acknowledge the PyPI 100 MB per-file default and capture the
   release-time decision tree (request a file-size grant vs trim the
   PDF surface vs publish only via a private index) without
   re-litigating the in-wheel scope.

The Plan phase should sequence (1) and (2) first because they unblock
the rest, then migrate Settings-mediated consumers, then the
PROJECT_ROOT hard-codes, then the tests, then the guards. The diff
will be wide (~120 files) but mechanical once the locator lands.
