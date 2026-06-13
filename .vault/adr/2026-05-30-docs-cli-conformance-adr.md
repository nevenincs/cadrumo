---
tags:
  - '#adr'
  - '#docs-cli-conformance'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-30-docs-architecture-research]]"
  - "[[2026-05-30-docs-architecture-adr]]"
  - "[[2026-05-30-docs-sphinx-build-adr]]"
  - "[[2026-04-25-json-output-contract-adr]]"
  - '[[2026-06-04-docs-cli-conformance-research]]'
---



# `docs-cli-conformance` adr: `cli documentation conformance` | (**status:** `partially superseded`)

> **Decisions 1 and 2 are superseded** by the build-time CLI reference
> extraction ADR (`2026-06-01-docs-cli-buildtime-adr`). The choice of a bespoke
> generator over `sphinx-click` (decision 1) and the committed,
> drift-tested generated pages (decision 2) are replaced by a build-time
> `sphinx-click` projection of the live command tree. The accepted-surface
> contract, the import-failure guard, and the English-only scope from the rest
> of this ADR are retained and re-homed onto the build-time mechanism.

This is the third of three ADRs in the documentation epic. It builds on
the surface taxonomy and conventions ADR (codebase-state-as-truth; the
docstring gates) and the Sphinx build architecture ADR (the `-n -W` build
gate and the colocated-test placement). It governs the one surface those
two deliberately fenced out: the operator-facing CLI reference and its
programmatic conformance to the live command surface.

## Problem Statement

