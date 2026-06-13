---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-persona-fleet-round3-findings-audit]]"
  - "[[2026-05-21-taxpayer-type-applicability-plan]]"
---



# `cli-testimonial` audit: `persona-fleet round 4 — taxpayer-type verification findings`

## Scope

Fourth testimonial batch, run to verify the landed Q1 Wave 1 + Wave 2
taxpayer-type work from the operator side — the schema and the
applicability derivation engine — and to harvest the next layer of
priorities. Three human-persona operators, CLI-only, no source
access, isolated `AEAT_LOCAL_STORAGE_ROOT`, no live rights.

| Persona | Shape exercised |
|---|---|
| Núria Bonet | Landlord — rental-only income, no economic activity |
| Jordi Ferran | First-time autónomo — estimación directa simplificada |
| Carme Vidal | Administradora of a sociedad limitada |

## Findings

### Confirmed positive — the headline defect is fixed

The Q1 applicability engine reasons correctly by taxpayer type. The
round-3 landlord defect is closed: `overview explain 130` returns
`applicable: false` for a pure landlord with a sound, plainly-worded
rationale, and no agenda/backlog ever shows Modelo 130 as overdue.
`explain 100` correctly returns `applicable: true`. For a non-natural
-person profile, `explain 100`/`explain 130` both return
`not_applicable` and point to Modelo 200. The autónomo-by-default
defect is genuinely removed. Modelo 200 calculates end-to-end on the
closest creatable profile.

### BLOCKER — legal-entity profile cannot be created non-interactively

A `--quiet` / flag-driven `config profile create --entity-type
legal_entity` always fails: `Respuesta booleana no válida para
Cónyuge no residente IRPF`. The setup catalogue carries spouse /
personal-IRPF questions that are required with an empty default and
have no `visible_when` excluding a legal entity; `--quiet` cannot
satisfy them and the `--no-` flag is ignored. `natural_person` and
`attribution_entity` create cleanly with the identical command shape
— `legal_entity` is the only broken path. This blocks the entire
corporate-entity stream: no S.L. profile, no IS routing verification.

### BLOCKER — `--legal-entity-form` is misrouted to the income-categories field

`config profile create --entity-type legal_entity --legal-entity-form
sl` fails with `Valor no reconocido para Categorías de renta IRPF:
sl`. The flag whose entire purpose is to record the company's legal
form feeds its value into the `irpf_income_categories` question — an
IRPF-personal concept that does not apply to a company. The
`--legal-entity-form` flag is non-functional; the CLI flag→question
binding is wrong.

### MAJOR — `explain` for an un-ruled modelo contradicts the saved profile

`overview explain 131` on a fully declared profile returns `verdict:
incomplete` with the rationale "el tipo de contribuyente no está
declarado" — while the same output prints the declared `entity_type`
and income categories. The applicability engine emits one INCOMPLETE
message for two distinct causes: a genuinely undeclared taxpayer
model, and a modelo with no seed rule (the seed table covers only
100/130/303/200/202). For a declared profile hitting an un-ruled
modelo the "declare your taxpayer type first" guidance is wrong and
alarming.

### MAJOR — the annual Renta has no deadline, so it never appears in any calendar

`explain 100` says Modelo 100 is applicable, but `calendar`,
`agenda` and `backlog` show zero entries for it — Modelo 100 has no
registered deadline window. Both Núria and Jordi hit this: the tool
tells a taxpayer the Renta applies but never tells them when to
file it. This is round-3 finding R1; remediation is in flight on the
registry track.

### MAJOR — `backlog` invents pre-registration obligations

A taxpayer who registered as autónomo in 2026 is shown `late_count
5`, including three 2025 IVA quarters from before they had any
activity. The deadline engine has no notion of an activity /
registration start date, so it assumes obligations stretch back
indefinitely — frightening a new registrant with phantom overdue
returns and penalties.

### MAJOR — Modelo 202 cannot be calculated

`modelo describe 202` advertises periods `1P/2P/3P`, `work create`
accepts them, but `work calculate` rejects every one with `invalid
registry period '1P'`. Modelo 130 and Modelo 200 calculate normally
— the corporate quarterly payment return is specifically a dead end.

### MAJOR — `--activity` is mandatory for taxpayers with no economic activity

The non-interactive `profile create` makes `--activity` (an
"actividad económica / epígrafe IAE" field) required and rejects an
empty string, forcing a pure landlord, a salaried-only taxpayer or a
pensioner to invent a business they do not have. The profile then
stores a misleading `activities.description` and assigns `iva.regime
= GENERAL`. The taxpayer model already carries the income-category
axis that should make `activity` conditional.

### MINOR

- `explain 200` on an attribution-entity profile returns a
  `not_applicable` rationale that calls the taxpayer "una persona
  física" — inaccurate; an attribution entity is a third entity type.
- `--irpf-income-categories` help says values are "separadas por
  comas", but a comma-separated value is rejected — the real syntax
  is to repeat the flag. Help contradicts behaviour.
- `modelo work create` succeeds for a modelo that `explain` has just
  declared `not_applicable`, with no guard or warning.
- Top-level `aeat --help` hides `explain` / `agenda` / `calendar` /
  `backlog`; only `overview status` is listed. `explain` — the one
  command that directly answers "do I owe this?" — is undiscoverable.
- `overview status`, the profile's advised next step, never mentions
  filing obligations; it reports only workspace plumbing.
- `modelo list` dumps all registered modelos with no "applies to
  you" marker.
- Multi-year `calendar` / `agenda` fails hard (`No registry deadline
  windows registered for year 2027`) instead of degrading.

### Transient — not graded as defects

Both `ImportError: SecureObjectUnreadable` and the earlier
`LockAcquisitionError` crashes were mid-edit windows on the shared
worktree caused by concurrent campaigns extracting error classes;
they were not reproducible once the refactors settled. The personas
caught the CLI between commits. One real robustness note rides on
this: when the import crash fires mid-create, `profile create`
prints `status created` while persisting nothing.

## Recommendations

- **Legal-entity profile BLOCKERs** — gate spouse / personal-IRPF
  setup questions behind a `visible_when` that excludes legal and
  attribution entities; fix the `--legal-entity-form` flag→question
  binding. Tracked as remediation task #38; gates Q1 W02.S08.
- **Applicability rationale** — split the INCOMPLETE message into an
  undeclared-taxpayer-model case and an un-ruled-modelo case; make
  the `not_applicable` rationale accurate for every excluded entity
  type. Tracked as task #39.
- **`--activity` conditionality** — make the activity question
  required only when the taxpayer declares the actividad-económica
  income category or is a legal entity. Folded into task #38.
- **Deadline-engine cluster** — register the missing Modelo 100 /
  303 / 347 windows (R1, in flight, W03.S12); give the deadline
  engine an activity/registration start date so `backlog` stops
  inventing pre-registration obligations; fix the Modelo 202
  describe/create/calculate period-token mismatch; degrade multi-year
  queries gracefully. Tracked as task #40, sequenced after W03.S12.
- **Discoverability MINORs** — surface `explain`/`agenda`/`calendar`
  at top-level help, have `overview status` point at the obligations
  view, mark `modelo list` rows by applicability, and guard
  `work create` against a `not_applicable` modelo. Lower priority;
  batch after the cluster fixes land.
