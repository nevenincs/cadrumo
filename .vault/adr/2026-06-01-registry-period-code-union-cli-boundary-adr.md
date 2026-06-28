---
tags:
  - '#adr'
  - '#registry-period-code-union'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]"
  - "[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-05-22-schema-hardening-adr]]"
  - '[[2026-06-04-registry-period-code-union-research]]'
---


# `registry-period-code-union` adr: CLI-boundary period-code typing — closed-set hint vs registry-driven refusal | (**status:** `accepted`)

## Authoring note

Authored via the Write tool following the canonical frontmatter shape — the architect's bash session has the same shell-quoting corruption flagged in the M303 dual-keying ADR (`2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr.md`). The `vault add adr` CLI invocation returns EOF immediately. The commit-bot validates via `vault check all` post-commit; the gate is identical regardless of scaffold path.

## Problem statement

The CLI exposes ~15 `--period` sites (per the S801 α-survey at commit `b9ff9dc09`) that span multi-modelo contexts. The legitimate value space at the CLI boundary is the UNION of four sub-vocabularies:

- **StandardPeriodCode** (closed StrEnum at `src/aeat/core/_period.py`): `1T-4T`, `1P-4P`, `0A`, `01-12`. 21 members. Covers the dominant case for M100/M130/M131/M200/M303 quarterly + monthly periods.
- **Extended OSS/IOSS scheme**: `EXT-1T`, `EXT-2T`, `EXT-3T`, `EXT-4T`. Used by M369 (Régimen Especial de la Unión OSS).
- **Ad-hoc lifecycle filings**: `AD-HOC` literal. Used by M308 (devolución a sujetos no establecidos), M309 (declaración no periódica), M360 (devolución intracomunitaria).
- **Event-driven informativas**: `EVENT-N` where `N` is a per-event counter integer. Used by event-triggered informativa filings (M180/M193/M210 event mode, etc.). The integer is operator-supplied per filing event.

The α-scope proposal — "type CLI `--period` flags as `StandardPeriodCode`" — would force Typer to render `Choice([...])` against the 21-member set and REFUSE legitimate `EXT-1T`/`AD-HOC`/`EVENT-N` inputs at parse time. That's wrong: those values are operator-actionable for the corresponding modelos.

The β-scope migration (~50-site application-layer data-class fields under `aggregation/`, `calculations/`, `workflow/`, `modelos/`) needs the same union answer plus persistence-roundtrip-discipline review per `aeat-roundtrip-discipline` — every persisted typed period field must roundtrip through the encrypted-envelope boundary identical to its in-memory form.

This ADR adjudicates the typing shape for both α (CLI hint) and β (application-layer data-class fields).

## Forces in tension

**Closed-set CLI hint**: per the `aeat-architecture-boundaries` rule, "every Typer argument whose value is a closed enum MUST declare that enum as its type so click renders `Choice([...])` and surfaces the accepted-value set on parse failure". This is the operator-facing instructive surface; a bare `str` type leaves operators guessing what's accepted.

**Multi-vocabulary union**: the period axis is genuinely a union, not a single enum. No member-extension of StandardPeriodCode can include `EVENT-N` because the `N` is an unbounded integer; member extension to `EXT-*` is possible but conflates Spanish-territory vocabulary with extra-Union scheme vocabulary that has different regulatory grounding (Reglamento UE 904/2010 + Ley 37/1992 OSS chapter).

**Registry-driven refusal escape clause**: `aeat-architecture-boundaries` explicitly permits "late, registry-driven refusals (e.g. modelo-period-revision combinatorial checks) ... for axes that depend on dynamic registry data, but the refusal MUST list the accepted set in the error message". This is the documented permission for cases where the closed-set hint is incompatible with the actual value space.

**Persistence roundtrip discipline**: per `aeat-roundtrip-discipline`, every persisted boundary must roundtrip via strict pydantic equality. A typed union that loses information at serialization (e.g. dropping the `N` integer of `EVENT-N` during JSON encode) violates the discipline.

**Future evolution**: the period axis will gain more sub-vocabularies as new modelos land (M210 event-mode, IRNR retención periods, supplementary regimes). The typing shape must accommodate growth without rewriting every CLI argument and every persistence boundary.

