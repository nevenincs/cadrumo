---
tags:
  - '#audit'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:a5a62a7451f57917eb21d1d84d4a470675f0d5c3ef4bae4ac46f87dfd15b05c9'
related: []
---

# `registry-dated-validity` audit: `what the collapse deliberately did not fix`

## Scope

The three corpora the `registry-dated-validity` migration collapsed onto dated
citation windows, and the defects that migration touched but did not close. This
record exists so a later reader does not mistake a deliberate boundary for an
oversight, and does not read a gate turning green as a claim that everything
beneath it is now grounded.

Out of scope: anything the migration actually delivered, which the ADR and the
plan's execution records carry.

## Findings

### The exact-year pinning defect is untouched and still owned elsewhere

All three resolvers still refuse a year they do not ground, with no adjacent-year
fallback. That refusal was preserved deliberately and byte-for-byte in effect:
the windows are closed, both bounds are required, and no code path widens or
interpolates. A separate brief owns whether that refusal is the right behaviour,
and coupling a behaviour change to a format migration would have made the blast
radius unattributable.

The one visible consequence is a better refusal message. Each resolver now names
the years it does ground and tells the reader to ground the missing one rather
than widen a window.

### Spending-category profiles now ground the whole supported window, and the route there found a live defect

The corpus previously reported 2024 and 2025, of which 2024 was a mirror. It now
grounds 2022 through 2026, and every year is derived rather than asserted.

The 41 mirrored 2024 citations were dropped rather than re-windowed. What
replaced them is not a wider claim on the same evidence: each of the 42 statutory
citations now names the provision it rests on, and its window is computed as the
intersection of that provision's effective span in the registry legal catalogue
with the declared supported filing window. LIRPF art. 28 (2007->), art. 29
(2007->) and art. 30 (2018->) all cover the window, so the widening is a fact the
catalogue can be asked to confirm, and a companion gate asks it on every run.

The three profiles that carried no statutory citation at all -- `cuotas_colegiales`,
`cuotas_autonomos_ss` and `mutualidad_alternativa` -- each gained one, quoted
verbatim from the bundled consolidated LIRPF. Which article establishes each rule
is an agent tax review, recorded as such in the TOML beside each citation, and it
is the part of this change most in need of operator re-stamping.

### The mutualidad cap was year-variable by law and encoded as a wrong constant

`mutualidad_alternativa` shipped `statutory_cap_eur = "15000"`. LIRPF art. 30.2.1.a
caps that premium at the cuota maxima por contingencias comunes established "en
cada ejercicio economico" in the RETA -- a figure the cotizacion orden re-fixes
every year. One constant cannot express it, and the constant chosen was not the
figure for any ejercicio:

| ejercicio | lawful cap | shipped | operator effect |
|---|---|---|---|
| 2022 | 14 057,40 | 15 000 | allowance overstated |
| 2023 | 15 266,72 | 15 000 | allowance understated |
| 2024 | 16 030,82 | 15 000 | allowance understated |
| 2025 | 16 672,66 | 15 000 | allowance understated |
| 2026 | 17 323,68 | 15 000 | allowance understated |

Four of the five years understate the allowance, so the taxpayer deducts less
than the law permits and OVER-pays. That direction produces a valid return, no
refusal and no signal, and `no-silent-under-declaration` names it as the axis
nothing in this repository watches -- which is why the defect survived a mirror,
a review and a format migration untouched. The 2022 row runs the other way and
would have overstated the deduction.

2022 to 2025 are the figures AEAT prints in the Manual practico Renta for each
ejercicio, each with its own arithmetic. 2026 has no Manual until 2027 and is
derived from Orden PJC/297/2026 art. 18 by AEAT's own printed method, which
reproduces all four published years to the cent; that reproduction is itself
asserted in the test suite, so the derivation cannot silently drift.

Carrying this required extending the format: windows were attached to citations
only, so a year-variable VALUE had nowhere to live. `ProportionalityRule` now
takes dated `statutory_cap_schedule` rows -- the brief's own
`{value, valid_from, valid_to}` idiom, applied to the value. A cap is either
law-fixed or year-referenced, never both, and coverage intersects cap
availability with citation evidence so the corpus cannot claim a year it can cite
but not compute.

### Two RIRPF articles were enrolled from the bundled corpus, with no fetch needed

Six profiles -- telefonia movil and the five vehiculo categories -- rest on RIRPF
art. 22 alone, and the dietas profiles on art. 9. Neither was in the legal
catalogue, and both looked like they would need fetching. They did not: RD
439/2007 is already bundled consolidated, so both were enrolled pointing at that
file with `required_text` phrases read out of it and verified present before the
entries were written.

Art. 9's dietas amounts (53,34 and 91,35 con pernocta; 26,67 and 48,08 sin
pernocta) match the shipped `statutory_cap_variants` exactly, and its
`effective_from` is recorded as 2008-01-01 rather than the 2007 publication
because apartado A.3 was given that effect by RD 1804/2008 -- the conservative
claim, and one that still spans every supported year. Both entries are
`agent_reviewed` with an explicit operator-re-stamp note, following the pattern
the sibling LIRPF entries already use.