The CLI is the project's primary operator surface — two command families
(`config`, `app`) over roughly 183 leaf commands, four levels deep — yet
none of it is documented in a way that is guaranteed to match reality.
Today the only CLI documentation is the inline `--help` text and a single
help-shape test; the `aeat.entrypoints` autodoc stub renders the package,
not the command tree, its options, or its output contracts. The epic's
charter requires that conformance be programmatically guaranteed for ALL
CLI documentation. Three properties of the CLI make naive approaches
fail: the command tree is composed lazily (registered groups are
incomplete until each subtree's module is imported), help text is sourced
from `tr()` localization keys rather than literals, and structured output
flows through a `SchemaEnvelope` recorded in a process-global
`SCHEMA_REGISTRY` whose own docstring already anticipates a "doc
generator" consumer that does not exist.

This ADR decides how the CLI reference is produced from codebase state and
how its conformance to the live tree, the accepted-surface contract, and
the output schema registry is enforced by tests — so that a command added,
renamed, retired, or re-shaped cannot drift from its documentation.

## Considerations

- **The command tree must be materialized to be enumerated.** Lazy
  subcommand loading means `typer.main.get_command(app)` plus Click
  `get_command`/`list_commands` walking is required to force every subtree
  to import; the registered-groups view is incomplete. Existing tests
  already use exactly this pattern, so the generator and the conformance
  test share a proven traversal.
- **A typed accepted-surface contract already exists.** The
  `operator_surface` package declares `ACCEPTED_ROOTS`,
  `MOUNTED_COMMAND_FAMILIES`, and `RETIRED_OPERATOR_SURFACES`, and curated
  `HelpDocument` models. It is the authority for which roots/families are
  accepted and which are retired — but its per-family `commands` tuples
  are curated summaries, not an exhaustive enumeration of the ~183 leaves,
  so completeness checking must walk the real tree rather than trust the
  contract's tuples.
- **Help text is localized at definition time.** Every `help=` is a
  `tr('cli.*')` key resolved against the locale catalogue when the module
  loads, so rendering the reference in a given language means controlling
  the active output language for the generation pass.
- **Structured output is registry-backed but partially migrated, on two
  distinct fronts.** `SCHEMA_REGISTRY` (`@register_schema`) records each
  registered command's `SchemaEnvelope`; the json-output-contract ADR
  defines the envelope, an eleven-entry exit-code table, and the TTY
  contract. Roughly 22 schemas are registered today across `modelo.*` and
  `review.*`, but only the 12 `modelo.work.*` commands in the
  `MIGRATED_COMMANDS` allow-list are envelope-conformance-gated; most of
  the ~183 leaves still emit a bare payload. The json-output-contract ADR
  is itself Phase-1 — the root `--json` wiring and per-command exit-code
  specialization are deferred. Any per-command output documentation must
  reflect this real, partial state rather than claim uniform coverage.
- **The Sphinx build owns the rendering gate.** The build architecture ADR
  established the `-n -W` nitpicky gate, the colocated-test placement, and
  the committed-stub-plus-drift-test precedent; the CLI reference is
  another generated surface that plugs into that machinery rather than a
  parallel pipeline.

## Constraints

- **English-only for this epic.** The CLI reference is rendered in English
  (output language forced to `en` for the generation pass). Per-locale
  CLI documentation is the deferred multilang user-help surface named in
  the conventions ADR and is explicitly out of scope; this ADR must not
  reuse the locale ymls to emit multilang docs.
- **Codebase-state-as-truth.** The reference is generated from the
  materialized tree, the `operator_surface` contract, and
  `SCHEMA_REGISTRY` — never hand-maintained.
- **Honesty about partial migration.** The conformance gate documents the
  actual per-command output shape (envelope vs bare payload); it does not
  assert a uniform `--json` contract that does not yet exist, and it must
  not become tautological by asserting only what it generated.
- **Inherited gates.** The CLI reference is subject to the conventions
  ADR's docstring gates (command callbacks are public symbols) and the
  Sphinx build ADR's `-n -W` link gate; this ADR adds CLI-specific
  conformance on top, not a replacement.
- **Placement under `src/aeat/`.** Conformance tests are colocated (beside
  the existing CLI invariant tests under `src/aeat/entrypoints/cli/`),
  never in a top-level `tests/` package.

## Implementation

This ADR decides the following.

**1. The CLI reference is generated, not hand-written, and not
`sphinx-click`.** A project doc-generator walks the materialized Click
tree (`typer.main.get_command(app)` then recursive
`get_command`/`list_commands`, forcing lazy imports) and emits a
per-command reference (name, full path, help, options/arguments, and —
where registered — the output schema). `sphinx-click` is rejected because
it does not account for the lazy composition, the `tr()`-sourced help, or
the `operator_surface` curation; the bespoke generator reuses the
traversal the tests already prove. This is the `SCHEMA_REGISTRY` consumer
the json-contract module anticipated.

**2. Generated reference is committed and drift-tested, mirroring the API
stubs.** The generated CLI reference pages live under the `docs/` tree
(see decision 7 for the path) and are committed; a colocated test
regenerates them and asserts the committed output matches, so a drift
fails the gate. This generated-vs-committed comparison is a *consistency*
gate (intentionally circular), distinct from the correctness gates in
decisions 3 and 4. Because regeneration materializes the full command tree
and the registry (a multi-second import), this test carries the same
fast-lane-exclusion marker the build architecture ADR gave the
`sphinx-build` test, and runs in `just docs-check` / CI. Generation
happens at test/generation time, not during `sphinx-build`, so the Sphinx
build stays hermetic.

**3. Docs-versus-tree conformance test.** A colocated test asserts, by
walking the materialized tree: (a) every documented command path resolves
to a real command in the live tree; (b) every non-retired command in the
live tree is present in the reference (completeness — walked from the real
tree, not the curated `commands` tuples); (c) no `RETIRED_OPERATOR_SURFACES`
entry appears as a live or documented command, and retired surfaces are
represented only by their redirect suggestion. This extends the existing
accepted-surface and grammar-invariant tests from contract-versus-tree to
docs-versus-tree.

**4. Per-command machine-contract documentation, honest about migration.**
The reference documents the global flags, the eleven-entry exit-code
table, and the TTY contract from the json-output-contract ADR as the
*global* contract (these are stable), and — for commands present in
`SCHEMA_REGISTRY` — the `SchemaEnvelope` shape. A conformance test asserts
that every registered schema (today ~22 across `modelo.*` and `review.*`)
corresponds to a real command path and that the documented shape matches
the registered schema. Because the json-output-contract ADR is Phase-1,
the reference flags that per-command `--json` adoption and exit-code
specialization track the same migration front — only the 12
`MIGRATED_COMMANDS` are envelope-gated; the rest are documented as
emitting the bare payload. The gate's independence (non-tautology) comes
from decision 3(b) completeness and this registry check sourcing truth
from the live tree and the registry — two sources independent of the
generated reference — not from the decision-2 drift comparison, which is
a separate consistency check.

**5. English rendering, language pinned before the first CLI import.**
Help strings are `tr()` values resolved at module-import time and stored
as plain strings on the Typer objects, so the output language must be
pinned to `en` *before* any CLI command module is imported — overriding
after import has no retroactive effect. The generator therefore forces
`en` under one of two operational contracts: either a fresh subprocess
with `AEAT_OUTPUT_LANGUAGE=en` in the environment (the clean guarantee,
mirroring the existing lazy-tree subprocess test), or entering the
settings override, clearing the output-language cache, and asserting that
no `aeat.entrypoints.cli` command module is already imported, *then*
materializing the tree. The reference notes the commands are localized at
runtime, but rendering it per-locale is the deferred multilang surface and
is not built here.

**6. The `operator_surface` contract is the accepted-surface authority.**
The reference documents only accepted roots and families; the two-family
(`config`, `app`) invariant is asserted, consistent with the existing
grammar-invariant tests. Retired surfaces are presented by their redirect
suggestion where one exists; a permanently-retired surface with no
replacement or suggestion (for example live submission) is documented as
permanently removed with no redirect, never given an invented one.

**7. Generator placement, reference location, and degraded-surface
guard.** The generator is importable production code under `src/aeat/`
(beside the CLI surface it introspects) and is therefore subject to the
conventions ADR's docstring gates like any other module. The generated
reference lives in a dedicated `docs/cli/` subtree attached to
`index.rst`; because a CLI reference page is not a module autodoc stub, it
is explicitly excluded from the build architecture ADR's module-to-stub
correspondence set so it is not flagged as an orphan. The generator runs
in a full-dependency environment and asserts that no subtree was replaced
by the CLI's import-failure fallback, so a missing optional dependency
reds the gate rather than silently emitting a degraded reference.

## Rationale

Generating the reference from the materialized tree is the only approach
that can honor codebase-state-as-truth for a lazily-composed,
`tr()`-localized, registry-backed CLI: any hand-written or `sphinx-click`
reference would silently drift the moment a command moved, because neither
sees the lazy subtrees or the curation layer. Reusing the traversal the
invariant tests already rely on means the generator and its conformance
gate share one proven mechanism rather than two divergent ones.

Committing the generated reference and drift-testing it (rather than
generating during `sphinx-build`) keeps the Sphinx build hermetic — a
property the build architecture ADR went to some length to secure — and
mirrors the API-stub precedent so contributors have one mental model for
"generated, committed, drift-gated" docs.

Documenting the output contract honestly about partial migration avoids
the trap of a tautological or false gate: the epic's value is that docs
match reality, and reality is that most commands still emit a bare
payload. A gate that asserted a uniform `--json` envelope would be
documenting an aspiration, not the code.

Keeping the reference English-only with the multilang rendering deferred
honors the epic's scope and the conventions ADR's explicit constraint that
the CLI locale ymls are not a documentation translation source.

## Consequences

- **A new doc-generator and its tests are built and maintained.** The
  generator (tree walk plus registry read) and three colocated tests
  (drift, docs-versus-tree, schema-conformance) are new code under
  `src/aeat/`, exercised by the suite and by `just docs-check`.
- **The generated reference must be regenerated on CLI changes.** Adding,
  renaming, or retiring a command requires regenerating the committed
  reference in the same change, or the drift test fails — the intended
  forcing function.
- **Output-contract documentation tracks the migration.** As more commands
  adopt the `SchemaEnvelope`, the reference and its schema-conformance gate
  reflect the growing coverage automatically; the partial state is
  documented truthfully in the interim rather than hidden.
- **CLI reference docstring obligations join the hard cut.** Command
  callbacks are public symbols, so the conventions ADR's `ruff`/`pydoclint`
  gates apply to them; the remediation wave includes the CLI modules.
- **Multilang CLI documentation has a named, deferred home.** Per-locale
  rendering is explicitly future work tied to the multilang user-help
  surface, with the constraint that it not be driven by the runtime CLI
  locale ymls.
- **The epic's three ADRs now cover all in-scope surfaces.** Conventions
  and the surface model (first ADR), the Sphinx build and API surface
  (second ADR), and the CLI reference and its conformance (this ADR)
  together let the L4 plan sequence scaffolding, the generators and gates,
  and the full-tree remediation wave.
