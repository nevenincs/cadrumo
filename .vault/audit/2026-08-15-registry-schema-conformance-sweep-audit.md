---
tags:
  - '#audit'
  - '#registry-schema-conformance-sweep'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:19cf0d3b422919849ef86992acb07a8dd2d9852d155574e01b129b480990d1e1'
related:
  - "[[2026-08-14-registry-campaign-sequencing-operator-attestation-ledger-audit]]"
---

# `registry-schema-conformance-sweep` audit: `Provenance-schema parallel lanes: review_status vocabularies and the sidecar-mechanism split`

## Scope

Operator directive: sweep the keys, file structures and mechanisms the registry
uses to measure its own state for parallel lanes -- one concept with two
homes, two spellings, or two mechanisms -- and for superfluous claims, schema
declaring something nothing consumes. This document persists the findings
from one bounded pass: the `review_status` field family across the registry
provenance/governance schema, and the disenos_registro sidecar-mechanism
split. Every claim below was corroborated against the live tree (loaded
`bundled_authority()`'s underlying loader, enumerated real catalogue
entries, grepped every consumer, or ran the actual gate) rather than trusted
from semantic search or a prior note. Nothing was edited to produce this
document; nothing under `modelos/**` was touched.

## Findings

### review-status-four-vocabularies | medium | `review_status` names four typed vocabularies under one field, and 35.5% of its instances are structurally inert

**Where:** `core/_revision_review.py` (`RevisionReviewStatus`), `core/_legal_review.py`
(`LegalReviewStatus`), `domain/calculations/registry/_schema_base.py:391`
(`ReviewStatus = Literal["reviewed"]`), `application/ledger/_models.py`
(`LedgerReviewStatus`, a different domain, noted but not itself a finding).

**What was measured, against the live loaded registry:** 633 `LegalReference`
entries (220 `operator_reviewed` / 413 `agent_reviewed` -- a real, varying,
gated distribution) versus 321 `SourceReference` and 28 `LegalParameter`
entries, both typed `ReviewStatus`, both **100% `"reviewed"`** because no
other value is typeable. 349 of 982 total `review_status`-bearing registry
entries (35.5%) carry a field that cannot vary. Confirmed by grep across all
of `src/` that every production `.review_status` read (`_coverage.py:772,776`,
`_legal.py:101`, `_snapshot.py:363,365`, `_schema.py:1298`,
`application/registry/_conformance.py`) resolves to `RevisionReviewStatus`
or `LegalReviewStatus`; zero production code reads `SourceReference.review_status`
or `LegalParameter.review_status`.

**The hazard is not dead code alone.** The field is REQUIRED (no default) on
both `SourceReference` and `LegalParameter`, so 349 authors hand-typed a
no-op, and it sits under the identical name as the field that gates filing
on the neighbouring `LegalReference` class in the same schema module. A
reader has no local signal distinguishing the live gate from the inert
constant next to it -- the same hazard as a revision name promising
coverage its selector does not carry.

**Split ruling reached by checking each type's actual integrity mechanism
rather than applying one answer to both** -- see the two findings below.

### source-reference-review-status-superfluous | low | hash-pin integrity makes `SourceReference.review_status` add nothing; ruled for removal, queued behind an in-flight migration

**Where:** `domain/calculations/registry/_corpus_catalogue.py:37-64,160-172`
(`verify_source_file`, `verify_source_catalogue`); wired into production at
`domain/calculations/registry/_validate.py:205`, inside the registry
validator's catalogue-failure check, exercised whenever `source_root` is
set (the normal production configuration).

**What was confirmed:** `verify_source_file` computes `hash_file` on the
resolved corpus path and raises `RegistryValidationError` on either a byte-count
mismatch or a sha256 mismatch against the declared `SourceReference.bytes`/
`sha256`. `verify_source_catalogue` runs this for every source in the
catalogue. This is not a test-only helper -- a bad hash fails the registry
build. A `SourceReference` names a document, and the hash pin is the live,
verified guarantee that the bundled bytes are the ones declared; human
review of "is this the right file" adds nothing a byte-exact hash does not
already assert.

**Ruling:** superfluous. Remove the field and its 321 declarations. **Queued,
not immediate** -- the removal is a schema change plus stripping every
declaration, and another agent is mid-flight on a structurally identical
schema-plus-data migration in an adjacent module; landing both concurrently
is the collision shape that produced tonight's other findings. Lands after
that migration closes.

### legal-parameter-review-status-unbuilt-capability | high | `LegalParameter.review_status` is not a document pointer's integrity field -- it is the missing gate on 28 transcribed regulatory values

**Where:** `domain/calculations/registry/_schema_references.py:272-284`
(`LegalParameter`); 28 entries in the bundled legal-parameter catalogue,
enumerated below in full.

**Why the hash-pin argument above does not reach this class.**
`LegalParameter` carries no `sha256`, no `bytes`, no `corpus_path` -- it is
not a pointer to a document at all. It is a **transcribed value**: a rate, a
threshold, a euro amount, or a code-set, extracted by a human or an agent
from a cited provision and typed directly into the registry
(`value: str`, `unit: str`), grounded only by its own `legal_refs`. Nothing
about a hash can verify that `"0.35"` is the correct percentage `ley-35-2006:art-101`
actually states -- that is exactly the class of claim `LegalReviewStatus`
exists to gate for a `LegalReference` citation, and `LegalParameter` cannot
participate in that gate because it is typed to the dead `ReviewStatus`
constant instead.

**All 28 entries, named as required, grouped by governing provision:**

- `ley-35-2006:art-101` / `rd-439-2007:art-80` (administrador retention, 3
  parameters): `lirpf-art-101:retencion-administrador-general` (0.35),
  `lirpf-art-101:retencion-administrador-incn-umbral-eur` (100000),
  `lirpf-art-101:retencion-administrador-reducida` (0.19).
- `ley-35-2006:art-31` (1 parameter):
  `lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur`
  (250000).
- `ley-35-2006:art-85` (3 parameters):
  `lirpf-art-85:catastral-revision-lookback-years` (10),
  `lirpf-art-85:imputacion-rate-old-or-no-revision` (0.02),
  `lirpf-art-85:imputacion-rate-recent-revision` (0.011).
- `ley-35-2006:dt-32` (3 parameters):
  `lirpf-dt-32:eo-exclusion-compras-eur` (250000),
  `lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur` (250000),
  `lirpf-dt-32:eo-exclusion-rendimientos-factura-eur` (125000).
- `ley-37-1992:art-161` (4 parameters, recargo de equivalencia rates):
  `liva-art-161:recargo-rate-general` (0.052),
  `liva-art-161:recargo-rate-reducido` (0.014),
  `liva-art-161:recargo-rate-super-reducido` (0.005),
  `liva-art-161:recargo-rate-tabaco` (0.0175).
- `rd-439-2007:art-110` (+ `orden-eha-1274-2007:art-1`, 2 parameters):
  `rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario` (a
  code set), `rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrario-objetiva`
  (a code set).
- `real-decreto-ley-7-2024:art-11.2` / `df-14` / `real-decreto-ley-6-2024:anexo`
  (1 parameter): `rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada-2024`
  (0.25).
