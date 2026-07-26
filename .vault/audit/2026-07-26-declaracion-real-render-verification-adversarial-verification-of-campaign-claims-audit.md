---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
  - "[[2026-07-26-declaracion-real-render-verification-specimen-less-static-route-audit-audit]]"
  - "[[2026-07-26-declaracion-real-render-verification-r8-arbitration-enrollment-readiness-audit]]"
---

# `declaracion-real-render-verification` audit: `adversarial verification of this campaign's own load-bearing claims`

## Scope

Adversarial verification of this campaign's own load-bearing claims, per the
dispatch brief's six numbered items. Posture: assume the campaign overstated
its results and try to break each claim. Re-derived rather than re-read
throughout -- every number below was produced by a script or a direct
production-code call I wrote myself this pass, or by git commands I ran
myself, never by re-reading a prior document's assertion. Report-only: no
production code, registry data, or test file was modified; every production
function call below ran the real, unmodified, currently-committed code.
Report-only extends to the test suite specifically: I did not perturb any
test file, even temporarily, to prove a negative-control; where a
perturb-and-restore claim needed checking I instead reconstructed the OLD
(pre-fix) state from the git diff and re-ran the OLD pattern against the
real specimen text in my own throwaway script, which proves the same thing
without touching a committed file. The semantic code index remained
truncated throughout and was not used as evidence.

## Findings

### the-real-render-gate-runs-the-actual-production-path-not-a-reimplementation | high | reproduced: confirmed by reading the call chain, not by trusting the test's own docstring

Read `test_real_render_extraction_coverage.py` and the parser module it
imports from directly (`_extract_profile_values`, `extract_pages_text` in
`adapters/inbound/declaracion/_parser.py`). Then read the production
entrypoint `parse_declaracion` in the same module and confirmed it calls
`extract_pages_text` and, via `_parse_declaracion_pages`, the same
`_extract_profile_values` the gate calls directly. This is one function,
one call chain, not a parallel implementation the gate could pass
vacuously against.

The gate own assertions are set-based, not ratio-based (`covered ==
declared - specimen.absent`, never a bare coverage-fraction compare), and
carry a stated anti-vacuity guard
(`test_the_suite_still_exercises_the_blank_box_tolerance`) asserting at
least one specimen scores below 1.0. I did not trust that guard's own
report of itself: I independently ran `_extract_profile_values` against
five real specimens myself (M390 annex, M390 real, M111 x4) and got
covered-set fractions of 1.0, 0.9167, 0.9167, 0.8333, 4/10 and 5/29, 5/29,
5/29, 1/29 -- several genuinely below 1.0, computed by my own script, not
read from the test.

**Reproduced independently.**

### m390-1-of-10-is-independently-reproduced-not-merely-re-read | critical | reconstructed the pre-fix patterns from the git diff and ran them myself

D5 rests on this number entirely, so it was the first target. Read the
commit that widened the M390 labels to English (`4a176fb5c7`) and
extracted the exact pre-fix, Spanish-only `label_pattern` strings from its
diff for the five `named_label` targets. Wrote a script that runs the real
`extract_pages_text` against the bundled real M390 render
(`justificantes/390/2021-0A.pdf`) and tests those five OLD patterns with
`re.search`, independent of any registry file: zero of five match. The
five `bbox_anchored` targets (boxes 02/04/06/26/49) are unaffected by
render language by construction (they anchor on the printed box number
via coordinates, not on translated text), and the diff confirms none of
their `bbox_anchor` definitions changed in that commit. Four of those five
are absent from this specimen for an unrelated, page-existence reason
(the render omits the page carrying boxes 02/04/06/26); the fifth, box 49
(`iva.anual.soportado.interiores`), is covered. That gives a reconstructed
pre-fix coverage of exactly 1 of 10 -- confirmed by my own run of the OLD
patterns, not by reading the commit message's claim.

