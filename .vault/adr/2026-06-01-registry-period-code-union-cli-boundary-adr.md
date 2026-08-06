---
tags:
  - '#adr'
  - '#registry-period-code-union'
date: '2026-06-01'
modified: '2026-08-05'
body_hash: 'sha256:4274de2543f2be8a565880bdf9a1ed8d2325f0994e8741702efc47820b7fdda4'
related:
  - "[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-05-22-schema-hardening-adr]]"
  - '[[2026-06-04-registry-period-code-union-research]]'
---

# `registry-period-code-union` adr: CLI-boundary period-code typing — closed-set hint vs registry-driven refusal | (**status:** `accepted`)

## Authoring note

Authored via the Write tool following the canonical frontmatter shape — the architect's bash session has the same shell-quoting corruption flagged in the M303 dual-keying ADR (`2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr.md`). The `vault add adr` CLI invocation returns EOF immediately. The commit-bot validates via `vault check all` post-commit; the gate is identical regardless of scaffold path.

## Problem statement

The CLI exposes ~15 `--period` sites (per the S801 α-survey at commit `b9ff9dc09`) that span multi-modelo contexts. The legitimate value space at the CLI boundary is the UNION of four sub-vocabularies:

- **StandardPeriodCode** (closed StrEnum at `src/cadrumo/core/_period.py`): `1T-4T`, `1P-4P`, `0A`, `01-12`. 21 members. Covers the dominant case for M100/M130/M131/M200/M303 quarterly + monthly periods.
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

### D2 — Define `RegistryPeriodCode` at `src/cadrumo/core/_period.py`

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

The validator is Python today (no period-vocabulary TOML). If a future ADR establishes a period-code registry under `src/cadrumo/_data/registry/aeat/period_codes/` (analogous to `_data/registry/aeat/legal/`), the validator becomes a thin lookup against that registry, and the regex shapes for `EXT-` / `EVENT-` become declared patterns in TOML. The validator's interface stays the same; only its data source changes. This preserves the registry-authority-flow direction of travel.

## Consequences

### Affected surfaces

- ~15 CLI `--period` sites. Each receives the new type annotation. Per-site `--help` text gets an explicit accepted-set list. Estimated 1 commit, ~30 LOC + 15 help-text updates.
- ~50 application-layer data-class fields under `aggregation/`, `calculations/`, `workflow/`, `modelos/`. Each gains the new type annotation. Pydantic roundtrip tests verify JSON encode/decode preserves the original string verbatim. Estimated 2-3 commits, ~80 LOC + new roundtrip-discipline tests.
- One new module entry-point at `src/cadrumo/core/_period.py` exporting `RegistryPeriodCode`, `accepted_period_codes`, `accepted_period_patterns`. ~50 LOC.

### Migration order

1. Land `RegistryPeriodCode` + validator + tests at `src/cadrumo/core/_period.py`. Standalone commit; no consumers yet.
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

## Amendment (2026-08-05): the union is five sub-vocabularies, and one validator cannot serve two boundaries

Two statements this record makes about the accepted value space are now false, and the
falsehood is a live regression rather than a documentation lag. Everything below was
measured at HEAD on 2026-08-05, not inferred.

### What happened

