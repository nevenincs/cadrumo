---
tags:
  - '#research'
  - '#registry-temporal-coverage'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:b8b9f080e3c91e3a85ff6dc503d56fcd784c310e1e8dca20e2ceb854ca0b4619'
related:
  - "[[2026-08-14-registry-temporal-coverage-research]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
---

# `registry-temporal-coverage` research: `design corpus acquisition worklist`

Which modelos' declared revisions can never be corpus-proven by `[[2026-08-14-registry-temporal-coverage-research]]`'s coverage instrument, what years each one's declared law actually needs, and — now that the tagging-exercise owner's title-based attribution has landed — which of those gaps acquisition from AEAT must close versus which ones this repository has already resolved by reading evidence it already possessed more carefully.

This document was first written scoped to the stable slice only (17 modelos with zero bundled design files), deliberately excluding the attribution-dependent population while the policy was still moving. That policy has now landed (`_design_coverage_years`, unioning title-text and field-constant attribution with the existing filename regex). This revision adds the second half: what changed, the new third category the landing created, and a reconciliation between two independently-derived enrolment-population counts.

## Findings

### 17 modelos carry zero bundled design files, confirmed by directory absence — unaffected by attribution

Every one of the following has NO `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_<id>/` directory at all — not an empty directory, not a directory with unparseable files, but no directory: 121, 136, 140, 143, 179, 186, 231, 233, 234, 238, 289, 361, 379, 380, 592, 721, 848. Verified directly against the filesystem, not inferred from a parse failure, so a future extractor fix cannot silently "discover" a design that was never bundled. Re-verified after attribution landed: unchanged, since attribution can only reclassify files that exist, and these 17 have none. **Confirmed a third time via an entirely different derivation** (see the reconciliation finding below): a source-catalogue-based check ("does a `record_design`-shaped source exist, and does a bundled file exist regardless") lands on the identical 17 modelo ids. Three independent methods, one filesystem walk, one registry-source check, one bundled-file check, all agreeing — this is the most corroborated number in the whole coverage workstream.

### Per-modelo needed span for the 17, measured against today's calendar year

| modelo | declared revision | needed span |
|---|---|---|
| 121 | `2017-y-siguientes` | 2017–2026 |
| 136 | `2026` | 2026 |
| 140 | `2020-y-siguientes` | 2020–2026 |
| 143 | `2014-y-siguientes` | 2014–2026 |
| 179 | `2021-y-siguientes` | 2021–2026 |
| 186 | `2003-y-siguientes` | 2003–2026 |
| 231 | `2021-y-siguientes` | 2021–2026 |
| 233 | `2018-y-siguientes` | 2018–2026 |
| 234 | `2021-y-siguientes` | 2021–2026 |
| 238 | `2024-y-siguientes` | 2024–2026 |
| 289 | `2025` | 2025 |
| 361 | `2010-y-siguientes` | 2010–2026 |
| 379 | `2024-y-siguientes` | 2024–2026 |
| 380 | `2005-y-siguientes` | 2005–2026 |
| 592 | `2022-y-siguientes` | 2022–2026 |
| 721 | `2023-y-siguientes` | 2023–2026 |
| 848 | `2003-y-siguientes` | 2003–2026 |

14 of 17 are open-ended (`...-y-siguientes`), so the acquisition need does not shrink to one year — a re-layout could land anywhere across the full span.

### Two genuinely single-year modelos in the 17

136 (`2026`) and 289 (`2025`) declare their entire span as one filing year, and neither has a second declared revision at all. Acquiring one design closes "no corpus at all" for either but does not by itself satisfy the neighbour-comparison check (`[[2026-08-14-registry-temporal-coverage-research]]`) — there is still nothing adjacent to compare it against.

### `disenos_registro` manifest presence — uniformly absent across the 17, not a distinguishing factor

All 17 show no directory at all; none has a partially-populated manifest. A framing that singled out Modelo 289 as uniquely lacking design provenance was not corroborated by this check — provenance absence is uniform across the set on this axis. If 289 is worse in some other sense, that needs its own verification before being repeated as a finding.

### Attribution landing: 11 of 20 previously-invisible modelos now have at least one attributed design

Before `_design_coverage_years` landed, 20 modelos had design files on disk but ZERO filename-attributable ejercicio year (`_design_years` alone, on every file `_design_sources` returns): 038, 145, 156, 165, 180, 181, 187, 188, 189, 190, 194, 210, 270, 280, 360, 369, 576, 720, 763, 840. Re-measured against the current pipeline (title text + field constants + filename, unioned): **11 of those 20 now resolve at least one attributed year** — 156, 165, 180, 181, 187, 188, 189, 190, 194, 270, 280. Modelo 190 gained the most: 0 → 4 attributed years (2021, 2023, 2024, 2025).