## Candidate shapes evaluated

### Candidate 1 — Wider StrEnum subsuming all extended forms

Extend `StandardPeriodCode` with `EXT_Q1..EXT_Q4`, `AD_HOC`, and per-event members `EVENT_1..EVENT_N` for some bounded N.

**Pros**: Single type. CLI gets `Choice([...])`. Pydantic validation is trivial.

**Cons (fatal):**
- `EVENT-N` is genuinely unbounded — the operator may supply event-number 1, 2, 27, 142. Bounding `EVENT_N` at any constant (1..50, 1..100) is arbitrary and the bound IS the gate: filings beyond the bound get silently refused without registry grounding.
- Loses regex-precision for `EVENT-N`. The structural shape `EVENT-` + integer cannot be expressed as enum members; trying to enumerate it produces an explosion of dead members.
- Conflates regulatory vocabularies — Spanish-territory + OSS + ad-hoc + event are four distinct regulatory regimes; folding them into one enum hides the discriminator that runtime code may legitimately want to consult.

REJECT.

### Candidate 2 — Discriminated union

Pydantic `Union[StandardPeriodCode, ExtendedPeriodCode, AdHocLiteral, EventPeriodCode]` where:
- `StandardPeriodCode` is the existing 21-member StrEnum (unchanged).
- `ExtendedPeriodCode` is a separate StrEnum with 4 members (`EXT-1T..EXT-4T`).
- `AdHocLiteral` is `Literal["AD-HOC"]`.
- `EventPeriodCode` is a typed model with a `number: int` field and a `__str__` that produces `EVENT-{number}`.

**Pros:**
- Each sub-vocabulary stays cleanly typed and regulator-anchored.
- Pydantic discriminated-union validation accepts every legitimate value and refuses anything not in the union.
- Persistence roundtrip survives — the union's discriminator (e.g. a `kind: Literal["standard", "extended", "ad_hoc", "event"]` field) tags each member; JSON roundtrip preserves both the kind and the value.