Commit `972e8636ff` ("fix(core): define the registry selector period code its export
already names", 2026-08-01) repaired a genuine break: `cadrumo.core` exported
`RegistrySelectorPeriodCode` while the name was undefined, so `import cadrumo.core`
failed on a clean checkout. The repair was necessary and its admission of the
administrative tokens was necessary too — this amendment does **not** call for a revert.
Three registry declarations that all predate the commit require those tokens at the
registry coordinate:

- `_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/revision.toml:4` —
  `periods = ["alta", "modificacion", "baja"]`
- `_data/registry/aeat/modelos/145/revisions/2012-01-31-y-siguientes/revision.toml:3` —
  `periods = ["comunicacion", "variacion"]`
- `_data/registry/aeat/modelos/210/revisions/2025/revision.toml:8` —
  `periods = ["EVENT-N", "0A"]`

`PeriodSelector.periods` had been typed `RegistrySelectorPeriodCode` at commit
`fa16c86f66` (it was a bare `tuple[str, ...]` before that), so once the alias was
defined, the registry could not load unless the validator admitted those tokens. The
defect is not the admission. The defect is that the admission was made in
`_validate_period_against_registry` — the validator that **also** backs `Period.code`
(`core/_period.py:231`). One validator was serving two boundaries with genuinely
different value spaces, and widening it for the registry coordinate silently widened the
typed filing period.

### The regression, measured

`Period.from_year_and_code(2025, "alta")` now returns `Period(filing_year=2025,
code='ALTA')`. Before the widening it raised `PeriodError`. That refusal was
load-bearing: `_resolve_year_period` (`entrypoints/cli/_modelo.py:312-331`) catches
`PeriodError` and only then builds the instructive refusal that names the modelo and
enumerates its declared tokens. With no exception raised, the whole cascade is dead.
Confirmed directly:

    _resolve_year_period(2025, "alta",         modelo="036") -> Period(2025, 'ALTA')
    _resolve_year_period(2025, "comunicacion", modelo="036") -> Period(2025, 'COMUNICACION')
    _resolve_year_period(2025, "EVENT-N",      modelo="036") -> Period(2025, 'EVENT-N')
    _resolve_year_period(2025, "bogus",        modelo="036") -> BadParameter (still correct)

So `aeat app modelo work create --modelo 036 --period alta` accepts a censo registration
event as a filing period. The command still fails, but downstream and generically: the
JSON envelope carries `ERROR_MODELOS` and no longer carries the `--period '<token>'`
parse-boundary refusal. That is a direct breach of `aeat-architecture-boundaries` — "the
refusal MUST list the accepted set in the error message — never a bare 'value invalid'
without options". The instructive surface was replaced by a late generic one.
`test_work_create_rejects_censo_tokens_as_non_filing_periods` fails on all three
parametrised cases (`entrypoints/cli/tests/test_modelo_discovery_defects.py:225`); the
undeclared-token and quarterly-token siblings still pass, isolating the fault to declared
administrative tokens rather than to the validator in general.

For precision, one thing this regression is **not**: it is not a silent
under-declaration. `Period(code='ALTA').has_date_span()` returns `False` and
`.contains(date)` raises `PeriodError` with an instructive message, so an administrative
period that reaches the aggregation boundary fails late and loudly rather than silently
folding a wrong span. `no-silent-under-declaration` is therefore not breached today; its
relevance here is prospective, and it is the reason the fix must restore a type-level
refusal rather than rely on the downstream `contains()` guard as the safety net.

### Scope corrections to this record's own text

**The set is five tokens, not three.** `_ADMINISTRATIVE_PERIOD_SET`
(`core/_period.py:80`) carries `ALTA`, `MODIFICACION`, `BAJA`, `COMUNICACION`,
`VARIACION`. Only M036's three appear in the failing test because they are the ones M036
declares; M145 supplies the other two. `accepted_period_patterns()`
(`core/_period.py:132`) under-reports the set as "Administrative (ALTA, MODIFICACION,
BAJA)" while `accepted_period_codes()` returns all five — the operator-facing pattern
listing and the machine-readable code listing already disagree.

**A second widening rode the same commit, unrelated to the administrative tokens.**
`_EVENT_PERIOD_RE` went from `^EVENT-\d+$` to `^EVENT-(?:N|\d+)$`, admitting the literal
placeholder `EVENT-N`. That token is M210's declared *selector* string — a pattern
placeholder standing for "an event number", not an event number. `Period(code='EVENT-N')`
is therefore a filing period whose code is a documentation placeholder. This is the same
defect class as the administrative leak (registry-selector vocabulary reaching the typed
filing boundary), it arrived by the same conflation, and any fix scoped to the
administrative branch alone will leave it standing.

**The record's Problem statement and Future-proofing sections are corrected** to read
five sub-vocabularies at the registry coordinate: standard, extended OSS/IOSS, ad-hoc,
event-driven, and administrative (censo/comunicación registration events). The claim in
Operator surface that "the validator accepts the full union regardless of which command
invoked it" is superseded by A2 below: from this amendment there are two validators, and
which one applies is decided by the boundary, not by the command.