This is real progress, but it is progress on VISIBILITY, not on PROOF. Of the 11, only Modelo 190 now has enough distinct attributed years (4) to be genuinely compared; the other 10 gained exactly ONE attributed year each, which is not enough to satisfy the multi-year branch's two-comparable-year requirement (`[[2026-08-14-registry-temporal-coverage-research]]`) on its own. Confirmed against the relayout gate directly: of the 11, only 190 (together with 193, discussed below) moved category — from "needs more corpus" to "proven relayout crossing", a reclassification onto the true cause, not a new pass. **Zero revisions moved from failing to passing as a direct result of attribution landing.** The other 9 (156, 165, 180, 181, 187, 188, 189, 194, 270, 280) still fail the coverage instrument, now for a MORE PRECISE reason — "one comparable year, need a second" rather than "zero comparable years" — but still fail. Acquiring ONE more design year for each closes the gap; acquiring the design that ALREADY EXISTS was not, in fact, the blocker for these 10 — the second year is.

(Modelo 193 is a related but distinct case, not one of these 20 — it already had one filename-attributed year before attribution landed, and gained a second via the same pipeline, which is why it also newly reclassified to "proven relayout crossing".)

### A third category the landing created: UNMEASURED — files exist, state no ejercicio anywhere

9 modelos carry design files on disk that resolve to ZERO attributed years even under the full title+constant+filename pipeline: 038, 145, 210, 360, 369, 576, 720, 763, 840. Re-derived under the corrected absent/unparseable/non-ejercicio distinction: **all 9 are cleanly and entirely non-ejercicio-scoped** — every file each of them carries parses without error and states no ejercicio anywhere in its content or filename. Zero of the 9 hold an unparseable file. This is a genuine answer, not a defect in the attribution work — the coverage pipeline's own documented intent is that some designs are legitimately scoped by something other than an ejercicio (a registro in force from a date, a devengo span). These are NOT acquisition gaps in the same sense as the 17: a file already exists, so fetching one from AEAT does nothing — what is missing is either a metadata source this pipeline does not yet read, or a registry-side decision that these modelos are legitimately unattributable by ejercicio and need a different validation shape than the year-comparison instrument provides. Do not fold this into the acquisition count.

Modelo 720 is notable here: it was measured earlier this campaign as "one act from filable" on the attestation axis, and independently sits in this UNMEASURED set on the corpus-coverage axis — the two gates are answering different questions and a taxpayer-facing "can this modelo file" answer needs both closed, not either alone.

### Modelo 036 is the ONE mixed case, and the gate now says so directly rather than needing a hand-check

Modelo 036 is NOT one of the 9 clean UNMEASURED modelos above — it carries a genuinely mixed cause across its 5 bundled files. 2 files (`...-2025-y-siguientes...xlsx`, the current in-force design and its provisional sibling) parse their sheets fine and legitimately resolve zero ejercicio years — matching the pipeline's documented intent for a date-scoped registro, the same shape as the 9. The other 3 (`...-ejercicio-2023-y-siguientes...`, two `...-ejercicio-2021-y-siguientes...` files) carry a real filename-attributable year (2023, 2021, 2021) but `_design_sheets` returns ZERO parsed sheets for all three — a total parse failure, not the partial-read shape the extraction-layer work elsewhere in this campaign is making representable. `_designs_in_publication_order`'s own first filter drops a design whose sheets do not parse before year-attribution is ever consulted, so these 3 files' filename-derivable years never reach any comparison, for a reason unrelated to attribution policy.

**This is no longer a hand-check finding — the gate now makes the distinction itself.** `_unparseable_design_sources(modelo_id)` returns every bundled file whose sheets fail to parse entirely, and both of the coverage gate's failure branches (the multi-year "only N comparable years" message and the single-year `_neighbour_divergence` message) now consult it before naming a fix: a missing year backed by an unparseable file is reported UNPARSEABLE ("fix the extractor, acquiring another copy would not help"), never conflated with a genuinely ABSENT year ("bundle AEAT's published design") or a parsed-but-non-ejercicio design (silently correct, no failure at all for that file). Verified against Modelo 036's own revision: its current declared span (`2025-02-03-y-siguientes`) does not happen to need 2021 or 2023, so the unparseable files do not presently appear inside any live gate failure — but the mechanism was bite-proofed synthetically both directions (a fabricated unparseable file inside a span reports UNPARSEABLE; none present reports ABSENT) before being trusted, since the live corpus currently offers no in-span example to exercise it against.

