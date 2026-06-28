---
tags:
  - '#adr'
  - '#output-language-typed-constant-migration'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-06-01-registry-period-code-union-cli-boundary-adr]]"
  - "[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]"
  - '[[2026-06-04-output-language-typed-constant-migration-research]]'
---


# `output-language-typed-constant-migration` adr: tighten OutputLanguage consumers to the typed StrEnum | (**status:** `accepted`)

## Authoring note

Authored via the Write tool — same bash-quoting-corruption constraint as the M303 dual-keying ADR (2026-06-01) and the RegistryPeriodCode ADR (2026-06-01). Commit-bot validates via `vault check all`.

## Problem statement

Sibling ADR to the RegistryPeriodCode CLI-boundary work (committed `68e36a134`). The output-language axis is the OTHER constant-like axis that the S801 α-survey-and-beyond audits surfaced as candidate for typed-constant migration.

Ground-truth at `src/aeat/core/external_constants.py`:

- Line 329: `class OutputLanguage(StrEnum)` — closed 4-member enum (`ES`, `EN`, `CA`, `HU`).
- Line 345: `DEFAULT_OUTPUT_LANGUAGE: Final[OutputLanguage] = OutputLanguage.ES`.
- Line 348: `SUPPORTED_OUTPUT_LANGUAGES: Final[tuple[OutputLanguage, ...]] = tuple(OutputLanguage)`.
- Line 324: `OUTPUT_LANGUAGE_ENV_VAR: Final[str] = "AEAT_OUTPUT_LANGUAGE"`.

The StrEnum is ALREADY in place. The question is consumer-side coverage: 11 consumer files exercise the language axis as bare `str` (CLI argument types, settings field types, internal data-class fields, test surfaces), while only the constants module itself imports `OutputLanguage` directly. The audit question for this ADR is whether to tighten the 11 consumer sites to the typed enum, and if so how.

## Forces in tension

**Closed-set CLI hint (`aeat-architecture-boundaries` mandate)**: "every Typer argument whose value is a closed enum MUST declare that enum as its type so click renders `Choice([...])` and surfaces the accepted-value set on parse failure". The language axis is a closed 4-member set with NO unbounded member (unlike the period axis at `RegistryPeriodCode`). The escape clause from the period ADR does NOT apply here — there is no regex-shaped member that justifies the `Annotated[str, BeforeValidator]` shape.

**Roundtrip discipline (`aeat-roundtrip-discipline`)**: persisted boundary fields carrying language must roundtrip through the encrypted-envelope identical to in-memory form. StrEnum values JSON-serialise as their underlying string ("es" / "en" / "ca" / "hu"); pydantic v2 deserialises them back to enum members via the StrEnum-as-value coercion. Roundtrip is clean.

**Settings interaction**: pydantic-settings reads `AEAT_OUTPUT_LANGUAGE` env var as `str | None` today (the field at `src/aeat/core/config.py`). The settings layer historically uses bare `str` for env-var-sourced fields because the env-var value can be anything an operator passes. Typing the settings field as `OutputLanguage | None` would refuse malformed env-var values at settings-load time rather than at use-time. That's a behaviour change the team should opt into deliberately.

**Existing fallback semantics**: per `src/aeat/core/i18n/_render.py:172, 180`, an invalid `aeat_output_language` value (anything outside the supported set) normalises to `None` via `_normalise_supported_language()` and falls back to `DEFAULT_OUTPUT_LANGUAGE`. The renderer is forgiving by design — operators with mistyped language codes still get Spanish output rather than a hard refusal. This fallback is documented operator-friendly behaviour (test_render_override.py:28-38 pins it). Typing the field as `OutputLanguage | None` AT THE PYDANTIC LAYER would refuse load with ValidationError, breaking the forgiving fallback.

**Migration cost**: 11 consumer files. The CLI sites (~3-4 of them via Typer `--output-language` flags) get clean `OutputLanguage` typing. The internal data-class fields (~3-4 of them) get clean `OutputLanguage | None`. The settings-layer field (1) and the resolver-internal `_cached_output_language` cache key (1) are the tricky ones — they touch the forgiving-fallback semantics.

## Candidate shapes evaluated

### Candidate 1 — Migrate all 11 consumer sites to `OutputLanguage` / `OutputLanguage | None`

Typer CLI flags type-annotated as `OutputLanguage` (click renders `Choice(["es", "en", "ca", "hu"])`). Internal data-class fields typed as `OutputLanguage | None`. Settings field typed as `OutputLanguage | None` with a pydantic `BeforeValidator` that normalises invalid input to `None` (preserving the forgiving fallback semantic at the validator layer rather than the type layer).

