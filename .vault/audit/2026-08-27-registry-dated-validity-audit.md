---
tags:
  - '#audit'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:2611653f2deb6753622a4e2f5d99f329f98ba9cbb688f937b43b6e579dc614e8'
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

### Spending-category profiles ground 2025 only, and that red is real

The corpus previously reported 2024 and 2025. The 2024 file was a mirror of the
reviewed 2025 one, and its 41 year-dated citations were rewritten by string
substitution; they were dropped rather than re-windowed, per the accepted ADR.

Thirty-nine of the 42 profiles keep statutory `ley_irpf` and `reglamento_irpf`
grounding, which is the stronger authority and was never year-dated. Three carry
no year-neutral citation at all -- `cuotas_colegiales`, `cuotas_autonomos_ss`
and `mutualidad_alternativa` -- and at least one citation is a hard model
invariant, so those three pin the corpus to 2025.

`test_exact_key_corpus_year_coverage` therefore reds for this corpus, missing
2022, 2023, 2024 and 2026. It was already red for 2022, 2023 and 2026 before this
work; 2024 joined them. That is the designed outcome: the year is now visibly
ungrounded instead of invisibly mirrored. Closing it means reading the manual for
those years, never widening a window -- and the model now refuses the widening.

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

### Category citations cannot be provision-checked, so their windows stay narrow

The IVA corpora's windows are bounded by the cited provision's own effective span
in the registry legal catalogue, which makes a multi-year span a derived fact.
Category citations carry free-text `reference`, `locator` and `url` rather than a
registry legal-reference id, so nothing can check a wider span there.

Every category window was therefore authored at 2025 only -- the year that was
actually reviewed -- including the statutory citations that are almost certainly
stable across neighbouring years. Converting those citations to legal-reference
ids is what would let the provision-window gate widen them honestly, and is the
single highest-value follow-up for this corpus.

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

- Ground filing years 2022, 2023, 2024 and 2026 for the spending-category corpus
  against the Manual práctico for each year, starting with the three profiles
  that carry no statutory citation. Never widen an existing window to admit a
  year; the model refuses it and the refusal is the point.
- Close the category citation `quote` defect the way the IVA catalogue closed it:
  inline verbatim Spanish, check it against the bundled corpus, and correct the
  locale-scanner comment that already describes the intended state.
- Convert category citations from free-text references to registry
  legal-reference ids, so the provision-window gate reaches that corpus and its
  statutory windows can be widened on evidence rather than confidence.
- Leave the exact-year pinning question to the brief that owns it, and read this
  record before concluding the migration changed refusal behaviour.
