---
tags:
  - '#research'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:729a4b5c84b5d0aa1aa4e3852d91091377f570b3bda3b6254ab29b5d5f4dc43d'
related: []
---

# `registry-dated-validity` research: `whole-file-per-year duplication, the four validity spellings, and what the copies actually assert`

A brief proposed replacing whole-file-per-year registry duplication with dated
`valid_from` / `valid_to` rows, naming `aeat/categories/profiles`,
`aeat/iva/catalogues` and `aeat/iva/place_of_supply` as the candidates and the
511-file `valid_from` corpus as the canonical idiom to follow. Measurement at
HEAD (`507a5fb98b`) confirms the duplication and sharpens it in four ways the
brief did not have: the duplicated content is 100% invariant rather than 95%,
its only variance is a set of citations produced by string substitution rather
than by reading, the registry carries four validity spellings rather than one,
and the two IVA corpora are not a duplication problem at all but a live
grounding hole whose own gate forbids closing it by copying.

## Findings

### The two profile years differ only in 82 citation lines, and in nothing normative

`categories/profiles/2024.toml` (1022 lines) and `2025.toml` (1013 lines) both
declare the same 42 `[[profiles]]` and the same 83 citations. Diffing them
yields exactly three classes of change: a 9-line header comment present only in
2024, 41 `reference` lines, and 41 `url` lines. Filtering the diff for any other
content returns nothing.

The 41-of-83 split is exactly the year-dated citation sources: 39 `manual_renta`
plus 2 `aeat_help` carry a year in their reference string and URL path; the 34
`ley_irpf` and 8 `reglamento_irpf` citations are year-neutral and byte-identical.

Every normative field is byte-identical across the two years: all 42 `kind`
values (23 `full_deductible`, 9 `usage_ratio_home_area`, 6
`usage_ratio_personal`, 4 `statutory_cap`), every `statutory_multiplier`, and
every cap, being `statutory_cap_eur = "15000"` for mutualidad,
`statutory_cap_eur = "500"` for seguro, and the four dietas rates `"26.67"`,
`"53.34"`, `"48.08"` and `"91.35"`. The brief estimated the genuinely
year-variable surface at roughly 5%, naming the mutualidad and dietas caps. At
HEAD that surface is 0%: those caps do not vary between the two files. The total
variance is 82 of 2035 lines, all of it citation metadata.

### The 2024 file states in its own header that it was mirrored, not read

`categories/profiles/2024.toml:1-8` declares itself "Generated to parity with
the reviewed 2025 registry", says the proportionality rules are
"framework-stable LIRPF art. 28/30 + RD 439/2007 art. 9 values unchanged for
2024", and says the year-specific caps "are mirrored from the 2025 artifact".

This makes the 82 differing lines the load-bearing observation rather than an
incidental one. A mirrored file whose year-dated citations were rewritten by
substitution asserts, 41 times, that a named 2024 document at a specific URL
supports a specific rule. Nothing in the header claims the 2024 manual was
opened. The framework-stability claim for the rules is plausible on its face,
since LIRPF art. 28/30 did not move, but it is an assertion the file makes about
itself rather than one any gate checks.

The registry already has a written position on exactly this act, in a different
corpus.
`src/cadrumo/domain/iva/tests/test_year_coverage_matches_supported_filing_years.py:22-24`
states that closing its red "never means copying an adjacent year's table: a
mirrored provision is a fabricated citation wearing a legal reference, which is
the failure the grounding rules exist to prevent." The categories corpus is not
enrolled in that gate.

This bears directly on the migration shape. Collapsing the two years to one
dated row set is not citation-neutral: either both citation sets are retained,
in which case the duplication that actually exists is not removed, or they
collapse to one, which silently retracts 41 claims about the 2024 manual.
Widening a window over mirrored content converts a copy into an assertion of
multi-year grounding.

### The two IVA corpora are four years short of the declared window, and the gate is red at HEAD

`aeat/legal/supported-filing-years.toml` declares
`years = [2022, 2023, 2024, 2025, 2026]`. A live load shows
`load_iva_catalogues()` and `load_place_of_supply_rules()` each covering `[2025]`
only, against `load_category_profile_registry()` covering `[2024, 2025]`.

`test_year_coverage_matches_supported_filing_years.py` consequently fails both
its parameterisations at HEAD, pre-existing and unrelated to this work:
"aeat/iva/place_of_supply resolves by exact year but does not cover supported
filing year(s) [2022, 2023, 2024, 2026]".

The brief characterised these two corpora as "single year; will duplicate on the
next year admitted". The measurement is the opposite condition: they are not
duplicated and cannot become duplicated by admitting a year, because the years
are already admitted and the tables are missing. Their problem is grounding, and
the gate's remedy clause is explicit that a format change cannot discharge it.