Not fixed here: the underlying parser gap (`_design_sheets` / the xlsx extraction backend) is a parsing-layer question, outside this worklist's scope. Flagging it, and now having the gate flag it automatically, is what keeps a future "Modelo 036 needs acquisition" reading from being wrong when three of its five files are already bundled and simply unreadable.

### Reconciling two enrolment-population counts: 29 (revisions, source-declaration) versus 34-35 (modelos, proof-sufficiency) — different questions, both real, deliberately not collapsed to one

A second population was independently derived by a peer working the registry's `record_design` source-enrolment: **46 revisions declare no `record_design`-shaped source at all; of those, 29 have a bundled design file present in the corpus and 17 do not.** That 17 is the SAME 17 modelo ids as this document's acquisition list, confirmed above — strong, independent corroboration of the one number that matters most for the operator.

The 29 does not equal either of this document's own modelo-level counts (34 modelos short of two comparable years overall in the earlier close-out audit, or 35 in a later refinement), and it should not be forced to. **They measure different things.** The 29 counts REVISIONS by a source-DECLARATION criterion: is a `record_design`-kind entry present in the registry's source catalogue for this revision, regardless of whether that revision's coverage can be PROVEN. The 34/35 counts MODELOS by a proof-SUFFICIENCY criterion: does every one of this modelo's revisions have at least two comparable corpus years. A modelo can be short of proof while its bundled file is already correctly declared as a source (nothing to enrol, still nothing to compare against); another can have an undeclared bundled file that, once declared, still would not supply a second comparable year. The two axes are independent by construction, not merely by coincidence of counting error.