Then ran the CURRENT (already-fixed) profile through the real
`_extract_profile_values` myself and got covered = {soportado.interiores,
cuota-deducible-total, resultado-regimen-general,
compensacion-ultimo-periodo-97}, exactly 4 of 10, matching the committed
test's own `_M390_REAL_ABSENT` set exactly. Also independently reran the
printed-arithmetic cross-check on the AEAT annex specimen (a different
document): extracted box 47 = 88416.00, box 64 = 68202.00, box 65 =
20214.00, and 88416.00 - 68202.00 = 20214.00 exactly, computed by my own
script call to the real production function.

**Reproduced independently, by a different method than reading the test.**

### m111-worst-case-1-of-29-is-independently-reproduced-and-the-absences-are-genuinely-blank | high | reproduced by direct execution, and cross-checked against a source outside the profile entirely

Ran the real `_extract_profile_values` against all four bundled M111
specimens myself, loading each snapshot through the production authority
rather than assuming the registry coordinate: 1T, 2T, 3T each covered
exactly {07, 08, 09, 28, 30} (5 of 29), 4T covered exactly {30} (1 of 29).
Matches the committed test's own numbers, but reproduced by my own
execution, not by reading them.

The stronger check is whether the 24 (or 28) absences are genuinely blank
boxes rather than pattern failures on a genuinely populated box, since
that distinction is the entire argument for the zero floor. Read each
quarter's sanitiser sidecar directly -- a source the extraction profile
cannot influence, since the sanitiser rewrites the PDF content stream
independently of any profile -- and counted amount-shaped
(`"N.NNN,NN"`-formatted) replacement entries: 1T, 2T, 3T each declare six,
4T declares one. Six real amounts is consistent with five covered
casillas (a repeated amount at more than one content-stream offset for
the same visual field is an ordinary PDF-internals artefact, not a
discrepancy); one real amount is consistent with one covered casilla. If
the parser were instead failing to read a box that genuinely carried a
value, the sanitiser -- which operates on raw bytes, not on any
extraction result -- would still have found and replaced that amount, and
the replacement count would exceed the covered count. It does not, on any
of the four quarters.

**Reproduced independently, and corroborated against a source the profile
cannot influence.**

### m100-63-refusals-is-independently-reproduced-and-the-fabrication-is-visible | critical | reproduced by direct execution; the drifted values themselves are the evidence

