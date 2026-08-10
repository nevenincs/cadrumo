# AEAT documentation, terminology and shipped search

## User-facing language

Write user-facing documentation in simplistic, singular, imperative instruction
steps — "Create taxpayer profile." / "Import bank statement." — never
conversational plural narration ("We will now set up…"). Walk concrete
scenarios step by step instead of presenting every option; use general
terminology (NIF, CIF, DNI, NIE, NII); guide from profile setup and transaction
import through calculation and reconciliation, cross-linking so complex topics
arrive gradually; keep descriptions objective.

## Workflow

Every documentation change follows the `vaultspec-documentation` lifecycle:
wireframe → refinement → approval; context gathering and isolated
section-by-section drafting; technical review (against the codebase and
conformance gates) and editorial review; final approval. A *researcher* gathers
context without writing drafts; an *author* writes from that research only; an
*editor* reviews for a newcomer's clarity, tone and link integrity. **Final
wording and approval stay with the main session** — never delegate final prose
to a subagent.

Verify with
`pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`
and the nitpicky Sphinx gate `pytest dev/docs/tests/test_docs_build.py`. Chat
responses use absolute `file://` links with forward slashes; user-facing docs
use relative markdown links.

## The generated API reference is CLI-owned

Maintain with `python -m dev.docs.apidocs scaffold`; never hand-author or
hand-edit `docs/api/*.rst`. Run `scaffold` after any `src/cadrumo/` module-tree
change (relocation, rename, deletion) and land the regenerated stubs in the
same commit; `scaffold --check` is the drift gate, `audit` the health report. A
stub left for a deleted module hard-crashes the nitpicky `-n -W` autodoc build;
a module without a stub silently drops out.

**`scaffold` is tree-wide, not change-scoped:** one run also emits stubs for
peers' unscaffolded modules. Diff each modified stub and stage only those whose
added lines name YOUR module; leave the rest for their owners and do not revert
them. A red docs build after `scaffold` is often not yours — grep the log for
your own module names first.

## Docstrings cross-link the core spine

A module importing a canonical core struct MUST cross-link it in at least one
docstring via a Sphinx role (`` :class:`ModeloRevision` ``). The spine is the
`CORE_STRUCTS` mapping in
`src/cadrumo/tests/test_docstring_core_struct_links.py`; anchors are bare (no
dotted path — the build's missing-reference resolver handles them). Choose
anchors for navigability, not import in-degree: a central data aggregate, a
domain authority, or a domain's primary closed-value enum — never ubiquitous
infrastructure, error subclasses, or low-reach types. The link MUST be
semantically truthful.

## Terminology: one declaration, preserved by scaffold

Every user-facing domain term is enrolled once in the Terminology Handbook
(fragments under `src/cadrumo/_data/terminology/concepts/`) and referenced via
`:term:`; never redeclare an enrolled definition in prose or maintain a
parallel glossary. Scaffold runs preserve curated fields verbatim, add new
entries as **empty drafts**, and retire vanished entries as **tombstones** with
`replaced_by` — never clobber, invent, or delete.

**Only a taxpayer- or operator-facing AEAT concept may be `approved`** (and so
render in the glossary and shipped search): a tax, modelo, casilla, régimen,
period, legal concept, or operator workflow noun. A concept naming search,
calculation or registry **machinery** is `deprecated` with a `scope_note`
(resolvable for the developer RAG, excluded from the glossary) — never
`retired` (asserts a successor a mis-enrolment lacks), never deleted.

## Shipped search artefacts are licence-clean

*(Home of the retired rule slug `shipped-search-licence-clean` — deliberately
merged here, not shipped as its own file, so a search for the slug lands here.)*

Ship only licence-clean sources, laundered identifiers and rankings. **Never
ship** NC/ND/gated derivatives, raw oracle output (scores, snippets, sparse
maps, term weights), or raw or unbounded vectors. **Sole narrow exception:** a
bounded term-embedding matrix in the BUILT DOCS only (never the wheel) —
reviewable plain data, computed on the dev box by a pinned, named MIT or
Apache-2.0 model over project vocabulary, provenance-stamped (model, revision,
licence, vocabulary fingerprint, size), no larger than 3 MB. **That exception
currently has NO consumer** — the matrix, its compiler and its client tier were
removed. It is a deliberately unlocked, presently unused door: shipping through
it is a first use that needs a ruling, not sanctioned practice.

**Commit only the LIGHT precompiled data** (laundered relevance mapping,
synonym candidates, held-out queries, Handbook fragments, a qualifying matrix).
**Never commit the HEAVY generated search index** — gitignored, regenerated per
docs build; committing it bloats every clone and drifts from the corpus.

## How

- **Good:** a relocation commit runs `scaffold` and stages only its own
  modules' regenerated deltas in the same explicit-path commit.
- **Good:** stdlib cross-references module-qualified
  (`` :exc:`~decimal.InvalidOperation` ``); bare *project* anchors stay bare.
- **Good:** add or update a concept fragment, then `:term:` references; commit
  a ratified relevance mapping and regenerate the index at build time.
- **Bad:** hand-editing an API stub; landing a delete or rename without
  re-running `scaffold` (orphan stub crashes the next build); a scaffold run
  rewriting curated prose; promoting internal tooling to `approved`; committing
  an embedding outside the exception, sparse maps, raw scores, or the generated
  index.

Source: ADRs `2026-06-10-docs-terminology-search-adr`,
`2026-06-15-docs-terminology-search-adr`,
`2026-08-01-user-docs-search-consolidation-adr` (R5),
`2026-05-30-docs-architecture-adr`.