### A1 — The administrative sub-vocabulary is ratified at the registry coordinate

`RegistryPeriodCode` keeps the wide validator, administrative set included. The registry
snapshot coordinate (`RegistrySnapshotRef.period`,
`domain/calculations/registry/_schema_references.py:53`) genuinely addresses M036 and
M145 revisions by their administrative tokens, and `RegistrySelectorPeriodCode`
(`core/_period.py:164`) is unchanged — including its lowercasing of administrative
tokens, which is itself the tell that the code already treats these as a distinct
vocabulary. It applies a different casing rule to them; what it lacked was a different
*type* at the filing boundary.

### A2 — Split the validator: `Period.code` moves to a narrow `FilingPeriodCode`

Introduce `FilingPeriodCode` in `core/_period.py` alongside the existing aliases: the
same `Annotated[str, BeforeValidator(...)]` shape this ADR's D1 adopted, running the
standard / extended / ad-hoc / event-number checks and **never** the administrative
branch, and rejecting the literal `EVENT-N` placeholder while continuing to accept
`EVENT-3`. `Period.code` is retyped to it. This restores the pre-`972e8636ff` refusal and
with it the entire `_resolve_year_period` cascade, contained to one module — no change to
the CLI support modules, the declaración parser, or `RegistrySnapshotRef`.

D1 is not overturned. Candidate 3's shape survives intact; what changes is that the
single alias becomes two, one per boundary. D3 anticipated exactly this pressure —
"if a future need arises to dispatch on period-kind at runtime" — and it has arrived as a
defect rather than as a feature request. The split is the cheap half of D3's migration
path: it separates the vocabularies without paying for the discriminated union.

`ManualCounterpartObservation.operation_period`
(`application/aggregation/_counterpart.py:72`) also moves to `FilingPeriodCode`. An M347
counterpart operation period is a real filing period — every construction site in the
tree passes `0A` — and there is no production writer that could feed it an
administrative token, so it inherits the widening with no compensating benefit. Extend
the existing `test_non_registry_operation_periods_are_refused`
(`application/aggregation/tests/test_counterpart.py:285`) rather than adding a parallel
guard.

**Naming.** `FilingPeriodCode` joins the established `*PeriodCode` family
(`StandardPeriodCode`, `RegistryPeriodCode`, `RegistrySelectorPeriodCode`), which is
English throughout. `aeat-spanish-stem-naming` does not push toward a Spanish stem here:
its trigger is a concept mapping 1:1 to an AEAT surface, and the AEAT noun `periodo`
covers the filing period and the administrative event alike, so it cannot discriminate
the two types this amendment is separating. The rule's generic-vocabulary exception
applies.

### A3 — Acceptance gate: pin both directions, or this returns

The implementing change is not complete without a type-boundary regression test pinning
**both** halves in one place, because the failure mode is a future well-intentioned
widening, exactly as this one arrived:

- `Period.from_year_and_code(year, "alta")` raises `PeriodError`, parametrised across all
  five administrative tokens, not just M036's three.
- `Period.from_year_and_code(year, "EVENT-N")` raises `PeriodError`, while
  `Period.from_year_and_code(year, "EVENT-3")` still builds.
- `RegistrySnapshotRef(period="ALTA")` still validates, and a `PeriodSelector` carrying
  `["alta", "modificacion", "baja"]` and one carrying `["EVENT-N", "0A"]` both still
  validate — the registry must keep loading.
- The M036 CLI refusal is instructive again: `test_work_create_rejects_censo_tokens_as_non_filing_periods`
  passes on all three cases.

A test pinning only the refusal direction would let a later patch re-widen the shared
validator to fix a registry-load failure and re-break the filing boundary; a test pinning
only the registry direction is what we had. Both, adjacent, with the reason stated.

### A4 — The accessors split with the validators

