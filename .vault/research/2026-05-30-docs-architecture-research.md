---
tags:
  - '#research'
  - '#docs-architecture'
date: '2026-05-30'
modified: '2026-05-30'
related: []
---



# `docs-architecture` research: `documentation surfaces landscape audit`

This research grounds a documentation epic for the `aeat` codebase. The
epic establishes governed documentation across distinct surfaces, makes
CLI documentation conformance programmatically guaranteed, and codifies
the codebase's documentation conventions in accepted ADRs. It was
produced by a six-axis read-only discovery sweep (Sphinx tooling, GitHub
user docs, documentation tests/conformance, CLI command surface, runtime
i18n, and prior documentation ADRs) plus primary-source reads of
`docs/conf.py`, `README.md`, and the prior docs ADR.

The headline finding: the documentation surface is **half-built and
un-governed**, not greenfield. A full Sphinx pipeline exists on disk with
no ADR backing it, the only accepted documentation ADR is now
contradicted by reality, and the documented build entrypoint does not
exist.

## Decided surface model

Documentation is partitioned into distinct surfaces, each with its own
audience, language posture, and source of truth. Truth is always
context-dependent and must be driven by codebase state — generated or
verified from the command tree, docstrings, the schema registry, and the
operator-surface contract, never hand-maintained in isolation.

| Surface | Audience | Language | Source of truth |
| :------ | :------- | :------- | :-------------- |
| GitHub repo docs (markdown) | General / non-technical operator | English only | Hand-authored, pinned by conformance test |
| Docstrings (in-source) | Technical / contributor | English only | Google-style docstrings under `src/aeat/` |
| Sphinx docs (generated) | Technical / contributor | English only | Autodoc over docstrings + narrative |
| User help / user-docs page (future, not yet implemented) | General operator | Multilang | Deferred; NOT driven by the CLI `tr()` ymls |

The CLI `--help` surface is a technical, runtime-only surface localized
by `tr()`; documentation generation and conformance do **not** reuse the
locale ymls as a docs translation source. The multilang user-help page is
a declared future surface; the immediate epic is English-first.

## Findings — Sphinx tooling

A complete Sphinx 8.1 pipeline is configured in `docs/conf.py`: `furo`
theme; extensions `sphinx.ext.autodoc`, `napoleon` (Google-style only),
`viewcode`, `intersphinx`, `sphinx_autodoc_typehints`,
`sphinx_markdown_builder`, `myst_parser`. `source_suffix` maps `.rst` to
restructuredtext and `.md` to markdown as first-class sources.
Presentation conventions: `autoclass_content='class'`,
`autodoc_typehints='description'`, `autodoc_typehints_format='short'`,
`add_module_names=False`, `member-order='bysource'`, plus an
`exclude-members` list suppressing pydantic/SQLAlchemy dunder noise.
Intersphinx maps five projects: python, pydantic, sqlalchemy, httpx,
typer; `intersphinx_disabled_reftypes=['std:doc']`. Autodoc imports the
package via `sys.path` insertion of `src/` (no installed wheel) plus an
`autodoc_mock_imports` allowlist for heavy native deps (tree_sitter,
qdrant_client, playwright, pikepdf, pdfplumber, ofxparse, openpyxl,
reportlab, argon2, keyring, anthropic).

147 hand-committed autodoc stubs live under `docs/api/*.rst`, regenerated
manually on module-rename landings (last refreshed in a W04/W05 rename
cluster). The markdown builder has been run manually into
`docs/_build/markdown/` (gitignored output).

The build is **internally inconsistent today**: `docs/index.rst`'s
toctree references `getting-started` and `architecture`, but both source
files were deleted in commit `09c9c26a6`. `conf.py`'s `exclude_patterns`
still names legacy narrative docs (`casillas.md`, `concepts/**`,
`coverage/**`, `error-codes.md`, `exit-codes.md`, `json-contract.md`,
`security-runbook.md`) that no longer exist on disk. There is **no
`just docs` recipe** despite a `pyproject.toml` comment claiming one, no
HTML build automation, and no `nitpicky` / `linkcheck` / `-W` enforcement
(`suppress_warnings=['myst.xref_missing']` actively silences MyST
cross-ref warnings).

## Findings — GitHub user docs

`README.md` is explicitly flagged OUT OF DATE in a top-of-file comment
and enumerates stale content (Cl@ve Móvil, sanitizer, reconciliation,
sede walker, fixture corpus). `CONTRIBUTING.md`, `RELEASING.md`,
`ROADMAP.md`, `CHANGELOG.md`, and `src/aeat/tests/README.md` exist and
are reasonably current. `docs/getting-started.md` and
`docs/architecture.md` referenced by README and by the toctree are
**absent**. There is no hand-authored bootstrap guide beyond the README
quick-start, and no multilang user docs.

## Findings — documentation tests & conformance

