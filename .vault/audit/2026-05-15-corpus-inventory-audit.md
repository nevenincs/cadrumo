---
tags:
  - '#audit'
  - '#corpus-inventory'
date: '2026-05-15'
modified: '2026-05-15'
related: []
---



# `corpus-inventory` audit: `Corpus orphan inventory`

## Scope

Inventory-only scan of `corpus/` against every `corpus/...` reference
in `registry/`. Counts orphan files (on disk, no inbound reference) and
dangling references (referenced but absent). No file deletions, no
registry edits — this audit feeds future cleanup decisions, it does not
make them.

## Findings

- **Files on disk**: 447
- **Distinct corpus paths referenced from registry**: 254
- **Orphans (on disk, no inbound ref)**: 193
- **Dangling refs (referenced, absent)**: 0

The zero dangling-reference count is the strong signal: every
`corpus_ref` in `registry/` resolves on disk. No registry rot from
missing source files.

The 193 orphans partition into six families:

### O1 — `manifest.json` directory descriptors (37 files)

Each `corpus/<area>/<modelo>/.../manifest.json` is a tooling artefact
produced by the corpus ingestion scripts. The registry never cites
manifests directly because authority flows through individual source
files. These are intentional, not real orphans.

### O2 — `disenos_registro/` historical revision archives (132 files)

The bulk of the orphan list. Within `corpus/aeat_official/disenos_registro/modelo_<N>/files/`
each modelo carries every revision of its record-design document the
ingestion script could find — `pre-2015 PDF`, `2015–2018 XLS`,
`2019-and-following XLSX`, etc. The registry typically wires only the
canonical-revision file (one per declared revision span); the
historical predecessors stay on disk as a corpus-archive but are not
cited from modelo TOMLs. Subfamilies:

- 25 `.xls` files paired with a referenced `.xlsx` sibling (same content,
  legacy format kept alongside).
- 19 `.xlsx` files paired with a referenced `.xls` sibling.
- ~88 fully unpaired historical-revision PDFs / XLS for pre-2015 ejercicios.

### O3 — `normatives/` legal-corpus orphans (13 files)

Eleven LIVA `art-163-*` HTML files (regime-especial articles
`duovicies`, `octovicies`, `septiesdecies`, `septvicies`, `sexvicies`,
`tervicies`, `vicies`) plus the consolidated `ley-37-1992.html`
whole-text and an `orden-hac-1432-2024.html`. Cross-link with the
catalogue-validation audit: the `art-163-*` HTMLs sit ready for the
LIVA-article extension work flagged there (family F4).

### O4 — `manuals/` directory manifests (8 files)

All eight entries are `manifest.json` files — same intentional pattern
as O1. The renta and IVA manuals themselves (PDFs / HTMLs) are
referenced from registry.

### O5 — `parity_replays/` orphans (6 files)

Replay fixtures not yet wired to a verification expectation. Candidate
inputs for the live-parity-oracle work stream.

### O6 — Other `aeat_official` orphans (5 files)

A `README.md`, two GROI response samples, and two `modelo_131`
screenshot PNGs. Documentation aids, not citation targets.

## Recommendations

This audit is inventory-only. The cleanup decisions follow:

- O1 and O4 (45 `manifest.json` files) — keep; intentional tooling output.
- O2 historical revision archives — keep on disk as corpus archive,
  but consider an explicit allow-list mechanism in the orphan scan so
  future audits don't re-flag the same 132 files. Alternatively, mark
  the archive directories with a `.corpus-archive` sentinel that the
  scanner can detect.
- O3 LIVA HTMLs — author the corresponding `[legal."ley-37-1992:art-N"]`
  entries in `registry/aeat/legal/iva.toml`. Direct overlap with the
  catalogue-validation audit's F4 finding for core LIVA articles
  (`art-99`, `art-102/104`, `art-107-110`); the regime-especial
  `art-163-*` HTMLs are next-tier authorship.
- O5 replay fixtures — wire to `verification_expectations` in the
  relevant modelo TOMLs once the live-parity oracle is ready.
- O6 — keep; documentation / sample artefacts.

After the O3 and O5 work lands, the meaningful orphan count drops from
193 to the ~140 file-archive set (O1 + O2 + O4 + O6), which is
intentional and stable.