The catalogue's citations are additionally machine-checked verbatim against the
bundled corpus per `2026-08-06-iva-catalogue-prose-grounding-adr`, so any window
spanning years has to hold that check per year rather than once.

### The registry carries four validity spellings, not one

The brief's premise that `{ key, value, valid_from, valid_to }` is already
canonical holds for one subsystem only. A census of `aeat/` TOML files by token:

| spelling | files | where |
|---|---|---|
| `valid_from` | 510 | 499 `modelos/` (370 `parameters/`, 128 `revisions/`, 1 `casillas/`), 9 `treaties/`, 2 `legal/` |
| `valid_to` | 418 | subset of the above |
| `applies_from` | 102 | 54 `modelos/`, 48 `legal/` |
| `effective_from` | 68 | `legal/` catalogue, `iva/rates.toml`, `iva/recargo-rates.toml` |
| `effective_until` | 2 | `iva/rates.toml`, `iva/recargo-rates.toml` |
| `renta_years` | 29 | `authorization.d/` |

`valid_from`'s canonical home is the modelo revision parameter subsystem, being
`ParameterDefinition`, `bracket_table` and `keyed_brackets`, with its own
resolver `resolve_keyed_bracket`
(`src/cadrumo/domain/calculations/registry/formula_runtime_ops.py:307`), gap
validation (`_validate_parameter_temporal.py:36,86,131`), overlap validation
(`schema_formula.py:234`) and a dating-convention gate
(`_validate_valid_from_ejercicio_convention.py:63`). That machinery is scoped to
a revision, which is the unit the brief correctly places out of scope.

Neither `categories/profiles` nor the two IVA corpora sit inside a revision, so
none of that resolver machinery reaches them. Adopting the spelling does not
inherit the mechanism.

`iva/rates.toml` is the nearer precedent: dated rows in one undated file, using
`effective_from` / `effective_until`, sitting in the same `iva/` directory as the
two year-named corpora. Its header records a past defect in which
`effective_from` had been set to a data-refresh boundary and was then read as
legal effect, invalidating 2022 and 2023 lines across more than thirty modelos.

### Three near-identical loaders, one shape, none shared

`load_category_profile_registry` (`domain/categories/_registry.py:86`),
`load_iva_catalogues` (`domain/iva/_catalogue.py:69`) and
`load_place_of_supply_rules` (`domain/iva/_place_of_supply.py:138`) implement the
same five steps independently: `scan_directory(root, "*.toml")`, a stat
fingerprint, an `lru_cache` keyed on that fingerprint, `int(path.stem)` as the
year, and a `dict[int, ...]` resolved by exact key.

All three resolvers raise on a miss with no adjacent-year fallback:
`resolve_category_profiles` (`_registry.py:124`), `resolve_catalogue`
(`_catalogue.py:102`), `place_of_supply_rule` (`_place_of_supply.py:262`). The
refusal is deliberate and documented in the last: "an ungrounded placement has no
provision behind it, so answering anyway would manufacture one."

That refusal is the year-pinning behaviour the brief reserves to a separate
brief. It is expressible either way: closed windows preserve it exactly, an
omissible `valid_to` silently removes it. The choice is therefore inside this
change's blast radius even though the defect is not, which the ADR has to handle
rather than assume away.

### Partial adoption of dated rows fails silently, with an in-tree precedent

`2026-08-04-profile-derived-selectors-research` records that `_in_window_order`
sorts an absent `valid_from` as `date.min`
(`application/user_profile/_projections.py:30-36,168`), so once any dated row
exists at a path, an undated write persists without error and never resolves as
effective again. It concluded that incremental adoption of windows is unsafe "in
a way that does not announce itself".

That document also rejected effective-dating for the profile-fact corpus, on
grounds that do not transfer: its objection was that taxpayer facts already carry
a time axis twice, and that the registry revision windows are the authority for
the law's axis. For registry-resident regulatory data the same argument runs the
other way. What does transfer is the silent-partial-adoption hazard, and its
warning that a design introducing a temporal mechanism must adopt or retire the
dormant `_ProfileSelector.valid_at`
(`domain/calculations/registry/_bindings.py:762`) rather than leave a second
unread axis beside a new one.

### The two Tier-2 corpora are not candidates, for structural reasons

`authorization.d/` is 29 fragments of roughly five lines each carrying
`renta_years` arrays. It is already sparse; there is no duplication to remove. It
is also not convertible: the observed values include `renta_years = [2024, 2026]`,
a discontiguous set that a single `valid_from`/`valid_to` span cannot express
without either admitting 2025 wrongly or splitting into two rows, which is
strictly more verbose than the array it replaced.

