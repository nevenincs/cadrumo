---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S25'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Generate the glossary page from approved Handbook concepts at the builder-inited seam (uncommitted, like the CLI reference), one term per entry, with term anchors and hover tooltips via sphinx-hoverxref (ADR D7)

## Scope

- `docs/conf.py + dev docs generator`

Implements ADR D7: the generated glossary that closes the redeclaration hole.
One term per entry, `:term:` anchors the nitpicky `-n -W` gate enforces,
hover tooltips via sphinx-hoverxref. Advances the W04.P12 glossary chain
toward the redeclaration gate and the prorrata smoke gate. The hand-written
`docs/glossary.md` deletion and the inline-to-`:term:` conversion are the
SIBLING cutover step, not this one.

## Description

- Ground the Handbook loader (`load_terminology_handbook`, 95 concepts), the
  `ConceptRecord` schema (lifecycle, languages, terms, legal_refs,
  short_description/definition), and the `cli_reference.py` generation pattern
  to mirror.
- Author `dev/docs/glossary_reference.py` (sibling of `cli_reference.py`):
  load the Handbook, render an RST `.. glossary:: :sorted:` directive over the
  APPROVED concepts only, with the ES preferred term as headword + admitted
  aliases as additional term lines, the EN definition/short_description as
  body, and resolved BOE permalink grounding links.
- Add a lightweight legal-ref to BOE-permalink resolver reading the legal
  catalogue TOMLs directly (`[legal."<id>"].permalink`).
- Wire `_generate_glossary_reference` at the `builder-inited` seam in
  `docs/conf.py`, exactly like `_generate_cli_reference`, writing the page to
  the gitignored `docs/_generated/glossary.rst`.
- Add `sphinx-hoverxref` to the docs dependency group, the `hoverxref.extension`
  to conf.py extensions, and `hoverxref_roles = ["term"]` /
  `hoverxref_role_types = {"term": "tooltip"}`.
- Validate the generated RST parses as a clean Sphinx glossary (a throwaway
  dummy build, NOT the full multi-minute `-n -W` build) - no warnings,
  `:term:` targets registered.
- Verify: ruff + format + ty clean, the generator tests green, collect-only
  clean, apidocs scaffold-check shows only pre-existing peer drift.

## Outcome

### Generator location + contract

`dev/docs/glossary_reference.py`, `generate_glossary_reference(docs_root) ->
GlossaryResult` (the public entry mirroring `generate_cli_reference`), plus
the pure `render_glossary(repo_root, handbook) -> (rst, result)`. It loads the
typed Handbook authority, renders the page, and writes it to the gitignored
generated path - regenerated every build so it cannot drift from the curated
concepts. The generator is authoritative; the output is never hand-edited.

### Approved-only rule + counts

ONLY `approved` concepts render as glossary entries. The Handbook has **20
approved, 75 draft**. **19 approved concepts rendered** (one fully collided -
see dedup below); **75 drafts excluded**. The drafts carry no curated
definition - they are search-only, surfaced through the compiled search index,
never as a glossary entry (a blank/placeholder entry would mislead the reader
or red the build). The exclusion count is reported on `GlossaryResult`.

### Term-anchor + alias-as-term-line approach

Each entry's headword is the concept's Spanish PREFERRED term (the canonical
surface a Spanish-tax reader looks up); its ADMITTED aliases render as
additional term lines on the SAME glossary entry, so a `:term:`AEAT`` /
`:term:`Agencia Tributaria`` cross-reference resolves any declared surface to
one definition. One concept = one entry (the multi-term-line form is the
supported aliasing mechanism; the sphinx-hoverxref shared-entry rendering bug
forbids separate entries sharing a definition). The throwaway Sphinx build
registered **34 `:term:` targets** (19 headwords + their admitted aliases).
Deprecated/forbidden terms are not enrolled as resolvable anchors.

### Duplicate-term handling (a real Handbook-data finding, surfaced not hidden)

Two approved concepts (`iva-recargo-equivalencia` with terms `recargo de
equivalencia` + `RE`, and `recargo-equivalencia` with only `recargo de
equivalencia`) both claim the surface `recargo de equivalencia`. A Sphinx
glossary requires globally-unique terms, so the generator DEDUPLICATES: the
first concept keeps the anchor, the colliding term line is dropped from the
later concept (recorded in `GlossaryResult.deduplicated_terms`), and a concept
whose every term collided is skipped rather than emitting a term-less block.
This keeps the `-n -W` build green AND surfaces the collision as data for the
redeclaration-gate / Handbook-curation step (the two-concepts-one-term overlap
is a curation question, not something S25 silently merges). Without the dedup
the build would red with a duplicate-term warning - which the validation test
confirms is now absent.