- `rd-439-2007:art-95` (+ `orden-eha-1274-2007:art-1` on the selector
  entries, 11 parameters, the largest single cluster): the general/reduced/
  professional/agrarian/forestry retention rates
  (`retencion-actividades-agricolas-ganaderas-general` 0.02,
  `retencion-actividades-estimacion-objetiva` 0.01,
  `retencion-actividades-forestales` 0.02,
  `retencion-actividades-ganaderas-engorde-porcino-avicultura` 0.01,
  `retencion-actividades-profesionales-colectivos-especificos` 0.07,
  `retencion-actividades-profesionales-general` 0.15,
  `retencion-actividades-profesionales-inicio` 0.07) and four M036
  activity-code selectors feeding them
  (`selector-m036-actividades-agricolas-ganaderas`,
  `selector-m036-actividades-forestales`,
  `selector-m036-actividades-ganaderas-engorde-porcino-avicultura` --
  **deliberately empty**, its own `notes` field states the M036 activity
  table cannot discriminate this carve-out and an omission would misread as
  full partition --, `selector-m036-actividades-profesionales`).

**Why this is the same risk class as the campaign's founding finding, in a
quieter register.** The withdrawal-mechanism defect that opened this
campaign hid a capability gap behind a mechanism that looked like a real
refusal. This is the inverse shape: 28 regulatory figures -- IRPF retention
percentages, IVA recargo rates, estimación objetiva exclusion thresholds --
sit in the registry with a field NAMED `review_status`, typed identically to
the field that gates `LegalReference` citations, and it cannot ever record
that a human checked the transcribed number against the cited provision.
Every one of these values already flows into live calculations
(`applies_to` names the consuming concept for each); a wrong transcription
would reach a filed artefact with no mechanism positioned to have caught it,
because the mechanism shaped to catch it exists on the neighbouring class
and was never wired to this one.

**The shape a real gate would take, stated for the record, not built here.**
`LegalParameter.review_status` would need to be re-typed from the dead
`ReviewStatus` literal to a real closed vocabulary shaped like
`LegalReviewStatus` (pending/agent-reviewed/operator-reviewed, or a
purpose-built sibling), paired with `reviewed_by`/`reviewed_at` fields
matching the pairing rule `_validate_legal_review_metadata` already enforces
for `LegalReference`, and a build-time or snapshot-time check analogous to
`_check_snapshot_legal_review_status` that refuses a filing-grade snapshot
depending on an `agent_reviewed`-or-worse parameter. Whether that check
should be as strict as the legal-reference gate, and whether it should be a
new gate or folded into the existing one, are design and attestation
decisions the operator owns -- not decided or implemented here.

### disenos-registro-sidecar-split | low | two independent sidecar mechanisms cover disenos_registro PDFs; the gap in one is fully closed by the other

**Where:** `_data/corpus/tests/test_extraction_sidecar_freshness.py` (the
gate); `_data/corpus/aeat_official/disenos_registro/**` (81 PDFs);
`_data/manual_corpus_text/aeat_official/disenos_registro/**` (the mirror
tree); `application/corpus_search/_lexical_index.py` (scoped elsewhere,
checked and ruled out below).

**What was traced, per the operator's question -- for each consumer, does a
missing co-located `.extracted.json`/`.extracted.md` sidecar error, degrade
silently, or not matter:**

- **The design-relayout/box-offset detectors: not matter.** They parse the
  PDF binary directly (`extract_record_design_pdf`) and fall back to the
  `.extracted.md` derivative only when that parse fails. A missing sidecar
  is invisible to this consumer by design, confirmed by reading the parser
  dispatch, not assumed.
- **The committed-sidecar-workbook gate (`test_every_record_design_workbook_has_extraction_sidecars`):
  not applicable to PDFs.** Its own suffix set is `{.xls, .xlsm, .xlsx}` --
  PDFs are excluded from this gate's scope entirely, by design, not by an
  accidental miss. Ran the full sidecar-freshness test module: this test and
  seven of its nine siblings pass.
- **The shipped-search text corpus (`manual_corpus_text/`, gated by
  `test_every_corpus_pdf_has_a_corpus_text_sidecar`): fully covers the
  gap.** This is a SEPARATE, parallel sidecar convention -- a `.corpus_text.json`
  file in a directory tree that mirrors `_data/corpus/` rather than a
  co-located file next to the source. Counted directly: 81 disenos_registro
  PDFs, 81 `.corpus_text.json` mirrors, zero missing -- including all 24
  PDFs that lack the co-located `.extracted.json`/`.extracted.md` pair. The
  gate that enforces this (same test file) passed in the same run.
- **The legal-citation lexical search index
  (`application/corpus_search/_lexical_index.py`): not applicable.** Its
  own module-level constant scopes it to `corpus/normatives/html` only
  (`_CORPUS_HTML_PARTS`); it never reads `disenos_registro` at all.

**Conclusion: no silent degradation found for the 24 PDFs.** The apparent
gap reported in the prior pass of this sweep is real as a STRUCTURAL fact
(two sidecar conventions exist for the same artefact class, exactly the
parallel-lane shape named in the operator directive) but does not currently
cause invisibility for any consumer checked: one mechanism deliberately
excludes PDFs from its scope, the other fully covers every PDF including
the 24. Reporting the clean trace rather than either overclaiming urgency
or dropping the structural finding for looking harmless.

**One genuine gap surfaced during the trace, smaller in scope:** the sole
`.docx` in the corpus (`disenos_registro/modelo_349/files/02-349-orden-eha-769-2010-modificada-por-orden-eha-1721-2011-43-9-kb-docx.docx`)
has zero sidecar coverage under either mechanism, but it is also not cited
by any `SourceReference` in the legal catalogue at all (grepped every
`legal/*.toml` file; zero hits) -- it is acquired inventory recorded only in
`disenos_registro/modelo_349/manifest.json`, never promoted to a registered
source. Lower urgency than a wired-in gap: nothing currently reads it, so
there is no active mechanism silently degrading. Worth a registration
decision, not an emergency.

**Incidental, out of scope, flagged rather than chased:** running the
sidecar-freshness test module surfaced one currently RED test unrelated to
this sweep, `test_normative_html_sidecars_equal_current_production_extraction`,
failing on 20+ files under `corpus/normatives/html/` (BOE conventions,
modelo-145 amendments, an RDL 4/2024 IVA file) -- a drift between committed
sidecars and the live HTML extractor, not a disenos_registro or
`review_status` matter. Not investigated further here; named so it is not
lost.

### design-discovery-glob-mismatches | high | three named glob mismatches, measured: one live and unfixed, one already fixed, one dormant -- plus a fourth enumeration surfaced in the process

**Method note:** every claim below is the actual symmetric difference between
two enumerations, measured by running both against the live bundled tree,
not an argument that two patterns look equivalent.