`m303_orden_anual/` is a single generator-owned `manifest.toml` with one
`[[sources]]` row per ejercicio 2022 through 2026, each digest-pinned, beside one
591 KB `censuses.json`. It is not a duplicated corpus at all; it is already an
instance of the shape this work is trying to reach, arrived at by a different
route. Its header refuses hand-editing and
`dev/registry/analysis/m303_orden_anual.py` owns regeneration.

### Consumers, and the surfaces a migration touches

Excluding `dev/benchmarks/cli/.baseline-source-snapshot/`, which is a snapshot
copy of the tree rather than a live consumer:

Categories reaches 8 production modules beyond its own package, being
`domain/usage_ratios/_model.py` and `_service.py`, `domain/transactions/_llm.py`,
`application/ledger/ratios.py`, `application/filing/_review.py`,
`core/resources/_repos/category_profiles.py` and
`dev/locales/_registry_scanner.py`, plus 6 test modules. The IVA catalogue
reaches `application/invoices/_lifecycle.py`,
`application/operator_surface/_action_resolution.py`, `domain/iva/_lookup.py` and
three CLI modules, plus `core/resources/_repos/iva_catalogues.py`.
Place-of-supply is contained within `domain/iva` and its tests.

`core/resources/_repos/` wraps both as year-keyed `ResourceCacheRepository`
implementations keyed on `int`, so the year is a cache key in a second place and
any change to what "a year" means has to reach it.

### The in-flight campaign that abuts this, and what it does not own

`2026-08-14-registry-temporal-coverage-plan` (32/52 steps) owns the supported-year
enforcement flip: `W02.P05.S25` refuses consumption for an unsupported filing
year, and `W03.P08.S20` flips the advisory surfaces to blocking. Neither that
plan nor any other in flight has a row for the categories duplication or for the
IVA corpus grounding hole; scanning its rows for `place_of_supply`, `catalogues`,
`categor` and `profiles` returns only unrelated matches.

The ordering consequence is real: `S25` and `S20` make an unsupported year a
refusal, and the two IVA corpora are missing four supported years today.

### Not investigated

Whether the 41 mirrored 2024 citations are substantively correct. That is a tax
review against the 2024 Manual práctico, not a code question, and the answer
changes what a migration may collapse. Whether the `applies_from` and
`effective_from` populations should converge on one spelling; both sit behind
their own validated schemas and gates, and sweeping them is a larger relocation
than this corpus work. Whether `domain/categories/__init__.py` and
`domain/iva/__init__.py` are inert as `aeat-architecture-boundaries` requires;
both carry loader-naming docstrings and were not checked for symbol binding. The
9 `treaties/` and 2 `legal/` `valid_from` files were counted but not read.

## Sources

- `src/cadrumo/_data/registry/aeat/categories/profiles/2024.toml:1-8` - the mirroring header
- `src/cadrumo/_data/registry/aeat/categories/profiles/2025.toml` - 42 profiles, 83 citations
- `src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml` - `[2022..2026]`
- `src/cadrumo/_data/registry/aeat/iva/rates.toml` - the `effective_from`/`effective_until` precedent and its refresh-boundary defect note
- `src/cadrumo/_data/registry/aeat/m303_orden_anual/manifest.toml` - per-ejercicio digest-pinned rows
- `src/cadrumo/_data/registry/aeat/authorization.d/100.toml` - `renta_years` shape
- `src/cadrumo/domain/categories/_registry.py:86,124` - loader and exact-year resolver
- `src/cadrumo/domain/iva/_catalogue.py:69,102` - loader and exact-year resolver
- `src/cadrumo/domain/iva/_place_of_supply.py:138,262` - loader and exact-year resolver
- `src/cadrumo/domain/iva/tests/test_year_coverage_matches_supported_filing_years.py:22-24,66` - the never-mirror clause and the red assertion
- `src/cadrumo/domain/calculations/registry/formula_runtime_ops.py:307` - `resolve_keyed_bracket`
- `src/cadrumo/domain/calculations/registry/_validate_parameter_temporal.py:36,86,131` - bracket window gap validation
- `src/cadrumo/domain/calculations/registry/schema_formula.py:234` - cross-window bracket overlap
- `src/cadrumo/domain/calculations/registry/_validate_valid_from_ejercicio_convention.py:63` - dating convention gate
- `src/cadrumo/domain/calculations/registry/_bindings.py:762` - dormant `_ProfileSelector.valid_at`
- `src/cadrumo/application/user_profile/_projections.py:30-36,168` - absent `valid_from` sorts as `date.min`
- `src/cadrumo/core/resources/_repos/category_profiles.py` - year-keyed resource repository