**Pros**:
- Honours `aeat-architecture-boundaries` mandate at every site.
- CLI gets click `Choice([...])` rendering — operator sees the accepted set on parse failure.
- Type-checker (mypy / pyright) catches string-literal mismatches at every consumer site.
- Roundtrip-clean per `aeat-roundtrip-discipline` (StrEnum JSON-encodes as the underlying string).

**Cons**:
- Settings-layer migration is non-trivial. The forgiving-fallback semantic must be preserved (operators with mistyped env-vars get Spanish, not a ValidationError). Requires a `BeforeValidator` on the settings field that normalises invalid input to `None` BEFORE the type-check fires. ~10 LOC + new test.
- The `_cached_output_language` cache key (an internal helper, not a public surface) currently uses `str` to key the lru_cache; this is intentional because the cache must handle any input including invalid forms. Migration there is purely cosmetic and risks reintroducing the forgiving-fallback bypass if the cache-key type is tightened too aggressively.
- ~11-site migration is ~2-3 commits. Roundtrip tests per `aeat-roundtrip-discipline` add ~50 LOC.

ACCEPT for CLI sites + data-class fields. PARTIAL ACCEPT for settings + cache surfaces (see D2 below).

### Candidate 2 — Defer-with-discipline (status quo + new gate test)

Leave the 11 consumer sites as bare `str`. Author a regression-test gate that grep-asserts: any new `str` field referencing the language axis must either (a) consume `OutputLanguage` directly OR (b) be exempted via a documented inline comment citing the forgiving-fallback rationale. The gate prevents drift without forcing migration.

**Pros**:
- Zero behavioural change. Forgiving-fallback semantics preserved verbatim.
- Lowest implementation cost (~30 LOC gate test).

**Cons**:
- Violates `aeat-architecture-boundaries` mandate at every existing CLI site. Operator-facing CLI parse failures don't surface the accepted set today; that's a real UX gap.
- Type-checker can't catch string-literal mismatches at consumer sites.
- Defers a known migration without a forcing event — typed-axis hygiene drift accumulates.

REJECT as the standalone shape, but ADOPT the gate-test idea as a hardening complement to Candidate 1 (D3 below).

### Candidate 3 — `Annotated[str, BeforeValidator]` (the RegistryPeriodCode shape)

Mirror the period ADR's Candidate 3 verbatim. `OutputLanguageStr = Annotated[str, BeforeValidator(_validate_output_language)]`.

**Pros**:
- Symmetry with the period axis. Single template for both constant-like axes.
- Forgiving-fallback semantic can live inside the validator.

**Cons (fatal)**:
- The period ADR's Candidate 3 was chosen BECAUSE the period axis has an unbounded regex member (`EVENT-N`). Output language has NO such member. The escape clause that justified Candidate 3 there does NOT justify it here.
- Loses CLI `Choice([...])` rendering. The 4-member language set is small and stable; rendering it as a click choice is exactly the operator-facing surface `aeat-architecture-boundaries` mandates.
- Static-type-checker sees `str`, not `OutputLanguage`. Same downside as Candidate 2 but with extra runtime-validation overhead for zero gain.

REJECT. The shape exists for a specific failure mode (unbounded member) that doesn't apply here.

## Decision

### D1 — Adopt Candidate 1 (typed StrEnum) for CLI sites + data-class fields. Migrate now.

The ~7-8 CLI sites and data-class fields that today carry the language axis as bare `str` get retyped to `OutputLanguage` or `OutputLanguage | None`. Typer renders click `Choice(["es", "en", "ca", "hu"])`. Pydantic strict-frozen models reject string literals outside the enum. Type-checker catches mismatches at consumer sites.

Per `aeat-architecture-boundaries`: this is the documented direction; the language axis is the canonical example of a closed 4-member enum that SHOULD be typed at every boundary.

### D2 — PARTIAL migration for settings layer + cache surfaces. Document the forgiving-fallback semantic.

Two specific sites stay nuanced:

**Settings field at `src/aeat/core/config.py`**: type the field as `OutputLanguage | None = None` with a `BeforeValidator` named `_coerce_output_language_setting` that:
- Accepts any string input.
- Lower-cases and strips.
- Returns the matching `OutputLanguage` member OR `None` for invalid input (preserving the forgiving fallback).

The settings field stays operator-friendly: malformed `AEAT_OUTPUT_LANGUAGE` env vars normalise to `None` and fall through to `DEFAULT_OUTPUT_LANGUAGE` at resolution time, NOT raising at settings-load. The type signature stays clean (`OutputLanguage | None`) while the validator preserves the existing behaviour.

**Cache key at `_cached_output_language` (`src/aeat/core/i18n/_render.py`)**: the lru_cache key is a tuple of hashable values used as a memoisation key. Internal helper; no public surface. Leave as `str` per the existing implementation; the cache must handle any input including invalid forms because the cache is consulted BEFORE `_normalise_supported_language` resolves the final value. Cosmetic migration here would be net-negative (risk of reintroducing the forgiving-fallback bypass for zero type-safety gain).

