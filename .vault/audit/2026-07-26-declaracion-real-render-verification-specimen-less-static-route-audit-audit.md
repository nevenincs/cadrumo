---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-25-declaracion-profile-printed-box-scope-real-render-gate-and-naming-honesty-audit]]"
  - "[[2026-07-25-declaracion-profile-printed-box-scope-layout-blind-corpus-audit]]"
---

# `declaracion-real-render-verification` audit: `static route audit across all 29 declaracion_pdf profiles`

## Scope

This is Phase `P02` (Steps `S06`-`S09`) of the governing plan: a static route audit
across every `declaracion_pdf` extraction profile in the registry, covering the
routes that are decidable without a real or facsimile specimen (`R3`, `R4`, `R8`,
`R9`), plus a register of what each specimen-less profile would need to become
decidable (`R11`). This pass is report-only; it touches no code, registry data,
fixtures, or tests, and defers to the coder owning that surface for every fix.

The semantic code index remained truncated throughout (roughly 1027 chunks against
roughly 4546 files, self-reporting healthy with an empty degraded-reasons list), so
it was not used as evidence for any claim below. Every count in this document was
established by parsing the registry with `tomllib` (never a shell regex over TOML),
enumerating `[[revisions."<rev>".extraction_profiles]]` entries and filtering on
`surface = "declaracion_pdf"` -- there is no top-level `extraction_profiles` key, and
a wrong key shape silently returns zero rather than erroring. Casilla `required` and
`legal_refs` fields, and formula `target_casilla_id` sets, were read the same way
from each revision fragmented `casillas/` and `formulas/` subdirectories, never
inferred from a directory listing. Revision year ranges were read from each
revision `valid_from` / `valid_to` / `period_selector` to attribute fixture years
to the correct revision where a modelo has more than one. The full working set was
29 `declaracion_pdf` profiles across 20 modelos, re-confirmed against the working
tree at the time of writing. This selection matches the governing ADR's D4
(profile selection is by `surface`, never `artefact_kind`) independently, since it
was reached from the profile schema rather than from that decision. D1 (the printed
box number lives on `form_number`, not `number`) does not bear on any measurement
here: every intersection and comparison below keys on casilla `id`, never `number`.

Steps `P02.S06`-`P02.S09` are closed against this document rather than
individual per-step exec records. `vaultspec-core vault add exec` refuses any
exec creation for this feature ("no ADR document exists"), because the exec-
lifecycle gate resolves an ADR by feature-tag match on the filename, and this
plan legitimately executes the pre-existing `2026-07-25-declaracion-profile-
printed-box-scope-adr` from a different feature tag, linked only through the
plan `related:` frontmatter -- a pattern the plan template itself sanctions (an
epic plan rolling up a prior ADR) but the exec-creation CLI does not yet
support. This audit document is the closing record for the four steps; the
blocker is reported to the dispatching coordinator rather than worked around by
hand-authoring an exec file.

## Findings

### r3-vacuous-zero-floor-confirmed-exactly-three-profiles | medium | 111, 130 and 390 are the only profiles with a min_coverage-0 fail_hard pairing

Sweeping `min_coverage` across all 29 profiles, exactly three carry `"0"`:
`modelo-111-declaracion-pdf`, `modelo-130-declaracion-pdf` and
`modelo-390-declaracion-pdf`, all paired with `failure_semantics = "fail_hard"`.
This matches the dispatch brief known set exactly; no fourth profile shares the
shape. All three carry an author comment at the `min_coverage` line explaining the
zero as a deliberate choice for a form with mutually exclusive sections (M111 per
quarter column layout, M130 estimacion directa vs objetiva split, M390 per rate
rows) rather than an oversight -- but the deliberate intent does not change the
structural fact the printed box scope audit already established for M390: no
document can score below zero, so the coverage arm of a `min_coverage = 0` /
`fail_hard` gate can never refuse anything regardless of why the floor was set
there. `modelo-111-declaracion-pdf` and `modelo-130-declaracion-pdf` share the
identical vacuity, previously unconfirmed outside the M390 case.

