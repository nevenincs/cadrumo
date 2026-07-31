---
tags:
  - '#audit'
  - '#corpus-data-hydration'
date: '2026-07-21'
modified: '2026-07-21'
body_hash: 'sha256:94209545e3eb5bb3a43337b670cd9bf852aef15017501e4a4e81d540a6a0b4fa'
related: []
---

# `corpus-data-hydration` audit: Supported-period official corpus completion

## Scope

Audited the 2023-2026 supported-period hydration of official AEAT taxpayer calendars,
manuals, record designs, extracted sidecars, registry source references, and corpus
packaging boundaries. The review checks source-byte integrity, matrix applicability,
extraction freshness, `.xlsm` handling, test quality, and isolation from unrelated
worktree changes.

## Findings

### corpus-size-budget | high | Hydration exceeds both the total-data and compact-runtime budgets

The real size-budget gate is red after the hydration: `src/cadrumo/_data` measures
587.9 MiB against the accepted 550 MiB ceiling, and the compact-runtime slice measures
245.2 MiB against its 230 MiB ceiling. The companion wheels themselves remain below
the package-index cap (76.7 MB for manuals and 80.3 MB for official data), but those
successful compressed-artifact measurements do not authorize bypassing the reviewed
uncompressed-tree budgets. The change cannot close with this required gate failing.

### shared-build-snapshot | medium | Packaging parity compares different source snapshots in a dirty shared worktree

The companion parity gate derives its expected inventory from `git ls-files` while the
Hatch build hooks scan the live working tree recursively. In the current review this
made `test_companion_packages_exactly_its_owned_subtree` fail with 52 "extra" official
members: the files are valid hydration outputs, but they are untracked during the
pre-commit review and therefore exist only on the build side of the comparison. The
same split can sweep unrelated peer work into built artifacts, so a pass or failure in
this always-dirty shared worktree is not isolated evidence for the reviewed pathset.

### corpus-suffix-taxonomy | medium | The new `.xlsm` route leaves downstream suffix contracts inconsistent

The extractor, preprocess hook, root wheel and sdist excludes, companion hooks, and
primary artifact tests now handle real `.xlsm` files correctly. Two downstream
contracts still drift: `_classify` in `dev/docs/preprocess/_golden_queries.py` does not
recognize `.xlsm` as a corpus or Diseño source, so the retrieval trust gate can reject
a valid Modelo 220 hit; and the source-binary constants in
`src/cadrumo/tests/test_wheel_content_boundary.py` and
`src/cadrumo/tests/test_data_size_budget.py` omit the already-supported `.docx` and
`.zip` types even though both exist in the tracked corpus and are excluded to the
official companion. The latter misclassifies those bytes into the runtime budget and
makes the narrower wheel assertion unable to detect those leak types.

### record-design-currentness | medium | The sync gate cannot detect changed or newly published official sources

`dev/packaging/sync_aeat_record_design_corpus.py` treats the 53-entry `_REQUIRED`
tuple as the completeness authority and skips every URL already present in a manifest
when `--pull` runs. Its default `check()` only rehashes local files against their local
manifests. Consequently, a mutable AEAT URL can change, or a new supported-period link
can appear on an official index, while both `--pull` and
`test_supported_record_design_corpus_is_complete_and_current` still report success.
The page inventory is also incomplete: `_PAGES` contains nine pages, while the root
manifest records ten and the omitted historical Modelos 01-99 page currently exposes
five links for supported corpus modelos. An independent live review found no current
data loss -- 59 current supported-model URLs matched the raw manifested bytes and the
2023-2026 historical window was present -- but that evidence is not reproduced by the
committed gate.

### supported-window-union | medium | The matrix regression proves overlap, not complete supported-period coverage

`test_supported_period_matrix_has_applicable_record_design_sources` passes a model-year
when any source overlaps any part of the year. A source valid for only one day would
satisfy the assertion even if the rest of the filing year were uncovered. The test also
duplicates a nine-model table rather than deriving required windows from the validated
registry authority and evaluates aggregate modelo refs instead of the refs on the
revision active for each filing period. The currently added references cover their
intended 2023-2026 windows, but the regression can admit a future intra-year gap or omit
another supported family without failing.

### xlsm-extractor-contract-docs | low | XLSM behavior is implemented and tested but omitted from extractor documentation

The workbook dispatcher, preprocess rule, real `.xlsm` parity test, and committed
sidecars are coherent, but `dev/docs/preprocess/_workbook.py` still states that the
corpus has only two workbook formats and documents `build_outputs` and
`extract_workbook` as accepting only `.xls` or `.xlsx`. That contract is now inaccurate
for the newly supported `.xlsm` path.

### supported-family-discovery | medium | The remediated matrix still cannot detect an entirely missing family

The supported-window regression now selects production revisions, evaluates their own
record-design refs, and checks the complete day-union rather than a single overlap.
However, it discovers its required matrix only after filtering each revision to refs
that already resolve to `kind = "record_design"`, and immediately skips the revision
when that list is empty. Removing or omitting every record-design ref from an otherwise
supported revision therefore removes that family from `checked`; the global non-empty
assertion remains satisfied by unrelated modelos. The explicit annual-2026 exception
table independently anchors six families, but no equivalent authority anchors the
remaining required families, so the prior omission risk remains open.

### modelo-202-source-currentness | medium | The active revision remains bound to the superseded version 1.2 workbook