`accepted_period_codes()` / `accepted_period_patterns()` currently describe the wide
union and are consumed by the MCP completion surface
(`entrypoints/mcp/_completions.py:20`), which therefore offers `ALTA`, `BAJA`,
`COMUNICACION`, `MODIFICACION` and `VARIACION` as period completions for filing
arguments. Each accessor gains a filing-scoped counterpart, and every operator-facing
surface that describes *what may be filed* — CLI `--help`, CLI parse-failure text, MCP
completions — consumes the filing-scoped set. Registry-facing surfaces keep the wide set.
Fix the `accepted_period_patterns()` under-report of the administrative set to all five
members in the same change.

### Rejected alternative, and the condition that would revive it

The considered alternative was to leave the validator wide and generalise
`unsupported_local_work_period_refusal`
(`entrypoints/cli/_modelo_cli_support.py:201`) to fire on a case-folded administrative
match independent of `PeriodError`. Rejected — and on stronger grounds than call-site
count.

That helper is gated on `modelo_work_create_refusal_locale_key`, which returns non-`None`
only for `STUB_ONLY_MODELOS` = {151, 210, 600, 620, 650, 660, 714, 721}
(`application/modelo/_work_create_policy.py:36-47`). **M036 is not in that set, and
neither is M145.** The helper returns `None` for M036 today; the refusal the failing test
asserts comes from the `_period_token_error` fallback branch of `_resolve_year_period`,
not from this helper at all. Generalising it would therefore require decoupling it from
the stub-only policy as well — and its message is stub-modelo copy ("this modelo is not
supported for local work"), which is the wrong thing to tell an operator about M036,
whose `describe` and `casillas` surfaces legitimately accept these tokens
(`test_describe_and_casillas_accept_censo_period_tokens` passes and must keep passing).
The alternative is not merely more expensive; it is mis-targeted.

It becomes the right answer under one condition: **if a modelo ever declares a
`period_selector` mixing real filing periods with administrative tokens.** Then a type
that refuses administrative tokens outright is too blunt, because the same modelo needs
both admitted at the CLI and only one admitted as a `Period`, and the discrimination has
to move to a per-modelo registry-driven check. Today no modelo does this: M036 declares
three administrative tokens and nothing else, M145 declares two and nothing else. M210 is
the near miss — `["EVENT-N", "0A"]` mixes a placeholder with a real annual period — and
it is handled by A2's rule that the placeholder is refused while event *numbers* are
admitted. Revisit this decision when a `period_selector` first mixes the vocabularies.

### Consequences

- One module changes for the core fix: `core/_period.py` (new alias, retyped
  `Period.code`, split accessors), plus the one-line retype in
  `application/aggregation/_counterpart.py` and the completion-surface accessor swap in
  `entrypoints/mcp/_completions.py`.
- No change to `RegistrySnapshotRef`, `PeriodSelector`, the previous-filing selectors
  (`domain/calculations/registry/_bindings_previous_filing.py:333`), or any CLI support
  module. The same parse site builds both a `RegistrySnapshotRef` carrying the raw
  `snapshot.period` and a `Period` carrying the normalised one
  (`adapters/inbound/declaracion/_parser.py:295-303`), which is A1 and A2 already
  co-existing correctly in one function.
- **One implementation caveat the implementer must resolve before landing.**
  `_filing_period_for_observation` (`adapters/inbound/declaracion/_parser.py:318-323`)
  normalises only `ALTA` / `MODIFICACION` / `MODIFICACIÓN` / `BAJA` to `AD-HOC`; a
  `comunicacion` or `variacion` selector falls through to line 323 and builds a `Period`
  directly. That call succeeds today only because of the widening, and will raise
  `PeriodError` once `Period.code` narrows. Confirm whether an M145 template can reach
  this parser; if it can, extend the normalisation set to all five administrative tokens
  in the same change. If it cannot, the new refusal is correct and wanted. Do not
  discover this from a red suite.
- `period-filter-single-boundary-authority` is reinforced rather than altered:
  `Period.contains()` remains the single date-boundary authority, and the narrow type
  keeps values that have no date span from reaching it in the first place.
- This record's D4 (harmonise M308/M309/M360 to `AD-HOC`) and D5 (period-vocabulary TOML
  registry) are untouched and still open. D5 gains a data point: when the vocabularies do
  move to TOML, they must move as *two* declared sets, not one.

