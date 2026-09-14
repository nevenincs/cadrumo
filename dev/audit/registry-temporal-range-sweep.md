# Registry temporal support-range mechanical sweep

Date: 2026-09-14

## Authority established

The sole product-wide support declaration is
`src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml`:

```toml
[supported_filing_years]
floor = 2022
horizon = 2026
```

This means:

- 2022 is the hard lower gate.
- 2026 is the last year with authored corpus coverage, not a maximum accepted year.
- There is no `hard_ceiling`; years after 2026 remain admissible through forward
  projection of the newest applicable revision.
- `SupportedFilingYearsCatalogue.years` derives `(2022, 2023, 2024, 2025, 2026)`
  from those bounds. Consumers must not author that tuple independently.

The loader rejects a second `[supported_filing_years]` declaration, and the schema
rejects the retired enumerated `years` key. The canonical runtime route is
`ValidatedRegistryAuthority.catalogues.supported_filing_years`.

## Mechanical method

`dev/audit/registry_temporal_range_sweep.py` reads the canonical TOML first, then:

1. parses Python with `ast` and identifies literal year containers, literal `range`
   calls, policy-named assignments, and comparisons;
2. parses TOML with `tomllib` and identifies support/coverage enumerations outside the
   authority file;
3. limits candidates to values intersecting the authority's derived authored span;
4. leaves classification to review because legal vintages, revision identities,
   applicability windows, and boundary fixtures legitimately contain concrete years.

The initial AST pass produced 3,272 candidates. A narrower exact-pattern pass produced
314 sites. Most are legitimate single-coordinate fixtures or legal/revision spans; the
findings below are the sites whose names or behaviour claim broader support authority.

## Findings

### RY-001 — MCP filing-year completion invents a second product range

Severity: high. Confidence: high.

`src/cadrumo_harness/mcp/_completions.py:30` declares:

```python
_FILING_YEARS = tuple(str(year) for year in range(2019, 2031))
```

The module says its axes come from registry declarations and cannot drift, but this
list admits 2019–2021 below the registry floor and imposes an arbitrary 2030 endpoint
despite the registry having no hard ceiling. The CLI rejecting invalid selections
later does not make the offered completion range authoritative or non-divergent.

Required direction: obtain completion candidates from the validated registry
authority. Since an open upper span cannot be enumerated completely, the completion
policy needs a separately named UI suggestion window derived from `floor`, `horizon`,
and an explicit suggestion policy; it must not masquerade as supported years.

### RY-002 — historical corpus exclusions retain a known-drifted `support_years` list

Severity: high. Confidence: high.

`dev/corpus/sync_aeat_record_design_corpus.py:1538-1547` explicitly documents that
`[2023, 2024, 2025, 2026]` has drifted and already contradicts bundled evidence. The
same module nevertheless enforces the exact list at line 1881, and
`dev/corpus/tests/test_record_design_support.py:388` repeats it in a fixture.

This is not merely stale by one year. It is a second, semantically invalid support
authority retained after the code established that the URL list—not the year window—is
the actual exclusion authority.

Required direction: remove the `support_years` field and its exact-list check, or
rename/redefine it as a non-authoritative historical acquisition cohort with evidence
for its bounds. It must not use the product support vocabulary.

### RY-003 — “supported period matrix” is bounded by a private 2023–2026 range

Severity: high. Confidence: high.

`dev/registry/conformance/tests/test_catalogue_verification_coverage.py:51` defines
`_SUPPORTED_RECORD_DESIGN_YEARS = range(2023, 2027)` and line 93 drives the test from
it. The test is named `test_supported_period_matrix_has_applicable_record_design_sources`.

The private range omits the canonical floor year 2022 and freezes the current horizon.
It can therefore stay green when the registry support declaration changes. If 2022 is
intentionally excluded because record-design evidence is absent, that absence is a
coverage disposition/gap and should be surfaced, not erased from the denominator.

Required direction: derive the matrix from
`catalogues.supported_filing_years.years`; express publication-bound or unavailable
evidence through the existing typed exception/disposition mechanism.

## Explicit non-findings

The sweep does not classify the following as support-range drift without additional
evidence:

- concrete years in legal applicability and source windows;
- revision IDs/directories such as `2024-desde-09-y-3t`;
- single filing coordinates used as test fixtures;
- boundary years used to test `Period`, date, storage, or selector behaviour;
- modelo-specific inception, transition, carry, and record-layout epochs.

Those values must remain concrete because replacing legal or revision identities with
the product support catalogue would erase the temporal rule being tested.

## Recommended implementation order

1. Replace RY-001 with an authority-backed completion projection and add below-floor,
   horizon, and post-horizon tests.
2. Remove or reclassify the known-invalid corpus `support_years` field (RY-002).
3. Make the record-design conformance denominator authority-derived (RY-003) and let
   missing 2022 evidence appear explicitly.
4. Turn the high-confidence portion of the parser into a CI gate only after an
   allowlist taxonomy exists; the raw four-digit-year scan is intentionally too broad
   to gate safely.

## Remediation status

Implemented on 2026-09-14:

- RY-001 now obtains its finite authored-year completion values from the typed
  `SupportedFilingYearsCatalogue`. The shipped MCP server projects that catalogue from
  the installed content-addressed indexed authority artifact; tests inject it from the
  compiled validated authority.
- RY-002's invalid `support_years` member, contract, fixture, and literal check were
  removed. Historical exclusions are URL-keyed only.
- RY-003 now iterates `catalogues.supported_filing_years.years` and asserts the
  denominator is present and non-empty.
- Modelo-specific epochs, legal applicability spans, revision censuses, cadence years,
  and ordinary calendar probes remain concrete and are outside this audit's scope.
