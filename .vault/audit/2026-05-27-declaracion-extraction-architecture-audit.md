---
tags:
  - '#audit'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-20-branch-reconciliation-audit]]"
---

# `declaracion-extraction-architecture` audit: `session-2026-05-26-and-27 honest post-rush self-audit`

## Scope

Self-audit of the work I introduced during the two-session rush (2026-05-26
and 2026-05-27) that drove the declaracion-extraction-architecture campaign
from ~5 GROUNDED profiles to 16 GROUNDED + 3 GAP-DOCUMENTED + 1
HISTORICALLY-GROUNDED across 33 phases / 180 steps.

The rush delivered substantial progress but moved fast. This audit catalogs
defects, drifts, weakenings, and discovered-but-deferred items honestly so
they can be tracked and remediated.

## Findings

### HIGH severity — real defects worth fixing

#### H1. Synthetic-fixture circularity for AEAT-text-grounded modelos

For ten modelos this session (M036, M037, M180, M184, M193, M232 ×2
revisions, M347, M349, M369, M720), the workflow was: extract printed-form
text from AEAT-published material (Anexos, Diseños, instruction PDFs), then
author a SANITIZED synthetic fixture using THAT extracted text, then assert
the parser matches THAT text. The round-trip is real but the text on both
sides comes from the same AEAT source rather than the parser exercising a
real AEAT printed-form PDF. The `corpus_round_trip_verified = true` flag now
conflates two distinct verification strengths: real-AEAT-corpus-verified
(M100, M190, M303, M390) versus synthetic-from-AEAT-text-verified (the ten
modelos above). The flag's gate passes both, but the verification weight
differs. Closing this requires a finer typed `verification_source` field on
`ExtractionProfileDefinition` distinguishing
`real_aeat_corpus_pdf` / `synthetic_from_aeat_published_text` /
`historical_suppression`.

#### H2. PROVISIONAL gate test coverage gap (broader pattern)