### D3 — Add a regression-test ratchet (the Candidate 2 gate adapted)

Author a new test under `src/aeat/core/i18n/test_output_language_typed_consumers.py` that asserts every public-surface field referencing the language axis (settings, profile, CLI arguments, data-class fields) consumes `OutputLanguage` directly OR carries an explicit exemption comment citing this ADR. Internal helpers (cache keys, normalisation functions) are exempt by name.

The ratchet prevents future drift: a new feature that adds a bare `str` language field gets caught at PR review (test failure), not after merge.

### D4 — No new module surface needed

Unlike the RegistryPeriodCode ADR (which introduced `RegistryPeriodCode` + `accepted_period_codes()` + `accepted_period_patterns()`), this ADR doesn't introduce new public symbols. The existing `OutputLanguage` / `DEFAULT_OUTPUT_LANGUAGE` / `SUPPORTED_OUTPUT_LANGUAGES` surface is sufficient. The `_coerce_output_language_setting` validator (D2) is internal to `core/config.py`.

## Consequences

### Affected surfaces

- CLI: ~3-4 `--output-language` Typer sites. Each gets `output_language: OutputLanguage = OutputLanguage.ES` (or `OutputLanguage | None = None` if optional). Click renders `Choice([...])` automatically.
- Data-class fields: ~3-4 internal models (FilingDraft, calculation observation envelopes, profile fields). Each gets typed annotation. Roundtrip tests verify JSON encode/decode preserves the enum value.
- Settings: 1 field at `core/config.py`. New `BeforeValidator` (~10 LOC) + 1 test confirming malformed env-vars normalise to `None`.
- Cache: 0 changes. `_cached_output_language` key stays `str` per D2.
- New ratchet test (~30 LOC).

Total: ~3 commits.

### Migration order

1. Land `_coerce_output_language_setting` validator + settings-field migration + the regression-test ratchet. Standalone commit; preserves forgiving-fallback verbatim.
2. Migrate CLI sites. Per-site `--help` text already documents accepted languages; no operator-facing prose change beyond click's auto-rendered choice list.
3. Migrate data-class fields. Add roundtrip tests per `aeat-roundtrip-discipline`.

### Operator surface

- CLI parse failure on `--output-language BOGUS` now produces click's auto-generated choice prompt: `Invalid value: 'BOGUS'. Choose from 'es', 'en', 'ca', 'hu'.` Operator sees the accepted set at parse time, not at runtime fallback.
- Existing `AEAT_OUTPUT_LANGUAGE` env-var forgiving-fallback semantic preserved. Operators with mistyped env-vars STILL get Spanish output (per the documented test contract at `test_render_override.py:28-38`).

### Test discipline

- New ratchet (D3) refuses any new bare-`str` language field on public surfaces.
- Settings-validator test pins the forgiving-fallback semantic at the validator layer (mistyped env-var → None → fallback to ES).
- Roundtrip tests on the data-class fields pin StrEnum equality post-JSON-roundtrip.

## Out of scope

- The settings-load behavioural shift question (refuse vs forgive). This ADR documents the forgive-via-BeforeValidator path verbatim per existing test contract. A future ADR could revisit if the team wants strict refusal.
- Adding new languages (EU / Latin American Spanish variants). Not in scope; the 4-member set covers AEAT's filing-language requirements.
- The locale-resolution fallback chain itself (`_render._cached_output_language` decision tree). The behaviour stays as-shipped; only the type annotations at consumer surfaces change.

## Sibling impact assessment

- Period axis (`RegistryPeriodCode`): different shape entirely. Period needs `Annotated[str, BeforeValidator]` because it has an unbounded `EVENT-N` member. Language is a closed 4-member StrEnum. The two ADRs are complementary, not contradictory — they document the two ends of the "closed-set axis" spectrum.
- CCAA, modelo, IrpfSpecialRegime: already typed as StrEnums per `aeat-architecture-boundaries`. No migration needed.
- The output-language axis was the ONE constant-like axis that had a typed enum already authored but consumer-side coverage was patchy. This ADR closes the gap.

## Decision summary

ACCEPT Candidate 1 for CLI sites + data-class fields. PARTIAL Candidate 1 for settings layer (with `BeforeValidator` preserving forgiving fallback). REJECT Candidate 2 (status quo) as standalone but ADOPT its ratchet idea (D3). REJECT Candidate 3 (`Annotated[str, ...]`) as not justified — escape clause doesn't apply for closed 4-member axis. Existing `OutputLanguage` StrEnum surface stays; no new symbols introduced.

Migration scope ~3 commits. Forgiving-fallback semantic preserved verbatim per existing test contract.