Ran the real `_extract_profile_values` against all three bundled M100 real
renders (2021, 2022, 2023) myself: every render scores 21 of 21 covered
(coverage 1.0, satisfying the profile's floor of 1), and every one of the
resulting 63 extracted values differs from the sanitiser's declared
constant (`1.000,00` / `Decimal("1000.00")`) -- zero of 63 match, 63 of 63
drift. This exactly reproduces "coverage scores 1.0" and "the manifest
check refuses all 63".

The drifted values are themselves the strongest evidence: casilla `0545`
extracts as `10010000.50405`, `0546` as `10010000.50406`, `0505` as
`1001000.005005`. These are not near-misses or rounding artefacts; they
are the visual signature of a box number and an amount concatenated by
word assembly, exactly as the exclusion rationale states. I did not need
to trust the "fabrication" characterisation -- the numbers themselves show
it.

One qualification worth recording: the exclusion itself is a documented
convention (the module docstring names M100 as deliberately absent from
the specimen table) rather than an enforced gate. Nothing in the
committed test suite would fail today if M100 were re-added to
`_REAL_SPECIMENS` with weakened assertions; the exclusion currently relies
on the convention being followed, not on a structural check that refuses
a re-addition. This is a process observation, not a data-correctness
finding: the "63 refusals" figure is real and I reproduced it myself, but
the exclusion that reports it is not itself gate-enforced.

**Reproduced independently, and confirmed to be a real defect rather than
a manufactured one. The exclusion's own durability is not gate-enforced.**

### census-numbers-reproduced-by-a-different-method-than-the-original-tomllib-parse | high | five figures re-derived by grep and by the loaded authority API, not by rerunning the original script

Every figure below was re-derived by a method genuinely different from the
`tomllib` fragment-parsing script the companion static-route audit used:

- **29 `declaracion_pdf` profiles.** `grep -rl 'surface = "declaracion_pdf"'`
  across the registry returns 29 files, and `grep -rc` on the same pattern
  confirms no file carries more than one occurrence (total occurrences =
  29). Matches.
- **22 specimen-less / 7 specimen-bearing, per profile.** `grep -rl` for
  `"provenance": "real_corpus"` and `"provenance":
  "aeat_published_facsimile"` across every fixture sidecar returns the
  same 9 real-corpus and 7 facsimile files as before, none from the six
  modelos behind the nine unenrolled profiles. Cross-checked the
  revision-attribution separately by calling the real
  `ValidatedRegistryAuthority.snapshot()` for every specimen (modelo,
  filing_year, period) instead of parsing `valid_from`/`valid_to` myself:
  it resolves `100/2021-2023` to their own revisions, `111` and `390` to
  their single open-ended revisions, `303`'s 2024 facsimile quarters to
  `2023-y-siguientes` (not `2009-y-siguientes`), and -- the sharpest
  check -- `100/2024` and `100/2025` resolve to their own, separate,
  specimen-less revisions. Matches.
- **18/11 `artefact_kind` split.** `grep` for `artefact_kind = "..."`
  immediately after the `surface = "declaracion_pdf"` line in each of the
  29 files gives 18 `declaration_pdf` and 11 `declaracion`. Matches the
  ADR exactly.
- **20 of 29 profiles with an R8 hit.** Rewrote the intersection using the
  loaded authority (`snapshot.revision.formulas` and
  `snapshot.revision.extraction_profiles`) rather than parsing the
  `formulas/` TOML fragments directly. Every per-profile hit count matches
  the original figures exactly (100/2021-2023: 16 each; 100/2024-2025: 20
  each; 111: 2; 115: 2; 123/2019: 2; 123/2024: 5; 130: 11; 131 x3: 6 each;
  180: 2; 190: 2; 193: 2; 202: 2; 303/2009: 1; 303/2023: 11; 390: 3), and
  the total is 20 of 29. Matches.
- **Nine of nine unenrolled profiles are specimen-less.** Already covered
  by the `grep`-based sidecar sweep above: none of the nine profiles'
  candidate provenance files appear in either grep result.

All five reproduce exactly under an independent method. None could only
be reproduced by repeating the original script.

**Reproduced independently, by a different method, for all five.**

### two-more-circular-citations-found-and-fixed-in-the-exec-records | high | the audit-level fix did not reach the exec records that recorded the same Steps

Sweeping every document under this feature for corroboration language
(`corroborat`, `independently confirm`, `now records`, `second source`)
found two more instances of the exact pattern already corrected once in
the static-route audit, both in this campaign's own exec records rather
than in a fresh document:

- `P02-S07` repeated the original "refuses cleanly... the governing ADR
  now records this" framing verbatim from the audit finding it was closing
  against, before that finding was corrected. Fixed in place: it now
  states the claim was originally docstring-derived, names the companion
  `r8-arbitration-enrollment-readiness` audit as the actual grounding, and
  keeps the nine-profile scope as this Step's own measurement.
- `P02-S09` stated the ADR's "twenty-two of twenty-nine" figure
  "corroborat[es] the measurement from a second source" -- the exact
  reasoning the team lead flagged as wrong in a chat message, except this
  instance had reached a committed document, not only a message. Fixed in
  place: it now states plainly that the ADR adopted the figure from this
  Step's own measurement and that citing it back would manufacture
  agreement.

A third instance, in `P01-S02` (render-verifier's own exec record,
"independently corroborated by the specimens' own redaction manifests"),
was checked and is NOT circular: the sanitiser manifest is a genuinely
separate source, authored by a different tool and not derived from any
profile or prior report -- the same cross-check this audit performed
independently for M111 above and got the same result. Left unedited.

**Two genuine instances found and corrected; one candidate checked and
cleared.**

### the-adrs-enrolment-timeline-figure-does-not-match-the-measured-span | medium | a small, real inaccuracy in D5, checked directly against git rather than re-read

D5 states the six enrolled modelos "were added in three batches over five
days". Re-ran `git show -s --format="%ci"` against the three enrolment
commits directly: `7a0ed699b6` (first batch, `130` alone) at
2026-07-02 21:06:39, and `2b59a9fa06` (third batch, `100`) at
2026-07-05 15:57:21. That is 2 days, 18 hours, 51 minutes between the
first and last enrolment commit -- not five days. Confirmed there is no
fourth commit touching the frozenset that would extend the span: `git log
--follow -p` on the module shows exactly the three edits already found.
The three-batches count is correct; the five-days figure is not.

This does not affect D5's substance -- the ordering argument (development
sequence, not an evidential filter, with `130` as the counter-example)
holds regardless of whether the span was three days or five. It is
recorded because a wrong supporting number sitting next to a sound
conclusion is exactly the kind of small drift this pass exists to catch,
and because a reader checking only the argument and not the number would
not have found it.

