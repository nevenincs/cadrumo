---
tags:
  - '#adr'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-research]]'
  - '[[2026-04-21-declaracion-extractor-adr]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
  - '[[2026-05-30-purchase-invoice-ocr-extraction-discipline-adr]]'
  - '[[2026-05-28-borrador-extraction-architecture-research]]'
  - '[[2026-05-28-declaracion-extraction-architecture-research]]'
  - '[[2026-05-30-declaracion-extraction-architecture-research]]'
---
# `declaracion-extraction-architecture` adr: `registry-driven declaración extraction supersedes per-modelo extractor classes` | (**status:** `accepted`)

## Problem Statement

A filed-declaración PDF is parsed in HEAD by a registry-profile-driven
generic parser: `src/aeat/adapters/inbound/declaracion/_parser.py`
selects one `declaracion_pdf` `ExtractionProfileDefinition` from the
loaded `RegistrySnapshot` and matches each `target_casillas` entry
against the PDF text. There are no extractor classes and no
`DeclaracionExtractor` ABC.

The only accepted ADR on the subject — `2026-04-21-declaracion-extractor-adr`
— mandates the opposite: a `DeclaracionExtractor` ABC with one Python
subclass per modelo-revision, registered in a code registry keyed
`(modelo, año, revision)`. The hexagonal restructure **deleted every
per-modelo extractor class** (commits `1f301c9e1`, `624e7d7cf`,
`39d5bbc99`) and replaced them with the registry-driven parser. No ADR
sanctioned that re-architecture; it stands in undocumented contradiction
to the accepted ADR.

The contradiction must be resolved, and the resolution must also close a
correctness hole the re-architecture left: of the six modelos the
accepted ADR scoped (130, 303, 111, 115, 180, 190), only 130/111/115
have working registry extraction profiles. Modelo 303 — the MVP-v1
headline modelo — has no extraction profile at all; Modelo 180 has none;
Modelo 190 carries a `declaracion_pdf` profile whose `target_casillas`
are abstract `decl.*` slugs the parser's `re.escape(casilla_id)` regex
can never match — it loads green and silently extracts nothing.

## Considerations

- **The code/data line is already settled.** `2026-05-03-calculation-truth-
  registry-pending-adr` (accepted) moved per-modelo calculation authority
  out of Python (`_rulesets/`) into reviewed registry TOML. The
  registry-driven declaración parser is the *same move* applied to
  extraction: per-modelo parsing knowledge expressed as reviewed
  registry data, not code. Restoring per-modelo extractor classes would
  rebuild the exact pattern the codebase deliberately retired.
- **The generic parser's matching contract.** `_find_casilla_hits`
  compiles, per casilla, a line-anchored regex on the casilla id printed
  literally at line start with a trailing Spanish-formatted amount. This
  works only when the casilla id equals the printed number and the value
  is numeric.
- **The named-field gap.** Modelos 036, 037, 369, 720, 840 carry text
  fields keyed by printed label, not numeric casilla id. The generic
  parser structurally cannot read them — it would anchor on a slug that
  is never printed. `_label_regex.py` already exposes a `TEXT_VALUE_GROUP`
  the numeric path does not use; the missing piece is a typed
  match-strategy in the profile schema.
- **Conformance.** The registry-driven design conforms to the hexagonal
  layout, the registry-data direction of `2026-05-03`, the
  strict-pydantic discipline of `2026-05-18-schema-hardening-adr`, the
  Spanish-stem rule of `2026-05-19-spanish-stem-terminology-authority-adr`,
  and the fragment layout of `2026-05-19-modelo-registry-fragment-
  architecture-adr`. The per-modelo-class design conforms only to the
  now-contradicted `2026-04-21` ADR.
- **Scope drift.** The accepted ADR scoped six modelos; branch
  `feature/271-pdf-import` reached twenty-one; HEAD has already drifted
  (Modelo 123 ships working numeric extraction; 720/840 carry dead
  stubs) with no ADR.

## Constraints

- The named-field extension must hold the strict / frozen /
  `extra="forbid"` discipline of `ExtractionProfileDefinition`: typed
  `Literal` enums for the match strategy and value kind, no
  `dict[str, Any]`.
- Single-segment numeric modelos already working (130/111/115/123) must
  keep validating and parsing unchanged — the named-field primitive is
  purely additive.
- A `declaracion_pdf` profile whose `target_casillas` reference
  `data_type = "text"` casillas must fail the snapshot-build gate unless
  it uses the `named_label` strategy — so dead `decl.*`-slug stubs
  cannot load green.
- No live AEAT write surface is touched; this is an inbound-parsing and
  registry-data concern only.
- Bounded MVP scope: this ADR commits the numeric-casilla tier; it does
  not commit twenty-one modelos in one bite.

## Implementation