**Mismatch 1 -- the guard sharing the collector's blind spot: FIXED in the
canonical pair, LIVE AND UNFIXED in a third module.** The originally-reported
pair -- `_design_sources()` in `test_revision_span_matches_published_designs.py`
(collector) and the guard in `test_every_bundled_design_is_read_or_reported.py`
-- were both independently rewritten to `directory.rglob("*")`, confirmed by
reading both implementations; the guard module's own docstring names the
exact prior defect ("it derived its 'what is on disk' set with the SAME
`files/*` glob shape the inventory used... A check that shares its subject's
blind spot is worse than no check"). That pair is closed.

**But a third, separate enumeration of the same corpus still carries the old
shape.** `_record_design_pdf_files()` in
`domain/calculations/registry/tests/_record_design_support.py:142` uses
`_RECORD_DESIGN_ROOT.glob("modelo_*/files/*.pdf")` -- fixed-depth, unfixed.
Measured directly: 80 PDFs found by this glob against 81 by a full
`rglob("*.pdf")`; the symmetric difference is exactly one file,
`modelo_210/dr210_2011.pdf` -- the same file the other two enumerations were
fixed to see. This function backs a real coverage assertion,
`test_record_design_pdf_corpus_is_discovered_and_parseable` in
`test_record_design.py:800`, whose own comment states its purpose is so "a
rename/removal trips this gate rather than silently shrinking the corpus" --
but the corpus it asserts over is already one file short, silently, before
any rename or removal happens. A sibling gate in the same file,
`test_registered_record_design_sources_are_discovered_and_parseable`
(line 821), is NOT affected -- it enumerates from `catalogues.sources`
(the registered `SourceReference` entries) rather than the filesystem glob,
and `dr210_2011.pdf` IS registered there (`legal/irnr.toml:699`), so a
parsing regression on that specific file would still be caught by the
sibling gate. The blindness is real and live, but partially, not fully,
mitigated by a second gate that happens to enumerate a different way.

**A fourth enumeration, found while tracing the third, carries the same
fixed-depth shape and is currently dormant, not live.**
`_design_files()` in `test_rate_specific_box_pins_its_rate.py:95` uses
`directory.glob("files/*.extracted.md")` per modelo. Measured: 188 files
found by this pattern against 188 by a full `rglob("*.extracted.md")` --
zero difference today, because no `.extracted.md` sidecar currently sits
outside a `files/` directory (`dr210_2011.pdf` itself has no sidecar at all,
per the earlier finding in this document). The pattern is structurally
identical to the fixed one and would go blind the moment a sidecar is
generated for a design stored outside `files/` -- exactly the shape that
already bit twice.

**Mismatch 2 -- `.xlsm` in `_DESIGN_SUFFIXES`: NOT a live gap. Already
fixed, confirmed present.** Read the current definition directly:
`_DESIGN_SUFFIXES = (".xlsx", ".xlsm", ".xls", ".pdf")` at
`test_revision_span_matches_published_designs.py:210`, with a docstring
explaining the prior omission dropped two Modelo 220 designs "for no reason
anyone chose." Confirmed both bundled artefacts exist:
`modelo_220/files/02-220-ejercicio-2022.xlsm` and
`.../03-220-ejercicio-2023.xlsm`. Checked every other suffix set touching
design discovery for the same gap: `_PARSEABLE_SUFFIXES` in
`test_every_bundled_design_is_read_or_reported.py` already includes
`.xlsm`; the `SourceReference` schema validator's
`allowed_record_design_suffixes` in `_schema_references.py` already
includes `XLSM_EXTENSION`. Reporting this as closed rather than silently
confirming nothing, since the operator directive asked for the state to be
said plainly either way.

**Mismatch 3 -- `rglob` guard vs `glob` collector in `_loader.py`:
confirmed DORMANT, and the wake condition is named.** The pair is
`_require_revision_section_fragments` (`_loader.py:502-505`, recursive
`section_dir.rglob("*.toml")`, a non-emptiness guard raising
`RegistryLoadError` if a section directory has no TOML anywhere beneath it)
against `_revision_section_fragment_paths` (`_loader.py:508-509`,
non-recursive `section_dir.glob("*.toml")`, the actual collector feeding
the loader). Measured across every revision section directory in the
bundled tree -- 982 directories under `modelos/*/revisions/*/*` -- for a
TOML fragment visible to `rglob` but not to `glob`: zero found. Dormant is
confirmed, not assumed.

**What would wake it, stated as asked rather than left implicit:** a TOML
fragment placed in a sub-subdirectory of a revision's section directory
(e.g. `casillas/some-subfolder/extra.toml` instead of `casillas/extra.toml`)
would be seen by the emptiness guard (which would correctly report the
directory non-empty and let the load proceed) but silently excluded from
the actual collector feeding the loader -- the guard would give false
confidence that the section loaded completely while the nested fragment's
content never reaches the compiled revision. This is the same shape as
Mismatch 1, but where Mismatch 1's guard was blind to a whole FILE,
Mismatch 3's guard would be blind to the exclusion of a file its own
non-emptiness check had just certified present. No currently-bundled
fragment triggers it; whether any author-facing convention would ever place
a fragment at that depth is a question for whoever owns the loader's
directory-shape contract, not settled here.

**The sentence that names this failure mode precisely, preserved verbatim:**
the guard actively certifies "fine" over the exact gap it cannot see into.
That is strictly worse than Mismatch 1's shape. Mismatch 1 is a blind
counter -- it undercounts and says nothing. This is an affirmative all-clear
issued by something structurally incapable of checking the region it
clears. If it ever wakes, it reads as a passing gate over a silently
truncated revision -- a false green in the sense the operator has ruled
against: a signal reporting agreement where none exists, on the exact axis
someone would trust it for.

### form-spec-record-design-dual-convention | medium | two `SourceReference.kind` values are genuinely distinct and load-bearing; three mislabelled entries reclassified, one left open, 129 corpus files found unregistered by either

**Where:** `SourceReference.kind` (`_schema_references.py`), the hard dispatch
in `resolve_record_design_binary`
(`domain/calculations/registry/_corpus_catalogue.py:67-111`, line 93 refuses
any source whose `kind != "record_design"` regardless of file content),
`legal/irnr.toml`, `legal/modelo-280.toml`, `legal/modelo-345.toml`,
`legal/monedas-virtuales.toml`.

**What was measured before acting.** Cross-tabulated the full population:
145 `form_spec` + 80 `record_design` = 225 entries. `resolve_record_design_binary`
is confirmed load-bearing (a hard `RegistryValidationError`, not a soft
default) but its only production callers are M303-specific -- the gate is
real, currently dormant for every other modelo. Five outliers were found and
split by what actually distinguishes them, not treated uniformly:

- **Modelo 210 (`boe-modelo-210-diseno-registro-2011`) and Modelo 280
  (`aeat-dr-280-2022`): mislabelled `form_spec`, both pointing at a file
  physically inside `disenos_registro/`.** Same concept as every
  `record_design` sibling; the `kind` value alone disagreed with the file's
  own home.
- **Modelo 345 (`aeat-dr-345-2025`): mislabelled AND duplicated.** Registered
  as `form_spec` pointing at
  `corpus/aeat_official/instructions/modelo_345/files/DR_Modelo_345_2025.pdf`,
  while a byte-identical copy (confirmed: same size 331991, same
  sha256 `fb0faaf6...`) already sat unregistered at
  `corpus/aeat_official/disenos_registro/modelo_345/files/01-345-ejercicio-2025.pdf`.
- **Modelo 721 (two entries, `boe-modelo-721-2023-layout` /
  `boe-modelo-721-2024-layout`): genuinely different concept, not a
  mislabel.** Both point at `corpus/normatives/pdf/boe-a-20XX-*-modelo-721-layout*.pdf`
  -- a record layout published as an ANNEX inside the BOE órden's own text,
  not a separate AEAT Diseño de Registro artefact. No
  `disenos_registro/modelo_721/` directory exists at all (confirmed empty
  glob), and no duplicate of either file was found anywhere in the corpus.

**Reclassification applied (authorized).** Modelo 210 and Modelo 280 entries
changed `kind = "form_spec"` -> `"record_design"`, `corpus_path` unchanged.
Modelo 345's entry changed `kind` the same way AND was repointed to the
`disenos_registro/` copy's path, `sha256`/`bytes` left untouched since the
bytes are identical. All three independently verified post-edit: load
through `load_registry_tree`, resolve through `verify_source_file` against
the real bundled bytes, hash-pass. Population moved from 145/80 to a
confirmed live 142/83 form_spec/record_design split. Grepped every
`.kind`-asserting test for these three source ids (`test_modelo_210_diseno_registro.py`,
`test_modelo_345_grounding.py`, `test_modelo_280_grounding.py`): zero
matches. Ran those three files plus `test_catalogue_verification.py`
(12 failures, 21 passed) and traced every failure's actual assertion: all
twelve are the registry's standing pre-existing tree-wide refusal (undeclared
`authority_grade`/missing export layout across ~97 revisions, the operator's
explicit "refuses at load" ruling), raised by `RegistryValidator.validate_registry`
before any modelo-specific logic runs -- none reference `kind`, `form_spec`,
or `record_design`. The reclassification is confirmed clean.