**Cons:**
- CLI `Choice([...])` rendering loses fidelity. Typer's choice surface can't represent a union with one unbounded member (`EVENT-N`); the best it can do is render the 21 + 4 + 1 = 26 fully-enumerable values plus an "or EVENT-N where N is an event number" prose hint. The hint is non-machine-checkable; operators may still type `EVENT-abc` and get a late refusal.
- ~50-site application-layer migration is heavier — every data-class field becomes `RegistryPeriodCode = Union[...]` instead of a single enum. Roundtrip tests need explicit kind-discriminator assertions.
- Pydantic v2 discriminated-union shape requires a discriminator field on each member; adding `kind` to `StandardPeriodCode` is a behavioural change (StrEnum doesn't carry metadata cleanly).

DEFER but not reject. This is the architecturally cleanest long-term shape; the migration cost is the operational blocker.

### Candidate 3 — `Annotated[str, BeforeValidator]` with registry validator as single point of truth

Define a `RegistryPeriodCode` type alias:

```python
RegistryPeriodCode = Annotated[
    str,
    BeforeValidator(_validate_period_against_registry),
]
```

Where `_validate_period_against_registry(value: str) -> str`:
- Strips + upper-cases the input.
- Checks against `StandardPeriodCode` membership (fast path).
- Checks against `_EXT_PERIOD_RE` regex (`^EXT-[1-4]T$`).
- Checks against `AD-HOC` literal.
- Checks against `_EVENT_PERIOD_RE` regex (`^EVENT-\d+$`).
- Raises `PeriodValidationError` with the accepted-set in the message if none match.

CLI `--period` argument keeps `str` type. The Typer-side `--help` text manually describes the accepted forms (operator-facing hint) and the registry validator at the application boundary refuses invalid input AT INVOCATION TIME with a message listing the accepted set.

**Pros:**
- Single source of truth: `_validate_period_against_registry`. Every site (CLI, data-class field, persisted boundary) consults the same validator.
- Per `aeat-architecture-boundaries` escape clause: "Late, registry-driven refusals... are acceptable for axes that depend on dynamic registry data". The period axis IS such an axis (the union depends on which modelo the filing targets; `EVENT-N` legitimately depends on the modelo's event-mode registration).
- Roundtrip-clean: the underlying type is `str`. JSON encode/decode is trivial. No discriminator-field complexity.
- Future extension is one regex / one literal added to the validator. No 50-site migration.
- The CLI `--help` text carries the documented accepted-set per the rule's "refusal MUST list the accepted set in the error message" — the operator sees the set when parsing fails AND when reading `--help`.

**Cons:**
- Loses Typer `Choice([...])` rendering. The closed-set hint at the CLI parse layer is replaced by an application-layer refusal. Operator sees the same accepted set but slightly later in the flow (after pressing Enter, not as a tab-completion / parse-time error).
- Static type checkers see `str`, not a constrained type. mypy / pyright won't catch a string-literal mismatch. Counter-argument: the runtime validator catches it on every call, and registry-driven axes need runtime checking anyway (the union members shift per-modelo).
- The validator is the "registry-authoritative" surface, but for `EXT-` / `AD-HOC` / `EVENT-` codes the validator is essentially hardcoded regex/literal sets — there's no registry TOML for period vocabularies today. Means the validator is the de-facto single source even though it's Python, not TOML.

ACCEPT.

## Decision

### D1 — Adopt Candidate 3 (`Annotated[str, BeforeValidator]` with registry validator).

The α-scope CLI typing for `--period` becomes `RegistryPeriodCode` (a `str` alias with a `BeforeValidator`). Typer's `--help` text for each `--period` site explicitly lists the accepted forms relevant to that command's modelo scope. Parse failures route through the validator's error message which carries the accepted set verbatim.

The β-scope ~50-site application-layer migration uses the same alias. Data-class fields declare `period: RegistryPeriodCode`. Pydantic v2 applies the `BeforeValidator` automatically during model_validate; roundtrip through JSON serialises as plain `str`, deserialises back through the validator. No discriminator field needed.

### D2 — Define `RegistryPeriodCode` at `src/aeat/core/_period.py`

Co-locate with `StandardPeriodCode`. Module-level constants for the regex patterns. Module-level frozen set for the literal members.

```python
RegistryPeriodCode = Annotated[
    str,
    BeforeValidator(_validate_period_against_registry),
]
```

The validator function exposes the accepted set via a public function (`accepted_period_codes() -> tuple[str, ...]` for the fully enumerable set; `accepted_period_patterns() -> tuple[str, ...]` for the regex shapes including `EVENT-N`). CLI `--help` builders consult these.

### D3 — Reserve Candidate 2 (discriminated union) as a future-hardening option

If a future need arises to dispatch on period-kind at runtime (e.g. an engine that routes `EXT-` periods differently from `EVENT-N`), the migration path is from D2's `Annotated[str, ...]` to D2-evolved-into-discriminated-union. The validator's existing categorisation logic becomes the union's discriminator function. Migration cost stays bounded because the type alias hides the underlying representation from call sites.

### D4 — Update the M308/M309/M360 modelo registrations to use `AD-HOC`

Spot-check during investigation: M308, M309, M360 currently carry varied period strings in their registry TOMLs. Out of scope for this ADR's authoring Step, but a follow-up should harmonise them to the canonical `AD-HOC` literal so the validator's set membership covers them cleanly. File as FU when prioritised.

### D5 — Author the validator with the registry-authority-flow rule in mind

The validator is Python today (no period-vocabulary TOML). If a future ADR establishes a period-code registry under `src/aeat/_data/registry/aeat/period_codes/` (analogous to `_data/registry/aeat/legal/`), the validator becomes a thin lookup against that registry, and the regex shapes for `EXT-` / `EVENT-` become declared patterns in TOML. The validator's interface stays the same; only its data source changes. This preserves the registry-authority-flow direction of travel.

## Consequences

### Affected surfaces

- ~15 CLI `--period` sites. Each receives the new type annotation. Per-site `--help` text gets an explicit accepted-set list. Estimated 1 commit, ~30 LOC + 15 help-text updates.
- ~50 application-layer data-class fields under `aggregation/`, `calculations/`, `workflow/`, `modelos/`. Each gains the new type annotation. Pydantic roundtrip tests verify JSON encode/decode preserves the original string verbatim. Estimated 2-3 commits, ~80 LOC + new roundtrip-discipline tests.
- One new module entry-point at `src/aeat/core/_period.py` exporting `RegistryPeriodCode`, `accepted_period_codes`, `accepted_period_patterns`. ~50 LOC.

### Migration order

1. Land `RegistryPeriodCode` + validator + tests at `src/aeat/core/_period.py`. Standalone commit; no consumers yet.
2. Migrate CLI sites first (α scope). Each site picks up the new type; `--help` text updated; CLI tests assert the parse-failure error message lists the accepted set.
3. Migrate application-layer data-class fields (β scope). Roundtrip tests per `aeat-roundtrip-discipline` confirm encrypted-envelope persistence preserves the string verbatim and the validator re-runs on deserialise.

### Regression-test gate

- New test: every existing modelo's registry TOML must declare a `period_selector` whose codes pass `_validate_period_against_registry`. This is a structural ratchet — if a future modelo authors a new period vocabulary without updating the validator, the gate refuses the registry-load.
- New test: anti-tautology — mutate a registered period code on a CalculationRevision fixture to a non-member value, assert the persistence roundtrip refuses.

### Operator surface

- CLI parse failure on `--period BOGUS` now produces an error message listing every accepted code AND the accepted patterns (`EVENT-N` where N is an integer). Per `aeat-architecture-boundaries`: "the refusal MUST list the accepted set in the error message — never a bare 'value invalid' without options".
- `--help` text for each `--period` site includes the accepted-set list scoped to the command's modelo (M100 sees `1T-4T, 0A, 01-12`; M369 sees `EXT-1T..EXT-4T`; M308 sees `AD-HOC`; etc.). Per-modelo scoping is documentation, not validation — the validator accepts the full union regardless of which command invoked it.

### Future-proofing

- Adding a new sub-vocabulary (e.g. an IRNR retención period scheme) requires editing only the validator + the `accepted_period_*` accessors. No CLI argument retyping. No data-class field changes. The structural ratchet test catches any registry TOML that uses the new vocabulary before the validator knows about it.
- Per `aeat-architecture-boundaries`'s typed-enum mandate, this ADR documents the explicit exception: period codes are NOT typed as a closed StrEnum at the CLI surface, BECAUSE the union includes a regex member (`EVENT-N`) that cannot be enumerated. The escape-clause invocation is documented here so future audits don't re-flag the deviation.

## Out of scope

- The β-scope ~50-site migration itself. This ADR adjudicates the type shape; the migration lands under a separate plan Step (or task) once D1-D2 ship.
- Period-vocabulary TOML registry (per D5). Future-hardening direction; not Phase 1.
- Per-modelo period-applicability validation (i.e. "M100 cannot file with period EXT-1T"). That's the existing modelo-revision applicability gate, not this ADR's scope.
- Harmonising M308/M309/M360 to the `AD-HOC` literal (per D4). FU when prioritised.

## Sibling impact assessment

The same closed-set-vs-union tension surfaces in two other axes:

- **CCAA code**: closed StrEnum `CCAA` with all autonomous communities. No union problem — every CCAA is enumerable. Stays as StrEnum.
- **Modelo identifier**: closed set of known modelos (M100, M130, M131, M200, M210, M303, M349, ...). Stays as StrEnum-or-Literal.
- **`tipo_renta`** (M210 IRNR): open string today (see the m210-irnr-full-engine ADR). Not a true union; just an extensible enum where the registry adds members. Different shape from period codes; no implication for this ADR.

The period axis is unique in carrying a regex-member (`EVENT-N`). No other CLI axis I'm aware of needs the Candidate 3 shape; CCAA and modelo identifiers stay as StrEnum per `aeat-architecture-boundaries`.

## Decision summary

ACCEPT Candidate 3. `RegistryPeriodCode = Annotated[str, BeforeValidator(_validate_period_against_registry)]`. Single source of truth. CLI `--help` carries the accepted set. CLI parse failure routes the accepted set through the validator's error message. Roundtrip-clean (underlying type is `str`). Future extension is one regex / one literal added to the validator. Candidate 2 (discriminated union) reserved for if-and-when a runtime needs to dispatch on period-kind. Candidate 1 (wider StrEnum) rejected because `EVENT-N` is unbounded.