### Observation, not a ruling

`2026-06-11-period-grammar-standardisation-adr` describes `Period` as carrying
`code: StandardPeriodCode`. That drifted when this ADR's D1 landed `RegistryPeriodCode`
on the field and is not corrected here; it is flagged so the next author of that record
does not read it as the current contract.

### Why no second guard caught this

Revision resolution does not backstop the type boundary, and that is by design.
`select_revision` (`domain/calculations/registry/_temporal.py:80-103`) compares the
requested period against the revision's declared periods **case-insensitively**, with an
in-source rationale: the declaración parser uppercases every period string before it
reaches the registry, producing `ALTA` / `MODIFICACION` / `BAJA` for M036 whose canonical
registry periods are lowercase. So once `Period` admitted `ALTA`, revision resolution
resolved the M036 revision for it and `work create` proceeded. Nothing downstream was
positioned to refuse. This is not a defect in `select_revision` — the deliberate
case-insensitivity serves a real import path — and it must not be tightened as an
alternative fix. It is the reason the refusal has to be restored at the type boundary
where it previously lived.

The same comment block independently confirms A2's ruling on the event placeholder: it
records that the shared matcher "lets symbolic `EVENT-N` selectors cover concrete
`EVENT-1`/`EVENT-2` operator scopes". `EVENT-N` is therefore a *symbolic selector*
covering concrete event numbers, by the registry's own documented intent — which is
exactly why it must never itself become a `Period`. The literal placeholder standing in
for a set of periods cannot also be a member of that set.

The same block carries a standing warning worth restating here, because the split touches
its neighbourhood: the canonical period form is normalised once at the snapshot boundary
(`_build_validated_snapshot` via `registry_period_for_request`), and consumers such as
`relation_source_requirements` compare the snapshot period by exact membership. Do not
drop that snapshot-side normalisation on the strength of the comparison being
case-insensitive.

### Correction (2026-08-05, post-implementation): the Consequences inventory above was incomplete

The split landed as commit `f50de47521` across 8 files. D6 held on contact, including the
`EVENT-N` ruling — the implementation's own docstring now records the token as a selector
placeholder that "addresses a revision rather than names a period", and the regex split
makes `EVENT-\d+` filing-only.

The Consequences list in this amendment was nonetheless wrong, and the reason it needs
correcting is not that it was inaccurate but that it was **read as an inventory**: a
reviewer sized its own scope against it. That makes such a list load-bearing rather than
descriptive, and nothing in a list distinguishes a complete inventory from a partial one
— an incomplete one tells a reader they are finished when they are not. Two surfaces were
missing.

**`domain/calculations/registry/_schema.py:766`.**
`_filing_schedule_period_kind_mismatches` reconciles a `filing_schedules` declaration's
`period_kind` against its `periods` by minting a throwaway
`Period.from_year_and_code(2000, token)` purely to read `.kind`. Registry tokens include
the administrative ones, so narrowing `Period.code` stopped that resolving and broke
registry load outright. Resolved by extracting `registry_period_kind(token)`
(`core/_period.py:300`), which accepts the full registry vocabulary: cadence is a property
of the token alone, so `Period.kind` and the registry-facing check now read one classifier
and neither needs a probe year. This also retires a latent oddity — a consistency check
that had to invent a meaningless year 2000 to ask a question that was never about a year.

**`entrypoints/mcp/_prompts.py`.** A4 named the MCP completion surface but not the
prompt-argument description, which advertised its accepted forms from the same wide
accessor. Both now consume the filing-scoped set, so the five administrative tokens are no
longer offered or advertised as filing periods.

**Why the inventory missed them, which is the part worth carrying forward.** It was built
from two searches: consumers of the type *annotation* (`rg RegistryPeriodCode`) and
construction from an administrative *literal* (`rg` for the token strings). The
`_schema.py` site is neither. It builds a `Period` from a registry-sourced *variable* to
read a *derived property*, and no administrative token appears anywhere in that file. Any
site reading `.kind`, `.has_date_span()`, `.contains()`, or another derived property off a
`Period` built from a registry-sourced token is a consumer of that type's admission set,
and is invisible to both searches. A type-narrowing inventory needs a third sweep:
`Period.from_year_and_code(` / `Period(` with a non-literal argument, each read for where
its argument comes from. Neither of the first two sweeps can find a site whose token is
never spelled out.