**Modelo 721: left alone, reported as an open concept question, not ruled
here.** The evidence above is presented for the operator to decide, not
resolved by reflex: is a record layout published inside a BOE órden's own
text the same concept as AEAT's own separately-published Diseño de Registro,
or is the current `form_spec` label correct because the two really do have
different provenance and update cadence (a BOE órden amendment vs. an AEAT
static PDF/XLS republication)? No consumer differential was found either way
-- nothing currently reads M721 through `resolve_record_design_binary`.

**The now-orphaned `instructions/` copy: not deleted, flagged.**
`corpus/aeat_official/instructions/modelo_345/files/DR_Modelo_345_2025.pdf`
is byte-identical to the file the registry now points at under
`disenos_registro/`, and nothing else in the legal catalogue cites it (grepped
every `legal/*.toml`; zero hits after the repoint). Left on disk per
instruction; this is a duplicate-corpus-inventory decision for whoever owns
corpus hygiene, not a registry-schema one.

### disenos-registro-registration-gate-red | high | 129 of 212 bundled record-design files carry no `SourceReference` at all; landed red deliberately, across 28 of 57 modelo directories

**Where:** new gate
`domain/calculations/registry/tests/test_every_bundled_record_design_is_registered.py`,
independently enumerating `disenos_registro/**` by suffix
(`.pdf`/`.xls`/`.xlsx`/`.xlsm`, matching the sibling read/report gate's own
independently-declared set) and comparing against every
`SourceReference.corpus_path` in the live loaded sources catalogue --
deliberately not derived from the parser's or any inventory's own
enumeration, so it cannot inherit either one's blind spot.

**Result, run against the live tree: 129 of 212 files (60.8%) are
unregistered, spanning 28 of the corpus's 57 modelo directories.** Per the
standing project directive this is reported as the initial red set, not
scoped down to pass. The unregistered population is overwhelmingly
**historical/superseded revision-year files** -- filenames carrying an
explicit `ejercicio-YYYY` or a date range (`14-100-ejercicio-2009-...pdf`
through `24-100-ejercicio-2019-...xlsx` for Modelo 100 alone; a comparable
run of years for Modelo 200, Modelo 303 and Modelo 390) sitting alongside a
registered current-year design in the same directory. This matches the
pattern already surfaced in `disenos-registro-sidecar-split` above for the
Modelo 349 `.docx`: acquired corpus inventory that was never promoted to a
registered `SourceReference`, at a scale the sidecar finding's single
example did not suggest. Every one of these 129 files is real, hash-unpinned,
unresolvable through `resolve_record_design_binary`, and invisible to any
consumer that walks the catalogue rather than the filesystem.

**Not adjudicated here.** Whether each file should be registered (as
historical-revision evidence, following the same pattern as currently-live
entries), explicitly marked as deliberately-unregistered acquired inventory,
or removed from the corpus entirely is a per-file or per-modelo authoring
decision, not a schema fix -- the gate's job is to make the gap visible and
keep it visible until an owning decision closes each entry, not to pick the
resolution.

**Partition of the 129, per instruction, before anyone adjudicates it.**
One undifferentiated 129 invites a blanket response in either direction.
Split by whether each file's derived covered year(s) fall inside or outside
the UNION of its modelo's declared revision spans (`valid_from`/`valid_to`,
declared data, read regardless of whether a revision is otherwise
calc-grade) -- this is measurement, not judgement.

**Year-derivation rule, stated so the numbers are reproducible, applied in
this fixed priority per file, first match wins, no guessing past this
list:**

1. `ejercicio(s)?-YYYY-a-YYYY` -> range `[Y1, Y2]`
2. `ejercicio(s)?-YYYY-hasta-YYYY` -> range `[Y1, Y2]`
3. `ejercicio(s)?-YYYY-y-siguientes` -> open range `[Y, unbounded)`
4. `ejercicio(s)?-YYYY-y-YYYY` -> range `[Y1, Y2]`
5. `ejercicio(s)?-YYYY-YYYY` (hyphen-joined, no word) -> range `[Y1, Y2]`
6. `devengos-entre-DD-MM-YYYY-y-DD-MM-YYYY` -> range `[Y1, Y2]`
7. `devengos-a-partir-de-YYYY` -> open range `[Y, unbounded)`
8. `ejercicio(s)?-YYYY` (bare, year sits directly after the marker) ->
   point `[Y, Y]`

Anything where the year does not sit directly after an `ejercicio(s)?`/
`devengos` marker matching one of the shapes above -- including every case
where the year appears only later in the filename (order numbers like
`orden-eha-3435-2007`, amendment dates, KB/MB size suffixes) -- is put in a
third AMBIGUOUS bucket rather than guessed from a bare 4-digit scan of the
whole name, which would also capture order numbers and file sizes as false
years.

**Result: 29 inside, 75 outside, 25 ambiguous of the 129.**

- **INSIDE a declared span (29) -- the hard gap.** The registry claims to
  compute these filing years and the design file naming that year is
  unregistered. By modelo: 036 (3), 111 (1), 115 (1), 122 (1), 123 (2), 130
  (1), 200 (1), 202 (2), 210 (2), 303 (11), 322 (1), 345 (1), 347 (2). Modelo
  303 dominates because its `2009-y-siguientes` revision declares
  `valid_to = None` (genuinely open in the loaded data, confirmed by reading
  `rev.valid_from`/`rev.valid_to` directly) and so overlaps nearly every
  historical-year file the modelo carries; this is the declared span as
  authored, not a judgement that the overlap itself is correct -- the
  `-y-siguientes` naming-versus-bound question for other modelos is the
  finding already routed to recon-temporal-legal, out of scope here.
  **Caveat stated plainly:** "inside" means the file's derived year overlaps
  a declared span: it does not by itself prove no OTHER already-registered
  file also covers that exact year for the same modelo (that per-file
  overlap check was not run at this scale) -- whether a given inside-bucket
  file is itself the governing design or a superseded duplicate of one
  already registered is part of the un-adjudicated per-file decision above.
- **OUTSIDE every declared span (75) -- acquired inventory beyond current
  claimed coverage.** By modelo: 100 (16), 111 (5), 115 (3), 123 (3), 130
  (5), 131 (4), 200 (24), 202 (4), 216 (1), 220 (1), 222 (1), 296 (1), 345
  (1), 390 (6). Modelo 200 alone accounts for a third of this bucket: its
  sole declared span is `(2025, unbounded)`, so every pre-2025 design
  (2010-2024) falls outside by construction. Not necessarily a defect --
  the registry does not currently claim to compute these years at all.
- **AMBIGUOUS (25) -- no year derivable by the stated rule, not guessed.**
  By modelo: 036 (1), 038 (1), 111 (1), 189 (1), 190 (2), 193 (5), 200 (1),
  202 (6), 303 (1), 345 (1), 349 (1), 576 (1), 604 (2), 763 (1). Mostly
  amendment-only filenames (`...-actualizada-por-orden-hfp-1822-2016...`)
  or names with no `ejercicio`/`devengos` marker at all
  (`01-576-diseno-de-registro-vigente.xlsx`). These need a human or a
  smarter rule to resolve a year, not this pass.

**The number that matters, per the instruction:** 29 designs govern a
filing year the registry currently claims to support and are unverifiable
today -- not "60% of the corpus is unregistered."