### Output language + legal grounding

The docs build pins `AEAT_OUTPUT_LANGUAGE=en` (conf.py:12), so the entry body
is the English definition (or the English short_description when no full
definition is authored - every approved concept has the short_description),
with the Spanish term as the headword. Concepts carrying `legal_refs` render
resolved BOE permalink grounding links: **9 legal links** across the 7
grounded approved concepts (e.g. `autoliquidacion` -> LGT art. 120 ->
`boe.es/buscar/act.php?id=BOE-A-2003-23186#a120`), all resolved from the legal
catalogue.

### conf.py builder-inited wiring

`_generate_glossary_reference` is connected to `builder-inited` alongside
`_generate_cli_reference`, writing `docs/_generated/glossary.rst` before
Sphinx reads the source tree, so its `:term:` anchors resolve. The path is
gitignored (`docs/_generated/`, added next to `docs/cli/`).

### hoverxref status: ADDED

sphinx-hoverxref was ABSENT; it is now ADDED - `sphinx-hoverxref>=1.4` pinned
in the docs dependency group (lockfile updated, sphinx-hoverxref 1.4.2 +
sphinxcontrib-jquery resolved), `hoverxref.extension` added to conf.py
extensions, and `hoverxref_roles = ["term"]` configured so every `:term:`
reference to a glossary entry shows the curated definition on hover. The
`:term:` anchors are the load-bearing part; the tooltips are the enhancement
over them.

### How validation ran WITHOUT a full docs build

Per the brief, the full multi-minute `-n -W` build was NOT run. Instead the
generator was tested directly (it loads the real Handbook and renders a valid
glossary) and the OUTPUT was parsed by a throwaway dummy Sphinx project over
just the generated page: it built with ZERO warnings (proving the directive is
well-formed and the duplicate-term collision is deduplicated) and registered
the `:term:` targets in the std domain. This isolates the glossary's validity
from the full build's cost.

### Test names + pass

`dev/docs/tests/test_glossary_reference.py` (integration), 5 green:
approved-only/drafts-excluded; headword + alias term lines present; legal
grounding links resolve to permalinks; the generated page parses without a
duplicate-term warning and registers 30+ `:term:` targets; the generator
writes to the gitignored generated path. ruff / format / ty clean;
collect-only clean.

### S26 handoff (the cutover, now that the generated replacement exists)

S26 (the cutover, which must land WITH this generated replacement) deletes and
converts:

- DELETE the hand-written `docs/glossary.md` (26 deflist entries) - the
  generated `docs/_generated/glossary.rst` replaces it.
- SWAP the `docs/index.md` toctree entry `glossary` (line 130, the .md) to the
  generated `_generated/glossary` path.
- DELETE the explanation mini-glossary ("the plain words you'll meet") and the
  inline term re-definitions, CONVERTING prose mentions of enrolled terms to
  `:term:` references so the nitpicky build enforces enrolment + single
  declaration.
- NOTE for S26/S27: the `recargo de equivalencia` two-concept collision this
  generator surfaced (`deduplicated_terms`) is a Handbook-curation item - the
  redeclaration gate (S27) or a curation pass should resolve whether
  `iva-recargo-equivalencia` and `recargo-equivalencia` are one concept.

## Notes

- SCOPE FENCE honoured: S25 GENERATES the glossary + wires hoverxref. It does
  NOT delete `docs/glossary.md`, does NOT convert inline re-definitions, does
  NOT build the redeclaration conformance gate. The hand-written glossary
  stays in place; the generated one stands alongside at the generated path so
  the cutover can swap.
- The apidocs scaffold-check reports drift, but ONLY for peer
  `_participation_*` modules (peer commit `bac180efd`,
  ledger-modelo-crossref); none of my S25 changes touch `src/aeat` module
  structure, so I introduce zero apidocs drift and did not touch the peer
  stubs.
- No PM wave/phase/step tokens in production code (ADR ids only in this exec
  record). The generated glossary page itself carries a "generated, do not
  edit" header.
- The generated glossary is uncommitted (gitignored `docs/_generated/`); only
  the generator, its test, the conf.py wiring, the hoverxref pin
  (pyproject/lock), and the gitignore entry are committed.
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` as the very last action,
  explicit paths only, never touching `index.lock`.
