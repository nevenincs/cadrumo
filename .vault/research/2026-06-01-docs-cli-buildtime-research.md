---
tags:
  - '#research'
  - '#docs-cli-buildtime'
date: '2026-06-01'
modified: '2026-06-01'
related: []
---



# `docs-cli-buildtime` research: build-time CLI reference extraction

The CLI reference under `docs/cli/` is produced by a bespoke generator
(`aeat.entrypoints.cli._doc_reference`) that walks the materialised Click
command tree, lifts each command's help, and writes fully-rendered RST pages
that are committed to the repository. A drift test asserts byte-for-byte
identity between the committed pages and a fresh in-memory regeneration. This
research evaluates replacing that generate-and-commit pipeline with a build-time
extraction that renders the reference live during the Sphinx build.

## Findings

### The help text already has a single source of truth

Command and option help is declared with `tr()` keys (for example
`help=tr("cli.config.auth.apoderado.help")`), resolved at module-import time
from the localisation catalogue. The generator already lifts those resolved
strings rather than authoring help by hand. The source of truth for help is the
English localisation catalogue, surfaced through `tr()`; nothing is hand-written
in the reference.

### The defect is commit-time rendering, not the help source

The reference is rendered once and the result is committed: `docs/cli/app.rst`
is roughly 100 KB and `config.rst` roughly 44 KB, with every help string frozen
into the file. The drift test then forces a regenerate-and-commit cycle on every
command or help change. This is asymmetric with the API reference, which is
build-time: the `docs/api/` stubs are thin `automodule` directives that autodoc
expands live from docstrings. The committed CLI snapshot can drift from the code
until the test catches it, and carries a permanent maintenance burden.

### Build-time extraction is feasible with the standard tooling

The industry-standard approach for a Click-based CLI is the `sphinx-click`
extension, which renders a Click command tree at build time. A spike confirmed
it renders this CLI: pointing the `click` directive at
`typer.main.get_command(app)` (the Click group materialised from the Typer app),
with `AEAT_OUTPUT_LANGUAGE=en` exported before any project import, produced the
full command tree with English help (the `app` and `config` families, ledger,
modelo, profile, and their leaf commands). No committed RST and no drift test
are required, because nothing is frozen.

Two constraints surfaced in the spike:

1. The `click` directive needs a Click object, so the Typer app must expose
   `typer.main.get_command(app)` as an importable attribute, and the build must
   pin the output language to English before importing the CLI.
2. Some `tr()` help strings contain reStructuredText-unsafe characters (stray
   backtick fences) that raise docutils errors when rendered. These strings need
   cleaning at the catalogue source, which also improves the live `--help`
   output.

### Project-specific annotations are out of scope for the user reference

The bespoke generator also emits per-command output-schema (envelope) notes,
registry keys, and a retired-surface redirect table. `sphinx-click` does not
produce these. They are developer-facing concerns rather than operator
reference, so the recommendation is to drop them from the user CLI reference and,
if still wanted, surface the schema mapping from the API/schema reference rather
than the command reference.

### Recommendation

Adopt build-time extraction with `sphinx-click`, pinning the output language to
English in the Sphinx configuration. Retire the bespoke generator, the committed
`docs/cli/` pages, and the drift test. Treat RST-unsafe help strings as a
localisation-catalogue fix. This removes the committed artifact, the drift
surface, and the regenerate-and-commit burden, and makes the CLI reference a
true build-time projection of the command tree and its localised help.