**Decision.** Ratify the registry-profile-driven generic parser as the
canonical declaración-extraction architecture. This ADR **formally
supersedes `2026-04-21-declaracion-extractor-adr`**; the
`DeclaracionExtractor` ABC and per-modelo Python extractor classes are
not restored. Extend the registry profile with a typed named-field
primitive (the research's Option C).

**Named-field primitive.** Extend `ExtractionProfileDefinition` (and its
per-target descriptor) with `match_strategy: Literal["numeric_casilla",
"named_label"]` and `value_kind: Literal["amount", "text", "enum"]`,
plus an optional label pattern for the `named_label` strategy.
`_find_casilla_hits` branches on `match_strategy`: the `numeric_casilla`
path is unchanged; the `named_label` path anchors on the printed label
and captures with the existing `TEXT_VALUE_GROUP`. The snapshot-build
validator gains a rule: a `declaracion_pdf` profile target that names a
`data_type = "text"` casilla must use `named_label`.

**Scope — two tiers.**

- *Numeric-casilla tier (committed by this ADR):* modelos 130, 303, 111,
  115, 180, 190, and 123. 130/111/115/123 already work; the execution
  work is to author `declaracion_pdf` extraction profiles for 303 and
  180, and to replace Modelo 190's abstract `decl.*` stub targets with
  the real numeric/labelled casilla targets the form prints. The Modelo
  130 `03 = 01 − 02` intra-filing cross-check is restored as a
  `verification_expectations` stanza.
- *Named-field tier (committed as mechanism, deferred as content):*
  modelos 036, 037, 369, 720, 840. This ADR commits the named-field
  primitive as the mechanism and requires that the dead 720/840 stub
  profiles be corrected or removed so they no longer load green;
  authoring functional named-field profiles for these modelos (and
  registering 037, which has no registry presence) is scheduled as
  follow-up, gated on the primitive.

Per-modelo bbox and AcroForm extraction primitives (the superseded
ADR's P2/P3) are deferred as a named future extension if a modelo's
layout proves unreadable by label/numeric matching.

## Rationale

The registry-driven design is the only option in step with the settled
post-April direction: `2026-05-03` already decided per-modelo authority
belongs in registry data. The undocumented restructure moved declaración
extraction onto the correct side of the code/data line; the defect was
procedural — a missing ADR — not architectural. Restoring the per-modelo
extractor classes (research Option B) would reverse three deletion
commits, delete a working tested parser, and rebuild a retired pattern
at the highest migration cost.

Ratifying the parser as-is (Option A) would be cheapest but leaves five
named-field modelos unreadable and three `declaracion_pdf` stub profiles
that load green while extracting nothing — a silent-failure class this
codebase has repeatedly resolved to make loud. The hybrid (Option C)
closes that hole inside the registry contract at moderate, additive
cost, and makes the dead-stub failure mode a hard snapshot-build error.

## Consequences

- `2026-04-21-declaracion-extractor-adr` is superseded; its
  `DeclaracionExtractor` ABC and per-modelo class registry are not
  built. That ADR is marked `superseded` on acceptance of this one.
- `ExtractionProfileDefinition` gains the typed named-field fields; the
  change is additive — numeric-casilla profiles are unaffected.
- The snapshot-build validator gains a rule that turns a dead
  text-casilla `decl.*`-slug stub into a hard error; Modelo 190/720/840
  profiles must be corrected as part of the rollout or they fail the
  gate.
- The numeric-casilla tier is a bounded, executable plan: author 303 and
  180 profiles, fix Modelo 190, restore the M130 cross-check. The
  named-field tier is scheduled follow-up gated on the primitive.
- This ADR does not itself author the extraction profiles or the
  parser-code extension; those are Plan/execution work depending on this
  decision.
- No live AEAT write surface is affected.

## 2026-05-26 amendment

### Silent-failure class and the provisional_pending_specimen field

The task-32 audit (swarm axis: extraction-profile grounding) identified a
systematic silent-failure class not addressed by this ADR's original
`named_label` rule: nine `declaracion_pdf` profiles had loaded green for
months with `label_pattern` values derived circularly from the registry's
own casilla `label_es` fields, never verified against a real printed PDF.
Three profiles (M036, M347, M840) carried inline `# PROVISIONAL` comments;
six (M184, M193, M232 ×2, M720, M349) were silently provisional. Task-33
added warning comments and downgraded confidence on M184, M193, and M720.

This amendment formalises the acknowledgement mechanism as a typed schema
field. `ExtractionProfileDefinition` now carries `provisional_pending_specimen:
bool = False`. When True, it declares that the profile's `label_pattern`
values were authored without a corpus PDF specimen for round-trip
verification — the silent-failure class described above.

### Validator gate

The snapshot-build validator gains a complementary rule: for any
`declaracion_pdf` profile that is NOT marked `provisional_pending_specimen =
true`, the validator checks for a corpus fixture PDF at
`tests/fixtures/justificantes/<modelo_id>/`. If no fixture exists and the
flag is false, validation raises `RegistryValidationError`, requiring the
author to either supply a specimen or explicitly acknowledge the open risk
by setting the field. The gate is activated when the `RegistryValidator`
has a `justificante_corpus_root` available (derived automatically from
`source_root` or supplied directly for tests). M190 — the only GROUNDED
profile in the audit's classification — retains the default `false` because
its corpus fixture at `tests/fixtures/justificantes/190/` satisfies the
gate.

### Discipline going forward

Any new `declaracion_pdf` extraction profile without a corpus fixture PDF
must set `provisional_pending_specimen = true` explicitly. The silent
path — authoring a profile, watching it load green, and shipping it — is
now closed. Removing the provisional flag requires depositing a real
specimen PDF and confirming the `label_pattern` values match its printed
labels. The nine profiles tagged in task-34 (M036, M184, M193, M232
2016-2017, M232 2018-y-siguientes, M347, M349, M720, M840) carry the flag
until their respective specimen PDFs are acquired and the patterns are
verified.

## 2026-05-26 amendment (round-trip gate)

### Silent-failure class exposed by M111 and M130

Task-37 real-corpus round-trip work revealed a second silent-failure class
not addressed by the existing provisional_pending_specimen gate: M111 and
M130 both had real corpus fixture PDFs at
tests/fixtures/justificantes/{111,130}/ -- satisfying the specimen gate's
fixture-existence check -- yet production-profile extraction structurally
fails on both. M111's numeric_casilla strategy cannot match AEAT's printed
form because casilla numbers appear at line-end merged with value tokens
rather than at line-start. M130's numeric casillas appear in a detached value
block that the parser's line-anchored patterns cannot reach. The specimen gate
passed them as grounded; round-trip tests exposed them as extraction failures.

Fixture existence alone is therefore an insufficient signal of extraction
correctness. A profile may have corpus AND fail silently on every PDF in it.

### Strengthened gate: corpus_round_trip_verified

ExtractionProfileDefinition gains a second boolean field:
corpus_round_trip_verified: bool = False.

Semantic: true declares that the author has confirmed extraction works
end-to-end against the modelo's corpus PDFs via a parametrized real-corpus
round-trip test in test_parser_boundary.py (or an equivalent module).

The snapshot-build validator gains a complementary rule
(validate_declaracion_pdf_round_trip_gate): for any declaracion_pdf
profile where corpus fixture exists AND both corpus_round_trip_verified and
provisional_pending_specimen are false, validation raises
RegistryValidationError. The gate logic is:

- surface != declaracion_pdf: dormant
- provisional_pending_specimen = true: dormant (explicit opt-out)
- corpus_round_trip_verified = true: dormant (author asserts verified)
- no corpus fixture: dormant (specimen gate handles the missing-fixture case)
- fixture exists, neither flag set: FAIL

The two gates are complementary and non-overlapping: the specimen gate fires
when no fixture exists and the provisional flag is absent; the round-trip gate
fires when a fixture exists but neither verification flag is set.

### Ground-truth tagging applied

VERIFIED (corpus_round_trip_verified = true):
- M100 revisions 2021, 2022, 2023: 19 named_label casillas, round-trip
  confirmed against 3-PDF corpus.
- M190 revision 2024-y-siguientes: 3 named_label casillas, 1-PDF corpus.
- M303 revisions 2009-y-siguientes and 2023-y-siguientes: 4 and 12 casillas,
  15-PDF corpus across two templates.
- M390 revision 2010-y-siguientes: 6 named_label casillas, 2-PDF corpus.

CORPUS-GAP (provisional_pending_specimen = true added):
- M111 revision 2019-y-siguientes: corpus exists; numeric_casilla layout
  defeats extraction due to line-end box-number merging.
- M130 revision 2019-y-siguientes: corpus exists; numeric_casilla layout
  defeats extraction due to detached value blocks. Coverage = 0 on all
  corpus PDFs. Layout-defeated counts as unverified.

NO-FIXTURE-ALREADY-PROVISIONAL (no change):
- M036, M115, M123 (x2), M131, M184, M193, M232 (x2), M347, M349, M720, M840.

### Discipline going forward

Any declaracion_pdf profile with a corpus fixture must satisfy one of two
conditions or fail the snapshot-build gate:
1. A real parametrized round-trip test exists and corpus_round_trip_verified =
   true is set.
2. Extraction is known to fail or is unverified, and provisional_pending_specimen
   = true is set explicitly.

Fixture presence with neither flag is the newly-closed silent-failure path.

## 2026-05-27 amendment — M190 revision rename

### Original revision id and its semantic at authoring time

The M190 extraction profile was initially authored with revision
`id = "2025-y-siguientes"` and `period_selector = { year_from = 2025,
periods = ["0A"] }`. This named the revision after the earliest AEAT
filing year the author expected it to serve, matching the campaign
year of the M100-2025 relation that references M190.

### Rename: `"2025-y-siguientes"` → `"2024-y-siguientes"` and year_from = 2024

Task-36 Cluster B (commit `be12b2c7a`) renamed the revision id to
`"2024-y-siguientes"` and shifted `year_from` from 2025 to 2024. The
TOML registry, every cross-revision selector, and the round-trip gate
tag (`corpus_round_trip_verified = true`) were updated atomically.

### Rationale

Three independent facts converge on `year_from = 2024`.

First, the sole corpus fixture PDF for M190 is `tests/fixtures/justificantes/190/2024-0A.pdf`
— a year=2024 document. The round-trip gate requires the profile id and
period selector to be consistent with the fixture's filing year; a
revision anchored at 2025 would be semantically misaligned with the
only verified specimen.

Second, the M100-2025 cross-modelo relation
`renta-2025-rel-190-retenciones-anuales` carries
`source_revision_selector = { year = 2025 }`. For that selector to
resolve correctly, M190's period window must include year 2025;
`year_from = 2024` with an open upper bound satisfies it.

Third, the task-32 audit confirmed that the AEAT 2024 and 2025 M190
EDI specifications are structurally identical: Orden HAC/1432/2024
(modelo 190 2024 tax year) and Orden HAC/1431/2025 (modelo 190 2025
tax year) define the same Tipo 1 and Tipo 2 record layouts with no
field additions, removals, or re-numbering. A single revision
therefore covers both years without ambiguity.

### Decision

One revision with `id = "2024-y-siguientes"` and `year_from = 2024`
correctly covers the 2024 corpus PDF, satisfies the M100-2025 relation
selector, and reflects the structural identity of the two AEAT Ordenes.
If AEAT publishes a future Orden that diverges from the current Tipo 1/2
layout — introducing new record fields or restructuring the perceptor
block — a new revision with an appropriate `year_from` boundary would be
added at that point, following the same named-revision pattern already
used for other modelos in the registry.

## 2026-05-28 amendment — bbox extraction primitive landed

### Third match strategy: bbox_anchored

Task-66 Phase 1 (commits `ad285e970` schema + parser + profiles + tests,
`e6c4a2879` plan tracking) implemented the bbox extraction primitive that
this ADR named as the future extension in the original 2026-05-21 decision.
The `ExtractionTargetDefinition.match_strategy` Literal gained a third
value `bbox_anchored`, alongside a new `BboxAnchorSpec` frozen pydantic
model capturing the bbox extraction configuration (`box_number_pattern`,
`value_offset`, optional `column_anchor` for multi-column disambiguation,
and bbox spatial constraints `anchor_x_min`/`anchor_x_max`/`value_x_max`).

The parser's `_find_casilla_hits` in `adapters/inbound/declaracion/_parser.py`
now branches on three match strategies. The bbox branch uses
`pdfplumber.Page.extract_words` to locate the box-number word matching
the pattern, then resolves the value word from the same row using
`value_offset` ("left_of_number" for line-end-numeric forms like M111/M130;
analogous for above/right where layouts vary). The branch integrates with
the existing `DeclaracionParseError` structured attributes (`missing`,
`malformed`, `ambiguous`, `coverage`) — no new exception types — so the
post-rush audit hardening (`DeclaracionParseError` extended in commit
`e2de32c62`) carries through unchanged.

### Structural gap class closed: line-end box numbers

The silent-failure class exposed by the 2026-05-26 amendment (M111 and
M130 corpus PDFs structurally defeating numeric_casilla because casilla
numbers appear at line-end merged with value tokens) is closed for both
modelos plus M131 (which shares the same layout family). Each modelo's
`declaracion_pdf` extraction profile was converted target-by-target from
numeric_casilla to bbox_anchored with empirically-determined spatial
constraints inspected from the corresponding corpus PDFs:

- M111 (29 targets across 3 column groups, per-column anchor_x +
  value_x_max)
- M130 (19 targets in the right-column layout at x0~464,
  anchor_x 450-480)
- M131-2026 (15 targets single-box-per-row, no x-constraints needed)

The three corresponding gap tests (`test_parser_modelo_130_corpus_*_gap`,
`test_parser_modelo_131_*_gap`, plus the M111 gap material from task-37)
are replaced with real round-trip tests asserting per-casilla extraction
against the corpus PDFs. After the conversion each profile flips
`provisional_pending_specimen = false` and `corpus_round_trip_verified = true`
with `verification_source = "real_aeat_corpus_pdf"` (M111/M130) or
`synthetic_from_aeat_published_text` (M131 since its only fixture is
synthetic per the prior closure).

### Snapshot-build validator: validate_bbox_anchor_consistency

Defense-in-depth registry rule added in `_validate_extraction_profiles.py`
+ `_validate_record_sections.py`: when `match_strategy == "bbox_anchored"`,
`bbox_anchor` must be present and well-formed; when the strategy is
numeric_casilla or named_label, `bbox_anchor` must be None. The
model_validator on `ExtractionTargetDefinition` enforces this at
construction time; the snapshot-build validator catches the same
invariant at registry-tree load time so a hand-edited TOML with a
mis-strategy cannot pass validation.

### Still deferred

The bbox primitive closes the line-end-numeric structural gap. It does
NOT address: OCR fallback for image-only PDFs (W02 original deferral
stands), arbitrary-table-cell extraction for forms outside the
single-column or fixed-column-layout families, or non-Latin-script forms.
The four remaining `provisional_pending_specimen = true` profiles
(M036, M184, M193, M232 ×2, M347, M720 — those without real-AEAT-PDF
specimens, only WebFetched AEAT-published printed-form text) remain in
that state until real specimens are acquired and verified, per the
2026-05-26 amendment's discipline.

---

## Amendment 2026-05-28 — Verification chain landed (W09.P40.S197)

### New module: `test_verification_chain.py`

`src/aeat/adapters/inbound/declaracion/test_verification_chain.py` (596 lines)
implements the project-mission end-to-end fidelity gate. The test chain:

1. `parse_declaracion(corpus_pdf)` → `DeclaracionObservation.values`
2. Filter extracted casillas to non-computed → `inputs: dict[str, Decimal]`
3. `calculate_registry_snapshot(snapshot, inputs=inputs, binding_values=...)` → `RegistryCalculationResult`
4. Assert `result.values[closure_casilla_id] == extracted[closure_casilla_id]`

All centralized infrastructure confirmed: `calculate_registry_snapshot` from
`aeat.domain.calculations.registry`, `RegistryValidationError` from same package,
`DeclaracionParseError` from `aeat.adapters.inbound.declaracion`, `parse_declaracion`
from `aeat.adapters.inbound.declaracion`, `FIXTURES_DIR` from `aeat.tests`.
No new exceptions, no new schemas, no mocks.

### Per-modelo verdict

| Modelo | Corpus | Engine formula verified | Verdict |
|--------|--------|------------------------|---------|
| M111 2024-1T/2T/3T | 3 PDFs | `28=sum(col-C)`, `30=28−29` | VERIFIED |
| M111 2024-4T | 1 PDF | negative filing; inputs=∅ | FORMULA-MISMATCH (corpus) |
| M130 2021-2T..2024-4T | 15 PDFs | `19=f(01..18)` | FORMULA-MISMATCH (corpus non-consistent) |
| M303 2023-1T..2024-4T | 8 PDFs | no registry formulas | VERIFIED (extraction) |
| M390 2022/2023 | 2 PDFs | leaf inputs not in profile | BINDING-GAP |
| M180 2024-0A | 1 synthetic | relation binding (M115) required | BINDING-GAP |
| M190 2024-0A | 1 real corpus | no formulas in registry | VERIFIED (extraction) |

### FORMULA-MISMATCH root cause

The M130 and M111-4T corpus PDFs were created for extraction testing only —
the sanitiser placed arbitrary round amounts in each field independently
without preserving the arithmetic chain. The engine computes arithmetically
correct results from the extracted inputs; the mismatch is a corpus-consistency
defect, not an engine defect. To achieve VERIFIED for M130, corpus PDFs must
be generated with formula-consistent synthetic values.

### Follow-up items surfaced

1. M130 formula-consistent corpus fixtures needed (15 PDFs).
2. M111 2024-4T negative-filing fixture: leaf inputs must be printed or casilla 30 must be 0.
3. M390 extraction profile expansion: add leaf sub-total casillas to enable engine verification.
4. M180 relation supply: requires M115 quarterly data as `relation_values`.

---

## 2026-05-28 amendment — discipline extended to justificante surface (W10.P41.S198)

### Audit findings (UNIT 1 + 2)

**Extraction model:** The justificante surface uses **hardcoded regex-driven extraction** in
`src/aeat/adapters/inbound/justificante/_extract.py` — NOT registry-profile-driven extraction.
The `ExtractionProfileDefinition` schema supports `surface = "justificante_pdf"` but the
`validate_extraction_profile_artefacts` gate explicitly rejects any `justificante_pdf` profile
that has `target_casillas`, blocking the registry-profile path at schema level. No
`justificante_pdf` registry extraction profiles exist in the TOML tree.

**Exception hierarchy pre-amendment:** `JustificanteParseError` in
`src/aeat/domain/justificante/_errors.py` was a bare string-message exception.
It had none of the `missing/malformed/ambiguous/coverage` structured attributes
that `DeclaracionParseError` carries, which forced test code and callers to
parse message strings to identify the failure kind — the exact brittleness class
closed by task #51.

**PROVISIONAL gates:** Both `validate_declaracion_pdf_specimen_gate` and
`validate_declaracion_pdf_round_trip_gate` guard on
`if profile.surface != "declaracion_pdf": return []` and are correctly dormant
for the justificante surface. Because no casilla-level corpus extraction exists
for justificante PDFs (AEAT receipts carry CSV/NIF/period/timestamp metadata, not
casilla values), the registry-profile gate discipline does not transfer. The
existing sidecar roundtrip tests (`test_corpus_sidecar_roundtrip.py`, landed in
task #41) are the discipline equivalent for the justificante surface.

**Silent-failure classes per surface:**

- *AEAT receipt format change* (new header layout, different CSV encoding): the
  five-tier CSV regex in `_extract_csv` is the primary exposure. The sidecar corpus
  covers 40+ fixture combinations; a format change surfaces as a
  `JustificanteCsvNotFoundError` across the corpus parametrize run.

- *Parser regex generalises poorly across years*: the `_PERIOD_POSITIONAL_RE` and
  `_EJERCICIO_LOOSE_RE` tiers were developed against known layouts; new layouts can
  silently extract the wrong value without raising. The 15 pre-existing
  `JustificanteCsvNotFoundError` failures on the `test_corpus_pdf_parses` parametrize
  (modelos 036, 115, 123, 131, 180, 184, 193, 232, 347, 349, 369, 720, 840) are this
  exact class — newly added corpus PDFs using a sanitiser layout whose CSV token is
  not matched by any current regex tier.

- *Sidecar and parser drift*: `test_corpus_sidecar_roundtrip.py` pins 40+ PDF+sidecar
  pairs. If the sanitiser injects a CSV token using the `SANITIZED{modelo}{year}`
  convention and the parser extracts a different token, the test fails loudly.

### Alignment applied (UNIT 3)

**UNIT 3(c) — Structured exception attributes (applied):**
`JustificanteParseError` in `src/aeat/domain/justificante/_errors.py` now carries
`missing`, `malformed`, `ambiguous`, and `coverage` structured attributes with the
same type signature as `DeclaracionParseError`. All error-raising sites in
`src/aeat/adapters/inbound/justificante/_extract.py` populate the appropriate
attribute: `_require()` sets `missing=(field,)`, `_parse_decimal()` accepts an
optional `field` argument and sets `malformed=(field,)` on parse failure,
`_parse_datetime()` sets `malformed=("presented_at",)`, and the URL extractor sets
`missing` or `malformed` as appropriate. Ten new tests in
`test_extract_helpers.py` and `test_parser.py` assert on the typed attributes.

**UNIT 3(a/d) — PROVISIONAL gates (not generalised; dormant by design):**
The existing gates are correctly scoped to `declaracion_pdf`. Generalising them to
also fire for `justificante_pdf` would be incorrect because: (a) no justificante_pdf
registry profile with `target_casillas` can pass schema validation; (b) the
justificante surface has no equivalent concept of "label_pattern accuracy" tracked
by the gate. The gate discipline for justificante is the sidecar corpus test, which
already exists.

**UNIT 3(b) — Sidecar coverage (documented, not extended this step):**
The 15 pre-existing corpus parse failures represent coverage gaps in the extractor,
not in the sidecar discipline. These fixture PDFs exist in the corpus (added by a
prior campaign) but use a receipt format not matched by the current regex tiers.
Closing those 15 failures requires adding new regex tiers or updating the sanitiser
to use an already-matched layout — that work is a separate extractor-expansion task,
not part of this discipline-alignment step.

### Honest verdict

The discipline transferred **with structural adaptation**. The justificante surface
is architecturally distinct from the declaracion surface (hardcoded regex vs
registry-profile-driven extraction), so the PROVISIONAL gate generalisation was
not applicable. The transferable part — structured exception attributes — was
applied cleanly. The sidecar corpus discipline (task #41) is the equivalent
gate for this surface and was already in place.

## 2026-05-28 amendment — borrador surface architectural exception (W10.P43.S200)

### Audit findings

The borrador surface (`src/aeat/adapters/inbound/borrador/`) was audited
for alignment with the registry-profile-driven extraction architecture this ADR
established for the declaración surface.

**Extraction model.** `parse_borrador` dispatches to a per-año concrete extractor
class from `_REGISTRY_BY_AÑO: dict[int, type]` in
`src/aeat/adapters/inbound/borrador/_extractors/__init__.py`. The single registered
class is `Modelo100ObservedV2025Extractor` (year 2025). There is no ABC, no
`(modelo, año, revision)` tuple key, and no consultation of
`RegistrySnapshot.extraction_profiles`. The per-año registry is a `dict[int, type]`
used to version year-on-year Renta PDF layout changes.

**Registry integration.** `BorradorExtractionProfile` in `_schema.py` is a
structural `Protocol` (duck-typed interface). It is supplied by the caller as an
optional parameter — not looked up from the registry snapshot inside the adapter.
The registry schema enumerates `"borrador_pdf"` as a valid `surface` literal in
`ExtractionProfileDefinition`; no `borrador_pdf` TOML extraction profiles exist in
the registry data tree. The Protocol is the integration boundary between the
application layer and the borrador parser.

**W02 ADR scope.** This ADR scoped exclusively to `declaracion_pdf` profiles and
the `parse_declaracion` surface. The borrador surface was not in scope for this ADR
or its superseded predecessor (`2026-04-21-declaracion-extractor-adr`).

### Accepted architectural exception

The borrador surface is **formally accepted as an architecturally distinct variant**
of the PDF extraction discipline. The rationale:

- The borrador extractor's purpose is to extract _all observable casilla/value rows_
  printed on a Renta PDF as an observed-value record, not to apply a registry-defined
  target-casilla filter. Its primary contract is coverage of what is printed, not
  what the registry declares as relevant.
- Renta Web Open PDFs (borrador, predeclaración) change layout year-on-year
  independently of registry revision logic. The `_REGISTRY_BY_AÑO` dispatch
  provides a clean, low-overhead mechanism for year-revision transitions without
  coupling extractor code to the registry fragment architecture.
- The `BorradorExtractionProfile` Protocol as a caller-supplied optional is a
  correct hexagonal boundary: the adapter remains registry-agnostic; callers
  (CLI, application layer) supply a profile projection when they need filtered
  extraction.

### Partial discipline gap: structured exception attributes

`BorradorParseError` does not carry the `missing/malformed/ambiguous/coverage`
structured attributes that `DeclaracionParseError` and `JustificanteParseError`
carry. This gap is the same class closed for justificante in `W10.P41.S198`.
Closing it for the borrador surface is a follow-up task independent of this
architectural acceptance.

### Decision

No migration of the borrador surface to registry-profile-driven extraction is
required. The per-año class dispatch and the `BorradorExtractionProfile` Protocol
are accepted as the canonical borrador extraction model. The follow-up obligation
is:

1. Add `missing`, `malformed`, `ambiguous`, and `coverage` structured attributes
   to `BorradorParseError`, updating error-raising sites and tests to populate
   them — aligning the borrador exception discipline with the declaracion and
   justificante surfaces.
2. No `borrador_pdf` TOML extraction profiles need to be authored unless a future
   use-case requires registry-authority-driven casilla selection from the borrador
   surface (at which point the Protocol boundary already accommodates it).

## 2026-05-28 amendment — verification chain extension closed (W10 wrap-up)

Commit `0a64250eb`. Step `W10.P49.S206`. Extends `test_verification_chain.py`
from 32 tests (Phase 2 baseline) to 45 tests (W10 close).

### Per-modelo verdict table (final)

| Modelo | Revisions              | Specimens         | Closure formulas | Verdict |
|--------|------------------------|-------------------|------------------|---------|
| M100   | 2021, 2022, 2023       | 3 real PDFs       | yes (complex)    | EXTRACTION-ONLY — mid-chain casillas extracted; deep actividades leaf inputs (017x) absent from declaracion_pdf profile. Follow-up: extend profile. |
| M111   | 2024                   | 4 real PDFs       | yes              | VERIFIED (1T/2T/3T) + NEGATIVA correctly handled (4T) |
| M115   | 2019-y-siguientes      | 1 synthetic PDF   | yes              | VERIFIED — 03=percent(02,rate), 05=03-04 |
| M123   | 2019-2023              | 1 synthetic PDF   | yes              | VERIFIED — 06-legacy=03+05, 08-legacy=06-07 |
| M123   | 2024-y-siguientes      | 1 synthetic PDF   | yes              | VERIFIED — 03=01+02, 06=04+05, 09=07+08, 12=10+11, 14=12-13 |
| M130   | 2021-y-siguientes      | 15 synthetic PDFs | yes              | VERIFIED — casilla 19 closure, 2021–2024 |
| M131   | 2026                   | 1 synthetic PDF   | yes              | VERIFIED — 07=02+04+06, 10=07-08-09, 13=10-11-12, 15=13-14 |
| M180   | 2023-y-siguientes      | 1 synthetic PDF   | yes (cross-mod.) | VERIFIED via M115→M180 relation_values |
| M184   | 2015-y-siguientes      | 1 synthetic PDF   | none             | EXTRACTION-ONLY — informativa; decl.ejercicio only |
| M190   | 2023-y-siguientes      | 1 real PDF        | none             | EXTRACTION-ONLY — no formulas in registry |
| M193   | 2024-y-siguientes      | 1 synthetic PDF   | yes (cross-mod.) | VERIFIED via M123→M193 relation_values |
| M303   | 2023-y-siguientes      | 8 real PDFs       | none             | EXTRACTION-ONLY — 12 casillas; formulas deferred |
| M347   | 2008-y-siguientes      | 1 synthetic PDF   | none             | EXTRACTION-ONLY — informativa; decl.ejercicio only |
| M349   | 2020-y-siguientes      | 1 synthetic PDF   | none             | EXTRACTION-ONLY — 4 summary casillas; no aggregation formulas |
| M369   | esquema-union          | 1 synthetic PDF   | none             | EXTRACTION-ONLY — decl.ejercicio + decl.periodo |
| M390   | 2022-y-siguientes      | 2 real PDFs       | yes              | VERIFIED (cuota-devengada-total + cuota-deducible-total); FORMULA-MISMATCH resultado (documented sanitiser artefact) |
| M720   | 2013-y-siguientes      | 1 synthetic PDF   | none             | EXTRACTION-ONLY — informativa; decl.ejercicio only |
| M840   | 2003-y-siguientes      | 1 synthetic PDF   | none             | EXTRACTION-ONLY — informativa; decl.tipo-declaracion + decl.ejercicio |

### Summary

- **9 modelos VERIFIED** (formula chain closes end-to-end): M111, M115, M123 ×2, M130, M131, M180, M193, M390 (partial).
- **8 modelos EXTRACTION-ONLY** (parser verified; no closure formulas or leaf inputs absent): M100, M184, M190, M303, M347, M349, M369, M720, M840.
- **1 modelo NOT-CHAIN-READY** (registry gap): M036 — no revision selector for year=2025 period=0A.

### Tracked follow-up items

1. **M100 leaf profile extension**: add actividades-económicas leaf casillas (017x series) to the declaracion_pdf extraction profile to enable full ED formula chain verification.
2. **M036 revision gap**: the synthetic fixture `2025-0A.pdf` does not match any revision selector. Investigate `2025-02-03-y-siguientes` period_selector and either extend it for period=0A or regenerate the fixture for the correct year.
3. **M303 formula coverage**: the 2023-y-siguientes revision carries no registry formulas; formula verification requires a dedicated future campaign.

---

## 2026-05-30 amendment — OCR research closure (W10.P44)

### W10 wave structural mission-complete

The W10 wave (`W10.P41` through `W10.P49`) reached structural mission-complete on
text-layer PDF extraction. Four PDF parser surfaces now carry discipline parity:

- `declaracion_pdf` — registry-profile-driven, three match strategies
  (`numeric_casilla`, `named_label`, `bbox_anchored`), 18 modelos enrolled,
  45+ verified chain proof points.
- `justificante_pdf` — hardcoded regex extraction, sidecar corpus discipline,
  structured `JustificanteParseError` attributes.
- `borrador_pdf` — per-año class dispatch, accepted architectural exception,
  structured `BorradorParseError` attributes.
- Bank PDF — `FinancialProvider` ABC, `CorpusVerificationSource` provenance enum,
  `BankStatementParseError` structured attributes.

The two gate fields (`provisional_pending_specimen`, `corpus_round_trip_verified`)
and the structured exception pattern (`missing/malformed/ambiguous/coverage`)
are now consistently applied across all text-layer surfaces.

### OCR deferred extension: research now landed

The W02 ADR (`2026-05-21` decision section, "Still deferred") explicitly named
OCR fallback for image-only PDFs as a future extension. `W10.P44.S201` tracked
this as the deferred research deliverable, intentionally held back during the
active declaration-extraction campaign to avoid displacing text-layer work.

Research has now been authored at
`2026-05-30-declaracion-extraction-architecture-research.md`
and is the canonical input for the next-campaign ADR. Key findings:

- The OCR evidence path (`src/aeat/application/ledger/_evidence.py`) is
  **entirely unimplemented**. `PurchaseInvoiceEvidence` stores file hashes and
  manual overrides; there is no OCR pipeline, no extraction confidence field,
  no extraction method field, and no OCR library dependency.
- The 2026-05-12 receipt-OCR-pdf-evidence ADR mandated OCR confidence and
  extraction-method tracking; neither has been delivered.
- OCR introduces seven silent-failure classes that the text-layer discipline
  does not address (image quality degradation, supplier-layout variation,
  multi-page continuation, thermal-paper fading, non-Spanish-locale number
  formats, OCR engine version drift, aggregate-confidence false floors).
- The discipline analogue transfers — `InvoiceCorpusSource` provenance enum,
  `InvoiceOcrExtractionError` structured attributes, confidence-threshold
  gate — but requires a **separate ADR** because the surface layer
  (application/ledger), document class (operator-uploaded supplier invoices),
  and extraction technology (OCR vs text-layer) are all distinct from what
  this ADR governs.

### Decision

A separate ADR titled `purchase-invoice-ocr-extraction-discipline` is the
correct next-campaign vehicle. This ADR does not govern the OCR surface; it
formally documents the research closure and points at the durable artefact.
No changes to this ADR's existing decisions are required.

---

## Amendment W12.P65.S216 - M303 Closure DAG Extension (2026-05-30)

### Context

The M303 closure formula DAG previously computed only box 46 (resultado
regimen general = 27 - 45) via `modelo-303-iva-resultado-regimen-general`,
and box 69 with a simplified formula `c46 - c78` that was only correct when
all intermediate boxes were zero. Boxes 64, 66, and 71 were classified as
`input_kind = "manual"` in the casilla catalogue, meaning they could not be
engine-verified against corpus PDF extractions.

Orden HAC/819/2024 (BOE-A-2024-6840), Articulo 1 §§4-6, specifies the
complete closure chain:

- §4: box 64 = box 46 + box 58 + box 76 (suma de resultados)
- §4: box 66 = (box 64 * box 65) / 100 (atribuible Administracion del Estado)
- §5: box 69 = box 66 + box 77 + box 68 - box 78 (resultado autoliquidacion)
- §6: box 71 = box 69 - box 70 + box 109 (resultado final)

### Decisions

1. Added three new formulas to the `2023-y-siguientes` revision TOML:
   `modelo-303-iva-suma-resultados`, `modelo-303-iva-atribuible-estado`,
   `modelo-303-iva-resultado-final`. All cite `orden-hac-819-2024:art-1`.

2. Corrected `modelo-303-iva-resultado` (box 69) from the simplified
   `c46 - c78` to the canonical `(c66 + c77 + c68) - c78`.

3. Changed casillas 64, 66, and 71 from `input_kind = "manual"` to
   `input_kind = "computed"` with explicit `formula` backlinks.

4. Registered `orden-hac-819-2024:art-1` in the legal catalogue
   (`iva.toml`) with evidence_tier `legal_authority`, BOE-A-2024-6840,
   and the required corpus HTML file at
   `corpus/normatives/html/orden-hac-819-2024-art-1.html`.

5. Box 65 (porcentaje atribuible Estado) remains `input_kind = "manual"`;
   for standard territorio-comun filers it is 100. Engine tests supply
   `Decimal("100")` directly.

6. All 16 M303 corpus PDFs regenerated with formula-consistent values.
   32 new VERIFIED engine-recomputes tests added covering all 4 closure
   boxes across 8 new-template specimens (2023-1T through 2024-4T).