The governing ADR (`declaracion-real-render-verification`, D2) now settles two of
the three on the evidence this audit measured: `111` keeps its zero floor because
four specimens exist and the worst case is 1 of 29 absent, and `390` keeps its zero
floor for the opposite reason, having exactly one specimen, so no floor can be set
from it under D2 ("where only one specimen exists, no floor is set"). `130` is
different from both: per the `R11` register below it carries zero specimens of any
kind, so its vacuous floor is not yet grounded the way `111` and `390` are under
D2 -- it remains an undecided D3 evidence gap rather than a settled case, and
should not be read as resolved by the same reasoning that now covers its two
siblings.

### r4-over-strict-unit-floor-spans-23-profiles | high | every profile with min_coverage of 1 refuses any real filing missing even one target, ranked by exposure

23 of the 29 profiles carry `min_coverage = "1"` or `1.0` with
`failure_semantics = "fail_hard"` -- every profile that is neither in the R3 set
above nor one of the three fractional-floor profiles (`303` at `0.75`/`0.8333`,
`349` at `0.5`). This matches the dispatch brief count of 23 profiles exactly.
Each of these 23 refuses the entire filing the moment one declared target
is absent, which is exactly the shape that made M303 refuse every real render for
its whole history before the printed box scope change.

The registry own `required` field on a casilla (a boolean the loader carries
through unchanged; present on 4450 casillas project-wide, spanning 68 of the 91
registry-modelo/revision pairs, but declared on only a subset of casillas in any
given revision) is the strongest available exposure signal where it exists, because
it is the registry asserting -- not this audit inferring -- that a target may
legitimately be absent from a real filing. Where the field is absent from a
profile's targets entirely, as on the five `100` revisions, the ranking below falls
back to a qualitative reading of the target labels, and that fallback is called out
explicitly rather than blended with the registry-asserted tiers, because the two are
different strengths of evidence. Ranked by that signal:

- Fully self-declared optional (every target `required = False`), the sharpest
  exposure in the set: `131/2024`, `131/2025`, `131/2026` (15 of 15 targets each),
  `123/2024-y-siguientes` (14 of 14), `123/2019-2023` (8 of 8), `115` (5 of 5). A
  real Modelo 131 or 123 filing that leaves even one of these registry declared
  optional boxes blank -- plausible on every one of them, since the registry itself
  asserts none is mandatory -- is refused outright by these six profiles.
- Partially self-declared optional: `202/2025-y-siguientes` (3 of 4 targets
  optional -- `03`, `04`, `34` -- one, presumably the identifying box, required) and
  both `232` revisions (1 of 3 optional -- `decl.tipo-ejercicio`).
- No `required` field on any target, but the largest target surface in the R4
  set and a qualitatively conditional sub-chain: the five `100` revisions, 21
  targets each. Registry silence here is not evidence of low exposure: eight of the
  21 targets (`0171`, `0180`, `0218`, `0223`, `0224`, `0226`, `0231`, `0235`) belong
  to the "actividades economicas en estimacion directa" branch of the form by their
  own labels, a branch a salaried-only filer real declaracion plausibly never
  populates. 21 targets under a unit floor is, by the same target-count logic that
  flagged M303 12-18 targets, itself a high-exposure shape independent of the
  qualitative reasoning.
- No `required` field, but every target is an identifying or resumen-total field
  a filed declaracion always states: `180`, `190`, `193` (3 targets each,
  `decl.total-*`/`decl.*-total` summary fields), `369`, `840` (2 targets each,
  `decl.ejercicio`/`decl.periodo`/`decl.tipo-declaracion` identifying metadata),
  `036`, `184`, `347`, `720` (1 target each, `decl.ejercicio` or equivalent). These
  nine profiles are technically R4 by the `min_coverage = 1` test, but their
  targets are the class of field an AEAT informativa always prints regardless of
  the filer situation, so their real exposure is the lowest in the set.

### r8-formula-computed-targets-are-widespread-not-modelo-303-specific | high | 20 of 29 profiles target at least one casilla the engine also computes by formula

Intersecting each profile `target_casillas` against its revision formula
`target_casilla_id` set finds a hit in 20 of the 29 profiles -- this is not a
Modelo-303/390 peculiarity, it is the majority shape. The fraction of a profile
own targets that are formula outputs ranges from 0.07 (`111`, 2 of 29) to 0.95
(`100/2024` and `100/2025`, 20 of 21). The nine profiles with zero hits are `036`,
`184`, `232` (both revisions), `347`, `349`, `369`, `720`, `840` -- exclusively the
identifying-metadata and low-target-count profiles from the R4 low-exposure tier
above.