**Per-file cross-check of the 29, closing the caveat above.** For each of
the 29, checked whether any REGISTERED `kind = "record_design"` source for
the same modelo has its own derived span (same rule, applied to the
registered filename) overlapping the unregistered file's derived span --
tractable at this scale, not attempted across the full 129.
`dictionary`/`xsd` companion kinds are excluded from the comparison set;
they are not layout-governing artefacts.

- **NO REGISTERED COVERAGE -- genuine hard gap (11):** modelo 122 (1,
  `01-122-ejercicio-2016-y-siguientes.xlsx` -- this modelo has **zero**
  registered `record_design` sources at all, so its entire layout capability
  is unverifiable) and modelo 303 (10, ejercicios 2014, 2015-2016, 2017,
  2018 x2, 2019-2020, 2021 x2, plus the 2021-desde-periodo-07 file --
  confirmed no registered M303 design covers any year before 2022).
- **REGISTERED COVERAGE EXISTS -- likely superseded duplicate (11):**
  111 (1), 115 (1), 123 (2), 130 (1), 200 (1), 202 (2), 303 (1), 322 (1),
  345 (1). The clearest pattern: an unregistered `.xls` sitting beside an
  identically-named registered `.xlsx` for the same design (111, 115, 123 x1,
  130, 200) -- same design, two formats, only one enrolled.
- **CANNOT DETERMINE (7), by filename alone -- resolved below by reading
  content.**

**The 7 resolved by reading the registered artefacts directly, per
instruction, rather than staying blocked on filename ambiguity.** Extracted
each blocking registered design's own fields (`RecordDesignField.content`/
`.description`), read what they actually declare, and cross-checked against
the legal catalogue's own amendment timeline. Result: **4 move to NO
COVERAGE, 3 move to REGISTERED COVERAGE EXISTS, 0 stay undetermined.**

- **Modelo 036 (3 files) -> REGISTERED COVERAGE EXISTS.** Read the
  registered `aeat-dr-036-2025.xlsx`'s own "Ejercicio devengo" field: it
  carries `content = None` -- a variable input field, not a fixed year --
  meaning the design is a version-dated GENERIC template (any ejercicio),
  keyed by its `03-02-2025` effective date, not by a specific filing year.
  Cross-checked the legal catalogue (`censo.toml`): the base order is
  `orden-eha-1274-2007`, the sole intervening amendment is
  `orden-hac-1526-2024` (`applies_from = 2025-02-03`, matching the
  registered file exactly) -- **no legal amendment is declared for 2021 or
  2023**, the years the 3 unregistered files' filenames carry. With no
  intervening legal change and the same variable-ejercicio template shape,
  the 3 unregistered files are earlier technical-refresh versions of the
  SAME base-2007-order template, superseded by the 2025 registered one --
  not distinct designs for distinct years.
- **Modelo 210 (2 files) -> NO COVERAGE, genuine hard gap.** Read the
  registered `dr210_2011.pdf`'s "Devengo. Año. AAAA" field: `content = None`,
  also a variable field -- the 2011 PDF is a generic base template, not
  year-specific. But the legal catalogue (`irnr.toml`) carries two DATED,
  REGISTERED amendments the base template cannot be: `boe-modelo-210-2024-form-layout`
  (`orden-hac-56-2024`, `applies_from = 2024-02-01`, `applies_to = 2026-12-31`)
  and `boe-modelo-210-2026-form-layout` (`orden-hac-623-2026`,
  `applies_from = 2026-01-01`) -- dates matching the two unregistered
  filenames almost exactly (`02-210-devengos-entre-01-06-2022-y-01-01-2026.xls`,
  `01-210-devengos-a-partir-de-2026.xlsx`). Both amendments are registered
  only as `form_spec` (the BOE order text), never as `record_design` -- so
  no layout artefact for either window is registered at all. Real, dated
  legal changes exist for exactly these windows; the 2011 base design cannot
  cover them.
- **Modelo 347 (2 files) -> NO COVERAGE, genuine hard gap.** Read the
  registered `aeat-dr-347-2011.pdf`'s three "EJERCICIO." fields: each
  `content` reads *"Las cuatro cifras del ejercicio fiscal..."* -- an
  instruction for a variable input, not a fixed year. The legal catalogue
  (`operaciones-terceros.toml`) shows the base order `orden-eha-3012-2008`
  (`effective_from = 2008-10-23`) established the ORIGINAL M347 layout, and
  `orden-eha-3378-2011` (Dec 2011) is the amendment backing the registered
  design -- a layout change, not a retroactive one. The two unregistered
  files (`02-347-ejercicio-2008-y-2009...`, `03-347-orden-eha-3062-2010-ejercicio-2010...`)
  predate the 2011 amendment and their own filenames cite a still-earlier
  order (`eha-3062-2010`) than either registered design. No registered
  `record_design` exists for the 2008-order-era layout at all.

**Revised totals: 15 NO COVERAGE (genuine hard gap), 14 REGISTERED
COVERAGE EXISTS, 0 CANNOT DETERMINE -- 15 + 14 = 29.** The escalation number
moves from 11 to **15**.

**The M303 dependency, checked rather than left hanging.** All 10 M303
"no coverage" entries derive their INSIDE-membership from the disputed
`2009-y-siguientes` revision. Read the actual conflicting fields directly:
`valid_to = None` (open, what the partition used) versus
`period_selector.year_to = 2022` (closed) -- the exact contradiction routed
to recon. **The 10 M303 hard-gap years are 2014-2021, every one at or below
2022** -- so however that contradiction resolves, none of these 10 leaves
the INSIDE bucket; the closed reading `[2009, 2022]` still covers all of
them. The M303 share of the 11-file genuine-hard-gap count is stable
regardless of the routed dependency's outcome; only years *after* 2022
would have been at risk, and none of the 29 land there via that revision.

**Testing whether the 75 OUTSIDE files are genuinely outside, per
instruction -- measurement only, no span edits.** The 14 modelos in the 75
were checked against three signals, in order of how discriminating each
turned out to be.

**Signal 1, tried first, discarded as non-discriminating.** Compared each
modelo's earliest `legal_refs`-grounding date against its earliest declared
span start. Every one of the 14 modelos showed the enabling statute
predating declared coverage, by 2 to 29 years (e.g. Modelo 100's `ley-35-2006:art-22`
foundational article is dated 2007, 13 years before its 2020 span start).
**This is expected for all 14 and proves nothing**: a modelo's foundational
tax law (establishing the tax itself) is essentially always older than any
specific box-layout revision the registry has authored, whether or not that
revision's declared coverage is accurate. Reporting the check and its
non-result rather than presenting it as evidence, since a uniform signal
that fires on literally everything cannot separate "genuinely late registry
authoring" from "under-declared."

**Signal 2, sharp and discriminating: deadline windows.** Each modelo's OWN
`ModeloRevision.deadline_windows` (an independent obligation-calendar
mechanism, not derived from corpus/design evidence) was checked for a
`filing_year` earlier than the modelo's declared span start. 13 of the 14
show no such window. **Modelo 200 does, and it is a self-contained internal
contradiction, not corpus circumstantial evidence:** its SOLE revision is
`id = "2024-y-siguientes"` (name asserting "2024 and following") but
declares `valid_from = 2025-01-01` -- one year later than its own name --
while that SAME revision's own `deadline_windows` correctly carries
`modelo-200-2024-0a` (`filing_year = 2024`, opens 2025-07-01, closes
2025-07-25, the real Impuesto de Sociedades July-filing calendar for fiscal
2024). The revision's name and its own deadline window both assert 2024;
its `valid_from` field alone excludes it. This directly explains the bulk
of Modelo 200's 24-file OUTSIDE share: even the correct 2024 design --
already registered (`16-200-ejercicio-2024-...xls`) -- sits outside its own
revision's declared validity range. **Same defect family as the
`2009-y-siguientes` name/bound contradiction already routed to
recon-temporal-legal** (name says open/early, a declared field says later)
-- a new instance, not adjudicated or corrected here, flagged for the same
routing decision.

