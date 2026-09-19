---
tags:
  - '#research'
  - '#dev-harness-bleed'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ba5548d9cf2a1a0976810a322021e9faa931d9813e6e9c00b46563f96138e711'
related:
  - "[[2026-06-14-docs-tooling-separation-research]]"
---

# `dev-harness-bleed` research: `dev/CI tooling shipped inside src/cadrumo: verified inventory`

## Findings

### `src/cadrumo/locales/` is a mixed package

Runtime-resident data (five files, loaded by the renderer, never touched by this
research): `en.yml`, `es.yml`, `ca.yml`, `hu.yml` and `_intentional_identical.json`.
Two independent runtime load paths resolve them through
`importlib.resources.files(PRODUCT_IDENTITY.python_package).joinpath("locales", ...)`:
`src/cadrumo/core/i18n/_render.py:128` (registers the `locales` directory on the
i18n load path) and `:491` inside `_packaged_locale_map` (reads one catalogue's
bytes for the cache-digest path).

Dev/CI catalogue-maintenance tooling with no runtime importer (seven modules,
their package facade, and six tests): `manager.py`, `_ast_scanner.py`,
`_registry_scanner.py`, `_fstring_registry.py`, `_status.py`, `cli.py`,
`__main__.py`, `__init__.py` (re-exports only tooling symbols, confirmed by
reading `locales/__init__.py:19-46`, which imports exclusively from the seven
tooling modules, never from a `.yml` file), and the six tests under
`locales/tests/`: `test_allow_identical.py`, `test_audit.py`,
`test_dynamic_prefix_registry_coverage.py`, `test_status.py`,
`test_ternary_tr_argument_discovery.py`, `test_tr_constant_naming_convention.py`.

### The tooling scans the source tree and localises itself

`LocaleManager.get_codebase_keys()` walks `self.src_dir.rglob("*.py")` at
`manager.py:198`, where `src_dir` is `src/cadrumo` (constructed in `cli.py`'s
`_default_manager()` as `locales_dir.parent`), the scan root is `src` only,
never `dev`.

`locales/cli.py` makes 26 `tr()` calls localising its own operator-facing
output (counted by literal occurrence of `tr(` in the file at HEAD). Every
`cli.locales.*` / `locales.cli.*` key those calls reference resolves in all
four shipped catalogues, confirmed by grepping each catalogue for a top-level
`locales:` block (`en.yml`, `es.yml`, `ca.yml`, `hu.yml` each carry exactly one,
`es.yml` at line 7031). Because the scanner's root is `src` and the CLI's own
keys live inside `src/cadrumo/locales/cli.py`, moving `cli.py` out of `src`
removes the only site the scanner sees these keys at, and the parity gate
(`locales/manager.py:229` `audit()`, driven by `locales/cli.py:30` `audit`
command and exercised tree-wide by `tests/test_parity.py`) would report them
orphaned (`codebase_extra`) the next time it runs.

### Import consumers, verified individually

Six files across four subpackages import the tooling by a real Python import
(not a string literal, not a docstring cross-reference, not a resource-path
lookup):

- `src/cadrumo/tests/test_registry_locale_key_parity.py:26-27`:
  `from ..locales import scan_registry_keys` and
  `from ..locales.manager import LocaleManager`.
- `src/cadrumo/tests/test_parity.py:8,12,13`: imports the `locales` facade,
  `locales.cli.app`, and `LocaleError`/`LocaleManager`/`LocaleNode` from
  `locales.manager`; four more `from ..locales import get_registered_keys`
  imports recur inside test bodies at `:783,797,814,838,864`. This module also
  pins a logger name at `:585`:
  `caplog.set_level(logging.DEBUG, logger="cadrumo.locales._ast_scanner")`,
  a string coupling to the tooling's dotted module path, independent of any
  `import` statement, that a move breaks silently (no import error, the log
  capture simply stops matching anything).
- `src/cadrumo/tests/test_locale_translation_honesty.py:152`:
  `from ..locales import RESERVED_INTERPOLATION_TOKENS`. This is the tree-wide
  translation-honesty gate; its docstring at `:26` also cross-references
  `cadrumo.locales._status` by dotted name (prose, not a second import).
- `src/cadrumo/application/operator_surface/tests/test_contract.py:41`:
  `from ....locales import LocaleManager`.
