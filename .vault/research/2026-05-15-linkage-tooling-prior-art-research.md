---
tags:
  - '#research'
  - '#linkage-tooling-prior-art'
date: '2026-05-15'
modified: '2026-05-15'
related:
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
---



# `linkage-tooling-prior-art` research: `Linkage tooling and constraint-enforcement prior art`

This document grounds the AEAT linkage problem in published prior art and
tooling, so the upcoming verification phase can adopt existing solutions
rather than building from scratch. The audit record (the sibling research
document) identified 21 convergent findings F1–F21 describing a codebase
where typed information degrades at every cross-domain edge. Each section
below answers: what is this, who maintains it, what specifically does it
solve from the F-list, and what is the integration cost.

Sources were fetched in-session from authoritative project documentation and
primary essays. Every claim is traceable to those fetched sources.

---

## Part A — Python static-analysis and architectural-constraint tooling

### import-linter

**What it is.** `import-linter` (https://import-linter.readthedocs.io) is
a command-line tool and pre-commit hook that enforces architectural contracts
over a Python project's import graph. It analyses all imports in a package
and compares them against a declarative ruleset. The tool is actively
maintained; documentation references versions from 1.x through 2.9, with
the v2.x series current as of 2025. Five contract types are supported:
`forbidden`, `protected`, `layers`, `independence`, and `acyclic siblings`.
Configuration lives in `.importlinter` (INI) or `pyproject.toml`.

**Relevance to F-list.** The most direct target is F7: the cross-package
import at `domain/calculations/registry/_bindings.py` pulling from
`domain/renta`. A `forbidden` contract makes this a CI failure immediately:

```ini
[importlinter]
root_package = aeat

[importlinter:contract:no-renta-in-registry]
name = Registry must not import from renta domain
type = forbidden
source_modules =
    aeat.domain.calculations.registry
forbidden_modules =
    aeat.domain.renta
```

A `layers` contract can encode the hexagonal direction (domain → adapters
forbidden, core → domain permitted) and covers F7's broader class of
boundary violations. `ignore_imports` allows surgical exceptions where a
temporary coupling must remain while callers are migrated.

**Integration cost.** Runs as `lint-imports` on the CLI or as a pre-commit
hook. Pure Python, no native deps. Compatible with Python 3.8+. Adopted in
Django, Mercurial, and other large projects. Zero runtime impact. The
`.importlinter` config file is the only artefact; it can be generated
incrementally — start with `forbidden` contracts for the known violations
and expand to full layered architecture as the codebase converges.

---

### tach

**What it is.** `tach` (https://github.com/tach-org/tach) is a Rust-backed
Python tool that enforces module boundaries and public interfaces. It flags
imports that violate declared `depends_on` constraints in `tach.toml`, and
can also enforce that cross-module calls go through declared public
interfaces rather than internal symbols. Initialisation is interactive
(`tach init`). As of search results reviewed in this session, the tool was
noted as no longer actively maintained after mid-2025; a community fork
`dtach` exists but its future is uncertain.

**Relevance to F-list.** Like `import-linter`, `tach` addresses F7. Its
public-interface enforcement goes further: it would flag calls into
`domain/calculations/registry` internal modules from adapters, covering the
broader set of layering violations. The `depends_on` model also makes
implicit coupling explicit — every package must declare what it depends on,
exposing accidental transitive wiring.

**Integration cost.** CLI lint step, no runtime overhead. However, the
maintenance uncertainty is a significant adoption risk. Recommend using
`import-linter` as the primary boundary tool and evaluating `tach` only if
the interface-enforcement feature is specifically needed, given `tach`'s
status.

---

### deptry

**What it is.** `deptry` (https://deptry.com) is a command-line tool that
scans Python source files for import usage and compares against declared
dependencies in `pyproject.toml` or requirements files. It detects unused
dependencies, missing direct declarations, and transitive dependencies
imported without being declared. It supports uv, Poetry, PDM, and PEP 621.
The tool is actively maintained and installable as a pre-commit hook.

**Relevance to F-list.** Indirectly relevant to F7 and the broader
source-hygiene concerns. `deptry` would flag any package pulled in
transitively via the `domain/renta` cross-package import that is not
declared as a direct dependency, making the hidden coupling visible in CI.

**Integration cost.** `deptry check .` or `uv run deptry check .`. JSON
report output for CI annotation. Pre-commit integration available. Low
adoption friction.

---

### grimp

**What it is.** `grimp` (https://github.com/python-grimp/grimp) builds a
queryable `ImportGraph` of all imports within one or more Python packages.
It exposes an API for querying reachability, layers, and closure violations.
Version 3.14 is documented as of this session. `pydeps` (https://github.com/thebjorn/pydeps)
is a complementary visualisation tool that renders the dependency graph as
an image and highlights cycles in blue.

**Relevance to F-list.** Both tools are discovery instruments rather than
enforcement tools. `grimp` is the underlying engine that `import-linter`
uses. Running `grimp` directly during investigation lets a developer ask
"what does `domain/calculations/registry` actually import, transitively?"
before writing contracts. `pydeps` makes cycle detection visual, useful for
identifying the acyclic-sibling violations that span multiple inventory rows.

**Integration cost.** `grimp` is a Python library; `pydeps` requires
Graphviz. Neither is a CI gate by itself — they are investigation and
documentation aids.

---

### semgrep

**What it is.** Semgrep (https://semgrep.dev) is a lightweight,
pattern-based static analyser supporting 30+ languages including Python.
Rules are YAML files with a pattern that looks like source code. It ships
with a Community Edition and a large registry of community rules. The Fall
2025 Community Edition improved scan performance by 3x and added Windows
support. Rules compose with `patterns` (AND), `pattern-either` (OR), and
the `...` ellipsis operator for matching variable-arity constructs.

**Relevance to F-list.** Semgrep is the right tool for encoding the Issue
Taxonomy directly as CI rules. Examples of what can be encoded:

- F1 (stringly-typed cross-boundary values): match `Mapping[str, Any]` or
  `dict[str, Decimal]` in `domain/` type annotations.
- F3 (untyped selector): match `selector: str` field declarations in
  `DataBindingDefinition`-related models.
- F5 (deferred existence checks): match calls to `validate_registry` inside
  method bodies that are not `__init__` or `model_post_init`, flagging
  deferred validation patterns.

A minimal rule for the stringly-typed envelope pattern:

```yaml
rules:
  - id: no-mapping-str-any-in-domain
    languages: [python]
    message: >
      Bare Mapping[str, Any] or dict[str, Decimal] in domain/ bypasses typed
      referential integrity. Use a typed observation model instead.
    severity: ERROR
    patterns:
      - pattern: |
          $FIELD: Mapping[str, $T]
      - pattern-inside: |
          class $MODEL(BaseModel):
            ...
```

**Integration cost.** `semgrep scan --config rules/` as a CI step or
pre-commit hook. Rules live in a project-local YAML directory. No build
system changes. Community Edition is free and open-source. Semgrep does not
require the codebase to compile, making it useful before other fixes land.

---

### ruff (custom rules)

**What it is.** `ruff` (https://docs.astral.sh/ruff) is the primary linter
and formatter for the project. However, as confirmed from the GitHub
discussion fetched in this session (#8409), ruff does **not** currently
support a plugin system for custom rules. The maintainers acknowledge the
limitation and are tracking a future plugin design, but no timeline is
committed.

**Relevance to F-list.** Not applicable for project-specific rules at this
time. Ruff's built-in rules cover general Python hygiene (import ordering,
type annotation style, etc.) but cannot encode domain-specific invariants
such as "no `Mapping[str, Any]` in `domain/`." Semgrep is the correct
replacement for that use case.

---

### libcst — codemods for typed migration

**What it is.** LibCST (https://libcst.readthedocs.io), maintained by Meta
(Instagram), parses Python 3.0–3.14 source as a concrete syntax tree
preserving all formatting, comments, and whitespace. The `codemod` framework
allows writing `CodemodCommand` subclasses that transform the CST and
regenerate source. It is actively maintained with PyPI releases current
through 2025.

**Relevance to F-list.** F1 and the actionable suggestion #2 from the audit
(replacing `Mapping[str, Decimal]` with a typed observation) requires
touching potentially hundreds of sites. A LibCST codemod can mechanically
rewrite `casilla_values: Mapping[str, Decimal]` to a typed field across all
models, and rewrite construction sites from dict literals to the new model
constructor. This is preferable to manual migration because it is
deterministic, reviewable as a diff, and can be re-run as the typed model
evolves.

**Integration cost.** Development cost to write the codemod is moderate
(a few hundred lines of CST visitor code). The run is one-shot with human
review of the diff. LibCST is a pure Python library; no native deps. Not
a CI gate — a migration tool.

---

### mypy and pyright

**What they are.** `mypy` and `pyright` are the two dominant Python static
type checkers. Pydantic ships an official mypy plugin (`pydantic.mypy`) that
teaches mypy about model validators, field aliases, and discriminated union
narrowing. Pyright is maintained by Microsoft and tends to be stricter on
generic narrowing and discriminated union exhaustiveness.

**Relevance to F-list.** Once discriminated unions (F3) and typed envelopes
(F1) are in place, mypy/pyright become the ongoing referential-integrity
gate. Specifically: if `DataBindingDefinition.selector` becomes a
discriminated union, mypy will flag any match-arm that does not handle a
branch, making missing-case errors compile-time failures rather than runtime
surprises. Pyright's stricter narrowing catches cases mypy misses in
`match` statements.

**Integration cost.** Already in the project toolchain. The incremental
cost is enabling the pydantic mypy plugin in `mypy.ini` and tightening
`--strict` or `--disallow-any-generics` flags as typed envelopes replace
bare dicts.

---

## Part B — Pydantic ecosystem patterns

### Discriminated unions

Pydantic v2's `Field(discriminator=...)` mechanism (https://docs.pydantic.dev/latest/concepts/unions/)
allows a union of models to be resolved by inspecting a single `Literal`-typed
field. This is directly applicable to F3 (`DataBindingDefinition.selector`
and `source_revision_selector`). The resolution is O(1) (hash lookup rather
than sequential try), and validation errors are precise: the validator
reports which branch was selected and which field was missing within that
branch.

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class RegistrySourceSelector(BaseModel):
    source: Literal['registry']
    casilla_id: str

class FilingSourceSelector(BaseModel):
    source: Literal['filing']
    modelo_id: str
    periodo: str

DataBindingSelector = Annotated[
    Union[RegistrySourceSelector, FilingSourceSelector],
    Field(discriminator='source')
]
```

Validated at registry load, this makes it impossible to construct a binding
with an unrecognised `source` literal. Nested discriminators (e.g.
discriminating first on `source` then on `variant`) are supported via
`Annotated` nesting, as shown in the pydantic docs fetched in this session.

---

### `model_validator(mode="after")` for cross-field invariants

`model_validator(mode="after")` runs after all fields have been individually
validated. It receives the fully constructed model instance. This is the
correct hook for existence checks that require multiple fields (F5): for
example, verifying that a `formula_id` referenced in a binding definition
actually exists in the registry snapshot. Load-time failure replaces the
deferred `validate_registry` pattern.

---

### `RootModel` and `TypeAdapter`

`RootModel[T]` wraps a single value of type `T` in a pydantic model,
enabling schema export and validation of bare collections. `TypeAdapter[T]`
validates arbitrary types without a model class. Both are useful for
constructing typed cross-boundary envelopes from existing `Mapping[str, Decimal]`
sites without redesigning the entire model graph at once.

---

### msgspec

`msgspec` (https://jcristharif.com/msgspec) provides typed `Struct` records
with encode/decode performance 4–24x faster than pydantic v2 for equivalent
structures, as benchmarked and published by the project's author. Its `Struct`
type is immutable-by-default and supports `gc=False` for allocation-critical
paths. However, it does not support `model_validator`, discriminated unions
with `Field(discriminator=...)`, or the pydantic mypy plugin. For the
cross-boundary envelope problem (F1, F6), msgspec `Struct` is appropriate
for high-frequency value-passing (casilla value bundles passed between the
calculation engine and persistence) but not for the registry snapshot models
where complex cross-field validation is needed.

---

## Part C — Cross-schema referential integrity

### taplo (TOML schema validation)

**What it is.** Taplo (https://taplo.tamasfe.dev) is a TOML toolkit with a
CLI validator, LSP server, and formatter. Its `check` subcommand validates
TOML files against JSON Schema Draft 4:

```
taplo check --schema https://example.com/registro-formula.schema.json formulas.toml
```

Schema catalogs allow automatic matching of schemas to TOML files by
filename pattern, eliminating per-file `--schema` flags. `tombi`
(https://tombi-toml.github.io/tombi) is a newer alternative inspired by
Taplo that extends JSON Schema with `x-tombi-*` annotations and supports
per-key schema application inside `pyproject.toml`.

**Relevance to F-list.** The AEAT registry is declared as TOML. If each
TOML schema (formulas, bindings, relations, legal refs) exports a JSON
Schema, `taplo check` can verify referential integrity at the TOML layer
before any Python is executed. A formula TOML referencing a casilla that
does not exist in the casilla schema becomes a schema violation caught in
CI. This directly addresses the load-time validation deferral (F2) at the
source file level rather than the Python level.

**Integration cost.** `taplo check` runs as a pre-commit hook. JSON schemas
must be authored or exported from pydantic models via `model.model_json_schema()`.
One-time setup per schema type, then CI-enforced.

---

### `validate-pyproject`

`validate-pyproject` (https://github.com/abravalheri/validate-pyproject)
validates `pyproject.toml` against PEP-defined JSON schemas using
`fastjsonschema`. It supports plugin-supplied schemas for `[tool.*]`
sections. If the AEAT registry configuration lives under a `[tool.aeat.*]`
section, a `validate-pyproject` plugin can enforce schema constraints as
part of the existing Python toolchain. Less powerful than `taplo` for
arbitrary TOML files but directly integrated with standard Python packaging
tooling.

---

## Part D — Tax and regulatory rules-engine modelling

### OpenFisca

**What it is.** OpenFisca (https://openfisca.org) is an open-source
rules-as-code engine used by France, Tunisia, New Zealand, and others to
model tax-and-benefit legislation. It is actively maintained by the OpenFisca
Core team. The Python API centres on three primitives:

- `Variable`: a typed quantity associated with an entity (person,
  household) and a `definition_period` (`MONTH`, `YEAR`, `ETERNITY`).
  Each Variable carries a `reference` field — a list of legislative
  reference URLs (analogous to our `legal_refs`).
- `formula`: a method on `Variable` that retrieves other variables using
  `entity('variable_name', period)`. This explicit period-parameterised
  call is the mechanism by which cross-variable dependencies are declared
  and traced.
- `Reform`: a class with an `apply()` method that substitutes variables
  or modifies parameter values for a given period, representing a change
  in the law.

```python
class income_tax(Variable):
    value_type = float
    entity = Person
    definition_period = YEAR
    label = "Annual income tax"
    reference = ["https://boe.es/buscar/act.php?id=BOE-A-2006-20764"]

    def formula(person, period, parameters):
        salary = person('salary', period)
        rate = parameters(period).taxes.income.rate
        return salary * rate
```

**Relevance to F-list.** OpenFisca is the closest published prior art to
the AEAT registry model. Its `reference` field is a direct analogue of
`legal_refs` — the key difference is that OpenFisca attaches references
at the variable class level (loaded unconditionally) whereas the AEAT
registry attaches them to formula entries that are then discarded before
persistence (F6, F14). OpenFisca's period-parameterised cross-variable call
prevents the implicit period collapse that causes F12. The `Reform` mechanism
provides a typed, auditable path for implementing the multi-period reopen
scenario (F-series around `source_revision_selector`). The `definition_period`
constraint is structurally analogous to our cross-period dependency problem.

**Integration cost.** OpenFisca is a full framework, not a lint tool. The
relevant adoption is pattern adoption: the `reference` list convention, the
explicit period parameter in every formula call, and the `Reform` class as
the unit of law change. These patterns can be adopted in the AEAT registry
TOML/Python layer without importing OpenFisca.

---

### Tax-Calculator (PSL)

Tax-Calculator (https://github.com/PSLmodels/Tax-Calculator) is a US federal
income-tax microsimulation model from the Policy Simulation Library. It
models tax calculation as a deterministic function: inputs are individual
characteristics, output is tax liability. Cross-variable references are
encoded as flat column names in a pandas DataFrame — typed only weakly. It
does not offer the typed cross-reference or legal grounding primitives that
OpenFisca provides. Noted here for completeness; OpenFisca is the better
prior-art reference for the AEAT pattern.

---

### OPA / Rego and DMN

Open Policy Agent (https://www.openpolicyagent.org) and its Rego language
are used in regulated systems (finance, healthcare) for policy-as-code. Rego
rules can reference other rules by name, and the OPA evaluator traces the
dependency graph at evaluation time. However, Rego's datalog-like semantics
do not map well to the imperative calculation graph the AEAT registry uses.
DMN (Decision Model Notation) is an OMG standard for tabular decision logic
with explicit input/output typing; it enforces referential integrity between
decision tables at the model level. Both are cited as evidence that the
pattern of typed, traceable cross-rule references is an established practice
in regulated software, not an exotic requirement.

---

## Part E — Type-driven design literature

### "Parse, Don't Validate" — Alexis King (2019)

The essay (https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)
argues that validation and parsing differ in information preservation:
validation answers a boolean and discards what it learned; parsing answers
a more precise type that encodes the constraint permanently. The essay states:
"the difference between validation and parsing lies almost entirely in how
information is preserved."

**Relevance to F-list.** F2 is a textbook case. The AEAT registry loads
TOML, constructs Python objects, but defers existence checks to explicit
`validate_registry` calls. The essay's prescription — accept broad types at
the boundary, parse to precise types immediately, pass only precise types
inward — maps directly to actionable suggestion #3 in the audit: fire
existence checks unconditionally on snapshot construction. Every field that
carries a `formula_id`, `casilla_id`, or `legal_ref` URL should become a
`NewType` or `Annotated` type that can only be constructed by a parsing step
that has already verified existence.

---

### "From Primitive Obsession to Domain Modelling" — Mark Seemann (2015)

The essay (https://blog.ploeh.dk/2015/01/19/from-primitive-obsession-to-domain-modelling/)
argues that replacing primitive types (`str`, `int`) with domain value
objects eliminates an entire category of runtime errors. The root problem,
as Seemann states, is that "just because you can represent a value as a
string, it doesn't mean you always should."

**Relevance to F-list.** F1 is a structural case of primitive obsession:
`Mapping[str, Decimal]` uses `str` to key casilla identifiers when a
`CasillaId` newtype would make the key domain-meaningful and type-checked.
The same pattern recurs for `ModeloId`, `FormulaId`, `FiscalYear`, and
`Periodo`. Adopting newtypes closes the class of errors where a raw string
from one domain is passed as a key in another domain's mapping.

---

### Anemic Domain Model — Fowler (2003) and subsequent critique

The anemic domain model anti-pattern (https://en.wikipedia.org/wiki/Anemic_domain_model),
described by Martin Fowler, occurs when domain objects carry data but no
behaviour — validation and calculation logic lives in separate service
objects. The critique is that invariants cannot be guaranteed because
mutation logic is scattered across the codebase.

**Relevance to F-list.** `RegistryFilingObservation` and
`RegistryCalculationResult` are pure-data envelopes with no invariant
enforcement. Any caller can construct them with mismatched `casilla_values`
keys because the envelope does not know which casillas are valid for a given
modelo. This is the anemic model pattern applied to the cross-boundary
envelope problem (F1). The remedy — a rich envelope that validates its own
keys against a schema at construction time — directly maps to pydantic's
`model_validator` pattern described in Part B.

---

## Part F — Adjacent published critiques

### "Stringly-typed APIs"

The stringly-typed critique describes APIs that pass domain concepts as raw
strings, relying on convention rather than type to signal meaning. Searches
conducted in this session locate the critique in the context of "make illegal
states unrepresentable" literature. In Python, the prescribed remedy is
`NewType` or `Annotated` wrappers that preserve the runtime representation
but make the type checker treat `CasillaId` and `ModeloId` as distinct types.
A function accepting `casilla_id: CasillaId` cannot silently receive a
`ModeloId` string even though both are `str` at runtime.

**Relevance to F-list.** F1 is the primary target. The AEAT CLI surfaces
(inventory rows covering `--casilla`, `--modelo`, `--periodo`) currently
accept raw strings. Introducing `NewType` at the CLI parse boundary and
threading it into all internal APIs closes the stringly-typed surface at
every layer simultaneously.

---

## Recommended adoption order

The following six tools/patterns are ranked by `coverage_increase / integration_cost`.
Coverage is measured against the 102-row inventory and the 21 F-findings.

**1. Pydantic discriminated unions + `model_validator`**
Coverage: closes F3 (untyped selector), F5 (deferred existence checks),
and inventory rows R-12, R-31, R-67 (binding selector sites). Integration
cost: low — pure Python, within the existing pydantic v2 dependency.
Mechanical check written: `DataBindingDefinition.selector` becomes a
discriminated union; `model_validator(mode="after")` fires existence checks
on snapshot construction; mypy/pyright flag missing match arms.

**2. semgrep rules targeting the Issue Taxonomy**
Coverage: closes F1 (stringly-typed envelopes), F3 (bare selector fields),
and provides ongoing detection for regressions across all 102 inventory rows.
Integration cost: low — YAML files in a `rules/` directory, one CI step.
Mechanical check written: pattern rules for `Mapping[str, $T]` in `domain/`
models; `selector: str` field declarations; `validate_registry` calls outside
`__init__`.

**3. import-linter forbidden + layers contracts**
Coverage: closes F7 (cross-package boundary violation at
`domain/calculations/registry/_bindings.py`). Prevents recurrence across
the full boundary surface. Integration cost: very low — one `.importlinter`
file, pre-commit hook. Mechanical check written: `forbidden` contract for
`domain/calculations/registry -> domain/renta`; `layers` contract encoding
the hexagonal direction.

**4. taplo check with JSON Schema exported from pydantic models**
Coverage: closes F2 (deferred validation) at the TOML source layer, before
Python execution. Integration cost: moderate — requires authoring or
exporting JSON schemas from registry pydantic models, then wiring `taplo
check` into CI. Mechanical check written: `taplo check --schema
formula.schema.json formulas/*.toml` flags dangling `casilla_id` or
`formula_id` references at the file level.

**5. LibCST codemod for typed envelope migration**
Coverage: enables closing F1 mechanically across all 102 rows by rewriting
`Mapping[str, Decimal]` sites to the typed observation model.  Integration
cost: moderate one-time development (codemod authoring), zero ongoing cost.
Not a CI gate — a migration accelerant. Mechanical change written:
`ReplaceStringMappingCodemod` rewrites field declarations and construction
sites; the resulting diff is reviewed once and then enforced by semgrep rule
#1 above.

**6. OpenFisca patterns (reference list, period-parameterised formula calls)**
Coverage: closes F6 and F14 (legal ref erasure before persistence), F12
(period collapse). Integration cost: zero external dependency — pattern
adoption only. Mechanical check written: add `reference: list[LegalRef]`
to every formula class in the registry; require that every cross-formula
call passes an explicit period argument; write a semgrep rule that flags
formula calls without a period parameter.