`interrogate` is configured (`fail-under=80`, with private/magic/nested/
test exclusions) but is **informational only** — no test or `just`
recipe enforces it. The single existing doc-conformance test is
`src/aeat/entrypoints/cli/test_root_help_shape.py`, which asserts the
curated help surface maps to real Typer command paths and that retired
surfaces are absent. There is no doctest runner, no Sphinx nitpicky/
linkcheck gate, no docstring-to-help sync check, and no build gate. The
prior pin `tests/test_docs.py` (from the docs-rewrite ADR) has been
**deleted**.

## Findings — CLI command surface

The CLI root is exactly two families — `config` and `app` — enforced by
the operator-surface contract `ACCEPTED_ROOTS`. The tree is ~**183 leaf
commands** four levels deep (e.g. `config auth apoderado scopes`,
`app ledger inventory movement`). All `help=` text is `tr('cli.*')` i18n
keys resolved against `src/aeat/locales/{es,en,ca,hu}.yml` — no raw
help strings.

There is a typed, machine-readable contract in
`src/aeat/application/operator_surface/`: `ACCEPTED_ROOTS`,
`MOUNTED_COMMAND_FAMILIES` (child name, operator question, service owner,
verb tuple, READ_ONLY / LOCAL_STATE_MUTATING mutability),
`RETIRED_OPERATOR_SURFACES` (14 retired roots with replacement +
suggestion + reason — some permanently retired with no redirect), and
curated `HelpDocument`/`HelpSection`/`HelpEntry` models. The `commands` tuples are curated summaries, not
exhaustive of the 183 leaves.

Structured output flows through a strict frozen `SchemaEnvelope`
(`{schema_version, command, result, warnings}`) and a process-global
`SCHEMA_REGISTRY` populated by `@register_schema('command path')` in
`src/aeat/core/json_contract.py`. That module's own docstring names "the
doc generator and the JSON-contract conformance tests" as registry
consumers — **the doc generator does not exist yet**. Envelope migration
is partial (~12 `modelo.work.*` commands in `MIGRATED_COMMANDS`; the rest
emit bare payloads).

Command-tree introspection must materialize the Click command
(`typer.main.get_command(app)`) and use Click `get_command`/
`list_commands` to force lazy subtree loading; `registered_groups` is
incomplete due to lazy loading. Existing tests already use this exact
pattern (`test_apex_workflow_verification.py`,
`test_root_grammar_invariants.py`, `test_lazy_command_tree.py`,
`src/aeat/tests/cli_runner.py`) — the conformance backbone to extend
from contract-vs-tree to docs-vs-tree.

## Findings — runtime i18n

Runtime translation is a custom mechanism in `src/aeat/core/i18n/`
(`tr`, `Translatable`, `output_language`) reading four flat-nested YAML
catalogues under `src/aeat/locales/` (note: under `src/aeat/`, not
repo-root). `SUPPORTED_OUTPUT_LANGUAGES=('es','en','ca','hu')`,
`DEFAULT_OUTPUT_LANGUAGE='es'`. The hot path is a custom lru-cached
flat-dict reader; `python-i18n` is a lazy fallback only. Language
precedence: explicit `Settings.aeat_output_language` (flag / env / .env)
> active-profile language > default `es`. Catalogue completeness is gated
by a `LocaleManager` audit/scaffold flow, a duplicate-key guard, AST +
regex key scanners, and `_intentional_identical.json` with per-language
untranslated ceilings (ca 158, hu 118).

Sphinx docs have **zero** multilang wiring: `language='en'`, no
`locale_dirs`, no gettext builder, no `sphinx-intl` / babel dependency.
The trilingual-i18n ADR is **stale**: it scopes es/en/hu and explicitly
rejects gettext/.po for runtime data, while the implementation ships four
languages including Catalan via custom YAML; Catalan is authorized by no
ADR.

## Findings — prior documentation ADRs

The only documentation-focused ADR is `2026-04-12-docs-rewrite-adr`
(status: accepted). It scoped documentation-only markdown work
(`README.md` rewrite, `docs/getting-started.md`, `docs/architecture.md`,
and a `tests/test_docs.py` smoke test) and **explicitly deferred** "API
docs (sphinx/mkdocs/pdoc), docs site, translations". Its decisions have
drifted: the smoke test is deleted and both narrative pages are gone. The
on-disk Sphinx tree directly contradicts its scope statement, so it is
stale-in-practice while nominally accepted and needs explicit
supersession.

Two adjacent accepted ADRs constrain the epic: `relative-imports-adr`
(relative imports inside `src/aeat/`, enforced by Ruff; this is why
autodoc resolves via `sys.path` + mock-imports) and
`json-output-contract-adr` (the `--json` flag, `SCHEMA_REGISTRY`,
eleven-entry exit-code table, TTY contract that CLI docs must reflect).
The Google-style docstring + Sphinx cross-reference convention is
implied only by `conf.py` and a `pyproject.toml` comment — codified in no
ADR.

## Gaps to close

- No `just docs` build entrypoint; the documented one does not exist.
- `docs/index.rst` toctree and `conf.py` exclusions reference deleted
  files; the build is inconsistent.
