---
tags:
  - '#adr'
  - '#docs-cli-buildtime'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-06-01-docs-cli-buildtime-research]]"
---



# `docs-cli-buildtime` adr: build-time CLI reference extraction | (**status:** `accepted`)

This decision supersedes decisions 1 and 2 of the CLI-documentation-conformance
ADR, which chose a bespoke generator over `sphinx-click` and committed the
rendered reference behind a byte-for-byte drift test. Those two decisions are
marked superseded by this ADR; the rest of that ADR (the accepted-surface
contract, the import-failure guard, English-only for this epic) is retained and
re-homed onto the build-time mechanism.

## Problem Statement

The CLI reference is rendered once by a bespoke generator and the result is
committed to the repository as fully-baked reStructuredText (roughly 100 KB for
the `app` family and 44 KB for `config`), guarded by a test that asserts the
committed pages match a fresh regeneration. Every command rename, every help
edit, and every localisation change forces a regenerate-and-commit cycle or the
gate fails. This is a standing maintenance burden and a live drift surface. It
is also asymmetric with the API reference, which is build-time: its stubs are
thin autodoc directives that render live from docstrings, so they cannot drift.
The CLI reference should be a build-time projection of the command tree and its
localised help, not a committed snapshot.

## Considerations

- The help text already has a single source of truth: command and option help
  are `tr()` keys resolved from the English localisation catalogue at import
  time. The reference must lift those resolved strings, never author help.
- The command tree lives in the source as a Typer application that wraps Click.
  `typer.main.get_command(app)` materialises the Click group the standard tools
  render.
- `sphinx-click` is the maintained, widely-used extension for documenting a
  Click command tree at build time. A spike confirmed it renders this CLI with
  English help once the output language is pinned before import.
- The prior ADR rejected `sphinx-click` to keep project-specific annotations
  (per-command output-schema envelopes, registry keys, a retired-surface
  redirect table). Those annotations are developer-facing, not operator
  reference, and are out of scope for a user CLI reference.

## Constraints

- No new third-party documentation dependency is added. The build reuses the
  project's existing flat renderer rather than `sphinx-click` (see the mechanism
  note in Implementation for why the standard extension was set aside).
- `tr()` resolves at module-import time, so the Sphinx build must export the
  English output-language setting before any project module is imported. The
  configuration sets it at the top of `docs/conf.py`.
- The build-time generation must run before Sphinx reads the source tree, so it
  is wired to the `builder-inited` event, and its output directory is gitignored.
- The accepted-surface and import-failure guarantees from the prior ADR are
  preserved: only accepted roots are documented, and a missing optional
  dependency makes the renderer raise (fail-closed) rather than emit a degraded
  reference.
- The flat renderer is unaffected by the command tree's depth, so the
  section-nesting limitation that ruled out `sphinx-click` does not apply, and no
  help-string sanitisation is required.

## Implementation

The CLI reference becomes a build-time surface generated fresh on every
documentation build and never committed. The Sphinx configuration exports the
English output-language setting at the top of the module, before any project
import, so `tr()` resolves to English for the whole build, and a
`builder-inited` hook renders the reference into a gitignored `docs/cli/`
directory before Sphinx reads the source tree. The committed pages and the
byte-for-byte drift test are retired; `docs/cli/` is gitignored.

**Mechanism note — `sphinx-click` was evaluated and set aside.** The first plan
was the standard `sphinx-click` extension rendering the materialised Click group
(`typer.main.get_command(app)`). A spike confirmed it renders this CLI, but it
emits a docutils section per command level, and the `aeat` command tree nests
six levels deep (for example `aeat app ledger inventory movement add`), which
exceeds docutils' section handling and raises "unexpected section title or
transition" under the nitpicky gate. Splitting per top-level family only reduced
the failures. The existing flat renderer already avoids this by documenting each
command as a single annotated entry rather than a deep section tree, and it
built green across the epic. The decision therefore keeps the flat rendering
logic but runs it at build time rather than at commit time: a build-time
projection that is regenerated every build and gitignored, which delivers the
same outcome (no committed artifact, no drift, lifted `tr()` help) without the
section-depth limitation.

Conformance shifts from "the committed pages match a regeneration" to "the build
renders the reference and the rendered reference covers every accepted surface":
the nitpicky build itself is the gate, and a focused test renders the reference
in a fresh English-pinned subprocess to a temporary directory and asserts it
covers the accepted roots, matches the schema registry, and carries no
import-failure fallback marker. No committed pages are consulted.

## Rationale

The research found that the help source was never the problem; the commit-time
rendering was. Build-time extraction removes the committed artifact, the drift
surface, and the regenerate-and-commit burden in one move, and it makes the CLI
reference symmetric with the API reference. The prior ADR's reason for a bespoke
generator, preserving developer-facing annotations, is outweighed by the
maintenance cost, and those annotations do not belong in an operator reference.
`sphinx-click` is the industry-standard mechanism, is mature, and was shown to
render this CLI.

## Consequences

- The committed `docs/cli/` snapshot, the generator module, and the drift test
  are deleted, removing a recurring maintenance task and a class of drift.
- The CLI reference can no longer go stale: it is regenerated on every build
  from the live command tree and the localised help.
- The build depends on importing the CLI under autodoc-like conditions, so a
  broken or dependency-missing command surfaces as a build failure rather than a
  silently degraded page. This is the intended fail-closed behaviour.
- The localisation catalogue must keep help strings reStructuredText-safe. This
  is a new, small discipline on help authoring, enforced by the build.
- Per-command output-schema and registry-key detail leaves the user reference.
  If a machine-contract surface is still wanted, it is documented separately
  from the operator command reference.

## Codification candidates

- **Rule slug:** `cli-docs-are-build-time`.
  **Rule:** The CLI reference is rendered at build time from the live command
  tree and the localised help, and `docs/cli/` is gitignored; never commit a
  pre-rendered CLI reference, and never hand-author command or option help in
  the documentation.
