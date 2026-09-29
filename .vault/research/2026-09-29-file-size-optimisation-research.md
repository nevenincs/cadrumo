---
tags:
  - '#research'
  - '#file-size-optimisation'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:61bef93925f58027541c7b5e40cc605919838cc3f90ca7ef8dff7d4988bb6fd6'
related:
  - "[[2026-07-13-docs-cli-sequences-adr]]"
  - "[[2026-09-29-docs-sequence-output-weight-plan]]"
  - "[[2026-09-10-data-provenance-consolidation-adr]]"
---

# `file-size-optimisation` research: `Oversized JSON inventory and remediation options`

Which committed JSON files exceed 5,000 lines, what they are, whether they must be committed, and how each family can become reviewable. Measured on `origin/main` at `8099d7d966` (2026-09-29) with full, unshallowed history (1,342 commits). Conclusion: every oversized file is machine-written. None is hand-authored source. They fall into five families with different fixes. JSON is not what makes clones heavy: all versions of every oversized JSON family together occupy under 10 MB of the pack, while corpus binaries account for most of the 385 MB. The cost is reviewability: a single 1 MB golden or a 10 MB one-line manifest cannot be read in a diff.

## Findings

### Inventory

43 JSON paths have exceeded 5,000 lines at some point in history. 17 exceed it in the current tree. Line counts undercount one family: the generation provenance manifests are single-line minified JSON, so they never appear in a line census although the largest is 10.9 MB. The census was produced with `git rev-list --objects --all` piped through `git cat-file --batch`, counting newlines per blob.

Current tree, over 5,000 lines:

| Lines | Size | Path | Family |
| ---: | ---: | --- | --- |
| 47,614 | 1.4 MB | `docs/_sequences/how-to/modelo-100/modelo-100-renta-2025.json` | A |
| 47,408 | 1.4 MB | `docs/_sequences/how-to/review-calculation-values/review-values-relation.json` | A |
| 45,364 | 1.3 MB | `docs/_sequences/how-to/modelo-100/modelo-100-inspect-inputs.json` | A |
| 42,866 | 1.4 MB | `docs/_sequences/explanation/how-renta-is-assembled/renta-assembly-requires.json` | A |
| 16,279 | 0.5 MB | `docs/_sequences/how-to/filing-spine/filing-spine-select.json` | A |
| 12,286 | 0.6 MB | `src/cadrumo/_data/registry/aeat/m303_orden_anual/censuses.json` | D |
| 12,198 | 0.3 MB | `docs/_sequences/how-to/modelo-390/modelo-390-annual-2025.json` | A |
| 11,538 | 4.8 MB | `src/cadrumo/_data/corpus/manuals/renta/2023/part1/source.pdf.extracted.json` | B |
| 11,072 | 0.3 MB | `docs/_sequences/how-to/modelo-390/modelo-390-supply-binding.json` | A |
| 10,032 | 4.4 MB | `src/cadrumo/_data/corpus/manuals/renta/2022/part1/source.pdf.extracted.json` | B |
| 9,360 | 3.7 MB | `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.json` | B |
| 9,156 | 4.0 MB | `src/cadrumo/_data/corpus/manuals/renta/2021/part1/source.pdf.extracted.json` | B |
| 8,808 | 3.5 MB | `src/cadrumo/_data/corpus/manuals/renta/2020/part1/source.pdf.extracted.json` | B |
| 8,700 | 3.7 MB | `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.json` | B |
| 8,102 | 0.3 MB | `docs/_sequences/how-to/verification-reports/verification-reports-incomplete.json` | A |
| 5,220 | 2.3 MB | `src/cadrumo/_data/corpus/manuals/sociedades/2025/source.pdf.extracted.json` | B |
| 5,124 | 2.3 MB | `src/cadrumo/_data/corpus/manuals/sociedades/2024/source.pdf.extracted.json` | B |

Byte-heavy but under the line threshold (family C): 38 `_generation.provenance.json` manifests totalling 26 MB, largest `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes/export/_generation.provenance.json` at 10.9 MB on one line. Family B also has two siblings per PDF that are not JSON-line-heavy but repeat the same text: 105 `*.pdf.extracted.md` (45.6 MB) and 141 `*.pdf.corpus_text.json` under `src/cadrumo/_data/manual_corpus_text/` (47.9 MB).