This is the exact parser-versus-engine impedance the printed box scope ADR named
and left the M303/M390 implementation lane to arbitrate via the reconcile path
own printed-value comparison (`iva.resultado-regimen-general` compared against box
27 minus box 45, and similar). The intersection reported here is the full extent of
where that same arbitration question now arises across the registry, not a defect
in itself -- see the two findings immediately below for where it is and is not
currently resolved.

### r8-six-modelos-are-enrolled-in-the-reconcile-arbitration-the-rest-are-not | high | the reconcile module own enrolled set covers only 11 of the 20 profiles with a computed-casilla target

`_DECLARATION_CASILLA_RECONCILE_MODELOS` in `application/modelo/_reconcile.py`
names exactly six modelos -- `M100`, `M111`, `M130`, `M190`, `M303`, `M390` -- as
enrolled in casilla-level filed-declaration reconciliation; its own docstring
states that a modelo outside this set is refused with
`ReconciliationDeclaracionSourceUnsupportedError` at the reconcile-command
boundary, and that the enrolled set grows one modelo at a time as each modelo
`declaracion_pdf` extraction profile is confirmed to line up with its registry
casilla ids one-to-one.

Cross-referencing the 20 profiles with an R8 hit against this set: 11 profiles
(the five `100` revisions, `111`, `130`, `190`, both `303` revisions, `390`) belong
to enrolled modelos, where the reconcile arbitration this audit related records
describe is the intended, designed consumer of the intersection. The other nine --
`115`, both `123` revisions, all three `131` revisions, `180`, `193`, `202`
-- are NOT in the enrolled set, so a reconcile attempt against one of their
formula-computed targets is refused cleanly today rather than silently
double-counted or discarded. This is not a live defect (the refusal is loud, and
no-silent-under-declaration class harm is not occurring), but it is nine profiles
where the printed-versus-primitive impedance the ADR flagged as project-wide,
rather than Modelo-303 trivia, has not yet been arbitrated by any mechanism because
none applies to them yet. The governing `declaracion-real-render-verification` ADR
now records this same nine-profile scope in its Constraints section, naming it a
non-live defect that is deliberately left undecided pending its own evidence -- this
audit's measurement is what let that scope be named exactly rather than gestured at.

### r8-reconcile-docstring-misstates-modelo-202-declaracion-pdf-surface | high | the enrolled-set docstring gives a factually false reason for excluding Modelo 202

The same docstring names Modelo 202 as an example of a Modelo whose extraction
profile has not yet been authored, quoting "e.g. Modelo 200, Modelo 202 -- no
`declaracion_pdf` surface at all". That is false as of this audit: Modelo 202 does
carry a `declaracion_pdf` profile, `modelo-202-declaracion-pdf`, in revision
`2025-y-siguientes`, with 4 targets, 2 of which (`03`, `34`) are formula-computed --
exactly the shape the docstring own reasoning would place inside scope for
enrollment consideration rather than outside it. Whether the profile predates the
docstring or was authored afterward without the cross-reference being swept could
not be established from the registry alone; either way the claim in the docstring
no longer matches the tree it describes, and a reader relying on it to judge which
modelos still need a `declaracion_pdf` profile authored would be misled about
Modelo 202 specifically. Modelo 200, the docstring other example, does genuinely
carry no `declaracion_pdf` profile in this registry sweep, so only the 202 half of
the claim is wrong.

### r9-two-modelo-100-revisions-omit-legal-refs-their-own-retained-targets-carry | medium | 2024 and 2025 drop the reglamento IRPF pagos-fraccionados articles; 2025 additionally drops that year Orden

Comparing each profile own `legal_refs` against the union of its retained
targets own `legal_refs` finds a clean discrepancy in exactly two of the 29
profiles, both Modelo 100: `100/2024` and `100/2025`. In both, casilla `0604`
("Pagos fraccionados ingresados") carries `rd-439-2007:art-109` and
`rd-439-2007:art-110` in its own `legal_refs`, and both are absent from the
profile `legal_refs` list. The `100/2021`, `100/2022` and `100/2023` sibling
profiles carry the identical target set and correctly include both articles,
so this is a drift specific to the two newest revisions rather than a
never-included omission. `100/2025` additionally drops `orden-hac-277-2026:art-3`,
which every one of its targets (`0545` through `0510`) carries individually --
the year applicability Orden is present on the casillas but entirely absent
from the profile-level grounding. No other direction of mismatch (a profile
`legal_refs` entry that no retained target carries) was found anywhere in the
29-profile sweep.

