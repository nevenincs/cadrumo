---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S26'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Delete the hand-written glossary page, the explanation mini-glossary, and every inline term re-definition in the same change, converting prose to term-role references so the nitpicky build gate enforces enrolment and single declaration (ADR D7, no-legacy rule)

## Scope

- `docs tree editorial cutover`

Implements ADR D7 + no-legacy-compatibility: the one-time cutover that deletes
every hand-written glossary surface so the generated glossary is the only
terminology source. Makes terminology codebase-state-as-truth. The
redeclaration conformance gate (forbidding FUTURE inline redefinition) and the
prorrata smoke gate are sibling steps, not this one.

## Description

- Establish the two load-bearing mechanics empirically (small Sphinx builds,
  not the full gate): `:term:` matching is CASE-INSENSITIVE (so `Casilla`
  resolves the `casilla` anchor), and an UNAPPROVED term yields a `ref.term`
  warning (so only approved anchors are convertible).
- Resolve the recargo collision the generator surfaced: the two concepts are
  genuinely distinct (the regime vs the surcharge), so disambiguate the
  regime's preferred term to `regimen del recargo de equivalencia`, freeing the
  bare `recargo de equivalencia` surface for the surcharge concept. The loader
  re-validates the whole tree; `scaffold --check` is a clean no-op.
- Delete `docs/glossary.md` and swap the `docs/index.md` toctree entry
  `glossary` to the generated `_generated/glossary`.
- Delete the explanation mini-glossary ("The plain words you'll meet") and the
  explicit inline re-definition paragraphs (the "quick note on terms" block,
  the from-records inline definitions), converting the canonical mentions of
  APPROVED terms to `{term}` references and pointing the rest at the glossary.
- Redirect every `[glossary](../glossary.md)` link (8 pages) to the generated
  glossary via the MyST `{doc}` role (build-time resolved; not a filesystem
  markdown link the conformance test rejects).
- Validate: a targeted Sphinx build over the changed pages + the generated
  glossary asserts ZERO `ref.term` warnings; the educational-docs and
  documented-command conformance suites pass.

## Outcome

### What was deleted

- `docs/glossary.md` (the 28-entry hand-written glossary) - DELETED; the
  generated `docs/_generated/glossary.rst` replaces it, and the `docs/index.md`
  toctree now points at `_generated/glossary`.
- The explanation mini-glossary section "## The plain words you'll meet"
  (`docs/explanation/index.md`) - DELETED.
- The inline re-definition paragraphs: the "A quick note on terms. A *modelo*
  is ... A *casilla* is ..." block in `building-on-earlier-filings.md` and the
  "*modelos* (numbered official tax forms) ... *casillas* (numbered boxes)"
  inline definitions in `from-records-to-figures.md` - REPLACED with `{term}`
  references and a glossary pointer.

### Mentions converted to :term: vs left plain

The 35 approved anchors (20 concepts; the recargo fix added
`regimen del recargo de equivalencia`) are the only convertible surfaces.
Converted to `{term}` references: `casilla`, `AEAT`, `justificante`,
`modelo 100` - all approved anchors, resolving case-insensitively. Left as
PLAIN mentions (not convertible - no approved anchor, converting would red the
`-n -W` build): `IVA`, `IRPF`, `RENTA`, and generic `modelo` (only the specific
`modelo 100/130/303/390` are anchors, not a bare `modelo`). The 8 cross-page
"see the glossary" links were redirected to the generated page via the `{doc}`
role.

### Referenced-but-unapproved GAP LIST (drives curation / informs S27)

16 terms the docs reference or formerly defined that are NOT approved concepts,
so they cannot be `:term:`-converted yet: `asesor fiscal`, `autonomo`,
`binding`, `fichero-BOE`, `formula`, `IRPF`, `IVA`, `ledger`, `modelo`
(generic), `NIF`, `preflight`, `renta`, `revision`, `verificado completo`,
`VIES`, `work unit`. The high-frequency ones (`IVA`, `IRPF`, `modelo`) are the
priority curation backlog: approving them (or a generic `modelo` concept) would
let a future pass convert their remaining plain mentions. This is a PARTIAL
cutover by necessity (green build + clean hand-store deletion now; incremental
conversion as concepts get approved) - no approvals were fabricated.

### Recargo collision resolution

The generator's S25 finding (`iva-recargo-equivalencia` vs `recargo-equivalencia`
both claiming `recargo de equivalencia`) is resolved as TWO genuinely distinct
concepts: `iva-recargo-equivalencia` is the special VAT *regime* (domain
`regimen`), `recargo-equivalencia` is the *surcharge* amount (domain
`concepto`), and they are `related`. The regime's preferred Spanish term is
disambiguated to `regimen del recargo de equivalencia` (keeping `RE` admitted);
the bare `recargo de equivalencia` surface now belongs solely to the surcharge
concept. The generator renders 20 entries with ZERO deduplication (was 19 + 1
skipped), and the loader + `scaffold --check` both accept the tree.

### Targeted-build proof (zero ref.term warnings)

Per the brief the full multi-minute `-n -W` build was NOT run. Instead a
targeted Sphinx build over the changed pages (`building-on-earlier-filings.md`,
`from-records-to-figures.md`, `explanation/index.md`) plus the generated
glossary asserted ZERO `ref.term` warnings - every `:term:` introduced
resolves against an approved anchor, and no unresolved/duplicate term remains.
A second build confirmed no broken `glossary.md`-link warnings after the
redirects.

### Tests + pass

- `test_educational_docs_conformance.py` - 65 green (the `test_relative_links_
  resolve` parametrisations that initially failed on the generated-glossary
  path are green after switching the links to the build-time `{doc}` role).
- `test_documented_command_conformance.py` - 41 green.
- `aeat.terminology scaffold --check` - clean no-op (95 unchanged) after the
  recargo term-label edit.

## Notes

- SCOPE FENCE honoured: S26 is the one-time cutover. It does NOT build the
  redeclaration conformance gate (S27) or the prorrata smoke gate (S28).
- The generated-glossary link uses the MyST `{doc}` role, not a markdown
  `[](path)` link: the generated page does not exist on disk at test time
  (it is build-time-generated, gitignored), so a filesystem markdown link
  would fail the relative-link conformance gate; the `{doc}` role resolves at
  build time and is not a filesystem link.
- PEER-WIP discipline: before editing each docs file I confirmed no
  non-authored WIP via `git diff`. The working tree also carries PEER changes I
  did NOT touch or stage - `docs/api/*.rst` (peer apidocs drift) and
  `docs/how-to/classify-transactions.md` / `docs/how-to/filing-periods.md`
  (peer doc edits); only the files I actually converted are staged.
- No PM wave/phase/step tokens in production docs (ADR ids only in this exec
  record). The user-docs language stays simple and taxpayer-general.
- S27 handoff: the redeclaration gate enforces no NEW inline redefinition of an
  approved term. The approved-term set is the 35 anchors from 20 concepts; the
  16-term gap list above is what the gate must NOT flag (those have no anchor
  yet) and what a curation pass should approve to widen `:term:` coverage. The
  recargo two-concept overlap is now resolved, so the gate starts from a clean
  single-declaration baseline.
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` over ONLY my explicit paths.