History only, already deleted from the tree (family E): `tmp-facts-lane-c.json` (106,133 lines, added `6dc7a94d21`), `unr.json` (18,378 lines, added `f46f4ff4d3`), `dev/quality/registry_facade_family_census.v1.json` (40,221 lines), `dev/quality/registry_authority_consumer_census.v1.json` (10,440 lines), `src/aeat/domain/calculations/registry/tests/_inline_fragment_baselines/*.json` (up to 16,497 lines), `src/cadrumo/_data/terminology/evaluation/coverage-report.json` (8,483 lines), `src/cadrumo/_data/terminology/relevance/relevance.json` (6,211 lines), and two `aeat_official/manuals/modelo_200/files/*.pdf.extracted.json` copies later moved under `corpus/manuals/sociedades/`. `dev/quality/metadata/import_boundary_ratchet.json` (28,535 lines at peak, 4,207 now) and `dev/registry/generated/714-binding-id-address-map.json` (21,219 at peak, 1,330 now) have already been reduced below the threshold.

### A. Documentation sequence goldens (`docs/_sequences/**.json`)

These are recorded CLI transcripts written only by the sequence refresh CLI (`dev/docs/sequences/golden_store.py`). The docs build renders each reader-facing frame's full envelope into the page (`dev/docs/sequence_directive.py:178`). They are necessary: they are the behaviour-change review surface and the docs build input. Their size, however, is not intrinsic to the docs. It comes from four `--format json` frames whose envelopes each carry a whole-modelo list:

- `app modelo work calculate` for Modelo 100 returns `result.observations`, 1,817 entries and 893 KB, although the page's expectations read three `casilla_values` keys.
- `app modelo work observations --modelo 100` returns the same 893 KB list.
- `app modelo requires 100` returns `result.optional_manual`, 1,979 entries and 980 KB, of which the page explains only the derived buckets.
- The same Modelo 100 observations list is therefore stored three times, in `modelo-100-renta-2025.json`, `review-values-relation.json` and `modelo-100-inspect-inputs.json`.

Governing authority already exists. The docs CLI sequences ADR's output weight amendment (lines 31 to 70) sets A3: a reader frame uses text output unless a capture or expectation needs JSON, and a result frame uses the narrowest command whose payload carries its claim. It sets A4: a named advisory above 64 KiB. The approved output weight plan closed S01 to S04 today, and removed setup output and inline payload duplication. The four frames above survived because they legitimately need JSON for `@capture` or `@expect`, and no narrower command exists. They are the remaining A4 advisories.

Options, not decided here:

- Narrow the product surface. For example, `work calculate` could leave the observation list to `work observations`, and `observations` and `requires` could take a casilla or state filter. This benefits every CLI user as well as the goldens. It changes public command contracts, so it needs its own decision, and a filter must not hide missing inputs under the no-silent-under-declaration rule.
- Point the pages at narrower existing commands. This is bounded by what the CLI offers today.
- Rejected by the governing ADR: truncating displayed output, and content-addressed deduplication across goldens.

The evidence favours narrowing the product surface, since the golden weight mirrors what a reader is actually shown.

### B. PDF text extraction sidecars

Each manual PDF carries up to three committed derivatives of the same text:

- `*.pdf.extracted.json`: provenance plus pre-chunked `units` (`dev/docs/preprocess/sidecar.py:40`).
- `*.pdf.extracted.md`: the units rendered as Markdown for the retrieval indexer (`dev/docs/preprocess/sidecar.py:37`, `dev/docs/preprocess/schema.py:36`).
- `*.pdf.corpus_text.json`: a separately extracted, normalised, lower-cased copy used by the evidence validator. It is platform-stamped (`win32`) and falls back to live extraction when refused (`dev/corpus/manual_corpus_sidecar.py:35`).

For Renta 2025 part 1 these are 3.9 MB, 3.4 MB and 3.4 MB of the same 3.4 M characters. All three ship in the wheel (`pyproject.toml:390` to `pyproject.toml:408`), where the source PDFs do not. They are regenerable from the committed PDFs, which are byte-pinned evidence.

They are needed at runtime or in gates, so they cannot simply be deleted. Options:

- Keep one canonical extraction (the units JSON) and derive the Markdown and normalised text from it at build time or on first use. The Markdown is a pure rendering of the units. Whether the normalised text equals `normalise_corpus_text` over the units was not verified: the local interpreter could not import `cadrumo`. If it does not, the two extractors must first converge.
- Store sidecars with one unit per line, compact, so a re-extraction diff is readable line by line rather than a pretty-printed tree.
- Generate the sidecars during the wheel build instead of committing them. This removes about 140 MB from the tree but moves pypdfium2 into the release path and loses the committed diff that shows an extraction change.

