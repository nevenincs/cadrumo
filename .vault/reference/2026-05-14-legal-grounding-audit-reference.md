---
tags:
  - '#reference'
  - '#legal-grounding-audit'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `legal-grounding-audit` reference: `Legal-grounding corpus and registry coverage audit`

Inventory of the project's legal-grounding architecture across three
surfaces: the BOE / AEAT-published HTML corpus under
`corpus/normatives/html/`, the canonical legal-entry index under
`registry/aeat/legal/`, and the per-binding `legal_refs` citations
in `registry/aeat/modelos/`.

This is a structural audit. It verifies the citation graph has no
broken edges and surfaces gaps where corpus material exists without
downstream consumers. It does NOT pass legal judgement on whether a
binding cites the correct article, and it does NOT verify that a
modelo's casilla set is complete against the AEAT-published modelo
form.

## Findings

### Coverage summary (verified by script)

- **131 canonical `[legal."slug"]` entries** across the twelve
  `registry/aeat/legal/*.toml` topic files.
- **131 of 131 entries have `corpus_ref` fields**; **131 of 131
  resolve to an existing HTML file** under
  `corpus/normatives/html/`. No broken edges from registry to corpus.
- **128 distinct `legal_refs` slugs cited** across the modelo
  registry. **128 of 128 resolve** to a canonical legal entry.
- **107 corpus HTML files**; **81 are consumed** by at least one
  legal entry; **26 are orphans** (no legal entry cites them).

### Citation graph: zero broken edges

The structural contract holds. Every slug a modelo cites resolves to
a canonical legal entry; every canonical legal entry's `corpus_ref`
resolves to a file that exists; the path from modelo binding to BOE
text is intact for everything currently wired.

### The 26 corpus orphans

These are corpus HTML files with no `[legal."slug"]` entry pointing
at them. They split into two categories.

**Whole-document orphans (9)** — full Ley / Orden HTML snapshots
where the canonical legal entries index by `:art-...` slug pointing
at the same file with an anchor. Indexing the whole-document by a
bare-stem slug would create canonical entries with zero downstream
consumers.

  - `ley-35-2006.html`
  - `ley-37-1992.html`
  - `orden-eha-3012-2008.html`
  - `orden-eha-3111-2009.html`
  - `orden-eha-3378-2011.html`
  - `orden-eha-3434-2007.html`
  - `orden-eha-3786-2008.html`
  - `orden-eha-789-2010.html`
  - `orden-hap-2250-2015.html`

**Article-specific orphans (17)** — corpus files at the article
granularity that no canonical legal entry indexes. The category
splits further:

  - `ley-37-1992:art-163-*` (7 OSS / IOSS sub-articles:
    `duovicies`, `octovicies`, `septiesdecies`, `septvicies`,
    `sexvicies`, `tervicies`, `vicies`) — Modelo 369 binds only 3
    of the 11 art-163 sub-articles
    (`octiesdecies`, `quinvicies`, `unvicies`). The other 7 are
    corpus context; no current 369 binding needs them.
  - `orden-eha-1274-2007-art-1.html`, etc. — orden-level articles
    where the parent orden is consumed at a different article-id.
  - `orden-hac-{1432-2024, 248-2021, 2572-2003, 265-2024,
    3625-2003, 610-2021, 657-2025}.html`,
    `orden-hap-72-2013.html`, `orden-hfp-{207-2022, 310-2023}.html`
    — orden documents whose articles are not yet indexed because
    the modelos they govern (308, 309, etc.) have no current
    bindings cited at the article level.

### What the audit does NOT establish

The "no broken edges" finding is a structural property. It does NOT
imply legal completeness. Two distinct gaps remain open and are NOT
addressed by this audit:

#### Modelo coverage completeness (separate work)