- `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py:73`:
  `from ....locales.manager import LocaleManager, LocaleNode`. (The module's
  docstring mentions the mandated `python -m cadrumo.locales set` command in
  prose at `:47`; the import itself is at `:73`.)
- `src/cadrumo/adapters/persistence/storage/tests/test_hardening_convention_guards.py:13`:
  `from .....locales.manager import LocaleManager`. This is a five-dot relative
  import reaching a private submodule across a package boundary
  (`adapters.persistence.storage` importing from `locales`). Ownership of
  `locales.manager` is `locales`, and the public facade `locales/__init__.py`
  already re-exports `LocaleManager` at line 36, so the site should import
  `from ......locales import LocaleManager` regardless of any relocation
  decision. Recording this precisely because it is an
  `aeat-architecture-boundaries` facade violation on its own terms, standing
  whatever this ADR decides about relocating the tooling.

Grouped by subpackage: three files under `src/cadrumo/tests/` (the tree-wide
parity, registry-key-parity and translation-honesty gates), one under
`application/operator_surface/tests/`, one under `entrypoints/cli/tests/`, and
one under `adapters/persistence/storage/tests/` (the facade-violating import).
The first five are legitimate cross-domain consumers of the tooling as a
general-purpose key-inventory utility; the sixth is the independent facade
defect above.

### Four consumers reference only data or literal text, not code

These are unaffected by a code relocation because they never import a tooling
module:

- `src/cadrumo/application/export/tests/test_tabular.py:176` resolves the
  catalogue directory via `importlib.resources.files("cadrumo.locales")`
  and reads a `.yml` file directly, a data-path lookup, not a code import.
- `src/cadrumo/tests/test_locale_coverage_inventory.py:94`,
  `test_locale_coverage_hardened_errors.py:84` and
  `application/wizard/tests/test_flow_description_keys.py:39` each embed the
  literal instruction string "python -m cadrumo.locales set" inside an
  assertion failure message, human-readable guidance text, not a call site.
  If the mandated invocation path changes, these three literal strings go
  stale as documentation, not as code; they do not break on import.

### The dead central error-registry entry

`src/cadrumo/core/errors/registry/_core.py:451` registers the string
`"cadrumo.locales.manager.LocaleError"` against
`ErrorCode(code="FAIL_LOCALE_MANAGER", message_key="errors.fail.fail_locale_manager", ...)`.
`LocaleError` is defined in `locales/manager.py:66` and is raised only inside
`locales/manager.py` and `locales/cli.py` (confirmed by grepping the tree for
`raise LocaleError` and `LocaleError(` outside those two files: zero hits in
production code). No operator-facing command reaches it, and no production
module imports `LocaleError`. Because the registry keys on a string qualname
rather than an import, a relocation that changes the dotted path breaks this
entry silently, no `ImportError`, just a permanently dangling key that never
matches any raised exception again.

### Packaging needs zero edits

`pyproject.toml`'s `[tool.hatch.build.targets.wheel]` ships `src/cadrumo` as a
single package entry (`packages = ["src/cadrumo"]`) with no per-module include
or exclude naming any of the seven tooling modules; the only wheel excludes are
`**/tests/**` and the corpus source-binary globs. A relocation changes nothing
in `pyproject.toml`.

### Completeness: this is the sole dev-harness-in-src instance of this shape

A tree-wide search for `typer.Typer(` / `import click` / `import argparse`
across `src/cadrumo` (excluding `entrypoints/cli/` and its tests) returns
exactly one standalone CLI application: `locales/cli.py`. Every other hit is
either inside `entrypoints/cli/` itself, is `application/wizard/_commands.py`
(which builds Typer `Command` objects that `entrypoints/cli` mounts, part of
the product surface, not a standalone app), or is `core/click_context.py` (a
context-propagation utility, not an app). A tree-wide search for `__main__.py`
files under `src/cadrumo` returns exactly one: `locales/__main__.py`. Both
confirm the ADR's completeness claim rather than merely repeating it.

### The second, distinct dev-bleed instance