The data provenance consolidation ADR already expects derived artifacts to name their input digest and producer, which all three do. It does not settle whether derived text is committed.

### C. Export generation provenance manifests (`_generation.provenance.json`)

These are generator output under `src/cadrumo/_data/registry/aeat/**/export/` (`dev/registry/compiler/export_fragment_grammar.py:28`). They are read only by development analyses and tests, such as `dev/registry/analysis/fabricated_required_ness.py:80` and `dev/registry/tests/test_render_check.py:77`, and are excluded from the wheel with the rest of `registry/aeat`. For each exported field, `field_derivations` restates the emitted field, the parsed record-design row and the semantic-map entry: three copies of facts that already live in the export TOML, the record-design corpus and the semantic map. The Modelo 200 manifest compresses to 3.9% of its size. It is minified onto one line, so any change is a one-line 10 MB diff.

Options:

- Store per-field input digests and a derivation code, not full copies, and let analyses rehydrate through the canonical loader.
- Emit it pretty-printed or line-per-derivation so diffs are reviewable.
- Stop committing it and regenerate it in the gates that read it. This conflicts with render check's committed-manifest comparison and would need that gate redesigned.

The evidence favours digest references. It removes the duplication and the review problem together.

### D. Annual Orden census cache (`m303_orden_anual/censuses.json`)

This is a committed build cache of a pure function over digest-pinned BOE HTML. It avoids about 1.6 s per warm authority load, and the runtime falls back to full extraction on any mismatch (`dev/registry/compiler/m303_orden_census_artefact.py`, module docstring). It is necessary as a performance artifact but not as evidence. At 0.6 MB it is the smallest problem. Compact one-record-per-line serialisation would cut about 20% and keep it diffable. Generating it at build time is also safe, because the reader already refuses a stale or absent cache.

### E. Deleted history

Several blobs are scratch or retired artifacts: `tmp-facts-lane-c.json` and `unr.json` at the repository root were plainly accidental. Removing them from history needs a history rewrite (`git filter-repo`) and a force-push of `main`. That invalidates every clone, open branch and worktree, and the repository's no-destructive-git rule forbids it. All deleted oversized JSON together occupies 1.9 MB of the compressed pack. The trade is not worth it. The durable fix is prevention: a size gate, plus ignore rules for root-level scratch files.

### Prevention

No gate currently fails on a new oversized committed data file. The sequence A4 advisory is sequence-specific and advisory only. A gate that walks the current source tree, not the Git index, per the quality-gates rule, and refuses any JSON above a line or byte ceiling unless its path belongs to an enrolled generated family, would keep new oversized files from landing unnoticed. Generated families could also be marked `linguist-generated` in `.gitattributes` so that GitHub collapses them in pull request diffs. That is presentation only and does not reduce size.

### Not investigated

- Corpus binaries (PDF, XLS, XLSX), which are the largest cost in both the tree (370 MB) and the pack. They are byte-pinned legal evidence and outside this JSON scope. Git LFS or moving them into the `cadrumo-data-*` companion distributions' own repository would be a separate decision.
- `.vault/` weight (45 MB, 5,359 files).
- Non-PDF `*.extracted.*` sidecars (HTML normatives, 90 MB), which follow the family B pattern.

## Sources

- `dev/docs/sequences/golden_store.py` (module docstring: golden storage policy)
- `dev/docs/sequence_directive.py:178` (full envelope rendered to the page)
- `docs/_sequences/contracts/how-to/modelo-100/modelo-100-renta-2025.seq`
- `docs/_sequences/contracts/explanation/how-renta-is-assembled/renta-assembly-requires.seq`
- `dev/docs/preprocess/sidecar.py:37`, `dev/docs/preprocess/sidecar.py:40`
- `dev/docs/preprocess/schema.py:36`
- `dev/corpus/manual_corpus_sidecar.py:35`
- `src/cadrumo/application/corpus_search/runtime.py:53`
- `pyproject.toml:390`
- `dev/registry/compiler/export_fragment_grammar.py:28`
- `dev/registry/analysis/fabricated_required_ness.py:80`
- `dev/registry/tests/test_render_check.py:77`
- `dev/registry/compiler/m303_orden_census_artefact.py`
- commits `8099d7d966`, `6dc7a94d21`, `f46f4ff4d3`