**Signal 3, weaker, corroborating only: design-file continuity.** For each
modelo, walked the bundled corpus (registered and unregistered) for every
derivable design year and checked for a gap between the earliest design
year and the declared span start. 11 of 14 show unbroken year-by-year
AEAT publication right up to the declared span start (Modelo 111: 2004-2018
continuous into a 2019 span; Modelo 200: 2010-2024 continuous into a 2025
span). This is circumstantial, not a registry-internal contradiction, and
is not by itself evidence that the app needs to compute those years --
distinct from Signal 2 on purpose, so acquisition volume is never
substituted for a legal-validity claim. Two exceptions, weaker still and
noted rather than chased: Modelo 131's design corpus itself has a 2017-2018
gap between otherwise-continuous 2008-2016 and 2019 (a gap in what AEAT
published or what was acquired, not a registry declaration issue); Modelo
202's corpus is sparse before 2015 (2010-2014 and 2016 have no design on
file at all).

**No modelo among the 14 shows a discontinuity BETWEEN its own declared
revision spans** -- every modelo's revisions, once they start, are
contiguous with no internal gap. The pattern across 13 of the 14 is "started
late" with nothing internally contradicting that; Modelo 200 is the one
exception, and it is a real internal contradiction, not a judgement call.

### dated-layout-amendments-without-registered-design | high | swept every dated layout amendment against registered coverage: 43 candidates name a modelo with zero registered design at all, 13 are structurally newer than any design the registry has

**Where:** every `SourceReference` with `kind = "form_spec"`, its OWN
declared `evidence_tier = "layout_authority"` (the registry's own
classification of "this establishes/amends a layout", not "legal_authority"
or "official_source_guidance" -- the exact discriminator the operator's
caution about filing-rule-versus-layout amendments calls for), and a
declared `applies_from`/`applies_to` window. **108 such candidates**,
generalising the exact M210/M347 shape.

**Method, in two passes, because the first pass was wrong twice before
landing.** Linking a candidate to its modelo via `rev.source_refs` (or a
full recursive walk of every `source_refs` field in the revision tree)
proved unsafe in BOTH directions: M210's own registered base design was
absent from its revision's `source_refs` entirely (present in the
catalogue, never cited), while a recursive walk picked up Modelo 184's
design as "Modelo 100's coverage" through a legitimate cross-modelo
binding (`0041-renta-2025-modelo-184-atribucion-actividades-economicas.toml`)
-- a real citation, but not evidence of Modelo 100's OWN layout. Settled on
the same convention this whole vein has used throughout: a candidate's own
id-naming (`boe-modelo-<NNN>-...`, `enrolled-modelo-<NNN>-layout`) and a
registered design's `corpus_path` directory (`disenos_registro/modelo_<NNN>/`)
-- no `source_refs` walk. **3 of 108 candidates could not be id-resolved to
a modelo** (`aeat-dr-123-2024-v20-form-text`, `aeat-dr-123-2019-2023-v13-form-text`,
`boe-rd-1021-2015`) and are not classified below.

**Second correction, mid-sweep.** A naive interval-overlap check (does the
candidate's window overlap ANY registered design's declared window) put 46
candidates in "covered" purely because both windows were open-ended
(`applies_to = None`) -- mathematically two unbounded intervals always
overlap, regardless of which came first. This is the SAME shape that
already misled once: `dr210_2011.pdf` itself carries a declared
`applies_from = 2011-01-01, applies_to = None`, which trivially "overlaps"
the 2024 and 2026 amendment candidates despite the prior, carefully-read
finding that it does NOT cover them. **Replaced with a chronology test that
does not need content-reading to be certain in one direction: a design
authored BEFORE an amendment cannot embody it.** A candidate whose
`applies_from` is later than every registered design's `applies_from` for
its modelo is a structural gap by construction, not a heuristic.

**Result: 43 NO REGISTERED DESIGN AT ALL (any date) / 13 STRUCTURAL GAP /
49 PLAUSIBLE / 3 unresolved. 43+13+49+3 = 108.**

- **NO REGISTERED DESIGN AT ALL (43 candidates, 24 modelos) splits into two
  genuinely different problems, checked by whether `disenos_registro/`
  even has a directory for the modelo:**
  - **6 modelos have unregistered files ON DISK -- the same class as the
    15-file escalation, now measurably larger.** Modelo 038 (1 file),
    Modelo 100 (16 files, matching the earlier OUTSIDE-partition finding
    that M100 has zero registered coverage even for its in-scope
    2020-2025 span), Modelo 122 (1, already escalated), Modelo 189 (1),
    Modelo 576 (1), Modelo 763 (1).
  - **17 modelos have NO `disenos_registro/` directory at all -- a
    different problem, per the operator's framing.** 121, 136, 140, 143,
    179, 186, 231, 233, 234, 238, 289 (13 candidates alone), 361, 379, 380,
    592, 721 (already an open concept question above), 848. A design that
    was never published cannot be acquired; whether these modelos
    genuinely need no fixed-layout artefact (simple web-only forms) or
    whether acquisition never happened is a corpus-acquisition question,
    not a registry-schema one, and not resolved here.
- **STRUCTURAL GAP (13 candidates, 9 modelos) -- newer than any registered
  design, certain by construction:** Modelo 210 (3, already confirmed
  above), Modelo 145 (2, amendments dated 2014/2015 against a design dated
  2012), Modelo 280 (1, a Dec-2022 amendment against a Jan-2022 design),
  Modelo 123, 180, 202, 216, 296, 345 (1 each, amendments landing 1-11
  months after their modelo's latest registered design's own
  `applies_from`). **One flagged as ambiguous rather than asserted:**
  `boe-modelo-200-2025-form`'s window (`2025-07-01` to `2025-07-25`, a
  25-day span) reads like a FILING-DEADLINE window, not a layout amendment,
  despite carrying `evidence_tier = "layout_authority"` -- the declared
  data does not let this sweep tell which kind of order it is, so it is
  bucketed here and named rather than folded into either count.
- **PLAUSIBLE (49 candidates) -- NOT asserted as covered.** The modelo's
  most recent registered design was authored at or after the candidate's
  window, which is a real, defensible prior but not confirmation --
  confirming any one of these requires the same content-read-plus-legal-
  timeline discipline that resolved Modelo 036/210/347, not attempted at
  this scale.

**Correction, confirmed directly: Modelo 100 is NOT a gap. The sweep's
`kind = "record_design"` filter was too narrow for this specific modelo,
and the byproduct claim in the prior message overstated it.** Checked all
three things the operator asked for:

- **Every registered source under `disenos_registro/modelo_100/`:** 18
  entries, all `dictionary` (12) or `xsd` (6), one set of three per
  ejercicio 2020-2025. Zero `record_design`-kind entries -- confirmed, the
  sweep's headline number is correct in isolation.