### Recorded so it is not re-derived: one narrow-`Period` site is guarded by modelo, not by type

`application/calculations/_iva_compensation_history.py:406` builds a `Period` from stored
observation data — `observation.filing_period or Period.from_year_and_code(
observation.filing_year, observation.period)` — with no vocabulary guard on the stored
token. It is correct today and was rightly left unchanged, but its safety rests on the
M303 refusal six lines earlier at line 400: M303 never carries an administrative token, so
the stored period is always a filing period.

That is a modelo guard doing a type guard's job. It holds exactly as long as that function
stays M303-only, and widening it for an unrelated reason would silently reopen a narrow-
`Period` construction over stored data — with no local signal that anything depended on
the restriction. Not a defect and not a change request; recorded because the next reader
will otherwise re-derive "this is fine" without knowing what it rests on, which is the
same way the original conflation survived review.

### The parser reachability caveat stays open

`f50de47521` did not touch `adapters/inbound/declaracion/_parser.py`. It still normalises
only `ALTA` / `MODIFICACION` / `MODIFICACIÓN` / `BAJA` (line 321), so `comunicacion` and
`variacion` still fall through to the narrow construction at line 323 and will now raise
where they previously built a `Period`. `aeat app registry verify` loading all 73 modelos
is not evidence either way — it does not exercise the PDF parser. The open question is
unchanged: can an M145 template reach this parser? If yes, extend the normalisation set to
all five tokens; if no, the new refusal is correct and wanted.

### On keeping `registry_period_kind` in `core`

Endorsed, on this ground and not the obvious one: one shared cadence classification means
registry ownership would force either a cross-package private import — barred by
`service-imports-via-top-level-reexports` — or a duplicated token-to-cadence map that can
drift from the one `Period.kind` reads. "`PeriodKind` is core-owned" is not the argument,
because it would equally permit the registry keeping its own map beside it.

### Correction (2026-08-05, second post-implementation pass)

Three further items the landed implementation turned. The incomplete-inventory item is
already recorded above and is not repeated here.

**The parser reachability caveat RESOLVES CLEAN — it is settled, not open.** This
supersedes the "stays open" section above. Modelo 145 declares no extraction profiles at
all: its revision directory carries `application_links`, `casillas`, `export_layouts` and
`workbook_parity_refs`, and no `extraction_profiles` anywhere in its tree. The profile
tuple built at `adapters/inbound/declaracion/_parser.py:488-492` is therefore empty for
M145 and the parse raises `DeclaracionParseError` before `_filing_period_for_observation`
is ever reached. The other production caller supplying a period override passes an
already-typed `Period.registry_token`. So `comunicacion` and `variacion` cannot reach the
narrow construction at line 323 in production: the normalisation set correctly stays at
four spellings, and the new refusal is right and unreachable rather than right and
latent-breaking.

**`operation_period`: right conclusion, wrong reasoning, wrong class name.** Two
corrections to A2 above.

The class is `CounterpartObservation` (`application/aggregation/_counterpart.py:48`).
`ManualCounterpartObservation`, as A2 names it, does not exist.

More seriously, A2 justified the move on the ground that "every construction site in the
tree passes `0A`" and "there is no production writer that could feed it an administrative
token". That is wrong in the direction that matters. The model IS the operator boundary,
and says so itself: its docstring records that `aeat app modelo aggregate` validates each
`--counterpart-observation` JSON object directly against it, "so whatever it admits
reaches the preview rollups unchecked". The flag is real
(`entrypoints/cli/_modelo_aggregate_cli.py:57-91`). Before the narrowing an operator could
have typed `"operation_period": "ALTA"` into an M347 rollup preview and had it accepted
into a surface they read as a preview of a real declaration. The correct justification is
therefore the opposite of the one given: this is an operator JSON boundary, the narrowing
protects it, and the refusal now surfaces as a `BadParameter` carrying the pydantic field
message and the flag name — the instructive-refusal property `aeat-architecture-boundaries`
requires.

