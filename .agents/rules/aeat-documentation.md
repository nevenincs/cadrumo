---
name: aeat-documentation
trigger: always_on
---

# AEAT documentation, terminology and shipped search

## User-facing language

Write user-facing documentation in simplistic, singular, imperative instruction
steps. This keeps documentation clear, prevents technical detours, and optimizes
token usage.

- **Good:** "Create taxpayer profile." / "Import bank statement." / "Run
  calculation."
- **Bad:** "We will now set up the taxpayer profiles." / "Let's import our
  transactions." / "Running the calculations."

Do not present every option at once; walk through concrete scenarios step by
step. Use general terminology (NIF, CIF, DNI, NIE, NII) rather than naming a
single taxpayer group. Guide the reader from profile setup and transaction import
through calculation and reconciliation, cross-linking so complex topics arrive
gradually. Keep descriptions objective — no self-congratulatory phrasing.

## Workflow

Every documentation change follows the `vaultspec-documentation` lifecycle:
wireframe, refinement, approval; then context gathering and isolated
section-by-section drafting; then technical review (cross-referencing the
codebase and conformance gates) and editorial review; then final approval.

A *researcher* gathers codebase context, help output and CLI structures without
writing draft files; an *author* writes the pages using only that research; an
*editor* reviews for a newcomer's clarity, tone and link integrity. **Final
wording and approval stay with the main session** — never delegate final
documentation prose to a subagent.

Verify with `pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`
and the nitpicky Sphinx build gate `pytest dev/docs/tests/test_docs_build.py`.
Chat responses use absolute `file://` links with forward slashes; user-facing
docs use relative markdown links.

## The generated API reference is CLI-owned

Maintain it with `python -m dev.docs.apidocs scaffold`; never hand-author or
hand-edit the `docs/api/*.rst` stubs. Run `scaffold` after any change to the
`src/cadrumo/` module tree — especially a relocation, rename or deletion — and
land the regenerated stubs in the same commit. Use `scaffold --check` as the
drift gate and `audit` for a health report.

The stubs are generated from the module tree, and the nitpicky `-n -W` build
imports every stubbed module: a stub left for a deleted module is an *orphan*
that hard-crashes autodoc, and a module added without a stub silently drops out.

**`scaffold` is tree-wide, not change-scoped.** Peers routinely add modules
without scaffolding, so one run emits stubs for *their* modules too. Diff each
modified stub and stage only the ones whose added lines name **your** module;
leave the rest for their owners and do not revert them. A red docs build after
`scaffold` is often not yours — grep the log for your own module names first.

## Docstrings cross-link the core spine

A module that imports a canonical core struct MUST cross-link that struct in at
least one docstring, using a Sphinx role such as `:class:`ModeloRevision``.
Docstrings must form a graph steering readers to the canonical spine; a module
depending on a core struct but never cross-referencing it is a dead end.

The spine is the `CORE_STRUCTS` mapping in
`src/cadrumo/tests/test_docstring_core_struct_links.py`. Anchors are documented
public symbols, so a bare `:class:`Name`` resolves through the build's
missing-reference resolver — do not add a dotted path. **Choose anchors for
navigability, not import in-degree**: a central data aggregate, a domain
authority that owns access, or a domain's primary closed-value enum — never
ubiquitous infrastructure learned once, error subclasses, or low-reach types.
The link MUST be semantically truthful; do not satisfy the gate with unrelated
roles.

## Terminology: one declaration, preserved by scaffold

Every user-facing domain term is enrolled once in the Terminology Handbook and
referenced from docs through that entry. Never redeclare an enrolled term's
definition in prose, and never maintain a parallel hand-authored glossary — four
unsynchronised terminology stores were the failure mode the Handbook removes.

Every scaffold run must preserve curated fields verbatim, scaffold new entries as
**empty drafts**, and retire vanished entries as **tombstones** with
`replaced_by`. Generated discovery and human curation share one authoring tree,
so clobbering curated prose, inventing definitions or deleting vanished records
breaks reviewability and the immutable-id model.

**Only a taxpayer- or operator-facing AEAT concept may be `approved`** and thus
render in the generated glossary and shipped search: a tax, modelo, casilla,
régimen, period, legal concept, or operator workflow noun. A concept naming the
search, calculation or registry **machinery** MUST NOT be `approved` — it is
`deprecated` (resolvable for the developer RAG, excluded from the glossary, with
a `scope_note` marking it internal) and **never deleted**. `deprecated` is right
rather than `retired` (which asserts a successor a mis-enrolment lacks) or
deletion (which the scaffold-preserve contract forbids).

## Shipped search artefacts are licence-clean

Documentation search artefacts that ship in the package or the built docs must
come only from licence-clean sources and contain only laundered identifiers and
rankings. **Never ship** anything derived from NC, ND or gated sources; raw
oracle output (raw scores, snippets, sparse maps, sparse term weights); or raw or
unbounded vectors.

**The sole narrow embedding exception:** a bounded term-embedding matrix may ship
**in the built docs, never in the wheel**, only when it is reviewable plain data
computed on the dev box by a pinned, named model under the MIT or Apache-2.0
licence over project-authored or project-bundled vocabulary. Its provenance stamp
must name the model, exact revision, licence, vocabulary fingerprint and
serialized size, and it must be no larger than 3 MB.

**That exception currently has NO consumer.** The tree carries no
term-embedding matrix, no compiler for one, and no client tier that would read
one — they were removed, and whether that removal stands is an open ruling. The
permission is kept open rather than re-narrowed because a permission that
oscillates is worse than one that is documented. So read it as a door that is
deliberately unlocked and presently unused: shipping a matrix through it is not
"already sanctioned practice", it is the first use, and it needs the ruling
first.

**Commit only the LIGHT precompiled data** — the laundered relevance mapping,
synonym candidates, held-out queries, the Handbook fragments, and any qualifying
matrix. **Never commit the HEAVY generated search index**, which is gitignored
and regenerated on every docs build: it is a deterministic build output, not
source, so committing it bloats every clone and drifts from the corpus.

## How

- **Good:** a relocation commit runs `scaffold` and stages the regenerated deltas
  for its own modules in the same explicit-path commit.
- **Good:** a newly-stubbed module module-qualifies stdlib cross-references
  (`:exc:`~decimal.InvalidOperation``), while bare *project* anchors stay bare.
- **Good:** add or update a concept fragment under
  `src/cadrumo/_data/terminology/concepts/`, then use `:term:` references.
- **Good:** commit a relevance mapping of target ids, URLs, surfaces and
  normalised weights after ratified review; regenerate the index at build time.
- **Bad:** hand-creating or editing an API stub; or committing a delete or rename
  without re-running `scaffold`, leaving an orphan that crashes the next build.
- **Bad:** defining a term in a how-to paragraph while a Handbook concept also
  exists; a scaffold run rewriting a curated description; or promoting an
  internal tooling concept to `approved`.
- **Bad:** committing an embedding outside the narrow exception, sparse maps, raw
  score payloads, or the generated index corpus.

Source: ADRs `2026-06-10-docs-terminology-search-adr`,
`2026-06-15-docs-terminology-search-adr`,
`2026-08-01-user-docs-search-consolidation-adr` (R5),
`2026-05-30-docs-architecture-adr`.