**Not reproduced as stated; the underlying conclusion is unaffected.**

### the-r9-legal-refs-gap-has-already-been-fixed-since-the-original-measurement | low | re-read HEAD rather than trusting the original finding to still describe the tree

Attempting to re-verify the R9 finding (100/2024 and 100/2025 missing
`rd-439-2007:art-109`/`art-110`, 2025 also missing
`orden-hac-277-2026:art-3`) by grep instead of the original `tomllib`
script first appeared to contradict it: both articles are present in the
current `100/2024` profile file. Reading `git log` on that file
explains why: commit `5f020a2bd2`, "fix(registry): restore the legal
grounding the M100 2024 and 2025 profiles dropped", has already landed
and restores exactly the three missing references this campaign named,
each with an inline comment citing the casilla or revision that carries
it. This is not a wrong finding; it is a finding whose target moved
between measurement and re-verification, which the standing discipline
in this shared worktree exists to catch before acting on stale state.

**The original finding was sound, and is now also fixed.**

### what-could-not-be-independently-verified-this-pass | medium | named plainly rather than left implicit

Two things this pass could not put through the same independent-execution
standard as the findings above, recorded rather than silently omitted:

- Whether the AEAT Manual Practico IVA source text itself states that
  boxes 78/37 are blank for the 2024 supuesto practico (the legal-document
  cross-check `legal-grounding-verifies-bundled-authoritative-corpus`
  governs), as distinct from whether the parser correctly reads the
  bundled PDF rendering of it, which this pass did verify directly. I
  re-ran the extraction and got the same 12/11/11/10 covered counts the
  companion audits report, but did not re-open the bundled manual text
  itself to confirm the absences against the underlying legal source.
- Whether a vault document outside this feature cites any claim from this
  campaign circularly. This sweep covered every document tagged to this
  feature; it did not search the rest of the vault.

Everything else asked for in the dispatch brief was either reproduced
independently (findings above) or, where reproduction surfaced a
discrepancy, the discrepancy was itself resolved by reading `git log`
(the R9 finding above) rather than left unexplained.

## Recommendations

No claim attacked in this pass survived only by repeating the original
method; every load-bearing number reproduced under a genuinely different
method (a fresh script calling the real production functions, `grep`
instead of `tomllib`, the loaded authority API instead of raw fragment
parsing, or `git log` timestamps read directly). This is a real result in
the direction the campaign hoped for, and is reported as one rather than
softened.

Consider a structural test for the M100 exclusion (finding
`m100-63-refusals-is-independently-reproduced-and-the-fabrication-is-visible`):
today nothing would fail if a future edit re-added M100 to
`_REAL_SPECIMENS` with weakened assertions, since the exclusion is a
documented convention rather than an enforced one. A dedicated test
asserting M100 stays absent from that tuple, or a fixture-level marker
`test_fixture_naming_honesty.py`-style gate could check, would close that
gap without needing the merge fix itself.

Correct the "five days" figure in D5 to the measured span (a little under
three days) or drop the specific duration, since the three-batches
sequencing argument the decision actually rests on does not need it and
is unaffected either way.

No further action needed on the R9 legal-refs gap: it is already fixed at
HEAD (`5f020a2bd2`).