`src/cadrumo/application/wizard/_translations.py` (`audit_wizard_translations`,
`audit_cli_translations`, `cli_keys_referenced_in_source`) has zero production
importers anywhere in the tree, verified by grepping the whole tree for
`_translations` imports outside its own two test files
(`application/wizard/tests/test_wizard_translations_resolve.py`,
`test_translations_helpers.py`) and by reading `application/wizard/__init__.py`,
which re-exports none of these three names. Its `cli_keys_referenced_in_source()`
(`_translations.py:105-127`) independently `rglob`s `entrypoints/cli/*.py` for
`cli.*` `tr()`-literal keys, the same "walk src for `tr()` keys" concern
`locales/manager.py`'s regex scanner already covers for the whole tree,
reimplemented narrower and in a different package. It defines no CLI, exports
no `Typer` app, and is not itself named in this ADR's decision; it is recorded
here, and in the ADR's Out of scope section, so the completeness claim (this
is the sole dev-harness-in-src instance of this shape) is honest about the
one instance that has a different shape (a scanner-and-audit pair with no CLI
at all, versus `locales/`'s full scanner-scaffold-CLI stack).

### Same-commit carry facts, verified

- Autodoc stubs: `docs/api/` carries eight stubs matching
  `cadrumo.locales*.rst`: `cadrumo.locales.rst` (the package itself),
  `cadrumo.locales.cli.rst`, `cadrumo.locales.manager.rst`,
  `cadrumo.locales.__main__.rst`, `cadrumo.locales._ast_scanner.rst`,
  `cadrumo.locales._fstring_registry.rst`, `cadrumo.locales._registry_scanner.rst`
  and `cadrumo.locales._status.rst`.
- Coverage allowlist: `src/cadrumo/tests/test_every_module_has_test_coverage.py:80-81`
  exempts `"src/cadrumo/locales/__main__.py"` with the comment "locales/__main__
  dispatches into locales/cli.py", confirmed live at HEAD (a neighbouring
  docstring at `:363-366` records that an earlier, already-corrected version of
  this same allowlist entry named a nonexistent `locales/scaffold.py`, which is
  history, not a current defect).
- Literal invocation strings outside `src/cadrumo/locales/`:
  `dev/registry/newmodelo/manager.py:130-131` embeds two `python -m
  cadrumo.locales set es ...` lines inside a scaffolded TOML comment template;
  `dev/registry/newmodelo/checklist.py:40,120` embeds the same command in
  checklist prose twice. `src/cadrumo/tests/test_registry_locale_key_parity.py:78-79`
  and `:128` (assertion-failure text, not a call site) and
  `src/cadrumo/tests/test_locale_translation_honesty.py:229` and `:250`
  (likewise) all cite `python -m cadrumo.locales scaffold`/`set` in
  human-readable failure guidance.

## Sources

- `src/cadrumo/locales/manager.py`, `_ast_scanner.py`, `_registry_scanner.py`,
  `_fstring_registry.py`, `_status.py`, `cli.py`, `__main__.py`, `__init__.py`,
  read in full at HEAD.
- `src/cadrumo/core/i18n/_render.py:120-135,485-495`, the two runtime catalogue
  load paths.
- `src/cadrumo/core/errors/registry/_core.py:440-460`, the dead
  `FAIL_LOCALE_MANAGER` entry.
- `src/cadrumo/tests/test_parity.py`, `test_registry_locale_key_parity.py`,
  `test_locale_translation_honesty.py`, `test_every_module_has_test_coverage.py`,
  grepped and spot-read for the exact line numbers cited above.
- `src/cadrumo/application/operator_surface/tests/test_contract.py`,
  `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`,
  `src/cadrumo/adapters/persistence/storage/tests/test_hardening_convention_guards.py`,
  read for their exact import lines.
- `src/cadrumo/application/export/tests/test_tabular.py`,
  `src/cadrumo/tests/test_locale_coverage_inventory.py`,
  `test_locale_coverage_hardened_errors.py`,
  `src/cadrumo/application/wizard/tests/test_flow_description_keys.py`, read
  to confirm each is a data/literal-text consumer, not a code import.
- `src/cadrumo/application/wizard/_translations.py` and
  `application/wizard/__init__.py`, read in full; tree-wide grep for
  `_translations` imports found only its own two test files.
- `pyproject.toml`, `[tool.hatch.build.targets.wheel]` section, read at HEAD.
- `docs/api/cadrumo.locales*.rst`, enumerated via directory listing.
- `dev/registry/newmodelo/manager.py`, `checklist.py`, grepped and spot-read.
- `.vault/adr/2026-06-14-docs-tooling-separation-adr.md`, the accepted
  precedent this ADR follows in shape.
- `.vault/adr/2026-08-07-dev-harness-bleed-adr.md`, the accepted decision this
  research grounds.