The hydrated Modelo 202 manifest now contains the official 14 July 2026 version 1.3
workbook for exercise 2025 and following, but `aeat-dr-202-2025` and both the modelo and
active `2025-y-siguientes` revision still reference the 17 March 2026 version 1.2 bytes.
Production extraction reports the same three sheets and the same 116 field definitions,
so no positional-layout drift was observed, but the authoritative text did change:
version 1.3 replaces the version 1.2 exercise-specific rate list with the official rate
reference for tax periods 2025 and following. Catalogue-integrity and applicability
tests remain green because they validate the internally coherent older source entry,
not whether the active registry ref selects the newest manifested official revision.

### renta-2025-manual-currentness | medium | The bundled Part 1 manual has drifted behind its mutable official URL

The bundled Renta 2025 Part 1 PDF, its manifest, its generic text sidecar, and registry
source `aeat-renta-2025-manual-parte1` identify the 7,543,283-byte PDF with SHA-256
`60e6b2d71c97d93a9e0943e6ff8c886f4dd6d3741a797cb8001dcbcadfb33528` fetched on
12 April 2026. The same official AEAT URL now returns an 8,554,799-byte PDF with SHA-256
`02c6e8300a7f56c8c24aa947d4c39c5657c9a9eda6f5d727d44b4112d7de15d4` and a
20 May 2026 `Last-Modified` timestamp. The active Modelo 100 2025 revision and its
calculation evidence still cite the older source. Local extraction and catalogue gates
remain green because none downloads and byte-compares mutable manual URLs.

### pdf-sidecar-content-freshness | medium | Generic PDF text sidecars are hash-linked but not extraction-parity checked

The generic `.pdf.corpus_text.json` checker proves that each payload is schema-valid,
non-empty, and records the current bundled PDF hash. It does not regenerate
`normalised_text` with the production extractor or compare the committed text to a
derived digest. A truncated or incorrect non-empty text payload carrying the correct
PDF hash therefore passes both the extraction command's check mode and the committed
freshness test, while runtime legal-evidence validation trusts that text.

### manual-matrix-explicitness | medium | The required manual matrix omits Renta Part 2 and silent 2026 publication exceptions

The explicit supported-manual regression anchors IVA and Renta Part 1 for 2023-2025
and Sociedades for 2024-2025. It does not anchor the separately published Renta Part 2
autonomic-deductions manuals for 2024 and 2025, so deleting both one of those PDFs and
its sidecar would evade the generic existing-PDF check. Its exclusive ranges also stop
at 2025 without explicitly classifying the not-yet-published 2026 annual IVA, Renta,
and Sociedades editions, leaving absence indistinguishable from an intentional support
boundary.

## Recommendations

- For `corpus-size-budget`, keep the gate red until a reviewed decision either
  authorizes new total/runtime ceilings with current measurements or repartitions the
  derived payload; then rerun the real size-budget tests and record the green values.
- For `shared-build-snapshot`, build and inventory one identical immutable temporary
  source snapshot assembled from the explicitly reviewed pathset (or an equivalent
  explicit Git tree), rather than mixing `git ls-files` expectations with a recursive
  live-worktree build. Do not use stash, reset, restore, or clean to obtain isolation.
- For `corpus-suffix-taxonomy`, add `.xlsm` to the golden-source classifier and cover it
  with a direct classification/evaluation test. Make the packaging and budget gates
  derive one complete suffix set from the shipping contract, or at minimum include
  `.docx`, `.pdf`, `.xls`, `.xlsm`, `.xlsx`, and `.zip` consistently and assert each
  currently represented type.
- For `record-design-currentness`, add an explicit live-audit mode that crawls all ten
  official current and historical index pages, derives the supported-period URL set,
  downloads raw official artifacts even when their URL is already known, and reports
  additions or byte drift against manifests. Keep the deterministic offline unit gate,
  but name it as local integrity and require the live audit as recorded release evidence.
  The live comparison must select raw artifacts rather than LibreOffice-derived siblings
  that intentionally retain the original source URL.
- For `supported-window-union`, derive required modelo/revision/filing windows from the
  validated registry authority, union every applicable source interval, and assert that
  the union covers each entire supported filing window. Represent publication-bound
  2026 annual exceptions explicitly instead of omitting families or allowing a prior
  exercise source to satisfy them implicitly.
- For `xlsm-extractor-contract-docs`, update the module and callable documentation to
  list `.xlsm` alongside `.xls` and `.xlsx`, using the repository documentation workflow.
- For `supported-family-discovery`, derive required families from the validated modelo-level
  source authority before inspecting revision refs, then fail when any supported active
  revision lacks its own record-design source instead of skipping it.
- For `modelo-202-source-currentness`, bind the active Modelo 202 source, modelo manifest,
  and revision to the official July 2026 version 1.3 workbook and add a regression that
  prevents an older manifested revision from remaining authoritative.
- For `renta-2025-manual-currentness`, replace the bundled PDF with the current official
  bytes, regenerate every canonical and generic extraction, refresh manifest and registry
  integrity metadata, and add a live manual-byte audit analogous to record-design currentness.
- For `pdf-sidecar-content-freshness`, make check mode regenerate production PDF text and
  require exact normalised-text parity, or validate a production-derived text digest that
  cannot be satisfied by merely copying the source PDF hash.
- For `manual-matrix-explicitness`, add Renta Part 2 for 2024-2025 to the required edition
  table and encode explicit self-expiring 2026 publication-bound exceptions for each annual
  manual family.