Tried to close the gap toward an exact reconciled figure by deriving the strictest defensible per-revision match — an undeclared revision whose bundled file's attributed year genuinely falls inside that SPECIFIC revision's own declared need, not merely "some file exists somewhere in the modelo's directory." That check landed on **21**, stable across two different declared-source definitions (strict `record_design`-only, and the broader `record_design`-or-legacy-`form_spec` reading below). 21 is offered as the most rigorously-derived number available, not as a supersession of 29: the difference between 21 and 29 was not tracked down (the most likely remaining variable is the needed-years upper bound each derivation used), and per operator directive this gap is not worth closing further while enrolment itself is blocked on provenance recoverability, not on the exact count. **Record all three figures with their units rather than picking one:** 29 revisions (source-declared, modelo-directory-file-present), 21 revisions (source-declared, file-present-AND-year-matched, this document's own strictest derivation), 34-35 modelos (proof-insufficient, a different axis entirely).

### A live measurement trap, independent of which count is right: two coexisting conventions for "this AEAT design is declared"

While deriving the reconciliation above, found that **some modelos already declare their AEAT record design under the OLDER `kind = "form_spec"` convention rather than the current `kind = "record_design"` + `record_design_epoch` shape** — Modelo 280's `aeat-dr-280-2022` source is the clearest example, hash-pinned and correctly declared, but carrying `kind = "form_spec"` with no `record_design_epoch` field at all. A measurement that filters strictly on `kind == "record_design"` reports these modelos as UNENROLLED when they are not, silently inflating whatever "needs enrolment" count it produces.

This is not a footnote to the count above; it is its own finding, and it is the same pattern the operator has named repeatedly across tonight's work: two vocabularies coexisting for one concept, with nothing in the schema or a gate declaring which is canonical or requiring both to be read together. The `valid_to`-versus-year-selector split, `data_type` carrying two meanings, five type vocabularies elsewhere in the registry, a filesystem view and a registry-source view of the same corpus with no shared authority (recorded separately in the coverage audit) — and now a `form_spec`/`record_design` split on the exact concept this enrolment effort is trying to measure. **Anyone deriving an enrolment count, now or later, must read both `kind` values as "AEAT design declared" or the number is wrong before the first modelo is touched.** Whether `form_spec` should be migrated to `record_design` + a back-filled `record_design_epoch`, or the two are kept as a deliberately dual-recognized pair, is a registry-authoring decision this document does not make.

### Extension: the same acquisition shape applies to legal citations, not only designs — 10 revisions across 8 modelos

Authorized follow-on to the vein this worklist otherwise covers (the coverage-instrument research and its governing ADR): a revision whose corpus-proven relayout (`_boundaries_for`) is not backed by ANY second orden citation is not thereby proven unrevised — it is a legal-catalogue acquisition gap of the identical shape as a missing design file, with a different fetch target. `test_every_modelo_revision_span_is_corpus_proven` (`src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`) now reports this as its own DISTINCT failure reason, `NO LEGAL EVIDENCE OF REVISION RECORDED`, appended alongside — never in place of — the design-evidence failure it accompanies, and it is coded so it can never become a pass condition: only a positively-cited amending or superseding orden clears it, never the absence of one.

Measured directly against the live gate (`_distinct_orden_documents`, counting distinct BOE orden documents — by the token before the first `:` — cited anywhere across a modelo's own revision history): **10 revisions across 8 modelos** carry a corpus-proven relayout while citing only their founding orden, tree-wide, exhaustively swept rather than sampled:

| modelo | revision(s) | sole cited orden |
|---|---|---|
| 193 | `2024-y-siguientes` | `orden-eha-3377-2011` |
| 200 | `2024-y-siguientes` | `orden-hac-657-2025` |
| 220 | `2024-y-siguientes` | `orden-hac-657-2025` |
| 303 | `2009-y-siguientes`, `2024-desde-09-y-3t`, `2024-hasta-08-y-2t` | `orden-eha-3786-2008` |
| 322 | `2008-y-siguientes` | `orden-eha-3434-2007` |
| 353 | `2008-y-siguientes` | `orden-eha-3434-2007` |
| 604 | `2021-y-siguientes` | `orden-hac-510-2021` |
| 714 | `2021-y-siguientes` | `orden-hac-1023-2021` |

322 and 353 are the confirmed pair the ruling named directly (each is the modelo's ONLY declared revision, so the "relayout" here means the corpus proves the bundled record-design layout changed somewhere inside one continuously-declared 2008-onward span, with nothing in the legal catalogue dating or authorising that change). 200 and 220 share their sole orden because they are filed under the same base order (Sociedades and its consolidated-group counterpart); 303's three revisions share one founding orden despite the modelo's own later revisions (`2023`, `2025`, `2026-y-siguientes`) already citing that same single orden too — the 2024 mid-year split is real and corpus-proven, but nothing in the catalogue names the instrument that authorised splitting one year into two filing halves.

**This is an acquisition list, not an authoring licence**, per the ruling: record what is missing, never compose or infer the missing orden's citation, article, or text. Provenance rules are unchanged from every other enrolment this worklist tracks — `source_url` and `retrieved_at` observed or absent, nothing fetched, nothing invented. Closing any one of these 10 rows requires locating the actual BOE instrument AEAT used to authorise each later layout and grounding it the same way every other `legal.*` entry in this registry is grounded — not merely finding A later orden and assuming it fits.

Distinct from the 17-modelo design-acquisition list above: a modelo can appear on neither list (fully proven both ways), one list only (322/353 already have their one design comparably read — the corpus evidence itself is what triggered this finding, so they are NOT on the 17 design-gap list), or in principle both (no such case was found in this sweep — every modelo in this legal-gap table already clears the design-comparison requirement that produced the relayout proof in the first place, which is the precondition for this failure reason to fire at all).

## Sources

- `[[2026-08-14-registry-temporal-coverage-research]]` — the coverage-instrument research this worklist extends; defines the corpus-comparison mechanism, the neighbour-comparison branch, and the `_current_filing_year` convention this document reuses.
- `[[2026-08-14-registry-temporal-coverage-adr]]` — the governing decision record for the coverage gate this worklist supports.
- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py` — `_designs_for`, `_design_sources`, `_design_coverage_years`, `_designs_in_publication_order`, `_declared_span_is_single_year`, `_neighbour_divergence`, `_boundaries_for`, `_current_filing_year` — the functions this worklist's measurements were run through directly.
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/` — the bundled design corpus whose directory listing and file-level parse results were checked per modelo; the per-modelo `manifest.json` sidecars recording `source_url`/`retrieved_at`/`sha256`/`bytes` for every bundled artefact.
- `src/cadrumo/domain/calculations/registry/_loader.py` — `load_registry_tree`, used to read each modelo's declared `period_selector` fields.
- `src/cadrumo/domain/calculations/registry/_schema_references.py` — `SourceReference`, the schema behind a `record_design`/`form_spec` source declaration.
- `src/cadrumo/domain/calculations/registry/_corpus_catalogue.py` — `resolve_record_design_binary`, `verify_source_catalogue`, the byte-integrity and epoch-matching consumer of a declared `record_design` source.