**The failure mode, recorded because this record named it in advance.** A2 rested on an
absence argument, and this feature's hand-off explicitly flagged absence arguments as the
ones most likely to break against a real implementation. It broke exactly there, and the
falsifying site was not obscure — it was the operator-facing CLI flag. Two things
generalise. An absence claim is refuted by a single site the search shape could not see,
so it is only as strong as the sweep behind it; and "I grepped the construction sites"
structurally cannot see a value that arrives as parsed JSON at runtime, because there is
no construction site to find. That is the same blind spot as the `_schema.py` miss
recorded above — a token never spelled out in source — arrived at by a different route. A
type narrowing justified by absence should name the sweep that produced it, so the next
reader can judge what that sweep was incapable of seeing rather than re-trusting the
conclusion.

**`EVENT-N` framing.** The phrase "documentation placeholder" earlier in this amendment is
superseded by the stronger ground recorded under "Why no second guard caught this" and now
carried in source: the registry's own matcher treats the literal as a symbolic selector
covering the concrete `EVENT-<n>` scopes, so it stands for a SET of periods by documented
intent and cannot be a member of that set. `core-engineer` reached the same correction
independently and named the constant `_SYMBOLIC_EVENT_SELECTOR` (`core/_period.py:91`,
commit `76833ef3d8`). Prefer that framing; a placeholder argument rests on how the token
looks, the selector argument on what the registry declares it to mean.

### Correction (2026-08-05, third pass): "settled" was itself a half-closure

The reachability answer above is right and the framing around it was wrong, in the exact
way this record has already warned about twice.

**The evidence, upgraded from absence to positive.** The section above argued M145 is
unreachable from a directory listing showing no `extraction_profiles` fragment — an
absence argument, and by now this record's least trustworthy shape. The positive form is
available and was measured: exactly twenty modelos ship extraction profiles — 036, 100,
111, 115, 123, 130, 131, 180, 184, 190, 193, 202, 232, 303, 347, 349, 369, 390, 720, 840 —
and M145 is not one of them. The parser requires a resolved profile, so `comunicacion` and
`variacion` cannot reach `_filing_period_for_observation`. Same conclusion, resting on an
enumeration rather than on a hole.

**But closing on reachability was the wrong question to close.** At HEAD on 2026-08-05,
`adapters/inbound/declaracion/_parser.py:321` carries its own inline administrative-token
set — `{"ALTA", "MODIFICACION", "MODIFICACIÓN", "BAJA"}` — while `core/_period.py:86`
declares `_ADMINISTRATIVE_PERIOD_SET` with five members. That is a second authority for
"which tokens are administrative", and the two diverge in **both** directions: the parser
lacks `COMUNICACION` and `VARIACION` entirely, and core lacks every accented spelling the
parser found it necessary to carry for `MODIFICACION`. Neither is a superset of the other,
so neither can simply absorb the other.

**The divergence is invisible for precisely the reason the reachability question closed
clean.** The two members the parser lacks belong to M145, and M145 ships no extraction
profile — so the drift cannot produce a symptom, and nothing will surface it until the day
someone adds a profile for a modelo with an administrative selector. The fact that makes
the gap unreachable is the same fact that hides it. That is the half-closure shape:
answering the surface a finding names is what makes the surface it did not name invisible,
and this record performed it one section ago by writing "settled, not open".

**A constraint on whoever routes this through one authority**, because the obvious repair
regresses a case HEAD currently handles. It is not "delete the local set and ask core":
core's five members are unaccented, and AEAT prints these tokens in correct Spanish — the
parser's inline set carries `MODIFICACIÓN` for exactly that reason, which is HEAD's own
evidence that accented forms arrive. A naive swap to the core membership test would start
refusing a spelling that works today. Folding accents before the membership question is
asked handles it, and it also covers `COMUNICACIÓN` and `VARIACIÓN`, which **neither**
authority handles at HEAD.

This item is tracked and being worked separately. This section states the HEAD position on
2026-08-05 and should not be read as describing its resolution.