- **M100's declared revision spans (2020, 2021, ..., 2025, one revision per
  year) each declare `export_layouts` with `format = XML_DICTIONARY`, and
  each revision's OWN `source_refs` correctly cites that year's
  `dictionary`+`xsd` sources plus the year's `boe-modelo-100-YYYY-form`
  legal text** (e.g. the 2020 revision cites `aeat-dr-100-2020-dictionary`,
  `aeat-dr-100-2020-input-dictionary`, `aeat-dr-100-2020-xsd`,
  `boe-modelo-100-2020-form`). **A `record_design`-kind (fixed-width
  PDF/XLS) artefact is not the mechanism M100 uses for 2020-2025 at all --
  the modelo's own declared export format for every in-scope year is the
  XML/dictionary schema, not fixed-width.** `resolve_record_design_binary`
  and the `allowed_record_design_suffixes` validator (`.pdf`/`.xls`/`.xlsx`/
  `.xlsm` only, explicitly excluding `.xsd`) treat `record_design` and
  `xsd` as different, non-substitutable kinds by design -- so the absence
  of a `record_design` entry for an `xml_dictionary`-format revision is the
  CORRECT, expected shape, not a gap of the same kind as Modelo 122's.
- **The 16 disk files (ejercicios 2009-2019, all PDF/XLS fixed-width) sit
  entirely BEFORE the 2020 cutover** where AEAT's own M100 mechanism
  switched from a fixed-width record design to the XML dictionary/XSD
  schema (matching the Renta WEB modernisation). They remain real,
  unregistered, acquired inventory -- already correctly counted in the
  75-file OUTSIDE partition above, where none of them fall inside M100's
  declared 2020-2025 span -- but they are LEGACY artefacts from a
  mechanism M100 no longer uses, not evidence of a hole in the modelo's
  current, actively-computed coverage.

**Net effect: Modelo 100 drops out of the "unverified layout for an
in-scope year" class entirely.** It was never the largest exposure in the
campaign; it is a clean case where the registry correctly uses a different,
fully-registered mechanism (`xsd`+`dictionary`) for its declared span. This
also means the sweep's `kind = "record_design"`-only candidate/coverage
filter is too narrow as a general rule: any modelo whose revisions declare
`export_layouts.format = XML_DICTIONARY` should be checked against its
`xsd`/`dictionary` registration, not `record_design`, before being counted
as a gap. Not re-run at full scale here; flagged as the sweep's own
limitation.

**The other five, checked as instructed -- genuine, but a different and
lower-urgency shape than M100 would have been.** Modelo 038, 122, 189,
576 and 763 each declare `export_layouts = ()` (empty) and no
`authority_grade` on their sole revision, cite only their own
`enrolled-modelo-<NNN>-layout`/procedure sources (not a `dictionary`/`xsd`
substitute), and carry minimal schemas (2-9 casillas, zero formulas each).
None has M100's XML-dictionary escape hatch -- their single unregistered
disk file each is real, acquired inventory with no registered substitute
of any kind. But unlike M100, none of these five currently declares an
export mechanism at all, so the record-design gap sits underneath a modelo
that is not yet computing or exporting anything verified -- real exposure,
smaller in scale and lower in urgency than a modelo already filing
computed values against no verified layout.

**Full re-run of the two escalated sets by declared export format, per
instruction, since the same narrow filter produced M100's false positive
and more were assumed possible.** Checked every remaining modelo in the
15 NO COVERAGE set (122, 303 -- 210 and 347 already independently confirmed
via content-reading in the earlier finding, not filter artifacts) and the
43 NO REGISTERED DESIGN AT ALL set (all 23 remaining after Modelo 100):
`export_layouts.format` per revision, and every registered `dictionary`/
`xsd` source for the modelo by id-pattern AND `corpus_path` (not
directory-scoped, so a substitute registered outside `disenos_registro/`
would not be missed).

**Result: zero further false positives. Every one of the 23 checked
modelos (038, 121, 122, 136, 140, 143, 179, 186, 189, 231, 233, 234, 238,
289, 303, 361, 379, 380, 576, 592, 721, 763, 848) declares
`export_layouts = ()` on every one of its revisions -- NO mechanism at
all, not `XML_DICTIONARY`, not fixed-width -- and carries ZERO registered
`dictionary`/`xsd` source of any kind.** Modelo 100 was the sole
XML-dictionary-format member of either set; there was no second one to
find. The caution about checking a substitute's actual year-span coverage
before crediting it as covered did not need to be exercised, because none
of the 23 has a candidate substitute to check in the first place.

**Numbers restated: 15 stands unchanged (122 and 303 confirmed genuine, no
mechanism mismatch). 43 becomes 42 (Modelo 100 the sole correction,
already applied above; no further movement).** The empty-`export_layouts`
finding is itself the sharper characterisation for all 23 -- per the
instruction's third bucket, these modelos declare no mechanism at all, so
neither `record_design` nor any substitute kind can be "missing" until the
modelo declares what it needs. That is the same conclusion the five-modelo
check above already reached, now confirmed to hold for the remaining
eighteen as well.

### undeclared-export-mechanism-registry-wide | high | 78 of 97 revisions across 66 of 73 modelos declare no export mechanism at all -- reconciles exactly with the standing load-refusal count, and splits into a modelled-but-unexportable population and an enrolment-placeholder population