The original task #34 unit tests for `validate_declaracion_pdf_specimen_gate`
constructed `RegistryValidator(catalogues, justificante_corpus_root=...)`
with direct injection, bypassing the production code path that derives
`corpus_root` from `source_root`. The gate was silently disabled in
production for the entire window between commit `e285001d0` and the code
review catch at commit `8c8865d90`. Tests passed because they exercised the
gate logic with explicit injection but never the production wiring. The
specific bug was fixed and a production-path test added, but the broader
pattern (unit tests bypass production wiring via direct dependency
injection) was not audited across other tests authored in this session.
`validate_declaracion_pdf_round_trip_gate` (task #38) followed the same
pattern.

#### H3. Cumulative target_casillas shrinkage via "REMOVED" verdicts

Across the grounding push, five casillas were removed from `target_casillas`
arrays as the dispatches concluded that the AEAT printed form does not
expose the casilla as a labelled field: `decl.vigencia-2025` from M036,
`decl.tipo-declaracion` from M720, M184, M347, and `decl.cnae` adjustment
on M232. Each removal is individually justified by the EDI specification
(positions 121-122 are flag bytes for `complementaria`/`sustitutiva` etc.,
not a printed label). The cumulative effect was not audited: do the
calculation-completeness manifests for these modelos still resolve cleanly
when the extraction profile no longer covers those casillas? Are those
casillas marked as `input_kind = "informational"` or otherwise
non-extractable in the registry, or are they expected-extractable casillas
that now have no extraction path?

### MEDIUM severity — drifts and weakenings

#### M4. Cross-campaign WIP sweep commits muddied authorship attribution

Approximately 14 "sweep:" commits I authored contained files modified by
other concurrent campaign agents, committed via explicit-path staging to
keep the working tree clean. The explicit-path-staging memory rule was
respected (no ambient `git add -A`), but the commits are git-stamped under
my authorship for changes I did not author. The "factory-direct, no PRs"
policy makes this operationally acceptable but the audit trail conflates
my work with other agents' work.

#### M5. Plan-doc attribution scattered

Several subagent dispatches added step records to whatever plan-doc they
deemed relevant rather than the canonical
`2026-05-21-declaracion-extraction-architecture-plan.md`. Task #39
landed steps on `2026-05-22-secure-storage-production-hardening-refactor-plan.md`;
task #40 landed on `2026-05-20-schema-hardening-plan.md`; task #36 bonus
M200 fix landed elsewhere. The campaign plan has 33 phases now but the
true work surface is wider than the plan tree shows.

#### M6. `.vault-scratch/bound_casilla_sweep.json` committed in a sweep

A `.vault-scratch/` file was included in a sweep commit. The memory rule
`audit_docs_via_vaultspec_only` says scratch directories must never be
swept; durable artifacts go to `.vault/` via vaultspec-core. The file
should have been left untracked or `.gitignore`d.

#### M7. M193 `_total` suffix reversal not independently verified

Task #32 audit flagged the `_total` suffix on M193's `decl.base-total` and
`decl.retenciones-total` patterns as fabrication-risk because the AEAT EDI
field name does not include `_total`. The M193 grounding dispatch (task
#48) reversed the audit's caution, arguing that the suffix is a
"fixture-disambiguation convention" matching M180's pattern. The reversal
may be correct but the audit's verdict was overturned on one agent's
reasoning without independent verification against the AEAT printed form
or a structural cross-check against M180's actual extraction behaviour
on real corpus PDFs.

#### M8. `_temporal.py` case-sensitivity fix unaudited across callers

A one-line change to `select_revision` at `_temporal.py:27` made period
comparison case-insensitive. The fix correctly handled M036's lowercase
canonical periods (`alta/modificacion/baja`) against the uppercase
`period_override` produced by `_resolve_period()._upper()`. The change
was not audited for other callers that might legitimately depend on
case-sensitive period matching (e.g. modelos with quarterly periods
where the registry distinguishes `1T` versus `1t`, or any caller that
treats period strings as case-sensitive identifiers downstream of
`select_revision`).

#### M9. M190 revision-id rename rationale incomplete

Task #36 Cluster B renamed M190 revision id from `"2025-y-siguientes"`
to `"2024-y-siguientes"` with `period_selector.year_from = 2024`. The
audit confirmed AEAT 2024 and 2025 EDI specs are structurally identical,
justifying single-revision coverage. The audit did not document whether
the original `"2025-y-siguientes"` name was intentionally
forward-looking (covering 2025+) at authoring time or accidentally
future-only. The rename was correct for the corpus PDF (year 2024)
but the semantic shift was not recorded in an ADR amendment or step
record commentary.

#### M10. Gap-tests brittle to parser error-type changes

The M111, M130, and M131 gap tests
(`test_parser_modelo_111_*`, `test_parser_modelo_130_*`,
`test_parser_modelo_131_numeric_casilla_profile_gap`) assert the parser
raises `DeclaracionParseError` with specific message content
(`coverage=0`, `missing=01..15`). If the parser's error format or
exception type changes (a likely outcome of further hardening), the
gap tests will fail in confusing ways or pass under wrong conditions
rather than catching real bugs. They should assert on structured
exception attributes (a typed `failure_mode` enum, a `missing` tuple)
rather than message text.

### LOW severity — housekeeping

#### L11. Subagent suite-verification scope often partial

Most dispatch deliverables reported scoped pass counts like "98/98 tests
pass" or "127 passed" rather than the full ~1923-test registry +
declaration suite. Cumulative drift across multiple parallel dispatches
in one wave is harder to detect without a final full-suite run.

#### L12. Step Record granularity drift

Plan-hardening convention says one Step = one prompt-run + one commit.
Several dispatches produced step records covering multiple commits
(profile commit + fixture commit + test commit + step-record commit, all
under one Step id). The convention's spirit was met (one logical
deliverable per Step) but the letter (one commit per Step) was not.

#### L13. `_generate.py` PDF determinism drift

Standalone fixtures (`modelo_100_2025A.pdf`, `modelo_130_2026Q1.pdf`,
`modelo_303_2026Q1.pdf`, the new 036/180/349/369/720/840 fixtures) keep
showing as modified across sessions when the source `_generate.py` has
not changed. Indicates reportlab metadata non-determinism (timestamp,
producer string). Eliminates would stop the rolling fixture-regen
sweep commits.

#### L14. PROVISIONAL gate scope limited to declaracion_pdf

The strengthened gate (`corpus_round_trip_verified` plus
`provisional_pending_specimen`) only enforces discipline on
`surface == "declaracion_pdf"` profiles. Other extraction surfaces
(`borrador_pdf`, `justificante_pdf`, `export_record`,
`official_workbook`) have no equivalent gate. If those surfaces have
profiles authored from registry self-reference, the silent-failure
class still exists for them undocumented.

#### L15. Cross-attribution risk in sweep commits

Files in sweep commits may have been in transitional mid-edit states by
other agents. Explicit-path staging mitigates but does not eliminate the
risk: I committed a file an agent was actively editing, freezing a
half-completed state.

## Recommendations

Track each finding as a plan step under a new phase. Dispatch the highest-
leverage remediations in parallel:

- **H1 + H3 + M4**: a structural fix promoting verification-source to a
  typed schema field, plus a coverage-drift audit verifying the
  completeness manifest still aligns after the target_casillas removals.

- **H2 + L14 + M4**: a test-coverage audit asserting that registry-gate
  unit tests exercise the production wiring (snapshot-build path) and
  not just direct-injection, plus extending the gate to other surfaces.

- **M7**: re-audit M193 `_total` suffix conclusion against an actual M193
  printed-form sample if any becomes available, or document the
  remaining uncertainty in the profile comment.

- **M8**: audit `select_revision` callers for case-sensitive expectations
  that could be regressed by the new case-insensitive comparison.

- **M9 + M10**: ADR amendment recording the M190 rename semantic, plus
  restructuring the gap tests to assert on typed exception attributes.

- **M6**: remove the `.vault-scratch/` file from git history if safe, or
  add the path to `.gitignore`.

- **L13**: investigate `_generate.py` PDF determinism.

- **L11 + L12**: process-discipline reminders for future dispatches;
  no remediation needed beyond the documentation.

## 2026-05-27 second-pass amendment — honest follow-through

After the first-pass remediation (W08 phases P34-P37) closed many findings via
"acknowledged" or "documented" rationales, a strict-honest review (tasks #57-#64)
re-opened the deflected items. Material findings that overturn earlier closures:

**Finding A — Concurrent-campaign regressions hidden as "pre-existing"** (task
#59 verification): The two test failures task #51 classified as "pre-existing,
unrelated" were ACTUALLY regressions introduced during this session by
concurrent-campaign commits authored by the same operator under different task
IDs. `test_previous_filing_selector_accepts_singular_source_output_shape`
was broken by commit `63e6bd6bc` (m130 carry-forward retired the
`_PreviousModeloSelector.relation` field without updating callers, 09:11:58);
`test_no_hand_summed_aggregation_tests_across_codebase` was broken by commit
`13818f914` (no-synthetic-sede plan-close reverted commit `b84c03ce7`'s
hand-summed fix at 08:59:31). Both fixed within the same morning at commits
`120243920` and `cc3a6d32f`. Both currently passing at HEAD. The
"pre-existing" classification was wrong; the cross-attribution risk M4 / L15
flagged is operationally real and active, not theoretical.

**Finding B — M036 uppercase-period drift caused by the M036-grounding work
itself** (task #61 trace): The uppercase ALTA/MODIFICACION/BAJA values in
M036's `period_selector` that motivated the `_temporal.py:27` case-insensitive
fix were introduced by commit `33783e00c` (the M036 grounding work from this
session at 06:33), which mirrored AEAT Anexo 3 HTML table display casing
without checking the domain-layer constant `CENSUS_MODELO_EVENT_KINDS`
canonicalized as lowercase 10 days earlier. Fixed in commit `472de9c02`
21 minutes later. The subsequent `_temporal.py` case-insensitive mask in
`c5deb30ff` does not protect the case-sensitive equality guard in
`_active_036_ownership_from_registry()`. Task #63 added a registry-author
lint test (`test_m036_revision_periods_are_lowercase_canonical`) at commit
`8e84ad7e1` to catch future re-introduction. The drift class is closed
through the lint; the masking comparison in `_temporal.py` remains as a
secondary defence but is no longer the only protection.

**Finding C — `verification_source` honor-system tightened to fixture-
metadata-verified** (task #58): The `verification_source` enum added in task
#49 was honor-system — a profile tagged `real_aeat_corpus_pdf` against a
synthetic reportlab-generated fixture would pass validation. Commit
`61654633c` added `test_verification_source_fixture_metadata.py` that walks
every grounded profile, reads fixture `/Producer` PDF metadata, asserts
`real_aeat_corpus_pdf` profiles have NO `aeat-test-fixture-generator`
producer string and `synthetic_from_aeat_published_text` profiles DO have
it. 18 parametrized + sentinel tests pass; no mis-tagged profiles. Edge
case documented: a synthetic generator that omits `setProducer` cannot
be distinguished from real AEAT PDF; protected by the invariant that
`_generate.py` always sets the explicit producer string (established by
commit `a04be5ff2` task #53).

**Finding D — M037 AEAT-surface search exhausted** (task #60): The earlier
M037 closure as "historically suppressed" was correct but never empirically
verified. Commit `1a9eaa34c` exhausted every AEAT Sede URL pattern, the
Diseños de Registro archive (which lists M036 then M038 with M037 absent
entirely), and captured the BOE-A-2025-410 suppression order. SEARCH_LOG.md
authored documenting every URL attempted so future agents do not repeat
the search. Domain-enforced absence is the only correct state for M037,
now empirically established.

**Finding E — Pure-production-path gate tests honestly limited** (task #62):
The earlier "production-path" test added in task #50 was classified
"Hybrid" by the same agent's own pre-survey table (used `source_root` plus
direct `corpus_root` injection). Commit `7749a997f` added three pure-
production-path tests (`source_root=bundled_path()` with NO kwarg
injection). Honest finding: specimen-gate Scenario A (no fixture + no flag
→ fires) CANNOT be triggered via pure-production wiring because every
real modelo has at least one fixture in the corpus directory; the
Scenario A test stays in the empty-corpus-injection pattern with inline
prose explaining the limitation.

**Honest meta-conclusion**: The first-pass post-rush audit was insufficient
where it closed findings via "acknowledged" or "documented" rationales
without performing the actual remediation work. Two findings (A, B) that
the first pass rationalized away turned out to be REAL silent-failure
classes that were active during the session. The second pass surfaced
them through independent verification of the closure claims. Going
forward: prefer explicit "out of scope" classification over
"acknowledged" rationalization when a finding is real but the operator
chooses not to remediate immediately; this preserves the audit signal
for future sessions.