- No Sphinx build / linkcheck / nitpicky conformance gate.
- No programmatic CLI-doc generator or docs-vs-tree conformance test,
  despite the contract and registry being ready to drive one.
- `interrogate` docstring-coverage gate is unenforced.
- No accepted ADR governs the Sphinx pipeline, the docstring conventions,
  or the docs language posture.
- The docs-rewrite ADR needs supersession to resolve the authority
  conflict.

## Conventions to codify in ADRs

- The surface model above (audience / language / source of truth), with
  codebase-state-as-truth as the governing principle.
- Google-style docstrings with Sphinx cross-reference and module-linking
  syntax as the in-source authoring convention.
- `docs/` as the Sphinx source root; `docs/api/` autodoc stubs;
  markdown-builder + HTML dual output; intersphinx baseline and the
  semantic cross-linking / module-linking standard.
- Autodoc import strategy (`sys.path` + `autodoc_mock_imports`) tied to
  the relative-imports constraint.
- CLI-doc conformance driven by the materialized Click tree +
  operator-surface contract + `SCHEMA_REGISTRY` + exit-code table, using
  the existing tree-walk test pattern.
- An editorial / review workflow for documentation changes and the
  conformance gates that pin each surface.

## Conformance enforcement model

"Appropriate and true-to-reality documentation" decomposes into four
distinct guarantees, each needing its own mechanism; no single tool
delivers all four. Presence is not accuracy, accuracy is not style, and
none of those is link validity.

| Guarantee | Catches | Tool | Gate layer |
| :-------- | :------ | :--- | :--------- |
| Presence (module + public symbols) | missing docstring | `ruff` D-rules (`D100`/`D101`/`D103`/`D104`) + `interrogate` coverage | lint (fast, hard) |
| Style (Google-style sections) | wrong/absent sections, non-imperative summary | `ruff` pydocstyle `convention="google"` | lint |
| True-to-reality at symbol level | documented args/returns/raises mismatching the signature | `pydoclint --style=google` (`DOC*` codes) | lint |
| True-to-reality at module-file level | undocumented module or orphan stub | custom module-tree to API-stub correspondence test | test |
| Link validity & display | broken `:class:`/`:func:`/`:mod:` cross-refs, malformed directives | `sphinx-build -n -W --keep-going` (nitpicky + warnings-as-errors) | build/test |
| External URL validity | dead URLs, stale intersphinx | `sphinx-build -b linkcheck` | build |
| RST/MyST formatting | line-length, malformed RST | `doc8` / `rstcheck` | build/lint |

The canonical link gate is
`sphinx-build -b html -n -W --keep-going docs docs/_build/html`, wrapped
as a pytest test (shell `sphinx-build`, assert exit 0) so it lives in the
suite, plus the missing `just docs` / `just docs-check` recipes.

Module-file-level coverage is gated by `ruff` `D100` (missing module
docstring) and `D104` (missing package `__init__` docstring) as a pure,
fast lint gate, with `interrogate` as the public-symbol coverage ratchet.

Tools to add to dev dependencies: `pydoclint`, `doc8` (or `rstcheck`),
and `interrogate` (its `[tool.interrogate]` config exists in
`pyproject.toml` but the tool is not a declared dependency). `ruff` and
`sphinx` are already present — `ruff` only needs the `D` ruleset +
`convention="google"`, `sphinx` only needs `-n -W` + a `linkcheck`
recipe and removal of the warning suppression.

## Decided: hard-cut full enforcement from day one

Enforcement is hard-cut, not phased: the full `ruff` `D` ruleset,
`pydoclint` signature-matching, `interrogate` coverage, and the Sphinx
`-n -W` nitpicky build gate are all enabled at once, with no baselines,
ratchets, or per-file skips. This guarantees conformance from the first
landing and matches the repository's standing prohibition on lint skips
and its "retire means delete fully" posture.

Two consequences follow and constrain the epic plan. First, two settings
in `docs/conf.py` currently hide the defects the gates must catch —
`suppress_warnings=['myst.xref_missing']` and the broad
`autodoc_mock_imports` list — so the gate cannot be meaningful until the
suppression is removed and a curated `nitpick_ignore` /
`nitpick_ignore_regex` baseline covers the legitimately-external and
mock-imported types. Establishing that nitpick baseline is a design task,
not a skip. Second, a hard cut means the gates and a full-tree
remediation must land together: a green build is a merge precondition, so
the epic must include a remediation wave that brings every module to a
true-to-reality module docstring, every public symbol to a
signature-matching Google docstring, and the Sphinx build to `-n -W`
clean before the gates are switched on. That remediation is large but
parallelizable.

## Implications for the ADR slate

Three ADRs follow from this research: (1) a documentation surface
taxonomy & conventions ADR that supersedes the docs-rewrite ADR; (2) a
Sphinx documentation architecture ADR (English-only now, with a declared
seam for the future multilang user-help page); (3) a CLI documentation
conformance ADR. The L4 epic plan sequences scaffolding, conformance
harness, user-doc rewrite, and the editorial workflow on top of the
accepted ADRs.