**Where:** `ModeloRevision.export_layouts` (empty tuple vs populated),
measured across every loaded modelo and revision, cross-checked against
the standing registry-refusal figure ("97 ungraded revisions, 78 without
export layout") already recorded as a load-bearing fact for this campaign.

**Method: the corpus-side sample (the 23 checked in the prior finding) was
correct but partial by construction -- it only reached modelos the
layout-amendments/registration-gate sweeps had already surfaced.** Measured
the same axis from the registry side instead, over every loaded modelo and
revision, independent of any corpus evidence.

**Result: 73 modelos loaded (one fewer than the standing figure's "74" --
noted, not chased; a small drift is expected in a tree that is actively
being authored, and nothing here depends on resolving it). 97 revisions
total. 78 of those 97 revisions declare NO `export_layouts` at all -- an
EXACT match to the standing load-refusal count.** No discrepancy to
report: the refusal's "78 without export layout" and this measurement's
"78 revisions with no export_layouts" are counting the identical set. Only
**7 modelos** declare an export mechanism on any revision at all:
Modelo 100 (`xml_dictionary`); Modelo 131, 145, 180, 349, 390, 720
(`fixed_width`). **66 of 73 modelos declare no export mechanism on ANY
revision.**

**The split that matters, per instruction -- modelled-but-unexportable
versus enrolment-placeholder, applied to all 66:**

- **31 modelos are MODELLED BUT NOT EXPORTABLE** (a real casilla/formula
  schema with no way to emit it) -- work half done, in the operator's
  framing. Ranked by casilla count: Modelo 200 (3250 casillas, 10
  formulas), Modelo 303 (1154 casillas, 151 formulas -- **consistent with
  the already-known blocked S20 work**, its five export trees generated
  but unpublished pending operator review, exactly matching a modelled,
  non-exported revision), Modelo 202 (136/35), Modelo 232 (56/0), Modelo
  210 (34/8), Modelo 036 (31/0), Modelo 111 (30/2), Modelo 345 (29/0),
  Modelo 136 (24/3), Modelo 123 (22/7), Modelo 130 (20/12), Modelo 379
  (18/0), Modelo 714 (18/8), Modelo 289 (17/0), Modelo 151 (14/5), Modelo
  369 (14/3), Modelo 353 (13/3), Modelo 126 (12/2), Modelo 280 (12/0),
  Modelo 117 (11/2), Modelo 322 (10/3), Modelo 216 (8/3), Modelo 128
  (7/1), Modelo 115 (5/2), Modelo 309 (5/1), Modelo 187/188/190/193/194/296
  (3 casillas each, 1-2 formulas). **Note that several of these already
  carry a REGISTERED `record_design` (M210, M280, M345, M347's absence
  from this list is because it lands in the placeholder bucket below) --
  a registered layout ARTEFACT and a declared `ExportLayoutDefinition` are
  two different schema objects, and a modelo can have the former grounding
  its casilla positions while genuinely lacking the latter, the build-plan
  object the export pipeline actually consumes.**
- **35 modelos are NEAR-EMPTY ENROLMENT PLACEHOLDERS** (10 or fewer
  casillas, zero formulas) -- calling these a gap overstates them; they are
  scaffolding, not modelled capability waiting on an export mechanism.
  Includes the five already confirmed in the prior finding (038, 122, 189,
  576, 763) plus 30 more: 121, 140, 143, 156, 165, 179, 181, 182, 184, 185,
  186, 220, 222, 231, 233, 234, 238, 270, 308, 341, 347, 360, 361, 380,
  490, 592, 604, 721, 840, 848.

**What this changes about the escalated counts from the prior finding.**
The operator's own framing applies directly: a modelo that declares no
export mechanism cannot be MISSING one. The 23 modelos checked in the
prior finding (all confirmed `export_layouts = ()`) are not a corpus
acquisition backlog at all -- they are a schema-completeness question,
different owner, and do not belong on an acquisition worklist. This
registry-wide measurement confirms that reading holds for the full
population, not just the 23 sampled from the corpus side.

## Recommendations

**`SourceReference.review_status`:** remove the field and its 321
declarations once the concurrent adjacent-module migration lands; do not
land both in the same window.

**`LegalParameter.review_status`:** do not delete. This is an open design
decision for the operator -- whether to build a real gate now, defer it with
an explicit tracked row, or accept the current risk consciously -- not
something to resolve by schema cleanup. The 28 named entries above are the
worklist if a gate is built.

**Sidecar mechanisms:** no action needed on the disenos_registro PDF gap
itself (fully covered). Consider registering the orphaned `modelo_349`
`.docx` as a `SourceReference` or explicitly recording that it is
deliberately unregistered, so a future sweep does not have to re-derive
that distinction. The red `test_normative_html_sidecars_equal_current_production_extraction`
failure needs its own triage; it is not scoped to this document's findings.

**Design-discovery glob mismatches:** converge `_record_design_pdf_files()`
(`_record_design_support.py:142`) onto the same `rglob("*")` shape already
adopted by its two sibling enumerations, so
`test_record_design_pdf_corpus_is_discovered_and_parseable` stops asserting
over a corpus that is silently one file short -- this is the live,
unfixed mismatch and the only one of the three requiring a code change.
Converge `_design_files()` (`test_rate_specific_box_pins_its_rate.py:95`)
onto the same recursive shape pre-emptively; it is dormant today but shares
the identical fixed-depth pattern that already caused two live defects, and
fixing it now costs one line rather than a third rediscovery later. No
change indicated for `.xlsm` (already closed) or the `_loader.py` guard/
collector pair (dormant, and per the operator's ruling a stricter guard
reacting to a real gap is correct behaviour, not something to pre-emptively
tighten against a gap that does not exist yet) -- record the wake condition
here rather than acting on a hypothetical.

**`form_spec`/`record_design`:** Modelo 210, Modelo 280 and Modelo 345 are
reclassified and verified clean; no further action. Modelo 721 needs an
operator ruling on whether an órden-embedded layout is the same concept as
an AEAT-published Diseño de Registro -- not resolved here. The orphaned
`instructions/modelo_345/files/DR_Modelo_345_2025.pdf` copy needs a corpus-
hygiene decision (delete as a confirmed duplicate, or record why it stays);
left untouched pending that decision.

**Registration gate:** the new gate stays in the suite landed red -- that is
the deliverable, not a defect to silence. The escalation number is **15 --
a genuine hard gap**, confirmed by per-file cross-check against the
registered `record_design` population plus, for the 7 that filename alone
could not resolve, by reading the registered artefacts' own field content
and the legal catalogue's amendment timeline. Modelo 122 is the sharpest
single item: its entire layout capability has zero registered
`record_design` sources. Modelo 210 (2 files) and Modelo 347 (2 files) are
now confirmed hard gaps too, each backed by a dated legal amendment the
registry has no registered layout artefact for. The remaining 14 of the 29
are superseded duplicates -- 11 from `.xls`/`.xlsx` sibling pairs, 3 from
Modelo 036's version-dated generic template, all confirmed covered rather
than assumed. **0 remain undetermined.** The 25-file AMBIGUOUS partition is
lower urgency. The gate itself is not weakened or scoped by any of this; it
keeps reporting all 129 until each is closed by an authoring decision.

**The 75 OUTSIDE partition:** 13 of the 14 modelos show a consistent,
internally uncontradicted "started late" pattern -- treat as acquired
inventory beyond current claimed coverage, as originally classified.
**Modelo 200 is the exception and needs the same routing as the M303
`-y-siguientes` contradiction**: its sole revision's name (`2024-y-siguientes`)
and its own `deadline_windows` entry both assert 2024, while its
`valid_from` field alone excludes it -- a one-field, one-year discrepancy,
not a judgement call, and not corrected here per the no-span-edits
constraint.

**Dated layout amendments without registered coverage:** prioritise the 13
STRUCTURAL GAP candidates and the confirmed 5-modelo disk-inventory set
(038, 122, 189, 576, 763) -- both are certain, not heuristic. **Modelo 100
is confirmed CLEAR, not a gap** -- its declared 2020-2025 span uses an
`XML_DICTIONARY` export mechanism backed by fully-registered `dictionary`/
`xsd` sources for every year; its 16 unregistered PDF/XLS files are legacy
pre-2020 fixed-width inventory from before AEAT's own cutover, already
counted correctly in the 75-file OUTSIDE partition. **Full re-run
completed, not just flagged as a limitation:** every other modelo in both
the 15-file and 43-file sets was checked the same way and Modelo 100 was
the only mechanism-mismatch found -- the remaining 23 modelos all declare
`export_layouts = ()` (no mechanism at all) and carry zero `dictionary`/
`xsd` substitute of any kind, so their record-design gap stands as
originally classified. **43 revises to 42**; the 15 stands unchanged. The 17
modelos with no `disenos_registro/` directory at all need a
corpus-acquisition decision (was a layout ever published? was it ever
acquired?), not a registry-schema fix -- do not conflate this population
with the registration gate's 129. The 49 PLAUSIBLE candidates are explicitly
unconfirmed; treat as a worklist for the same content-read discipline that
resolved Modelo 036/210/347, not as closed. `boe-modelo-200-2025-form`
needs a human classification (layout amendment vs. filing-deadline window)
before it is counted either way.

**Undeclared export mechanisms, registry-wide:** the registry-side
measurement reconciles exactly with the standing load-refusal figure (78
revisions without export layout, both counts) -- no correction needed
there. **Route the split, not the raw count.** The 31 MODELLED BUT NOT
EXPORTABLE modelos (Modelo 200 and Modelo 303 largest by casilla count)
are work half done -- a schema-completeness backlog for whoever owns
export-layout authoring, separate from any corpus-acquisition list; Modelo
303's presence here is the same, already-known blocked S20 work, not a
new finding. The 35 NEAR-EMPTY ENROLMENT PLACEHOLDER modelos are
scaffolding, not a worklist item, and should not be counted as gaps of any
kind. **None of the 66 no-mechanism modelos belongs on the operator's
corpus-acquisition list** -- a modelo that declares no export mechanism
cannot be missing one; that list stays scoped to modelos with a declared
mechanism and a genuinely absent artefact (M210, M347, and whichever of
the 49 PLAUSIBLE eventually resolve to genuine gaps).
