---
tags:
  - '#reference'
  - '#external-tax-definition-engines'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-inventory-research]]'
---



# `external-tax-definition-engines` reference: `Spain-focused AEAT model definition and tax rule architecture`

This reference corrects scope to Spain. It does not use UK or French policy
rules as evidence for Spanish tax content. OpenFisca and PolicyEngine are used
only for their jurisdiction-neutral engine mechanics: external parameter trees,
dated values, schema-like validation, and formula runtimes. Spain-specific
evidence comes from public AEAT sources and Spanish localization code.

## Sources Consulted

- OpenFisca core and country template source trees, for neutral engine mechanics.
- PolicyEngine core source tree, for neutral parameter lookup mechanics.
- Tax-Calculator source tree, for an external current-law policy file pattern.
- OCA `l10n-spain`, especially `l10n_es_aeat`, `l10n_es_aeat_mod303`,
  `l10n_es_aeat_mod390`, and `l10n_es_aeat_mod130`.
- `ruromgar-freelance`, a small Spanish freelancer fiscal app, as a negative
  example of hardcoded modelo services.
- AEAT official model pages for Modelo 303, Modelo 390, and Modelo 130.

## Findings

### Jurisdiction-Neutral Engine Patterns

OpenFisca separates runtime variables from legislative parameters. The country
template initializes a tax benefit system by loading variable source code from a
variables directory and legislation parameters from a parameters directory. In
core, `load_parameter_file` returns a `ParameterNode` for a directory. The node
loader treats child directories and YAML files as tree children, reserves index
files for node metadata, and rejects duplicate child names. `Parameter` stores
dated values and validates instant keys in `YYYY-MM-DD` shape. `ParameterScale`
stores bracketed scale data and returns tax scale objects for an instant.

PolicyEngine core keeps the same useful pattern: `ParameterNode` maintains a
parent/child tree, metadata, a cache, and directory/YAML loading; `Parameter`
stores dated values and supports update periods; `get_parameter` resolves dotted
paths and bracket selectors. The relevant architectural point is not any policy
content, but that lookup and time selection are runtime operations over an
external parameter tree.

Tax-Calculator is less hierarchical, but it has a strong separation between
calculator code and current-law values. `Policy` reads `policy_current_law.json`
through `Parameters`, and the JSON carries parameter metadata, validators,
labels, indexing flags, and yearly values. It also supports external revisions
through policy adjustments. The useful pattern is a validated external policy
data file with calculator code as runtime, not as the owner of legal values.

### Spain-Specific OCA Patterns

OCA `l10n-spain` has a reusable AEAT base module plus one Odoo module per
modelo. The base report class `l10n.es.aeat.report` owns shared period fields,
company/context fields, state transitions, export configuration lookup, and BOE
export dispatch. Modelo-specific modules subclass it: `l10n.es.aeat.mod303.report`
inherits `l10n.es.aeat.report.tax.mapping`, `l10n.es.aeat.mod390.report` inherits
the same mapping base, and `l10n.es.aeat.mod130.report` inherits the base report
directly.

OCA externalizes some modelo structure as data records. Modelo 303 loads
year-scoped CSV files such as `data/2022/aeat.model.export.config.csv`,
`data/2024-10/aeat.model.export.config.line.csv`, and
`data/2026/aeat.model.export.config.line.csv`. The 2026 export config starts on
`2026-01-01` and binds model number `303` to the Odoo report model. The export
line CSV contains fixed fields, field sizes, decimal sizes, alignment, boolean
encoding, and expressions such as object field lookups.

OCA also externalizes tax-to-casilla mapping for VAT models. Modelo 303 and 390
load CSV records for `l10n.es.aeat.map.tax`, `l10n.es.aeat.map.tax.line`, and
tax/account XML id mapping rows. A mapping line contains `field_number`, name,
operation type, field type, sum type, inverse flag, regularization flag, and
tax/account references. Runtime calculation then queries posted accounting
entries in the period, filters by tax/account metadata, and computes amounts
from debit/credit values.

OCA still keeps substantial legal/calculation behavior in Python. Modelo 303
computes totals and result type in `mod303.py` using fixed casilla numbers and
Python logic. Modelo 390 computes many casillas by summing explicit field-number
sets and also derives annual results from Modelo 303 reports. Modelo 130 is the
clearest hardcoding example: constants such as `0.20`, `0.02`, `660.14`, and
logic around casillas are embedded directly in `mod130.py`. That is useful as
evidence of the exact failure mode to avoid, not as a target pattern.

OCA export config uses executable expressions. `aeat.model.export.config.line`
has `expression`, `conditional_expression`, and `repeat_expression` fields; the
BOE export wizard evaluates expressions while building the file. This is
configurable, but it is not auditable enough for this project unless replaced by
a typed, constrained expression model whose operations are enumerated,
validated, cited, and tested.

### Spanish Public Source Signals

AEAT publishes current instructions and technical help for relevant modelos.
The official Modelo 303 page has 2026 instructions. The Modelo 390 technical
help states that generated files must match the record design published in the
AEAT electronic office. Modelo 130 instructions reference official presentation
procedures and legal instruments such as Orden HAP/2194/2013. These pages are
source-of-truth inputs that a registry must cite and validate against.

Search did not identify a mature public OpenFisca Spain country package for
AEAT tax filings. OpenFisca lists a Barcelona package/service context, and
public pages describe Barcelona's social-benefit simulator using OpenFisca, but
that is benefits eligibility work, not AEAT modelo/casilla filing logic.

### Negative Example: Small Freelancer App

`ruromgar-freelance` implements `calculate_modelo_130`,
`calculate_modelo_303`, and `calculate_modelo_390` as direct service functions.
The services contain Spanish descriptions, fixed constants such as 20 percent
and 5 percent, direct invoice/expense aggregation, and no legal citation model.
It is a useful warning: simple service modules are readable, but they collapse
legal truth, data-source selection, formula logic, and presentation-specific
modelo outputs into the same Python surface.

## Takeaways For This Repository

The better direction is a Spain-first central registry where `ModeloDefinition`
is the parent object and each `CasillaDefinition` is a child object with typed
formula, data-source bindings, validity period, legal basis references, AEAT
source references, required tests, and export binding. Python classes should
provide scaffolding, strict loading, validation, typed execution, tracing, and
test harnesses. Python should not own live rates, casilla field lists, thresholds,
or mutable AEAT filing metadata.

Config should be declarative and reviewable. TOML is reasonable for this
repository if each model file is schema-validated, cited, normalized into
immutable runtime objects, and rejected when duplicate modelo/casilla ids,
overlapping validity ranges, missing legal references, missing tests, or unknown
formula operations are found.

The OCA pattern supports the parent-child intuition: a reusable AEAT report base
can carry common model context, while per-model subclasses customize behavior.
However, this repository should push much more into audited model/casilla
definitions than OCA does, and should avoid unrestricted expression evaluation.

## Design Constraints Implied

- One registry owns model, casilla, formula, validity, source, and legal-basis
  metadata.
- Modelo is the parent context; casillas inherit model context and may add
  casilla-specific legal references and formula references.
- Formula definitions are external data, but executable operations must be a
  small typed DSL or enum-backed operation graph, not arbitrary Python strings.
- Legal values and thresholds are dated values selected by filing period.
- Every registry item must carry legal basis and source references before it can
  be used by calculation code.
- Duplicate definitions and shadowing must be fatal validation errors.
- Hydration that mutates repository source files is incompatible with this
  design. Ingestion may read external source artifacts into reviewed config
  inputs, but runtime code must not rewrite its own legal definitions.