### The category citation `quote` fields carry locale keys that do not exist

Every one of the 83 citations sets `quote` to a dotted key such as
`categories.registry.cuotas_colegiales.citations.0.quote`. A search of all four
locale catalogues finds zero `categories.registry.` keys, so each resolves
through the translation fallback to a word derived from the final key segment.

This is the same defect `2026-08-06-iva-catalogue-prose-grounding-adr` closed for
the IVA catalogue, still open here, and it is why the three under-cited profiles
above could not simply be re-grounded in passing: their citations carry a
document pointer and a locator but no evidence text at all.

`dev/locales/_registry_scanner.py` deliberately excludes citation quotes from the
locale scan, documenting that they are "verbatim AEAT excerpts ... authored as
Spanish text in the registry TOML, never translated". The data disagrees with
that comment. The fix is the one the IVA catalogue took: inline the verbatim
Spanish and check it against the bundled corpus.

It was left alone here on purpose. It is a grounding defect, not a format one,
and folding it into a format migration would have hidden a substantive change to
what the corpus asserts inside a mechanical diff.

### Every citation is now bounded on exactly one axis

The corpus previously had a hole the first pass did not close: an edition-dated
citation was bounded by the edition year it names, but a statutory citation was
bounded by nothing a gate could read, so its window was pure author assertion.

`CategoryCitationSource` is now partitioned. An annual-edition source is bounded
by its edition and must NOT carry a provision id; a statutory source must carry
one and is bounded by that provision's effective span. The partition is derived
from the enum rather than listed, and a gate asserts the two sets union to the
whole enum and do not intersect -- so a new source cannot arrive bounded by
neither, which is the failure this closes.

### The IVA gates went green, and the reason matters

`test_year_coverage_matches_supported_filing_years` failed both its
parameterisations at `507a5fb98b` and now passes. `test_exact_key_corpus_year_coverage`
went from three failing corpora to one.

Neither corpus gained a year by copying. Both were year-neutral throughout -- the
catalogue file contained no `2025` token in its body, and place-of-supply's only
year token was `1992`, the law's identifier -- so the four-year shortfall was an
artefact of filing year-neutral content under year-named filenames. Every cited
provision resolves in the legal catalogue, took effect before 2022, and is
repealed in none of the supported years, so the 2022-2026 span is derived and
re-derived on every run by the provision-window gate.

A reviewer seeing one red test turn green beside a corpus that lost two thirds of
its filenames is looking at the same shape a mirror would produce. The
provision-window gate is what distinguishes them and has to be read as part of
the same change.

### The place-of-supply sentinel row carries no window and is unchecked

One `[[place_of_supply_rules]]` row is `legal_basis_exempt`: it codifies no tax
treatment, cites no provision, and now declares no validity window either. It is
excluded from the coverage derivation rather than treated as covering everything
or nothing, and the provision-window gate has nothing to check it against.

That is consistent with the row's existing contract, which already refuses
citations and a supply nature on an exempt row, and the model refuses a window
there too rather than allowing an optional one to drift. It is nonetheless a row
whose applicability rests on a product decision, not a legal one, and it is
recorded here so nobody concludes the gate covers every row.

### Two corpora were assessed and are permanently excluded

`authorization.d` is excluded structurally: its `renta_years` values include a
discontiguous set, which a single span cannot express without either admitting a
year wrongly or costing more rows than the array it replaces.
`m303_orden_anual` is excluded as already conforming -- generator-owned
per-ejercicio rows in one digest-pinned manifest, reached by a different route.
Neither is a deferral, and neither should be revisited as one.

### Unrelated red in the shared worktree at the time of this work

`src/cadrumo/domain/usage_ratios/tests/test_censo_refuse_load.py` fails eight
parameterisations with
`load_usage_ratios_with_censo_guard() missing 1 required keyword-only argument: 'year'`.
Neither that test nor the service it calls was touched here; a peer's in-flight
change added the parameter. Recorded so the failure is not attributed to this
migration.

## Recommendations

- Operator re-stamp on the four agent-reviewed legal judgments this change
  landed: the two RIRPF catalogue entries, and the article chosen as the basis
  for each of the three previously uncited profiles. These are tax reviews an
  agent performed against the bundled corpus, and they are marked as such rather
  than passed off as operator-reviewed.
- Re-derive the 2026 mutualidad cap against the Manual practico Renta 2026 when
  AEAT publishes it in 2027. It is the one figure in the schedule that is derived
  rather than published, and the test that pins it names that distinction.
- Close the category citation `quote` defect the way the IVA catalogue closed it:
  inline verbatim Spanish, check it against the bundled corpus, and correct the
  locale-scanner comment that already describes the intended state.
- Convert category citations from free-text references to registry
  legal-reference ids, so the provision-window gate reaches that corpus and its
  statutory windows can be widened on evidence rather than confidence.
- Leave the exact-year pinning question to the brief that owns it, and read this
  record before concluding the migration changed refusal behaviour.
