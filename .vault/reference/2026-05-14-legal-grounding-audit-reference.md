---
tags:
  - '#reference'
  - '#legal-grounding-audit'
date: '2026-05-14'
modified: '2026-06-29'
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

- **348 canonical `[legal."slug"]` entries** across the
  `registry/aeat/legal/*.toml` topic files.
- **348 of 348 entries have `corpus_ref` fields**; **348 of 348
  resolve to an existing HTML file** under
  `corpus/normatives/html/`. No broken edges from registry to corpus.
- **297 distinct `legal_refs` slugs cited** across the modelo
  registry. **297 of 297 resolve** to a canonical legal entry.
- **262 corpus HTML files**; **245 are consumed** by at least one
  legal entry; **17 are orphans** (no legal entry cites them).

### Citation graph: zero broken edges

The structural contract holds. Every slug a modelo cites resolves to
a canonical legal entry; every canonical legal entry's `corpus_ref`
resolves to a file that exists; the path from modelo binding to BOE
text is intact for everything currently wired.

### The 17 corpus orphans

These are corpus HTML files with no `[legal."slug"]` entry pointing
at them. They currently fall into one category.

All 17 current orphans are whole-document Orden snapshots where the
canonical legal entries index by article/apartado slug or by narrower
article-specific files. Indexing the whole-document by a bare-stem slug
would create canonical entries with zero downstream consumers. There are
no current `ley-37-1992-art-163-*` article-specific orphans.

  - `orden-eha-2887-2008.html`
  - `orden-eha-3012-2008.html`
  - `orden-eha-3111-2009.html`
  - `orden-eha-3378-2011.html`
  - `orden-eha-3434-2007.html`
  - `orden-eha-3786-2008.html`
  - `orden-eha-789-2010.html`
  - `orden-hac-1023-2021-modelo-714.html`
  - `orden-hac-1432-2024.html`
  - `orden-hac-2572-2003.html`
  - `orden-hac-3625-2003.html`
  - `orden-hac-610-2021.html`
  - `orden-hac-623-2026.html`
  - `orden-hac-657-2025.html`
  - `orden-hap-2250-2015.html`
  - `orden-hap-72-2013.html`
  - `orden-hfp-886-2023.html`

### What the audit does NOT establish

The "no broken edges" finding is a structural property. It does NOT
imply legal completeness. Currentization on 2026-06-29 closed the
historical Modelo 100 deduction-family, Modelos 308/309 article-level
grounding, and Modelo 369 scheme-range examples below. Future
per-modelo reviews can still find casilla/binding completeness defects
against AEAT-published forms, but these three cited examples are no
longer current gaps:

#### Modelo coverage completeness (separate work)

A modelo can have a fully-connected citation graph while still
under-specifying its casilla / binding set against the AEAT-published
form. Concrete examples surfaced during the audit:

  - **Modelo 100 (IRPF) 2025 — currentized closed for the cited
    deduction-family gap**: the earlier statement that only
    `ley-35-2006:art-68.4` was grounded is stale. The current registry
    carries fine-grained legal entries and casilla/formula references for
    the cited state deduction families: `art-68.1` (empresas de nueva o
    reciente creación), `art-68.2` (incentivos de actividad económica),
    `art-68.3` (donativos), `art-68.4` (Ceuta/Melilla), `art-68.5`
    (Patrimonio Histórico), plus the transitional or adjacent deduction
    authorities used by the same M100 settlement surface (`dt-15`,
    `dt-18`, `da-50`, `art-81`, and `art-81-bis`). The current
    regression gate is
    `src/aeat/domain/calculations/registry/tests/test_modelo_100_registry_legal_refs.py`;
    focused verification on 2026-06-29 passed (`133 passed`) and asserts
    those surfaces do not fall back to the broad `ley-35-2006:art-68`
    reference where a fine-grained article exists. This closes the cited
    deduction-family grounding defect; it does not by itself certify every
    autonomous-community deduction row against every annual instruction.
  - **Modelos 308 / 309 — currentized closed for article-level order
    grounding**: the earlier statement that their orden ministerial corpus
    was unindexed at the article level is stale. The current IVA legal
    catalogue resolves `orden-eha-3786-2008:art-2` and `art-11` for
    Modelo 308, and `orden-hac-3625-2003:apartado-1` and `apartado-3`
    for Modelo 309, against article/apartado-level corpus files. The
    current registry cites those refs from the model manifests, revisions,
    filing schedules, constructs, links, and the M309 formula/binding
    closure. Focused verification on 2026-06-29 passed
    `test_modelo_308_registry.py` and `test_modelo_309_registry.py`
    (`17 passed`). This closes the article-level-order grounding defect;
    it does not by itself certify every ad-hoc IVA scenario against every
    AEAT instruction row.
  - **Modelo 369 (OSS / IOSS) — currentized closed for scheme-range
    article grounding**: the earlier statement that only 3 of the 11
    LIVA art. 163 OSS/IOSS sub-articles were referenced is stale. The
    current Modelo 369 manifest and scheme envelopes carry the full
    LIVA ranges advertised by their revision labels: Esquema Exterior
    (`octiesdecies`, `noniesdecies`, `vicies`), Esquema Unión
    (`unvicies`, `duovicies`, `tervicies`, `quatervicies`), and
    Esquema Importación (`quinvicies`, `sexvicies`, `septvicies`,
    `octovicies`). The current IVA legal catalogue also resolves the
    two formerly missing range refs, `ley-37-1992:art-163-noniesdecies`
    and `ley-37-1992:art-163-quatervicies`, against bundled
    consolidated LIVA corpus anchors. Focused verification on
    2026-06-29 passed `test_modelo_369_registry.py` (`32 passed`) and
    asserts the loaded registry carries those ranges through the model
    manifest, snapshots, revision envelopes, constructs, completeness
    manifests, total casillas, formulas, and calculation links. This
    closes the cited scheme-range grounding defect; it does not by
    itself certify every destination/rate/correction row against the
    full AEAT-published Modelo 369 instruction surface.

#### Procedural-grounding gap (R14 / R15 follow-up)

Currentization on 2026-06-29 closes the LGT side of this finding for
the local workflow-gate and cross-period verification surfaces. The
current legal catalogue resolves:

| Slug | Topic | Status |
|---|---|---|
| `ley-58-2003:art-119` | Declaración tributaria | corpus-backed in `legal/lgt-autoliquidacion.toml` |
| `ley-58-2003:art-120` | Autoliquidaciones and rectification | corpus-backed in `legal/lgt-autoliquidacion.toml` |
| `ley-58-2003:art-122` | Complementarias / sustitutivas | corpus-backed in `legal/lgt-autoliquidacion.toml` |

The application-level workflow constant
`WORKFLOW_GATE_LEGAL_REFS` now carries those three refs, and
`src/aeat/application/modelo/tests/test_cross_period_finding_legal_grounding.py`
verifies that application literal legal refs resolve to bundled corpus.
The same gate also verifies cross-period findings, including the
same-year non-official local-chain advisory, carry non-empty legal refs.

The e-presentation framework refs remain intentionally outside the
current local workflow gate. This application does not perform live AEAT
submission; it builds, verifies, exports, records local filing state, and
reads official evidence through read-only surfaces. If a future feature
adds actual electronic presentation, it must fetch and catalogue the
governing `rd-1671-2009:art-*` and `orden-hap-2194-2013:art-*` articles
before encoding that live-submission path.

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