### r9-clean-across-the-other-27-profiles | low | no other profile diverges from its targets own legal_refs in either direction

The remaining 27 profiles -- including both `303` revisions and `390`, whose
`legal_refs` cite orden/RD provisions at the profile level distinct from any
single target own citation -- show zero discrepancy under this check. This
sweep does not itself validate that a profile `legal_refs` are the correct
binding provision (`registry-calculation-legal-grounding` governs that), only
that the profile-level set equals the union its own retained targets declare;
within that narrower claim, the check is clean outside the two `100` revisions
above.

### r11-evidence-gap-register-measures-22-specimen-less-profiles-not-19 | high | the dispatch brief expected count does not match a direct measurement, and the discrepancy is reported rather than reconciled to the brief

Cross-referencing every `real_corpus` and `aeat_published_facsimile` sidecar
(9 real-corpus, spanning Modelos 100, 111, 190 and 390 only, plus 7 facsimile
annex sidecars for Modelos 303 and 390) against each profile revision year
window finds exactly 7 profiles with a specimen and 22 without, not the 19 the
dispatch brief named. The 7 covered profiles are `100/2021`, `100/2022`,
`100/2023` (real corpus each), `111` (real corpus, its single open-ended
revision), `190` (real corpus, its single revision), `390` (real corpus plus
facsimile, its single revision) and `303/2023-y-siguientes` (facsimile only,
since the four facsimile quarters are dated 2024 and the revision own
`valid_from = 2023-01-01` with no upper bound places them there rather than in
`303/2009-y-siguientes`, whose `period_selector.year_to = 2022` excludes them).
Notably, `100/2024` and `100/2025` -- despite Modelo 100 being one of the four
modelos with real-corpus evidence, and despite Phase P01 naming M100 across
its five revisions -- carry no specimen of their own; a comment inside
`100/2024` own profile TOML confirms this directly (No real ejercicio-2024
declaracion PDF specimen is bundled). Likewise `303/2009-y-siguientes` carries
none, leaving Modelo 303 with facsimile coverage for one of its two revisions
only. This measurement could not be reconciled to 19 by any grouping this
audit could construct (by profile: 22; by modelo, counting a modelo as covered
the moment any one of its revisions has a specimen: 15) -- it is reported as
measured rather than adjusted to match the expectation, per the standing
discipline that a number asserted in a dispatch brief is itself unverified until
checked against the tree.

The full register, one row per specimen-less profile, naming which routes stay
undecidable for it and what class of specimen would close the gap:

Blocked routes shared by every row below: R2 (real AEAT typographic/kerning
drift against the `label_pattern`/`bbox_anchor` match, which only a real render
can exercise), and confirmation of the R4 floor true headroom (whether the
measured worst-case coverage genuinely has zero margin, as `303` and `390` own
prior audits found, or whether it is looser or tighter than assumed). Rows using
`bbox_anchored` additionally carry R6 (bbox fragility -- a real render
whitespace/font metrics can shift a box geometry in ways a synthetic fixture,
built from the same generator conventions as the profile, cannot expose). Rows
whose modelo carries a sibling revision also carry R10 (whether a floor or
match pattern validated on one revision generalises to the others).

