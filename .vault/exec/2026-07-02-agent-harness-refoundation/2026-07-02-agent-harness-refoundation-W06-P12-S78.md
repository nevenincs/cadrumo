---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S78'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Build the structured citation lookup keyed on citation id over the registry typed legal_refs, corpus_ref, and BOE permalink data

## Scope

- `src/aeat/application/corpus_search/_citation_lookup.py`

## Description

- Add `CitationLookup` over the reviewed registry legal catalogue and the bundled corpus source root, with a `bundled_citation_lookup` factory that reads both from the single registry authority.
- Resolve a citation id to catalogue metadata (document id, kind, permalink, article, section, anchor) plus the verbatim authoritative text its `corpus_ref` points at, keyed on the registry `legal_refs` ids — a structured lookup, never a parallel citation parser.
- Read verbatim text from the bundled `*.extracted.json` sidecar and slice it to the anchor-named unit when the source file carries multiple units; fall back to the `*.extracted.md` sidecar, then to a BeautifulSoup case-preserving strip of the raw BOE HTML excerpt for the minority of refs without a sidecar.
- Refuse an unknown citation id or a `corpus_ref` that escapes the corpus root with a typed input error.
- Add real-behavior tests covering verbatim resolution of LGT art. 27.2, the raw-HTML fallback, the consolidated-document anchor slice, the unknown-id refusal, catalogue-authority parity, and a full sweep asserting every one of the 453 catalogue citations resolves to non-empty text.
- Export the citation surface on the package top-level facade.

## Outcome

The runtime `legal_refs`-to-verbatim-text resolution the product lacked is live and grounded in the registry legal catalogue as the single citation authority. All 453 reviewed catalogue citations resolve to authoritative text, including the 98 refs whose corpus file ships no extracted sidecar (served via the raw-HTML fallback). Focused tests are green; ruff and pyright are clean.

## Notes

The catalogue authority is reused verbatim, satisfying the registry-authority-flow discipline. A process incident: the implementation and test files for this Step were staged in the shared index and were swept into a peer coordinator commit (`c955c0496d`, "consolidate cross-campaign WIP into a stable baseline") before this executor's own per-Step pathspec commit ran, so the code landed under that SHA rather than a `[W06.P12.S78]`-tagged commit; the package-facade export for this surface landed in `6aa3ebca3e`. The code is committed, tests are green at HEAD, and this record closes the Step; the attribution split is documented here for the audit trail.