A modelo can have a fully-connected citation graph while still
under-specifying its casilla / binding set against the AEAT-published
form. Concrete examples surfaced during the audit:

  - **Modelo 100 (IRPF) 2025**: 2,235 casillas, 44 bindings, 168
    formulas. Only `ley-35-2006:art-68.4` (vivienda habitual
    transitoria) is grounded from the IRPF deduction family. The
    other art-68 sub-articles (donativos, planes pensiones,
    maternidad, inversiones empresa nueva creación, alquiler
    vivienda habitual transitoria, etc.) are not in the corpus and
    are not bound by any Modelo 100 casilla. The modelo's deduction
    casillas for those families exist as form fields but their
    underlying calculations have no legal anchor in the registry.
  - **Modelos 308 / 309**: registry TOMLs exist but the orden
    ministerial corpus is unindexed at the article level. Coverage
    against the AEAT form has not been verified.
  - **Modelo 369 (OSS / IOSS)**: 31 art-163 citations, but only 3
    of the 11 art-163 sub-articles are referenced. Whether the
    remaining 8 are out-of-scope or simply unfetched is unverified.

These cases are **not solvable by connecting existing corpus** —
they require a per-modelo completeness review against the
AEAT-published instruction booklet, followed by either fresh BOE
fetches (for under-grounded articles) or explicit out-of-scope
declarations (for sub-articles the modelo intentionally does not
support).

#### Procedural-grounding gap (R14 / R15 follow-up)

The procedural law for what makes a Modelo declaration *legally
filed* is not in the corpus today. The apex CLI-workflow redesign
ADR's R14 / R15 rows are now code-closed (the workflow gate is
shipped) but the gate has no `legal_refs` annotation. Bridging
requires net-new BOE fetches:

| Slug | Topic | Status |
|---|---|---|
| `ley-58-2003:art-119` | Autoliquidación general regime | not in corpus |
| `ley-58-2003:art-120` | Rectificación de autoliquidación | not in corpus |
| `ley-58-2003:art-122` | Autoliquidación complementaria | not in corpus |
| `rd-1671-2009:art-*` | E-presentation framework | not in corpus |
| `orden-hap-2194-2013:art-*` | E-presentation procedure | not in corpus |

### Schema patterns confirmed by the audit

The proven legal-entry shape any new entry must follow:

- `evidence_tier`: `"legal_authority"` for BOE-published primary
  sources; `"derived"` for parameter tables that interpret a legal
  source.
- `authority`: `"boe"` for BOE-published text.
- `kind`: `"ley"`, `"real-decreto"`, `"orden"`, `"reglamento"`.
- `corpus_ref`: relative path under `corpus/normatives/html/` with
  an anchor (`#aXX` or `#articulo-XX`) for article scope. Filename
  convention uses hyphens (`art-68-4`) even when the slug uses dots
  (`art-68.4`).
- `document_id`: BOE identifier (`BOE-A-YYYY-NNNNN`).
- `article`: numeric or letter id (string).
- `permalink`: canonical `boe.es/buscar/act.php?id=...#aXX` URL.
- `published_at`, `effective_from`: ISO dates.
- `review_status`: `"reviewed"` after operator signoff;
  `"pending_review"` before. Never falsely marked reviewed.
- `reviewed_at`, `reviewed_by`: filled only after operator signoff.
- `notes`: human-readable summary of the article's contribution.
- `required_text`: tuple of verbatim BOE excerpts that the canonical
  entry assertively quotes. Renders to a parity check the legal
  surface can verify against the corpus HTML.

### Hygiene principle preserved by the audit

`registry/aeat/legal/` follows the rule **every canonical entry has
at least one downstream consumer** (a `legal_refs` citation from a
modelo binding, casilla, formula, parameter, or relation). Adding
canonical entries for the 26 orphan corpus files now would create
canonical entries with zero downstream references, breaking that
invariant. Orphans should be indexed *when* a binding that needs
them is added, not preemptively.

## Conclusion

The "connect existing corpus" task has **zero work to do**. The
citation graph is fully connected; the 26 orphan corpus files are
context-only spillover from earlier harvest passes; indexing them
without a consumer would degrade the registry's integrity invariant.

The two real outstanding gaps — **modelo coverage completeness**
(per-form bindings against AEAT-published instructions) and the
**procedural-grounding gap** for R14 / R15 — both require net-new
BOE fetches and per-modelo completeness reviews. Neither is
"connect what's there"; both are "fetch what's missing".