| Profile | Match strategy | Extra blocked route | Specimen class needed |
|---|---|---|---|
| `036/2025-02-03-y-siguientes` | named_label | none | real_corpus, censal alta/baja/modificacion |
| `100/2024` | named_label | R10 (siblings 2021-2023 have specimens; 2024/2025 do not) | real_corpus, ejercicio 2024 |
| `100/2025` | named_label | R10 | real_corpus, ejercicio 2025 |
| `115/2019-y-siguientes` | named_label | none | real_corpus or aeat_published_facsimile, any 1T-4T |
| `123/2019-2023` | numeric_casilla | R10 | real_corpus or facsimile, any 2019-2023 quarter |
| `123/2024-y-siguientes` | numeric_casilla | R10 | real_corpus or facsimile, any post-2024 quarter |
| `130/2019-y-siguientes` | bbox_anchored | R6 | real_corpus or facsimile, any 1T-4T |
| `131/2024` | bbox_anchored | R6, R10 | real_corpus or facsimile, ejercicio 2024 |
| `131/2025` | bbox_anchored | R6, R10 | real_corpus or facsimile, ejercicio 2025 |
| `131/2026` | bbox_anchored | R6, R10 | real_corpus or facsimile, ejercicio 2026 |
| `180/2023-y-siguientes` | named_label | none | real_corpus or facsimile |
| `184/2015-y-siguientes` | named_label | none | real_corpus or facsimile |
| `193/2024-y-siguientes` | named_label | none | real_corpus or facsimile |
| `202/2025-y-siguientes` | bbox_anchored | R6 | real_corpus or facsimile |
| `232/2016-2017` | named_label | R10 | real_corpus or facsimile, 2016 or 2017 |
| `232/2018-y-siguientes` | named_label | R10 | real_corpus or facsimile, any post-2018 year |
| `303/2009-y-siguientes` | named_label | R10 (sibling 2023-onwards has facsimile) | real_corpus or facsimile, any 2009-2022 quarter |
| `347/2008-y-siguientes` | named_label | none | real_corpus or facsimile |
| `349/2020-y-siguientes` | named_label | none | real_corpus or facsimile |
| `369/esquema-union` | named_label | none | real_corpus or facsimile (esquema de la union) |
| `720/2013-y-siguientes` | named_label | none | real_corpus or facsimile |
| `840/2003-y-siguientes` | named_label | none | real_corpus or facsimile |

22 data rows above (`111/2019-y-siguientes`, the one modelo not appearing, is
excluded because its single revision already has a real_corpus specimen). Every
row is an evidence gap, not a pass -- none of the routes named above should be
read as satisfied for these profiles until a specimen closes it, which is the exact
posture the governing ADR codifies as D3 ("an untestable profile is an evidence
gap, never a pass").

## Recommendations

Treat the R4 low-exposure tier (`180`, `190`, `193`, `369`, `840`, `036`, `184`,
`347`, `720` -- identifying/resumen-total fields only) as lower priority for
specimen acquisition than the fully-self-declared-optional tier (`131` x3, `123`
x2, `115`) and the `100` revisions, where a real render is far more likely to
trip the unit floor. A follow-on plan step choosing which specimen-less profile to
acquire evidence for next should read this ranking rather than pick by target
count alone.

Route the `100/2024` and `100/2025` legal_refs gap (finding
`r9-two-modelo-100-revisions-omit-legal-refs-their-own-retained-targets-carry`)
to the coder owning the registry surface as a small, mechanical fix: add
`rd-439-2007:art-109`, `rd-439-2007:art-110` to both, and
`orden-hac-277-2026:art-3` to the `100/2025` profile-level `legal_refs`.

Sweep the `_DECLARATION_CASILLA_RECONCILE_MODELOS` docstring Modelo 202 claim
(finding `r8-reconcile-docstring-misstates-modelo-202-declaracion-pdf-surface`)
in the same change that next touches that enrolled set, correcting or removing
the "no `declaracion_pdf` surface at all" example for Modelo 202 specifically;
Modelo 200 remains a correct example.

Decide, as a follow-on ADR question rather than something this audit resolves,
whether the nine not-yet-enrolled modelos with an R8 hit (`115`, `123` x2,
`131` x3, `180`, `193`, `202`) should be added to the reconcile-enrolled set on
the same one-modelo-at-a-time cadence the docstring already describes, or
whether their formula-computed targets should instead be reconsidered as targets
at all -- the same "profile targets only what AEAT prints" principle that
narrowed the Modelo 303/390 profiles applies here too, and this audit does not
adjudicate which of the two resolutions is correct for each of the nine.

Prioritise specimen acquisition for the R3 profiles (`111`, `130`, `390`) low,
since their vacuous floor is a documented, deliberate choice for legitimately
partial filings rather than an unnoticed gap -- but do not read the deliberate
rationale as removing the exposure: a genuine coverage regression on any of the
three is currently undetectable by the coverage arm of their gate regardless of
intent, exactly as the prior audit already found for `390`.
